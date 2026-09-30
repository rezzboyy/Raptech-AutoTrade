"""Audit dan pengujian komprehensif untuk strategi Fast Cycle & Adaptive Market Recovery."""

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
def recovery_source():
    src = load_script("fast_cycle_recovery")
    assert src, "Skrip fast_cycle_recovery tidak boleh kosong"
    return src


def create_df(n_bars=60, base_price=1.1000, trend="up"):
    """Buat DataFrame candle sintetis sederhana."""
    times = pd.date_range("2026-09-24 10:00:00", periods=n_bars, freq="1min", tz="UTC")
    closes = []
    opens = []
    highs = []
    lows = []
    vols = []

    price = base_price
    for i in range(n_bars):
        step = 0.00010 if trend == "up" else -0.00010
        op = price
        cl = price + step
        hi = max(op, cl) + 0.00005
        lo = min(op, cl) - 0.00005
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


def test_compilation_and_ast_sandbox(recovery_source):
    """Pastikan skrip lolos audit keamanan AST sandbox."""
    ns = compile_script(recovery_source)
    assert "on_bar" in ns
    assert callable(ns["on_bar"])
    assert "SETTINGS" in ns
    assert "PARAMS" in ns
    assert "STATE" in ns


def test_settings_extraction(recovery_source):
    """Pastikan SETTINGS terdeteksi dan diekstrak dengan akurat."""
    ns = compile_script(recovery_source)
    settings = extract_script_settings(ns)

    assert settings.get("symbol") == "BTCUSDm"
    assert settings.get("timeframe_str") == "M1"
    assert settings.get("volume") == 0.01
    assert settings.get("sl_points") == 150
    assert settings.get("tp_points") == 100
    assert settings.get("trailing_stop_enabled") is True
    assert settings.get("trailing_stop_points") == 80
    assert settings.get("break_even_enabled") is True
    assert settings.get("break_even_points") == 60
    assert settings.get("max_spread_points") == 2500
    assert settings.get("max_positions") == 1


def test_initial_fast_entry_buy(recovery_source):
    """Audit: Saat trading dimulai dan pasar bullish/netral, langsung buka BUY cepat."""
    strat = ScriptStrategy(recovery_source)
    df = create_df(40, trend="up")

    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )

    sig = strat.generate_signal(df)
    assert sig is not None, "Harus langsung menghasilkan sinyal masuk cepat"
    assert sig.get("action") == "BUY"
    assert sig.get("volume") == 0.01
    assert sig.get("tp_points") == 100
    assert sig.get("sl_points") == 150


def test_adaptive_direction_sell(recovery_source):
    """Audit: Jika kondisi tren pasar turun (Close < EMA 20), arah adaptif memilih SELL."""
    strat = ScriptStrategy(recovery_source)
    df = create_df(40, trend="down")  # Tren menurun tajam

    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )

    sig = strat.generate_signal(df)
    assert sig is not None
    assert sig.get("action") == "SELL", "Arah adaptif harus beralih ke SELL saat pasar bearish"
    assert sig.get("volume") == 0.01


def test_active_position_lock(recovery_source):
    """Audit: Jika sedang ada posisi terbuka di siklus ini, jangan buka posisi ganda."""
    strat = ScriptStrategy(recovery_source)
    df = create_df(40, trend="up")

    pos = {"ticket": 12345, "type": "BUY", "volume": 0.01}
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[pos],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )

    sig = strat.generate_signal(df)
    assert sig is None, "Tidak boleh membuka posisi baru selama ada posisi aktif"


def test_loss_recovery_stepping_and_reset(recovery_source):
    """Audit: Uji kenaikan lot saat Loss dan reset ke Base Lot saat Win."""
    strat = ScriptStrategy(recovery_source)
    df = create_df(40, trend="up")

    # 1. Order Pertama (Base Lot 0.01, saldo 1000)
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )
    sig1 = strat.generate_signal(df)
    assert sig1["volume"] == 0.01

    # 2. Simulasi Posisi Selesai LOSS: Saldo turun dari 1000 menjadi 998.80
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 998.80, "equity": 998.80, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )
    sig2 = strat.generate_signal(df)
    # Step 1: Base lot 0.01 * 2.0^1 = 0.02 lot
    assert sig2 is not None
    assert sig2["volume"] == 0.02
    assert "FastRec_B1" in sig2["comment"]

    # 3. Simulasi Posisi Selesai LOSS Lagi: Saldo turun menjadi 996.40
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 996.40, "equity": 996.40, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )
    sig3 = strat.generate_signal(df)
    # Step 2: Base lot 0.01 * 2.0^2 = 0.04 lot
    assert sig3 is not None
    assert sig3["volume"] == 0.04
    assert "FastRec_B2" in sig3["comment"]

    # 4. Simulasi Posisi Selesai PROFIT (Recovery Sukses): Saldo naik menjadi 1000.40
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.40, "equity": 1000.40, "margin_level": 5000.0},
        tick={"bid": 1.1000, "ask": 1.10015},
        spec={"point": 0.00001, "digits": 5},
    )
    sig4 = strat.generate_signal(df)
    # Reset kembali ke Base Lot 0.01
    assert sig4 is not None
    assert sig4["volume"] == 0.01
    assert "FastRec_B0" in sig4["comment"]


