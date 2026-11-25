"""Unit test untuk fitur Mode Programmer Full Script Settings.

Menguji deklarasi SETTINGS, PARAMS dict, dot notation ParamDict,
auto-sync konfigurasi ke engine/settings, dan eksekusi order dengan setting skrip.
"""

import pandas as pd
import pytest

from config.settings import settings
from src.bot_engine import BotEngine
from src.controller import BotController
from strategies.script_runtime import (
    ParamDict,
    ScriptContext,
    ScriptError,
    ScriptStrategy,
    compile_script,
    extract_script_settings,
)


def test_param_dict_access():
    """ParamDict mendukung dot-notation dan key-indexing."""
    pd_obj = ParamDict({"fast": 9, "slow": 21, "nested": {"sub": 42}})
    assert pd_obj.fast == 9
    assert pd_obj["fast"] == 9
    assert pd_obj.slow == 21
    assert pd_obj.get("slow") == 21
    assert pd_obj.nested.sub == 42
    assert pd_obj.nested["sub"] == 42

    # Menambah dan mengubah nilai
    pd_obj.new_key = 100
    assert pd_obj["new_key"] == 100

    with pytest.raises(AttributeError):
        _ = pd_obj.non_existent_key


def test_compile_script_with_dict_params():
    """Kompilasi skrip dengan PARAMS berupa dictionary langsung berhasil tanpa error."""
    src = """
PARAMS = {
    "fast_ema": 9,
    "slow_ema": 21,
    "rsi_len": 14,
}

def on_bar(ctx):
    return None
"""
    ns = compile_script(src)
    assert isinstance(ns["PARAMS"], dict)
    assert ns["PARAMS"]["fast_ema"] == 9
    assert callable(ns["on_bar"])


def test_extract_script_settings_from_dict():
    """Ekstraksi settings dari kamus SETTINGS terpusat."""
    src = """
SETTINGS = {
    "symbol": "EURUSDm",
    "timeframe": "M15",
    "volume": 0.05,
    "sl_points": 250,
    "tp_points": 500,
    "trailing_stop_points": 120,
    "trailing_step_points": 25,
    "break_even_points": 100,
    "break_even_offset_points": 10,
    "max_spread_points": 30,
    "max_positions": 2,
    "magic_number": 999111,
    "comment": "TestScript",
}

def on_bar(ctx):
    return None
"""
    ns = compile_script(src)
    cfg = extract_script_settings(ns)

    assert cfg["symbol"] == "EURUSDm"
    assert cfg["timeframe_str"] == "M15"
    assert cfg["volume"] == 0.05
    assert cfg["lot"] == 0.05
    assert cfg["sl_points"] == 250
    assert cfg["tp_points"] == 500
    assert cfg["trailing_stop_points"] == 120
    assert cfg["trailing_stop_enabled"] is True
    assert cfg["trailing_step_points"] == 25
    assert cfg["break_even_trigger_points"] == 100
    assert cfg["break_even_enabled"] is True
    assert cfg["break_even_offset_points"] == 10
    assert cfg["max_spread_points"] == 30
    assert cfg["max_open_positions"] == 2
    assert cfg["magic_number"] == 999111
    assert cfg["comment"] == "TestScript"


def test_extract_script_settings_from_uppercase_constants():
    """Ekstraksi settings dari variabel konstanta huruf besar level-atas."""
    src = """
SYMBOL = "BTCUSDm"
TIMEFRAME = "H1"
LOT = 0.02
SL = 400
TP = 800
MAX_POSITIONS = 3
MAX_SPREAD = 50

def on_bar(ctx):
    return None
"""
    ns = compile_script(src)
    cfg = extract_script_settings(ns)

    assert cfg["symbol"] == "BTCUSDm"
    assert cfg["timeframe_str"] == "H1"
    assert cfg["volume"] == 0.02
    assert cfg["sl_points"] == 400
    assert cfg["tp_points"] == 800
    assert cfg["max_open_positions"] == 3
    assert cfg["max_spread_points"] == 50


