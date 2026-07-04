"""Watermark service: embed + extract license-specific HMAC watermarks in binaries.

APK watermarking:  writes HMAC hex as ZIP comment (standard, non-disruptive).
.so watermarking: appends magic marker + HMAC at end-of-file (harmless to loader).

Verification can be done by recomputing HMAC(MASTER_SECRET, license_key) and
comparing against the extracted watermark from the binary.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import struct
import zipfile

from app.core.config import settings

logger = logging.getLogger(__name__)

# Magic bytes prepended to .so watermark for identification
_SO_MAGIC = b"\x58\x59\x41\x01"  # "XYA\x01"
_SO_MAGIC_LEN = len(_SO_MAGIC)


# ---------------------------------------------------------------------------
# HMAC computation
# ---------------------------------------------------------------------------


def compute_watermark(license_key: str) -> str:
    """Compute HMAC-SHA256(server_secret, license_key) → hex string."""
    return hmac.new(
        settings.master_secret.encode(),
        license_key.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_watermark(license_key: str, extracted_watermark: str) -> bool:
    """Recompute and compare watermark."""
    expected = compute_watermark(license_key)
    return hmac.compare_digest(expected, extracted_watermark)


# ---------------------------------------------------------------------------
# APK watermarking (ZIP comment)
# ---------------------------------------------------------------------------


def watermark_apk(source_path: str, dest_path: str, license_key: str) -> None:
    """Read an APK (ZIP), set its comment to the license HMAC, write to dest.

    The ZIP comment is a standard field that does not affect APK
    installation or execution. It can be read back later for verification.
    """
    wm = compute_watermark(license_key)

    with (
        zipfile.ZipFile(source_path, "r") as zin,
        zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        for item in zin.infolist():
            data = zin.read(item.filename)
            zout.writestr(item, data)
        zout.comment = wm.encode("utf-8")

    logger.info("Watermarked APK: %s → %s (comment=%s)", source_path, dest_path, wm[:16] + "...")


def extract_apk_watermark(apk_path: str) -> str | None:
    """Read the ZIP comment from an APK. Returns None if not found."""
    with zipfile.ZipFile(apk_path, "r") as zf:
        comment = zf.comment
    if not comment:
        return None
    return comment.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# .so watermarking (end-of-file append)
# ---------------------------------------------------------------------------


def watermark_so(source_path: str, dest_path: str, license_key: str) -> None:
    """Read a .so (ELF) binary, append magic + HMAC at end, write to dest.

    The appended data sits past the last ELF section and is invisible
    to the dynamic loader. Verification reads the last N bytes looking
    for the magic prefix.
    """
    wm = compute_watermark(license_key)

    with open(source_path, "rb") as f:
        original = f.read()

    watermark_blob = _SO_MAGIC + wm.encode("utf-8")

    with open(dest_path, "wb") as f:
        f.write(original)
        f.write(watermark_blob)

    logger.info(
        "Watermarked .so: %s → %s (appended %d bytes)", source_path, dest_path, len(watermark_blob)
    )


def extract_so_watermark(so_path: str) -> str | None:
    """Read the appended watermark from a .so file. Returns None if not found."""
    with open(so_path, "rb") as f:
        # Read the last chunk that could contain a watermark
        # HMAC-SHA256 hex = 64 chars + magic = 68 bytes
        f.seek(-(_SO_MAGIC_LEN + 64), os.SEEK_END)
        tail = f.read()

    idx = tail.find(_SO_MAGIC)
    if idx == -1:
        # Try larger tail in case the file is small
        f.seek(0)
        tail = f.read()
        idx = tail.find(_SO_MAGIC)
        if idx == -1:
            return None

    # Extract the 64 hex chars after the magic
    start = idx + _SO_MAGIC_LEN
    return tail[start:start + 64].decode("ascii", errors="replace")


# ---------------------------------------------------------------------------
# High-level: watermark both artifacts for a license
# ---------------------------------------------------------------------------


async def watermark_license_artifacts(
    product_id: str,
    license_key: str,
    apk_source: str | None,
    so_source: str | None,
    output_dir: str,
) -> dict[str, str | None]:
    """Watermark both APK and .so for a given license.

    Returns dict with paths to watermarked files (or None if skipped).
    """
    os.makedirs(output_dir, exist_ok=True)

    result: dict[str, str | None] = {"apk": None, "so": None}

    if apk_source and os.path.exists(apk_source):
        apk_dest = os.path.join(output_dir, f"{license_key}.apk")
        watermark_apk(apk_source, apk_dest, license_key)
        result["apk"] = apk_dest

    if so_source and os.path.exists(so_source):
        so_dest = os.path.join(output_dir, f"{license_key}.so")
        watermark_so(so_source, so_dest, license_key)
        result["so"] = so_dest

    return result
