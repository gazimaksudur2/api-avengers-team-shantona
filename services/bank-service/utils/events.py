"""
Event Publishing Utilities
"""
import json
from datetime import datetime
import pika

from app.config import settings
from app.models import Transaction


def publish_transfer_event(transaction: Transaction, event_type: str):
    """
    Publish transfer event to RabbitMQ
    
    Args:
        transaction: Transaction instance
        event_type: Type of event (TransferCompleted, FundsReserved, FundsSettled)
    """
    try:
        connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        channel = connection.channel()
        
        channel.exchange_declare(
            exchange='bank.events',
            exchange_type='topic',
            durable=True
        )
        
        message = json.dumps({
            "event_type": event_type,
            "transaction_id": str(transaction.id),
            "transaction_type": transaction.transaction_type,
            "from_account_id": str(transaction.from_account_id) if transaction.from_account_id else None,
            "to_account_id": str(transaction.to_account_id) if transaction.to_account_id else None,
            "amount": float(transaction.amount),
            "currency": transaction.currency,
            "status": transaction.status,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        routing_key = f"bank.{event_type.lower()}"
        channel.basic_publish(
            exchange='bank.events',
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json'
            )
        )
        
        connection.close()
        print(f"✓ Published bank event: {event_type}")
        
    except Exception as e:
        print(f"✗ Failed to publish bank event: {e}")

