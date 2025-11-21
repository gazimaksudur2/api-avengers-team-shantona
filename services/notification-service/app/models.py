"""
SQLAlchemy Database Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class Notification(Base):
    """Notification model"""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    donation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient = Column(String(255), nullable=False, index=True)
    type = Column(String(20), nullable=False)  # EMAIL, SMS, WEBHOOK
    status = Column(String(20), nullable=False, default="PENDING", index=True)  # PENDING, SENT, FAILED
    template_id = Column(String(100), nullable=True)
    payload = Column(JSONB, nullable=True)
    retry_count = Column(Integer, default=0)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_notification_status', 'status'),
    )

