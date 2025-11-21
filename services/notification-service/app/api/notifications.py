"""
Notification API Endpoints
"""
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification
from app.schemas import NotificationCreate, NotificationResponse
from app.observability import tracer, notifications_sent_counter, notification_duration
from utils.email import send_email

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post("/send", response_model=NotificationResponse, status_code=201)
async def send_notification(
    notification_data: NotificationCreate,
    db: Session = Depends(get_db)
):
    """
    Send a notification (internal endpoint)
    
    Called by other services to trigger notifications.
    """
    with notification_duration.time():
        with tracer.start_as_current_span("send_notification") as span:
            span.set_attribute("donation_id", str(notification_data.donation_id))
            span.set_attribute("recipient", notification_data.recipient)
            
            try:
                # Create notification record
                notification = Notification(
                    id=uuid.uuid4(),
                    donation_id=notification_data.donation_id,
                    recipient=notification_data.recipient,
                    type=notification_data.type,
                    status="PENDING",
                    template_id=notification_data.template_id,
                    payload=notification_data.payload
                )
                
                db.add(notification)
                db.commit()
                db.refresh(notification)
                
                # Send notification
                if notification_data.type == "EMAIL":
                    success = send_email(
                        recipient=notification_data.recipient,
                        template_id=notification_data.template_id,
                        data=notification_data.payload or {}
                    )
                    
                    notification.status = "SENT" if success else "FAILED"
                    if success:
                        notification.sent_at = datetime.utcnow()
                    
                    db.commit()
                    db.refresh(notification)
                
                # Update metrics
                notifications_sent_counter.labels(
                    type=notification_data.type,
                    status=notification.status
                ).inc()
                
                span.set_attribute("status", "success")
                
                return NotificationResponse.from_orm(notification)
                
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


@router.get("/{donation_id}", response_model=List[NotificationResponse])
async def get_notifications(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get notifications for a donation"""
    with tracer.start_as_current_span("get_notifications") as span:
        span.set_attribute("donation_id", str(donation_id))
        
        notifications = db.query(Notification)\
            .filter(Notification.donation_id == donation_id)\
            .order_by(Notification.created_at.desc())\
            .all()
        
        span.set_attribute("count", len(notifications))
        
        return [NotificationResponse.from_orm(n) for n in notifications]

