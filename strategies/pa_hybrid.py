from __future__ import annotations

"""
Raptech Autotrade CLI — Price Action Hybrid Scalper (M1).
Master multi-regime scalper: Seamlessly unifies Momentum Breakout, Pin Bar Rejection,
and Bullish/Bearish Engulfing patterns.
Fully market-agnostic (Gold, Forex, Cent, Crypto).
"""

from typing import List, Optional

from backend.base import Candle
from strategies import SIGNAL_BUY, SIGNAL_SELL, Strategy, register
from strategies.pa_breakout import PABreakoutScalper
from strategies.pa_rejection import PARejectionScalper


@register
class PAHybridScalper(Strategy):
    name = "pa_hybrid"
    display_name = "Price Action Hybrid Scalper (M1)"
    description = (
        "Master M1 scalper combining Momentum Breakouts, Pin Bar Rejections, "
        "and Engulfing Impulses into a unified, high-frequency, all-market system."
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
        {"key": "enable_breakout", "label": "Aktifkan Breakout (1=Ya, 0=Tidak)", "type": "int", "default": 1},
        {"key": "enable_rejection", "label": "Aktifkan Rejection (1=Ya, 0=Tidak)", "type": "int", "default": 1},
        {"key": "enable_engulfing", "label": "Aktifkan Engulfing (1=Ya, 0=Tidak)", "type": "int", "default": 1},
        {"key": "lookback_bars", "label": "Lookback Swing Bars", "type": "int", "default": 6},
        {"key": "volatility_filter", "label": "Filter Volatilitas (1=Ya, 0=Tidak)", "type": "int", "default": 1},
    ]

    def __init__(self, **params) -> None:
        super().__init__(**params)
        # Sub-strategy delegates
        self._breakout_strat = PABreakoutScalper(
            lookback_bars=self.lookback_bars,
            volatility_filter=self.volatility_filter,
        )
        self._rejection_strat = PARejectionScalper(
            lookback_bars=self.lookback_bars,
            volatility_filter=self.volatility_filter,
        )

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        if len(candles) < max(self.lookback_bars + 3, 12):
            return None

        # 1. EVALUATE PIN BAR REJECTION (Highest priority: early entry at extreme turning points)
        if self.enable_rejection:
            sig = self._rejection_strat.generate_signal(candles)
            if sig in (SIGNAL_BUY, SIGNAL_SELL):
                return sig

        # 2. EVALUATE MOMENTUM BREAKOUT (Fast trend continuation impulse)
        if self.enable_breakout:
            sig = self._breakout_strat.generate_signal(candles)
            if sig in (SIGNAL_BUY, SIGNAL_SELL):
                return sig

        # 3. EVALUATE ENGULFING IMPULSE (Powerful 2-bar sentiment shift)
        if self.enable_engulfing:
            curr = candles[-1]
            prev = candles[-2]

            curr_range = curr.high - curr.low
            prev_range = prev.high - prev.low
            if curr_range <= 0.0 or prev_range <= 0.0:
                return None

            curr_body = abs(curr.close - curr.open)
            prev_body = abs(prev.close - prev.open)

            # Volatility check
            if self.volatility_filter:
                recent_ranges = [(c.high - c.low) for c in candles[-11:-1]]
                avg_range = sum(recent_ranges) / max(len(recent_ranges), 1)
                if avg_range > 0.0 and curr_range < (avg_range * 0.70):
                    return None

            # Bullish Engulfing:
            # Prev was red, curr is green, curr body engulfs previous body and body ratio >= 60%
            if (
                prev.close < prev.open
                and curr.close > curr.open
                and curr.close > prev.open
                and curr.open <= prev.close
                and curr_body >= (prev_body * 1.15)
                and (curr_body / curr_range) >= 0.60
            ):
                return SIGNAL_BUY

            # Bearish Engulfing:
            # Prev was green, curr is red, curr body engulfs previous body and body ratio >= 60%
            if (
                prev.close > prev.open
                and curr.close < curr.open
                and curr.close < prev.open
                and curr.open >= prev.close
                and curr_body >= (prev_body * 1.15)
                and (curr_body / curr_range) >= 0.60
            ):
                return SIGNAL_SELL

        return None
