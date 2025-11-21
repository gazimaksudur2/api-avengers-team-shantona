"""
Event Publishing Utilities
"""
import json
from datetime import datetime
import pika

from app.config import settings
from app.models import Campaign


def publish_campaign_event(campaign: Campaign, event_type: str):
    """
    Publish campaign event to RabbitMQ
    
    Args:
        campaign: Campaign instance
        event_type: Type of event (CampaignCreated, CampaignUpdated, CampaignClosed)
    """
    try:
        connection = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        channel = connection.channel()
        
        channel.exchange_declare(
            exchange='campaigns.events',
            exchange_type='topic',
            durable=True
        )
        
        message = json.dumps({
            "event_type": event_type,
            "campaign_id": str(campaign.id),
            "title": campaign.title,
            "goal_amount": float(campaign.goal_amount),
            "currency": campaign.currency,
            "status": campaign.status,
            "category": campaign.category,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        routing_key = f"campaign.{event_type.lower()}"
        channel.basic_publish(
            exchange='campaigns.events',
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type='application/json'
            )
        )
        
        connection.close()
        print(f"✓ Published campaign event: {event_type}")
        
    except Exception as e:
        print(f"✗ Failed to publish campaign event: {e}")

