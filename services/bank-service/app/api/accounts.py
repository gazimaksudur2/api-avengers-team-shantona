"""
Bank Account API Endpoints
"""
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BankAccount, Transaction
from app.schemas import AccountCreate, AccountResponse, TransactionResponse
from app.observability import tracer, accounts_created_counter
from utils.validation import generate_account_number

router = APIRouter(prefix="/api/v1/bank/accounts", tags=["accounts"])


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new bank account
    
    Generates unique account number automatically
    """
    with tracer.start_as_current_span("create_account") as span:
        span.set_attribute("user_id", str(account_data.user_id))
        
        try:
            # Check if user already has an account
            existing = db.query(BankAccount).filter(
                BankAccount.user_id == account_data.user_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail="User already has a bank account"
                )
            
            # Generate unique account number
            account_number = generate_account_number()
            
            # Create account
            account = BankAccount(
                id=uuid.uuid4(),
                user_id=account_data.user_id,
                account_number=account_number,
                account_holder_name=account_data.account_holder_name,
                email=account_data.email,
                balance=account_data.initial_deposit,
                status="ACTIVE"
            )
            
            db.add(account)
            db.commit()
            db.refresh(account)
            
            # Update metrics
            accounts_created_counter.labels(status="ACTIVE").inc()
            
            span.set_attribute("account_number", account_number)
            span.set_attribute("status", "success")
            
            return AccountResponse.from_orm(account)
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            span.set_attribute("status", "error")
            span.set_attribute("error", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create account: {str(e)}"
            )


@router.get("/{account_number}", response_model=AccountResponse)
async def get_account(
    account_number: str,
    db: Session = Depends(get_db)
):
    """Get account by account number"""
    with tracer.start_as_current_span("get_account") as span:
        span.set_attribute("account_number", account_number)
        
        account = db.query(BankAccount).filter(
            BankAccount.account_number == account_number
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        return AccountResponse.from_orm(account)


@router.get("", response_model=List[AccountResponse])
async def list_accounts(
    user_id: uuid.UUID = Query(None),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List accounts with filters"""
    query = db.query(BankAccount)
    
    if user_id:
        query = query.filter(BankAccount.user_id == user_id)
    
    if status:
        query = query.filter(BankAccount.status == status)
    
    accounts = query.order_by(BankAccount.created_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
    
    return [AccountResponse.from_orm(a) for a in accounts]


@router.get("/{account_number}/transactions", response_model=List[TransactionResponse])
async def get_account_transactions(
    account_number: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get transaction history for an account"""
    with tracer.start_as_current_span("get_account_transactions") as span:
        span.set_attribute("account_number", account_number)
        
        # Get account
        account = db.query(BankAccount).filter(
            BankAccount.account_number == account_number
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get transactions (both incoming and outgoing)
        transactions = db.query(Transaction).filter(
            (Transaction.from_account_id == account.id) |
            (Transaction.to_account_id == account.id)
        ).order_by(Transaction.created_at.desc())\
         .limit(limit)\
         .offset(offset)\
         .all()
        
        span.set_attribute("transaction_count", len(transactions))
        
        return [TransactionResponse.from_orm(t) for t in transactions]

