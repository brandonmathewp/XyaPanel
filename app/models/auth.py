"""Authentication-related Pydantic models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    ADMIN = "admin"
    RESELLER = "reseller"
    CLIENT = "client"


# ---------------------------------------------------------------------------
# MongoDB document models
# ---------------------------------------------------------------------------


class AdminDocument(BaseModel):
    """The single admin account stored in MongoDB."""

    email: str
    password_hash: str
    role: str = "admin"
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class ResellerDocument(BaseModel):
    """Reseller account stored in MongoDB."""

    username: str
    email: str
    password_hash: str
    balance: float = 0.0
    invited_by: str  # admin id
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class InviteCodeDocument(BaseModel):
    """Single-use invite code for reseller registration."""

    code: str
    created_by: str  # admin id
    used_by: str | None = None  # reseller id after redemption
    expires_at: datetime
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class ClientSessionDocument(BaseModel):
    """Client session derived from license validation."""

    license_key: str
    hwid: str
    product_id: str
    session_key_hash: str  # hash of the derived AES session key for verification
    established_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_heartbeat_at: datetime | None = None


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class ResellerLoginRequest(BaseModel):
    username: str
    password: str


class ResellerRegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    invite_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


class InviteCodeCreateRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=50)
    expires_in_hours: int = Field(default=72, ge=1, le=168)  # max 7 days


class InviteCodeResponse(BaseModel):
    code: str
    expires_at: datetime
    is_used: bool


# ---------------------------------------------------------------------------
# Client auth (two-stage login)
# ---------------------------------------------------------------------------


class ClientVersionCheckRequest(BaseModel):
    """Stage 1: APK version check (pre-login, unencrypted per spec)."""

    product_id: str
    apk_version: str


class ClientVersionCheckResponse(BaseModel):
    """Response to APK version check."""

    version_valid: bool
    latest_version: str
    min_version: str
    update_required: bool
    reason: str | None = None


class ClientLoginRequest(BaseModel):
    """Stage 2: .so check / full login (post-version-check)."""

    license_key: str
    hwid: str
    product_id: str
    so_version: str


class ClientLoginResponse(BaseModel):
    """Response to client login — establishes a session."""

    session_id: str
    features: list[str]
    expiry_date: datetime | None = None
    heartbeat_interval_seconds: int = 600  # 10 minutes
