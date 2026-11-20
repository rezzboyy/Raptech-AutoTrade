"""Strategi Stochastic Oscillator."""

import pandas as pd

from strategies.base import Strategy, register, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

logger = get_logger("mt5bot")


@register
class StochasticStrategy(Strategy):
    """Strategi Stochastic Oscillator (%K dan %D).

    - BUY  saat %K memotong ke atas %D di area oversold (level <= oversold).
    - SELL saat %K memotong ke bawah %D di area overbought (level >= overbought).
    """

    name = "stochastic"
    display_name = "Stochastic Oscillator"
    PARAMS = [
        {"key": "k_period", "label": "Periode %K", "type": "int", "default": 14, "min": 2},
        {"key": "d_period", "label": "Periode %D", "type": "int", "default": 3, "min": 1},
        {"key": "oversold", "label": "Level Oversold", "type": "float", "default": 20.0, "min": 1},
        {"key": "overbought", "label": "Level Overbought", "type": "float", "default": 80.0, "min": 1},
    ]

    @classmethod
    def extra_validate(cls, params: dict) -> list:
        try:
            os_lvl = float(params.get("oversold", 20.0))
            ob_lvl = float(params.get("overbought", 80.0))
            if os_lvl >= ob_lvl:
                return ["Level oversold harus lebih kecil dari overbought."]
        except (TypeError, ValueError):
            pass
        return []

    def generate_signal(self, df: pd.DataFrame):
        min_bars = self.k_period + self.d_period + 2
        if len(df) < min_bars:
            return None

        low_min = df["low"].rolling(self.k_period).min()
        high_max = df["high"].rolling(self.k_period).max()
        denom = (high_max - low_min).replace(0, 1e-9)

        k = 100 * ((df["close"] - low_min) / denom)
        d = k.rolling(self.d_period).mean()

        prev_k, now_k = k.iloc[-2], k.iloc[-1]
        prev_d, now_d = d.iloc[-2], d.iloc[-1]

        if pd.isna(prev_k) or pd.isna(now_k) or pd.isna(prev_d) or pd.isna(now_d):
            return None

        # %K cross up %D saat berada di/keluar dari zona oversold -> BUY
        if prev_k <= prev_d and now_k > now_d and prev_k <= self.oversold:
            logger.info("Sinyal BUY (Stochastic cross up oversold: %%K=%.1f, %%D=%.1f).", now_k, now_d)
            return SIGNAL_BUY

        # %K cross down %D saat berada di/keluar dari zona overbought -> SELL
        if prev_k >= prev_d and now_k < now_d and prev_k >= self.overbought:
            logger.info("Sinyal SELL (Stochastic cross down overbought: %%K=%.1f, %%D=%.1f).", now_k, now_d)
            return SIGNAL_SELL

        return None
