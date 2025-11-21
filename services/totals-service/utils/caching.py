"""
Multi-Level Caching Utilities

Implements a 3-tier caching strategy:
- L1: Redis (ultra-fast, 30s TTL)
- L2: Materialized View (fast, refreshed periodically)
- L3: Base Table (real-time, accurate)
"""
import json
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.dependencies import get_redis
from app.observability import (
    tracer, cache_hit_ratio, totals_calculation_duration,
    materialized_view_age
)
from app.config import settings


def get_totals_from_cache(campaign_id: uuid.UUID) -> Optional[dict]:
    """
    Get totals from Redis cache (L1 - Fastest)
    
    Args:
        campaign_id: Campaign UUID
    
    Returns:
        Cached totals dict if found, None otherwise
    """
    with tracer.start_as_current_span("get_from_cache") as span:
        span.set_attribute("campaign_id", str(campaign_id))
        
        redis_client = get_redis()
        cache_key = f"campaign_totals:{campaign_id}"
        cached = redis_client.get(cache_key)
        
        if cached:
            span.set_attribute("cache_hit", True)
            cache_hit_ratio.labels(cache_type="redis").set(1.0)
            return json.loads(cached)
        
        span.set_attribute("cache_hit", False)
        cache_hit_ratio.labels(cache_type="redis").set(0.0)
        return None


def get_totals_from_materialized_view(campaign_id: uuid.UUID, db: Session) -> Optional[dict]:
    """
    Get totals from materialized view (L2 - Fast)
    
    Args:
        campaign_id: Campaign UUID
        db: Database session
    
    Returns:
        Totals from materialized view if found, None otherwise
    """
    with tracer.start_as_current_span("get_from_materialized_view") as span:
        span.set_attribute("campaign_id", str(campaign_id))
        
        try:
            result = db.execute(text("""
                SELECT 
                    campaign_id,
                    total_donations,
                    total_amount,
                    unique_donors,
                    last_updated
                FROM campaign_totals
                WHERE campaign_id = :campaign_id
            """), {"campaign_id": str(campaign_id)}).fetchone()
            
            if result:
                span.set_attribute("found", True)
                cache_hit_ratio.labels(cache_type="materialized_view").set(1.0)
                
                age = (datetime.utcnow() - result[4]).total_seconds()
                materialized_view_age.set(age)
                
                return {
                    "campaign_id": result[0],
                    "total_donations": result[1],
                    "total_amount": float(result[2]),
                    "unique_donors": result[3],
                    "last_updated": result[4].isoformat(),
                    "data_source": "materialized_view",
                    "cache_age_seconds": age
                }
            
            span.set_attribute("found", False)
            cache_hit_ratio.labels(cache_type="materialized_view").set(0.0)
            return None
            
        except Exception as e:
            span.set_attribute("error", str(e))
            print(f"Error querying materialized view: {e}")
            return None


def get_totals_realtime(campaign_id: uuid.UUID, db: Session) -> dict:
    """
    Get totals from base table (L3 - Real-time, accurate)
    
    Args:
        campaign_id: Campaign UUID
        db: Database session
    
    Returns:
        Real-time totals calculated from base table
    """
    with tracer.start_as_current_span("get_realtime_totals") as span:
        span.set_attribute("campaign_id", str(campaign_id))
        
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total_donations,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(DISTINCT donor_email) as unique_donors,
                MAX(updated_at) as last_updated
            FROM donations
            WHERE campaign_id = :campaign_id AND status = 'COMPLETED'
        """), {"campaign_id": str(campaign_id)}).fetchone()
        
        return {
            "campaign_id": str(campaign_id),
            "total_donations": result[0],
            "total_amount": float(result[1]),
            "unique_donors": result[2],
            "last_updated": result[3].isoformat() if result[3] else datetime.utcnow().isoformat(),
            "data_source": "realtime",
            "cache_age_seconds": 0
        }


def set_totals_cache(campaign_id: uuid.UUID, data: dict):
    """
    Set totals in Redis cache
    
    Args:
        campaign_id: Campaign UUID
        data: Totals data to cache
    """
    redis_client = get_redis()
    cache_key = f"campaign_totals:{campaign_id}"
    redis_client.setex(cache_key, settings.cache_ttl, json.dumps(data))


def invalidate_cache(campaign_id: uuid.UUID):
    """
    Invalidate cache for a campaign
    
    Args:
        campaign_id: Campaign UUID
    """
    redis_client = get_redis()
    cache_key = f"campaign_totals:{campaign_id}"
    redis_client.delete(cache_key)
    print(f"✓ Invalidated cache for campaign {campaign_id}")


def refresh_materialized_view(db: Session):
    """
    Refresh the materialized view
    
    Uses CONCURRENT refresh to avoid locking the view.
    
    Args:
        db: Database session
    """
    with tracer.start_as_current_span("refresh_materialized_view"):
        try:
            db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY campaign_totals"))
            db.commit()
            print("✓ Materialized view refreshed")
        except Exception as e:
            print(f"✗ Failed to refresh materialized view: {e}")
            db.rollback()

