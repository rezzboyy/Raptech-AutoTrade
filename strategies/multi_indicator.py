"""Strategi Multi-Indikator (Trend MA + Momentum RSI)."""

import pandas as pd

from strategies.base import Strategy, register, series_to_points, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

logger = get_logger("mt5bot")


@register
class MultiIndicatorStrategy(Strategy):
    """Strategi kombinasi Multi-Indikator (Konfirmasi Tren MA + Pemicu Momentum RSI).

    - Filter Tren:
        * Bullish: MA Cepat > MA Lambat
        * Bearish: MA Cepat < MA Lambat
    - Pemicu Sinyal:
        * BUY  saat kondisi Bullish DAN RSI memotong ke atas level pemicu BUY (default 50).
        * SELL saat kondisi Bearish DAN RSI memotong ke bawah level pemicu SELL (default 50).
    """

    name = "multi_indicator"
    display_name = "Multi-Indicator (Trend + RSI)"
    PARAMS = [
        {"key": "ma_fast", "label": "MA Cepat (Tren)", "type": "int", "default": 20, "min": 2},
        {"key": "ma_slow", "label": "MA Lambat (Tren)", "type": "int", "default": 50, "min": 3},
        {"key": "rsi_period", "label": "Periode RSI", "type": "int", "default": 14, "min": 2},
        {"key": "rsi_buy_level", "label": "RSI Trigger Buy", "type": "float", "default": 50.0, "min": 10},
        {"key": "rsi_sell_level", "label": "RSI Trigger Sell", "type": "float", "default": 50.0, "min": 10},
    ]

    @classmethod
    def extra_validate(cls, params: dict) -> list:
        try:
            fast = int(params.get("ma_fast", 20))
            slow = int(params.get("ma_slow", 50))
            if fast >= slow:
                return ["MA Cepat harus lebih kecil dari MA Lambat."]
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
        min_bars = max(self.ma_slow, self.rsi_period) + 2
        if len(df) < min_bars:
            return None

        close = df["close"]
        ma_f = close.rolling(self.ma_fast).mean()
        ma_s = close.rolling(self.ma_slow).mean()
        rsi = self._rsi(close, self.rsi_period)

        fast_now = ma_f.iloc[-1]
        slow_now = ma_s.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        now_rsi = rsi.iloc[-1]

        if pd.isna(fast_now) or pd.isna(slow_now) or pd.isna(prev_rsi) or pd.isna(now_rsi):
            return None

        is_bullish = fast_now > slow_now
        is_bearish = fast_now < slow_now

        # Bullish Trend + RSI momentum cross up
        if is_bullish and prev_rsi <= self.rsi_buy_level and now_rsi > self.rsi_buy_level:
            logger.info("Sinyal BUY (Multi-Indicator: Bullish Trend MA & RSI naik ke %.1f).", now_rsi)
            return SIGNAL_BUY

        # Bearish Trend + RSI momentum cross down
        if is_bearish and prev_rsi >= self.rsi_sell_level and now_rsi < self.rsi_sell_level:
            logger.info("Sinyal SELL (Multi-Indicator: Bearish Trend MA & RSI turun ke %.1f).", now_rsi)
            return SIGNAL_SELL

        return None

    def compute_overlays(self, df):
        if len(df) < 2:
            return []
        close = df["close"]
        return [
            {"name": f"MA{self.ma_fast}", "color": "#5b8bef",
             "points": series_to_points(close.rolling(self.ma_fast).mean())},
            {"name": f"MA{self.ma_slow}", "color": "#e0a15c",
             "points": series_to_points(close.rolling(self.ma_slow).mean())},
        ]
