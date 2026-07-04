"""Product business logic: CRUD, artifact management (SQLite)."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any

from fastapi import UploadFile

from app.core.database import get_db
from app.models.product import ProductCreateRequest, ProductUpdateRequest


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_ARTIFACTS_DIR = "artifacts"


async def create_product(request: ProductCreateRequest) -> dict:
    db = get_db()
    rows = await db.execute_fetchall("SELECT id FROM products WHERE product_id = ?", (request.product_id,))
    if rows:
        raise ValueError(f"Product '{request.product_id}' already exists")

    now = _now()
    durations_json = json.dumps([d.model_dump() for d in request.durations])
    features_json = json.dumps(request.features)

    cursor = await db.execute(
        """INSERT INTO products (product_id, name, description, durations, features,
           created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (request.product_id, request.name, request.description, durations_json, features_json, now, now),
    )
    await db.commit()
    return {"_id": str(cursor.lastrowid), "product_id": request.product_id, "name": request.name}


async def get_product(product_id: str) -> dict | None:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM products WHERE product_id = ?", (product_id,))
    if not rows:
        return None
    d = dict(rows[0])
    d["_id"] = str(d["id"])
    for col in ("durations", "features"):
        if col in d and isinstance(d[col], str):
            d[col] = json.loads(d[col])
    d["store_enabled"] = bool(d["store_enabled"])
    return d


async def list_products(page: int = 1, page_size: int = 20, store_only: bool = False) -> tuple[list, int]:
    db = get_db()
    where = "WHERE store_enabled = 1" if store_only else ""
    row = await db.execute_fetchall(f"SELECT COUNT(*) as cnt FROM products {where}")
    total = row[0]["cnt"]

    offset = (page - 1) * page_size
    rows = await db.execute_fetchall(
        f"SELECT * FROM products {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    results = []
    for r in rows:
        d = dict(r)
        d["_id"] = str(d["id"])
        for col in ("durations", "features"):
            if col in d and isinstance(d[col], str):
                d[col] = json.loads(d[col])
        d["store_enabled"] = bool(d["store_enabled"])
        results.append(d)
    return results, total


async def update_product(product_id: str, request: ProductUpdateRequest) -> bool:
    db = get_db()
    sets = ["updated_at = ?"]
    vals: list = [_now()]

    for field, attr in [("name", request.name), ("description", request.description),
                         ("apk_latest_version", request.apk_latest_version),
                         ("apk_min_version", request.apk_min_version),
                         ("so_latest_version", request.so_latest_version),
                         ("so_min_version", request.so_min_version)]:
        if attr is not None:
            sets.append(f"{field} = ?")
            vals.append(attr)
    if request.features is not None:
        sets.append("features = ?")
        vals.append(json.dumps(request.features))
    if request.durations is not None:
        sets.append("durations = ?")
        vals.append(json.dumps([d.model_dump() for d in request.durations]))
    if request.store_enabled is not None:
        sets.append("store_enabled = ?")
        vals.append(1 if request.store_enabled else 0)

    vals.append(product_id)
    cursor = await db.execute(
        f"UPDATE products SET {', '.join(sets)} WHERE product_id = ?", vals
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_product(product_id: str) -> tuple[bool, str]:
    db = get_db()
    row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM licenses WHERE product_id = ?", (product_id,))
    count = row[0]["cnt"]
    if count > 0:
        return False, f"Cannot delete product '{product_id}' — {count} license key(s) still exist."
    cursor = await db.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
    await db.commit()
    if cursor.rowcount == 0:
        return False, f"Product '{product_id}' not found."
    return True, f"Product '{product_id}' deleted."


async def upload_artifact(product_id: str, artifact_type: str, file: UploadFile) -> bool:
    if artifact_type not in ("apk", "so"):
        raise ValueError("artifact_type must be 'apk' or 'so'")

    product = await get_product(product_id)
    if product is None:
        raise ValueError(f"Product '{product_id}' not found")

    os.makedirs(_ARTIFACTS_DIR, exist_ok=True)
    ext = ".apk" if artifact_type == "apk" else ".so"
    filepath = os.path.join(_ARTIFACTS_DIR, f"{product_id}{ext}")
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    db = get_db()
    field = f"{artifact_type}_artifact_path"
    await db.execute(
        f"UPDATE products SET {field} = ?, updated_at = ? WHERE product_id = ?",
        (filepath, _now(), product_id),
    )
    await db.commit()
    return True


def product_to_response(doc: dict) -> dict:
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


async def setup_product_indexes() -> None:
    pass
