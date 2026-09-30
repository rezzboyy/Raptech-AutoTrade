"""Strategi Moving Average Crossover (dua SMA)."""

import pandas as pd

from strategies.base import Strategy, register, series_to_points, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

logger = get_logger("mt5bot")


@register
class MovingAverageCrossStrategy(Strategy):
    """Crossover dua Simple Moving Average.

    - BUY  saat MA cepat memotong ke atas MA lambat.
    - SELL saat MA cepat memotong ke bawah MA lambat.
    """

    name = "ma_cross"
    display_name = "MA Crossover"
    PARAMS = [
        {"key": "fast_period", "label": "MA Cepat", "type": "int", "default": 10, "min": 1},
        {"key": "slow_period", "label": "MA Lambat", "type": "int", "default": 30, "min": 2},
    ]

    @classmethod
    def extra_validate(cls, params: dict) -> list:
        try:
            fast = int(params.get("fast_period", 10))
            slow = int(params.get("slow_period", 30))
            if fast >= slow:
                return ["MA Cepat harus lebih kecil dari MA Lambat."]
        except (TypeError, ValueError):
            pass
        return []

    def generate_signal(self, df: pd.DataFrame):
        if len(df) < self.slow_period + 2:
            return None

        close = df["close"]
        fast = close.rolling(self.fast_period).mean()
        slow = close.rolling(self.slow_period).mean()

        fast_prev, fast_now = fast.iloc[-2], fast.iloc[-1]
        slow_prev, slow_now = slow.iloc[-2], slow.iloc[-1]

        if fast_prev <= slow_prev and fast_now > slow_now:
            logger.info("Sinyal BUY (MA cross up).")
            return SIGNAL_BUY

        if fast_prev >= slow_prev and fast_now < slow_now:
            logger.info("Sinyal SELL (MA cross down).")
            return SIGNAL_SELL

        return None

    def compute_overlays(self, df):
        if len(df) < 2:
            return []
        close = df["close"]
        return [
            {"name": f"MA{self.fast_period}", "color": "#5b8bef",
             "points": series_to_points(close.rolling(self.fast_period).mean())},
            {"name": f"MA{self.slow_period}", "color": "#e0a15c",
             "points": series_to_points(close.rolling(self.slow_period).mean())},
        ]
