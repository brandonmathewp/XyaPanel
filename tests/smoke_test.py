"""Quick smoke test for Phase 1 — verification without MongoDB."""

from datetime import datetime, timezone

from app.models.license import LicenseStatus, LicenseDuration, LicenseCreateRequest
from app.services.license_service import _generate_license_key, _compute_expiry


def test_key_generation():
    for _ in range(10):
        key = _generate_license_key()
        assert key.startswith("xya-"), key
        assert len(key) == 36, f"bad length: {len(key)} (key={key})"
    print("PASS: key generation")


def test_expiry_calculation():
    now = datetime.now(tz=timezone.utc)

    # 2 hours
    exp = _compute_expiry(LicenseDuration.TWO_HOURS, now)
    assert exp is not None
    assert (exp - now).total_seconds() == 7200

    # 1 day
    exp = _compute_expiry(LicenseDuration.ONE_DAY, now)
    assert (exp - now).total_seconds() == 86400

    # 1 year
    exp = _compute_expiry(LicenseDuration.ONE_YEAR, now)
    assert (exp - now).days == 365

    # lifetime
    exp = _compute_expiry(LicenseDuration.LIFETIME)
    assert exp is None

    print("PASS: expiry calculation")


def test_models():
    req = LicenseCreateRequest(
        product_id="prod-1",
        duration=LicenseDuration.ONE_MONTH,
        features=["feat_a", "feat_b"],
    )
    assert req.product_id == "prod-1"
    assert req.duration == LicenseDuration.ONE_MONTH
    assert req.features == ["feat_a", "feat_b"]

    assert LicenseStatus.PENDING == "pending"
    assert LicenseStatus.ACTIVE == "active"

    print("PASS: models")


if __name__ == "__main__":
    test_key_generation()
    test_expiry_calculation()
    test_models()
    print("\nAll smoke tests passed.")
