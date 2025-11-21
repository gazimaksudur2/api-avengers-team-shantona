"""
Donation Service - Core donation orchestration with Transactional Outbox pattern
"""
import os
import uuid
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import create_engine, Column, String, Numeric, DateTime, Integer, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import redis

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/donations_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "donation-service")

# Database setup
engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

# Prometheus metrics
donation_created_counter = Counter(
    'donation_created_total', 
    'Total number of donations created',
    ['campaign_id', 'status']
)
donation_duration = Histogram(
    'donation_creation_duration_seconds',
    'Time spent creating donation'
)
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# ==================
# Database Models
# ==================
class Donation(Base):
    __tablename__ = "donations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    donor_email = Column(String(255), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False, default="PENDING", index=True)
    payment_intent_id = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)
    extra_data = Column(JSONB, nullable=True)

    __table_args__ = (
        Index('idx_donations_status_campaign', 'status', 'campaign_id'),
        Index('idx_donations_created_at', 'created_at'),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    aggregate_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_outbox_unprocessed', 'created_at', postgresql_where=(processed_at.is_(None))),
    )


# Create tables
Base.metadata.create_all(bind=engine)

# ==================
# Pydantic Models
# ==================
class DonationCreate(BaseModel):
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
        # Round to 2 decimal places
        return round(v, 2)


class DonationResponse(BaseModel):
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
    status: str = Field(pattern="^(PENDING|COMPLETED|FAILED|REFUNDED)$")
    payment_intent_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    checks: dict


# ==================
# Dependencies
# ==================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================
# Application
# ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting {SERVICE_NAME}...")
    yield
    # Shutdown
    print(f"Shutting down {SERVICE_NAME}...")


