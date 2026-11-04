from __future__ import annotations

"""Unit tests for secure store, authenticated encryption (AES-256-GCM), and v1 migration."""

import base64
import pytest

from core.secure_store import _legacy_keystream_xor, _load_or_create_key, decrypt, encrypt, mask_token


def test_encryption_roundtrip():
    secret = "MySuperSecretPassword123!"
    encrypted = encrypt(secret)
    assert encrypted.startswith("enc:v2:")
    assert encrypted != secret

    decrypted = decrypt(encrypted)
    assert decrypted == secret


def test_idempotent_encryption():
    secret = "AlreadyEncrypted"
    enc1 = encrypt(secret)
    enc2 = encrypt(enc1)
    assert enc1 == enc2


def test_decrypt_legacy_v1_compatibility():
    secret = "LegacyPasswordToMigrate"
    key = _load_or_create_key()
    legacy_cipher = _legacy_keystream_xor(secret.encode("utf-8"), key)
    legacy_enc = f"enc:v1:{base64.urlsafe_b64encode(legacy_cipher).decode('ascii')}"

    # Decrypt should handle legacy enc:v1: perfectly
    assert decrypt(legacy_enc) == secret


def test_decrypt_plain_fallback():
    plain = "PlainTextPassword"
    assert decrypt(plain) == plain
    assert decrypt("") == ""


def test_mask_token():
    assert mask_token("abcdef123456", visible_chars=3) == "abc...456"
    assert mask_token("short", visible_chars=4) == "*****"
    assert mask_token("") == ""
