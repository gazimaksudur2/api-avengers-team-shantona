"""
Configuration and Environment Variables
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Info
    service_name: str = "notification-service"
    version: str = "1.0.0"
    debug: bool = True
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/notifications_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    
    # OpenTelemetry
    otel_endpoint: str = "http://localhost:4317"
    
    # Email Providers
    sendgrid_api_key: str = "dummy"
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings(
    database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/notifications_db"),
    rabbitmq_url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    service_name=os.getenv("SERVICE_NAME", "notification-service"),
    sendgrid_api_key=os.getenv("SENDGRID_API_KEY", "dummy")
)

