"""
Admin API Endpoints - Dashboard and Management
"""
import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_redis, verify_token, create_access_token
from app.models import Donation
from app.schemas import (
    LoginRequest, TokenResponse, DashboardMetrics,
    SystemHealthResponse, DonationSummary
)
from app.observability import tracer, admin_requests_counter, admin_login_counter
from app.config import settings
from utils.aggregation import get_dashboard_metrics

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/auth/login", response_model=TokenResponse)
async def admin_login(login: LoginRequest):
    """
    Admin login endpoint
    
    Returns JWT token for authenticated access
    
    **Credentials (change in production!):**
    - Username: admin
    - Password: admin123
    """
    with tracer.start_as_current_span("admin_login") as span:
        span.set_attribute("username", login.username)
        
        # Simple authentication (use proper auth in production!)
        if login.username == settings.admin_username and login.password == settings.admin_password:
            # Create JWT token
            token = create_access_token(
                data={"sub": login.username, "role": "admin"}
            )
            
            admin_login_counter.labels(status="success").inc()
            span.set_attribute("status", "success")
            
            return TokenResponse(access_token=token)
        else:
            admin_login_counter.labels(status="failed").inc()
            span.set_attribute("status", "failed")
            raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/dashboard", response_model=DashboardMetrics)
async def get_dashboard(
    token: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Get dashboard metrics
    
    **Requires:** JWT authentication
    
    **Returns:**
    - Total donations
    - Total amount raised
    - Campaign statistics
    - Donor statistics
    - Today's activity
    """
    with tracer.start_as_current_span("get_dashboard") as span:
        span.set_attribute("admin_user", token.get("sub"))
        
        try:
            # Try cache first
            redis_client = get_redis()
            cached = redis_client.get("admin:dashboard")
            
            if cached:
                span.set_attribute("cache_hit", True)
                return DashboardMetrics(**json.loads(cached))
            
            span.set_attribute("cache_hit", False)
            
            # Aggregate metrics
            metrics = get_dashboard_metrics(db)
            
            # Cache for 1 minute
            redis_client.setex(
                "admin:dashboard",
                60,
                json.dumps(metrics, default=str)
            )
            
            admin_requests_counter.labels(
                endpoint="dashboard",
                status="success"
            ).inc()
            
            return DashboardMetrics(**metrics)
            
        except Exception as e:
            span.set_attribute("error", str(e))
            admin_requests_counter.labels(
                endpoint="dashboard",
                status="error"
            ).inc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get dashboard metrics: {str(e)}"
            )


@router.get("/donations", response_model=List[DonationSummary])
async def list_all_donations(
    token: dict = Depends(verify_token),
    status: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all donations (admin view)
    
    **Requires:** JWT authentication
    
    **Query Parameters:**
    - status: Filter by donation status
    - limit: Number of results (max 500)
    - offset: Pagination offset
    """
    with tracer.start_as_current_span("list_all_donations") as span:
        span.set_attribute("admin_user", token.get("sub"))
        
        try:
            query = db.query(Donation)
            
            if status:
                query = query.filter(Donation.status == status)
                span.set_attribute("filter_status", status)
            
            donations = query.order_by(Donation.created_at.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
            
            span.set_attribute("result_count", len(donations))
            
            admin_requests_counter.labels(
                endpoint="donations",
                status="success"
            ).inc()
            
            return [DonationSummary.from_orm(d) for d in donations]
            
        except Exception as e:
            span.set_attribute("error", str(e))
            admin_requests_counter.labels(
                endpoint="donations",
                status="error"
            ).inc()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list donations: {str(e)}"
            )


@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(token: dict = Depends(verify_token)):
    """
    Get system-wide health status
    
    **Requires:** JWT authentication
    
    Checks health of all microservices:
    - Donation Service
    - Payment Service
    - Totals Service
    - Notification Service
    - Campaign Service
    - Bank Service
    """
    with tracer.start_as_current_span("get_system_health") as span:
        span.set_attribute("admin_user", token.get("sub"))
        
        import httpx
        
        services = {
            "donation-service": "http://donation-service:8001/health",
            "payment-service": "http://payment-service:8002/health",
            "totals-service": "http://totals-service:8003/health",
            "notification-service": "http://notification-service:8004/health",
            "campaign-service": "http://campaign-service:8005/health",
            "bank-service": "http://bank-service:8006/health"
        }
        
        service_statuses = {}
        
        for service_name, health_url in services.items():
            try:
                response = httpx.get(health_url, timeout=2.0)
                if response.status_code == 200:
                    data = response.json()
                    service_statuses[service_name] = data.get("status", "unknown")
                else:
                    service_statuses[service_name] = "unhealthy"
            except:
                service_statuses[service_name] = "unreachable"
        
        # Determine overall status
        if all(status == "healthy" for status in service_statuses.values()):
            overall_status = "healthy"
        elif any(status == "healthy" for status in service_statuses.values()):
            overall_status = "degraded"
        else:
            overall_status = "down"
        
        admin_requests_counter.labels(
            endpoint="system_health",
            status="success"
        ).inc()
        
        return SystemHealthResponse(
            overall_status=overall_status,
            services=service_statuses,
            timestamp=datetime.utcnow()
        )

