"""Reseller service: stock, balance, purchase flow, key-gen, ledger."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.database import get_database
from app.models.license import (
    LicenseCreateRequest,
    LicenseDocument,
    LicenseDuration,
    LicenseStatus,
)
from app.models.reseller import (
    AdminCreditRequest,
    GenerateKeyRequest,
    LedgerEntryDocument,
    LedgerType,
    PurchaseRequest,
    ResellerStockDocument,
)
from app.services.license_service import create_license

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------


def _resellers() -> AsyncIOMotorCollection:
    return get_database()["resellers"]


def _stock() -> AsyncIOMotorCollection:
    return get_database()["reseller_stock"]


def _ledger() -> AsyncIOMotorCollection:
    return get_database()["ledger"]


# ---------------------------------------------------------------------------
# Balance helpers
# ---------------------------------------------------------------------------


async def get_reseller_balance(reseller_id: str) -> float:
    """Get a reseller's current balance."""
    doc = await _resellers().find_one({"_id": ObjectId(reseller_id)})
    if doc is None:
        raise ValueError(f"Reseller {reseller_id} not found")
    return doc.get("balance", 0.0)


async def get_reseller_by_username(username: str) -> dict[str, Any] | None:
    """Get reseller by username."""
    doc = await _resellers().find_one({"username": username})
    if doc is not None:
        doc["_id"] = str(doc["_id"])
    return doc


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------


async def _write_ledger(
    reseller_id: str,
    ledger_type: LedgerType,
    amount: float,
    resulting_balance: float,
    product_id: str | None = None,
    duration: LicenseDuration | None = None,
    external_ref: str | None = None,
    note: str | None = None,
) -> None:
    """Write an immutable ledger entry."""
    entry = LedgerEntryDocument(
        reseller_id=reseller_id,
        type=ledger_type,
        amount=amount,
        resulting_balance=resulting_balance,
        product_id=product_id,
        duration=duration,
        external_ref=external_ref,
        note=note,
    )
    await _ledger().insert_one(entry.model_dump())


