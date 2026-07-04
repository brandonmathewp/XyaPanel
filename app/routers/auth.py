"""Authentication endpoints: login, invite codes, reseller registration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.auth import (
    AdminLoginRequest,
    ClientLoginRequest,
    ClientLoginResponse,
    ClientVersionCheckRequest,
    ClientVersionCheckResponse,
    InviteCodeCreateRequest,
    InviteCodeResponse,
    ResellerLoginRequest,
    ResellerRegisterRequest,
    TokenResponse,
)
from app.models.license import LicenseValidationRequest, LicenseValidationResponse
from app.services import auth_service, license_service, product_service

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Health check — no auth needed
# ---------------------------------------------------------------------------


@router.get("/health")
async def auth_health():
    return {"status": "auth_ok"}


# ---------------------------------------------------------------------------
# Admin login
# ---------------------------------------------------------------------------


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(request: AdminLoginRequest):
    token = await auth_service.authenticate_admin(request.email, request.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=token, role="admin")


# ---------------------------------------------------------------------------
# Reseller login
# ---------------------------------------------------------------------------


@router.post("/reseller/login", response_model=TokenResponse)
async def reseller_login(request: ResellerLoginRequest):
    token = await auth_service.authenticate_reseller(request.username, request.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=token, role="reseller")


# ---------------------------------------------------------------------------
# Reseller registration (invite code redemption)
# ---------------------------------------------------------------------------


@router.post("/reseller/register", response_model=TokenResponse)
async def reseller_register(request: ResellerRegisterRequest):
    reseller = await auth_service.register_reseller(
        username=request.username,
        email=request.email,
        password=request.password,
        invite_code=request.invite_code,
    )
    if reseller is None:
        raise HTTPException(
            status_code=400,
            detail="Registration failed: invalid, expired, or already used invite code, "
            "or username/email already taken.",
        )
    # Auto-login after registration
    token = await auth_service.authenticate_reseller(request.username, request.password)
    return TokenResponse(access_token=token or "", role="reseller")


# ---------------------------------------------------------------------------
# Invite codes (admin only — auth enforced via dependency in router registration)
# ---------------------------------------------------------------------------

# These endpoints are registered under /admin prefix and protected by admin auth dependency.
# They are defined here but wired into main.py with the admin dependency.

from .dependencies import get_current_admin  # noqa: E402 — forward ref, resolved at startup


@router.post("/admin/invite-codes/generate")
async def admin_generate_invite_codes(
    request: InviteCodeCreateRequest = Depends(),
    _admin: None = Depends(get_current_admin),
):
    """Admin generates reseller invite codes."""
    codes = await auth_service.generate_invite_codes(
        count=request.count,
        expires_in_hours=request.expires_in_hours,
    )
    return {"codes": codes, "count": len(codes)}


@router.get("/admin/invite-codes")
async def admin_list_invite_codes(
    _admin: None = Depends(get_current_admin),
):
    """Admin lists all invite codes."""
    codes = await auth_service.list_invite_codes()
    return {"data": codes, "total": len(codes)}


# ---------------------------------------------------------------------------
# Client two-stage login
# ---------------------------------------------------------------------------


@router.post("/client/version-check", response_model=ClientVersionCheckResponse)
async def client_version_check(request: ClientVersionCheckRequest):
    """Stage 1: APK version check (pre-login, unencrypted per spec).

    This endpoint verifies the APK version against the configured min/latest
    versions for the given product. This runs before any session is established.
    """
    product = await product_service.get_product(request.product_id)
    if product is None:
        return ClientVersionCheckResponse(
            version_valid=False,
            latest_version="unknown",
            min_version="unknown",
            update_required=False,
            reason="unknown_product",
        )

    latest = product.get("apk_latest_version", "1.0.0")
    min_ver = product.get("apk_min_version", "1.0.0")
    update_required = request.apk_version < min_ver

    return ClientVersionCheckResponse(
        version_valid=request.apk_version >= min_ver,
        latest_version=latest,
        min_version=min_ver,
        update_required=update_required,
        reason="version_too_old" if update_required else None,
    )


@router.post("/client/login", response_model=ClientLoginResponse)
async def client_login(request: ClientLoginRequest):
    """Stage 2: Full client login — validates license, binds HWID, establishes session.

    This is effectively the same as license validation but also creates a client
    session record for future heartbeat/auth verification.
    """
    # First validate the license (same flow as /licenses/validate)
    validation_request = LicenseValidationRequest(
        license_key=request.license_key,
        hwid=request.hwid,
        product_id=request.product_id,
        app_version=request.so_version,
    )
    validation = await license_service.validate_license(validation_request)

    if not validation.valid:
        raise HTTPException(
            status_code=401,
            detail=f"Login rejected: {validation.reason}",
        )

    # Create a client session (session key placeholder — full HKDF in Phase 7)
    import secrets

    temp_session_key = secrets.token_hex(32)
    session_id = await auth_service.create_client_session(
        license_key=request.license_key,
        hwid=request.hwid,
        product_id=request.product_id,
        session_key=temp_session_key,
    )

    return ClientLoginResponse(
        session_id=session_id,
        features=validation.features or [],
        expiry_date=validation.expiry_date,
    )
