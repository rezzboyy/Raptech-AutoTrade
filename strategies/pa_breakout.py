from __future__ import annotations

"""
Raptech Autotrade CLI — Price Action Momentum Breakout Strategy (M1).
Universal scalper: Designed for Forex, Gold (XAUUSD), Crypto (BTC/ETH), and Cent accounts.
Zero-indicator, dimensionless ratio math, 100% immune to point/pip unit differences.
"""

from typing import List, Optional

from backend.base import Candle
from strategies import SIGNAL_BUY, SIGNAL_SELL, Strategy, register


@register
class PABreakoutScalper(Strategy):
    name = "pa_breakout"
    display_name = "Price Action Momentum Breakout (M1)"
    description = (
        "Universal M1 scalper capturing aggressive momentum breakouts past recent swing highs/lows "
        "with strong candle body dominance and minimal opposing wick rejection."
    )
    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 50.0          # Stop Loss Harian ($ USD) maksimal untuk strategi ini
    max_open_positions = 3         # Batas maksimal posisi terbuka bersamaan
    fixed_lot = 0.01              # Ukuran lot default
    default_sl_points = 150       # Stop Loss Virtual (points)
    default_tp_points = 250       # Take Profit Virtual (points)
    trailing_enabled = True       # Trailing Stop Aktif (True / False)
    trail_start_points = 80       # Profit (points) untuk mulai trailing
    trail_step_points = 30        # Langkah kenaikan trailing (points)
    symbols = ["XAUUSDm", "EURUSDm", "BTCUSDm"]
    timeframe = "M1"
    recommended_timeframe = "M1"
    risk_percent = 1.0
    sizing_mode = "fixed_lot"  # fixed_lot | risk_percent
    use_server_sl = False
    server_sl_points = 0
    max_drawdown_percent = 5.0
    min_margin_level = 500.0
    max_symbol_exposure_lots = 1.0
    allow_hedging = False
    close_on_opposite_signal = True
    auto_start = False

    PARAMS = [
        {"key": "lookback_bars", "label": "Lookback Swing Bars", "type": "int", "default": 6},
        {"key": "min_body_ratio", "label": "Min Body Ratio (0.0-1.0)", "type": "float", "default": 0.60},
        {"key": "max_rejection_wick", "label": "Max Head Wick Ratio", "type": "float", "default": 0.25},
        {"key": "volatility_filter", "label": "Filter Volatilitas (1=Aktif, 0=Non)", "type": "int", "default": 1},
    ]

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        # Need lookback bars + current + volatility window
        min_bars = max(self.lookback_bars + 2, 12)
        if len(candles) < min_bars:
            return None

        curr = candles[-1]
        total_range = curr.high - curr.low
        if total_range <= 0.0:
            return None

        body = abs(curr.close - curr.open)
        body_ratio = body / total_range

        # Require significant body mass (filter out dojis and indecision candles)
        if body_ratio < self.min_body_ratio:
            return None

        # Volatility check: Compare current bar range against recent average range
        if self.volatility_filter:
            recent_ranges = [(c.high - c.low) for c in candles[-11:-1]]
            avg_range = sum(recent_ranges) / max(len(recent_ranges), 1)
            # Must have at least 65% of average recent candle range to ensure momentum is real
            if avg_range > 0.0 and total_range < (avg_range * 0.65):
                return None

        # Recent swing reference window
        history = candles[-(self.lookback_bars + 1) : -1]
        highest_high = max(c.high for c in history)
        lowest_low = min(c.low for c in history)

        # 1. BULLISH BREAKOUT
        # Price closes strictly above recent highest high, candle is bullish,
        # and upper rejection wick is small (buyers finished in full control)
        if curr.close > highest_high and curr.close > curr.open:
            upper_wick = curr.high - curr.close
            if (upper_wick / total_range) <= self.max_rejection_wick:
                return SIGNAL_BUY

        # 2. BEARISH BREAKOUT
        # Price closes strictly below recent lowest low, candle is bearish,
        # and lower rejection wick is small (sellers finished in full control)
        if curr.close < lowest_low and curr.close < curr.open:
            lower_wick = curr.close - curr.low
            if (lower_wick / total_range) <= self.max_rejection_wick:
                return SIGNAL_SELL

        return None
