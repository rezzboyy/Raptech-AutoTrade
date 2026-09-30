"""Enkripsi rahasia at-rest (password akun & API Key MCP).

Menggantikan penyandian base64 dengan enkripsi sungguhan (Fernet = AES-128-CBC +
HMAC-SHA256) dari paket `cryptography`.

Manajemen kunci:
    - Default: kunci acak disimpan di berkas lokal `.secret_key` (masuk .gitignore).
      Ini melindungi berkas profil dari terbaca/terbagi tanpa sengaja (mis. ter-commit
      atau dikirim), bukan dari penyerang yang sudah menguasai mesin.
    - Opsional master password: set env `MASTER_PASSWORD` -> kunci diturunkan via
      PBKDF2-HMAC-SHA256 (tanpa menyimpan kunci di disk).

Kompatibilitas mundur:
    - Token terenkripsi diawali penanda "enc:v1:".
    - Nilai lama (base64 murni tanpa penanda) tetap bisa dibaca (fallback) lalu
      otomatis dienkripsi ulang saat disimpan berikutnya.
"""

import base64
import hashlib
import os
import sys
from pathlib import Path

from src.logger import get_logger

logger = get_logger(__name__)

_PREFIX = "enc:v1:"
_KEY_FILE = ".secret_key"
# Salt tetap untuk derivasi master password (disimpan bersama aplikasi).
_PBKDF2_SALT = b"raptech-mt5-bot-v1-salt"
_PBKDF2_ITERS = 200_000

_fernet = None  # cache instance


def _key_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent / _KEY_FILE)
    return _KEY_FILE


def _load_or_create_key() -> bytes:
    """Ambil kunci Fernet dari master password (env) atau berkas kunci lokal."""
    from cryptography.fernet import Fernet

    master = os.getenv("MASTER_PASSWORD")
    if master:
        dk = hashlib.pbkdf2_hmac("sha256", master.encode("utf-8"), _PBKDF2_SALT, _PBKDF2_ITERS)
        return base64.urlsafe_b64encode(dk)

    path = _key_path()
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                data = f.read().strip()
            if data:
                return data
        except OSError as exc:
            logger.error("Gagal membaca berkas kunci: %s", exc)

    key = Fernet.generate_key()
    try:
        with open(path, "wb") as f:
            f.write(key)
        logger.info("Berkas kunci enkripsi dibuat: %s", path)
    except OSError as exc:
        logger.error("Gagal menulis berkas kunci: %s", exc)
    return key


def _get_fernet():
    global _fernet
    if _fernet is None:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def reset_cache() -> None:
    """Kosongkan cache instance (dipakai di test setelah ganti kunci)."""
    global _fernet
    _fernet = None


def encrypt(text: str) -> str:
    """Enkripsi teks menjadi token '<prefix><base64>'. String kosong -> "" apa adanya."""
    text = text or ""
    if text == "":
        return ""
    try:
        token = _get_fernet().encrypt(text.encode("utf-8")).decode("ascii")
        return _PREFIX + token
    except Exception as exc:  # noqa: BLE001
        logger.error("Enkripsi gagal, fallback ke base64: %s", exc)
        return base64.b64encode(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Dekripsi token. Mendukung format lama (base64 murni) demi kompatibilitas."""
    if not token:
        return ""
    if token.startswith(_PREFIX):
        raw = token[len(_PREFIX):]
        try:
            return _get_fernet().decrypt(raw.encode("ascii")).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.error("Dekripsi gagal: %s", exc)
            return ""
    # Fallback: nilai lama tersandi base64 (bukan enkripsi).
    try:
        return base64.b64decode(token.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def is_encrypted(token: str) -> bool:
    return bool(token) and token.startswith(_PREFIX)
