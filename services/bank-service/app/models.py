"""
SQLAlchemy Database Models
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class BankAccount(Base):
    """Bank Account model - Ledger"""
    __tablename__ = "bank_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    account_number = Column(String(20), unique=True, nullable=False, index=True)
    account_holder_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    balance = Column(Numeric(12, 2), nullable=False, default=0.00)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)  # ACTIVE, SUSPENDED, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1)

    __table_args__ = (
        Index('idx_accounts_status', 'status'),
    )


class Transaction(Base):
    """Transaction model - All money movements"""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_type = Column(String(20), nullable=False, index=True)  # TRANSFER, DEPOSIT, WITHDRAWAL
    from_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True, index=True)
    to_account_id = Column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(String(20), nullable=False, default="PENDING", index=True)  # PENDING, COMPLETED, FAILED, REVERSED
    reference = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)
    extra_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_transactions_type_status', 'transaction_type', 'status'),
        Index('idx_transactions_from_account', 'from_account_id', 'created_at'),
        Index('idx_transactions_to_account', 'to_account_id', 'created_at'),
    )


class TransferIdempotency(Base):
    """Transfer Idempotency model - Prevent duplicate transfers"""
    __tablename__ = "transfer_idempotency"

    key = Column(String(255), primary_key=True)
    transaction_id = Column(UUID(as_uuid=True), nullable=False)
    response_body = Column(String, nullable=False)
    response_status = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_transfer_idempotency_expires', 'expires_at'),
    )

