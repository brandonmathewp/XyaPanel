"""Celery application configuration for XyaPanel."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "xya_panel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.watermark"],
)

# Optional serialization config
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Re-deliver on worker crash
    worker_prefetch_multiplier=1,  # One task at a time (watermarking is CPU/IO heavy)
)
