"""
Totals API Endpoints - Multi-Level Caching
"""
import uuid
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CampaignTotals
from app.observability import tracer, totals_requests_total, totals_calculation_duration
from utils.caching import (
    get_totals_from_cache,
    get_totals_from_materialized_view,
    get_totals_realtime,
    set_totals_cache,
    invalidate_cache,
    refresh_materialized_view
)

router = APIRouter(prefix="/api/v1/totals", tags=["totals"])


@router.get("/campaigns/{campaign_id}", response_model=CampaignTotals)
async def get_campaign_totals(
    campaign_id: uuid.UUID,
    realtime: bool = Query(False, description="Force real-time calculation"),
    db: Session = Depends(get_db)
):
    """
    Get campaign totals with multi-level caching
    
    **Caching Strategy:**
    - **L1 (Redis)**: 30s TTL, ultra-fast (<10ms)
    - **L2 (Materialized View)**: Refreshed periodically, fast (<30ms)
    - **L3 (Base Table)**: Real-time calculation, accurate (<100ms)
    
    **Query Parameters:**
    - `realtime`: Force real-time calculation, bypassing cache
    
    **Returns:**
    - Campaign totals with data source indicator
    """
    with tracer.start_as_current_span("get_campaign_totals") as span:
        span.set_attribute("campaign_id", str(campaign_id))
        span.set_attribute("realtime_mode", realtime)
        
        # If realtime mode requested, skip cache
        if realtime:
            with totals_calculation_duration.labels(source="realtime").time():
                data = get_totals_realtime(campaign_id, db)
            
            totals_requests_total.labels(
                campaign_id=str(campaign_id),
                cache_hit="none"
            ).inc()
            
            span.set_attribute("data_source", "realtime")
            return CampaignTotals(**data)
        
        # Try L1: Redis cache
        cached_data = get_totals_from_cache(campaign_id)
        if cached_data:
            totals_requests_total.labels(
                campaign_id=str(campaign_id),
                cache_hit="redis"
            ).inc()
            span.set_attribute("data_source", "redis")
            return CampaignTotals(**cached_data)
        
        # Try L2: Materialized view
        with totals_calculation_duration.labels(source="materialized_view").time():
            mv_data = get_totals_from_materialized_view(campaign_id, db)
        
        if mv_data:
            # Populate Redis cache
            set_totals_cache(campaign_id, mv_data)
            
            totals_requests_total.labels(
                campaign_id=str(campaign_id),
                cache_hit="materialized_view"
            ).inc()
            span.set_attribute("data_source", "materialized_view")
            return CampaignTotals(**mv_data)
        
        # Fallback to L3: Real-time calculation
        with totals_calculation_duration.labels(source="realtime").time():
            data = get_totals_realtime(campaign_id, db)
        
        # Populate cache
        set_totals_cache(campaign_id, data)
        
        totals_requests_total.labels(
            campaign_id=str(campaign_id),
            cache_hit="none"
        ).inc()
        span.set_attribute("data_source", "realtime")
        
        return CampaignTotals(**data)


@router.post("/refresh")
async def refresh_totals(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Refresh materialized view (internal endpoint)
    
    Triggers a concurrent refresh of the materialized view in the background.
    """
    with tracer.start_as_current_span("refresh_totals"):
        try:
            # Run in background to avoid blocking
            background_tasks.add_task(refresh_materialized_view, db)
            return {"status": "scheduled", "message": "Materialized view refresh scheduled"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to refresh: {str(e)}")


@router.delete("/cache/{campaign_id}")
async def invalidate_campaign_cache(campaign_id: uuid.UUID):
    """
    Invalidate cache for a campaign (internal endpoint)
    
    Removes the campaign totals from Redis cache, forcing a fresh calculation.
    """
    with tracer.start_as_current_span("invalidate_cache"):
        try:
            invalidate_cache(campaign_id)
            return {"status": "success", "message": f"Cache invalidated for campaign {campaign_id}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")

