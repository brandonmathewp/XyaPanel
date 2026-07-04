"""Authentication and authorization service: JWT, passwords, invite codes."""

from __future__ import annotations

import hashlib
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.config import settings
from app.core.database import get_database
from app.models.auth import (
    AdminDocument,
    ClientSessionDocument,
    InviteCodeDocument,
    ResellerDocument,
    UserRole,
)

# ---------------------------------------------------------------------------
# Password hashing
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_jwt_token(subject: str, role: UserRole, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expiry_minutes)
    )
    claims = {
        "sub": subject,
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------


def _admins() -> AsyncIOMotorCollection:
    return get_database()["admins"]


def _resellers() -> AsyncIOMotorCollection:
    return get_database()["resellers"]


def _invite_codes() -> AsyncIOMotorCollection:
    return get_database()["invite_codes"]


def _client_sessions() -> AsyncIOMotorCollection:
    return get_database()["client_sessions"]


# ---------------------------------------------------------------------------
# Admin bootstrap
# ---------------------------------------------------------------------------


async def bootstrap_admin() -> None:
    """Ensure exactly one admin account exists. If none, create from env config."""
    coll = _admins()
    count = await coll.count_documents({})
    if count > 0:
        return

    if not settings.admin_email or not settings.admin_password_hash:
        raise RuntimeError(
            "No admin account found and ADMIN_EMAIL/ADMIN_PASSWORD_HASH not configured. "
            "Set ADMIN_PASSWORD_HASH to a bcrypt hash of your initial password."
        )

    doc = AdminDocument(
        email=settings.admin_email,
        password_hash=settings.admin_password_hash,
    )
    await coll.insert_one(doc.model_dump())


async def authenticate_admin(email: str, password: str) -> str | None:
    """Verify admin credentials and return a JWT token, or None on failure."""
    coll = _admins()
    doc = await coll.find_one({"email": email})
    if doc is None:
        return None
    admin = AdminDocument(**doc)
    if not verify_password(password, admin.password_hash):
        return None
    return create_jwt_token(email, UserRole.ADMIN)


# ---------------------------------------------------------------------------
# Reseller auth
# ---------------------------------------------------------------------------


async def authenticate_reseller(username: str, password: str) -> str | None:
    """Verify reseller credentials and return a JWT token, or None on failure."""
    coll = _resellers()
    doc = await coll.find_one({"username": username})
    if doc is None:
        return None
    reseller = ResellerDocument(**doc)
    if not verify_password(password, reseller.password_hash):
        return None
    return create_jwt_token(str(doc["_id"]), UserRole.RESELLER)


async def register_reseller(
    username: str,
    email: str,
    password: str,
    invite_code: str,
) -> ResellerDocument | None:
    """Register a new reseller by redeeming an invite code. Returns None on failure."""
    inv_coll = _invite_codes()
    res_coll = _resellers()

    # Find and validate the invite code
    code_doc = await inv_coll.find_one({"code": invite_code})
    if code_doc is None:
        return None

    invite = InviteCodeDocument(**code_doc)
    now = datetime.now(tz=timezone.utc)

    if invite.used_by is not None:
        return None  # already used
    if invite.expires_at < now:
        return None  # expired

    # Check username / email uniqueness
    existing = await res_coll.find_one(
        {"$or": [{"username": username}, {"email": email}]}
    )
    if existing is not None:
        return None

    # Create reseller
    reseller = ResellerDocument(
        username=username,
        email=email,
        password_hash=hash_password(password),
        invited_by=invite.created_by,
    )
    result = await res_coll.insert_one(reseller.model_dump())

    # Mark invite code as used
    await inv_coll.update_one(
        {"code": invite_code},
        {"$set": {"used_by": str(result.inserted_id), "used_at": now}},
    )

    return reseller


# ---------------------------------------------------------------------------
# Invite code management (admin only)
# ---------------------------------------------------------------------------


async def generate_invite_codes(count: int, expires_in_hours: int) -> list[str]:
    """Generate admin invite codes. Returns the list of code strings."""
    coll = _invite_codes()
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(hours=expires_in_hours)

    codes: list[str] = []
    docs: list[dict[str, Any]] = []
    for _ in range(count):
        code = f"xya-inv-{secrets.token_hex(16)}"
        codes.append(code)
        docs.append(
            InviteCodeDocument(
                code=code,
                created_by="admin",
                expires_at=expires_at,
            ).model_dump()
        )

    await coll.insert_many(docs)
    return codes


async def list_invite_codes() -> list[dict[str, Any]]:
    """List all invite codes (admin only)."""
    coll = _invite_codes()
    cursor = coll.find().sort("created_at", -1)
    results: list[dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["is_used"] = doc.get("used_by") is not None
        results.append(doc)
    return results


# ---------------------------------------------------------------------------
# Client session management
# ---------------------------------------------------------------------------


async def create_client_session(
    license_key: str,
    hwid: str,
    product_id: str,
    session_key: str,
) -> str:
    """Create a client session and return the session ID.

    session_key is the derived AES-256 key (from HKDF) for this session.
    We store a hash of it for verification during encrypted requests.
    """
    coll = _client_sessions()
    session_doc = ClientSessionDocument(
        license_key=license_key,
        hwid=hwid,
        product_id=product_id,
        session_key_hash=hashlib.sha256(session_key.encode()).hexdigest(),
    )
    result = await coll.insert_one(session_doc.model_dump())
    return str(result.inserted_id)


async def verify_client_session(session_id: str) -> ClientSessionDocument | None:
    """Verify a client session exists and return it, or None."""
    from bson import ObjectId

    coll = _client_sessions()
    try:
        doc = await coll.find_one({"_id": ObjectId(session_id)})
    except Exception:
        return None
    if doc is None:
        return None
    return ClientSessionDocument(**doc)


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------


async def setup_auth_indexes() -> None:
    """Create MongoDB indexes for auth-related collections."""
    await _admins().create_index("email", unique=True)
    await _resellers().create_index("username", unique=True)
    await _resellers().create_index("email", unique=True)
    await _invite_codes().create_index("code", unique=True)
    await _client_sessions().create_index("license_key")