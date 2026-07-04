"""License-related Pydantic models and MongoDB document schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LicenseStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"
    EXPIRED = "expired"
    WATERMARK_FAILED = "watermark_failed"


class PauseReason(str, Enum):
    ADMIN_MANUAL = "admin_manual"
    MISSED_HEARTBEAT = "missed_heartbeat"


class LicenseDuration(str, Enum):
    TWO_HOURS = "2_hours"
    ONE_DAY = "1_day"
    THREE_DAYS = "3_days"
    ONE_WEEK = "1_week"
    ONE_MONTH = "1_month"
    TWO_MONTHS = "2_months"
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"
    LIFETIME = "lifetime"


# ---------------------------------------------------------------------------
# MongoDB document model (used for DB read/write)
# ---------------------------------------------------------------------------


class LicenseDocument(BaseModel):
    """Shape of a license document in MongoDB."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    product_id: str
    license_key: str
    customer: str | None = None
    hwid: str | None = None
    issue_date: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    expiry_date: datetime | None = None
    status: LicenseStatus = LicenseStatus.PENDING
    duration: LicenseDuration
    features: list[str] = Field(default_factory=list)
    last_heartbeat_at: datetime | None = None
    pause_reason: PauseReason | None = None
    flagged_for_review: bool = False
    apk_watermark: str | None = None
    so_watermark: str | None = None
    created_by: str | None = None  # "admin" | reseller_id
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class LicenseCreateRequest(BaseModel):
    """Admin or reseller issuing a new license key."""

    product_id: str
    customer: str | None = None
    duration: LicenseDuration
    features: list[str] = Field(default_factory=list)


class LicenseResponse(BaseModel):
    """Public license response shape (no internal secrets)."""

    id: str = Field(alias="_id")
    product_id: str
    license_key: str
    customer: str | None = None
    hwid: str | None = None
    issue_date: datetime
    expiry_date: datetime | None = None
    status: LicenseStatus
    duration: LicenseDuration
    features: list[str]
    last_heartbeat_at: datetime | None = None
    pause_reason: PauseReason | None = None
    flagged_for_review: bool
    created_by: str | None = None
    created_at: datetime


class LicenseValidationRequest(BaseModel):
    """Client request to validate / activate a license key."""

    license_key: str
    hwid: str
    product_id: str
    app_version: str  # informational – can be logged for diagnostics


class LicenseValidationResponse(BaseModel):
    """Response to a successful validation (server → client)."""

    valid: bool
    status: LicenseStatus | None = None
    features: list[str] = Field(default_factory=list)
    expiry_date: datetime | None = None
    reason: str | None = None  # populated on rejection: "invalid_key", "pending", "revoked", etc.


class LicenseListParams(BaseModel):
    """Query parameters for listing licenses."""

    status: LicenseStatus | None = None
    product_id: str | None = None
    flagged_for_review: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
