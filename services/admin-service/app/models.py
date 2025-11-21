"""
SQLAlchemy Database Models (Read-Only Views)
"""
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Donation(Base):
    """Donation model (read-only)"""
    __tablename__ = "donations"

    id = Column(UUID(as_uuid=True), primary_key=True)
    campaign_id = Column(UUID(as_uuid=True))
    donor_email = Column(String(255))
    amount = Column(Numeric(10, 2))
    currency = Column(String(3))
    status = Column(String(20))
    payment_intent_id = Column(String(255))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    version = Column(Integer)


# Note: Admin service reads from donation service DB
# For other data, it makes HTTP calls to respective services

