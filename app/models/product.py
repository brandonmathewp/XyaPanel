"""Product-related Pydantic models and MongoDB document schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.license import LicenseDuration


# ---------------------------------------------------------------------------
# Pricing entry for a specific duration
# ---------------------------------------------------------------------------


class ProductDurationPricing(BaseModel):
    """Price for a (product, duration) combination."""

    duration: LicenseDuration
    price: float = Field(ge=0.0)
    enabled: bool = True  # Admin can pause specific duration in store


# ---------------------------------------------------------------------------
# MongoDB document model
# ---------------------------------------------------------------------------


class ProductDocument(BaseModel):
    """Shape of a product document in MongoDB."""

    model_config = ConfigDict(extra="forbid")

    product_id: str  # immutable once created — used as the canonical reference
    name: str
    description: str | None = None
    durations: list[ProductDurationPricing] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)

    # Version tracking for client two-stage login
    apk_latest_version: str = "1.0.0"
    apk_min_version: str = "1.0.0"
    so_latest_version: str = "1.0.0"
    so_min_version: str = "1.0.0"

    # Store visibility
    store_enabled: bool = True

    # Artifact paths (relative to server artifacts directory)
    apk_artifact_path: str | None = None
    so_artifact_path: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class ProductCreateRequest(BaseModel):
    """Admin creates a new product."""

    product_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    features: list[str] = Field(default_factory=list)
    durations: list[ProductDurationPricing] = Field(default_factory=list)


class ProductUpdateRequest(BaseModel):
    """Admin updates an existing product. product_id cannot be changed."""

    name: str | None = None
    description: str | None = None
    features: list[str] | None = None
    durations: list[ProductDurationPricing] | None = None
    apk_latest_version: str | None = None
    apk_min_version: str | None = None
    so_latest_version: str | None = None
    so_min_version: str | None = None
    store_enabled: bool | None = None


class ProductResponse(BaseModel):
    """Public product response."""

    product_id: str
    name: str
    description: str | None = None
    durations: list[ProductDurationPricing]
    features: list[str]
    apk_latest_version: str
    apk_min_version: str
    so_latest_version: str
    so_min_version: str
    store_enabled: bool
    has_apk: bool
    has_so: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated product list."""

    data: list[ProductResponse]
    total: int
    page: int
    page_size: int
