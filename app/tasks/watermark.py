"""Watermarking Celery tasks — embed license-derived watermark into APK/.so files.

This module contains the background task that watermarks the product artifacts
(APK and .so) with a license-specific HMAC, then transitions the license from
pending → active (or watermark_failed on error).
"""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import logging

from app.core.config import settings
from app.services.license_service import activate_license, mark_watermark_failed
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _compute_watermark(license_key: str) -> str:
    """Compute HMAC-SHA256 watermark for a given license key.

    Uses the server's master secret as the HMAC key.
    """
    return hmac.new(
        settings.master_secret.encode(),
        license_key.encode(),
        hashlib.sha256,
    ).hexdigest()


async def _async_watermark_artifacts(product_id: str, license_key: str) -> bool:
    """Watermark the product's APK and .so files with the license key's HMAC.

    Returns True on success, False on failure.

    This is a skeleton — actual APK (ZIP) and .so (ELF) binary manipulation
    will be implemented as a dedicated Phase 1 sub-task.
    """
    watermark = _compute_watermark(license_key)

    # TODO: Actual binary watermarking implementation
    # - Locate the product's original APK/.so files (stored on disk / GridFS)
    # - For APK (ZIP format): embed watermark as a file entry or ZIP comment
    # - For .so (ELF format): embed watermark in a .note section or similar
    # - Write watermarked copies to an artifacts/ directory or designated storage
    # - Update the license document with watermark hashes

    logger.info(
        "Watermark task (skeleton): product=%s license=%s watermark=%s",
        product_id,
        license_key,
        watermark,
    )
    return True


@celery_app.task(name="watermark_license", bind=True, max_retries=2, default_retry_delay=30)
def watermark_license(self, license_key: str, product_id: str) -> dict[str, str]:
    """Watermark a newly generated license's artifacts.

    On success: transitions license from pending → active.
    On failure (after retries): transitions license from pending → watermark_failed.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        success = loop.run_until_complete(
            _async_watermark_artifacts(product_id, license_key)
        )
        if success:
            loop.run_until_complete(activate_license(license_key))
            logger.info("Watermark succeeded, license %s → active", license_key)
            return {"status": "active", "license_key": license_key}
        else:
            raise RuntimeError("Watermarking returned False")
    except Exception as exc:
        logger.error("Watermark failed for license %s: %s", license_key, exc)
        try:
            loop.run_until_complete(mark_watermark_failed(license_key))
            logger.warning("License %s → watermark_failed", license_key)
        except Exception as inner_exc:
            logger.error(
                "Failed to mark license %s as watermark_failed: %s",
                license_key,
                inner_exc,
            )
        # Re-raise so Celery can retry or mark as failed
        raise self.retry(exc=exc)
