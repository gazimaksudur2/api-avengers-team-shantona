"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field


class PaymentIntentCreate(BaseModel):
    """Schema for creating a payment intent"""
    donation_id: uuid.UUID
    amount: float = Field(gt=0, le=1000000)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    gateway: str = Field(default="stripe", pattern="^(stripe|paypal)$")


class PaymentIntentResponse(BaseModel):
    """Schema for payment intent response"""
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
    """Schema for webhook event"""
    event_type: str
    payment_intent_id: str
    status: str
    timestamp: datetime
    data: Optional[Dict] = None


class PaymentStatusResponse(BaseModel):
    """Schema for payment status response"""
    id: uuid.UUID
    payment_intent_id: str
    status: str
    amount: float
    currency: str
    version: int
    updated_at: datetime

    class Config:
        from_attributes = True


