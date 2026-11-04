from __future__ import annotations

"""
Raptech Autotrade CLI — Brutal Cent Scalper (100% Self-Contained Standalone File).
Semua parameter, rumus indikator, dan logika eksekusi berada di dalam file ini.
"""

from typing import Any, Dict, List, Optional

from backend.base import Candle
from strategies import Strategy, register

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"


# ---------------------------------------------------------------------------
# Rumus Indikator Mandiri (EMA & RSI)
# ---------------------------------------------------------------------------
def _calc_ema(values: List[float], period: int) -> List[Optional[float]]:
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


def _calc_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
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


# ---------------------------------------------------------------------------
# Kelas Strategi Mandiri
# ---------------------------------------------------------------------------
@register
class BrutalCentScalper(Strategy):
    name = "brutal_cent_scalper"
    display_name = "Brutal Cent Scalper"
    description = "High-frequency scalper designed for Cent/Standard forex pairs on M1 targeting quick moves."

    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 30.0          # Stop Loss Harian ($ USD) maksimal untuk strategi ini
    max_open_positions = 5         # Batas maksimal posisi terbuka bersamaan
    fixed_lot = 0.05              # Ukuran lot default
    default_sl_points = 100       # Stop Loss Virtual (points)
    default_tp_points = 150       # Take Profit Virtual (points)
    trailing_enabled = True       # Trailing Stop Aktif (True / False)
    trail_start_points = 50       # Profit (points) untuk mulai trailing
    trail_step_points = 20        # Langkah kenaikan trailing (points)
    symbols = ["EURUSDm", "EURUSDc", "GBPUSDm", "USDJPYm", "XAUUSDm"]
    timeframe = "M1"
    recommended_timeframe = "M1"
    risk_percent = 1.0
    sizing_mode = "fixed_lot"
    use_server_sl = False
    server_sl_points = 0
    max_drawdown_percent = 5.0
    min_margin_level = 500.0
    max_symbol_exposure_lots = 1.0
    allow_hedging = False
    close_on_opposite_signal = True
    auto_start = False

    PARAMS = [
        {"key": "fast_period", "label": "EMA Cepat", "type": "int", "default": 5},
        {"key": "slow_period", "label": "EMA Lambat", "type": "int", "default": 13},
        {"key": "rsi_period", "label": "RSI Filter", "type": "int", "default": 7},
        {"key": "rsi_oversold", "label": "RSI Oversold", "type": "float", "default": 30.0},
        {"key": "rsi_overbought", "label": "RSI Overbought", "type": "float", "default": 70.0},
    ]

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        if len(candles) < self.slow_period + 3:
            return None

        closes = [c.close for c in candles]
        fast = _calc_ema(closes, self.fast_period)
        slow = _calc_ema(closes, self.slow_period)
        r = _calc_rsi(closes, self.rsi_period)

        if fast[-1] is None or slow[-1] is None or r[-1] is None or fast[-2] is None or slow[-2] is None:
            return None

        # Fast momentum scalp
        if fast[-2] <= slow[-2] and fast[-1] > slow[-1] and r[-1] < self.rsi_overbought:
            return SIGNAL_BUY
        elif fast[-2] >= slow[-2] and fast[-1] < slow[-1] and r[-1] > self.rsi_oversold:
            return SIGNAL_SELL

        return None
