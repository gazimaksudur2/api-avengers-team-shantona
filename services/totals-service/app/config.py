"""
Configuration and Environment Variables
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Info
    service_name: str = "totals-service"
    version: str = "1.0.0"
    debug: bool = True
    
    # Database (shared with donation service)
    database_url: str = "postgresql://postgres:postgres@localhost:5432/donations_db"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    
    # Redis
    redis_url: str = "redis://localhost:6379/2"
    cache_ttl: int = 30  # seconds
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    
    # OpenTelemetry
    otel_endpoint: str = "http://localhost:4317"
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings(
    database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/donations_db"),
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/2"),
    rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    service_name=os.getenv("SERVICE_NAME", "totals-service"),
    cache_ttl=int(os.getenv("CACHE_TTL", "30"))
)

