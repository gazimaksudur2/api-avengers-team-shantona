"""
Outbox Processor - Polls outbox events and publishes to RabbitMQ

This separate process ensures reliable event publishing with at-least-once delivery.
"""
import os
import time
import json
from datetime import datetime, timedelta

import pika
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from main import OutboxEvent, Base

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/donations_db")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))  # seconds
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))

# Setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# OpenTelemetry
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)


class OutboxProcessor:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.connect_rabbitmq()
    
    def connect_rabbitmq(self):
        """Connect to RabbitMQ with retry logic"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            try:
                print(f"Connecting to RabbitMQ... (attempt {attempt + 1}/{max_attempts})")
                self.connection = pika.BlockingConnection(
                    pika.URLParameters(RABBITMQ_URL)
                )
                self.channel = self.connection.channel()
                
                # Declare exchanges
                self.channel.exchange_declare(
                    exchange='donations.events',
                    exchange_type='topic',
                    durable=True
                )
                
                print("✓ Connected to RabbitMQ")
                return
                
            except Exception as e:
                attempt += 1
                print(f"✗ Failed to connect to RabbitMQ: {e}")
                if attempt < max_attempts:
                    time.sleep(5)
                else:
                    raise
    
    def publish_event(self, event: OutboxEvent):
        """Publish event to RabbitMQ"""
        with tracer.start_as_current_span("publish_event") as span:
            span.set_attribute("event_id", event.id)
            span.set_attribute("event_type", event.event_type)
            span.set_attribute("aggregate_id", str(event.aggregate_id))
            
            try:
                # Ensure connection is alive
                if self.connection.is_closed:
                    self.connect_rabbitmq()
                
                # Prepare message
                message = json.dumps({
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "aggregate_id": str(event.aggregate_id),
                    "timestamp": event.created_at.isoformat(),
                    "payload": event.payload
                })
                
                # Publish to exchange
                routing_key = f"donation.{event.event_type.lower()}"
                self.channel.basic_publish(
                    exchange='donations.events',
                    routing_key=routing_key,
                    body=message,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistent
                        content_type='application/json',
                        timestamp=int(time.time())
                    )
                )
                
                span.set_attribute("status", "published")
                print(f"✓ Published event {event.id} ({event.event_type})")
                return True
                
            except Exception as e:
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                print(f"✗ Failed to publish event {event.id}: {e}")
                return False
    
    def process_batch(self):
        """Process a batch of unprocessed outbox events"""
        db = SessionLocal()
        
        try:
            with tracer.start_as_current_span("process_outbox_batch") as span:
                # Fetch unprocessed events
                events = db.query(OutboxEvent)\
                    .filter(OutboxEvent.processed_at.is_(None))\
                    .filter(OutboxEvent.retry_count < MAX_RETRIES)\
                    .order_by(OutboxEvent.created_at)\
                    .limit(BATCH_SIZE)\
                    .with_for_update(skip_locked=True)\
                    .all()
                
                span.set_attribute("batch_size", len(events))
                
                if not events:
                    return 0
                
                print(f"Processing {len(events)} outbox events...")
                
                published_count = 0
                for event in events:
                    success = self.publish_event(event)
                    
                    if success:
                        # Mark as processed
                        event.processed_at = datetime.utcnow()
                        published_count += 1
                    else:
                        # Increment retry count
                        event.retry_count += 1
                    
                    db.commit()
                
                span.set_attribute("published_count", published_count)
                print(f"✓ Successfully published {published_count}/{len(events)} events")
                
                return published_count
                
        except Exception as e:
            db.rollback()
            print(f"✗ Error processing batch: {e}")
            return 0
        finally:
            db.close()
    
    def cleanup_old_events(self):
        """Clean up processed events older than 7 days"""
        db = SessionLocal()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            deleted = db.query(OutboxEvent)\
                .filter(OutboxEvent.processed_at.isnot(None))\
                .filter(OutboxEvent.processed_at < cutoff_date)\
                .delete()
            
            db.commit()
            
            if deleted > 0:
                print(f"✓ Cleaned up {deleted} old processed events")
            
            return deleted
            
        except Exception as e:
            db.rollback()
            print(f"✗ Error during cleanup: {e}")
            return 0
        finally:
            db.close()
    
    def run(self):
        """Main processing loop"""
        print("Starting Outbox Processor...")
        print(f"Poll interval: {POLL_INTERVAL}s")
        print(f"Batch size: {BATCH_SIZE}")
        print(f"Max retries: {MAX_RETRIES}")
        
        cleanup_counter = 0
        
        while True:
            try:
                # Process outbox events
                self.process_batch()
                
                # Cleanup old events every 100 iterations (~8 minutes with 5s interval)
                cleanup_counter += 1
                if cleanup_counter >= 100:
                    self.cleanup_old_events()
                    cleanup_counter = 0
                
                # Wait before next poll
                time.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                print("\nShutting down gracefully...")
                break
            except Exception as e:
                print(f"✗ Unexpected error: {e}")
                time.sleep(POLL_INTERVAL)
        
        # Cleanup
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        print("✓ Outbox Processor stopped")


if __name__ == "__main__":
    processor = OutboxProcessor()
    processor.run()

