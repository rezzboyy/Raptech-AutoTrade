"""Audit dan unit test komprehensif untuk XAU Fast Scalper Pro (Soft Multi Recovery)."""

import pytest
import pandas as pd
import numpy as np

from strategies.script_runtime import (
    compile_script,
    extract_script_settings,
    ScriptStrategy,
    ScriptContext,
    load_script,
)


@pytest.fixture
def xau_source():
    src = load_script("xau_fast_scalper")
    assert src, "Skrip xau_fast_scalper tidak boleh kosong"
    return src


def create_df(n_bars=60, base_price=2650.0, trend="up"):
    """Buat DataFrame candle sintetis XAUUSD."""
    times = pd.date_range("2026-10-05 10:00:00", periods=n_bars, freq="1min", tz="UTC")
    closes = []
    opens = []
    highs = []
    lows = []
    vols = []

    price = base_price
    for i in range(n_bars):
        step = 0.50 if trend == "up" else -0.50
        op = price
        cl = price + step
        hi = max(op, cl) + 0.25
        lo = min(op, cl) - 0.25
        opens.append(op)
        closes.append(cl)
        highs.append(hi)
        lows.append(lo)
        vols.append(150.0)
        price = cl

    return pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols,
    }, index=times)


def test_compilation_and_ast_sandbox(xau_source):
    """Audit: Skrip lolos validasi keamanan AST sandbox (tanpa import berbahaya, dunder, dsb)."""
    ns = compile_script(xau_source)
    assert "on_bar" in ns
    assert callable(ns["on_bar"])
    assert "SETTINGS" in ns
    assert "PARAMS" in ns
    assert "STATE" in ns


def test_settings_extraction(xau_source):
    """Audit: Pengaturan SETTINGS teridentifikasi dan diekstrak dengan akurat."""
    ns = compile_script(xau_source)
    st = extract_script_settings(ns)

    assert st.get("symbol") == "XAUUSDm"
    assert st.get("timeframe_str") == "M1"
    assert st.get("volume") == 0.01
    assert st.get("sl_points") == 180
    assert st.get("tp_points") == 120
    assert st.get("trailing_stop_enabled") is True
    assert st.get("trailing_stop_points") == 80
    assert st.get("trailing_step_points") == 20
    assert st.get("break_even_enabled") is True
    assert st.get("break_even_points") == 60
    assert st.get("break_even_offset_points") == 15
    assert st.get("max_spread_points") == 60
    assert st.get("max_positions") == 1


def test_instant_fast_trigger_buy(xau_source):
    """Audit: Saat bot aktif dan pasar bullish, langsung buka posisi BUY tanpa lama menunggu."""
    strat = ScriptStrategy(xau_source)
    df = create_df(30, trend="up")

    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )

    sig = strat.generate_signal(df)
    assert sig is not None, "Harus langsung open posisi (anti-bengong)"
    assert sig.get("action") == "BUY"
    assert sig.get("volume") == 0.01
    assert sig.get("tp_points") == 120
    assert sig.get("sl_points") == 180


def test_instant_fast_trigger_sell(xau_source):
    """Audit: Saat pasar bearish (Close < EMA 9), arah responsif memilih SELL instan."""
    strat = ScriptStrategy(xau_source)
    df = create_df(30, trend="down")

    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )

    sig = strat.generate_signal(df)
    assert sig is not None
    assert sig.get("action") == "SELL"
    assert sig.get("volume") == 0.01


def test_active_position_lock(xau_source):
    """Audit: Jika ada posisi aktif berjalan, jangan membuka posisi dobel."""
    strat = ScriptStrategy(xau_source)
    df = create_df(30, trend="up")

    pos = {"ticket": 998811, "type": "BUY", "volume": 0.01}
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[pos],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )

    sig = strat.generate_signal(df)
    assert sig is None, "Tidak boleh membuka posisi baru ketika ada posisi aktif"


