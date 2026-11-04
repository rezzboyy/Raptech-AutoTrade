from __future__ import annotations

"""
Raptech Autotrade CLI — Strategies Package.
Manages strategy registry and core signal constants.
All strategies are 100% self-contained inside their own files.
"""

from typing import Any, Dict, List, Optional

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"

_REGISTRY: Dict[str, type] = {}


def register(cls: type) -> type:
    """Decorator to register a trading strategy."""
    _REGISTRY[cls.name] = cls
    return cls


def get_registry() -> Dict[str, type]:
    """Return dictionary of all registered strategies."""
    return dict(_REGISTRY)


# ---------------------------------------------------------------------------
# Generic Lightweight Strategy Base Class
# ---------------------------------------------------------------------------
class Strategy:
    """Lightweight strategy base supporting dynamic parameter resolution."""
    name: str = "base"
    display_name: str = "Base Strategy"
    description: str = ""
    recommended_timeframe: str = "M5"
    timeframe: str = "M5"
    symbols: List[str] = ["XAUUSDm", "EURUSDm", "BTCUSDm"]
    recommended_symbols: List[str] = ["XAUUSDm", "EURUSDm", "BTCUSDm"]

    fixed_lot: float = 0.01
    risk_percent: float = 1.0
    sizing_mode: str = "fixed_lot"
    default_sl_points: int = 150
    default_tp_points: int = 250
    trailing_enabled: bool = True
    trail_start_points: int = 100
    trail_step_points: int = 50
    use_server_sl: bool = False
    server_sl_points: int = 0
    max_daily_loss: float = 50.0
    max_open_positions: int = 3
    max_drawdown_percent: float = 5.0
    min_margin_level: float = 500.0
    max_symbol_exposure_lots: float = 1.0
    allow_hedging: bool = False
    close_on_opposite_signal: bool = True
    auto_start: bool = False

    PARAMS: List[Dict[str, Any]] = []

    def __init__(self, **params: Any) -> None:
        self.params = self.resolve_params(params)
        for k, v in self.params.items():
            setattr(self, k, v)
        # Dukungan penyesuaian risiko & batasan posisi per strategi secara dinamis
        for risk_key in (
            "max_daily_loss", "max_open_positions", "fixed_lot", "risk_percent",
            "sizing_mode", "default_sl_points", "default_tp_points",
            "trailing_enabled", "trail_start_points", "trail_step_points",
            "use_server_sl", "server_sl_points", "allow_hedging", "close_on_opposite_signal"
        ):
            if risk_key in params:
                val = params[risk_key]
                t = float if "loss" in risk_key or "lot" in risk_key or "percent" in risk_key else (
                    bool if "enabled" in risk_key or "server_sl" in risk_key or "hedging" in risk_key or "opposite" in risk_key else int
                )
                try:
                    setattr(self, risk_key, t(val))
                except Exception:
                    setattr(self, risk_key, val)

    def get_risk_settings(self) -> Any:
        from core.config_store import RiskSettings
        return RiskSettings(
            fixed_lot=getattr(self, "fixed_lot", 0.01),
            risk_percent=getattr(self, "risk_percent", 1.0),
            sizing_mode=getattr(self, "sizing_mode", "fixed_lot"),
            virtual_sl_points=getattr(self, "default_sl_points", 150),
            virtual_tp_points=getattr(self, "default_tp_points", 250),
            use_server_sl=getattr(self, "use_server_sl", False),
            server_sl_points=getattr(self, "server_sl_points", 0),
            trailing_enabled=getattr(self, "trailing_enabled", True),
            trail_start_points=getattr(self, "trail_start_points", 100),
            trail_step_points=getattr(self, "trail_step_points", 50),
            max_daily_loss=getattr(self, "max_daily_loss", 50.0),
            max_open_positions=getattr(self, "max_open_positions", 3),
            max_drawdown_percent=getattr(self, "max_drawdown_percent", 5.0),
            min_margin_level=getattr(self, "min_margin_level", 500.0),
            max_symbol_exposure_lots=getattr(self, "max_symbol_exposure_lots", 1.0),
        )

    @classmethod
    def resolve_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        resolved = {}
        for spec in getattr(cls, "PARAMS", []):
            k = spec["key"]
            val = params.get(k, spec["default"])
            resolved[k] = int(val) if spec["type"] == "int" else float(val)
        return resolved

    def generate_signal(self, candles: list) -> Optional[str]:
        return None


# ---------------------------------------------------------------------------
# General Indicator Math (Optional Utilities)
# ---------------------------------------------------------------------------
def sma(values: List[float], period: int) -> List[Optional[float]]:
    if len(values) < period or period < 1:
        return [None] * len(values)
    res: List[Optional[float]] = [None] * (period - 1)
    rolling_sum = sum(values[:period])
    res.append(rolling_sum / period)
    for i in range(period, len(values)):
        rolling_sum += values[i] - values[i - period]
        res.append(rolling_sum / period)
    return res


def ema(values: List[float], period: int) -> List[Optional[float]]:
    if len(values) < period or period < 1:
        return [None] * len(values)
    res: List[Optional[float]] = [None] * (period - 1)
    multiplier = 2.0 / (period + 1.0)
    current_ema = sum(values[:period]) / period
    res.append(current_ema)
    for i in range(period, len(values)):
        current_ema = (values[i] - current_ema) * multiplier + current_ema
        res.append(current_ema)
    return res


def rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    if len(prices) <= period or period < 1:
        return [None] * len(prices)
    res: List[Optional[float]] = [None] * period

    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0.0:
        res.append(100.0)
    else:
        rs = avg_gain / avg_loss
        res.append(100.0 - (100.0 / (1.0 + rs)))

    for i in range(period + 1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gain = max(0.0, diff)
        loss = max(0.0, -diff)

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0.0:
            res.append(100.0)
        else:
            rs = avg_gain / avg_loss
            res.append(100.0 - (100.0 / (1.0 + rs)))

    return res


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[Optional[float]]:
    if len(closes) <= period or period < 1:
        return [None] * len(closes)
    tr_list = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr_list.append(max(hl, hc, lc))

    res: List[Optional[float]] = [None] * (period - 1)
    current_atr = sum(tr_list[:period]) / period
    res.append(current_atr)

    for i in range(period, len(closes)):
        current_atr = (current_atr * (period - 1) + tr_list[i]) / period
        res.append(current_atr)

    return res


# ---------------------------------------------------------------------------
# Katalog Strategi Bawaan Mandiri
# ---------------------------------------------------------------------------
from strategies.fast_gold_scalper import FastGoldScalper
from strategies.brutal_cent_scalper import BrutalCentScalper
from strategies.ma_cross import MACross
from strategies.rsi_reversal import RSIReversal
from strategies.pa_breakout import PABreakoutScalper
from strategies.pa_rejection import PARejectionScalper
from strategies.pa_hybrid import PAHybridScalper

__all__ = [
    "Strategy",
    "register",
    "get_registry",
    "SIGNAL_BUY",
    "SIGNAL_SELL",
    "SIGNAL_HOLD",
    "sma",
    "ema",
    "rsi",
    "atr",
    "FastGoldScalper",
    "BrutalCentScalper",
    "MACross",
    "RSIReversal",
    "PABreakoutScalper",
    "PARejectionScalper",
    "PAHybridScalper",
]
