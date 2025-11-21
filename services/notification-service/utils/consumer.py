"""
RabbitMQ Event Consumer
"""
import uuid
import json
import threading
from datetime import datetime

import pika

from app.config import settings
from app.database import SessionLocal
from app.models import Notification
from utils.email import send_email
from app.observability import notifications_sent_counter


# Global stop event for graceful shutdown
stop_event = threading.Event()


def consume_donation_events():
    """
    Background thread to consume donation events and send notifications
    
    Listens to:
    - DonationCreated events
    - DonationStatusChanged.COMPLETED events
    """
    print("Notification event consumer started...")
    
    try:
        connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
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
            """Process incoming donation event"""
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


def start_consumer():
    """Start the event consumer in a background thread"""
    consumer_thread = threading.Thread(target=consume_donation_events, daemon=True)
    consumer_thread.start()
    return consumer_thread


def stop_consumer():
    """Stop the event consumer gracefully"""
    stop_event.set()