def test_soft_multiplier_recovery_progression_and_reset(xau_source):
    """Audit: Uji kenaikan lot lembut (soft progression) saat loss dan reset ke base lot saat profit."""
    strat = ScriptStrategy(xau_source)
    df = create_df(30, trend="up")

    # 1. Order Pertama (Base Lot: 0.01, Saldo awal 1000.00)
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 1000.00, "equity": 1000.00, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )
    sig0 = strat.generate_signal(df)
    assert sig0["volume"] == 0.01
    assert "XAU_Fast_B0" in sig0["comment"]

    # 2. Posisi selesai LOSS 1: Saldo turun menjadi 998.20
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 998.20, "equity": 998.20, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )
    sig1 = strat.generate_signal(df)
    assert sig1["volume"] == 0.02
    assert "XAU_Fast_B1" in sig1["comment"]

    # 3. Posisi selesai LOSS 2: Saldo turun menjadi 994.60
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 994.60, "equity": 994.60, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )
    sig2 = strat.generate_signal(df)
    assert sig2["volume"] == 0.02
    assert "XAU_Fast_B2" in sig2["comment"]

    # 4. Posisi selesai LOSS 3: Saldo turun menjadi 991.00
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 991.00, "equity": 991.00, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )
    sig3 = strat.generate_signal(df)
    assert sig3["volume"] == 0.03
    assert "XAU_Fast_B3" in sig3["comment"]

    # 5. Posisi selesai PROFIT (Recovery Berhasil): Saldo naik menjadi 1002.50
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[],
        account={"balance": 1002.50, "equity": 1002.50, "margin_level": 3000.0},
        tick={"bid": 2650.00, "ask": 2650.25},
        spec={"point": 0.01, "digits": 2},
    )
    sig_reset = strat.generate_signal(df)
    assert sig_reset["volume"] == 0.01, "Setelah profit, lot harus langsung reset ke Base Lot (0.01)"
    assert "XAU_Fast_B0" in sig_reset["comment"]


def test_max_recovery_safety_cap(xau_source):
    """Audit: Jika berturut-turut loss melebihi max_steps, wajib reset ke base lot demi keamanan."""
    strat = ScriptStrategy(xau_source)
    df = create_df(30, trend="up")

    # Start
    strat.bind_runtime(positions=[], account={"balance": 1000.0}, tick={"bid": 2650.0, "ask": 2650.25}, spec={"point": 0.01})
    strat.generate_signal(df)

    # Loss 1 -> 0.02
    strat.bind_runtime(positions=[], account={"balance": 998.0}, tick={"bid": 2650.0, "ask": 2650.25}, spec={"point": 0.01})
    s1 = strat.generate_signal(df)
    assert s1["volume"] == 0.02

    # Loss 2 -> 0.02
    strat.bind_runtime(positions=[], account={"balance": 994.0}, tick={"bid": 2650.0, "ask": 2650.25}, spec={"point": 0.01})
    s2 = strat.generate_signal(df)
    assert s2["volume"] == 0.02

    # Loss 3 -> 0.03
    strat.bind_runtime(positions=[], account={"balance": 990.0}, tick={"bid": 2650.0, "ask": 2650.25}, spec={"point": 0.01})
    s3 = strat.generate_signal(df)
    assert s3["volume"] == 0.03

    # Loss 4 -> 0.04
    strat.bind_runtime(positions=[], account={"balance": 985.0}, tick={"bid": 2650.0, "ask": 2650.25}, spec={"point": 0.01})
    s4 = strat.generate_signal(df)
    assert s4["volume"] == 0.04

    # Loss 5 (melebihi max_recovery_steps = 4) -> Harus reset ke base lot 0.01!
    strat.bind_runtime(positions=[], account={"balance": 978.0}, tick={"bid": 2650.0, "ask": 2650.25}, spec={"point": 0.01})
    s5 = strat.generate_signal(df)
    assert s5["volume"] == 0.01, "Wajib reset ke base lot demi mencegah drawdown bengkak"


def test_spread_and_margin_protection(xau_source):
    """Audit: Proteksi spread melebar dan margin level kritis pada XAU."""
    strat = ScriptStrategy(xau_source)
    df = create_df(30)

    # 1. Spread melebar (misal 90 pts > max_spread 60) -> Blokir order
    ctx_sp = ScriptContext(df, {"max_spread": 60}, tick={"bid": 2650.0, "ask": 2650.90}, spec={"point": 0.01})
    assert ctx_sp.spread == 90
    assert strat._on_bar(ctx_sp) is None

    # 2. Margin level tipis (< 200%) -> Blokir order
    ctx_mg = ScriptContext(
        df,
        {},
        account={"balance": 1000.0, "equity": 1000.0, "margin": 600.0, "margin_level": 166.0},
        tick={"bid": 2650.0, "ask": 2650.25},
        spec={"point": 0.01},
    )
    assert strat._on_bar(ctx_mg) is None
