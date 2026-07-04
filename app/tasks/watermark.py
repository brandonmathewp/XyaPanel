"""Watermarking Celery tasks — embed license-derived HMAC watermark into APK/.so files.

This task is enqueued when a license is generated. On completion,
the license transitions from pending → active.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import get_database
from app.services.watermark_service import watermark_license_artifacts
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _activate_license(license_key: str, apk_path: str | None, so_path: str | None) -> None:
    """Transition license from pending → active and store watermark paths."""
    coll = get_database()["licenses"]
    from datetime import datetime, timezone

    set_fields: dict = {
        "status": "active",
        "updated_at": datetime.now(tz=timezone.utc),
    }
    if apk_path:
        set_fields["apk_watermark"] = apk_path
    if so_path:
        set_fields["so_watermark"] = so_path

    await coll.update_one(
        {"license_key": license_key, "status": "pending"},
        {"$set": set_fields},
    )


async def _fail_license(license_key: str) -> None:
    """Transition license from pending → watermark_failed."""
    coll = get_database()["licenses"]
    from datetime import datetime, timezone

    await coll.update_one(
        {"license_key": license_key, "status": "pending"},
        {"$set": {"status": "watermark_failed", "updated_at": datetime.now(tz=timezone.utc)}},
    )


@celery_app.task(name="watermark_license", bind=True, max_retries=2, default_retry_delay=30)
def watermark_license(self, license_key: str, product_id: str) -> dict:
    """Watermark a newly generated license's artifacts.

    1. Looks up the product's APK and .so source file paths from the DB.
    2. Watermarks both artifacts using HMAC(MASTER_SECRET, license_key).
    3. On success: transitions license status pending → active.
    4. On failure (after retries): transitions license → watermark_failed.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(_run_watermark(product_id, license_key))
        loop.run_until_complete(_activate_license(license_key, result["apk"], result["so"]))
        logger.info("Watermark succeeded, license %s → active", license_key)
        return {"status": "active", "license_key": license_key}
    except Exception as exc:
        logger.error("Watermark failed for license %s: %s", license_key, exc)
        try:
            loop.run_until_complete(_fail_license(license_key))
        except Exception:
            pass
        raise self.retry(exc=exc)


async def _run_watermark(product_id: str, license_key: str):
    """Look up product artifacts and watermark them."""
    db = get_database()
    product = await db["products"].find_one({"product_id": product_id})
    if product is None:
        raise ValueError(f"Product '{product_id}' not found")

    apk_source = product.get("apk_artifact_path")
    so_source = product.get("so_artifact_path")

    if not apk_source and not so_source:
        # No artifacts to watermark — activate directly
        logger.info("No artifacts for product %s, activating license %s directly", product_id, license_key)
        return {"apk": None, "so": None}

    import os
    output_dir = os.path.join("artifacts", "watermarked")

    return await watermark_license_artifacts(
        product_id=product_id,
        license_key=license_key,
        apk_source=apk_source,
        so_source=so_source,
        output_dir=output_dir,
    )
