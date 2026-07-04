"""Heartbeat service: process heartbeats, detect missed heartbeats."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.license import LicenseStatus, PauseReason

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_MINUTES = 10
_HEARTBEAT_GRACE_MINUTES = 1
_MISSED_THRESHOLD = _HEARTBEAT_INTERVAL_MINUTES + _HEARTBEAT_GRACE_MINUTES  # 11 minutes


def _licenses() -> AsyncIOMotorCollection:
    return get_database()["licenses"]


async def process_heartbeat(license_key: str, hwid: str) -> dict | None:
    """Process a heartbeat from the client.

    Verifies the license key + HWID match, updates last_heartbeat_at,
    and returns the current features list for piggybacking.

    Returns None if the license is not found or HWID doesn't match.
    """
    coll = _licenses()
    doc = await coll.find_one({"license_key": license_key})

    if doc is None:
        logger.warning("Heartbeat: license %s not found", license_key)
        return None

    # Verify HWID
    if doc.get("hwid") != hwid:
        logger.warning("Heartbeat: HWID mismatch for license %s", license_key)
        return None

    # Verify license is in a state that allows heartbeats
    status = doc.get("status")
    if status not in (LicenseStatus.ACTIVE, LicenseStatus.PAUSED):
        logger.warning(
            "Heartbeat: license %s is %s, rejecting", license_key, status
        )
        return None

    # Update last_heartbeat_at
    now = datetime.now(tz=timezone.utc)
    await coll.update_one(
        {"license_key": license_key},
        {"$set": {"last_heartbeat_at": now, "updated_at": now}},
    )

    return {
        "status": doc.get("status"),
        "features": doc.get("features", []),
        "last_heartbeat_at": now.isoformat(),
    }


async def sweep_missed_heartbeats() -> int:
    """Background job: find licenses with missed heartbeats and auto-pause them.

    A heartbeat is considered missed if last_heartbeat_at is older than
    11 minutes (10min interval + 1min grace) AND the license is still active.

    Returns the number of licenses auto-paused.
    """
    coll = _licenses()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=_MISSED_THRESHOLD)
    now = datetime.now(tz=timezone.utc)

    # Find active licenses whose last heartbeat is too old (or never set, but active)
    query = {
        "status": LicenseStatus.ACTIVE,
        "$or": [
            {"last_heartbeat_at": {"$lt": cutoff}},
            {"last_heartbeat_at": None},
        ],
    }

    # Also find PAUSED licenses that haven't been flagged yet (just in case)
    # Actually, the spec says: auto-pause + flag active licenses with missed heartbeats

    result = await coll.update_many(
        query,
        {
            "$set": {
                "status": LicenseStatus.PAUSED,
                "pause_reason": PauseReason.MISSED_HEARTBEAT,
                "flagged_for_review": True,
                "updated_at": now,
            }
        },
    )

    count = result.modified_count
    if count > 0:
        logger.info("Heartbeat sweep: auto-paused %d license(s)", count)

    return count
