"""
Account Validation Utilities
"""
from sqlalchemy.orm import Session
from app.models import BankAccount


def validate_account_status(account: BankAccount) -> tuple[bool, str]:
    """
    Validate account is in good standing
    
    Returns:
        (is_valid, error_message)
    """
    if account.status != "ACTIVE":
        return False, f"Account is {account.status.lower()}"
    return True, ""


def validate_sufficient_balance(account: BankAccount, amount: float) -> tuple[bool, str]:
    """
    Validate account has sufficient balance
    
    Returns:
        (is_valid, error_message)
    """
    if account.balance < amount:
        return False, f"Insufficient balance. Available: {account.balance}, Required: {amount}"
    return True, ""


def validate_transfer(
    from_account: BankAccount,
    to_account: BankAccount,
    amount: float
) -> tuple[bool, str]:
    """
    Validate a transfer between two accounts
    
    Returns:
        (is_valid, error_message)
    """
    # Validate from_account
    is_valid, error = validate_account_status(from_account)
    if not is_valid:
        return False, f"Source account error: {error}"
    
    # Validate to_account
    is_valid, error = validate_account_status(to_account)
    if not is_valid:
        return False, f"Destination account error: {error}"
    
    # Validate sufficient balance
    is_valid, error = validate_sufficient_balance(from_account, amount)
    if not is_valid:
        return False, error
    
    # Check same account
    if from_account.id == to_account.id:
        return False, "Cannot transfer to same account"
    
    # Check currency match
    if from_account.currency != to_account.currency:
        return False, f"Currency mismatch: {from_account.currency} vs {to_account.currency}"
    
    return True, ""


def generate_account_number() -> str:
    """
    Generate unique account number
    
    Format: YYYYMMDDNNNNNNNN (Year + Month + Day + 8-digit sequence)
    """
    from datetime import datetime
    import random
    
    date_part = datetime.utcnow().strftime("%Y%m%d")
    sequence = str(random.randint(10000000, 99999999))
    
    return f"{date_part}{sequence}"

