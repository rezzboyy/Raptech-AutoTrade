from __future__ import annotations

"""Unit tests for OrderManager volume normalization and price rounding."""

import pytest

from backend.base import OrderResult, Position, SymbolSpec
from core.order_manager import OrderManager


class MockTradingBackend:
    def __init__(self):
        self.sent_orders = []
        self.closed_positions = []

    def symbol_spec(self, symbol: str):
        return SymbolSpec(
            symbol=symbol,
            digits=2 if "XAU" in symbol else 5,
            point=0.01 if "XAU" in symbol else 0.00001,
            volume_min=0.01,
            volume_max=10.0,
            volume_step=0.01,
        )

    def send_market_order(self, symbol, side, volume, sl=0.0, tp=0.0, magic=0, comment=""):
        res = OrderResult(ok=True, ticket=12345, price=2000.0, volume=volume, message="ok")
        self.sent_orders.append((symbol, side, volume, sl, tp))
        return res

    def close_position(self, ticket, symbol, volume=None):
        self.closed_positions.append((ticket, symbol, volume))
        return OrderResult(ok=True, ticket=ticket, message="closed")

    def positions(self, symbol=None):
        closed_tickets = {c[0] for c in self.closed_positions}
        all_p = [
            Position(ticket=1, symbol="XAUUSDm", type="BUY", volume=0.02, price_open=2000.0, price_current=2005.0),
            Position(ticket=2, symbol="EURUSDm", type="SELL", volume=0.05, price_open=1.08, price_current=1.079),
        ]
        active = [p for p in all_p if p.ticket not in closed_tickets]
        if symbol:
            return [p for p in active if p.symbol == symbol]
        return active


def test_lot_normalization():
    mock_be = MockTradingBackend()
    om = OrderManager(mock_be)
    spec = mock_be.symbol_spec("EURUSDm")

    # Min lot clamp
    assert om.normalize_lot(0.001, spec) == 0.01
    # Max lot clamp
    assert om.normalize_lot(25.0, spec) == 10.0
    # Step round
    assert om.normalize_lot(0.024, spec) == 0.02
    assert om.normalize_lot(0.028, spec) == 0.03


def test_price_rounding():
    mock_be = MockTradingBackend()
    om = OrderManager(mock_be)

    gold_spec = mock_be.symbol_spec("XAUUSDm")
    eur_spec = mock_be.symbol_spec("EURUSDm")

    assert om.round_price(2745.3289, gold_spec) == 2745.33
    assert om.round_price(1.082346, eur_spec) == 1.08235


def test_send_and_close_all():
    mock_be = MockTradingBackend()
    om = OrderManager(mock_be)

    res = om.send_market_order("XAUUSDm", "BUY", 0.02, sl=2730.0, tp=2750.0)
    assert res.ok
    assert len(mock_be.sent_orders) == 1

    close_results = om.close_all_positions()
    assert len(close_results) == 2
    assert len(mock_be.closed_positions) == 2
