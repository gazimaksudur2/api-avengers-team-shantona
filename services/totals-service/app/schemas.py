"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CampaignTotals(BaseModel):
    """Schema for campaign totals response"""
    campaign_id: uuid.UUID
    total_donations: int
    total_amount: float
    unique_donors: int
    last_updated: datetime
    data_source: str  # redis, materialized_view, realtime
    cache_age_seconds: Optional[float] = None


class HealthResponse(BaseModel):
    """Schema for health check response"""
    status: str
    service: str
    timestamp: datetime
    checks: dict

