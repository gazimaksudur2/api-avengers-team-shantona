"""
Donation API Endpoints
"""
import uuid
import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_redis
from app.models import Donation
from app.schemas import DonationCreate, DonationResponse, DonationStatusUpdate
from app.observability import (
    tracer, donation_created_counter, donation_duration, http_requests_total
)
from utils.outbox import create_outbox_event
from pydantic import EmailStr

router = APIRouter(prefix="/api/v1/donations", tags=["donations"])


@router.post("", response_model=DonationResponse, status_code=201)
async def create_donation(
    donation_data: DonationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new donation pledge with Transactional Outbox pattern
    
    This ensures that both the donation record and the event are written
    atomically in a single transaction, preventing lost donations.
    """
    with donation_duration.time():
        with tracer.start_as_current_span("create_donation") as span:
            span.set_attribute("campaign_id", str(donation_data.campaign_id))
            span.set_attribute("amount", donation_data.amount)
            
            try:
                # Start transaction
                donation = Donation(
                    id=uuid.uuid4(),
                    campaign_id=donation_data.campaign_id,
                    donor_email=donation_data.donor_email,
                    amount=donation_data.amount,
                    currency=donation_data.currency,
                    status="PENDING",
                    extra_data=donation_data.extra_data
                )
                
                db.add(donation)
                db.flush()  # Get the ID without committing
                
                # Create outbox event in SAME transaction
                create_outbox_event(db, donation, "DonationCreated")
                
                # Commit both atomically
                db.commit()
                db.refresh(donation)
                
                # Update metrics
                donation_created_counter.labels(
                    campaign_id=str(donation.campaign_id),
                    status=donation.status
                ).inc()
                
                http_requests_total.labels(
                    method="POST",
                    endpoint="/api/v1/donations",
                    status="201"
                ).inc()
                
                span.set_attribute("donation_id", str(donation.id))
                span.set_attribute("status", "success")
                
                return DonationResponse.from_orm(donation)
                
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                http_requests_total.labels(
                    method="POST",
                    endpoint="/api/v1/donations",
                    status="500"
                ).inc()
                raise HTTPException(status_code=500, detail=f"Failed to create donation: {str(e)}")


@router.get("/{donation_id}", response_model=DonationResponse)
async def get_donation(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get donation details by ID"""
    with tracer.start_as_current_span("get_donation") as span:
        span.set_attribute("donation_id", str(donation_id))
        
        # Try cache first
        redis_client = get_redis()
        cache_key = f"donation:{donation_id}"
        cached = redis_client.get(cache_key)
        
        if cached:
            span.set_attribute("cache_hit", True)
            return json.loads(cached)
        
        span.set_attribute("cache_hit", False)
        donation = db.query(Donation).filter(Donation.id == donation_id).first()
        
        if not donation:
            http_requests_total.labels(
                method="GET",
                endpoint="/api/v1/donations/:id",
                status="404"
            ).inc()
            raise HTTPException(status_code=404, detail="Donation not found")
        
        response = DonationResponse.from_orm(donation)
        
        # Cache for 5 minutes
        redis_client.setex(
            cache_key,
            300,
            json.dumps(response.dict(), default=str)
        )
        
        http_requests_total.labels(
            method="GET",
            endpoint="/api/v1/donations/:id",
            status="200"
        ).inc()
        
        return response


@router.get("/history", response_model=List[DonationResponse])
async def get_donation_history(
    donor_email: EmailStr = Query(..., description="Donor email address"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get donation history for a donor"""
    with tracer.start_as_current_span("get_donation_history") as span:
        span.set_attribute("donor_email", donor_email)
        
        donations = db.query(Donation)\
            .filter(Donation.donor_email == donor_email)\
            .order_by(Donation.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        span.set_attribute("result_count", len(donations))
        
        http_requests_total.labels(
            method="GET",
            endpoint="/api/v1/donations/history",
            status="200"
        ).inc()
        
        return [DonationResponse.from_orm(d) for d in donations]


@router.patch("/{donation_id}/status", response_model=DonationResponse)
async def update_donation_status(
    donation_id: uuid.UUID,
    status_update: DonationStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Update donation status (internal endpoint, called by payment service)
    """
    with tracer.start_as_current_span("update_donation_status") as span:
        span.set_attribute("donation_id", str(donation_id))
        span.set_attribute("new_status", status_update.status)
        
        try:
            donation = db.query(Donation).filter(Donation.id == donation_id).first()
            
            if not donation:
                http_requests_total.labels(
                    method="PATCH",
                    endpoint="/api/v1/donations/:id/status",
                    status="404"
                ).inc()
                raise HTTPException(status_code=404, detail="Donation not found")
            
            old_status = donation.status
            donation.status = status_update.status
            if status_update.payment_intent_id:
                donation.payment_intent_id = status_update.payment_intent_id
            donation.version += 1
            donation.updated_at = datetime.utcnow()
            
            # Create outbox event for status change
            event_type = f"DonationStatusChanged.{status_update.status}"
            create_outbox_event(db, donation, event_type)
            
            db.commit()
            db.refresh(donation)
            
            # Invalidate cache
            redis_client = get_redis()
            cache_key = f"donation:{donation_id}"
            redis_client.delete(cache_key)
            
            # Update metrics
            donation_created_counter.labels(
                campaign_id=str(donation.campaign_id),
                status=donation.status
            ).inc()
            
            http_requests_total.labels(
                method="PATCH",
                endpoint="/api/v1/donations/:id/status",
                status="200"
            ).inc()
            
            span.set_attribute("old_status", old_status)
            span.set_attribute("status", "success")
            
            return DonationResponse.from_orm(donation)
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            span.set_attribute("status", "error")
            span.set_attribute("error", str(e))
            http_requests_total.labels(
                method="PATCH",
                endpoint="/api/v1/donations/:id/status",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=f"Failed to update donation: {str(e)}")


