"""Strategi MACD (Moving Average Convergence Divergence) Crossover."""

import pandas as pd

from strategies.base import Strategy, register, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

logger = get_logger("mt5bot")


@register
class MACDCrossoverStrategy(Strategy):
    """Strategi Crossover Garis MACD dan Garis Sinyal.

    - BUY  saat garis MACD memotong ke atas garis Sinyal.
    - SELL saat garis MACD memotong ke bawah garis Sinyal.
    """

    name = "macd"
    display_name = "MACD Crossover"
    PARAMS = [
        {"key": "fast_ema", "label": "Fast EMA", "type": "int", "default": 12, "min": 2},
        {"key": "slow_ema", "label": "Slow EMA", "type": "int", "default": 26, "min": 3},
        {"key": "signal_period", "label": "Signal Period", "type": "int", "default": 9, "min": 1},
    ]

    @classmethod
    def extra_validate(cls, params: dict) -> list:
        try:
            fast = int(params.get("fast_ema", 12))
            slow = int(params.get("slow_ema", 26))
            if fast >= slow:
                return ["Fast EMA harus lebih kecil dari Slow EMA."]
        except (TypeError, ValueError):
            pass
        return []

    def generate_signal(self, df: pd.DataFrame):
        min_bars = self.slow_ema + self.signal_period + 2
        if len(df) < min_bars:
            return None

        close = df["close"]
        fast = close.ewm(span=self.fast_ema, adjust=False).mean()
        slow = close.ewm(span=self.slow_ema, adjust=False).mean()
        macd_line = fast - slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()

        prev_m, now_m = macd_line.iloc[-2], macd_line.iloc[-1]
        prev_s, now_s = signal_line.iloc[-2], signal_line.iloc[-1]

        if pd.isna(prev_m) or pd.isna(now_m) or pd.isna(prev_s) or pd.isna(now_s):
            return None

        # Cross up -> BUY
        if prev_m <= prev_s and now_m > now_s:
            logger.info("Sinyal BUY (MACD cross up: %.5f -> %.5f).", now_m, now_s)
            return SIGNAL_BUY

        # Cross down -> SELL
        if prev_m >= prev_s and now_m < now_s:
            logger.info("Sinyal SELL (MACD cross down: %.5f -> %.5f).", now_m, now_s)
            return SIGNAL_SELL

        return None