app = FastAPI(
    title="Donation Service",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================
# Helper Functions
# ==================
def create_outbox_event(db: Session, donation: Donation, event_type: str):
    """Create an outbox event for reliable event publishing"""
    event = OutboxEvent(
        aggregate_id=donation.id,
        event_type=event_type,
        payload={
            "id": str(donation.id),
            "campaign_id": str(donation.campaign_id),
            "donor_email": donation.donor_email,
            "amount": float(donation.amount),
            "currency": donation.currency,
            "status": donation.status,
            "payment_intent_id": donation.payment_intent_id,
            "created_at": donation.created_at.isoformat(),
            "updated_at": donation.updated_at.isoformat(),
            "extra_data": donation.extra_data
        }
    )
    db.add(event)
    return event


# ==================
# API Endpoints
# ==================
@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    checks = {}
    
    # Check database
    try:
        db.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        redis_client.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"
    
    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        service=SERVICE_NAME,
        timestamp=datetime.utcnow(),
        checks=checks
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/donations", response_model=DonationResponse, status_code=201)
async def create_donation(
    donation_data: DonationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new donation pledge with Transactional Outbox pattern
    
    This ensures that both the donation record and the event are written
    atomically in a single transaction, preventing lost donations.
    """
    with donation_duration.time():
        with tracer.start_as_current_span("create_donation") as span:
            span.set_attribute("campaign_id", str(donation_data.campaign_id))
            span.set_attribute("amount", donation_data.amount)
            
            try:
                # Start transaction
                donation = Donation(
                    id=uuid.uuid4(),
                    campaign_id=donation_data.campaign_id,
                    donor_email=donation_data.donor_email,
                    amount=donation_data.amount,
                    currency=donation_data.currency,
                    status="PENDING",
                    extra_data=donation_data.extra_data
                )
                
                db.add(donation)
                db.flush()  # Get the ID without committing
                
                # Create outbox event in SAME transaction
                create_outbox_event(db, donation, "DonationCreated")
                
                # Commit both atomically
                db.commit()
                db.refresh(donation)
                
                # Update metrics
                donation_created_counter.labels(
                    campaign_id=str(donation.campaign_id),
                    status=donation.status
                ).inc()
                
                http_requests_total.labels(
                    method="POST",
                    endpoint="/api/v1/donations",
                    status="201"
                ).inc()
                
                span.set_attribute("donation_id", str(donation.id))
                span.set_attribute("status", "success")
                
                return DonationResponse.from_orm(donation)
                
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                http_requests_total.labels(
                    method="POST",
                    endpoint="/api/v1/donations",
                    status="500"
                ).inc()
                raise HTTPException(status_code=500, detail=f"Failed to create donation: {str(e)}")


@app.get("/api/v1/donations/{donation_id}", response_model=DonationResponse)
async def get_donation(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get donation details by ID"""
    with tracer.start_as_current_span("get_donation") as span:
        span.set_attribute("donation_id", str(donation_id))
        
        # Try cache first
        cache_key = f"donation:{donation_id}"
        cached = redis_client.get(cache_key)
        
        if cached:
            span.set_attribute("cache_hit", True)
            import json
            return json.loads(cached)
        
        span.set_attribute("cache_hit", False)
        donation = db.query(Donation).filter(Donation.id == donation_id).first()
        
        if not donation:
            http_requests_total.labels(
                method="GET",
                endpoint="/api/v1/donations/:id",
                status="404"
            ).inc()
            raise HTTPException(status_code=404, detail="Donation not found")
        
        response = DonationResponse.from_orm(donation)
        
        # Cache for 5 minutes
        import json
        redis_client.setex(
            cache_key,
            300,
            json.dumps(response.dict(), default=str)
        )
        
        http_requests_total.labels(
            method="GET",
            endpoint="/api/v1/donations/:id",
            status="200"
        ).inc()
        
        return response


@app.get("/api/v1/donations/history", response_model=List[DonationResponse])
async def get_donation_history(
    donor_email: EmailStr = Query(..., description="Donor email address"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get donation history for a donor"""
    with tracer.start_as_current_span("get_donation_history") as span:
        span.set_attribute("donor_email", donor_email)
        
        donations = db.query(Donation)\
            .filter(Donation.donor_email == donor_email)\
            .order_by(Donation.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
        
        span.set_attribute("result_count", len(donations))
        
        http_requests_total.labels(
            method="GET",
            endpoint="/api/v1/donations/history",
            status="200"
        ).inc()
        
        return [DonationResponse.from_orm(d) for d in donations]


@app.patch("/api/v1/donations/{donation_id}/status", response_model=DonationResponse)
async def update_donation_status(
    donation_id: uuid.UUID,
    status_update: DonationStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Update donation status (internal endpoint, called by payment service)
    """
    with tracer.start_as_current_span("update_donation_status") as span:
        span.set_attribute("donation_id", str(donation_id))
        span.set_attribute("new_status", status_update.status)
        
        try:
            donation = db.query(Donation).filter(Donation.id == donation_id).first()
            
            if not donation:
                http_requests_total.labels(
                    method="PATCH",
                    endpoint="/api/v1/donations/:id/status",
                    status="404"
                ).inc()
                raise HTTPException(status_code=404, detail="Donation not found")
            
            old_status = donation.status
            donation.status = status_update.status
            if status_update.payment_intent_id:
                donation.payment_intent_id = status_update.payment_intent_id
            donation.version += 1
            donation.updated_at = datetime.utcnow()
            
            # Create outbox event for status change
            event_type = f"DonationStatusChanged.{status_update.status}"
            create_outbox_event(db, donation, event_type)
            
            db.commit()
            db.refresh(donation)
            
            # Invalidate cache
            cache_key = f"donation:{donation_id}"
            redis_client.delete(cache_key)
            
            # Update metrics
            donation_created_counter.labels(
                campaign_id=str(donation.campaign_id),
                status=donation.status
            ).inc()
            
            http_requests_total.labels(
                method="PATCH",
                endpoint="/api/v1/donations/:id/status",
                status="200"
            ).inc()
            
            span.set_attribute("old_status", old_status)
            span.set_attribute("status", "success")
            
            return DonationResponse.from_orm(donation)
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            span.set_attribute("status", "error")
            span.set_attribute("error", str(e))
            http_requests_total.labels(
                method="PATCH",
                endpoint="/api/v1/donations/:id/status",
                status="500"
            ).inc()
            raise HTTPException(status_code=500, detail=f"Failed to update donation: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

