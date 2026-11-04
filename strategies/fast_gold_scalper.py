from __future__ import annotations

"""
Raptech Autotrade CLI — Fast Gold Scalper (100% Self-Contained Standalone File).
Semua parameter, rumus indikator EMA & RSI, serta logika eksekusi berada di dalam file ini.
"""

from typing import Any, Dict, List, Optional

from backend.base import Candle
from strategies import Strategy, register

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"


# ---------------------------------------------------------------------------
# Rumus Indikator Mandiri (Pure Python, Zero External Dependencies)
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
class FastGoldScalper(Strategy):
    name = "fast_gold_scalper"
    display_name = "Fast Gold Scalper (XAUUSD)"
    description = "Optimized for Gold (XAUUSD) on M1/M5 with multi-EMA alignment and RSI momentum."

    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 50.0          # Stop Loss Harian ($ USD) maksimal untuk strategi ini
    max_open_positions = 2         # Batas maksimal posisi terbuka bersamaan
    fixed_lot = 0.02              # Ukuran lot default
    default_sl_points = 200       # Stop Loss Virtual (points)
    default_tp_points = 400       # Take Profit Virtual (points)
    trailing_enabled = True       # Trailing Stop Aktif (True / False)
    trail_start_points = 150      # Profit (points) untuk mulai trailing
    trail_step_points = 50        # Langkah kenaikan trailing (points)
    symbols = ["XAUUSDm", "XAUUSD", "GOLD"]
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

    # Parameter Indikator
    PARAMS = [
        {"key": "fast_ema", "label": "EMA Cepat", "type": "int", "default": 9},
        {"key": "slow_ema", "label": "EMA Lambat", "type": "int", "default": 21},
        {"key": "trend_ema", "label": "EMA Tren", "type": "int", "default": 50},
        {"key": "rsi_period", "label": "Periode RSI", "type": "int", "default": 14},
        {"key": "rsi_buy_level", "label": "RSI Min Buy", "type": "float", "default": 48.0},
        {"key": "rsi_sell_level", "label": "RSI Max Sell", "type": "float", "default": 52.0},
    ]

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        if len(candles) < max(self.trend_ema, self.rsi_period) + 3:
            return None

        closes = [c.close for c in candles]
        fast_emas = _calc_ema(closes, self.fast_ema)
        slow_emas = _calc_ema(closes, self.slow_ema)
        trend_emas = _calc_ema(closes, self.trend_ema)
        rsis = _calc_rsi(closes, self.rsi_period)

        # Evaluasi candle tertutup terakhir (-2 dan -1)
        prev_fast = fast_emas[-2]
        prev_slow = slow_emas[-2]
        curr_fast = fast_emas[-1]
        curr_slow = slow_emas[-1]
        curr_trend = trend_emas[-1]
        curr_rsi = rsis[-1]

        if any(v is None for v in (prev_fast, prev_slow, curr_fast, curr_slow, curr_trend, curr_rsi)):
            return None

        # BUY Condition: Fast EMA melintas di atas Slow EMA, harga di atas Trend EMA, RSI >= 48
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            if closes[-1] > curr_trend and curr_rsi >= self.rsi_buy_level:
                return SIGNAL_BUY

        # SELL Condition: Fast EMA melintas di bawah Slow EMA, harga di bawah Trend EMA, RSI <= 52
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            if closes[-1] < curr_trend and curr_rsi <= self.rsi_sell_level:
                return SIGNAL_SELL

        return None
