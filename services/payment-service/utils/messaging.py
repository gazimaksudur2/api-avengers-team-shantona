"""
RabbitMQ Messaging Utilities
"""
import json
from datetime import datetime
import pika

from app.config import settings
from app.models import PaymentTransaction


def publish_payment_event(payment: PaymentTransaction, event_type: str):
    """
    Publish payment event to RabbitMQ
    
    Args:
        payment: Payment transaction instance
        event_type: Type of event to publish
    """
    try:
        connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        channel = connection.channel()
        
        channel.exchange_declare(
            exchange='payments.events',
            exchange_type='topic',
            durable=True
        )
        
        message = json.dumps({
            "event_type": event_type,
            "payment_id": str(payment.id),
            "donation_id": str(payment.donation_id),
            "payment_intent_id": payment.payment_intent_id,
            "status": payment.status,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        routing_key = f"payment.{event_type.lower()}"
        channel.basic_publish(
            exchange='payments.events',
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json'
            )
        )
        
        connection.close()
        print(f"✓ Published payment event: {event_type}")
        
    except Exception as e:
        print(f"✗ Failed to publish payment event: {e}")


