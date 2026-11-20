"""Strategi RSI (Relative Strength Index) oversold/overbought."""

import pandas as pd

from strategies.base import Strategy, register, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

logger = get_logger("mt5bot")


@register
class RSIStrategy(Strategy):
    """Sinyal berbasis RSI.

    - BUY  saat RSI naik melewati level oversold dari bawah.
    - SELL saat RSI turun melewati level overbought dari atas.
    """

    name = "rsi"
    display_name = "RSI Oversold/Overbought"
    PARAMS = [
        {"key": "period", "label": "Periode RSI", "type": "int", "default": 14, "min": 2},
        {"key": "oversold", "label": "Level Oversold", "type": "float", "default": 30.0, "min": 1},
        {"key": "overbought", "label": "Level Overbought", "type": "float", "default": 70.0, "min": 1},
    ]

    @classmethod
    def extra_validate(cls, params: dict) -> list:
        try:
            os_lvl = float(params.get("oversold", 30.0))
            ob_lvl = float(params.get("overbought", 70.0))
            if os_lvl >= ob_lvl:
                return ["Level oversold harus lebih kecil dari overbought."]
        except (TypeError, ValueError):
            pass
        return []

    @staticmethod
    def _rsi(close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        return 100 - (100 / (1 + rs))

    def generate_signal(self, df: pd.DataFrame):
        if len(df) < self.period + 2:
            return None

        rsi = self._rsi(df["close"], self.period)
        prev, now = rsi.iloc[-2], rsi.iloc[-1]
        if pd.isna(prev) or pd.isna(now):
            return None

        # Naik melewati level oversold -> BUY.
        if prev <= self.oversold and now > self.oversold:
            logger.info("Sinyal BUY (RSI keluar oversold %.1f).", now)
            return SIGNAL_BUY

        # Turun melewati level overbought -> SELL.
        if prev >= self.overbought and now < self.overbought:
            logger.info("Sinyal SELL (RSI keluar overbought %.1f).", now)
            return SIGNAL_SELL

        return None
