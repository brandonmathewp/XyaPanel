"""Product management endpoints (admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.models.product import ProductCreateRequest, ProductUpdateRequest
from app.routers.dependencies import get_current_admin
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Admin: Create product
# ---------------------------------------------------------------------------


@router.post("/admin")
async def admin_create_product(
    request: ProductCreateRequest,
    _admin: dict = Depends(get_current_admin),
):
    """Admin creates a new product."""
    try:
        doc = await product_service.create_product(request)
        return product_service.product_to_response(doc.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ---------------------------------------------------------------------------
# Admin: List all products
# ---------------------------------------------------------------------------


@router.get("/admin")
async def admin_list_products(
    page: int = 1,
    page_size: int = 20,
    _admin: dict = Depends(get_current_admin),
):
    """Admin lists all products (including store-disabled)."""
    results, total = await product_service.list_products(
        page=page,
        page_size=page_size,
        store_only=False,
    )
    return {
        "data": [product_service.product_to_response(r) for r in results],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Admin: Get single product
# ---------------------------------------------------------------------------


@router.get("/admin/{product_id}")
async def admin_get_product(
    product_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Admin fetches a single product."""
    doc = await product_service.get_product(product_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_service.product_to_response(doc)


# ---------------------------------------------------------------------------
# Admin: Update product
# ---------------------------------------------------------------------------


@router.put("/admin/{product_id}")
async def admin_update_product(
    product_id: str,
    request: ProductUpdateRequest,
    _admin: dict = Depends(get_current_admin),
):
    """Admin updates an existing product. product_id cannot be changed."""
    success = await product_service.update_product(product_id, request)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    doc = await product_service.get_product(product_id)
    return product_service.product_to_response(doc)


# ---------------------------------------------------------------------------
# Admin: Delete product (blocked if licenses exist)
# ---------------------------------------------------------------------------


@router.delete("/admin/{product_id}")
async def admin_delete_product(
    product_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Admin deletes a product. Blocked if any licenses still reference it."""
    success, message = await product_service.delete_product(product_id)
    if not success:
        raise HTTPException(status_code=409, detail=message)
    return {"status": "deleted", "product_id": product_id, "message": message}


# ---------------------------------------------------------------------------
# Admin: Upload artifact (APK / .so)
# ---------------------------------------------------------------------------


@router.post("/admin/{product_id}/upload-apk")
async def admin_upload_apk(
    product_id: str,
    file: UploadFile = File(...),
    _admin: dict = Depends(get_current_admin),
):
    """Admin uploads an APK file for a product."""
    try:
        await product_service.upload_artifact(product_id, "apk", file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "uploaded", "product_id": product_id, "type": "apk"}


@router.post("/admin/{product_id}/upload-so")
async def admin_upload_so(
    product_id: str,
    file: UploadFile = File(...),
    _admin: dict = Depends(get_current_admin),
):
    """Admin uploads a .so file for a product."""
    try:
        await product_service.upload_artifact(product_id, "so", file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "uploaded", "product_id": product_id, "type": "so"}


# ---------------------------------------------------------------------------
# Public: List store products (for reseller store — no auth needed to browse)
# ---------------------------------------------------------------------------

# These endpoints are intentionally separate from admin endpoints.
# The reseller store will use these in Phase 6/8.


@router.get("/store")
async def store_list_products(
    page: int = 1,
    page_size: int = 20,
):
    """List products available in the reseller store."""
    results, total = await product_service.list_products(
        page=page,
        page_size=page_size,
        store_only=True,
    )
    return {
        "data": [product_service.product_to_response(r) for r in results],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
