from __future__ import annotations

"""Unit tests for SimulationBackend, Paper Trading, and Trading Mode Switcher."""

import asyncio
from pathlib import Path
import pytest

from backend.base import TradingBackend
from backend.simulation_backend import SimulationBackend
from core.config_store import AccountProfile, load_profile, save_profile
from core.controller import TradeController


def test_simulation_backend_protocol_and_connect(tmp_path: Path):
    state_file = tmp_path / "sim_state.json"
    sim = SimulationBackend(initial_balance=10000.0, state_file=state_file, seed=42)

    assert isinstance(sim, TradingBackend)
    assert sim.connect() is True

    acc = sim.account_info()
    assert acc is not None
    assert acc.balance == 10000.0
    assert acc.equity == 10000.0
    assert acc.account_type == "SIMULASI"
    assert acc.server_connected is True
    assert acc.trade_allowed is True

    sim.disconnect()


def test_simulation_market_data_feed(tmp_path: Path):
    state_file = tmp_path / "sim_state.json"
    sim = SimulationBackend(initial_balance=5000.0, state_file=state_file, seed=101)
    sim.connect()

    symbols = sim.list_symbols()
    assert "XAUUSDm" in symbols
    assert "EURUSDm" in symbols

    spec = sim.symbol_spec("XAUUSDm")
    assert spec is not None
    assert spec.digits == 2
    assert spec.point == 0.01

    tick = sim.get_tick("XAUUSDm")
    assert tick is not None
    assert tick.bid > 2000.0
    assert tick.ask >= tick.bid

    candles = sim.get_candles("XAUUSDm", "M5", count=30)
    assert len(candles) == 30
    for c in candles:
        assert c.high >= c.low
        assert c.open > 0
        assert c.close > 0


def test_simulation_order_lifecycle_and_closing(tmp_path: Path):
    state_file = tmp_path / "sim_state.json"
    sim = SimulationBackend(initial_balance=10000.0, state_file=state_file, seed=777)
    sim.connect()

    # Place market order
    res = sim.send_market_order(
        symbol="XAUUSDm",
        side="BUY",
        volume=0.10,
        sl=0.0,
        tp=0.0,
        comment="test_sim_order",
    )
    assert res.ok is True
    assert res.ticket is not None
    ticket = res.ticket

    # Verify open positions
    open_pos = sim.positions()
    assert len(open_pos) == 1
    assert open_pos[0].ticket == ticket
    assert open_pos[0].type == "BUY"
    assert open_pos[0].volume == 0.10

    # Margin should now be used
    acc = sim.account_info()
    assert acc.margin > 0.0
    assert acc.free_margin < 10000.0

    # Modify SL/TP
    mod_ok = sim.modify_sl_tp(ticket, "XAUUSDm", sl=2700.0, tp=2800.0)
    assert mod_ok is True
    assert sim.positions()[0].sl == 2700.0
    assert sim.positions()[0].tp == 2800.0

    # Close position
    close_res = sim.close_position(ticket, "XAUUSDm")
    assert close_res.ok is True
    assert len(sim.positions()) == 0

    # Balance should be updated with realized PnL
    acc2 = sim.account_info()
    assert acc2.margin == 0.0
    assert acc2.free_margin == acc2.equity

    sim.disconnect()


def test_simulation_auto_sl_tp_execution(tmp_path: Path):
    state_file = tmp_path / "sim_state.json"
    sim = SimulationBackend(initial_balance=10000.0, state_file=state_file, seed=555)
    sim.connect()

    # Get current price
    tick = sim.get_tick("XAUUSDm")
    assert tick is not None

    # Place order with tight SL that immediately triggers or triggers on next tick
    # For a BUY, if SL is set above or equal to current bid, it should trigger
    tight_sl = tick.bid + 5.0  # SL higher than bid -> guaranteed instant SL trigger
    res = sim.send_market_order(
        symbol="XAUUSDm",
        side="BUY",
        volume=0.01,
        sl=tight_sl,
        tp=0.0,
    )
    assert res.ok is True
    ticket = res.ticket

    # Calling positions() triggers _check_and_update_positions
    remaining_pos = sim.positions()
    # The position should have been auto-closed
    assert not any(p.ticket == ticket for p in remaining_pos)


def test_controller_trading_mode_dispatcher():
    # 1. Profile with trading_mode = "simulasi"
    prof_sim = AccountProfile(
        profile_name="TestSim",
        trading_mode="simulasi",
        backend="native",
    )
    controller_sim = TradeController(prof_sim)
    backend_sim = controller_sim.initialize_backend()
    assert isinstance(backend_sim, SimulationBackend)

    # 2. Profile with trading_mode = "real"
    prof_real = AccountProfile(
        profile_name="TestReal",
        trading_mode="real",
        backend="native",
    )
    controller_real = TradeController(prof_real)
    backend_real = controller_real.initialize_backend()
    assert not isinstance(backend_real, SimulationBackend)


def test_profile_trading_mode_serialization(tmp_path: Path):
    prof_file = tmp_path / "custom_profile.json"
    prof = AccountProfile(
        profile_name="CustomMode",
        trading_mode="simulasi",
    )
    d = prof.to_dict()
    assert d["trading_mode"] == "simulasi"

    # From dict normalization
    loaded = AccountProfile.from_dict({"profile_name": "P1", "trading_mode": "simulation"})
    assert loaded.trading_mode == "simulasi"

    loaded_real = AccountProfile.from_dict({"profile_name": "P2", "server": "Broker-Real"})
    assert loaded_real.trading_mode == "real"
