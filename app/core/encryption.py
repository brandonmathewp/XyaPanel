"""AES-256-GCM encryption utilities with HKDF key derivation."""

from __future__ import annotations

import json
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from app.core.config import settings

NONCE_LEN = 12
TAG_LEN = 16


def derive_session_key(license_key: str, hwid: str) -> bytes:
    """Derive a per-session AES-256 key using HKDF from master secret."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=f"xya-session:{license_key}:{hwid}".encode(),
    )
    return hkdf.derive(settings.master_secret.encode())


def encrypt_payload(plaintext: bytes | str, key: bytes) -> str:
    """Encrypt with AES-256-GCM, returning hex: nonce||ciphertext||tag."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")
    nonce = secrets.token_bytes(NONCE_LEN)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)
    # ct = ciphertext || tag (16 bytes).  Prepend nonce in the output.
    return (nonce + ct).hex()


def decrypt_payload(ciphertext_hex: str, key: bytes) -> bytes:
    """Decrypt a hex-encoded AES-256-GCM payload."""
    ct = bytes.fromhex(ciphertext_hex)
    nonce = ct[:NONCE_LEN]
    ct_tag = ct[NONCE_LEN:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct_tag, None)


def encrypt_json(payload: dict | list, key: bytes) -> str:
    return encrypt_payload(json.dumps(payload, separators=(",", ":")), key)


def decrypt_json(ciphertext_hex: str, key: bytes) -> dict | list:
    return json.loads(decrypt_payload(ciphertext_hex, key).decode("utf-8"))