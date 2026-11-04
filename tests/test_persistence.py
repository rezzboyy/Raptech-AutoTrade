from __future__ import annotations

"""Unit tests for StateStore persistence, atomic writes, and crash recovery."""

from pathlib import Path
import pytest

from core.state_store import PersistedVirtualProtection, StateStore, TradingStateData


def test_state_store_save_and_load(tmp_path: Path):
    file_path = tmp_path / "test_trading_state.json"
    store = StateStore(file_path=file_path)

    # Initial state
    assert store.state.daily_start_balance == 0.0
    assert not store.state.circuit_breaker_tripped

    # Modify and save
    today_str = store.state.trade_date
    store.update_daily_metrics(today_str, 1500.0, 1600.0)
    store.record_circuit_breaker(True, "Max Daily Loss Hit")

    prot = PersistedVirtualProtection(
        ticket=1001,
        symbol="XAUUSDm",
        side="BUY",
        price_open=2730.0,
        virtual_sl=2725.0,
        virtual_tp=2740.0,
        trailing_active=True,
        highest_price=2735.0,
        lowest_price=2730.0,
    )
    store.set_virtual_protection(prot)

    # Reload from disk (simulating process restart)
    store2 = StateStore(file_path=file_path)
    assert store2.state.circuit_breaker_tripped is True
    assert "Max Daily Loss Hit" in store2.state.circuit_breaker_reason
    assert store2.state.daily_start_balance == 1500.0
    assert store2.state.high_water_mark_equity == 1600.0
    assert "1001" in store2.state.virtual_protections
    saved_p = store2.state.virtual_protections["1001"]
    assert saved_p["symbol"] == "XAUUSDm"
    assert saved_p["virtual_sl"] == 2725.0


def test_corrupted_state_file_recovery(tmp_path: Path):
    file_path = tmp_path / "corrupt_state.json"
    # Write garbage bytes
    file_path.write_text("{invalid_json: true, broken...", encoding="utf-8")

    # Should recover gracefully to fresh state without raising exception
    store = StateStore(file_path=file_path)
    assert isinstance(store.state, TradingStateData)
    assert store.state.daily_start_balance == 0.0
    # Original corrupt file backed up
    assert (tmp_path / "corrupt_state.corrupt.bak").exists()


def test_remove_virtual_protection(tmp_path: Path):
    file_path = tmp_path / "test_state_remove.json"
    store = StateStore(file_path=file_path)

    prot = PersistedVirtualProtection(
        ticket=2002, symbol="EURUSDm", side="SELL", price_open=1.0850
    )
    store.set_virtual_protection(prot)
    assert "2002" in store.state.virtual_protections

    store.remove_virtual_protection(2002)
    assert "2002" not in store.state.virtual_protections

    # Verify disk reflects deletion
    store2 = StateStore(file_path=file_path)
    assert "2002" not in store2.state.virtual_protections
