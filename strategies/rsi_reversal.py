from __future__ import annotations

"""
Raptech Autotrade CLI — RSI Reversal Strategy (100% Self-Contained Standalone File).
Semua parameter, rumus kalkulasi RSI, dan logika eksekusi berada di dalam file ini.
"""

from typing import Any, Dict, List, Optional

from backend.base import Candle
from strategies import Strategy, register

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"


# ---------------------------------------------------------------------------
# Rumus Indikator Mandiri (RSI)
# ---------------------------------------------------------------------------
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
class RSIReversal(Strategy):
    name = "rsi_reversal"
    display_name = "RSI Reversal"
    description = "Detects extreme overbought and oversold conditions with confirmation bounce on M5."

    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 50.0          # Stop Loss Harian ($ USD) maksimal untuk strategi ini
    max_open_positions = 2         # Batas maksimal posisi terbuka bersamaan
    fixed_lot = 0.01              # Ukuran lot default
    default_sl_points = 250       # Stop Loss Virtual (points)
    default_tp_points = 500       # Take Profit Virtual (points)
    trailing_enabled = True       # Trailing Stop Aktif (True / False)
    trail_start_points = 120      # Profit (points) untuk mulai trailing
    trail_step_points = 40        # Langkah kenaikan trailing (points)
    symbols = ["EURUSDm", "GBPUSDm", "AUDUSDm", "XAUUSDm"]
    timeframe = "M5"
    recommended_timeframe = "M5"
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
        {"key": "period", "label": "Periode RSI", "type": "int", "default": 14},
        {"key": "oversold", "label": "Oversold Level", "type": "float", "default": 30.0},
        {"key": "overbought", "label": "Overbought Level", "type": "float", "default": 70.0},
    ]

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        if len(candles) < self.period + 3:
            return None

        closes = [c.close for c in candles]
        r = _calc_rsi(closes, self.period)

        if r[-1] is None or r[-2] is None:
            return None

        # Cross back up above oversold
        if r[-2] < self.oversold and r[-1] >= self.oversold:
            return SIGNAL_BUY
        # Cross back down below overbought
        elif r[-2] > self.overbought and r[-1] <= self.overbought:
            return SIGNAL_SELL

        return None