def test_script_context_fallback_order_intent():
    """ctx.buy() dan ctx.sell() otomatis menggunakan parameter dari SETTINGS bila kosong."""
    df = pd.DataFrame({
        "open": [1.0, 1.1], "high": [1.2, 1.3],
        "low": [0.9, 1.0], "close": [1.1, 1.2],
        "tick_volume": [100, 200]
    })
    st = {
        "symbol": "EURUSDm",
        "volume": 0.03,
        "sl_points": 220,
        "tp_points": 440,
        "comment": "DefaultComment",
    }
    ctx = ScriptContext(df, params={"p1": 10}, settings=st)

    # Order tanpa argumen -> fallback ke settings skrip
    buy_intent = ctx.buy()
    assert buy_intent["action"] == "BUY"
    assert buy_intent["volume"] == 0.03
    assert buy_intent["sl_points"] == 220
    assert buy_intent["tp_points"] == 440
    assert buy_intent["comment"] == "DefaultComment"

    # Order dengan argumen parsial -> argumen eksplisit menimpa setting
    sell_intent = ctx.sell(volume=0.10, sl_points=150)
    assert sell_intent["action"] == "SELL"
    assert sell_intent["volume"] == 0.10
    assert sell_intent["sl_points"] == 150
    assert sell_intent["tp_points"] == 440  # tetap dari settings


def test_script_strategy_execution():
    """ScriptStrategy mengoper settings ke ScriptContext dan mengeksekusi on_bar."""
    src = """
SETTINGS = {
    "volume": 0.04,
    "sl_points": 180,
    "tp_points": 360,
}

PARAMS = {
    "target_close": 1.15,
}

def on_bar(ctx):
    if ctx.close[-1] > ctx.params.target_close:
        return ctx.buy()
    return None
"""
    strat = ScriptStrategy(src)
    assert strat.params.target_close == 1.15
    assert strat.script_settings["volume"] == 0.04

    df = pd.DataFrame({
        "open": [1.0, 1.1], "high": [1.2, 1.3],
        "low": [0.9, 1.0], "close": [1.1, 1.2],
        "tick_volume": [100, 200]
    })
    sig = strat.generate_signal(df)
    assert sig is not None
    assert sig["action"] == "BUY"
    assert sig["volume"] == 0.04
    assert sig["sl_points"] == 180
    assert sig["tp_points"] == 360


def test_controller_script_settings_and_params():
    """Controller mampu mengekstrak settings dan men-generate schema UI dari PARAMS dict."""
    ctrl = BotController()
    src = """
SETTINGS = {
    "symbol": "XAUUSDm",
    "timeframe": "M5",
    "volume": 0.01,
    "sl_points": 350,
    "tp_points": 700,
}

PARAMS = {
    "ema_period": 14,
    "threshold": 0.5,
}

def on_bar(ctx):
    return None
"""
    st = ctrl.scriptSettings(src)
    assert st["symbol"] == "XAUUSDm"
    assert st["timeframe_str"] == "M5"
    assert st["volume"] == 0.01
    assert st["sl_points"] == 350

    p_schema = ctrl.scriptParams(src)
    assert len(p_schema) == 2
    keys = {p["key"]: p for p in p_schema}
    assert "ema_period" in keys
    assert keys["ema_period"]["type"] == "int"
    assert keys["ema_period"]["default"] == 14
    assert "threshold" in keys
    assert keys["threshold"]["type"] == "float"


def test_controller_apply_script_auto_sync(tmp_path, monkeypatch):
    """Controller.applyScript menyinkronkan seluruh settings dari skrip ke settings global."""
    from src import config_store
    monkeypatch.setattr(config_store, "CONFIG_FILE", str(tmp_path / "config.json"))
    ctrl = BotController()
    src = """
NAME = "MyFullStrategy"

SETTINGS = {
    "symbol": "USDJPYm",
    "timeframe": "M15",
    "volume": 0.02,
    "sl_points": 280,
    "tp_points": 560,
    "trailing_stop_points": 140,
    "break_even_points": 100,
    "max_positions": 2,
    "max_spread_points": 25,
}

PARAMS = {
    "fast": 10,
    "slow": 30,
}

def on_bar(ctx):
    return None
"""
    ok = ctrl.applyScript(src)
    assert ok is True

    # Verifikasi settings global telah diselaraskan
    assert settings.strategy_name == "custom_script"
    assert settings.script_name == "MyFullStrategy"
    assert settings.symbol == "USDJPYm"
    assert settings.timeframe_str == "M15"
    assert settings.sl_points == 280
    assert settings.tp_points == 560
    assert settings.trailing_stop_points == 140
    assert settings.trailing_stop_enabled is True
    assert settings.break_even_trigger_points == 100
    assert settings.break_even_enabled is True
    assert settings.max_open_positions == 2
    assert settings.max_spread_points == 25
    assert settings.strategy_params["fast"] == 10
    assert settings.strategy_params["slow"] == 30


