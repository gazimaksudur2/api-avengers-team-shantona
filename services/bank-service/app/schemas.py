"""
Pydantic Schemas for Request/Response Models
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator


class AccountCreate(BaseModel):
    """Schema for creating a bank account"""
    user_id: uuid.UUID
    account_holder_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    initial_deposit: float = Field(default=0.0, ge=0)


class AccountResponse(BaseModel):
    """Schema for account response"""
    id: uuid.UUID
    user_id: uuid.UUID
    account_number: str
    account_holder_name: str
    email: str
    balance: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransferCreate(BaseModel):
    """Schema for creating a transfer"""
    from_account_number: str = Field(..., min_length=10, max_length=20)
    to_account_number: str = Field(..., min_length=10, max_length=20)
    amount: float = Field(gt=0, le=1000000)
    description: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = None

    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return round(v, 2)


class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    id: uuid.UUID
    transaction_type: str
    from_account_id: Optional[uuid.UUID]
    to_account_id: Optional[uuid.UUID]
    amount: float
    currency: str
    status: str
    reference: Optional[str]
    description: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

