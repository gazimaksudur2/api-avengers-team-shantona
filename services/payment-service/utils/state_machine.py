"""
State Machine Utilities for Payment Status Transitions
"""
from typing import Dict, List

# Valid state transitions
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "INITIATED": ["AUTHORIZED", "FAILED"],
    "AUTHORIZED": ["CAPTURED", "FAILED", "REFUNDED"],
    "CAPTURED": ["REFUNDED"],
    "FAILED": [],  # Terminal state
    "REFUNDED": []  # Terminal state
}


def validate_state_transition(current_status: str, new_status: str) -> bool:
    """
    Validate if state transition is allowed
    
    Args:
        current_status: Current payment status
        new_status: Desired new status
    
    Returns:
        True if transition is valid, False otherwise
    """
    return new_status in VALID_TRANSITIONS.get(current_status, [])


def get_allowed_transitions(current_status: str) -> List[str]:
    """
    Get list of allowed transitions from current status
    
    Args:
        current_status: Current payment status
    
    Returns:
        List of allowed next statuses
    """
    return VALID_TRANSITIONS.get(current_status, [])


