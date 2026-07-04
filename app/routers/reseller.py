"""Reseller endpoints: dashboard, store, purchase, key-gen, ledger."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.reseller import (
    AdminCreditRequest,
    GenerateKeyRequest,
    PurchaseRequest,
)
from app.routers.dependencies import get_current_admin, get_current_reseller
from app.services import license_service, reseller_service

router = APIRouter(prefix="/reseller", tags=["reseller"])


def _rid(claims: dict) -> str:
    """Extract reseller MongoDB _id from JWT claims."""
    return claims.get("sub", "")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def reseller_dashboard(reseller: dict = Depends(get_current_reseller)):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")
    try:
        balance = await reseller_service.get_reseller_balance(rid)
        stock = await reseller_service.get_stock_inventory(rid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"balance": balance, "stock": stock}


@router.get("/balance")
async def reseller_balance(reseller: dict = Depends(get_current_reseller)):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")
    try:
        balance = await reseller_service.get_reseller_balance(rid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"balance": balance}


@router.get("/stock")
async def reseller_stock(reseller: dict = Depends(get_current_reseller)):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")
    stock = await reseller_service.get_stock_inventory(rid)
    return {"data": stock, "total": len(stock)}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@router.get("/store")
async def store_browse(
    page: int = 1,
    page_size: int = 20,
    _reseller: dict = Depends(get_current_reseller),
):
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
    reseller: dict = Depends(get_current_reseller),
):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")
    try:
        result = await reseller_service.purchase_stock(rid, request)
        return {"status": "purchased", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


@router.post("/generate-key")
async def reseller_generate_key(
    request: GenerateKeyRequest,
    reseller: dict = Depends(get_current_reseller),
):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")
    try:
        license_doc = await reseller_service.generate_key_from_stock(rid, request)
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
    reseller: dict = Depends(get_current_reseller),
):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")

    from app.models.license import LicenseListParams

    params = LicenseListParams(page=page, page_size=page_size)
    results, total = await license_service.list_licenses(params, reseller_id=rid)
    return {"data": results, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


@router.get("/ledger")
async def reseller_ledger(
    page: int = 1,
    page_size: int = 50,
    reseller: dict = Depends(get_current_reseller),
):
    rid = _rid(reseller)
    if not rid:
        raise HTTPException(status_code=401, detail="Invalid reseller identity")

    results, total = await reseller_service.get_ledger(
        reseller_id=rid, page=page, page_size=page_size
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
    try:
        result = await reseller_service.credit_balance(request)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
