"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator


class DonationCreate(BaseModel):
    """Schema for creating a donation"""
    campaign_id: uuid.UUID
    donor_email: EmailStr
    amount: float = Field(gt=0, le=1000000)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    extra_data: Optional[dict] = None

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        if v > 1000000:
            raise ValueError('Amount exceeds maximum limit')
        return round(v, 2)


class DonationResponse(BaseModel):
    """Schema for donation response"""
    id: uuid.UUID
    campaign_id: uuid.UUID
    donor_email: str
    amount: float
    currency: str
    status: str
    payment_intent_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    version: int

    class Config:
        from_attributes = True


class DonationStatusUpdate(BaseModel):
    """Schema for updating donation status"""
    status: str = Field(pattern="^(PENDING|COMPLETED|FAILED|REFUNDED)$")
    payment_intent_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Schema for health check response"""
    status: str
    service: str
    timestamp: datetime
    checks: dict


