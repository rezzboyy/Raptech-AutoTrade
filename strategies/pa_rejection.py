from __future__ import annotations

"""
Raptech Autotrade CLI — Price Action Pin Bar Rejection Strategy (M1).
Universal scalper: Captures swift reversals at swing boundaries using hammer and shooting star wicks.
100% indicator-free, dimensionless proportions, fully market-agnostic.
"""

from typing import List, Optional

from backend.base import Candle
from strategies import SIGNAL_BUY, SIGNAL_SELL, Strategy, register


@register
class PARejectionScalper(Strategy):
    name = "pa_rejection"
    display_name = "Price Action Pin Bar Rejection (M1)"
    description = (
        "Universal M1 scalper capturing immediate trend reversals at extreme swing levels "
        "using long rejecting tails (Hammers & Shooting Stars) with high risk-to-reward."
    )
    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 50.0          # Stop Loss Harian ($ USD) maksimal untuk strategi ini
    max_open_positions = 3         # Batas maksimal posisi terbuka bersamaan
    fixed_lot = 0.01              # Ukuran lot default
    default_sl_points = 120       # Stop Loss Virtual (points)
    default_tp_points = 200       # Take Profit Virtual (points)
    trailing_enabled = True       # Trailing Stop Aktif (True / False)
    trail_start_points = 60       # Profit (points) untuk mulai trailing
    trail_step_points = 25        # Langkah kenaikan trailing (points)
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
        {"key": "lookback_bars", "label": "Lookback Swing Bars", "type": "int", "default": 8},
        {"key": "min_wick_ratio", "label": "Min Tail Ratio (0.0-1.0)", "type": "float", "default": 0.50},
        {"key": "wick_to_body_ratio", "label": "Min Tail-to-Body Multiplier", "type": "float", "default": 2.0},
        {"key": "max_opposing_wick", "label": "Max Opposing Nose Ratio", "type": "float", "default": 0.20},
        {"key": "volatility_filter", "label": "Filter Volatilitas (1=Aktif, 0=Non)", "type": "int", "default": 1},
    ]

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        min_bars = max(self.lookback_bars + 2, 12)
        if len(candles) < min_bars:
            return None

        curr = candles[-1]
        total_range = curr.high - curr.low
        if total_range <= 0.0:
            return None

        body = abs(curr.close - curr.open)
        body_top = max(curr.open, curr.close)
        body_bottom = min(curr.open, curr.close)

        upper_wick = curr.high - body_top
        lower_wick = body_bottom - curr.low

        # Volatility check: Prevent micro-wicks during dormant quiet sessions
        if self.volatility_filter:
            recent_ranges = [(c.high - c.low) for c in candles[-11:-1]]
            avg_range = sum(recent_ranges) / max(len(recent_ranges), 1)
            if avg_range > 0.0 and total_range < (avg_range * 0.50):
                return None

        history = candles[-(self.lookback_bars + 1) : -1]
        recent_low = min(c.low for c in history)
        recent_high = max(c.high for c in history)

        # 1. BULLISH PIN BAR (HAMMER / BOTTOM REJECTION)
        # Criteria:
        # - Long lower tail (>= min_wick_ratio of total candle)
        # - Tail at least wick_to_body_ratio times the real body
        # - Tiny or negligible upper wick (opposing nose <= max_opposing_wick)
        # - The tail dipped to or pierced recent swing low (liquidity sweep / test)
        lower_wick_ratio = lower_wick / total_range
        upper_wick_ratio = upper_wick / total_range
        body_threshold = max(body, total_range * 0.05)  # Guard against zero-body doji division

        if (
            lower_wick_ratio >= self.min_wick_ratio
            and lower_wick >= (body_threshold * self.wick_to_body_ratio)
            and upper_wick_ratio <= self.max_opposing_wick
            and curr.low <= recent_low
        ):
            return SIGNAL_BUY

        # 2. BEARISH PIN BAR (SHOOTING STAR / TOP REJECTION)
        # Criteria:
        # - Long upper tail (>= min_wick_ratio of total candle)
        # - Tail at least wick_to_body_ratio times the real body
        # - Tiny or negligible lower wick (opposing nose <= max_opposing_wick)
        # - The tail pierced or tested recent swing high
        if (
            upper_wick_ratio >= self.min_wick_ratio
            and upper_wick >= (body_threshold * self.wick_to_body_ratio)
            and lower_wick_ratio <= self.max_opposing_wick
            and curr.high >= recent_high
        ):
            return SIGNAL_SELL

        return None
