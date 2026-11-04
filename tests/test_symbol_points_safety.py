from __future__ import annotations

"""
Unit tests for Symbol-Aware Point Scaling and Anti-Instant Stopout Protections.
Verifies that Stop Loss and Take Profit adapt properly across Forex, Gold, and Crypto,
and that positions never get closed instantly upon fill due to broker spread.
"""

from datetime import datetime, timezone
import pytest

from backend.base import AccountInfo, Position, SymbolSpec, Tick
from core.config_store import RiskSettings
from core.risk_manager import RiskManager, classify_market_symbol
from core.state_store import StateStore


class MockMultiAssetBackend:
    def __init__(self):
        self.specs = {
            "EURUSDm": SymbolSpec(symbol="EURUSDm", digits=5, point=0.00001),
            "XAUUSDm": SymbolSpec(symbol="XAUUSDm", digits=3, point=0.001),
            "BTCUSDm": SymbolSpec(symbol="BTCUSDm", digits=2, point=0.01),
        }
        self.ticks = {
            "EURUSDm": Tick(bid=1.11466, ask=1.11474, time=datetime.now(timezone.utc)),  # 8 pts spread
            "XAUUSDm": Tick(bid=4043.203, ask=4043.443, time=datetime.now(timezone.utc)), # 240 pts spread
            "BTCUSDm": Tick(bid=79719.11, ask=79725.51, time=datetime.now(timezone.utc)), # 640 pts spread ($6.40)
        }

    def symbol_spec(self, symbol: str):
        return self.specs.get(symbol)

    def get_tick(self, symbol: str):
        return self.ticks.get(symbol)

    def spread_points(self, symbol: str):
        t = self.ticks.get(symbol)
        s = self.specs.get(symbol)
        if t and s and s.point > 0:
            return round((t.ask - t.bid) / s.point, 1)
        return None


def test_classify_market_symbol():
    assert classify_market_symbol("EURUSDm") == "forex"
    assert classify_market_symbol("GBPUSD") == "forex"
    assert classify_market_symbol("XAUUSDm") == "metal"
    assert classify_market_symbol("GOLD") == "metal"
    assert classify_market_symbol("BTCUSDm") == "crypto"
    assert classify_market_symbol("ETHUSDm") == "crypto"
    assert classify_market_symbol("SOLUSDm") == "crypto"
    assert classify_market_symbol("US30m") == "index"
    assert classify_market_symbol("USOILm") == "oil"


def test_adapt_points_to_symbol(tmp_path):
    backend = MockMultiAssetBackend()
    settings = RiskSettings(virtual_sl_points=150, virtual_tp_points=250)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(backend, settings, store)

    # 1. Forex: EURUSD (150 pts = 15 pips)
    sl_eur = rm.adapt_points_to_symbol("EURUSDm", 150)
    assert sl_eur == 150
    tp_eur = rm.adapt_tp_points("EURUSDm", 250, sl_eur)
    assert tp_eur == 250

    # 2. Metal: XAUUSD (3 digits -> 10x multiplier = 1500 pts = $1.50)
    # Spread is 240 pts. 1500 > (240 * 2.5 = 600)
    sl_gold = rm.adapt_points_to_symbol("XAUUSDm", 150)
    assert sl_gold >= 1500
    tp_gold = rm.adapt_tp_points("XAUUSDm", 250, sl_gold)
    assert tp_gold >= int(sl_gold * 1.2)

    # 3. Crypto: BTCUSD (Spread is 640 pts = $6.40)
    # Base 150 pts ($1.50) MUST be scaled so SL > spread
    sl_btc = rm.adapt_points_to_symbol("BTCUSDm", 150)
    assert sl_btc >= 4000  # at least $40
    # Must be strictly greater than 2.5x spread
    assert sl_btc >= int(640 * 2.5)

    tp_btc = rm.adapt_tp_points("BTCUSDm", 250, sl_btc)
    assert tp_btc >= int(sl_btc * 1.2)


def test_anti_instant_stopout_on_btcusd(tmp_path):
    """
    Simulate the exact scenario from user's screenshot:
    BUY 0.01 BTCUSDm filled at Ask = 79,725.51, Bid = 79,719.11 (spread 640 pts = $6.40).
    With symbol adaptation, Virtual SL MUST NOT trigger immediately.
    """
    backend = MockMultiAssetBackend()
    settings = RiskSettings(virtual_sl_points=150, virtual_tp_points=250)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(backend, settings, store)

    # Simulate opening order at Ask price
    spec = backend.symbol_spec("BTCUSDm")
    tick = backend.get_tick("BTCUSDm")
    entry_price = tick.ask # 79,725.51

    pos = Position(
        ticket=2762152555,
        symbol="BTCUSDm",
        type="BUY",
        volume=0.01,
        price_open=entry_price,
        price_current=tick.bid,
    )

    # Register position (should automatically adapt 150 pts to BTCUSDm safe distance)
    rm.register_position(pos, spec, sl_points=150, tp_points=250)

    state = rm.virtual_states[pos.ticket]
    # Check that Virtual SL was set BELOW current Bid!
    # Bid is 79,719.11. Virtual SL must be < 79,719.11
    assert state.virtual_sl < tick.bid, f"Virtual SL {state.virtual_sl} must be below current Bid {tick.bid}!"

    # Evaluate protection immediately (simulating next tick)
    actions = rm.evaluate_virtual_protections([pos])
    # MUST NOT close!
    assert len(actions) == 0, f"Position should NOT be stopped out immediately! Actions: {actions}"


def test_pre_trade_risk_rejects_suicidal_spread(tmp_path):
    """If spread is >= 80% of SL, entry must be rejected to protect capital."""
    backend = MockMultiAssetBackend()
    # Set an artificially giant spread on BTCUSDm: 10,000 pts ($100 spread)
    backend.ticks["BTCUSDm"] = Tick(bid=79000.0, ask=79100.0, time=datetime.now(timezone.utc))
    settings = RiskSettings(virtual_sl_points=100)
    store = StateStore(tmp_path / "test_state.json")
    rm = RiskManager(backend, settings, store)

    acc = AccountInfo(balance=5000.0, equity=5000.0)
    allowed, reason = rm.check_pre_trade_risk("BTCUSDm", "BUY", 0.01, acc, [], sl_points=100)
    assert not allowed
    assert "terlalu lebar" in reason
