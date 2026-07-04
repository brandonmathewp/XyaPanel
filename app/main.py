"""XyaPanel — FastAPI application entry point."""

from __future__ import annotations

import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import connect_to_db, close_db_connection
from app.core.schema import init_schema
from app.core.security import NoSQLInjectionMiddleware, RateLimitMiddleware
from app.routers.license import router as license_router
from app.routers.auth import router as auth_router
from app.routers.product import router as product_router
from app.routers.heartbeat import router as heartbeat_router
from app.routers.reseller import router as reseller_router
from app.services.auth_service import bootstrap_admin
from app.services.heartbeat_service import sweep_missed_heartbeats


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_db()
    await init_schema()
    await bootstrap_admin()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(sweep_missed_heartbeats, "interval", seconds=60, id="heartbeat_sweep")
    scheduler.start()

    yield

    scheduler.shutdown(wait=False)
    await close_db_connection()


app = FastAPI(
    title="XyaPanel",
    description="Licensing panel system for generating, distributing, and validating software license keys.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(NoSQLInjectionMiddleware)

app.include_router(license_router)
app.include_router(auth_router)
app.include_router(product_router)
app.include_router(heartbeat_router)
app.include_router(reseller_router)


FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@app.middleware("http")
async def api_prefix_middleware(request, call_next):
    """Strip /api prefix so the React dashboard can call /api/* endpoints directly."""
    if request.url.path.startswith("/api/"):
        request.scope["path"] = request.url.path[4:]  # strip "/api"
        # Also clear raw_path if present (ASGI optional, but keeps routing consistent)
        if "raw_path" in request.scope:
            request.scope["raw_path"] = request.scope["raw_path"][4:]
    return await call_next(request)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": app.version}


if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
