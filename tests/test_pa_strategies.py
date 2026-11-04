from __future__ import annotations

"""Unit tests for Universal M1 Price Action Scalper Strategies (Options A, B, and C)."""

from datetime import datetime, timedelta, timezone
import pytest

from backend.base import Candle
from strategies import (
    PABreakoutScalper,
    PAHybridScalper,
    PARejectionScalper,
    get_registry,
)


def _make_flat_candles(base_price: float, count: int, range_size: float = 2.0) -> list[Candle]:
    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    candles = []
    for i in range(count):
        t = base_time + timedelta(minutes=i)
        # Gentle oscillation
        offset = 0.5 if (i % 2 == 0) else -0.5
        c_open = base_price + offset
        c_close = base_price - offset
        c_high = base_price + range_size
        c_low = base_price - range_size
        candles.append(Candle(time=t, open=c_open, high=c_high, low=c_low, close=c_close))
    return candles


# ---------------------------------------------------------------------------
# Test 1: Registry Verification
# ---------------------------------------------------------------------------
def test_pa_strategies_registered():
    reg = get_registry()
    assert "pa_breakout" in reg
    assert "pa_rejection" in reg
    assert "pa_hybrid" in reg
    assert issubclass(reg["pa_breakout"], PABreakoutScalper)
    assert issubclass(reg["pa_rejection"], PARejectionScalper)
    assert issubclass(reg["pa_hybrid"], PAHybridScalper)


# ---------------------------------------------------------------------------
# Test 2: PABreakoutScalper (Option A) — Multi-market tests
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("symbol_price,step", [(2700.0, 5.0), (1.0850, 0.0020), (68000.0, 500.0)])
def test_pa_breakout_bullish_and_bearish(symbol_price: float, step: float):
    strat = PABreakoutScalper(lookback_bars=5, min_body_ratio=0.60, max_rejection_wick=0.25)

    # 1. Bullish Breakout: 15 base candles, then a strong green bar piercing highest high
    candles = _make_flat_candles(symbol_price, 15, range_size=step)
    recent_high = max(c.high for c in candles[-6:])
    t_next = candles[-1].time + timedelta(minutes=1)

    # Strong breakout bar
    breakout_open = recent_high - (step * 0.2)
    breakout_close = recent_high + (step * 1.5)
    breakout_high = breakout_close + (step * 0.1)  # Minimal upper wick
    breakout_low = breakout_open - (step * 0.1)

    bullish_candle = Candle(
        time=t_next,
        open=breakout_open,
        high=breakout_high,
        low=breakout_low,
        close=breakout_close,
    )
    candles.append(bullish_candle)

    sig = strat.generate_signal(candles)
    assert sig == "BUY", f"Expected BUY for bullish breakout on price {symbol_price}, got {sig}"

    # 2. Bearish Breakout: strong red bar piercing lowest low
    candles = _make_flat_candles(symbol_price, 15, range_size=step)
    recent_low = min(c.low for c in candles[-6:])
    t_next = candles[-1].time + timedelta(minutes=1)

    breakout_open = recent_low + (step * 0.2)
    breakout_close = recent_low - (step * 1.5)
    breakout_low = breakout_close - (step * 0.1)  # Minimal lower wick
    breakout_high = breakout_open + (step * 0.1)

    bearish_candle = Candle(
        time=t_next,
        open=breakout_open,
        high=breakout_high,
        low=breakout_low,
        close=breakout_close,
    )
    candles.append(bearish_candle)

    sig = strat.generate_signal(candles)
    assert sig == "SELL", f"Expected SELL for bearish breakout on price {symbol_price}, got {sig}"


