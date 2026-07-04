"""Watermarking Celery tasks (SQLite)."""

from __future__ import annotations

import asyncio
import logging

from app.core.database import get_db
from app.services.watermark_service import watermark_license_artifacts
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _activate_license(license_key: str, apk_path: str | None, so_path: str | None) -> None:
    db = get_db()
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).isoformat()
    sets = ["status = 'active'", "updated_at = ?"]
    vals = [now]
    if apk_path:
        sets.append("apk_watermark = ?")
        vals.append(apk_path)
    if so_path:
        sets.append("so_watermark = ?")
        vals.append(so_path)
    vals.append(license_key)
    await db.execute(
        f"UPDATE licenses SET {', '.join(sets)} WHERE license_key = ? AND status = 'pending'",
        vals,
    )
    await db.commit()


async def _fail_license(license_key: str) -> None:
    db = get_db()
    from datetime import datetime, timezone
    await db.execute(
        "UPDATE licenses SET status = 'watermark_failed', updated_at = ? WHERE license_key = ? AND status = 'pending'",
        (datetime.now(tz=timezone.utc).isoformat(), license_key),
    )
    await db.commit()


@celery_app.task(name="watermark_license", bind=True, max_retries=2, default_retry_delay=30)
def watermark_license(self, license_key: str, product_id: str) -> dict:
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
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM products WHERE product_id = ?", (product_id,))
    if not rows:
        raise ValueError(f"Product '{product_id}' not found")

    product = rows[0]
    apk_source = product["apk_artifact_path"]
    so_source = product["so_artifact_path"]

    if not apk_source and not so_source:
        logger.info("No artifacts for product %s, activating license %s directly", product_id, license_key)
        return {"apk": None, "so": None}

    import os
    output_dir = os.path.join("artifacts", "watermarked")

    return await watermark_license_artifacts(
        product_id=product_id, license_key=license_key,
        apk_source=apk_source, so_source=so_source, output_dir=output_dir,
    )
