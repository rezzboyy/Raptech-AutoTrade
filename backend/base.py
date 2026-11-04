from __future__ import annotations

"""
Raptech Autotrade CLI — Backend Abstraction & Data Models.
Standardized interface for both Native MT5 (IPC) and MCP (JSON-RPC) backends.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Standard timeframe mapping
TIMEFRAME_TO_PERIOD: Dict[str, str] = {
    "M1": "M1",
    "M5": "M5",
    "M15": "M15",
    "M30": "M30",
    "H1": "H1",
    "H4": "H4",
    "D1": "D1",
}

TIMEFRAME_MINUTES: Dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}

PENDING_ORDER_TYPES = ("buy_limit", "sell_limit", "buy_stop", "sell_stop")


@dataclass
class AccountInfo:
    login: int = 0
    server: str = ""
    currency: str = "USD"
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    profit: float = 0.0
    trade_allowed: bool = False
    server_connected: bool = False
    account_type: str = "DEMO"  # DEMO | REAL | CONTEST | DEMO (CENT) | REAL (CENT)
    leverage: int = 100
    is_cent: bool = False
    algo_trading_allowed: bool = True


@dataclass
class Position:
    ticket: int
    symbol: str
    type: str  # BUY | SELL
    volume: float
    price_open: float
    price_current: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    magic: int = 0
    comment: str = ""
    time: Optional[datetime] = None
    virtual_sl: float = 0.0
    virtual_tp: float = 0.0


@dataclass
class SymbolSpec:
    symbol: str
    digits: int = 5
    point: float = 0.00001
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    tick_value: float = 1.0
    tick_size: float = 0.00001
    stop_level: int = 0


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0


@dataclass
class Tick:
    bid: float
    ask: float
    time: datetime
    last: float = 0.0
    volume: int = 0


class OrderState:
    """Explicit Order State Machine for execution reliability & reconciliation."""
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass
class OrderResult:
    ok: bool
    ticket: Optional[int] = None
    order: Optional[int] = None
    message: str = ""
    retcode: int = 0
    price: float = 0.0
    volume: float = 0.0
    state: str = OrderState.FILLED
    operation_id: Optional[str] = None


def classify_account_type(type_val: Any, server: str, currency: str = "") -> str:
    """Classify official account type: 'DEMO' | 'REAL' | 'CONTEST' | 'REAL (CENT)' | 'DEMO (CENT)'."""
    srv = str(server or "").lower()
    curr = str(currency or "").strip().upper()
    t_str = str(type_val).strip().lower() if type_val is not None else ""

    is_cent = (
        "cent" in srv
        or curr in ("USC", "USCC", "EUC", "EUCC", "GBC", "GBCC", "USDCENT", "EURCENT")
        or (curr.endswith("C") and len(curr) == 4 and curr != "BTCC")
    )

    base_type = "DEMO"
    if "demo" in srv or "trial" in srv or "practice" in srv or "sandbox" in srv:
        base_type = "DEMO"
    elif "contest" in srv or t_str in ("1", "contest"):
        base_type = "CONTEST"
    elif t_str in ("0", "demo", "demo_account"):
        base_type = "DEMO"
    elif t_str in ("2", "real", "live") or "real" in srv or "live" in srv or "prod" in srv:
        base_type = "REAL"
    elif t_str == "real":
        base_type = "REAL"
    else:
        base_type = "REAL" if ("real" in srv or "live" in srv) else "DEMO"

    if is_cent:
        return f"{base_type} (CENT)"
    return base_type


def map_timeframe_to_period(timeframe_str: str) -> str:
    """Map internal timeframe string to standard period string."""
    return TIMEFRAME_TO_PERIOD.get(str(timeframe_str).upper(), "M5")


def candidate_symbol_variations(symbol: str) -> List[str]:
    """Generate broker symbol variations (e.g., EURUSDm, EURUSDc, EURUSD.pro, etc.)."""
    sym = str(symbol or "").strip()
    if not sym:
        return []
    candidates = [sym]
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
        root + "m",        # Exness Standard
        root + "c",        # Exness Cent
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


def resolve_symbol_name(requested_symbol: str, available_symbols: List[str]) -> Optional[str]:
    """Match requested symbol against broker's available symbols."""
    req_clean = str(requested_symbol or "").strip()
    if not req_clean or not available_symbols:
        return None
    if req_clean in available_symbols:
        return req_clean
    avail_map = {s.upper(): s for s in available_symbols}
    if req_clean.upper() in avail_map:
        return avail_map[req_clean.upper()]
    for cand in candidate_symbol_variations(req_clean):
        if cand in available_symbols:
            return cand
        if cand.upper() in avail_map:
            return avail_map[cand.upper()]
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
    """Trading Backend Protocol Interface."""

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def account_info(self) -> Optional[AccountInfo]: ...
    def list_symbols(self, limit: int = 60) -> List[str]: ...
    def symbol_spec(self, symbol: str) -> Optional[SymbolSpec]: ...
    def resolve_symbol(self, symbol: str) -> Optional[str]: ...
    def ensure_symbol(self, symbol: str) -> bool: ...
    def get_candles(self, symbol: str, timeframe_str: str, count: int = 200) -> List[Candle]: ...
    def get_tick(self, symbol: str) -> Optional[Tick]: ...
    def spread_points(self, symbol: str) -> Optional[float]: ...
    def positions(self, symbol: Optional[str] = None) -> List[Position]: ...
    def send_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "raptech_cli",
    ) -> OrderResult: ...
    def close_position(self, ticket: int, symbol: str, volume: Optional[float] = None) -> OrderResult: ...
    def modify_sl_tp(
        self, ticket: int, symbol: str, sl: Optional[float] = None, tp: Optional[float] = None
    ) -> bool: ...
    def send_pending_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "raptech_cli",
    ) -> OrderResult: ...
    def delete_pending_order(self, ticket: int) -> OrderResult: ...