def test_pa_breakout_filters_doji():
    strat = PABreakoutScalper(lookback_bars=5, min_body_ratio=0.60)
    candles = _make_flat_candles(2700.0, 15, range_size=2.0)
    recent_high = max(c.high for c in candles[-6:])
    t_next = candles[-1].time + timedelta(minutes=1)

    # Breakout high, but closes near open (Doji / weak body)
    doji_candle = Candle(
        time=t_next,
        open=recent_high + 1.0,
        high=recent_high + 5.0,
        low=recent_high - 1.0,
        close=recent_high + 1.2,  # Body is only 0.2 out of 6.0 range (~3%)
    )
    candles.append(doji_candle)
    assert strat.generate_signal(candles) is None


# ---------------------------------------------------------------------------
# Test 3: PARejectionScalper (Option B) — Pin Bar Multi-market
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("symbol_price,step", [(2700.0, 5.0), (1.0850, 0.0020), (68000.0, 500.0)])
def test_pa_rejection_pinbar_hammer_and_shooting_star(symbol_price: float, step: float):
    strat = PARejectionScalper(lookback_bars=6, min_wick_ratio=0.50, wick_to_body_ratio=2.0)

    # 1. Bullish Hammer (Long tail down piercing swing low)
    candles = _make_flat_candles(symbol_price, 15, range_size=step)
    recent_low = min(c.low for c in candles[-7:])
    t_next = candles[-1].time + timedelta(minutes=1)

    # Low dips below recent low, but price closes back up near high
    h_low = recent_low - (step * 1.5)
    h_high = symbol_price + (step * 0.5)
    h_open = h_high - (step * 0.2)
    h_close = h_high - (step * 0.05)  # Small body at very top

    hammer = Candle(time=t_next, open=h_open, high=h_high, low=h_low, close=h_close)
    candles.append(hammer)

    sig = strat.generate_signal(candles)
    assert sig == "BUY", f"Expected BUY for hammer pinbar on price {symbol_price}, got {sig}"

    # 2. Bearish Shooting Star (Long tail up piercing swing high)
    candles = _make_flat_candles(symbol_price, 15, range_size=step)
    recent_high = max(c.high for c in candles[-7:])
    t_next = candles[-1].time + timedelta(minutes=1)

    s_high = recent_high + (step * 1.5)
    s_low = symbol_price - (step * 0.5)
    s_open = s_low + (step * 0.2)
    s_close = s_low + (step * 0.05)

    shooting_star = Candle(time=t_next, open=s_open, high=s_high, low=s_low, close=s_close)
    candles.append(shooting_star)

    sig = strat.generate_signal(candles)
    assert sig == "SELL", f"Expected SELL for shooting star pinbar on price {symbol_price}, got {sig}"


# ---------------------------------------------------------------------------
# Test 4: PAHybridScalper (Option C) — Engulfing & Delegation
# ---------------------------------------------------------------------------
def test_pa_hybrid_engulfing_and_delegation():
    strat = PAHybridScalper(lookback_bars=5)
    candles = _make_flat_candles(2700.0, 15, range_size=2.0)

    # Create previous small red candle
    t_prev = candles[-1].time + timedelta(minutes=1)
    prev_candle = Candle(time=t_prev, open=2701.0, high=2701.5, low=2699.5, close=2700.0)
    candles.append(prev_candle)

    # Bullish Engulfing: opens below prev close, closes well above prev open with solid body
    t_curr = t_prev + timedelta(minutes=1)
    engulf_candle = Candle(time=t_curr, open=2699.8, high=2704.0, low=2699.5, close=2703.8)
    candles.append(engulf_candle)

    sig = strat.generate_signal(candles)
    assert sig == "BUY", f"Expected BUY for Bullish Engulfing in PAHybridScalper, got {sig}"


def test_pa_strategies_zero_division_safety():
    """Verify strategies handle zero-range candles without throwing ZeroDivisionError."""
    now = datetime.now(timezone.utc)
    flat_candles = [Candle(time=now, open=100.0, high=100.0, low=100.0, close=100.0) for _ in range(20)]

    for cls in (PABreakoutScalper, PARejectionScalper, PAHybridScalper):
        inst = cls()
        sig = inst.generate_signal(flat_candles)
        assert sig is None