def test_extract_advanced_script_settings():
    """Ekstraksi variabel lanjutan: sesi waktu, RR ratio, ATR mult, kontrol bar, dan margin."""
    src = """
SETTINGS = {
    "trade_start_time": "08:30",
    "trade_end_time": "20:00",
    "close_friday_hour": 19,
    "active_days": [0, 1, 2, 3],
    "risk_reward_ratio": 2.5,
    "atr_sl_mult": 1.8,
    "atr_tp_mult": 3.6,
    "max_slippage_points": 25,
    "cooldown_bars": 3,
    "one_trade_per_bar": True,
    "close_on_reversal": True,
    "min_margin_level": 300.0,
    "max_holding_bars": 30,
}

def on_bar(ctx):
    return None
"""
    ns = compile_script(src)
    cfg = extract_script_settings(ns)

    assert cfg["trade_start_time"] == "08:30"
    assert cfg["trade_end_time"] == "20:00"
    assert cfg["close_friday_hour"] == 19
    assert cfg["active_days"] == [0, 1, 2, 3]
    assert cfg["risk_reward_ratio"] == 2.5
    assert cfg["atr_sl_mult"] == 1.8
    assert cfg["atr_tp_mult"] == 3.6
    assert cfg["max_slippage_points"] == 25
    assert cfg["cooldown_bars"] == 3
    assert cfg["one_trade_per_bar"] is True
    assert cfg["close_on_reversal"] is True
    assert cfg["min_margin_level"] == 300.0
    assert cfg["max_holding_bars"] == 30


def test_script_context_account_properties():
    """ScriptContext menyediakan properti akun lengkap (margin, margin_level, floating_profit)."""
    df = pd.DataFrame({
        "open": [1.0, 1.1], "high": [1.2, 1.3],
        "low": [0.9, 1.0], "close": [1.1, 1.2],
        "tick_volume": [100, 200]
    })
    acc = {
        "balance": 10000.0,
        "equity": 10500.0,
        "margin": 200.0,
        "free_margin": 10300.0,
        "margin_level": 5250.0,
        "profit": 500.0,
    }
    ctx = ScriptContext(df, params={}, account=acc)
    assert ctx.balance == 10000.0
    assert ctx.equity == 10500.0
    assert ctx.margin == 200.0
    assert ctx.free_margin == 10300.0
    assert ctx.margin_level == 5250.0
    assert ctx.floating_profit == 500.0
    assert ctx.unrealized_profit == 500.0


def test_controller_settings_reference():
    """Slot settingsReference() mengembalikan daftar kategori dan item dengan format lengkap."""
    ctrl = BotController()
    ref = ctrl.settingsReference()
    assert isinstance(ref, list)
    assert len(ref) >= 5

    group_titles = [g["group"] for g in ref]
    assert "Pasar & Simbol" in group_titles
    assert "Stop Loss, Take Profit & Rasio" in group_titles
    assert "Trailing Stop & Break-Even" in group_titles
    assert "Waktu & Sesi Pasar" in group_titles
    assert "Kontrol Entry & Anti-Spam Bar" in group_titles

    # Periksa kelengkapan field pada setiap item
    for grp in ref:
        assert "items" in grp
        for item in grp["items"]:
            assert "name" in item
            assert "type" in item
            assert "default" in item
            assert "desc" in item
            assert "snippet" in item
            assert item["name"] in item["snippet"]


def test_bot_engine_dynamic_sl_tp_calculation():
    """BotEngine menghitung SL/TP berdasarkan risk_reward_ratio dan ATR multiplier."""
    class FakeBackend:
        def symbol_spec(self, symbol):
            return {"point": 0.0001, "digits": 4}

        def get_rates(self, symbol, timeframe, count=25):
            return pd.DataFrame({
                "open": [1.1000] * 25,
                "high": [1.1050] * 25,
                "low": [1.0950] * 25,
                "close": [1.1020] * 25,
                "tick_volume": [100] * 25,
            })

    engine = BotEngine(backend=FakeBackend())

    # Kasus 1: risk_reward_ratio (SL=200, RRR=2.0 -> TP=400)
    engine.strategy.script_settings = {"risk_reward_ratio": 2.0}
    cmd = {"sl_points": 200}
    sl, tp = engine._compute_sl_tp("EURUSDm", "BUY", 1.1000, overrides=cmd)
    assert sl == pytest.approx(1.1000 - 200 * 0.0001)
    assert tp == pytest.approx(1.1000 + 400 * 0.0001)

    # Kasus 2: ATR multiplier (atr_sl_mult=1.5, atr_tp_mult=3.0)
    engine.strategy.script_settings = {"atr_sl_mult": 1.5, "atr_tp_mult": 3.0}
    sl2, tp2 = engine._compute_sl_tp("EURUSDm", "SELL", 1.1000, overrides={})
    assert sl2 > 1.1000
    assert tp2 < 1.1000

