"""
Payment Service - Main Application Entry Point

Clean, modular structure with separated concerns.
Focus on Idempotency and State Machine patterns.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.observability import instrument_app
from app.api import health, payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"Starting {settings.service_name}...")
    init_db()
    yield
    # Shutdown
    print(f"Shutting down {settings.service_name}...")


# Create FastAPI application
app = FastAPI(
    title="Payment Service",
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
app.include_router(payments.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)