async def get_ledger(
    reseller_id: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """Get paginated ledger entries for a reseller."""
    coll = _ledger()
    query = {"reseller_id": reseller_id}
    total = await coll.count_documents(query)
    skip = (page - 1) * page_size
    cursor = coll.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    results: list[dict[str, Any]] = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results, total


# ---------------------------------------------------------------------------
# Admin: credit reseller balance
# ---------------------------------------------------------------------------


async def credit_balance(request: AdminCreditRequest) -> dict[str, Any]:
    """Admin credits a reseller's balance. Atomic operation with ledger."""
    reseller = await get_reseller_by_username(request.username)
    if reseller is None:
        raise ValueError(f"Reseller '{request.username}' not found")

    reseller_id = reseller["_id"]

    # Atomic balance update
    result = await _resellers().update_one(
        {"_id": ObjectId(reseller_id)},
        {"$inc": {"balance": request.amount}},
    )
    if result.modified_count == 0:
        raise RuntimeError("Failed to credit balance")

    # Fetch new balance
    new_balance = await get_reseller_balance(reseller_id)

    # Write ledger
    await _write_ledger(
        reseller_id=reseller_id,
        ledger_type=LedgerType.CREDIT,
        amount=request.amount,
        resulting_balance=new_balance,
        external_ref=request.external_ref,
        note=request.note or f"Credit via {request.source}",
    )

    return {
        "username": request.username,
        "amount": request.amount,
        "new_balance": new_balance,
    }


# ---------------------------------------------------------------------------
# Store: purchase stock (SAGA pattern for M0 Free Tier)
# ---------------------------------------------------------------------------


async def purchase_stock(
    reseller_id: str,
    request: PurchaseRequest,
) -> dict[str, Any]:
    """Reseller purchases stock from the store.

    Saga flow:
    1. Atomically debit balance (with $gte guard)
    2. Credit stock (upsert)
    3. Write ledger (purchase)
    On any step failure after step 1: issue compensating credit + refund ledger.
    """
    # 1. Look up the product duration pricing
    product_coll = get_database()["products"]
    product = await product_coll.find_one({"product_id": request.product_id})
    if product is None:
        raise ValueError(f"Product '{request.product_id}' not found")

    # Find the matching duration price
    durations = product.get("durations", [])
    price_per_unit: float | None = None
    for d in durations:
        if d.get("duration") == request.duration:
            if not d.get("enabled", True):
                raise ValueError(
                    f"Duration '{request.duration}' is disabled for {request.product_id}"
                )
            price_per_unit = d.get("price", 0.0)
            break

    if price_per_unit is None:
        raise ValueError(
            f"Duration '{request.duration}' not available for {request.product_id}"
        )

    total_cost = price_per_unit * request.quantity

    # 2. Atomic debit with balance >= total_cost guard
    debit_result = await _resellers().update_one(
        {"_id": ObjectId(reseller_id), "balance": {"$gte": total_cost}},
        {"$inc": {"balance": -total_cost}},
    )

    if debit_result.modified_count == 0:
        # Check if it failed due to insufficient balance or reseller not found
        current_balance = await get_reseller_balance(reseller_id)
        if current_balance < total_cost:
            raise ValueError(
                f"Insufficient balance: need ${total_cost:.2f}, have ${current_balance:.2f}"
            )
        raise ValueError("Reseller not found")

    new_balance = await get_reseller_balance(reseller_id)

    # 3. Credit stock (upsert) — if this fails, refund the debit
    try:
        await _stock().update_one(
            {
                "reseller_id": reseller_id,
                "product_id": request.product_id,
                "duration": request.duration,
            },
            {
                "$inc": {"quantity": request.quantity},
                "$setOnInsert": {
                    "reseller_id": reseller_id,
                    "product_id": request.product_id,
                    "duration": request.duration,
                    "created_at": datetime.now(tz=timezone.utc),
                },
                "$set": {"updated_at": datetime.now(tz=timezone.utc)},
            },
            upsert=True,
        )

        # 4. Write purchase ledger
        await _write_ledger(
            reseller_id=reseller_id,
            ledger_type=LedgerType.PURCHASE,
            amount=-total_cost,
            resulting_balance=new_balance,
            product_id=request.product_id,
            duration=request.duration,
            note=f"Purchased {request.quantity}x {request.duration}",
        )

    except Exception:
        # Compensating action: refund the balance
        logger.exception("Purchase flow failed after debit — issuing refund")
        await _resellers().update_one(
            {"_id": ObjectId(reseller_id)},
            {"$inc": {"balance": total_cost}},
        )
        refund_balance = await get_reseller_balance(reseller_id)
        await _write_ledger(
            reseller_id=reseller_id,
            ledger_type=LedgerType.REFUND,
            amount=total_cost,
            resulting_balance=refund_balance,
            product_id=request.product_id,
            duration=request.duration,
            note="Compensating refund: purchase flow failed",
        )
        raise ValueError("Purchase failed: stock credit could not be completed. Balance refunded.")

    return {
        "product_id": request.product_id,
        "duration": request.duration,
        "quantity": request.quantity,
        "total_cost": total_cost,
        "new_balance": new_balance,
    }


# ---------------------------------------------------------------------------
# Key generation from stock (SAGA pattern)
# ---------------------------------------------------------------------------


async def generate_key_from_stock(
    reseller_id: str,
    request: GenerateKeyRequest,
) -> dict[str, Any]:
    """Reseller generates a license key from their stock inventory.

    Saga flow:
    1. Atomically decrement stock (with quantity >= 1 guard)
    2. Create license (same as admin flow)
    On step 2 failure: increment stock back + compensate.
    """
    # 1. Decrement stock with guard
    decrement_result = await _stock().update_one(
        {
            "reseller_id": reseller_id,
            "product_id": request.product_id,
            "duration": request.duration,
            "quantity": {"$gte": 1},
        },
        {
            "$inc": {"quantity": -1},
            "$set": {"updated_at": datetime.now(tz=timezone.utc)},
        },
    )

    if decrement_result.modified_count == 0:
        raise ValueError(
            f"No stock available for {request.product_id} / {request.duration}. "
            f"Purchase stock first from the store."
        )

    # 2. Create the license
    try:
        create_req = LicenseCreateRequest(
            product_id=request.product_id,
            customer=request.customer,
            duration=request.duration,
            features=request.features,
        )
        license_doc = await create_license(create_req, created_by=reseller_id)

        # Write key-generation ledger entry (zero-balance, informational)
        await _write_ledger(
            reseller_id=reseller_id,
            ledger_type=LedgerType.KEY_GENERATION,
            amount=0.0,
            resulting_balance=await get_reseller_balance(reseller_id),
            product_id=request.product_id,
            duration=request.duration,
            external_ref=license_doc["license_key"],
            note=f"Generated key {license_doc['license_key']}",
        )

        return license_doc

    except Exception:
        # Compensating action: return stock to inventory
        logger.exception("Key generation failed after stock decrement — returning stock")
        await _stock().update_one(
            {
                "reseller_id": reseller_id,
                "product_id": request.product_id,
                "duration": request.duration,
            },
            {"$inc": {"quantity": 1}},
        )
        raise ValueError("Key generation failed: stock has been returned to inventory.")


# ---------------------------------------------------------------------------
# Inventory queries
# ---------------------------------------------------------------------------


async def get_stock_inventory(reseller_id: str) -> list[dict[str, Any]]:
    """Get all stock for a reseller, enriched with product names."""
    stock_coll = _stock()
    product_coll = get_database()["products"]

    cursor = stock_coll.find({"reseller_id": reseller_id, "quantity": {"$gt": 0}})
    results: list[dict[str, Any]] = []
    async for doc in cursor:
        # Enrich with product name
        product = await product_coll.find_one({"product_id": doc["product_id"]})
        doc["_id"] = str(doc["_id"])
        doc["product_name"] = product["name"] if product else doc["product_id"]
        results.append(doc)
    return results


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------


async def setup_reseller_indexes() -> None:
    """Create MongoDB indexes for reseller-related collections."""
    await _stock().create_index(
        [("reseller_id", 1), ("product_id", 1), ("duration", 1)], unique=True
    )
    await _ledger().create_index("reseller_id")
    await _ledger().create_index("created_at")
