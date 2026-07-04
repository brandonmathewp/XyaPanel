"""Reseller service: stock, balance, purchase, key-gen, ledger (SQLite)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_db
from app.models.license import LicenseCreateRequest, LicenseDuration
from app.models.reseller import (
    AdminCreditRequest, GenerateKeyRequest, LedgerType, PurchaseRequest,
)
from app.services.license_service import create_license

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------


async def get_reseller_balance(reseller_id: str) -> float:
    db = get_db()
    rows = await db.execute_fetchall("SELECT balance FROM resellers WHERE id = ?", (int(reseller_id),))
    if not rows:
        raise ValueError(f"Reseller {reseller_id} not found")
    return rows[0]["balance"]


async def get_reseller_by_username(username: str) -> dict | None:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM resellers WHERE username = ?", (username,))
    if not rows:
        return None
    d = dict(rows[0])
    d["_id"] = str(d["id"])
    return d


async def _write_ledger(reseller_id: str, ledger_type: LedgerType, amount: float,
                        resulting_balance: float, product_id: str | None = None,
                        duration: LicenseDuration | None = None,
                        external_ref: str | None = None, note: str | None = None) -> None:
    db = get_db()
    await db.execute(
        """INSERT INTO ledger (reseller_id, type, amount, resulting_balance,
           product_id, duration, external_ref, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (reseller_id, ledger_type.value, amount, resulting_balance,
         product_id, duration.value if duration else None, external_ref, note, _now()),
    )
    await db.commit()


async def get_ledger(reseller_id: str, page: int = 1, page_size: int = 50) -> tuple[list, int]:
    db = get_db()
    row = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM ledger WHERE reseller_id = ?", (reseller_id,))
    total = row[0]["cnt"]
    offset = (page - 1) * page_size
    rows = await db.execute_fetchall(
        "SELECT * FROM ledger WHERE reseller_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (reseller_id, page_size, offset),
    )
    return [dict(r) for r in rows], total


async def credit_balance(request: AdminCreditRequest) -> dict:
    db = get_db()
    reseller = await get_reseller_by_username(request.username)
    if reseller is None:
        raise ValueError(f"Reseller '{request.username}' not found")

    rid = reseller["_id"]
    await db.execute("UPDATE resellers SET balance = balance + ? WHERE id = ?", (request.amount, int(rid)))
    await db.commit()
    new_balance = await get_reseller_balance(rid)

    await _write_ledger(rid, LedgerType.CREDIT, request.amount, new_balance,
                        external_ref=request.external_ref,
                        note=request.note or f"Credit via {request.source}")
    return {"username": request.username, "amount": request.amount, "new_balance": new_balance}


# ---------------------------------------------------------------------------
# Purchase (saga)
# ---------------------------------------------------------------------------


async def purchase_stock(reseller_id: str, request: PurchaseRequest) -> dict:
    db = get_db()
    rows = await db.execute_fetchall("SELECT * FROM products WHERE product_id = ?", (request.product_id,))
    if not rows:
        raise ValueError(f"Product '{request.product_id}' not found")

    import json
    durations = json.loads(rows[0]["durations"]) if isinstance(rows[0]["durations"], str) else rows[0]["durations"]
    price_per_unit = None
    for d in durations:
        if d.get("duration") == request.duration.value:
            if not d.get("enabled", True):
                raise ValueError(f"Duration '{request.duration.value}' is disabled for {request.product_id}")
            price_per_unit = d.get("price", 0.0)
            break
    if price_per_unit is None:
        raise ValueError(f"Duration '{request.duration.value}' not available for {request.product_id}")

    total_cost = price_per_unit * request.quantity

    # Atomic debit
    cursor = await db.execute(
        "UPDATE resellers SET balance = balance - ? WHERE id = ? AND balance >= ?",
        (total_cost, int(reseller_id), total_cost),
    )
    if cursor.rowcount == 0:
        current = await get_reseller_balance(reseller_id)
        raise ValueError(f"Insufficient balance: need ${total_cost:.2f}, have ${current:.2f}")

    new_balance = await get_reseller_balance(reseller_id)
    now = _now()

    # Upsert stock
    try:
        await db.execute(
            """INSERT INTO reseller_stock (reseller_id, product_id, duration, quantity, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(reseller_id, product_id, duration)
               DO UPDATE SET quantity = quantity + ?, updated_at = ?""",
            (int(reseller_id), request.product_id, request.duration.value, request.quantity, now, now,
             request.quantity, now),
        )
        await db.commit()
    except Exception:
        # Compensate
        await db.execute("UPDATE resellers SET balance = balance + ? WHERE id = ?", (total_cost, int(reseller_id)))
        await db.commit()
        raise ValueError("Purchase failed: stock could not be credited. Balance refunded.")

    await _write_ledger(reseller_id, LedgerType.PURCHASE, -total_cost, new_balance,
                        product_id=request.product_id, duration=request.duration,
                        note=f"Purchased {request.quantity}x {request.duration.value}")

    return {"product_id": request.product_id, "duration": request.duration.value,
            "quantity": request.quantity, "total_cost": total_cost, "new_balance": new_balance}


# ---------------------------------------------------------------------------
# Generate key from stock (saga)
# ---------------------------------------------------------------------------


async def generate_key_from_stock(reseller_id: str, request: GenerateKeyRequest) -> dict:
    db = get_db()
    # Decrement stock
    cursor = await db.execute(
        "UPDATE reseller_stock SET quantity = quantity - 1, updated_at = ? WHERE reseller_id = ? AND product_id = ? AND duration = ? AND quantity >= 1",
        (_now(), int(reseller_id), request.product_id, request.duration.value),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"No stock available for {request.product_id} / {request.duration.value}")

    await db.commit()

    try:
        create_req = LicenseCreateRequest(
            product_id=request.product_id, customer=request.customer,
            duration=request.duration, features=request.features,
        )
        license_doc = await create_license(create_req, created_by=reseller_id)

        from app.tasks.watermark import watermark_license
        watermark_license.delay(license_key=license_doc["license_key"], product_id=request.product_id)

        await _write_ledger(reseller_id, LedgerType.KEY_GENERATION, 0.0,
                            await get_reseller_balance(reseller_id),
                            product_id=request.product_id, duration=request.duration,
                            external_ref=license_doc["license_key"],
                            note=f"Generated key {license_doc['license_key']}")
        return license_doc
    except Exception:
        await db.execute(
            "UPDATE reseller_stock SET quantity = quantity + 1 WHERE reseller_id = ? AND product_id = ? AND duration = ?",
            (int(reseller_id), request.product_id, request.duration.value),
        )
        await db.commit()
        raise ValueError("Key generation failed: stock has been returned.")


# ---------------------------------------------------------------------------


async def get_stock_inventory(reseller_id: str) -> list[dict]:
    db = get_db()
    rows = await db.execute_fetchall(
        """SELECT rs.*, p.name as product_name FROM reseller_stock rs
           LEFT JOIN products p ON rs.product_id = p.product_id
           WHERE rs.reseller_id = ? AND rs.quantity > 0""",
        (int(reseller_id),),
    )
    return [dict(r) for r in rows]


async def setup_reseller_indexes() -> None:
    pass
