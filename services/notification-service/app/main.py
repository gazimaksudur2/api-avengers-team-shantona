"""
Notification Service - Main Application Entry Point

Clean, modular structure with separated concerns.
Sends donor confirmations via email, SMS, and webhooks.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.observability import instrument_app
from app.api import health, notifications
from utils.consumer import start_consumer, stop_consumer


# Global consumer thread reference
event_consumer_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global event_consumer_thread
    
    # Startup
    print(f"Starting {settings.service_name}...")
    init_db()
    
    # Start event consumer
    event_consumer_thread = start_consumer()
    print("✓ Event consumer started")
    
    yield
    
    # Shutdown
    print(f"Shutting down {settings.service_name}...")
    stop_consumer()
    if event_consumer_thread:
        event_consumer_thread.join(timeout=5)


# Create FastAPI application
app = FastAPI(
    title="Notification Service",
    version=settings.version,
    lifespan=lifespan
)

# Instrument with OpenTelemetry
instrument_app(app)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(notifications.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

