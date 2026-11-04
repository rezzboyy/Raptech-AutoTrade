from __future__ import annotations

from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock

from backend.base import Candle, Tick
from core.market_analyzer import MarketAnalyzer, MarketRecommendation


def make_candle(dt: datetime, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=dt, open=o, high=h, low=l, close=c, tick_volume=100)


def test_market_analyzer_empty_backend_fallback():
    analyzer = MarketAnalyzer(backend=None)
    rec = analyzer.analyze_symbol("XAUUSDm")
    assert isinstance(rec, MarketRecommendation)
    assert rec.symbol == "XAUUSDm"
    assert rec.readiness_score != ""
    assert rec.strategy_recommended != ""


def test_market_analyzer_calculations_bullish_breakout():
    backend = MagicMock()
    now = datetime.now()
    candles = []
    base_price = 2700.0

    # Create 30 upward moving candles
    for i in range(30):
        t = now - timedelta(minutes=(30 - i))
        op = base_price + (i * 1.5)
        cl = op + 2.0
        hi = cl + 0.5
        lo = op - 0.5
        candles.append(make_candle(t, op, hi, lo, cl))

    backend.get_candles.return_value = candles
    backend.get_tick.return_value = Tick(bid=2745.0, ask=2745.2, time=now)

    analyzer = MarketAnalyzer(backend=backend)
    rec = analyzer.analyze_symbol("XAUUSDm")

    assert "Bullish" in rec.condition
    assert rec.change_pct > 0
    assert "SIAP TRADING" in rec.readiness_score
    assert "Breakout" in rec.strategy_recommended or "Hybrid" in rec.strategy_recommended
    assert rec.high_24h > 2700.0
    assert rec.low_24h >= 2695.0


def test_market_analyzer_calculations_bearish_trend():
    backend = MagicMock()
    now = datetime.now()
    candles = []
    base_price = 2800.0

    # Create 30 downward moving candles
    for i in range(30):
        t = now - timedelta(minutes=(30 - i))
        op = base_price - (i * 1.5)
        cl = op - 2.0
        hi = op + 0.5
        lo = cl - 0.5
        candles.append(make_candle(t, op, hi, lo, cl))

    backend.get_candles.return_value = candles
    backend.get_tick.return_value = Tick(bid=2740.0, ask=2740.2, time=now)

    analyzer = MarketAnalyzer(backend=backend)
    rec = analyzer.analyze_symbol("XAUUSDm")

    assert "Bearish" in rec.condition
    assert rec.change_pct < 0
    assert "SIAP TRADING" in rec.readiness_score


def test_market_analyzer_calculations_sideways_rejection():
    backend = MagicMock()
    now = datetime.now()
    candles = []
    base_price = 1.08500

    # Create 30 oscillating candles with long wicks
    for i in range(30):
        t = now - timedelta(minutes=(30 - i))
        op = base_price + (0.00010 if i % 2 == 0 else -0.00010)
        cl = base_price
        hi = base_price + 0.00080
        lo = base_price - 0.00080
        candles.append(make_candle(t, op, hi, lo, cl))

    backend.get_candles.return_value = candles
    backend.get_tick.return_value = Tick(bid=1.08500, ask=1.08510, time=now)

    analyzer = MarketAnalyzer(backend=backend)
    rec = analyzer.analyze_symbol("EURUSDm")

    assert rec.symbol == "EURUSDm"
    assert rec.spread_pts >= 1
    assert "Rejection" in rec.condition or "Range" in rec.condition or "Konsolidasi" in rec.condition


def test_market_analyzer_spread_warning():
    backend = MagicMock()
    now = datetime.now()
    candles = []
    base_price = 2700.0

    for i in range(20):
        t = now - timedelta(minutes=(20 - i))
        candles.append(make_candle(t, base_price, base_price + 0.2, base_price - 0.2, base_price))

    backend.get_candles.return_value = candles
    # Huge suicidal spread
    backend.get_tick.return_value = Tick(bid=2700.0, ask=2710.0, time=now)

    analyzer = MarketAnalyzer(backend=backend)
    rec = analyzer.analyze_symbol("XAUUSDm")

    assert "Spread" in rec.condition
    assert "WASPADA" in rec.readiness_score or "Wait & See" in rec.strategy_recommended


def test_market_analyzer_scan_all():
    backend = MagicMock()
    backend.get_tick.return_value = Tick(bid=100.0, ask=100.2, time=datetime.now())
    backend.get_candles.return_value = []

    analyzer = MarketAnalyzer(backend=backend)
    recs = analyzer.scan_all(["XAUUSDm", "EURUSDm", "BTCUSDm"])
    assert len(recs) == 3
    assert [r.symbol for r in recs] == ["XAUUSDm", "EURUSDm", "BTCUSDm"]
