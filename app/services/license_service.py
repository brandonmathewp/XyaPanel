"""License business logic: generation, validation, lifecycle (SQLite)."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import get_db
from app.models.license import (
    LicenseCreateRequest,
    LicenseDuration,
    LicenseListParams,
    LicenseStatus,
    LicenseValidationRequest,
    LicenseValidationResponse,
    PauseReason,
)

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


def _generate_license_key() -> str:
    return f"xya-{secrets.token_hex(16)}"


def _compute_expiry(duration: LicenseDuration, from_dt: datetime | None = None) -> datetime | None:
    delta = _DURATION_DELTA.get(duration)
    if delta is None:
        return None
    return (from_dt or datetime.now(tz=timezone.utc)) + delta


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _dt_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _row_to_dict(row: Any, table_id: str = "id") -> dict:
    """Convert aiosqlite Row to a plain dict with id as string."""
    if row is None:
        return None
    d = dict(row)
    d["_id"] = str(d[table_id])
    # Parse JSON columns
    for col in ("features", "durations"):
        if col in d and isinstance(d[col], str):
            try:
                d[col] = json.loads(d[col])
            except (json.JSONDecodeError, TypeError):
                pass
    # Convert int bools
    if "flagged_for_review" in d:
        d["flagged_for_review"] = bool(d["flagged_for_review"])
    if "store_enabled" in d:
        d["store_enabled"] = bool(d["store_enabled"])
    return d


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def create_license(request: LicenseCreateRequest, created_by: str = "admin") -> dict:
    key = _generate_license_key()
    now = _now()
    expiry = _compute_expiry(request.duration)
    features_json = json.dumps(request.features)

    db = get_db()
    await db.execute(
        """INSERT INTO licenses (license_key, product_id, customer, issue_date, expiry_date,
           status, duration, features, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
        (key, request.product_id, request.customer, now, _dt_iso(expiry),
         request.duration.value, features_json, created_by, now, now),
    )
    await db.commit()

    return {
        "_id": str(db.total_changes),  # approximate — ok for response
        "license_key": key,
        "product_id": request.product_id,
        "customer": request.customer,
        "hwid": None,
        "issue_date": now,
        "expiry_date": _dt_iso(expiry),
        "status": "pending",
        "duration": request.duration.value,
        "features": request.features,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }


async def validate_license(request: LicenseValidationRequest) -> LicenseValidationResponse:
    db = get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM licenses WHERE license_key = ?", (request.license_key,)
    )
    if not row:
        return LicenseValidationResponse(valid=False, reason="invalid_key")

    doc = _row_to_dict(row[0])

    if doc["product_id"] != request.product_id:
        return LicenseValidationResponse(valid=False, reason="invalid_product")

    status = doc["status"]

    if status == "pending":
        return LicenseValidationResponse(valid=False, status=status, reason="pending")
    if status == "watermark_failed":
        return LicenseValidationResponse(valid=False, status=status, reason="watermark_failed")
    if status == "revoked":
        return LicenseValidationResponse(valid=False, status=status, reason="revoked")
    if status == "expired":
        return LicenseValidationResponse(valid=False, status=status, reason="expired")
    if status == "paused":
        return LicenseValidationResponse(valid=False, status=status, reason="paused")

    # HWID check / bind
    if doc["hwid"] is None:
        await db.execute(
            "UPDATE licenses SET hwid = ?, updated_at = ? WHERE license_key = ?",
            (request.hwid, _now(), request.license_key),
        )
        await db.commit()
    elif doc["hwid"] != request.hwid:
        return LicenseValidationResponse(valid=False, reason="hwid_mismatch")

    # Expiry check
    expiry = doc.get("expiry_date")
    if expiry and datetime.fromisoformat(expiry) < datetime.now(tz=timezone.utc):
        await db.execute(
            "UPDATE licenses SET status = 'expired', updated_at = ? WHERE license_key = ?",
            (_now(), request.license_key),
        )
        await db.commit()
        return LicenseValidationResponse(valid=False, status="expired", reason="expired")

    features = doc.get("features", [])
    if isinstance(features, str):
        features = json.loads(features)

    return LicenseValidationResponse(
        valid=True,
        status=status,
        features=features,
        expiry_date=expiry,
    )


async def get_license_by_key(license_key: str) -> dict | None:
    db = get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM licenses WHERE license_key = ?", (license_key,)
    )
    return _row_to_dict(rows[0]) if rows else None


async def list_licenses(params: LicenseListParams, reseller_id: str | None = None) -> tuple[list, int]:
    db = get_db()
    clauses = []
    values: list = []

    if params.status:
        clauses.append("status = ?")
        values.append(params.status.value if hasattr(params.status, 'value') else params.status)
    if params.product_id:
        clauses.append("product_id = ?")
        values.append(params.product_id)
    if params.flagged_for_review is not None:
        clauses.append("flagged_for_review = ?")
        values.append(1 if params.flagged_for_review else 0)
    if reseller_id:
        clauses.append("created_by = ?")
        values.append(reseller_id)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    # Count
    row = await db.execute_fetchall(f"SELECT COUNT(*) as cnt FROM licenses{where}", values)
    total = row[0]["cnt"] if row else 0

    # Fetch
    offset = (params.page - 1) * params.page_size
    rows = await db.execute_fetchall(
        f"SELECT * FROM licenses{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        values + [params.page_size, offset],
    )

    return [_row_to_dict(r) for r in rows], total


async def _update_status(license_key: str, **fields) -> bool:
    db = get_db()
    sets = ["updated_at = ?"]
    vals: list = [_now()]
    for k, v in fields.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(license_key)
    cursor = await db.execute(
        f"UPDATE licenses SET {', '.join(sets)} WHERE license_key = ?", vals
    )
    await db.commit()
    return cursor.rowcount > 0


async def transition_license_status(license_key: str, new_status: LicenseStatus,
                                     pause_reason: PauseReason | None = None,
                                     flagged_for_review: bool | None = None) -> bool:
    fields = {"status": new_status.value}
    if pause_reason:
        fields["pause_reason"] = pause_reason.value
    if flagged_for_review is not None:
        fields["flagged_for_review"] = 1 if flagged_for_review else 0
    return await _update_status(license_key, **fields)


async def resume_license(license_key: str) -> bool:
    return await _update_status(
        license_key,
        status="active",
        pause_reason=None,
        flagged_for_review=0,
    )


async def revoke_license(license_key: str) -> bool:
    return await transition_license_status(license_key, LicenseStatus.REVOKED)


async def pause_license(license_key: str, reason: PauseReason = PauseReason.ADMIN_MANUAL,
                        flag_for_review: bool = False) -> bool:
    return await transition_license_status(license_key, LicenseStatus.PAUSED, reason, flag_for_review)


async def activate_license(license_key: str) -> bool:
    return await transition_license_status(license_key, LicenseStatus.ACTIVE)


async def mark_watermark_failed(license_key: str) -> bool:
    return await transition_license_status(license_key, LicenseStatus.WATERMARK_FAILED)


async def setup_license_indexes() -> None:
    pass  # Indexes created in schema.py
