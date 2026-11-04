from __future__ import annotations

"""Unit tests for Risk Engine v3.0: Risk-based sizing, Server-side SL, and Persistence."""

from pathlib import Path
import pytest

from backend.base import AccountInfo, Position, SymbolSpec
from core.config_store import RiskSettings
from core.order_manager import OrderManager
from core.risk_manager import RiskManager
from core.state_store import StateStore


class MockBackendRiskV3:
    def __init__(self):
        self._spec = SymbolSpec(
            symbol="XAUUSDm",
            digits=3,
            point=0.001,
            volume_min=0.01,
            volume_max=50.0,
            volume_step=0.01,
            tick_value=1.0,
            tick_size=0.001,
        )

    def symbol_spec(self, symbol: str):
        return self._spec

    def get_tick(self, symbol: str):
        return None

    def positions(self, symbol=None):
        return []


def test_risk_percent_sizing_floors_without_exceeding_budget():
    backend = MockBackendRiskV3()
    om = OrderManager(backend)

    # Equity $1000, 1% risk = $10 budget.
    # SL = 500 points on XAUUSD (1 pt = $1 per 1.0 lot -> 500 pts = $500 per lot).
    # Raw lot = 10 / 500 = 0.02 lot.
    acc = AccountInfo(login=1, server="Test", balance=1000.0, equity=1000.0)

    lot, info = om.calculate_risk_based_lot(
        symbol="XAUUSDm",
        sizing_mode="risk_percent",
        fixed_lot=0.01,
        risk_percent=1.0,
        stop_loss_points=500.0,
        account=acc,
    )
    assert lot == 0.02
    assert "RISK_PERCENT" in info


def test_risk_percent_rejects_when_budget_too_small_for_min_lot():
    backend = MockBackendRiskV3()
    om = OrderManager(backend)

    # Equity $100, 1% risk = $1 budget.
    # SL = 3000 points ($3000 per lot). Minimum lot 0.01 costs $30.
    # Exceeds $1 budget by 30x -> Must be rejected (lot == 0.0)
    acc = AccountInfo(login=1, server="Test", balance=100.0, equity=100.0)

    lot, info = om.calculate_risk_based_lot(
        symbol="XAUUSDm",
        sizing_mode="risk_percent",
        fixed_lot=0.05,
        risk_percent=1.0,
        stop_loss_points=3000.0,
        account=acc,
    )
    assert lot == 0.0
    assert "ditolak demi modal" in info.lower()


def test_server_side_sl_calculation_layering():
    backend = MockBackendRiskV3()
    settings = RiskSettings(
        use_server_sl=True,
        server_sl_points=250,
        virtual_sl_points=300,
        virtual_tp_points=600,
    )
    rm = RiskManager(backend, settings)

    # BUY at 2730.000 -> Server SL at 2730 - (250 * 0.001) = 2729.750
    sl, tp = rm.calculate_server_sl_tp("BUY", 2730.0, backend.symbol_spec("XAUUSDm"))
    assert sl == 2729.750
    assert tp == 2730.600

    # SELL at 2730.000 -> Server SL at 2730 + (250 * 0.001) = 2730.250
    sl_sell, tp_sell = rm.calculate_server_sl_tp("SELL", 2730.0, backend.symbol_spec("XAUUSDm"))
    assert sl_sell == 2730.250
    assert tp_sell == 2729.400


def test_circuit_breaker_lock_persists_across_restart(tmp_path: Path):
    file_path = tmp_path / "cb_persist.json"
    store1 = StateStore(file_path=file_path)
    backend = MockBackendRiskV3()
    settings = RiskSettings(max_daily_loss=50.0)

    rm1 = RiskManager(backend, settings, store1)
    acc = AccountInfo(login=1, server="Test", balance=1000.0, equity=940.0) # Down $60 -> exceeds $50

    allowed, reason = rm1.check_pre_trade_risk("XAUUSDm", "BUY", 0.01, acc, [])
    assert allowed is False
    assert rm1.circuit_breaker_tripped is True

    # Simulate restart by instantiating new RiskManager with the stored file
    store2 = StateStore(file_path=file_path)
    rm2 = RiskManager(backend, settings, store2)
    assert rm2.circuit_breaker_tripped is True
    # Still blocked even with fresh call
    allowed2, reason2 = rm2.check_pre_trade_risk("XAUUSDm", "BUY", 0.01, acc, [])
    assert allowed2 is False
