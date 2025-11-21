"""
SQLAlchemy Database Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Campaign(Base):
    """Campaign model"""
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    goal_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)  # ACTIVE, PAUSED, COMPLETED, CANCELLED
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    organization = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    image_url = Column(String(500), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)

    __table_args__ = (
        Index('idx_campaigns_status_created', 'status', 'created_at'),
        Index('idx_campaigns_category_status', 'category', 'status'),
    )

