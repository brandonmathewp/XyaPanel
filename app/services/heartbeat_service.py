"""Heartbeat service: process heartbeats, detect missed heartbeats (SQLite)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.database import get_db

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL_MINUTES = 10
_HEARTBEAT_GRACE_MINUTES = 1
_MISSED_THRESHOLD = _HEARTBEAT_INTERVAL_MINUTES + _HEARTBEAT_GRACE_MINUTES


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def process_heartbeat(license_key: str, hwid: str) -> dict | None:
    db = get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM licenses WHERE license_key = ?", (license_key,)
    )
    if not rows:
        return None
    doc = rows[0]
    if doc["hwid"] != hwid:
        return None
    if doc["status"] not in ("active", "paused"):
        return None

    now = _now()
    await db.execute(
        "UPDATE licenses SET last_heartbeat_at = ?, updated_at = ? WHERE license_key = ?",
        (now, now, license_key),
    )
    await db.commit()

    import json
    features = doc["features"]
    if isinstance(features, str):
        features = json.loads(features)

    return {
        "status": doc["status"],
        "features": features,
        "last_heartbeat_at": now,
    }


async def sweep_missed_heartbeats() -> int:
    db = get_db()
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=_MISSED_THRESHOLD)).isoformat()
    now = _now()

    cursor = await db.execute(
        """UPDATE licenses SET status = 'paused', pause_reason = 'missed_heartbeat',
           flagged_for_review = 1, updated_at = ?
           WHERE status = 'active' AND (last_heartbeat_at IS NULL OR last_heartbeat_at < ?)""",
        (now, cutoff),
    )
    await db.commit()
    count = cursor.rowcount
    if count > 0:
        logger.info("Heartbeat sweep: auto-paused %d license(s)", count)
    return count
