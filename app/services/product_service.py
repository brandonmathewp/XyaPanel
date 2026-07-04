"""Product business logic: CRUD, artifact management, version tracking."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Any

from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.config import settings
from app.core.database import get_database
from app.models.product import (
    ProductCreateRequest,
    ProductDocument,
    ProductDurationPricing,
    ProductResponse,
    ProductUpdateRequest,
)


def _collection() -> AsyncIOMotorCollection:
    return get_database()["products"]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_product(request: ProductCreateRequest) -> ProductDocument:
    """Create a new product. Rejects if product_id already exists."""
    coll = _collection()

    existing = await coll.find_one({"product_id": request.product_id})
    if existing is not None:
        raise ValueError(f"Product '{request.product_id}' already exists")

    doc = ProductDocument(
        product_id=request.product_id,
        name=request.name,
        description=request.description,
        features=request.features,
        durations=[d.model_dump() for d in request.durations],  # type: ignore[arg-type]
    )
    await coll.insert_one(doc.model_dump())
    return doc


async def get_product(product_id: str) -> dict[str, Any] | None:
    """Fetch a single product by product_id."""
    coll = _collection()
    doc = await coll.find_one({"product_id": product_id})
    if doc is not None:
        doc["_id"] = str(doc["_id"])
    return doc


async def list_products(
    page: int = 1,
    page_size: int = 20,
    store_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """List products with pagination. Optional: only store-enabled products."""
    coll = _collection()
    query: dict[str, Any] = {}
    if store_only:
        query["store_enabled"] = True

    total = await coll.count_documents(query)
    skip = (page - 1) * page_size
    cursor = coll.find(query).sort("created_at", -1).skip(skip).limit(page_size)

    results: list[dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)

    return results, total


async def update_product(
    product_id: str,
    request: ProductUpdateRequest,
) -> bool:
    """Update an existing product. Returns True if product existed and was updated."""
    coll = _collection()

    update_fields: dict[str, Any] = {"updated_at": datetime.now(tz=timezone.utc)}
    if request.name is not None:
        update_fields["name"] = request.name
    if request.description is not None:
        update_fields["description"] = request.description
    if request.features is not None:
        update_fields["features"] = request.features
    if request.durations is not None:
        update_fields["durations"] = [d.model_dump() for d in request.durations]
    if request.apk_latest_version is not None:
        update_fields["apk_latest_version"] = request.apk_latest_version
    if request.apk_min_version is not None:
        update_fields["apk_min_version"] = request.apk_min_version
    if request.so_latest_version is not None:
        update_fields["so_latest_version"] = request.so_latest_version
    if request.so_min_version is not None:
        update_fields["so_min_version"] = request.so_min_version
    if request.store_enabled is not None:
        update_fields["store_enabled"] = request.store_enabled

    result = await coll.update_one(
        {"product_id": product_id},
        {"$set": update_fields},
    )
    return result.modified_count > 0


async def delete_product(product_id: str) -> tuple[bool, str]:
    """Delete a product. Blocked if any licenses still reference it.

    Returns (success, message).
    """
    coll = _collection()
    licenses_coll = get_database()["licenses"]

    # Check for existing licenses
    license_count = await licenses_coll.count_documents({"product_id": product_id})
    if license_count > 0:
        return False, (
            f"Cannot delete product '{product_id}' — "
            f"{license_count} license key(s) still exist for this product. "
            f"Delete all associated licenses first."
        )

    result = await coll.delete_one({"product_id": product_id})
    if result.deleted_count == 0:
        return False, f"Product '{product_id}' not found."

    return True, f"Product '{product_id}' deleted."


# ---------------------------------------------------------------------------
# Artifact management
# ---------------------------------------------------------------------------


_ARTIFACTS_DIR = "artifacts"


def _ensure_artifacts_dir():
    os.makedirs(_ARTIFACTS_DIR, exist_ok=True)


async def upload_artifact(
    product_id: str,
    artifact_type: str,  # "apk" or "so"
    file: UploadFile,
) -> bool:
    """Upload an APK or .so file for a product. Overwrites existing.

    The file is stored on disk (not in MongoDB) to stay under the 512MB Free Tier cap.
    Only the file path is stored in the product document.
    """
    if artifact_type not in ("apk", "so"):
        raise ValueError("artifact_type must be 'apk' or 'so'")

    # Verify product exists
    product = await get_product(product_id)
    if product is None:
        raise ValueError(f"Product '{product_id}' not found")

    # Determine file extension
    ext = ".apk" if artifact_type == "apk" else ".so"
    filename = f"{product_id}{ext}"
    filepath = os.path.join(_ARTIFACTS_DIR, filename)

    _ensure_artifacts_dir()

    # Save file to disk
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Update product document with the artifact path
    field = f"{artifact_type}_artifact_path"
    await _collection().update_one(
        {"product_id": product_id},
        {"$set": {field: filepath, "updated_at": datetime.now(tz=timezone.utc)}},
    )

    return True


# ---------------------------------------------------------------------------
# Product response formatting
# ---------------------------------------------------------------------------


def product_to_response(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw MongoDB product doc to a ProductResponse-compatible dict."""
    return {
        "product_id": doc["product_id"],
        "name": doc["name"],
        "description": doc.get("description"),
        "durations": doc.get("durations", []),
        "features": doc.get("features", []),
        "apk_latest_version": doc.get("apk_latest_version", "1.0.0"),
        "apk_min_version": doc.get("apk_min_version", "1.0.0"),
        "so_latest_version": doc.get("so_latest_version", "1.0.0"),
        "so_min_version": doc.get("so_min_version", "1.0.0"),
        "store_enabled": doc.get("store_enabled", True),
        "has_apk": bool(doc.get("apk_artifact_path")),
        "has_so": bool(doc.get("so_artifact_path")),
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------


async def setup_product_indexes() -> None:
    """Create MongoDB indexes for the products collection."""
    coll = _collection()
    await coll.create_index("product_id", unique=True)
