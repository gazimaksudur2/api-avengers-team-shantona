"""
SQLAlchemy Database Models (Read-only views)
"""
from sqlalchemy import Column, String, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Donation(Base):
    """
    Donation model (read-only view from donation service database)
    """
    __tablename__ = "donations"

    id = Column(UUID(as_uuid=True), primary_key=True)
    campaign_id = Column(UUID(as_uuid=True))
    donor_email = Column(String(255))
    amount = Column(Numeric(10, 2))
    currency = Column(String(3))
    status = Column(String(20))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

