from __future__ import annotations

"""Unit tests for pure Python indicators and strategy signals."""

from datetime import datetime, timezone
import pytest

from backend.base import Candle
from strategies import (
    BrutalCentScalper,
    FastGoldScalper,
    MACross,
    RSIReversal,
    atr,
    ema,
    get_registry,
    rsi,
    sma,
)


def test_sma_calculation():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    res = sma(vals, 3)
    assert res[0] is None
    assert res[1] is None
    assert res[2] == 2.0
    assert res[3] == 3.0
    assert res[4] == 4.0


def test_ema_calculation():
    vals = [10.0, 11.0, 12.0, 13.0, 14.0]
    res = ema(vals, 3)
    assert res[0] is None
    assert res[1] is None
    assert round(res[2], 2) == 11.0
    assert res[3] > res[2]


def test_rsi_calculation():
    # Uptrend prices
    prices = [10.0 + i for i in range(20)]
    res = rsi(prices, 14)
    # Consecutive gains result in high RSI (near 100)
    assert res[-1] is not None
    assert res[-1] > 90.0


def test_strategy_registry():
    reg = get_registry()
    assert "fast_gold_scalper" in reg
    assert "brutal_cent_scalper" in reg
    assert "ma_cross" in reg
    assert "rsi_reversal" in reg


def test_ma_cross_signal_generation():
    strat = MACross(fast_period=3, slow_period=5)
    now = datetime.now(timezone.utc)

    # Bullish crossover candles
    bullish_prices = [10, 9, 8, 8, 8, 9, 11, 14, 18]
    candles = [Candle(time=now, open=p, high=p + 1, low=p - 1, close=p) for p in bullish_prices]

    sig = strat.generate_signal(candles)
    assert sig in ("BUY", None)
