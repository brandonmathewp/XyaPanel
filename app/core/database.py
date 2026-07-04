"""SQLite database connection via aiosqlite (async)."""

from __future__ import annotations

import aiosqlite

from app.core.config import settings

_db: aiosqlite.Connection | None = None


async def connect_to_db() -> None:
    """Initialize the aiosqlite connection."""
    global _db
    _db = await aiosqlite.connect(settings.db_name + ".db")
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")


async def close_db_connection() -> None:
    """Close the aiosqlite connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def get_db() -> aiosqlite.Connection:
    """Return the database connection (must be called after connect_to_db)."""
    if _db is None:
        raise RuntimeError("Database not connected — call connect_to_db() at startup.")
    return _db
