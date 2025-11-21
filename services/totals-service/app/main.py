"""
Totals Service - Main Application Entry Point

Clean, modular structure with separated concerns.
Optimized fundraising analytics with multi-level caching.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_materialized_view
from app.observability import instrument_app
from app.api import health, totals
from utils.consumer import start_consumer, stop_consumer


# Global consumer thread reference
event_consumer_thread = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global event_consumer_thread
    
    # Startup
    print(f"Starting {settings.service_name}...")
    
    # Initialize materialized view
    init_materialized_view()
    
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
    title="Totals Service",
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
app.include_router(totals.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

