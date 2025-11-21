"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class NotificationCreate(BaseModel):
    """Schema for creating a notification"""
    donation_id: uuid.UUID
    recipient: EmailStr
    type: str = "EMAIL"
    template_id: Optional[str] = "donation_confirmation"
    payload: Optional[dict] = None


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    id: uuid.UUID
    donation_id: uuid.UUID
    recipient: str
    type: str
    status: str
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

