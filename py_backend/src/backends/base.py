"""Antarmuka backend trading + model data ternormalisasi + util bersama.

Semua operasi MT5 yang dibutuhkan bot diakses lewat `TradingBackend`. Dua
implementasi konkret:
    - NativeBackend : membungkus library `MetaTrader5` (perilaku lama).
    - McpBackend    : memakai server MCP bawaan MT5 (kebal masalah versi library).

Kontrak mengembalikan dict ternormalisasi (lihat "Model data" di bawah) agar
kode pemakai (engine, risk, order) tidak bergantung pada tipe objek `mt5`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol, runtime_checkable


# ----- Pemetaan timeframe internal -> string period MCP -----

# String timeframe yang dipakai UI/settings (settings.timeframe_str).
_TIMEFRAME_TO_PERIOD = {
    "M1": "M1",
    "M5": "M5",
    "M15": "M15",
    "M30": "M30",
    "H1": "H1",
    "H4": "H4",
    "D1": "D1",
}

# Perkiraan menit per timeframe (untuk menghitung rentang waktu candle).
_TIMEFRAME_MINUTES = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}

# Tipe pending order yang didukung.
PENDING_ORDER_TYPES = ("buy_limit", "sell_limit", "buy_stop", "sell_stop")

# Faktor buffer untuk mengantisipasi jam market tutup / akhir pekan sehingga
# jumlah candle yang terkumpul cukup sebelum dipangkas ke `count`.
_RANGE_BUFFER = 3.0


def classify_account_type(type_str: str, server: str) -> str:
    """Klasifikasi tipe akun resmi dari MT5: 'DEMO' | 'REAL' | 'CONTEST' | '?'.

    Menggabungkan field `type` MT5 dengan nama server, karena sebagian broker
    (mis. Exness) menaruh akun demo/trial di server bertipe 'real'. Nama server
    yang memuat 'demo'/'trial' diperlakukan sebagai DEMO agar tidak salah alarm.
    """
    t = str(type_str or "").strip().lower()
    srv = str(server or "").lower()
    if "demo" in srv or "trial" in srv:
        return "DEMO"
    if t == "contest" or "contest" in srv:
        return "CONTEST"
    if t == "demo":
        return "DEMO"
    if t == "real":
        return "REAL"
    return "?"


def map_timeframe_to_period(timeframe_str: str) -> str:
    """Petakan timeframe internal (mis. 'M5') ke string period MCP ('M5').

    Deterministik; default aman ke 'M5' bila tidak dikenal.
    """
    return _TIMEFRAME_TO_PERIOD.get(str(timeframe_str).upper(), "M5")


def candle_time_range(timeframe_str: str, count: int, now: Optional[datetime] = None) -> tuple[str, str]:
    """Hitung (datetime_from, datetime_to) ISO 8601 untuk mengambil `count` candle.

    datetime_to = now; datetime_from mundur sejauh menit_per_tf x count x buffer.
    Menjamin datetime_from < datetime_to untuk count >= 1.
    """
    if count < 1:
        count = 1
    now = now or datetime.now(timezone.utc)
    minutes = _TIMEFRAME_MINUTES.get(str(timeframe_str).upper(), 5)
    span_minutes = minutes * count * _RANGE_BUFFER
    dt_from = now - timedelta(minutes=span_minutes)
    return dt_from.isoformat(), now.isoformat()


import re


def candidate_symbol_variations(symbol: str) -> list[str]:
    """Hasilkan variasi nama simbol broker (Exness Standard 'm', Cent 'c', Pro/Raw polos, dsb).

    Contoh:
        'EURUSDm' -> ['EURUSDm', 'EURUSD', 'EURUSDc', 'EURUSD.pro', 'EURUSDpro', 'EURUSDraw', 'EURUSD.raw', 'EURUSDz', 'EURUSD_i']
        'EURUSD'  -> ['EURUSD', 'EURUSDm', 'EURUSDc', 'EURUSD.pro', 'EURUSDpro', 'EURUSDraw', 'EURUSD.raw', 'EURUSDz', 'EURUSD_i']
    """
    sym = str(symbol or "").strip()
    if not sym:
        return []
    candidates = [sym]
    # Ekstrak akar simbol tanpa suffix umum (m, c, pro, raw, z, _i, dll)
    root = re.sub(
        r"(\.pro|_pro|pro|\.raw|_raw|raw|\.z|_z|z|\.c|_c|c|\.m|_m|m|_i|\.i|\_sb|\.s|\.a|\+)$",
        "",
        sym,
        flags=re.IGNORECASE,
    )
    if not root:
        root = sym
    variants = [
        root,
        root + "m",        # Exness Standard (paling umum)
        root + "c",        # Exness Standard Cent
        root + ".pro",
        root + "pro",
        root + "raw",      # Exness Raw Spread
        root + ".raw",
        root + "z",        # Exness Zero
        root + "_i",
    ]
    for v in variants:
        if v not in candidates:
            candidates.append(v)
    return candidates


def resolve_symbol_name(requested_symbol: str, available_symbols: list[str]) -> Optional[str]:
    """Cocokkan simbol yang diminta dengan daftar simbol tersedia di broker.

    Menangani perbedaan suffix Exness (Standard 'm', Pro tanpa suffix, Cent 'c')
    dan case-insensitivity secara deterministik.
    """
    req_clean = str(requested_symbol or "").strip()
    if not req_clean or not available_symbols:
        return None
    # 1. Exact match langsung
    if req_clean in available_symbols:
        return req_clean
    avail_map = {s.upper(): s for s in available_symbols}
    # 2. Case-insensitive exact match
    if req_clean.upper() in avail_map:
        return avail_map[req_clean.upper()]
    # 3. Variasi kandidat suffix
    for cand in candidate_symbol_variations(req_clean):
        if cand in available_symbols:
            return cand
        if cand.upper() in avail_map:
            return avail_map[cand.upper()]
    # 4. Partial prefix match bila ada simbol berawalan root (mis. EURUSD.a)
    root = re.sub(
        r"(\.pro|_pro|pro|\.raw|_raw|raw|\.z|_z|z|\.c|_c|c|\.m|_m|m|_i|\.i|\_sb|\.s|\.a|\+)$",
        "",
        req_clean,
        flags=re.IGNORECASE,
    )
    if root:
        root_upper = root.upper()
        for s in available_symbols:
            if s.upper().startswith(root_upper) and len(s) <= len(root) + 5:
                return s
    return None


@runtime_checkable
class TradingBackend(Protocol):
    """Kontrak operasi MT5 yang dipakai bot (native atau MCP).

    Model data (dict ternormalisasi):
        Account   = {balance, equity, margin, free_margin, profit, currency,
                     trade_allowed: bool, server_connected: bool}
        SymbolSpec= {symbol, digits, point, volume_min, volume_max, volume_step,
                     tick_value, tick_size, stop_level}
        Tick      = {bid, ask, time}
        Position  = {ticket, symbol, type: 'BUY'|'SELL', volume, price_open,
                     price_current, sl, tp, profit, magic}
        Candle    = {t, o, h, l, c}
        Deal      = {ticket, time, symbol, magic, net_profit, profit}
        OrderResult = {ok: bool, ticket: int|None, message: str}
    """

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def account_info(self) -> Optional[dict]: ...
    def list_symbols(self, limit: int = 60) -> list: ...
    def symbol_spec(self, symbol: str) -> Optional[dict]: ...
    def resolve_symbol(self, symbol: str) -> Optional[str]: ...
    def ensure_symbol(self, symbol: str) -> bool: ...
    def get_rates(self, symbol: str, timeframe_str: str, count: int = 200): ...
    def get_tick(self, symbol: str) -> Optional[dict]: ...
    def spread_points(self, symbol: str) -> Optional[float]: ...
    def positions(self, symbol: Optional[str] = None) -> list: ...
    def history_deals(self, dt_from: datetime, dt_to: datetime) -> list: ...
    def send_market_order(self, symbol: str, side: str, volume: float,
                          sl: float = 0.0, tp: float = 0.0, magic: int = 0,
                          comment: str = "mt5bot") -> dict: ...
    def close_position(self, ticket: int, symbol: str) -> dict: ...
    def modify_sl_tp(self, ticket: int, symbol: str,
                     sl: Optional[float] = None, tp: Optional[float] = None) -> bool: ...
    def send_pending_order(self, symbol: str, order_type: str, volume: float,
                           price: float, sl: float = 0.0, tp: float = 0.0,
                           magic: int = 0, comment: str = "mt5bot") -> dict: ...
    def modify_pending_order(self, ticket: int, price: float,
                             sl: Optional[float] = None, tp: Optional[float] = None) -> dict: ...
    def delete_pending_order(self, ticket: int) -> dict: ...
    def pending_orders(self, symbol: Optional[str] = None) -> list: ...
