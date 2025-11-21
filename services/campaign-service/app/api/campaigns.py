"""
Campaign API Endpoints - CRUD Operations
"""
import uuid
import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.dependencies import get_redis
from app.models import Campaign
from app.schemas import CampaignCreate, CampaignUpdate, CampaignResponse
from app.observability import (
    tracer, campaigns_created_counter, campaign_operations_duration
)
from utils.events import publish_campaign_event

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: CampaignCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new campaign
    
    Publishes "CampaignCreated" event to RabbitMQ
    """
    with campaign_operations_duration.labels(operation="create").time():
        with tracer.start_as_current_span("create_campaign") as span:
            span.set_attribute("campaign_title", campaign_data.title)
            span.set_attribute("goal_amount", campaign_data.goal_amount)
            
            try:
                campaign = Campaign(
                    id=uuid.uuid4(),
                    title=campaign_data.title,
                    description=campaign_data.description,
                    goal_amount=campaign_data.goal_amount,
                    currency=campaign_data.currency,
                    status="ACTIVE",
                    end_date=campaign_data.end_date,
                    organization=campaign_data.organization,
                    category=campaign_data.category,
                    image_url=campaign_data.image_url,
                    created_by=campaign_data.created_by
                )
                
                db.add(campaign)
                db.commit()
                db.refresh(campaign)
                
                # Publish event
                publish_campaign_event(campaign, "CampaignCreated")
                
                # Update metrics
                campaigns_created_counter.labels(
                    category=campaign.category or "uncategorized",
                    status=campaign.status
                ).inc()
                
                span.set_attribute("campaign_id", str(campaign.id))
                span.set_attribute("status", "success")
                
                return CampaignResponse.from_orm(campaign)
                
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                raise HTTPException(status_code=500, detail=f"Failed to create campaign: {str(e)}")


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get campaign by ID (with caching)"""
    with tracer.start_as_current_span("get_campaign") as span:
        span.set_attribute("campaign_id", str(campaign_id))
        
        # Try cache first
        redis_client = get_redis()
        cache_key = f"campaign:{campaign_id}"
        cached = redis_client.get(cache_key)
        
        if cached:
            span.set_attribute("cache_hit", True)
            return json.loads(cached)
        
        span.set_attribute("cache_hit", False)
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        response = CampaignResponse.from_orm(campaign)
        
        # Cache for 5 minutes
        redis_client.setex(
            cache_key,
            300,
            json.dumps(response.dict(), default=str)
        )
        
        return response


@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    status: Optional[str] = Query(None, pattern="^(ACTIVE|PAUSED|COMPLETED|CANCELLED)$"),
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List campaigns with filters
    
    Query Parameters:
    - status: Filter by campaign status
    - category: Filter by category
    - search: Search in title and description
    - limit: Number of results (max 100)
    - offset: Pagination offset
    """
    with tracer.start_as_current_span("list_campaigns") as span:
        query = db.query(Campaign)
        
        if status:
            query = query.filter(Campaign.status == status)
            span.set_attribute("filter_status", status)
        
        if category:
            query = query.filter(Campaign.category == category)
            span.set_attribute("filter_category", category)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Campaign.title.ilike(search_pattern),
                    Campaign.description.ilike(search_pattern)
                )
            )
            span.set_attribute("search_query", search)
        
        campaigns = query.order_by(Campaign.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        span.set_attribute("result_count", len(campaigns))
        
        return [CampaignResponse.from_orm(c) for c in campaigns]


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    campaign_update: CampaignUpdate,
    db: Session = Depends(get_db)
):
    """
    Update campaign details
    
    Publishes "CampaignUpdated" event to RabbitMQ
    """
    with campaign_operations_duration.labels(operation="update").time():
        with tracer.start_as_current_span("update_campaign") as span:
            span.set_attribute("campaign_id", str(campaign_id))
            
            try:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                
                if not campaign:
                    raise HTTPException(status_code=404, detail="Campaign not found")
                
                # Update fields
                update_data = campaign_update.dict(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(campaign, field, value)
                
                campaign.updated_at = datetime.utcnow()
                campaign.version += 1
                
                db.commit()
                db.refresh(campaign)
                
                # Publish event
                publish_campaign_event(campaign, "CampaignUpdated")
                
                # Invalidate cache
                redis_client = get_redis()
                cache_key = f"campaign:{campaign_id}"
                redis_client.delete(cache_key)
                
                span.set_attribute("status", "success")
                
                return CampaignResponse.from_orm(campaign)
                
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                raise HTTPException(status_code=500, detail=f"Failed to update campaign: {str(e)}")


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """
    Close/Cancel a campaign (soft delete)
    
    Publishes "CampaignClosed" event to RabbitMQ
    """
    with campaign_operations_duration.labels(operation="delete").time():
        with tracer.start_as_current_span("delete_campaign") as span:
            span.set_attribute("campaign_id", str(campaign_id))
            
            try:
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                
                if not campaign:
                    raise HTTPException(status_code=404, detail="Campaign not found")
                
                # Soft delete - set status to CANCELLED
                campaign.status = "CANCELLED"
                campaign.updated_at = datetime.utcnow()
                campaign.version += 1
                
                db.commit()
                
                # Publish event
                publish_campaign_event(campaign, "CampaignClosed")
                
                # Invalidate cache
                redis_client = get_redis()
                cache_key = f"campaign:{campaign_id}"
                redis_client.delete(cache_key)
                
                span.set_attribute("status", "success")
                
                return {"status": "success", "message": "Campaign closed"}
                
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                raise HTTPException(status_code=500, detail=f"Failed to close campaign: {str(e)}")

