"""
FastAPI Dependencies
"""
import redis
from app.config import settings

# Redis client (singleton)
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def get_redis():
    """Dependency to get Redis client"""
    return redis_client


