"""License business logic: generation, validation, lifecycle."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.license import (
    LicenseCreateRequest,
    LicenseDocument,
    LicenseDuration,
    LicenseListParams,
    LicenseStatus,
    LicenseValidationRequest,
    LicenseValidationResponse,
    PauseReason,
)

# ---------------------------------------------------------------------------
# Duration → timedelta mapping
# ---------------------------------------------------------------------------

_DURATION_DELTA: dict[LicenseDuration, timedelta | None] = {
    LicenseDuration.TWO_HOURS: timedelta(hours=2),
    LicenseDuration.ONE_DAY: timedelta(days=1),
    LicenseDuration.THREE_DAYS: timedelta(days=3),
    LicenseDuration.ONE_WEEK: timedelta(weeks=1),
    LicenseDuration.ONE_MONTH: timedelta(days=30),
    LicenseDuration.TWO_MONTHS: timedelta(days=60),
    LicenseDuration.SIX_MONTHS: timedelta(days=180),
    LicenseDuration.ONE_YEAR: timedelta(days=365),
    LicenseDuration.LIFETIME: None,
}


def _collection() -> AsyncIOMotorCollection:
    return get_database()["licenses"]


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def _generate_license_key() -> str:
    """Generate a cryptographically strong license key (xya- prefix + 32 hex chars)."""
    return f"xya-{secrets.token_hex(16)}"


def _compute_expiry(duration: LicenseDuration, from_dt: datetime | None = None) -> datetime | None:
    delta = _DURATION_DELTA.get(duration)
    if delta is None:
        return None  # lifetime
    return (from_dt or datetime.now(tz=timezone.utc)) + delta


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def create_license(
    request: LicenseCreateRequest,
    created_by: str = "admin",
) -> dict[str, Any]:
    """Generate a new license key and insert it into MongoDB (status=pending)."""
    key = _generate_license_key()
    now = datetime.now(tz=timezone.utc)

    doc = LicenseDocument(
        product_id=request.product_id,
        license_key=key,
        customer=request.customer,
        hwid=None,
        issue_date=now,
        expiry_date=_compute_expiry(request.duration, now),
        status=LicenseStatus.PENDING,
        duration=request.duration,
        features=request.features,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )

    result = await _collection().insert_one(doc.model_dump())
    doc_dict = doc.model_dump()
    doc_dict["_id"] = str(result.inserted_id)
    return doc_dict


async def validate_license(request: LicenseValidationRequest) -> LicenseValidationResponse:
    """Validate / activate a license key from a client request.

    Handles HWID binding on first activation, status checks, and expiry.
    """
    coll = _collection()
    doc = await coll.find_one({"license_key": request.license_key})

    # 1. Key existence
    if doc is None:
        return LicenseValidationResponse(valid=False, reason="invalid_key")

    license_obj = LicenseDocument(**doc)

    # 2. Product match
    if license_obj.product_id != request.product_id:
        return LicenseValidationResponse(valid=False, reason="invalid_product")

    # 3. Status checks (must be active, or pending → bind)
    if license_obj.status == LicenseStatus.PENDING:
        return LicenseValidationResponse(
            valid=False, status=license_obj.status, reason="pending"
        )
    if license_obj.status == LicenseStatus.WATERMARK_FAILED:
        return LicenseValidationResponse(
            valid=False, status=license_obj.status, reason="watermark_failed"
        )
    if license_obj.status == LicenseStatus.REVOKED:
        return LicenseValidationResponse(valid=False, status=license_obj.status, reason="revoked")
    if license_obj.status == LicenseStatus.EXPIRED:
        return LicenseValidationResponse(
            valid=False, status=license_obj.status, reason="expired"
        )
    if license_obj.status == LicenseStatus.PAUSED:
        return LicenseValidationResponse(valid=False, status=license_obj.status, reason="paused")

    # 4. HWID check / bind
    if license_obj.hwid is None:
        # First activation — bind HWID
        await coll.update_one(
            {"license_key": request.license_key},
            {"$set": {"hwid": request.hwid, "updated_at": datetime.now(tz=timezone.utc)}},
        )
    elif license_obj.hwid != request.hwid:
        return LicenseValidationResponse(valid=False, reason="hwid_mismatch")

    # 5. Expiry check
    if license_obj.expiry_date is not None and license_obj.expiry_date < datetime.now(tz=timezone.utc):
        # Transition to expired
        await coll.update_one(
            {"license_key": request.license_key},
            {"$set": {"status": LicenseStatus.EXPIRED, "updated_at": datetime.now(tz=timezone.utc)}},
        )
        return LicenseValidationResponse(
            valid=False, status=LicenseStatus.EXPIRED, reason="expired"
        )

    return LicenseValidationResponse(
        valid=True,
        status=license_obj.status,
        features=license_obj.features,
        expiry_date=license_obj.expiry_date,
    )


async def get_license_by_key(license_key: str) -> dict[str, Any] | None:
    """Fetch a single license record by key."""
    doc = await _collection().find_one({"license_key": license_key})
    if doc is not None:
        doc["_id"] = str(doc["_id"])
    return doc


async def list_licenses(
    params: LicenseListParams,
    reseller_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """List licenses with optional filters and pagination."""
    coll = _collection()

    query: dict[str, Any] = {}
    if params.status is not None:
        query["status"] = params.status
    if params.product_id is not None:
        query["product_id"] = params.product_id
    if params.flagged_for_review is not None:
        query["flagged_for_review"] = params.flagged_for_review
    if reseller_id is not None:
        query["created_by"] = reseller_id

    total = await coll.count_documents(query)
    skip = (params.page - 1) * params.page_size
    cursor = coll.find(query).sort("created_at", -1).skip(skip).limit(params.page_size)

    results: list[dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)

    return results, total


async def transition_license_status(
    license_key: str,
    new_status: LicenseStatus,
    pause_reason: PauseReason | None = None,
    flagged_for_review: bool | None = None,
) -> bool:
    """Update a license's status. Optional: set pause_reason, flag for review."""
    set_fields: dict[str, Any] = {
        "status": new_status,
        "updated_at": datetime.now(tz=timezone.utc),
    }
    if pause_reason is not None:
        set_fields["pause_reason"] = pause_reason
    if flagged_for_review is not None:
        set_fields["flagged_for_review"] = flagged_for_review

    result = await _collection().update_one(
        {"license_key": license_key},
        {"$set": set_fields},
    )
    return result.modified_count > 0


