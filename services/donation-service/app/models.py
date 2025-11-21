"""
SQLAlchemy Database Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class Donation(Base):
    """Donation model"""
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
    """Outbox Event model for reliable event publishing"""
    __tablename__ = "outbox_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    aggregate_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_outbox_unprocessed', 'created_at', 
              postgresql_where=(processed_at.is_(None))),
    )


