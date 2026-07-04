"""Reseller models: stock, ledger, purchase/key-generation schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.license import LicenseDuration


class LedgerType(str, Enum):
    CREDIT = "credit"
    PURCHASE = "purchase"
    REFUND = "refund"
    KEY_GENERATION = "key_generation"


class ResellerStockDocument(BaseModel):
    reseller_id: str
    product_id: str
    duration: LicenseDuration
    quantity: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class LedgerEntryDocument(BaseModel):
    reseller_id: str
    type: LedgerType
    amount: float
    resulting_balance: float
    product_id: str | None = None
    duration: LicenseDuration | None = None
    external_ref: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class PurchaseRequest(BaseModel):
    product_id: str
    duration: LicenseDuration
    quantity: int = Field(ge=1, le=100)


class GenerateKeyRequest(BaseModel):
    product_id: str
    duration: LicenseDuration
    customer: str | None = None
    features: list[str] = Field(default_factory=list)


class ResellerStockResponse(BaseModel):
    product_id: str
    product_name: str | None = None
    duration: LicenseDuration
    quantity: int


class LedgerEntryResponse(BaseModel):
    type: LedgerType
    amount: float
    resulting_balance: float
    product_id: str | None = None
    duration: LicenseDuration | None = None
    external_ref: str | None = None
    note: str | None = None
    created_at: datetime


class AdminCreditRequest(BaseModel):
    username: str
    amount: float = Field(gt=0)
    source: str = "manual"
    external_ref: str | None = None
    note: str | None = None
