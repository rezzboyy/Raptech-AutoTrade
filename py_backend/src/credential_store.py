"""Profil kredensial akun MT5 (login otomatis tanpa input ulang).

Profil disimpan sebagai file JSON di folder `profiles/`. Setelah login sukses,
profil bisa disimpan lalu dimuat kembali (pilih file / pilih dari daftar).

KEAMANAN — HARAP DIBACA:
    Password disimpan dengan penyandian base64 yang HANYA menyamarkan tampilan,
    BUKAN enkripsi. Siapa pun yang punya file profil dapat memulihkan password.
    Karena itu:
        - folder `profiles/` masuk .gitignore (jangan di-commit),
        - jangan bagikan file profil,
        - simpan hanya di perangkat yang Anda percaya.
    Untuk keamanan sungguhan, pertimbangkan enkripsi dengan kata sandi master
    (bisa ditambahkan kemudian).
"""

import json
import os
import re

from config.settings import settings
from src import secure_store
from src.logger import get_logger

logger = get_logger(__name__)

PROFILES_DIR = "profiles"


def _ensure_dir() -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    """Ubah nama profil jadi nama file aman."""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return (safe or "profil") + ".json"


def _obfuscate(text: str) -> str:
    """Enkripsi password (Fernet/AES). Nama dipertahankan demi kompatibilitas."""
    return secure_store.encrypt(text)


def _deobfuscate(token: str) -> str:
    """Dekripsi password (mendukung format lama base64 untuk kompatibilitas)."""
    return secure_store.decrypt(token)


def validate(creds: dict) -> list:
    """Validasi kredensial. Kembalikan daftar pesan error."""
    errors = []
    try:
        if int(creds.get("login", 0)) <= 0:
            errors.append("Login (nomor akun) harus angka > 0.")
    except (TypeError, ValueError):
        errors.append("Login harus berupa angka.")
    if not str(creds.get("server", "")).strip():
        errors.append("Server broker tidak boleh kosong.")
    if not str(creds.get("password", "")):
        errors.append("Password tidak boleh kosong.")
    return errors


def apply_to_settings(creds: dict) -> None:
    """Terapkan kredensial ke settings (dipakai saat connect)."""
    if "login" in creds and creds["login"] not in (None, ""):
        settings.login = int(creds["login"])
    if "password" in creds and creds["password"] is not None:
        settings.password = str(creds["password"])
    if "server" in creds:
        settings.server = str(creds.get("server", ""))
    if "path" in creds:
        settings.path = str(creds.get("path", "") or "")


def current_credentials(include_password: bool = True) -> dict:
    """Ambil kredensial saat ini dari settings."""
    data = {
        "login": settings.login,
        "server": settings.server,
        "path": settings.path,
    }
    if include_password:
        data["password"] = settings.password
    return data


def save_profile(name: str, creds: dict = None) -> str:
    """Simpan profil ke JSON. Kembalikan path file, atau "" bila gagal."""
    _ensure_dir()
    data = creds or current_credentials(include_password=True)
    record = {
        "name": name.strip() or "profil",
        "login": int(data.get("login", 0) or 0),
        "server": str(data.get("server", "")),
        "path": str(data.get("path", "") or ""),
        "password": _obfuscate(str(data.get("password", ""))),
        "_note": "password terenkripsi (AES/Fernet) - tetap jangan dibagikan",
    }
    file_path = os.path.join(PROFILES_DIR, _safe_filename(record["name"]))
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        logger.info("Profil '%s' disimpan.", record["name"])
        return file_path
    except OSError as exc:
        logger.error("Gagal menyimpan profil: %s", exc)
        return ""


def load_profile(file_path: str) -> dict:
    """Muat profil dari file JSON. Kembalikan dict kredensial (password sudah dibuka).

    Kembalikan dict kosong bila gagal.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Gagal memuat profil %s: %s", file_path, exc)
        return {}

    return {
        "name": record.get("name", ""),
        "login": int(record.get("login", 0) or 0),
        "server": record.get("server", ""),
        "path": record.get("path", ""),
        "password": _deobfuscate(record.get("password", "")),
    }


def list_profiles() -> list:
    """Daftar profil tersimpan (tanpa password) untuk ditampilkan di UI."""
    _ensure_dir()
    result = []
    for fname in sorted(os.listdir(PROFILES_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(PROFILES_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
            result.append({
                "name": record.get("name", fname[:-5]),
                "login": record.get("login", 0),
                "server": record.get("server", ""),
                "file": path,
            })
        except (OSError, json.JSONDecodeError):
            continue
    return result


def delete_profile(file_path: str) -> bool:
    try:
        os.remove(file_path)
        logger.info("Profil dihapus: %s", file_path)
        return True
    except OSError as exc:
        logger.error("Gagal menghapus profil: %s", exc)
        return False
