from __future__ import annotations

"""
Raptech Autotrade CLI — Persistent State Store (v3.0).
Provides crash-resilient, restart-persistent state management for:
- Virtual SL / TP and Trailing Stop states
- Daily Drawdown & Circuit Breaker locks
- High-Water Mark equity tracking
- Order reconciliation markers
Uses atomic file writing with schema versioning.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger("state_store")
STATE_FILE = Path("data/trading_state.json")
SCHEMA_VERSION = 3


@dataclass
class PersistedVirtualProtection:
    ticket: int
    symbol: str
    side: str
    price_open: float
    virtual_sl: float = 0.0
    virtual_tp: float = 0.0
    trailing_active: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class TradingStateData:
    schema_version: int = SCHEMA_VERSION
    profile_name: str = "default"
    trade_date: str = field(
        default_factory=lambda: date.today().isoformat()
    )
    daily_start_balance: float = 0.0
    high_water_mark_equity: float = 0.0
    circuit_breaker_tripped: bool = False
    circuit_breaker_reason: str = ""
    circuit_breaker_time: Optional[str] = None
    virtual_protections: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    reconciliation_required: bool = False
    reconciliation_reason: str = ""
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class StateStore:
    """Manages persistent disk state to survive application restarts and crashes."""

    def __init__(self, file_path: Path = STATE_FILE) -> None:
        self.file_path = file_path
        self._state: TradingStateData = self.load()

    @property
    def state(self) -> TradingStateData:
        return self._state

    def load(self) -> TradingStateData:
        """Load state from disk with safe recovery from corruption."""
        if not self.file_path.exists():
            return TradingStateData()

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            
            # Schema validation
            if not isinstance(raw, dict):
                logger.warning(f"State file {self.file_path} bukan JSON valid dictionary, reset ke state baru.")
                return TradingStateData()

            ver = raw.get("schema_version", 1)
            # Safe parsing
            return TradingStateData(
                schema_version=ver,
                profile_name=str(raw.get("profile_name", "default")),
                trade_date=str(raw.get("trade_date", date.today().isoformat())),
                daily_start_balance=float(raw.get("daily_start_balance", 0.0)),
                high_water_mark_equity=float(raw.get("high_water_mark_equity", 0.0)),
                circuit_breaker_tripped=bool(raw.get("circuit_breaker_tripped", False)),
                circuit_breaker_reason=str(raw.get("circuit_breaker_reason", "")),
                circuit_breaker_time=raw.get("circuit_breaker_time"),
                virtual_protections=dict(raw.get("virtual_protections", {})),
                reconciliation_required=bool(raw.get("reconciliation_required", False)),
                reconciliation_reason=str(raw.get("reconciliation_reason", "")),
                last_updated=str(raw.get("last_updated", "")),
            )
        except Exception as exc:
            logger.error(f"Gagal memuat state dari {self.file_path}: {exc}. Mengamankan backup...")
            # Backup corrupted file
            try:
                corrupt_bak = self.file_path.with_suffix(".corrupt.bak")
                if self.file_path.exists():
                    os.replace(self.file_path, corrupt_bak)
            except Exception:
                pass
            return TradingStateData()

    def save(self) -> None:
        """Atomically commit current state to disk."""
        self._state.last_updated = datetime.now(timezone.utc).isoformat()
        data = asdict(self._state)

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_name = tempfile.mkstemp(
            dir=self.file_path.parent, prefix="state_", suffix=".tmp"
        )
        try:
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_name, self.file_path)
        except Exception as exc:
            if os.path.exists(temp_name):
                try:
                    os.remove(temp_name)
                except Exception:
                    pass
            logger.error(f"Gagal menyimpan persistent state: {exc}")
            raise exc

    def record_circuit_breaker(self, tripped: bool, reason: str = "") -> None:
        self._state.circuit_breaker_tripped = tripped
        self._state.circuit_breaker_reason = reason
        self._state.circuit_breaker_time = (
            datetime.now(timezone.utc).isoformat() if tripped else None
        )
        self.save()

    def update_daily_metrics(
        self, today_str: str, start_balance: float, current_equity: float
    ) -> None:
        if self._state.trade_date != today_str:
            self._state.trade_date = today_str
            self._state.daily_start_balance = start_balance
            self._state.high_water_mark_equity = max(start_balance, current_equity)
            # Only reset circuit breaker if it was from a previous day
            if self._state.circuit_breaker_tripped:
                logger.info(f"Reset harian pergantian tanggal: {today_str}")
                self._state.circuit_breaker_tripped = False
                self._state.circuit_breaker_reason = ""
                self._state.circuit_breaker_time = None
        else:
            if current_equity > self._state.high_water_mark_equity:
                self._state.high_water_mark_equity = current_equity
            if self._state.daily_start_balance <= 0.0 and start_balance > 0.0:
                self._state.daily_start_balance = start_balance

        self.save()

    def set_virtual_protection(self, prot: PersistedVirtualProtection) -> None:
        prot.updated_at = datetime.now(timezone.utc).isoformat()
        self._state.virtual_protections[str(prot.ticket)] = asdict(prot)
        self.save()

    def remove_virtual_protection(self, ticket: int) -> None:
        key = str(ticket)
        if key in self._state.virtual_protections:
            del self._state.virtual_protections[key]
            self.save()

    def set_reconciliation_required(self, required: bool, reason: str = "") -> None:
        self._state.reconciliation_required = required
        self._state.reconciliation_reason = reason
        self.save()
