"""XyaPanel — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.routers.license import router as license_router
from app.services.license_service import setup_license_indexes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await connect_to_mongo()
    await setup_license_indexes()
    yield
    await close_mongo_connection()


app = FastAPI(
    title="XyaPanel",
    description="Licensing panel system for generating, distributing, and validating software license keys.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(license_router)


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "version": app.version}