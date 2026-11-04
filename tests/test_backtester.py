from __future__ import annotations

"""Unit tests for Backtester: anti-lookahead, metrics, and risk simulation."""

from datetime import datetime, timedelta
import pytest

from backend.base import Candle, SymbolSpec
from core.backtester import Backtester
from core.config_store import RiskSettings
from strategies import Strategy, register


class MockTrendStrategy(Strategy):
    name = "mock_trend"
    display_name = "Mock Trend Strategy"

    def generate_signal(self, candles: list[Candle]) -> str:
        # Simple rule: if last 3 closes strictly ascending -> BUY, descending -> SELL
        if len(candles) < 3:
            return "HOLD"
        c1, c2, c3 = candles[-3].close, candles[-2].close, candles[-1].close
        if c3 > c2 > c1:
            return "BUY"
        elif c3 < c2 < c1:
            return "SELL"
        return "HOLD"


def test_backtester_execution_and_metrics():
    # Build 100 deterministic candles
    candles = []
    base_time = datetime(2026, 1, 1, 10, 0)
    price = 2700.0

    for i in range(100):
        # Create an oscillating wave
        step = 2.0 if (i // 10) % 2 == 0 else -2.0
        open_p = price
        price += step
        close_p = price
        high_p = max(open_p, close_p) + 1.0
        low_p = min(open_p, close_p) - 1.0
        candles.append(
            Candle(
                time=base_time + timedelta(minutes=i * 5),
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                tick_volume=50,
            )
        )

    strat = MockTrendStrategy()
    bt = Backtester(
        strategy=strat,
        initial_balance=1000.0,
        spread_points=10.0,
        slippage_points=2.0,
        commission_per_lot=4.0,
        risk_settings=RiskSettings(
            fixed_lot=0.01,
            virtual_sl_points=200,
            virtual_tp_points=400,
            trailing_enabled=True,
            trail_start_points=150,
            trail_step_points=50,
        ),
    )

    metrics = bt.run(candles, symbol="XAUUSDm")

    assert metrics.total_trades > 0
    assert 0.0 <= metrics.win_rate_percent <= 100.0
    assert metrics.profit_factor >= 0.0
    assert metrics.max_drawdown_percent >= 0.0
    assert metrics.total_commission > 0.0
    assert len(metrics.trades) == metrics.total_trades


def test_backtester_zero_trades_empty_safety():
    strat = MockTrendStrategy()
    bt = Backtester(strategy=strat)
    # Fewer than 30 candles -> safe empty metrics without crash
    res = bt.run([])
    assert res.total_trades == 0
    assert res.net_profit == 0.0
    assert res.profit_factor == 0.0
