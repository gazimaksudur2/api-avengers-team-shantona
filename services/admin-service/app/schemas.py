"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Schema for admin login"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"


class DashboardMetrics(BaseModel):
    """Schema for dashboard metrics"""
    total_donations: int
    total_amount: float
    total_campaigns: int
    active_campaigns: int
    total_donors: int
    avg_donation_amount: float
    donations_today: int
    last_updated: datetime


class SystemHealthResponse(BaseModel):
    """Schema for system-wide health check"""
    overall_status: str
    services: dict
    timestamp: datetime


class DonationSummary(BaseModel):
    """Schema for donation summary"""
    id: uuid.UUID
    campaign_id: uuid.UUID
    donor_email: str
    amount: float
    currency: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

