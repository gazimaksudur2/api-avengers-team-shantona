"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class CampaignCreate(BaseModel):
    """Schema for creating a campaign"""
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    goal_amount: float = Field(gt=0, le=10000000)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    end_date: Optional[datetime] = None
    organization: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=500)
    created_by: Optional[uuid.UUID] = None

    @validator('goal_amount')
    def validate_goal_amount(cls, v):
        if v <= 0:
            raise ValueError('Goal amount must be positive')
        return round(v, 2)


class CampaignUpdate(BaseModel):
    """Schema for updating a campaign"""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    goal_amount: Optional[float] = Field(None, gt=0, le=10000000)
    status: Optional[str] = Field(None, pattern="^(ACTIVE|PAUSED|COMPLETED|CANCELLED)$")
    end_date: Optional[datetime] = None
    organization: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=500)


class CampaignResponse(BaseModel):
    """Schema for campaign response"""
    id: uuid.UUID
    title: str
    description: Optional[str]
    goal_amount: float
    currency: str
    status: str
    start_date: datetime
    end_date: Optional[datetime]
    organization: Optional[str]
    category: Optional[str]
    image_url: Optional[str]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    version: int

    class Config:
        from_attributes = True

