"""XyaPanel — FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core.security import NoSQLInjectionMiddleware, RateLimitMiddleware
from app.routers.license import router as license_router
from app.routers.auth import router as auth_router
from app.routers.product import router as product_router
from app.routers.heartbeat import router as heartbeat_router
from app.services.license_service import setup_license_indexes
from app.services.auth_service import setup_auth_indexes, bootstrap_admin
from app.services.product_service import setup_product_indexes
from app.services.heartbeat_service import sweep_missed_heartbeats


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await connect_to_mongo()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sweep_missed_heartbeats, "interval", seconds=60, id="heartbeat_sweep")
    scheduler.start()

    await setup_license_indexes()
    await setup_auth_indexes()
    await setup_product_indexes()
    await bootstrap_admin()
    yield
    scheduler.shutdown(wait=False)
    await close_mongo_connection()


app = FastAPI(
    title="XyaPanel",
    description="Licensing panel system for generating, distributing, and validating software license keys.",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware (applied in reverse order — last added runs first)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(NoSQLInjectionMiddleware)

# Register routers
app.include_router(license_router)
app.include_router(auth_router)
app.include_router(product_router)
app.include_router(heartbeat_router)


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "version": app.version}