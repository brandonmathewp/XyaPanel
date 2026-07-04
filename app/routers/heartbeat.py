"""Heartbeat endpoints — client-side keepalive with piggybacked features."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.license import (
    LicenseStatus,
    LicenseValidationRequest,
    LicenseValidationResponse,
)
from app.routers.dependencies import get_current_client
from app.services import heartbeat_service

router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])


class HeartbeatRequest(LicenseValidationRequest):
    """Heartbeat request — same shape as validation but a different endpoint."""

    pass


class HeartbeatResponse(LicenseValidationResponse):
    """Heartbeat response — returns current status and piggybacked features."""

    last_heartbeat_at: str | None = None


@router.post("", response_model=HeartbeatResponse)
async def heartbeat(
    request: HeartbeatRequest,
    _session: dict = Depends(get_current_client),
):
    """Client sends a heartbeat every 10 minutes.

    Verifies license key + HWID, updates last_heartbeat_at,
    and piggybacks the current feature list in the response.
    """
    result = await heartbeat_service.process_heartbeat(
        license_key=request.license_key,
        hwid=request.hwid,
    )

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Heartbeat rejected: invalid license, HWID mismatch, or bad status",
        )

    is_valid = result["status"] in (LicenseStatus.ACTIVE, LicenseStatus.PAUSED)

    return HeartbeatResponse(
        valid=is_valid,
        status=LicenseStatus(result["status"]) if result["status"] else None,
        features=result.get("features", []),
        last_heartbeat_at=result.get("last_heartbeat_at"),
    )
