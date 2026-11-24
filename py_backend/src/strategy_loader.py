"""Pemuat strategi: menemukan & membuat instance strategi dari paket `strategies`.

- Mode EXE (frozen): mengandalkan import statis di strategies/__init__.py.
- Mode pengembangan: juga memindai folder untuk menemukan file strategi baru
  secara otomatis (tanpa perlu edit __init__.py).
"""

import importlib
import pkgutil
import sys

import strategies
from strategies.base import get_registry
from src.logger import get_logger

logger = get_logger("mt5bot")

_loaded = False


def load_all() -> None:
    """Muat semua modul strategi agar terdaftar di registry."""
    global _loaded
    # Import paket (memicu import statis strategi bawaan).
    importlib.reload(strategies) if _loaded else None

    if not getattr(sys, "frozen", False):
        # Pengembangan: pindai folder untuk strategi tambahan.
        for mod in pkgutil.iter_modules(strategies.__path__):
            if mod.name == "base":
                continue
            try:
                importlib.import_module(f"strategies.{mod.name}")
            except Exception as exc:  # noqa: BLE001
                logger.error("Gagal memuat strategi '%s': %s", mod.name, exc)

    _loaded = True


def ensure_loaded() -> None:
    if not _loaded:
        load_all()


_CUSTOM_SCRIPT_DESC = {
    "name": "custom_script",
    "display_name": "Custom Script (Programmer)",
    "params": [],  # parameter dinamis dari skrip, dikelola di tab Programmer
}


def available() -> list:
    """Daftar deskripsi strategi resmi (Mode Programmer tunggal)."""
    return [dict(_CUSTOM_SCRIPT_DESC)]


def names() -> list:
    ensure_loaded()
    return ["custom_script"] + list(get_registry().keys())


def get_class(name: str):
    ensure_loaded()
    return get_registry().get(name)


def create(name: str, params: dict = None):
    """Buat instance strategi berdasarkan nama + parameter."""
    if name == "custom_script":
        from strategies.script_runtime import ScriptStrategy
        from config import settings
        return ScriptStrategy(settings.script_source, params or {})
    cls = get_class(name)
    if cls is not None:
        return cls(**(params or {}))
    from strategies.script_runtime import ScriptStrategy
    return ScriptStrategy("", {})


def validate(name: str, params: dict) -> list:
    """Validasi nama strategi + parameternya. Kembalikan daftar error."""
    if name == "custom_script":
        return []
    cls = get_class(name)
    if cls is None:
        return [f"Strategi tidak dikenal: {name}"]
    return cls.validate_params(params or {})
