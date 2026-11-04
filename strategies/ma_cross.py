from __future__ import annotations

"""
Raptech Autotrade CLI — Moving Average Cross Strategy (100% Self-Contained Standalone File).
Semua parameter, rumus kalkulasi SMA, dan logika eksekusi berada di dalam file ini.
"""

from typing import Any, Dict, List, Optional

from backend.base import Candle
from strategies import Strategy, register

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"


# ---------------------------------------------------------------------------
# Rumus Indikator Mandiri (Simple Moving Average)
# ---------------------------------------------------------------------------
def _calc_sma(values: List[float], period: int) -> List[Optional[float]]:
    if len(values) < period or period < 1:
        return [None] * len(values)
    res: List[Optional[float]] = [None] * (period - 1)
    rolling_sum = sum(values[:period])
    res.append(rolling_sum / period)
    for i in range(period, len(values)):
        rolling_sum += values[i] - values[i - period]
        res.append(rolling_sum / period)
    return res


# ---------------------------------------------------------------------------
# Kelas Strategi Mandiri
# ---------------------------------------------------------------------------
@register
class MACross(Strategy):
    name = "ma_cross"
    display_name = "Moving Average Cross"
    description = "Classic moving average crossover system on M15/H1 for swing trend continuation."

    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 50.0          # Stop Loss Harian ($ USD) maksimal untuk strategi ini
    max_open_positions = 2         # Batas maksimal posisi terbuka bersamaan
    fixed_lot = 0.01              # Ukuran lot default
    default_sl_points = 300       # Stop Loss Virtual (points)
    default_tp_points = 600       # Take Profit Virtual (points)
    trailing_enabled = True       # Trailing Stop Aktif (True / False)
    trail_start_points = 150      # Profit (points) untuk mulai trailing
    trail_step_points = 50        # Langkah kenaikan trailing (points)
    symbols = ["EURUSDm", "GBPUSDm", "USDJPYm", "XAUUSDm"]
    timeframe = "M15"
    recommended_timeframe = "M15"
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
        {"key": "fast_period", "label": "MA Cepat", "type": "int", "default": 10},
        {"key": "slow_period", "label": "MA Lambat", "type": "int", "default": 20},
    ]

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        if len(candles) < self.slow_period + 2:
            return None

        closes = [c.close for c in candles]
        fast = _calc_sma(closes, self.fast_period)
        slow = _calc_sma(closes, self.slow_period)

        if fast[-1] is None or slow[-1] is None or fast[-2] is None or slow[-2] is None:
            return None

        if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
            return SIGNAL_BUY
        elif fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
            return SIGNAL_SELL

        return None
