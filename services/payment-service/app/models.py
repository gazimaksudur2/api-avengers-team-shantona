"""
SQLAlchemy Database Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class PaymentTransaction(Base):
    """Payment Transaction model"""
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    donation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    payment_intent_id = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False, index=True)
    gateway = Column(String(50), nullable=False)
    gateway_response = Column(JSONB, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_payment_status', 'status'),
    )


class IdempotencyKey(Base):
    """Idempotency Key model for duplicate detection"""
    __tablename__ = "idempotency_keys"

    key = Column(String(255), primary_key=True)
    response_body = Column(String, nullable=False)
    response_status = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_idempotency_expires', 'expires_at'),
    )


class PaymentStateHistory(Base):
    """Payment State History for audit trail"""
    __tablename__ = "payment_state_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    event_id = Column(String(255), nullable=True, index=True)
    event_timestamp = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    version = Column(Integer, nullable=False)


