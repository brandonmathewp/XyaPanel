"""Auth service: JWT, passwords, invite codes, sessions (SQLite)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import get_db
from app.models.auth import UserRole


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_jwt_token(subject: str, role: UserRole, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(tz=timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expiry_minutes))
    claims = {
        "sub": subject, "role": role.value,
        "exp": expire, "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


async def bootstrap_admin() -> None:
    db = get_db()
    row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM admins")
    if row[0]["cnt"] > 0:
        return
    if not settings.admin_email or not settings.admin_password_hash:
        raise RuntimeError("No admin account and ADMIN_EMAIL/ADMIN_PASSWORD_HASH not configured")
    await db.execute(
        "INSERT INTO admins (email, password_hash, role, created_at, updated_at) VALUES (?, ?, 'admin', ?, ?)",
        (settings.admin_email, settings.admin_password_hash, _now(), _now()),
    )
    await db.commit()


async def authenticate_admin(email: str, password: str) -> str | None:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM admins WHERE email = ?", (email,))
    if not rows:
        return None
    if not verify_password(password, rows[0]["password_hash"]):
        return None
    return create_jwt_token(str(rows[0]["id"]), UserRole.ADMIN)


# ---------------------------------------------------------------------------
# Reseller
# ---------------------------------------------------------------------------


async def authenticate_reseller(username: str, password: str) -> str | None:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM resellers WHERE username = ?", (username,))
    if not rows:
        return None
    if not verify_password(password, rows[0]["password_hash"]):
        return None
    return create_jwt_token(str(rows[0]["id"]), UserRole.RESELLER)


async def register_reseller(username: str, email: str, password: str, invite_code: str) -> dict | None:
    db = get_db()
    now = _now()

    # Validate invite code
    rows = await db.execute_fetchall("SELECT * FROM invite_codes WHERE code = ?", (invite_code,))
    if not rows:
        return None
    inv = rows[0]
    if inv["used_by"] is not None:
        return None
    if inv["expires_at"] < now:
        return None

    # Check uniqueness
    rows = await db.execute_fetchall(
        "SELECT id FROM resellers WHERE username = ? OR email = ?", (username, email),
    )
    if rows:
        return None

    # Create reseller
    pwh = hash_password(password)
    cursor = await db.execute(
        "INSERT INTO resellers (username, email, password_hash, invited_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (username, email, pwh, inv["created_by"], now, now),
    )
    reseller_id = cursor.lastrowid

    # Mark invite code used
    await db.execute(
        "UPDATE invite_codes SET used_by = ?, used_at = ? WHERE code = ?",
        (str(reseller_id), now, invite_code),
    )
    await db.commit()

    return {"_id": str(reseller_id), "username": username, "email": email}


# ---------------------------------------------------------------------------
# Invite codes
# ---------------------------------------------------------------------------


async def generate_invite_codes(count: int, expires_in_hours: int) -> list[str]:
    db = get_db()
    now = _now()
    expires_at = (datetime.now(tz=timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()
    codes: list[str] = []
    for _ in range(count):
        code = f"xya-inv-{secrets.token_hex(16)}"
        codes.append(code)
        await db.execute(
            "INSERT INTO invite_codes (code, created_by, expires_at, created_at) VALUES (?, 'admin', ?, ?)",
            (code, expires_at, now),
        )
    await db.commit()
    return codes


async def list_invite_codes() -> list[dict]:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM invite_codes ORDER BY created_at DESC")
    results = []
    for r in rows:
        d = dict(r)
        d["_id"] = str(d["id"])
        d["is_used"] = d["used_by"] is not None
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Client sessions
# ---------------------------------------------------------------------------


async def create_client_session(license_key: str, hwid: str, product_id: str, session_key: str) -> str:
    db = get_db()
    key_hash = hashlib.sha256(session_key.encode()).hexdigest()
    now = _now()
    cursor = await db.execute(
        "INSERT INTO client_sessions (license_key, hwid, product_id, session_key_hash, established_at) VALUES (?, ?, ?, ?, ?)",
        (license_key, hwid, product_id, key_hash, now),
    )
    await db.commit()
    return str(cursor.lastrowid)


async def verify_client_session(session_id: str) -> dict | None:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM client_sessions WHERE id = ?", (int(session_id),))
    if not rows:
        return None
    return dict(rows[0])


async def setup_auth_indexes() -> None:
    pass
