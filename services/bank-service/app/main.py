"""
Bank Service - Main Application Entry Point

Core banking system for user accounts and P2P transfers.
Implements idempotent transfers with ACID guarantees.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.observability import instrument_app
from app.api import health, accounts, transactions


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
    title="Bank Service",
    version=settings.version,
    description="Core banking system for accounts and transfers",
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
app.include_router(accounts.router)
app.include_router(transactions.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)

