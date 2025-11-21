"""
Idempotency Utilities - Dual-layer (Redis + DB) deduplication
"""
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import IdempotencyKey
from app.dependencies import get_redis
from app.observability import idempotency_cache_hits
from app.config import settings


def generate_idempotency_key(content: str) -> str:
    """
    Generate idempotency key from content
    
    Args:
        content: String content to hash
    
    Returns:
        SHA256 hash as idempotency key
    """
    return hashlib.sha256(content.encode()).hexdigest()


def check_idempotency_cache(key: str) -> Optional[Tuple[str, int]]:
    """
    Check Redis cache for idempotency key (L1 - Fast)
    
    Args:
        key: Idempotency key
    
    Returns:
        Tuple of (response_body, status_code) if found, None otherwise
    """
    redis_client = get_redis()
    cached = redis_client.get(f"idem:{key}")
    
    if cached:
        idempotency_cache_hits.labels(cache_type="redis").inc()
        data = json.loads(cached)
        return (data["body"], data["status"])
    
    return None


def check_idempotency_db(key: str, db: Session) -> Optional[Tuple[str, int]]:
    """
    Check database for idempotency key (L2 - Slower but persistent)
    
    Args:
        key: Idempotency key
        db: Database session
    
    Returns:
        Tuple of (response_body, status_code) if found, None otherwise
    """
    existing = db.query(IdempotencyKey).filter_by(key=key).first()
    
    if existing:
        idempotency_cache_hits.labels(cache_type="database").inc()
        
        # Warm up Redis cache
        redis_client = get_redis()
        redis_client.setex(
            f"idem:{key}",
            settings.idempotency_ttl,
            json.dumps({"body": existing.response_body, "status": existing.response_status})
        )
        
        return (existing.response_body, existing.response_status)
    
    return None


def save_idempotency_record(key: str, response_body: str, status: int, db: Session):
    """
    Save idempotency record to both Redis and DB
    
    Args:
        key: Idempotency key
        response_body: Response body to store
        status: HTTP status code
        db: Database session
    """
    expires_at = datetime.utcnow() + timedelta(seconds=settings.idempotency_ttl)
    
    # Save to Redis (fast path)
    redis_client = get_redis()
    redis_client.setex(
        f"idem:{key}",
        settings.idempotency_ttl,
        json.dumps({"body": response_body, "status": status})
    )
    
    # Save to DB (persistent)
    idem_record = IdempotencyKey(
        key=key,
        response_body=response_body,
        response_status=status,
        expires_at=expires_at
    )
    try:
        db.add(idem_record)
        db.commit()
    except IntegrityError:
        # Already exists, that's fine
        db.rollback()


