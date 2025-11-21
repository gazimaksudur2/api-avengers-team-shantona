"""
Configuration and Environment Variables
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Info
    service_name: str = "payment-service"
    version: str = "1.0.0"
    debug: bool = True
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/payments_db"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    
    # Redis
    redis_url: str = "redis://localhost:6379/1"
    idempotency_ttl: int = 86400  # 24 hours
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    
    # OpenTelemetry
    otel_endpoint: str = "http://localhost:4317"
    
    # Payment Gateways
    stripe_api_key: str = "sk_test_dummy"
    webhook_secret: str = "whsec_dummy"
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings(
    database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/payments_db"),
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
    rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    service_name=os.getenv("SERVICE_NAME", "payment-service"),
    stripe_api_key=os.getenv("STRIPE_API_KEY", "sk_test_dummy"),
    webhook_secret=os.getenv("WEBHOOK_SECRET", "whsec_dummy")
)