async def resume_license(license_key: str) -> bool:
    """Resume a paused license (one-click resume, clears flags)."""
    result = await _collection().update_one(
        {"license_key": license_key, "status": LicenseStatus.PAUSED},
        {
            "$set": {
                "status": LicenseStatus.ACTIVE,
                "pause_reason": None,
                "flagged_for_review": False,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        },
    )
    return result.modified_count > 0


async def revoke_license(license_key: str) -> bool:
    """Revoke a license permanently."""
    return await transition_license_status(license_key, LicenseStatus.REVOKED)


async def pause_license(
    license_key: str,
    reason: PauseReason = PauseReason.ADMIN_MANUAL,
    flag_for_review: bool = False,
) -> bool:
    """Pause a license. Admin manual pause does not flag for review by default."""
    return await transition_license_status(
        license_key,
        LicenseStatus.PAUSED,
        pause_reason=reason,
        flagged_for_review=flag_for_review,
    )


async def activate_license(license_key: str) -> bool:
    """Transition a license from pending → active (called after watermarking succeeds)."""
    return await transition_license_status(license_key, LicenseStatus.ACTIVE)


async def mark_watermark_failed(license_key: str) -> bool:
    """Transition a license from pending → watermark_failed."""
    return await transition_license_status(license_key, LicenseStatus.WATERMARK_FAILED)


async def setup_license_indexes() -> None:
    """Create MongoDB indexes for the licenses collection."""
    coll = _collection()
    await coll.create_index("license_key", unique=True)
    await coll.create_index("product_id")
    await coll.create_index("status")
    await coll.create_index("created_by")
    await coll.create_index("flagged_for_review")
    await coll.create_index("hwid")
    await coll.create_index([("last_heartbeat_at", 1)])  # for heartbeat sweep queries
