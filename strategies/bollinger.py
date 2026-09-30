"""Strategi Bollinger Bands (Mean Reversion)."""

import pandas as pd

from strategies.base import Strategy, register, series_to_points, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

logger = get_logger("mt5bot")


@register
class BollingerBandsStrategy(Strategy):
    """Strategi pembalikan arah (mean reversion) Bollinger Bands.

    - BUY  saat harga sebelumnya berada di/bawah Lower Band lalu ditutup kembali ke atas Lower Band.
    - SELL saat harga sebelumnya berada di/atas Upper Band lalu ditutup kembali ke bawah Upper Band.
    """

    name = "bollinger"
    display_name = "Bollinger Bands"
    PARAMS = [
        {"key": "period", "label": "Periode SMA", "type": "int", "default": 20, "min": 2},
        {"key": "std_dev", "label": "Deviasi Standar", "type": "float", "default": 2.0, "min": 0.5},
    ]

    def generate_signal(self, df: pd.DataFrame):
        if len(df) < self.period + 2:
            return None

        close = df["close"]
        sma = close.rolling(self.period).mean()
        std = close.rolling(self.period).std()

        upper = sma + (self.std_dev * std)
        lower = sma - (self.std_dev * std)

        prev_c, now_c = close.iloc[-2], close.iloc[-1]
        prev_l, now_l = lower.iloc[-2], lower.iloc[-1]
        prev_u, now_u = upper.iloc[-2], upper.iloc[-1]

        if pd.isna(prev_l) or pd.isna(now_l) or pd.isna(prev_u) or pd.isna(now_u):
            return None

        # Reversal dari bawah Lower Band -> BUY
        if prev_c <= prev_l and now_c > now_l:
            logger.info("Sinyal BUY (Bollinger Bands bounce dari Lower Band: %.5f -> %.5f).", prev_c, now_c)
            return SIGNAL_BUY

        # Reversal dari atas Upper Band -> SELL
        if prev_c >= prev_u and now_c < now_u:
            logger.info("Sinyal SELL (Bollinger Bands bounce dari Upper Band: %.5f -> %.5f).", prev_c, now_c)
            return SIGNAL_SELL

        return None

    def compute_overlays(self, df):
        if len(df) < 2:
            return []
        close = df["close"]
        sma = close.rolling(self.period).mean()
        std = close.rolling(self.period).std()
        return [
            {"name": "Upper", "color": "#8a8aa0", "points": series_to_points(sma + self.std_dev * std)},
            {"name": f"SMA{self.period}", "color": "#5b8bef", "points": series_to_points(sma)},
            {"name": "Lower", "color": "#8a8aa0", "points": series_to_points(sma - self.std_dev * std)},
        ]
