"""Interface dasar strategi + registry + skema parameter.

Setiap strategi:
    - subclass Strategy,
    - punya atribut `name` (unik), `display_name`, dan `PARAMS` (skema parameter),
    - didekorasi @register agar terdaftar otomatis,
    - mengimplementasikan generate_signal(df) -> SIGNAL_BUY / SIGNAL_SELL / None.

Skema PARAMS dipakai UI untuk merender form parameter secara dinamis. Contoh:
    PARAMS = [
        {"key": "fast_period", "label": "MA Cepat", "type": "int", "default": 10, "min": 1},
    ]
"""

from abc import ABC, abstractmethod

import pandas as pd

# Sinyal yang dikenali loop trading.
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"

# Registry global nama -> kelas strategi.
_REGISTRY = {}


def register(cls):
    """Dekorator untuk mendaftarkan kelas strategi ke registry."""
    _REGISTRY[cls.name] = cls
    return cls


def get_registry() -> dict:
    """Kembalikan salinan registry strategi (nama -> kelas)."""
    return dict(_REGISTRY)


def series_to_points(s) -> list:
    """Ubah pandas Series ke list angka; NaN menjadi None (untuk overlay chart)."""
    return [None if pd.isna(x) else round(float(x), 5) for x in s]


class Strategy(ABC):
    """Antarmuka dasar untuk semua strategi."""

    name = "base"
    display_name = "Base"
    PARAMS = []  # daftar skema parameter

    def __init__(self, **params):
        self.params = self.resolve_params(params)
        # Ekspos tiap parameter sebagai atribut untuk kemudahan akses.
        for key, value in self.params.items():
            setattr(self, key, value)

    @classmethod
    def resolve_params(cls, params: dict) -> dict:
        """Lengkapi parameter dengan default + konversi tipe sesuai skema."""
        resolved = {}
        for spec in cls.PARAMS:
            key = spec["key"]
            raw = params.get(key, spec["default"])
            resolved[key] = int(raw) if spec["type"] == "int" else float(raw)
        return resolved

    @classmethod
    def validate_params(cls, params: dict) -> list:
        """Validasi parameter. Kembalikan daftar pesan error (kosong bila valid)."""
        errors = []
        for spec in cls.PARAMS:
            key = spec["key"]
            if key not in params or params[key] is None:
                continue
            try:
                value = int(params[key]) if spec["type"] == "int" else float(params[key])
            except (TypeError, ValueError):
                errors.append(f"{spec['label']} harus berupa angka.")
                continue
            if "min" in spec and value < spec["min"]:
                errors.append(f"{spec['label']} minimal {spec['min']}.")
        errors.extend(cls.extra_validate(params))
        return errors

    @classmethod
    def extra_validate(cls, params: dict) -> list:
        """Validasi lintas-parameter khusus (override bila perlu)."""
        return []

    @classmethod
    def describe(cls) -> dict:
        """Deskripsi strategi untuk UI (nama, label, skema parameter)."""
        return {
            "name": cls.name,
            "display_name": cls.display_name,
            "params": [dict(p) for p in cls.PARAMS],
        }

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame):
        """Hasilkan sinyal dari data candle. -> SIGNAL_BUY / SIGNAL_SELL / None."""
        raise NotImplementedError

    def compute_overlays(self, df: pd.DataFrame) -> list:
        """Garis indikator untuk digambar di atas chart harga (opsional).

        Kembalikan list of dict, tiap dict:
            {"name": str, "color": "#rrggbb", "points": [float|None, ...]}
        `points` harus selaras dengan urutan baris df (lama -> baru).
        Default: kosong (mis. strategi oscillator tanpa overlay harga).
        """
        return []
