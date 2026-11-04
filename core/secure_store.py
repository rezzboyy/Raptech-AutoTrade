from __future__ import annotations

"""
Raptech Autotrade CLI — Secure Credential Store (v3.0).
Provides Authenticated Encryption (AES-256-GCM) with random 96-bit nonces.
Maintains full backward compatibility for decrypting legacy enc:v1: ciphertexts.
"""

import base64
import hashlib
import os
from pathlib import Path
import sys
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_AESGCM = True
except ImportError:
    AESGCM = None  # type: ignore
    HAS_AESGCM = False

_PREFIX_V2 = "enc:v2:"
_PREFIX_V1 = "enc:v1:"
_KEY_FILE = ".secret_key"
_SALT = b"raptech-autotrade-cli-salt-v1"


def _key_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        k1 = exe_dir / _KEY_FILE
        if k1.exists():
            return k1
        k2 = exe_dir.parent / _KEY_FILE
        if k2.exists():
            return k2
        return k1
    return Path(_KEY_FILE)


def _load_or_create_key() -> bytes:
    master = os.getenv("MASTER_PASSWORD")
    if master:
        dk = hashlib.pbkdf2_hmac("sha256", master.encode("utf-8"), _SALT, 100_000)
        return dk

    path = _key_path()
    if path.exists():
        try:
            data = path.read_bytes().strip()
            if len(data) >= 32:
                return data[:32]
        except Exception:
            pass

    # Generate 32 bytes (256-bit) cryptographically secure random key
    new_key = os.urandom(32)
    try:
        path.write_bytes(new_key)
        # On POSIX restrict permissions to owner only (0600)
        if sys.platform != "win32":
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
    except Exception:
        pass
    return new_key


def _legacy_keystream_xor(data: bytes, key: bytes) -> bytes:
    """Legacy CTR keystream cipher using SHA-256 blocks for v1 backward compatibility."""
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block_hash = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        out.extend(block_hash)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out[: len(data)]))


def encrypt(plain: str) -> str:
    """
    Encrypt plaintext string using AES-256-GCM with a fresh random 96-bit nonce.
    Returns format 'enc:v2:<nonce_b64>:<ciphertext_and_tag_b64>'.
    """
    if not plain:
        return ""
    if plain.startswith(_PREFIX_V2) or plain.startswith(_PREFIX_V1):
        return plain  # Already encrypted

    key = _load_or_create_key()

    if HAS_AESGCM:
        nonce = os.urandom(12)  # 96-bit unique nonce per encryption
        aesgcm = AESGCM(key)
        ct = aesgcm.encrypt(nonce, plain.encode("utf-8"), None)
        nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")
        ct_b64 = base64.urlsafe_b64encode(ct).decode("ascii")
        return f"{_PREFIX_V2}{nonce_b64}:{ct_b64}"
    else:
        # Fallback if cryptography package is missing in environment
        cipher_bytes = _legacy_keystream_xor(plain.encode("utf-8"), key)
        b64 = base64.urlsafe_b64encode(cipher_bytes).decode("ascii")
        return f"{_PREFIX_V1}{b64}"


def decrypt(encrypted: str) -> str:
    """
    Decrypt string. Supports enc:v2: (AES-256-GCM), legacy enc:v1:, or plain text fallback.
    """
    if not encrypted:
        return ""

    key = _load_or_create_key()

    # Case 1: v2 Authenticated AES-GCM
    if encrypted.startswith(_PREFIX_V2):
        body = encrypted[len(_PREFIX_V2) :]
        if ":" not in body:
            return encrypted
        nonce_b64, ct_b64 = body.split(":", 1)
        try:
            nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
            ct = base64.urlsafe_b64decode(ct_b64.encode("ascii"))
            if HAS_AESGCM:
                aesgcm = AESGCM(key)
                plain_bytes = aesgcm.decrypt(nonce, ct, None)
                return plain_bytes.decode("utf-8")
        except Exception:
            return encrypted

    # Case 2: Legacy v1 Keystream
    if encrypted.startswith(_PREFIX_V1):
        b64_part = encrypted[len(_PREFIX_V1) :]
        try:
            cipher_bytes = base64.urlsafe_b64decode(b64_part.encode("ascii"))
            plain_bytes = _legacy_keystream_xor(cipher_bytes, key)
            return plain_bytes.decode("utf-8")
        except Exception:
            return encrypted

    # Case 3: Plain text fallback
    return encrypted


def mask_token(token: str, visible_chars: int = 4) -> str:
    """Mask token showing only leading and trailing characters."""
    t = str(token or "").strip()
    if not t:
        return ""
    if len(t) <= visible_chars * 2:
        return "*" * len(t)
    return f"{t[:visible_chars]}...{t[-visible_chars:]}"
