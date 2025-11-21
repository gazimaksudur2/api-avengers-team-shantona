"""
Outbox Pattern Utilities
"""
from sqlalchemy.orm import Session
from app.models import Donation, OutboxEvent


def create_outbox_event(db: Session, donation: Donation, event_type: str) -> OutboxEvent:
    """
    Create an outbox event for reliable event publishing
    
    Args:
        db: Database session
        donation: Donation instance
        event_type: Type of event (e.g., "DonationCreated")
    
    Returns:
        OutboxEvent instance
    """
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


