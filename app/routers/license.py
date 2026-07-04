"""License endpoints: admin management + client validation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.license import (
    LicenseCreateRequest,
    LicenseListParams,
    LicenseValidationRequest,
    LicenseValidationResponse,
)
from app.routers.dependencies import get_current_admin
from app.services import license_service

router = APIRouter(prefix="/licenses", tags=["licenses"])


# ---------------------------------------------------------------------------
# Client-facing: license validation (no auth required, rate-limited)
# ---------------------------------------------------------------------------


@router.post("/validate", response_model=LicenseValidationResponse)
async def validate_license(request: LicenseValidationRequest):
    """Validate a license key and (on first use) bind it to a HWID.

    This is the endpoint client software hits on startup/periodically.
    No authentication required — the license key itself is the credential.
    """
    return await license_service.validate_license(request)


# ---------------------------------------------------------------------------
# Admin endpoints — protected by JWT auth
# ---------------------------------------------------------------------------


@router.post("/admin/generate")
async def admin_generate_license(
    request: LicenseCreateRequest,
    _admin: dict = Depends(get_current_admin),
):
    """Admin generates a new license key (status: pending, watermark queued)."""
    doc = await license_service.create_license(request, created_by="admin")
    # TODO Phase 1: enqueue watermarking task to Celery
    return doc


@router.get("/admin/list")
async def admin_list_licenses(
    status: str | None = None,
    product_id: str | None = None,
    flagged_for_review: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    _admin: dict = Depends(get_current_admin),
):
    """Admin lists licenses with optional filters."""
    params = LicenseListParams(
        status=status,
        product_id=product_id,
        flagged_for_review=flagged_for_review,
        page=page,
        page_size=page_size,
    )
    results, total = await license_service.list_licenses(params)
    return {"data": results, "total": total, "page": page, "page_size": page_size}


@router.get("/admin/{license_key}")
async def admin_get_license(
    license_key: str,
    _admin: dict = Depends(get_current_admin),
):
    """Admin fetches a single license by key."""
    doc = await license_service.get_license_by_key(license_key)
    if doc is None:
        raise HTTPException(status_code=404, detail="License not found")
    return doc


@router.post("/admin/{license_key}/revoke")
async def admin_revoke_license(
    license_key: str,
    _admin: dict = Depends(get_current_admin),
):
    """Admin revokes a license."""
    success = await license_service.revoke_license(license_key)
    if not success:
        raise HTTPException(status_code=404, detail="License not found")
    return {"status": "revoked", "license_key": license_key}


@router.post("/admin/{license_key}/pause")
async def admin_pause_license(
    license_key: str,
    _admin: dict = Depends(get_current_admin),
):
    """Admin pauses a license (manual)."""
    success = await license_service.pause_license(license_key)
    if not success:
        raise HTTPException(status_code=404, detail="License not found or cannot be paused")
    return {"status": "paused", "license_key": license_key}


@router.post("/admin/{license_key}/resume")
async def admin_resume_license(
    license_key: str,
    _admin: dict = Depends(get_current_admin),
):
    """Admin resumes a paused license (one-click, clears flags)."""
    success = await license_service.resume_license(license_key)
    if not success:
        raise HTTPException(status_code=404, detail="License not found or not paused")
    return {"status": "active", "license_key": license_key}
