"""
Payment API Endpoints - Idempotent Payment Processing
"""
import uuid
import json
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import PaymentTransaction, PaymentStateHistory
from app.schemas import (
    PaymentIntentCreate, PaymentIntentResponse,
    WebhookEvent, PaymentStatusResponse
)
from app.observability import (
    tracer, payment_processed_counter, payment_duration,
    webhook_processed_counter
)
from utils.idempotency import (
    generate_idempotency_key,
    check_idempotency_cache,
    check_idempotency_db,
    save_idempotency_record
)
from utils.state_machine import validate_state_transition
from utils.messaging import publish_payment_event

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/intent", response_model=PaymentIntentResponse, status_code=201)
async def create_payment_intent(
    payment_data: PaymentIntentCreate,
    db: Session = Depends(get_db)
):
    """Create a payment intent (simulated)"""
    with payment_duration.time():
        with tracer.start_as_current_span("create_payment_intent") as span:
            span.set_attribute("donation_id", str(payment_data.donation_id))
            span.set_attribute("amount", payment_data.amount)
            span.set_attribute("gateway", payment_data.gateway)
            
            try:
                # Generate payment intent ID (simulated)
                payment_intent_id = f"pi_{uuid.uuid4().hex[:24]}"
                
                # Create payment transaction
                payment = PaymentTransaction(
                    id=uuid.uuid4(),
                    donation_id=payment_data.donation_id,
                    payment_intent_id=payment_intent_id,
                    amount=payment_data.amount,
                    currency=payment_data.currency,
                    status="INITIATED",
                    gateway=payment_data.gateway,
                    gateway_response={"client_secret": f"{payment_intent_id}_secret_xxx"}
                )
                
                db.add(payment)
                db.commit()
                db.refresh(payment)
                
                # Update metrics
                payment_processed_counter.labels(
                    status="INITIATED",
                    gateway=payment_data.gateway
                ).inc()
                
                span.set_attribute("payment_id", str(payment.id))
                span.set_attribute("status", "success")
                
                return PaymentIntentResponse(
                    id=payment.id,
                    payment_intent_id=payment.payment_intent_id,
                    donation_id=payment.donation_id,
                    amount=float(payment.amount),
                    currency=payment.currency,
                    status=payment.status,
                    gateway=payment.gateway,
                    client_secret=payment.gateway_response.get("client_secret"),
                    created_at=payment.created_at
                )
                
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                raise HTTPException(status_code=500, detail=f"Failed to create payment intent: {str(e)}")


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handle payment gateway webhooks with IDEMPOTENCY
    
    This endpoint ensures exactly-once processing even if the gateway
    retries the webhook multiple times.
    """
    with tracer.start_as_current_span("handle_webhook") as span:
        try:
            # Get request body
            body = await request.body()
            body_str = body.decode()
            
            # Generate idempotency key from body if not provided
            if not x_idempotency_key:
                x_idempotency_key = generate_idempotency_key(body_str)
            
            span.set_attribute("idempotency_key", x_idempotency_key)
            
            # L1: Check Redis cache (FAST PATH - <10ms)
            cached_response = check_idempotency_cache(x_idempotency_key)
            if cached_response:
                span.set_attribute("idempotency_hit", "redis")
                webhook_processed_counter.labels(
                    status="cached",
                    idempotency_hit="redis"
                ).inc()
                body, status = cached_response
                return Response(content=body, status_code=status, media_type="application/json")
            
            # L2: Check DB (SLOWER PATH - <50ms)
            db_response = check_idempotency_db(x_idempotency_key, db)
            if db_response:
                span.set_attribute("idempotency_hit", "database")
                webhook_processed_counter.labels(
                    status="cached",
                    idempotency_hit="database"
                ).inc()
                body, status = db_response
                return Response(content=body, status_code=status, media_type="application/json")
            
            # Process webhook (FIRST TIME)
            span.set_attribute("idempotency_hit", "none")
            
            event_data = json.loads(body_str)
            webhook_event = WebhookEvent(**event_data)
            
            span.set_attribute("event_type", webhook_event.event_type)
            span.set_attribute("payment_intent_id", webhook_event.payment_intent_id)
            span.set_attribute("new_status", webhook_event.status)
            
            # Find payment transaction with row lock
            payment = db.query(PaymentTransaction).filter_by(
                payment_intent_id=webhook_event.payment_intent_id
            ).with_for_update().first()
            
            if not payment:
                error_response = json.dumps({"error": "Payment not found"})
                save_idempotency_record(x_idempotency_key, error_response, 404, db)
                return Response(content=error_response, status_code=404, media_type="application/json")
            
            span.set_attribute("payment_id", str(payment.id))
            span.set_attribute("current_status", payment.status)
            
            # Check if event is out of order (older than current state)
            if webhook_event.timestamp < payment.updated_at:
                span.set_attribute("out_of_order", True)
                print(f"⚠️  Ignoring out-of-order event: {webhook_event.event_type}")
                
                response_body = json.dumps({
                    "status": "ignored",
                    "reason": "out_of_order",
                    "message": "Event is older than current state"
                })
                save_idempotency_record(x_idempotency_key, response_body, 200, db)
                
                webhook_processed_counter.labels(
                    status="ignored",
                    idempotency_hit="none"
                ).inc()
                
                return Response(content=response_body, status_code=200, media_type="application/json")
            
            # Validate state transition
            if not validate_state_transition(payment.status, webhook_event.status):
                span.set_attribute("invalid_transition", True)
                error_msg = f"Invalid state transition: {payment.status} -> {webhook_event.status}"
                print(f"✗ {error_msg}")
                
                response_body = json.dumps({
                    "status": "rejected",
                    "reason": "invalid_transition",
                    "message": error_msg
                })
                save_idempotency_record(x_idempotency_key, response_body, 400, db)
                
                webhook_processed_counter.labels(
                    status="rejected",
                    idempotency_hit="none"
                ).inc()
                
                return Response(content=response_body, status_code=400, media_type="application/json")
            
            # Update payment status with optimistic locking
            old_status = payment.status
            payment.status = webhook_event.status
            payment.version += 1
            payment.updated_at = webhook_event.timestamp
            if webhook_event.data:
                payment.gateway_response = webhook_event.data
            
            # Log state transition
            state_history = PaymentStateHistory(
                payment_id=payment.id,
                from_status=old_status,
                to_status=webhook_event.status,
                event_id=x_idempotency_key,
                event_timestamp=webhook_event.timestamp,
                version=payment.version
            )
            db.add(state_history)
            
            db.commit()
            db.refresh(payment)
            
            # Publish event
            event_type = f"PaymentStatus.{webhook_event.status}"
            publish_payment_event(payment, event_type)
            
            # Update metrics
            payment_processed_counter.labels(
                status=webhook_event.status,
                gateway=payment.gateway
            ).inc()
            
            webhook_processed_counter.labels(
                status="processed",
                idempotency_hit="none"
            ).inc()
            
            # Prepare response
            response_body = json.dumps({
                "status": "processed",
                "payment_id": str(payment.id),
                "old_status": old_status,
                "new_status": payment.status,
                "version": payment.version
            })
            
            # Save idempotency record
            save_idempotency_record(x_idempotency_key, response_body, 200, db)
            
            span.set_attribute("status", "success")
            print(f"✓ Webhook processed: {webhook_event.event_type} - {old_status} -> {payment.status}")
            
            return Response(content=response_body, status_code=200, media_type="application/json")
            
        except Exception as e:
            db.rollback()
            span.set_attribute("status", "error")
            span.set_attribute("error", str(e))
            
            error_response = json.dumps({"error": str(e)})
            return Response(content=error_response, status_code=500, media_type="application/json")


@router.get("/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get payment status"""
    with tracer.start_as_current_span("get_payment_status") as span:
        span.set_attribute("payment_id", str(payment_id))
        
        payment = db.query(PaymentTransaction).filter(
            PaymentTransaction.id == payment_id
        ).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        return PaymentStatusResponse.from_orm(payment)


@router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Initiate payment refund"""
    with tracer.start_as_current_span("refund_payment") as span:
        span.set_attribute("payment_id", str(payment_id))
        
        payment = db.query(PaymentTransaction).filter(
            PaymentTransaction.id == payment_id
        ).with_for_update().first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        if payment.status != "CAPTURED":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot refund payment in status: {payment.status}"
            )
        
        # Simulate refund processing
        from datetime import datetime
        payment.status = "REFUNDED"
        payment.version += 1
        payment.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Publish event
        publish_payment_event(payment, "PaymentRefunded")
        
        return {"status": "success", "message": "Refund initiated"}


