"""
Payment Service - Payment processing with Idempotency and State Machine

Key Features:
1. Idempotency: Redis + DB backed deduplication for webhooks
2. State Machine: Validates state transitions with versioning
3. Event Ordering: Uses event timestamps to handle out-of-order webhooks
"""
import os
import uuid
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, String, Numeric, DateTime, Integer, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import redis
import pika

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/payments_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "payment-service")
# STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "sk_test_dummy")
# WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "whsec_dummy")

# Database setup
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

# Prometheus metrics
payment_processed_counter = Counter(
    'payment_processed_total',
    'Total number of payments processed',
    ['status', 'gateway']
)
webhook_processed_counter = Counter(
    'webhook_processed_total',
    'Total number of webhooks processed',
    ['status', 'idempotency_hit']
)
payment_duration = Histogram(
    'payment_processing_duration_seconds',
    'Time spent processing payments'
)
idempotency_cache_hits = Counter(
    'idempotency_cache_hits_total',
    'Number of idempotency cache hits',
    ['cache_type']
)

# ==================
# State Machine Configuration
# ==================
VALID_TRANSITIONS = {
    "INITIATED": ["AUTHORIZED", "FAILED"],
    "AUTHORIZED": ["CAPTURED", "FAILED", "REFUNDED"],
    "CAPTURED": ["REFUNDED"],
    "FAILED": [],
    "REFUNDED": []
}

# ==================
# Database Models
# ==================
class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    donation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    payment_intent_id = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False, index=True)
    gateway = Column(String(50), nullable=False)
    gateway_response = Column(JSONB, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_payment_status', 'status'),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    key = Column(String(255), primary_key=True)
    response_body = Column(String, nullable=False)
    response_status = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_idempotency_expires', 'expires_at'),
    )


class PaymentStateHistory(Base):
    __tablename__ = "payment_state_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    event_id = Column(String(255), nullable=True, index=True)
    event_timestamp = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    version = Column(Integer, nullable=False)


# Create tables
Base.metadata.create_all(bind=engine)

# ==================
# Pydantic Models
# ==================
class PaymentIntentCreate(BaseModel):
    donation_id: uuid.UUID
    amount: float = Field(gt=0, le=1000000)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    gateway: str = Field(default="stripe", pattern="^(stripe|paypal)$")


class PaymentIntentResponse(BaseModel):
    id: uuid.UUID
    payment_intent_id: str
    donation_id: uuid.UUID
    amount: float
    currency: str
    status: str
    gateway: str
    client_secret: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookEvent(BaseModel):
    event_type: str
    payment_intent_id: str
    status: str
    timestamp: datetime
    data: Optional[Dict] = None


class PaymentStatusResponse(BaseModel):
    id: uuid.UUID
    payment_intent_id: str
    status: str
    amount: float
    currency: str
    version: int
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================
# Dependencies
# ==================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================
# Application
# ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting {SERVICE_NAME}...")
    yield
    # Shutdown
    print(f"Shutting down {SERVICE_NAME}...")


app = FastAPI(
    title="Payment Service",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================
# Helper Functions
# ==================
def generate_idempotency_key(content: str) -> str:
    """Generate idempotency key from content"""
    return hashlib.sha256(content.encode()).hexdigest()


def check_idempotency_cache(key: str) -> Optional[tuple]:
    """Check Redis cache for idempotency key"""
    cached = redis_client.get(f"idem:{key}")
    if cached:
        idempotency_cache_hits.labels(cache_type="redis").inc()
        data = json.loads(cached)
        return (data["body"], data["status"])
    return None


def save_idempotency_record(key: str, response_body: str, status: int, db: Session):
    """Save idempotency record to both Redis and DB"""
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Save to Redis (fast path)
    redis_client.setex(
        f"idem:{key}",
        86400,  # 24 hours
        json.dumps({"body": response_body, "status": status})
    )
    
    # Save to DB (persistent)
    idem_record = IdempotencyKey(
        key=key,
        response_body=response_body,
        response_status=status,
        expires_at=expires_at
    )
    try:
        db.add(idem_record)
        db.commit()
    except IntegrityError:
        # Already exists, that's fine
        db.rollback()


def validate_state_transition(current_status: str, new_status: str) -> bool:
    """Validate if state transition is allowed"""
    return new_status in VALID_TRANSITIONS.get(current_status, [])


def publish_payment_event(payment: PaymentTransaction, event_type: str):
    """Publish payment event to RabbitMQ"""
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        
        channel.exchange_declare(
            exchange='payments.events',
            exchange_type='topic',
            durable=True
        )
        
        message = json.dumps({
            "event_type": event_type,
            "payment_id": str(payment.id),
            "donation_id": str(payment.donation_id),
            "payment_intent_id": payment.payment_intent_id,
            "status": payment.status,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        routing_key = f"payment.{event_type.lower()}"
        channel.basic_publish(
            exchange='payments.events',
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json'
            )
        )
        
        connection.close()
        print(f"✓ Published payment event: {event_type}")
        
    except Exception as e:
        print(f"✗ Failed to publish payment event: {e}")


# ==================
# API Endpoints
# ==================
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    checks = {}
    
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
    try:
        redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
    
    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    
    return {
        "status": overall_status,
        "service": SERVICE_NAME,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/payments/intent", response_model=PaymentIntentResponse, status_code=201)
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


@app.post("/api/v1/payments/webhook")
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
            
            # Check Redis cache first (FAST PATH)
            cached_response = check_idempotency_cache(x_idempotency_key)
            if cached_response:
                span.set_attribute("idempotency_hit", "redis")
                webhook_processed_counter.labels(
                    status="cached",
                    idempotency_hit="redis"
                ).inc()
                body, status = cached_response
                return Response(content=body, status_code=status, media_type="application/json")
            
            # Check DB (SLOWER PATH)
            existing = db.query(IdempotencyKey).filter_by(key=x_idempotency_key).first()
            if existing:
                span.set_attribute("idempotency_hit", "database")
                webhook_processed_counter.labels(
                    status="cached",
                    idempotency_hit="database"
                ).inc()
                # Populate Redis cache
                redis_client.setex(
                    f"idem:{x_idempotency_key}",
                    86400,
                    json.dumps({"body": existing.response_body, "status": existing.response_status})
                )
                return Response(
                    content=existing.response_body,
                    status_code=existing.response_status,
                    media_type="application/json"
                )
            
            # Process webhook (FIRST TIME)
            span.set_attribute("idempotency_hit", "none")
            
            event_data = json.loads(body_str)
            webhook_event = WebhookEvent(**event_data)
            
            span.set_attribute("event_type", webhook_event.event_type)
            span.set_attribute("payment_intent_id", webhook_event.payment_intent_id)
            span.set_attribute("new_status", webhook_event.status)
            
            # Find payment transaction
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
                print(f"⚠️  Ignoring out-of-order event: {webhook_event.event_type} "
                      f"(event: {webhook_event.timestamp}, current: {payment.updated_at})")
                
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


@app.get("/api/v1/payments/{payment_id}", response_model=PaymentStatusResponse)
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


@app.post("/api/v1/payments/{payment_id}/refund")
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
        payment.status = "REFUNDED"
        payment.version += 1
        payment.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Publish event
        publish_payment_event(payment, "PaymentRefunded")
        
        return {"status": "success", "message": "Refund initiated"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

