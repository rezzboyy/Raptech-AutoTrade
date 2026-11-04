from __future__ import annotations

"""Unit tests for Broker Reconciliation and Duplicate Order Prevention."""

from typing import List, Optional
import pytest

from backend.base import OrderResult, OrderState, Position, SymbolSpec, TradingBackend
from core.order_manager import OrderManager


class MockReconciliationBackend:
    def __init__(self, positions: List[Position]):
        self._positions = positions
        self.closed_tickets: List[int] = []

    def positions(self, symbol: Optional[str] = None) -> List[Position]:
        return [p for p in self._positions if p.ticket not in self.closed_tickets]

    def symbol_spec(self, symbol: str) -> Optional[SymbolSpec]:
        return SymbolSpec(symbol=symbol, digits=5, point=0.00001, volume_min=0.01, volume_max=10.0, volume_step=0.01)

    def close_position(self, ticket: int, symbol: str, volume: Optional[float] = None) -> OrderResult:
        self.closed_tickets.append(ticket)
        return OrderResult(ok=True, ticket=ticket, message="Closed")

    def send_market_order(self, **kwargs) -> OrderResult:
        raise TimeoutError("Network gateway timeout waiting for MT5 response")


def test_reconciliation_detects_unmanaged_and_ghosts():
    broker_positions = [
        Position(ticket=101, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2730.0, price_current=2732.0),
        Position(ticket=102, symbol="EURUSDm", type="SELL", volume=0.02, price_open=1.0850, price_current=1.0840),
    ]
    backend = MockReconciliationBackend(broker_positions)
    om = OrderManager(backend)

    # Local state thinks positions 101 and 999 are open (999 is already closed at broker = ghost)
    # Broker has 102 which local state doesn't know about (= unmanaged)
    known_local = [101, 999]
    report = om.reconcile_positions(known_local)

    assert report.reconciliation_required is True
    assert 101 in report.matched_positions
    assert 999 in report.ghost_positions_cleaned
    assert 102 in report.unmanaged_positions


def test_order_timeout_marks_reconciliation_required():
    backend = MockReconciliationBackend([])
    om = OrderManager(backend)

    # Sending order when network drops/timeouts
    res = om.send_market_order(symbol="EURUSDm", side="BUY", lot=0.01)
    assert res.ok is False
    assert res.state == OrderState.RECONCILIATION_REQUIRED
    assert res.operation_id is not None
    assert "timeout" in res.message.lower()


def test_verified_emergency_close_all():
    broker_positions = [
        Position(ticket=201, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2730.0, price_current=2732.0),
        Position(ticket=202, symbol="XAUUSDm", type="BUY", volume=0.02, price_open=2731.0, price_current=2732.0),
    ]
    backend = MockReconciliationBackend(broker_positions)
    om = OrderManager(backend)

    results, remaining = om.verified_emergency_close_all()
    assert len(results) == 2
    assert len(remaining) == 0
    assert 201 in backend.closed_tickets
    assert 202 in backend.closed_tickets
