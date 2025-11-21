"""
Configuration and Environment Variables
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Info
    service_name: str = "admin-service"
    version: str = "1.0.0"
    debug: bool = True
    
    # Database (read-only access to main DB)
    database_url: str = "postgresql://postgres:postgres@localhost:5432/donations_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Redis
    redis_url: str = "redis://localhost:6379/5"
    cache_ttl: int = 60  # 1 minute for admin data
    
    # OpenTelemetry
    otel_endpoint: str = "http://localhost:4317"
    
    # Authentication
    jwt_secret: str = "change-this-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours
    
    # Admin Credentials (change in production!)
    admin_username: str = "admin"
    admin_password: str = "admin123"  # Hash this in production
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings(
    database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/donations_db"),
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/5"),
    otel_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
    service_name=os.getenv("SERVICE_NAME", "admin-service"),
    jwt_secret=os.getenv("JWT_SECRET", "change-this-secret-key-in-production"),
    admin_username=os.getenv("ADMIN_USERNAME", "admin"),
    admin_password=os.getenv("ADMIN_PASSWORD", "admin123")
)

