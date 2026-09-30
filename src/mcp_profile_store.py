"""Profil koneksi MCP (login otomatis tanpa input ulang endpoint/API Key).

Profil disimpan sebagai JSON di folder `mcp_profiles/`. Setelah connect MCP sukses,
profil bisa disimpan lalu dimuat kembali (pilih file / pilih dari daftar), analog
dengan credential_store untuk backend native.

KEAMANAN: API Key disandikan base64 (HANYA menyamarkan tampilan, BUKAN enkripsi).
Folder `mcp_profiles/` masuk .gitignore — jangan dibagikan.
"""

import json
import os
import re

from config.settings import settings
from src import secure_store
from src.logger import get_logger

logger = get_logger(__name__)

PROFILES_DIR = "mcp_profiles"
DEFAULT_ENDPOINT = "http://127.0.0.1:22346/mcp"


def _ensure_dir() -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)


def _safe_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip())
    return (safe or "mcp") + ".json"


def _obfuscate(text: str) -> str:
    """Enkripsi API Key (Fernet/AES)."""
    return secure_store.encrypt(text)


def _deobfuscate(token: str) -> str:
    """Dekripsi API Key (mendukung format lama base64)."""
    return secure_store.decrypt(token)


def validate(cfg: dict) -> list:
    """Validasi konfigurasi MCP. Kembalikan daftar pesan error."""
    errors = []
    if not str(cfg.get("endpoint", "")).strip():
        errors.append("Endpoint MCP tidak boleh kosong.")
    if not str(cfg.get("api_key", "")).strip():
        errors.append("API Key MCP tidak boleh kosong.")
    return errors


def apply_to_settings(cfg: dict) -> None:
    """Terapkan konfigurasi MCP ke settings (backend=mcp)."""
    settings.backend = "mcp"
    if cfg.get("endpoint"):
        settings.mcp_endpoint = str(cfg["endpoint"])
    if cfg.get("api_key") is not None:
        settings.mcp_api_key = str(cfg["api_key"])


def current_config(include_key: bool = True) -> dict:
    data = {"endpoint": settings.mcp_endpoint or DEFAULT_ENDPOINT}
    if include_key:
        data["api_key"] = settings.mcp_api_key
    return data


def save_profile(name: str, cfg: dict = None) -> str:
    """Simpan profil MCP ke JSON. Kembalikan path file, atau "" bila gagal."""
    _ensure_dir()
    data = cfg or current_config(include_key=True)
    record = {
        "name": (name or "").strip() or "mcp",
        "endpoint": str(data.get("endpoint", DEFAULT_ENDPOINT)),
        "api_key": _obfuscate(str(data.get("api_key", ""))),
        "_note": "api_key terenkripsi (AES/Fernet) - tetap jangan dibagikan",
    }
    file_path = os.path.join(PROFILES_DIR, _safe_filename(record["name"]))
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        logger.info("Profil MCP '%s' disimpan.", record["name"])
        return file_path
    except OSError as exc:
        logger.error("Gagal menyimpan profil MCP: %s", exc)
        return ""


def load_profile(file_path: str) -> dict:
    """Muat profil MCP dari file JSON (api_key sudah dibuka). {} bila gagal.

    Mendukung DUA format:
      1. Profil MCP  : {"name","endpoint","api_key"(terenkripsi)}
      2. mcp_secret  : {"mcp_endpoint","mcp_api_key"(teks biasa)}  <- file rahasia startup
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Gagal memuat profil MCP %s: %s", file_path, exc)
        return {}

    if not isinstance(record, dict):
        return {}

    # Format mcp_secret.json (field mcp_* , API key TEKS BIASA / tidak terenkripsi).
    if "mcp_api_key" in record or "mcp_endpoint" in record:
        return {
            "name": record.get("name", "mcp_secret"),
            "endpoint": str(record.get("mcp_endpoint") or DEFAULT_ENDPOINT),
            "api_key": str(record.get("mcp_api_key", "")),
        }

    # Format profil MCP biasa (api_key terenkripsi).
    return {
        "name": record.get("name", ""),
        "endpoint": record.get("endpoint", DEFAULT_ENDPOINT),
        "api_key": _deobfuscate(record.get("api_key", "")),
    }


def list_profiles() -> list:
    """Daftar profil MCP tersimpan (tanpa api_key) untuk UI."""
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
                "endpoint": record.get("endpoint", ""),
                "file": path,
            })
        except (OSError, json.JSONDecodeError):
            continue
    return result


def delete_profile(file_path: str) -> bool:
    try:
        os.remove(file_path)
        logger.info("Profil MCP dihapus: %s", file_path)
        return True
    except OSError as exc:
        logger.error("Gagal menghapus profil MCP: %s", exc)
        return False


def secret_file_path() -> str:
    """Lokasi mcp_secret.json. Saat EXE (frozen) -> folder di samping EXE
    (agar SAMA dengan lokasi yang dibaca saat startup)."""
    import sys
    from pathlib import Path
    from config.settings import MCP_SECRET_FILE
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent / MCP_SECRET_FILE)
    return MCP_SECRET_FILE


def save_secret_file(cfg: dict = None, path: str = None) -> str:
    """Simpan endpoint + api_key ke mcp_secret.json (dipakai auto-load saat startup).

    Dipanggil otomatis tiap connect MCP sukses sehingga API key baru yang
    dimasukkan pengguna langsung tersimpan sebagai file JSON. Kembalikan path
    file, atau "" bila gagal.
    """
    data = cfg or current_config(include_key=True)
    target = path or secret_file_path()
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump({
                "mcp_endpoint": data.get("endpoint", DEFAULT_ENDPOINT),
                "mcp_api_key": data.get("api_key", ""),
            }, f, indent=2)
        logger.info("Konfigurasi MCP disimpan ke %s.", target)
        return target
    except OSError as exc:
        logger.error("Gagal menyimpan %s: %s", target, exc)
        return ""
