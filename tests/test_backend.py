from __future__ import annotations

"""Unit tests for backend abstraction, symbol resolution, and data models."""

from datetime import datetime, timezone
import pytest

from backend.base import (
    AccountInfo,
    Candle,
    OrderResult,
    Position,
    SymbolSpec,
    Tick,
    candidate_symbol_variations,
    classify_account_type,
    map_timeframe_to_period,
    resolve_symbol_name,
)


def test_classify_account_type():
    assert classify_account_type("real", "Exness-Trial") == "DEMO"
    assert classify_account_type("real", "Exness-Real1") == "REAL"
    assert classify_account_type("demo", "AnyServer") == "DEMO"
    assert classify_account_type("contest", "AnyServer") == "CONTEST"
    assert classify_account_type("other", "Exness-DemoServer") == "DEMO"
    # Automatic detection of MT5 trade_mode integers
    assert classify_account_type(0, "Exness-Real1") == "DEMO"
    assert classify_account_type(2, "Exness-Real1") == "REAL"
    assert classify_account_type(1, "Exness-Real1") == "CONTEST"
    # Automatic detection of Cent accounts (both Demo and Real)
    assert classify_account_type(2, "Exness-RealCent", "USC") == "REAL (CENT)"
    assert classify_account_type(0, "Exness-Trial", "USC") == "DEMO (CENT)"
    assert classify_account_type(2, "RoboForex-ProCent", "USD") == "REAL (CENT)"


def test_map_timeframe_to_period():
    assert map_timeframe_to_period("m1") == "M1"
    assert map_timeframe_to_period("M5") == "M5"
    assert map_timeframe_to_period("H1") == "H1"
    assert map_timeframe_to_period("unknown") == "M5"


def test_symbol_variations():
    cands = candidate_symbol_variations("EURUSD")
    assert "EURUSD" in cands
    assert "EURUSDm" in cands
    assert "EURUSDc" in cands
    assert "EURUSD.pro" in cands


def test_resolve_symbol_name():
    available = ["EURUSDm", "GBPUSDm", "XAUUSDm", "BTCUSD"]
    assert resolve_symbol_name("eurusd", available) == "EURUSDm"
    assert resolve_symbol_name("XAUUSD", available) == "XAUUSDm"
    assert resolve_symbol_name("btcusd", available) == "BTCUSD"
    assert resolve_symbol_name("NONEXISTENT", available) is None


def test_models_instantiation():
    acc = AccountInfo(login=12345, server="Demo", balance=1000.0, equity=1050.0)
    assert acc.balance == 1000.0
    assert acc.equity == 1050.0

    pos = Position(ticket=100, symbol="EURUSDm", type="BUY", volume=0.02, price_open=1.08, price_current=1.085)
    assert pos.ticket == 100
    assert pos.type == "BUY"

    spec = SymbolSpec(symbol="EURUSDm", digits=5, point=0.00001, volume_min=0.01, volume_max=100.0, volume_step=0.01)
    assert spec.digits == 5


def test_native_backend_account_info_and_filling_mode(monkeypatch):
    from unittest.mock import MagicMock
    from backend.native_backend import NativeBackend
    import backend.native_backend as nb_mod

    mock_mt5 = MagicMock()
    mock_acc = MagicMock()
    mock_acc.login = 12345678
    mock_acc.balance = 5000.0
    mock_acc.equity = 5000.0
    mock_acc.margin = 0.0
    mock_acc.margin_free = 5000.0
    mock_acc.margin_level = 0.0
    mock_acc.profit = 0.0
    mock_acc.trade_allowed = True
    mock_acc.currency = "USD"
    mock_acc.server = "Demo-Server"
    mock_acc.trade_mode = 0
    # Note: real mt5.account_info has NO attribute 'connected'
    del mock_acc.connected

    mock_term = MagicMock()
    mock_term.connected = True
    mock_mt5.terminal_info.return_value = mock_term
    mock_mt5.account_info.return_value = mock_acc

    mock_sym = MagicMock()
    mock_sym.filling_mode = 3
    mock_mt5.symbol_info.return_value = mock_sym
    mock_mt5.ORDER_FILLING_IOC = 1
    mock_mt5.ORDER_FILLING_FOK = 2

    monkeypatch.setattr(nb_mod, "mt5", mock_mt5)
    monkeypatch.setattr(nb_mod, "HAS_MT5", True)

    backend = NativeBackend(login=12345678, password="dummy", server="Demo-Server")
    backend._connected = True

    acc = backend.account_info()
    assert acc is not None
    assert acc.login == 12345678
    assert acc.balance == 5000.0
    assert acc.server_connected is True

    filling = backend._get_filling_type("EURUSDm")
    assert filling == mock_mt5.ORDER_FILLING_IOC
    backend.disconnect()

