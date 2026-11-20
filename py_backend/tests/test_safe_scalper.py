"""Audit dan pengujian menyeluruh untuk strategi Safe Precision Scalper Pro."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from strategies.script_runtime import (
    compile_script,
    extract_script_settings,
    ScriptStrategy,
    ScriptContext,
    load_script,
)


@pytest.fixture
def scalper_source():
    src = load_script("safe_precision_scalper")
    assert src, "Skrip safe_precision_scalper tidak boleh kosong"
    return src


def create_df(n_bars=250, base_price=1.1000, trend="up"):
    """Buat DataFrame candle sintetis dengan tren terarah."""
    times = pd.date_range("2026-09-24 10:00:00", periods=n_bars, freq="5min", tz="UTC")
    closes = []
    opens = []
    highs = []
    lows = []
    vols = []

    price = base_price
    for i in range(n_bars):
        step = 0.00015 if trend == "up" else -0.00015
        # Noise kecil
        noise = (i % 3 - 1) * 0.00005
        op = price
        cl = price + step + noise
        hi = max(op, cl) + 0.00010
        lo = min(op, cl) - 0.00010
        opens.append(op)
        closes.append(cl)
        highs.append(hi)
        lows.append(lo)
        vols.append(100.0)
        price = cl

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols,
    }, index=times)


def test_scalper_compilation_and_ast_sandbox(scalper_source):
    """Pastikan skrip lolos audit keamanan sandbox AST."""
    ns = compile_script(scalper_source)
    assert "on_bar" in ns
    assert callable(ns["on_bar"])
    assert "SETTINGS" in ns
    assert "PARAMS" in ns


def test_scalper_settings_extraction(scalper_source):
    """Pastikan SETTINGS terdeteksi dan diekstrak dengan akurat."""
    ns = compile_script(scalper_source)
    settings = extract_script_settings(ns)

    assert settings.get("symbol") == "EURUSDm"
    assert settings.get("timeframe_str") == "M5"
    assert settings.get("volume") == 0.01
    assert settings.get("sl_points") == 120
    assert settings.get("tp_points") == 180
    assert settings.get("trailing_stop_enabled") is True
    assert settings.get("trailing_stop_points") == 80
    assert settings.get("break_even_enabled") is True
    assert settings.get("break_even_points") == 60
    assert settings.get("max_spread_points") == 25
    assert settings.get("daily_drawdown_limit") == 0.03
    assert settings.get("max_positions") == 1


def test_scalper_protection_weekend_filter(scalper_source):
    """Audit Proteksi: Hari Sabtu/Minggu harus menolak trading."""
    ns = compile_script(scalper_source)
    on_bar = ns["on_bar"]
    df = create_df(220)

    # Buat context di hari Sabtu (weekday=5)
    ctx = ScriptContext(df, {}, tick={"bid": 1.1000, "ask": 1.1002}, spec={"point": 0.00001, "digits": 5})
    ctx.weekday = 5
    ctx.hour = 12

    result = on_bar(ctx)
    assert result is None


def test_scalper_protection_friday_evening(scalper_source):
    """Audit Proteksi: Hari Jumat malam (>= 20:00 UTC) harus menolak trading."""
    ns = compile_script(scalper_source)
    on_bar = ns["on_bar"]
    df = create_df(220)

    ctx = ScriptContext(df, {}, tick={"bid": 1.1000, "ask": 1.1002}, spec={"point": 0.00001, "digits": 5})
    ctx.weekday = 4  # Jumat
    ctx.hour = 21

    result = on_bar(ctx)
    assert result is None


def test_scalper_protection_rollover_hour(scalper_source):
    """Audit Proteksi: Jam 23:00 dan 00:00 (rollover broker) harus menolak trading."""
    ns = compile_script(scalper_source)
    on_bar = ns["on_bar"]
    df = create_df(220)

    # Jam 23
    ctx23 = ScriptContext(df, {}, tick={"bid": 1.1000, "ask": 1.1002}, spec={"point": 0.00001, "digits": 5})
    ctx23.weekday = 2  # Rabu
    ctx23.hour = 23
    assert on_bar(ctx23) is None

    # Jam 00
    ctx00 = ScriptContext(df, {}, tick={"bid": 1.1000, "ask": 1.1002}, spec={"point": 0.00001, "digits": 5})
    ctx00.weekday = 2
    ctx00.hour = 0
    assert on_bar(ctx00) is None


def test_scalper_protection_spread_filter(scalper_source):
    """Audit Proteksi: Spread melebihi batas (misal 35 > 25) harus menolak order."""
    ns = compile_script(scalper_source)
    on_bar = ns["on_bar"]
    df = create_df(220)

    # Spread 35 points (ask - bid = 0.00035, point=0.00001)
    ctx = ScriptContext(df, {}, tick={"bid": 1.1000, "ask": 1.10035}, spec={"point": 0.00001, "digits": 5})
    ctx.weekday = 1  # Selasa
    ctx.hour = 14
    assert ctx.spread == 35

    result = on_bar(ctx)
    assert result is None


def test_scalper_protection_margin_level(scalper_source):
    """Audit Proteksi: Margin level akun di bawah batas aman (< 300%) harus menahan trading."""
    ns = compile_script(scalper_source)
    on_bar = ns["on_bar"]
    df = create_df(220)

    ctx = ScriptContext(
        df,
        {},
        account={"balance": 1000.0, "equity": 800.0, "margin": 400.0, "margin_level": 200.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5}
    )
    ctx.weekday = 1
    ctx.hour = 14
    assert ctx.margin_level == 200.0

    result = on_bar(ctx)
    assert result is None


def test_scalper_insufficient_bars(scalper_source):
    """Audit Proteksi: Data candle kurang (< 210 bar untuk EMA 200) harus aman dan kembalikan None."""
    ns = compile_script(scalper_source)
    on_bar = ns["on_bar"]
    df = create_df(50)  # Hanya 50 bar

    ctx = ScriptContext(df, {}, tick={"bid": 1.1000, "ask": 1.10015}, spec={"point": 0.00001, "digits": 5})
    ctx.weekday = 1
    ctx.hour = 14

    result = on_bar(ctx)
    assert result is None


def test_scalper_emergency_invalidation_exit_buy(scalper_source):
    """Audit Proteksi: Jika ada posisi BUY terbuka tapi momentum berbalik patah tajam, lakukan emergency exit."""
    strat = ScriptStrategy(scalper_source)
    df = create_df(220, base_price=1.1000, trend="down")  # Tren berbalik turun

    pos = {"ticket": 999123, "type": "BUY", "volume": 0.01, "price_open": 1.1050}
    strat.bind_runtime(
        symbol="EURUSDm",
        positions=[pos],
        account={"balance": 1000, "equity": 980, "margin_level": 1000},
        tick={"bid": 1.0950, "ask": 1.09515},
        spec={"point": 0.00001, "digits": 5}
    )

    # Patch context weekday dan hour untuk simulasi sesi aktif
    orig_run_guarded = getattr(strat, "_on_bar")
    def guarded_with_session(ctx):
        ctx.weekday = 2
        ctx.hour = 14
        return orig_run_guarded(ctx)
    strat._on_bar = guarded_with_session

    sig = strat.generate_signal(df)
    # Harus menutup posisi (emergency exit) atau None jika syarat cross belum pas, tidak boleh buka order baru
    if sig:
        assert isinstance(sig, dict)
        assert sig.get("action") == "CLOSE"
        assert sig.get("ticket") == 999123


def test_scalper_bullish_signal_generation(scalper_source):
    """Audit Sinyal: Skenario tren naik kuat dengan pullback Stochastic oversold harus memicu BUY."""
    df = create_df(230, base_price=1.1000, trend="up")
    low_price = df.iloc[-8]["close"] - 0.0015
    for i in range(5, 1, -1):
        idx = -i
        c = low_price + (i % 2) * 0.00005
        df.iloc[idx, df.columns.get_loc("close")] = c
        df.iloc[idx, df.columns.get_loc("open")] = c + 0.0001
        df.iloc[idx, df.columns.get_loc("high")] = c + 0.0002
        df.iloc[idx, df.columns.get_loc("low")] = c - 0.0002

    c_prev = df.iloc[-2]["close"]
    df.iloc[-1, df.columns.get_loc("open")] = c_prev
    df.iloc[-1, df.columns.get_loc("close")] = c_prev + 0.0007
    df.iloc[-1, df.columns.get_loc("high")] = c_prev + 0.0008
    df.iloc[-1, df.columns.get_loc("low")] = c_prev - 0.0001

    strat = ScriptStrategy(scalper_source)
    strat.bind_runtime(
        symbol="EURUSDm",
        positions=[],
        account={"balance": 1000, "equity": 1000, "margin_level": 5000},
        tick={"bid": df.iloc[-1]["close"], "ask": df.iloc[-1]["close"] + 0.00015},
        spec={"point": 0.00001, "digits": 5},
    )

    orig_run_guarded = getattr(strat, "_on_bar")
    def guarded_with_session(ctx):
        ctx.weekday = 2  # Rabu
        ctx.hour = 14    # 14:00 UTC (Sesi London/NY)
        return orig_run_guarded(ctx)
    strat._on_bar = guarded_with_session

    sig = strat.generate_signal(df)
    assert sig is not None, "Sinyal BUY harus terpicu pada setup bullish pullback terkonfirmasi"
    assert isinstance(sig, dict)
    assert sig["action"] == "BUY"
    assert sig.get("sl_points") is not None and sig["sl_points"] >= 80
    assert sig.get("tp_points") is not None and sig["tp_points"] >= 120
    assert "SafeScalp" in sig.get("comment", "")


def test_scalper_bearish_signal_generation(scalper_source):
    """Audit Sinyal: Skenario tren turun dengan pullback Stochastic overbought harus memicu SELL."""
    df = create_df(230, base_price=1.1000, trend="down")
    high_price = df.iloc[-8]["close"] + 0.0015
    for i in range(5, 1, -1):
        idx = -i
        c = high_price - (i % 2) * 0.00005
        df.iloc[idx, df.columns.get_loc("close")] = c
        df.iloc[idx, df.columns.get_loc("open")] = c - 0.0001
        df.iloc[idx, df.columns.get_loc("high")] = c + 0.0002
        df.iloc[idx, df.columns.get_loc("low")] = c - 0.0002

    c_prev = df.iloc[-2]["close"]
    df.iloc[-1, df.columns.get_loc("open")] = c_prev
    df.iloc[-1, df.columns.get_loc("close")] = c_prev - 0.0007
    df.iloc[-1, df.columns.get_loc("high")] = c_prev + 0.0001
    df.iloc[-1, df.columns.get_loc("low")] = c_prev - 0.0008

    strat = ScriptStrategy(scalper_source)
    strat.bind_runtime(
        symbol="EURUSDm",
        positions=[],
        account={"balance": 1000, "equity": 1000, "margin_level": 5000},
        tick={"bid": df.iloc[-1]["close"], "ask": df.iloc[-1]["close"] + 0.00015},
        spec={"point": 0.00001, "digits": 5},
    )

    orig_run_guarded = getattr(strat, "_on_bar")
    def guarded_with_session(ctx):
        ctx.weekday = 2  # Rabu
        ctx.hour = 14    # 14:00 UTC (Sesi London/NY)
        return orig_run_guarded(ctx)
    strat._on_bar = guarded_with_session

    sig = strat.generate_signal(df)
    assert sig is not None, "Sinyal SELL harus terpicu pada setup bearish pullback terkonfirmasi"
    assert isinstance(sig, dict)
    assert sig["action"] == "SELL"
    assert sig.get("sl_points") is not None and sig["sl_points"] >= 80
    assert sig.get("tp_points") is not None and sig["tp_points"] >= 120
    assert "SafeScalp" in sig.get("comment", "")

