"""
Admin Service - Main Application Entry Point

Administrative panel for managing campaigns, pledges, and monitoring.
Provides dashboard, analytics, and system-wide health checks.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.observability import instrument_app
from app.api import health, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"Starting {settings.service_name}...")
    print(f"Admin credentials - Username: {settings.admin_username}, Password: {settings.admin_password}")
    yield
    # Shutdown
    print(f"Shutting down {settings.service_name}...")


# Create FastAPI application
app = FastAPI(
    title="Admin Service",
    version=settings.version,
    description="Administrative panel and monitoring",
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
app.include_router(admin.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

