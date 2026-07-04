"""MongoDB Atlas connection via Motor (async driver)."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    """Initialize the Motor client and database reference."""
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db_name]


async def close_mongo_connection() -> None:
    """Close the Motor client connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_database() -> AsyncIOMotorDatabase:
    """Return the database instance (must be called after connect_to_mongo)."""
    if _db is None:
        raise RuntimeError("Database not connected — call connect_to_mongo() at startup.")
    return _db
