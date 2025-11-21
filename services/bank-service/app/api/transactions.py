"""
Bank Transaction API Endpoints - P2P Transfers with Idempotency
"""
import uuid
import json
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Header, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.dependencies import get_redis
from app.models import BankAccount, Transaction, TransferIdempotency
from app.schemas import TransferCreate, TransactionResponse
from app.observability import (
    tracer, transfers_processed_counter, transfer_duration
)
from utils.validation import validate_transfer
from utils.ledger import execute_transfer
from utils.events import publish_transfer_event

router = APIRouter(prefix="/api/v1/bank/transfers", tags=["transfers"])


@router.post("", response_model=TransactionResponse, status_code=201)
async def create_transfer(
    transfer_data: TransferCreate,
    x_idempotency_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Create a P2P transfer with IDEMPOTENCY
    
    **Idempotency Handling:**
    - L1: Redis cache (< 10ms)
    - L2: Database (< 50ms)
    
    **Validation:**
    - Account status (ACTIVE)
    - Sufficient balance
    - Currency match
    - No self-transfers
    
    **ACID Transaction:**
    - Debit from_account
    - Credit to_account
    - Create transaction record
    - All or nothing
    
    Headers:
    - X-Idempotency-Key: Optional unique key (auto-generated if not provided)
    """
    with transfer_duration.time():
        with tracer.start_as_current_span("create_transfer") as span:
            span.set_attribute("from_account", transfer_data.from_account_number)
            span.set_attribute("to_account", transfer_data.to_account_number)
            span.set_attribute("amount", transfer_data.amount)
            
            try:
                # Generate idempotency key if not provided
                if not x_idempotency_key:
                    key_data = f"{transfer_data.from_account_number}:{transfer_data.to_account_number}:{transfer_data.amount}:{datetime.utcnow().isoformat()}"
                    x_idempotency_key = hashlib.sha256(key_data.encode()).hexdigest()
                
                span.set_attribute("idempotency_key", x_idempotency_key)
                
                # L1: Check Redis cache (FAST PATH - <10ms)
                redis_client = get_redis()
                cached = redis_client.get(f"transfer:{x_idempotency_key}")
                
                if cached:
                    span.set_attribute("idempotency_hit", "redis")
                    transfers_processed_counter.labels(
                        status="cached",
                        idempotency_hit="redis"
                    ).inc()
                    return TransactionResponse(**json.loads(cached))
                
                # L2: Check database (SLOWER PATH - <50ms)
                existing = db.query(TransferIdempotency).filter_by(
                    key=x_idempotency_key
                ).first()
                
                if existing:
                    span.set_attribute("idempotency_hit", "database")
                    
                    # Warm up Redis cache
                    redis_client.setex(
                        f"transfer:{x_idempotency_key}",
                        86400,
                        existing.response_body
                    )
                    
                    transfers_processed_counter.labels(
                        status="cached",
                        idempotency_hit="database"
                    ).inc()
                    
                    return TransactionResponse(**json.loads(existing.response_body))
                
                # FIRST TIME - Process transfer
                span.set_attribute("idempotency_hit", "none")
                
                # Get accounts
                from_account = db.query(BankAccount).filter(
                    BankAccount.account_number == transfer_data.from_account_number
                ).with_for_update().first()
                
                to_account = db.query(BankAccount).filter(
                    BankAccount.account_number == transfer_data.to_account_number
                ).with_for_update().first()
                
                if not from_account:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Source account {transfer_data.from_account_number} not found"
                    )
                
                if not to_account:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Destination account {transfer_data.to_account_number} not found"
                    )
                
                # Validate transfer
                is_valid, error_message = validate_transfer(
                    from_account,
                    to_account,
                    transfer_data.amount
                )
                
                if not is_valid:
                    span.set_attribute("validation_error", error_message)
                    raise HTTPException(status_code=400, detail=error_message)
                
                # Execute transfer (ACID transaction)
                transaction = execute_transfer(
                    from_account=from_account,
                    to_account=to_account,
                    amount=transfer_data.amount,
                    description=transfer_data.description or f"Transfer to {to_account.account_holder_name}",
                    db=db
                )
                
                # Prepare response
                response = TransactionResponse.from_orm(transaction)
                response_body = json.dumps(response.dict(), default=str)
                
                # Store idempotency record (Redis + DB)
                redis_client.setex(
                    f"transfer:{x_idempotency_key}",
                    86400,  # 24 hours
                    response_body
                )
                
                idem_record = TransferIdempotency(
                    key=x_idempotency_key,
                    transaction_id=transaction.id,
                    response_body=response_body,
                    response_status=201,
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                db.add(idem_record)
                db.commit()
                
                # Publish event
                publish_transfer_event(transaction, "TransferCompleted")
                
                # Update metrics
                transfers_processed_counter.labels(
                    status="processed",
                    idempotency_hit="none"
                ).inc()
                
                span.set_attribute("transaction_id", str(transaction.id))
                span.set_attribute("status", "success")
                
                print(f"✓ Transfer completed: {transfer_data.amount} from {from_account.account_number} to {to_account.account_number}")
                
                return response
                
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                
                transfers_processed_counter.labels(
                    status="failed",
                    idempotency_hit="none"
                ).inc()
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Transfer failed: {str(e)}"
                )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get transaction details"""
    with tracer.start_as_current_span("get_transaction") as span:
        span.set_attribute("transaction_id", str(transaction_id))
        
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return TransactionResponse.from_orm(transaction)

