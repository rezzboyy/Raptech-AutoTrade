from __future__ import annotations

"""Unit tests for RiskManager capital safeguards, limits, and virtual protections."""

from datetime import datetime, timezone
import pytest

from backend.base import AccountInfo, Position, SymbolSpec, Tick
from core.config_store import RiskSettings
from core.risk_manager import RiskManager
from core.state_store import StateStore


class MockBackendForRisk:
    def __init__(self):
        self.tick_map = {
            "XAUUSDm": Tick(bid=2735.0, ask=2735.2, time=datetime.now(timezone.utc)),
        }

    def symbol_spec(self, symbol: str):
        return SymbolSpec(symbol=symbol, digits=2, point=0.01)

    def get_tick(self, symbol: str):
        return self.tick_map.get(symbol)


def test_pre_trade_risk_max_positions(tmp_path):
    be = MockBackendForRisk()
    settings = RiskSettings(max_open_positions=2)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(be, settings, state_store=store)

    acc = AccountInfo(balance=10000.0, equity=10000.0, margin=0.0, margin_level=0.0)
    existing = [
        Position(ticket=1, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2730.0, price_current=2735.0),
        Position(ticket=2, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2732.0, price_current=2735.0),
    ]

    allowed, reason = rm.check_pre_trade_risk("XAUUSDm", "BUY", 0.01, acc, existing)
    assert not allowed
    assert "Batas maksimum posisi terbuka" in reason


def test_pre_trade_risk_min_margin(tmp_path):
    be = MockBackendForRisk()
    settings = RiskSettings(min_margin_level=500.0)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(be, settings, state_store=store)

    acc = AccountInfo(balance=10000.0, equity=10000.0, margin=2500.0, margin_level=400.0)
    allowed, reason = rm.check_pre_trade_risk("XAUUSDm", "BUY", 0.01, acc, [])
    assert not allowed
    assert "Margin level terlalu rendah" in reason


def test_daily_loss_circuit_breaker(tmp_path):
    be = MockBackendForRisk()
    settings = RiskSettings(max_daily_loss=50.0)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(be, settings, state_store=store)

    # Initial day reset
    rm.reset_daily_metrics_if_new_day(1000.0)

    # Equity dropped to 940 (loss = -60 > max 50)
    acc = AccountInfo(balance=1000.0, equity=940.0)
    allowed, reason = rm.check_pre_trade_risk("XAUUSDm", "BUY", 0.01, acc, [])
    assert not allowed
    assert rm.circuit_breaker_tripped
    assert "Circuit Breaker Aktif" in reason


def test_virtual_tp_and_sl_evaluation(tmp_path):
    be = MockBackendForRisk()
    settings = RiskSettings(virtual_sl_points=200, virtual_tp_points=400)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(be, settings, state_store=store)

    pos_buy = Position(ticket=10, symbol="XAUUSDm", type="BUY", volume=0.02, price_open=2730.0, price_current=2735.0)

    # At current price 2735, TP (2730 + 4.00 = 2734) should be triggered!
    actions = rm.evaluate_virtual_protections([pos_buy])
    assert len(actions) == 1
    assert "Virtual TP Hit" in actions[0][1]


def test_manual_circuit_breaker_reset(tmp_path):
    be = MockBackendForRisk()
    settings = RiskSettings(max_daily_loss=50.0)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(be, settings, state_store=store)

    rm.trip_circuit_breaker("Test trip")
    assert rm.circuit_breaker_tripped is True
    assert store.state.circuit_breaker_tripped is True

    # Manually reset
    rm.reset_circuit_breaker()
    assert rm.circuit_breaker_tripped is False
    assert rm.circuit_breaker_reason == ""
    assert store.state.circuit_breaker_tripped is False


def test_trailing_stop_rounding_precision(tmp_path):
    be = MockBackendForRisk()
    settings = RiskSettings(
        trailing_enabled=True,
        trail_start_points=100,
        trail_step_points=50,
    )
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(be, settings, state_store=store)

    # Symbol with 2 digits (e.g. XAUUSDm point=0.01)
    pos_buy = Position(
        ticket=101,
        symbol="XAUUSDm",
        type="BUY",
        volume=0.02,
        price_open=2730.00,
        price_current=2735.00,
    )
    rm.register_position(pos_buy, be.symbol_spec("XAUUSDm"))

    # Tick at 2735.00 (profit = 5.00 / 0.01 = 500 pts >= 1500 adapted start)
    # Let's adapt points: for metal digits=2, min_floor=150, start_pts=150
    # Current profit 500 pts > 150 pts
    # Update trailing
    state = rm.virtual_states[101]
    rm._update_trailing_stop(pos_buy, state, current_price=2735.12345, point=0.01)
    # Check that highest_price and virtual_sl are cleanly rounded to 2 digits
    assert state.highest_price == round(state.highest_price, 2)
    assert state.virtual_sl == round(state.virtual_sl, 2)

