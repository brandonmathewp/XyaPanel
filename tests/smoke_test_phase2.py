"""Smoke test for Phase 2: auth service logic (no MongoDB needed)."""

import time

from app.models.auth import UserRole
from app.services.auth_service import (
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)


def test_password_hashing():
    pw = "SuperSecret123!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)
    print("PASS: password hashing")


def test_jwt_roundtrip():
    token = create_jwt_token("admin@xya.local", UserRole.ADMIN)
    claims = decode_jwt_token(token)
    assert claims["sub"] == "admin@xya.local"
    assert claims["role"] == "admin"
    print("PASS: JWT roundtrip")


def test_jwt_role_enforcement():
    admin_token = create_jwt_token("admin@xya.local", UserRole.ADMIN)
    reseller_token = create_jwt_token("reseller1", UserRole.RESELLER)

    admin_claims = decode_jwt_token(admin_token)
    assert admin_claims["role"] == "admin"

    reseller_claims = decode_jwt_token(reseller_token)
    assert reseller_claims["role"] == "reseller"
    print("PASS: JWT role enforcement")


if __name__ == "__main__":
    test_password_hashing()
    test_jwt_roundtrip()
    test_jwt_role_enforcement()
    print("\nAll Phase 2 smoke tests passed.")
