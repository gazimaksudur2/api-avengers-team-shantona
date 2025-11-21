"""
Configuration and Environment Variables
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Info
    service_name: str = "bank-service"
    version: str = "1.0.0"
    debug: bool = True
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/bank_db"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    
    # Redis
    redis_url: str = "redis://localhost:6379/4"
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    
    # OpenTelemetry
    otel_endpoint: str = "http://localhost:4317"
    
    # Banking Settings
    initial_balance: float = 0.0
    min_transfer_amount: float = 0.01
    max_transfer_amount: float = 1000000.00
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings(
    database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bank_db"),
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/4"),
    rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    service_name=os.getenv("SERVICE_NAME", "bank-service")
)

