"""Reseller endpoints: dashboard, store, purchase, key-gen, ledger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.reseller import (
    AdminCreditRequest,
    GenerateKeyRequest,
    PurchaseRequest,
)
from app.routers.dependencies import get_current_admin, get_current_reseller
from app.services import license_service, reseller_service

router = APIRouter(prefix="/reseller", tags=["reseller"])


def _reseller_id(request: Request) -> str:
    """Extract reseller ID from the JWT claims (set by get_current_reseller)."""
    claims = request.state.user_claims if hasattr(request.state, "user_claims") else {}
    return claims.get("sub", "")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def reseller_dashboard(
    _reseller: dict = Depends(get_current_reseller),
):
    """Reseller dashboard: balance + stock summary."""
    return {"status": "ok", "message": "Reseller dashboard (Phase 8 will add full UI data)"}


@router.get("/balance")
async def reseller_balance(
    request: Request,
    _reseller: dict = Depends(get_current_reseller),
):
    """Get current reseller balance (demo — uses username from claims)."""
    return {"status": "ok"}


@router.get("/stock")
async def reseller_stock(
    request: Request,
    _reseller: dict = Depends(get_current_reseller),
):
    """Get reseller's stock inventory."""
    return {"status": "ok", "message": "Stock endpoints — provide reseller_id in production"}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@router.get("/store")
async def store_browse(
    page: int = 1,
    page_size: int = 20,
    _reseller: dict = Depends(get_current_reseller),
):
    """Browse available products in the reseller store."""
    # Reuse product store endpoint
    from app.services import product_service

    results, total = await product_service.list_products(
        page=page, page_size=page_size, store_only=True
    )
    return {
        "data": [product_service.product_to_response(r) for r in results],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/store/purchase")
async def store_purchase(
    request: PurchaseRequest,
    _reseller: dict = Depends(get_current_reseller),
):
    """Reseller purchases stock from the store."""
    reseller_id = _reseller.get("sub", "")
    if not reseller_id:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")

    try:
        result = await reseller_service.purchase_stock(reseller_id, request)
        return {"status": "purchased", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


@router.post("/generate-key")
async def reseller_generate_key(
    request: GenerateKeyRequest,
    _reseller: dict = Depends(get_current_reseller),
):
    """Reseller generates a license key from their stock."""
    reseller_id = _reseller.get("sub", "")
    if not reseller_id:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")

    try:
        license_doc = await reseller_service.generate_key_from_stock(
            reseller_id, request
        )
        return license_doc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# My keys
# ---------------------------------------------------------------------------


@router.get("/keys")
async def reseller_keys(
    page: int = 1,
    page_size: int = 20,
    _reseller: dict = Depends(get_current_reseller),
):
    """Reseller lists their own generated keys."""
    reseller_id = _reseller.get("sub", "")
    if not reseller_id:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")

    from app.models.license import LicenseListParams

    params = LicenseListParams(page=page, page_size=page_size)
    results, total = await license_service.list_licenses(params, reseller_id=reseller_id)
    return {"data": results, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


@router.get("/ledger")
async def reseller_ledger(
    page: int = 1,
    page_size: int = 50,
    _reseller: dict = Depends(get_current_reseller),
):
    """Reseller views their transaction ledger."""
    reseller_id = _reseller.get("sub", "")
    if not reseller_id:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")

    results, total = await reseller_service.get_ledger(
        reseller_id=reseller_id, page=page, page_size=page_size
    )
    return {"data": results, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Admin: credit reseller balance
# ---------------------------------------------------------------------------


@router.post("/admin/credit")
async def admin_credit_reseller(
    request: AdminCreditRequest,
    _admin: dict = Depends(get_current_admin),
):
    """Admin credits a reseller's balance."""
    try:
        result = await reseller_service.credit_balance(request)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
