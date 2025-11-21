"""
RabbitMQ Event Consumer for Cache Invalidation
"""
import uuid
import json
import threading

import pika

from app.config import settings
from app.database import SessionLocal
from app.models import Donation
from utils.caching import invalidate_cache


# Global stop event for graceful shutdown
stop_event = threading.Event()


def consume_events():
    """
    Background thread to consume payment events and invalidate cache
    
    Listens to:
    - PaymentStatus.CAPTURED events (successful payments)
    """
    print("Event consumer thread started...")
    
    try:
        connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
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
            """Process incoming payment event"""
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
                        
                        # Note: Materialized view refresh can be done on a schedule
                        # instead of per-event for better performance
                    
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


def start_consumer():
    """Start the event consumer in a background thread"""
    consumer_thread = threading.Thread(target=consume_events, daemon=True)
    consumer_thread.start()
    return consumer_thread


def stop_consumer():
    """Stop the event consumer gracefully"""
    stop_event.set()