def test_max_recovery_step_safety_cap(recovery_source):
    """Audit: Jika berturut-turut loss melebihi max_steps, wajib reset ke base lot demi keamanan."""
    strat = ScriptStrategy(recovery_source)
    df = create_df(40, trend="up")

    # Trade awal saldo 1000
    strat.bind_runtime(positions=[], account={"balance": 1000.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
    strat.generate_signal(df)

    # Loss 1
    strat.bind_runtime(positions=[], account={"balance": 998.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
    sig1 = strat.generate_signal(df)
    assert sig1["volume"] == 0.02

    # Loss 2
    strat.bind_runtime(positions=[], account={"balance": 995.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
    sig2 = strat.generate_signal(df)
    assert sig2["volume"] == 0.04

    # Loss 3
    strat.bind_runtime(positions=[], account={"balance": 990.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
    sig3 = strat.generate_signal(df)
    assert sig3["volume"] == 0.08

    # Loss 4 (melebihi default max_recovery_steps = 3) -> Wajib reset ke base lot 0.01
    strat.bind_runtime(positions=[], account={"balance": 980.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
    sig4 = strat.generate_signal(df)
    assert sig4["volume"] == 0.01, "Harus reset ke base lot untuk melindungi akun dari drawdown liar"


def test_safety_filters(recovery_source):
    """Audit: Proteksi spread dan margin level, serta kesiapan 24/7 di akhir pekan."""
    strat = ScriptStrategy(recovery_source)
    df = create_df(40)

    # 1. Weekend ready: Pada hari Sabtu/Minggu, order tetap boleh masuk (24/7 Crypto support)
    ctx_sat = ScriptContext(df, {}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
    ctx_sat.weekday = 5
    ctx_sat.hour = 12
    sig_sat = strat._on_bar(ctx_sat)
    assert sig_sat is not None, "Strategi harus siap eksekusi instan kapan pun termasuk akhir pekan"

    # 2. Spread melebar ekstrem (> 100 pts) harus diblokir
    ctx_sp = ScriptContext(df, {"max_spread": 100}, tick={"bid": 1.10, "ask": 1.10150}, spec={"point": 0.00001})
    assert ctx_sp.spread == 150  # 150 pts > max_spread 100
    assert strat._on_bar(ctx_sp) is None

    # 3. Margin level kritis (< 150%) harus diblokir
    ctx_mg = ScriptContext(
        df,
        {},
        account={"balance": 1000.0, "margin": 800.0, "margin_level": 125.0},
        tick={"bid": 1.10, "ask": 1.10015},
        spec={"point": 0.00001}
    )
    assert strat._on_bar(ctx_mg) is None


def test_crypto_high_value_adaptive_stops(recovery_source):
    """Audit: Pada aset crypto (BTCUSDm harga ~$84k, spread ~1000 pts), SL/TP otomatis beradaptasi."""
    strat = ScriptStrategy(recovery_source)
    df_btc = create_df(40, base_price=84250.0, trend="up")

    # Simulasi kondisi live Exness BTCUSDm: spread = 1000 pts, point = 0.01
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2, "stop_level": 0},
    )

    sig = strat.generate_signal(df_btc)
    assert sig is not None, "Harus langsung open order pada BTCUSDm tanpa terblokir filter spread"
    assert sig.get("action") == "BUY"
    assert sig.get("volume") == 0.01
    # Jarak SL dan TP harus otomatis disesuaikan di atas spread 1000 pts
    assert sig.get("sl_points") >= 2500, "SL harus lebih besar dari spread BTCUSDm agar tidak Invalid stops"
    assert sig.get("tp_points") >= 1800, "TP harus lebih besar dari spread BTCUSDm agar tidak Invalid stops"


