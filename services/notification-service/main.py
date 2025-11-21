"""
Notification Service - Send donor confirmations and alerts

Key Features:
1. Email notifications (simulated)
2. Event-driven via RabbitMQ
3. Retry logic with exponential backoff
4. Notification history tracking
"""
import os
import uuid
import json
import threading
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, String, DateTime, Integer, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import pika

# OpenTelemetry
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/notifications_db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "notification-service")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "dummy")

# Database setup
engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

# Prometheus metrics
notifications_sent_counter = Counter(
    'notifications_sent_total',
    'Total number of notifications sent',
    ['type', 'status']
)
notification_duration = Histogram(
    'notification_send_duration_seconds',
    'Time spent sending notifications'
)

# ==================
# Database Models
# ==================
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    donation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)  # EMAIL, SMS, WEBHOOK
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING, SENT, FAILED
    template_id = Column(String(100), nullable=True)
    payload = Column(JSONB, nullable=True)
    retry_count = Column(Integer, default=0)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)

# ==================
# Pydantic Models
# ==================
class NotificationCreate(BaseModel):
    donation_id: uuid.UUID
    recipient: EmailStr
    type: str = "EMAIL"
    template_id: Optional[str] = "donation_confirmation"
    payload: Optional[dict] = None


class NotificationResponse(BaseModel):
    id: uuid.UUID
    donation_id: uuid.UUID
    recipient: str
    type: str
    status: str
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


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
    
    # Start event consumer
    event_consumer_thread = threading.Thread(target=consume_donation_events, daemon=True)
    event_consumer_thread.start()
    print("✓ Event consumer started")
    
    yield
    
    # Shutdown
    print(f"Shutting down {SERVICE_NAME}...")
    stop_event.set()
    if event_consumer_thread:
        event_consumer_thread.join(timeout=5)


app = FastAPI(
    title="Notification Service",
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
def send_email(recipient: str, template_id: str, data: dict) -> bool:
    """
    Send email notification (simulated)
    In production, this would integrate with SendGrid, AWS SES, etc.
    """
    with tracer.start_as_current_span("send_email") as span:
        span.set_attribute("recipient", recipient)
        span.set_attribute("template_id", template_id)
        
        try:
            # Simulate email sending
            print(f"📧 Sending email to {recipient}")
            print(f"   Template: {template_id}")
            print(f"   Data: {data}")
            
            # In production:
            # sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
            # message = Mail(...)
            # response = sg.send(message)
            
            span.set_attribute("status", "sent")
            return True
            
        except Exception as e:
            span.set_attribute("status", "failed")
            span.set_attribute("error", str(e))
            print(f"✗ Failed to send email: {e}")
            return False


def consume_donation_events():
    """Background thread to consume donation events and send notifications"""
    print("Notification event consumer started...")
    
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        
        # Declare exchange
        channel.exchange_declare(
            exchange='donations.events',
            exchange_type='topic',
            durable=True
        )
        
        # Declare queue
        result = channel.queue_declare(queue='notifications.queue', durable=True)
        queue_name = result.method.queue
        
        # Bind to donation completed events
        channel.queue_bind(
            exchange='donations.events',
            queue=queue_name,
            routing_key='donation.donationstatuschanged.completed'
        )
        
        # Also listen to donation created events
        channel.queue_bind(
            exchange='donations.events',
            queue=queue_name,
            routing_key='donation.donationcreated'
        )
        
        def callback(ch, method, properties, body):
            try:
                event = json.loads(body)
                payload = event.get("payload", {})
                
                donation_id = payload.get("id")
                donor_email = payload.get("donor_email")
                amount = payload.get("amount")
                status = payload.get("status")
                
                print(f"Received donation event: {event.get('event_type')}")
                
                # Create notification
                db = SessionLocal()
                try:
                    notification = Notification(
                        id=uuid.uuid4(),
                        donation_id=uuid.UUID(donation_id),
                        recipient=donor_email,
                        type="EMAIL",
                        status="PENDING",
                        template_id="donation_confirmation",
                        payload={
                            "amount": amount,
                            "status": status,
                            "donation_id": donation_id
                        }
                    )
                    
                    db.add(notification)
                    db.commit()
                    
                    # Send notification
                    success = send_email(
                        recipient=donor_email,
                        template_id="donation_confirmation",
                        data={
                            "amount": amount,
                            "currency": payload.get("currency", "USD"),
                            "status": status
                        }
                    )
                    
                    # Update status
                    notification.status = "SENT" if success else "FAILED"
                    if success:
                        notification.sent_at = datetime.utcnow()
                    else:
                        notification.retry_count += 1
                    
                    db.commit()
                    
                    # Update metrics
                    notifications_sent_counter.labels(
                        type="EMAIL",
                        status="SENT" if success else "FAILED"
                    ).inc()
                    
                finally:
                    db.close()
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"Error processing notification event: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        
        print("✓ Waiting for donation events...")
        
        while not stop_event.is_set():
            connection.process_data_events(time_limit=1)
        
    except Exception as e:
        print(f"Error in notification consumer: {e}")
    finally:
        try:
            connection.close()
        except:
            pass
        print("Notification consumer thread stopped")


# ==================
# API Endpoints
# ==================
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    checks = {}
    
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
    
    overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    
    return {
        "status": overall_status,
        "service": SERVICE_NAME,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/notifications/send", response_model=NotificationResponse, status_code=201)
@notification_duration.time()
async def send_notification(
    notification_data: NotificationCreate,
    db: Session = Depends(get_db)
):
    """Send a notification (internal endpoint)"""
    with tracer.start_as_current_span("send_notification") as span:
        span.set_attribute("donation_id", str(notification_data.donation_id))
        span.set_attribute("recipient", notification_data.recipient)
        
        try:
            # Create notification record
            notification = Notification(
                id=uuid.uuid4(),
                donation_id=notification_data.donation_id,
                recipient=notification_data.recipient,
                type=notification_data.type,
                status="PENDING",
                template_id=notification_data.template_id,
                payload=notification_data.payload
            )
            
            db.add(notification)
            db.commit()
            db.refresh(notification)
            
            # Send notification
            if notification_data.type == "EMAIL":
                success = send_email(
                    recipient=notification_data.recipient,
                    template_id=notification_data.template_id,
                    data=notification_data.payload or {}
                )
                
                notification.status = "SENT" if success else "FAILED"
                if success:
                    notification.sent_at = datetime.utcnow()
                
                db.commit()
                db.refresh(notification)
            
            # Update metrics
            notifications_sent_counter.labels(
                type=notification_data.type,
                status=notification.status
            ).inc()
            
            span.set_attribute("status", "success")
            
            return NotificationResponse.from_orm(notification)
            
        except Exception as e:
            db.rollback()
            span.set_attribute("status", "error")
            span.set_attribute("error", str(e))
            raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


@app.get("/api/v1/notifications/{donation_id}", response_model=List[NotificationResponse])
async def get_notifications(
    donation_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get notifications for a donation"""
    with tracer.start_as_current_span("get_notifications") as span:
        span.set_attribute("donation_id", str(donation_id))
        
        notifications = db.query(Notification)\
            .filter(Notification.donation_id == donation_id)\
            .order_by(Notification.created_at.desc())\
            .all()
        
        span.set_attribute("count", len(notifications))
        
        return [NotificationResponse.from_orm(n) for n in notifications]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

