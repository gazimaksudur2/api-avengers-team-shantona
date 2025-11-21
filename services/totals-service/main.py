"""
Totals Service - Optimized fundraising analytics with multi-level caching

Key Features:
1. Materialized views for pre-aggregated data
2. Multi-level caching (Redis L1, Materialized View L2, Base table L3)
3. Event-driven cache invalidation
4. Real-time mode for accurate totals
"""
import os
import uuid
import json
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
import asyncio
import threading

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Numeric, DateTime, Integer, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import redis
import pika

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/donations_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "totals-service")
CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))  # seconds

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
totals_requests_total = Counter(
    'totals_requests_total',
    'Total number of totals requests',
    ['campaign_id', 'cache_hit']
)
cache_hit_ratio = Gauge(
    'cache_hit_ratio',
    'Cache hit ratio',
    ['cache_type']
)
totals_calculation_duration = Histogram(
    'totals_calculation_duration_seconds',
    'Time spent calculating totals',
    ['source']
)
materialized_view_age = Gauge(
    'materialized_view_age_seconds',
    'Age of materialized view data'
)

# ==================
# Database Models (Read-only views of donation service DB)
# ==================
class Donation(Base):
    __tablename__ = "donations"

    id = Column(UUID(as_uuid=True), primary_key=True)
    campaign_id = Column(UUID(as_uuid=True))
    donor_email = Column(String(255))
    amount = Column(Numeric(10, 2))
    currency = Column(String(3))
    status = Column(String(20))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


# ==================
# Pydantic Models
# ==================
class CampaignTotals(BaseModel):
    campaign_id: uuid.UUID
    total_donations: int
    total_amount: float
    unique_donors: int
    last_updated: datetime
    data_source: str  # redis, materialized_view, realtime
    cache_age_seconds: Optional[float] = None


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
event_consumer_thread = None
stop_event = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_consumer_thread
    
    # Startup
    print(f"Starting {SERVICE_NAME}...")
    
    # Create materialized view if not exists
    db = SessionLocal()
    try:
        print("Creating materialized view...")
        db.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS campaign_totals AS
            SELECT 
                campaign_id,
                COUNT(*) as total_donations,
                SUM(amount) as total_amount,
                COUNT(DISTINCT donor_email) as unique_donors,
                MAX(updated_at) as last_updated
            FROM donations
            WHERE status = 'COMPLETED'
            GROUP BY campaign_id
        """))
        
        db.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_campaign_totals_id 
            ON campaign_totals (campaign_id)
        """))
        
        db.commit()
        print("✓ Materialized view ready")
    except Exception as e:
        print(f"Note: {e}")
        db.rollback()
    finally:
        db.close()
    
    # Start event consumer in background thread
    event_consumer_thread = threading.Thread(target=consume_events, daemon=True)
    event_consumer_thread.start()
    print("✓ Event consumer started")
    
    yield
    
    # Shutdown
    print(f"Shutting down {SERVICE_NAME}...")
    stop_event.set()
    if event_consumer_thread:
        event_consumer_thread.join(timeout=5)


app = FastAPI(
    title="Totals Service",
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
def get_totals_from_cache(campaign_id: uuid.UUID) -> Optional[dict]:
    """Get totals from Redis cache (L1)"""
    with tracer.start_as_current_span("get_from_cache") as span:
        span.set_attribute("campaign_id", str(campaign_id))
        
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
    """Get totals from materialized view (L2)"""
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
    """Get totals from base table (L3 - real-time)"""
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
    """Set totals in Redis cache"""
    cache_key = f"campaign_totals:{campaign_id}"
    redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))


def invalidate_cache(campaign_id: uuid.UUID):
    """Invalidate cache for a campaign"""
    cache_key = f"campaign_totals:{campaign_id}"
    redis_client.delete(cache_key)
    print(f"✓ Invalidated cache for campaign {campaign_id}")


def refresh_materialized_view(db: Session):
    """Refresh the materialized view"""
    with tracer.start_as_current_span("refresh_materialized_view"):
        try:
            db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY campaign_totals"))
            db.commit()
            print("✓ Materialized view refreshed")
        except Exception as e:
            print(f"✗ Failed to refresh materialized view: {e}")
            db.rollback()


def consume_events():
    """Background thread to consume payment events and invalidate cache"""
    print("Event consumer thread started...")
    
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        
        # Declare exchange
        channel.exchange_declare(
            exchange='payments.events',
            exchange_type='topic',
            durable=True
        )
        
        # Declare queue
        result = channel.queue_declare(queue='totals.queue', durable=True)
        queue_name = result.method.queue
        
        # Bind to payment completed events
        channel.queue_bind(
            exchange='payments.events',
            queue=queue_name,
            routing_key='payment.paymentstatus.captured'
        )
        
        def callback(ch, method, properties, body):
            try:
                event = json.loads(body)
                donation_id = event.get("donation_id")
                
                print(f"Received payment event for donation {donation_id}")
                
                # Get campaign_id from donation
                db = SessionLocal()
                try:
                    donation = db.query(Donation).filter(
                        Donation.id == uuid.UUID(donation_id)
                    ).first()
                    
                    if donation:
                        # Invalidate cache
                        invalidate_cache(donation.campaign_id)
                        
                        # Optionally refresh materialized view
                        # (In production, this might be done on a schedule instead)
                        # refresh_materialized_view(db)
                    
                finally:
                    db.close()
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"Error processing event: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        
        print("✓ Waiting for payment events...")
        
        while not stop_event.is_set():
            connection.process_data_events(time_limit=1)
        
    except Exception as e:
        print(f"Error in event consumer: {e}")
    finally:
        try:
            connection.close()
        except:
            pass
        print("Event consumer thread stopped")


# ==================
# API Endpoints
# ==================
@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    checks = {}
    
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
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


@app.get("/api/v1/totals/campaigns/{campaign_id}", response_model=CampaignTotals)
async def get_campaign_totals(
    campaign_id: uuid.UUID,
    realtime: bool = Query(False, description="Force real-time calculation"),
    db: Session = Depends(get_db)
):
    """
    Get campaign totals with multi-level caching
    
    - L1: Redis cache (30s TTL) - ultra fast
    - L2: Materialized view (refreshed periodically) - fast
    - L3: Base table - accurate but slower
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


@app.post("/api/v1/totals/refresh")
async def refresh_totals(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Refresh materialized view (internal endpoint)"""
    with tracer.start_as_current_span("refresh_totals"):
        try:
            # Run in background to avoid blocking
            background_tasks.add_task(refresh_materialized_view, db)
            return {"status": "scheduled", "message": "Materialized view refresh scheduled"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to refresh: {str(e)}")


@app.delete("/api/v1/totals/cache/{campaign_id}")
async def invalidate_campaign_cache(campaign_id: uuid.UUID):
    """Invalidate cache for a campaign (internal endpoint)"""
    with tracer.start_as_current_span("invalidate_cache"):
        try:
            invalidate_cache(campaign_id)
            return {"status": "success", "message": f"Cache invalidated for campaign {campaign_id}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

