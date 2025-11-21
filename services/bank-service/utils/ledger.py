"""
Ledger Operations - Double-Entry Bookkeeping
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import BankAccount, Transaction


def execute_transfer(
    from_account: BankAccount,
    to_account: BankAccount,
    amount: float,
    description: str,
    db: Session
) -> Transaction:
    """
    Execute a transfer with double-entry bookkeeping
    
    Args:
        from_account: Source account
        to_account: Destination account
        amount: Transfer amount
        description: Transfer description
        db: Database session
    
    Returns:
        Transaction record
    
    Raises:
        Exception if transfer fails
    """
    try:
        # Create transaction record
        transaction = Transaction(
            id=uuid.uuid4(),
            transaction_type="TRANSFER",
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            amount=amount,
            currency=from_account.currency,
            status="PENDING",
            description=description,
            created_at=datetime.utcnow()
        )
        db.add(transaction)
        db.flush()
        
        # Update balances (double-entry)
        from_account.balance -= amount
        from_account.updated_at = datetime.utcnow()
        from_account.version += 1
        
        to_account.balance += amount
        to_account.updated_at = datetime.utcnow()
        to_account.version += 1
        
        # Mark transaction as completed
        transaction.status = "COMPLETED"
        transaction.completed_at = datetime.utcnow()
        
        # Commit all changes atomically
        db.commit()
        db.refresh(transaction)
        
        return transaction
        
    except Exception as e:
        db.rollback()
        if 'transaction' in locals():
            transaction.status = "FAILED"
            db.commit()
        raise Exception(f"Transfer failed: {str(e)}")


def get_account_balance(account_id: uuid.UUID, db: Session) -> float:
    """
    Get current account balance
    
    Args:
        account_id: Account UUID
        db: Database session
    
    Returns:
        Current balance
    """
    account = db.query(BankAccount).filter(BankAccount.id == account_id).first()
    if not account:
        raise ValueError("Account not found")
    return float(account.balance)


def reverse_transaction(transaction_id: uuid.UUID, db: Session) -> Transaction:
    """
    Reverse a completed transaction
    
    Args:
        transaction_id: Transaction UUID
        db: Database session
    
    Returns:
        Reversal transaction record
    """
    original = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not original:
        raise ValueError("Transaction not found")
    
    if original.status != "COMPLETED":
        raise ValueError("Only completed transactions can be reversed")
    
    if original.transaction_type != "TRANSFER":
        raise ValueError("Only transfers can be reversed")
    
    # Get accounts
    from_account = db.query(BankAccount).filter(BankAccount.id == original.from_account_id).first()
    to_account = db.query(BankAccount).filter(BankAccount.id == original.to_account_id).first()
    
    # Execute reverse transfer
    reversal = execute_transfer(
        from_account=to_account,  # Swap accounts
        to_account=from_account,
        amount=original.amount,
        description=f"Reversal of transaction {transaction_id}",
        db=db
    )
    
    # Mark original as reversed
    original.status = "REVERSED"
    db.commit()
    
    return reversal

