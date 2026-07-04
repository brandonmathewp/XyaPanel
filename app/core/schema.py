"""SQLite schema initialization — creates all tables if they don't exist."""

from __future__ import annotations

from app.core.database import get_db


async def init_schema() -> None:
    """Create all tables and indexes. Idempotent (IF NOT EXISTS)."""
    db = get_db()

    await db.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resellers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0.0,
            invited_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS invite_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL,
            used_by TEXT,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS client_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            hwid TEXT NOT NULL,
            product_id TEXT NOT NULL,
            session_key_hash TEXT NOT NULL,
            established_at TEXT NOT NULL,
            last_heartbeat_at TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            durations TEXT NOT NULL DEFAULT '[]',
            features TEXT NOT NULL DEFAULT '[]',
            apk_latest_version TEXT NOT NULL DEFAULT '1.0.0',
            apk_min_version TEXT NOT NULL DEFAULT '1.0.0',
            so_latest_version TEXT NOT NULL DEFAULT '1.0.0',
            so_min_version TEXT NOT NULL DEFAULT '1.0.0',
            store_enabled INTEGER NOT NULL DEFAULT 1,
            apk_artifact_path TEXT,
            so_artifact_path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL UNIQUE,
            product_id TEXT NOT NULL,
            customer TEXT,
            hwid TEXT,
            issue_date TEXT NOT NULL,
            expiry_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            duration TEXT NOT NULL,
            features TEXT NOT NULL DEFAULT '[]',
            last_heartbeat_at TEXT,
            pause_reason TEXT,
            flagged_for_review INTEGER NOT NULL DEFAULT 0,
            apk_watermark TEXT,
            so_watermark TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reseller_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reseller_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            duration TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(reseller_id, product_id, duration)
        );

        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reseller_id TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            resulting_balance REAL NOT NULL,
            product_id TEXT,
            duration TEXT,
            external_ref TEXT,
            note TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_licenses_product ON licenses(product_id);
        CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);
        CREATE INDEX IF NOT EXISTS idx_licenses_created_by ON licenses(created_by);
        CREATE INDEX IF NOT EXISTS idx_licenses_flagged ON licenses(flagged_for_review);
        CREATE INDEX IF NOT EXISTS idx_licenses_hwid ON licenses(hwid);
        CREATE INDEX IF NOT EXISTS idx_licenses_heartbeat ON licenses(last_heartbeat_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_license ON client_sessions(license_key);
        CREATE INDEX IF NOT EXISTS idx_ledger_reseller ON ledger(reseller_id);
        CREATE INDEX IF NOT EXISTS idx_ledger_created ON ledger(created_at);
    """)

    await db.commit()
