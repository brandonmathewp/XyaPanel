"""XyaPanel — FastAPI application entry point."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": app.version}
