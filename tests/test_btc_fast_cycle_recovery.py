"""Audit dan pengujian komprehensif untuk strategi BTC Fast Scalper & Adaptive Recovery."""

import pytest
import pandas as pd

from strategies.script_runtime import (
    compile_script,
    extract_script_settings,
    ScriptStrategy,
    ScriptContext,
    load_script,
)


@pytest.fixture
def btc_source():
    src = load_script("btc_fast_cycle_recovery")
    assert src, "Skrip btc_fast_cycle_recovery tidak boleh kosong"
    return src


def create_df(n_bars=60, base_price=84250.0, trend="up"):
    """Buat DataFrame candle sintetis skala harga Bitcoin."""
    times = pd.date_range("2026-09-27 08:00:00", periods=n_bars, freq="1min", tz="UTC")
    closes = []
    opens = []
    highs = []
    lows = []
    vols = []

    price = base_price
    for i in range(n_bars):
        step = 15.0 if trend == "up" else -15.0
        op = price
        cl = price + step
        hi = max(op, cl) + 5.0
        lo = min(op, cl) - 5.0
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


def test_compilation_and_ast_sandbox(btc_source):
    """Pastikan skrip btc_fast_cycle_recovery lolos audit AST sandbox tanpa pelanggaran."""
    ns = compile_script(btc_source)
    assert "on_bar" in ns
    assert callable(ns["on_bar"])
    assert "SETTINGS" in ns
    assert "PARAMS" in ns
    assert "STATE" in ns


def test_btc_settings_extraction(btc_source):
    """Pastikan seluruh konfigurasi SETTINGS bernilai tepat untuk instrumen Bitcoin."""
    ns = compile_script(btc_source)
    settings = extract_script_settings(ns)

    assert settings.get("symbol") == "BTCUSDm"
    assert settings.get("timeframe_str") == "M1"
    assert settings.get("volume") == 0.01
    assert settings.get("sl_points") == 4500
    assert settings.get("tp_points") == 3000
    assert settings.get("break_even_enabled") is True
    assert settings.get("break_even_points") == 1800
    assert settings.get("break_even_offset_points") == 400
    assert settings.get("trailing_stop_enabled") is True
    assert settings.get("trailing_stop_points") == 2500
    assert settings.get("trailing_step_points") == 500
    assert settings.get("max_spread_points") == 3500
    assert settings.get("max_positions") == 1
    assert settings.get("one_trade_per_bar") is False


def test_instant_entry_btc(btc_source):
    """Audit: Saat auto-trading dimulai, order BTC langsung terbuka di bar pertama."""
    strat = ScriptStrategy(btc_source)
    df = create_df(40, trend="up")

    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )

    sig = strat.generate_signal(df)
    assert sig is not None, "Harus menghasilkan sinyal masuk instan"
    assert sig.get("action") == "BUY"
    assert sig.get("volume") == 0.01
    assert sig.get("tp_points") >= 3000
    assert sig.get("sl_points") >= 4500
    assert "BTCRec_B0" in sig.get("comment", "")


def test_adaptive_direction_btc_trend(btc_source):
    """Audit: Jika momentum pasar BTC bearish (Close < EMA 20), arah otomatis SELL."""
    strat = ScriptStrategy(btc_source)
    df = create_df(40, trend="down")

    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )

    sig = strat.generate_signal(df)
    assert sig is not None
    assert sig.get("action") == "SELL"
    assert sig.get("volume") == 0.01
    assert "BTCRec_S0" in sig.get("comment", "")


def test_active_position_gate(btc_source):
    """Audit: Tidak boleh membuka posisi duplikat bila posisi saat ini masih aktif."""
    strat = ScriptStrategy(btc_source)
    df = create_df(40, trend="up")

    pos = {"ticket": 999999, "type": "BUY", "volume": 0.01}
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[pos],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )

    sig = strat.generate_signal(df)
    assert sig is None, "Wajib menunggu sampai posisi aktif tertutup"


def test_loss_recovery_stepping_and_reset(btc_source):
    """Audit: Pengujian kenaikan lot saat Loss dan reset ke Base Lot saat Profit."""
    strat = ScriptStrategy(btc_source)
    df = create_df(40, trend="up")

    # 1. Order Pertama (Base Lot 0.01, saldo 1000)
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )
    sig1 = strat.generate_signal(df)
    assert sig1["volume"] == 0.01
    assert "BTCRec_B0" in sig1["comment"]

    # 2. Posisi selesai LOSS (Saldo turun dari 1000 menjadi 995.50)
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 995.50, "equity": 995.50, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )
    sig2 = strat.generate_signal(df)
    # Step 1: Base lot 0.01 * 2.0^1 = 0.02 lot
    assert sig2 is not None
    assert sig2["volume"] == 0.02
    assert "BTCRec_B1" in sig2["comment"]

    # 3. Posisi kedua LOSS lagi (Saldo turun menjadi 986.50)
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 986.50, "equity": 986.50, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )
    sig3 = strat.generate_signal(df)
    # Step 2: Base lot 0.01 * 2.0^2 = 0.04 lot
    assert sig3 is not None
    assert sig3["volume"] == 0.04
    assert "BTCRec_B2" in sig3["comment"]

    # 4. Posisi ketiga PROFIT (Saldo naik menjadi 1005.00)
    strat.bind_runtime(
        symbol="BTCUSDm",
        positions=[],
        account={"balance": 1005.00, "equity": 1005.00, "margin_level": 5000.0},
        tick={"bid": 84250.00, "ask": 84260.00},
        spec={"point": 0.01, "digits": 2},
    )
    sig4 = strat.generate_signal(df)
    # Recovery berhasil -> Reset kembali ke Base Lot 0.01
    assert sig4 is not None
    assert sig4["volume"] == 0.01
    assert "BTCRec_B0" in sig4["comment"]


def test_max_recovery_step_safety_cap(btc_source):
    """Audit: Bila berturut-turut loss melebihi max_steps, wajib reset ke base lot."""
    strat = ScriptStrategy(btc_source)
    df = create_df(40, trend="up")

    # Inisialisasi awal
    strat.bind_runtime(positions=[], account={"balance": 1000.0}, tick={"bid": 84250.0, "ask": 84260.0}, spec={"point": 0.01, "digits": 2})
    strat.generate_signal(df)

    # Loss 1
    strat.bind_runtime(positions=[], account={"balance": 990.0}, tick={"bid": 84250.0, "ask": 84260.0}, spec={"point": 0.01, "digits": 2})
    sig1 = strat.generate_signal(df)
    assert sig1["volume"] == 0.02

    # Loss 2
    strat.bind_runtime(positions=[], account={"balance": 970.0}, tick={"bid": 84250.0, "ask": 84260.0}, spec={"point": 0.01, "digits": 2})
    sig2 = strat.generate_signal(df)
    assert sig2["volume"] == 0.04

    # Loss 3
    strat.bind_runtime(positions=[], account={"balance": 930.0}, tick={"bid": 84250.0, "ask": 84260.0}, spec={"point": 0.01, "digits": 2})
    sig3 = strat.generate_signal(df)
    assert sig3["volume"] == 0.08

    # Loss 4 (melebihi default max_recovery_steps = 3) -> Reset ke base lot
    strat.bind_runtime(positions=[], account={"balance": 850.0}, tick={"bid": 84250.0, "ask": 84260.0}, spec={"point": 0.01, "digits": 2})
    sig4 = strat.generate_signal(df)
    assert sig4["volume"] == 0.01, "Wajib reset ke base lot setelah melewati max_recovery_steps"


def test_reversal_on_loss_direction_mode(btc_source):
    """Audit: Mode arah 2 (Reversal on Loss) membalik arah order saat mengalami loss."""
    strat = ScriptStrategy(btc_source, params={"direction_mode": 2})
    df = create_df(40, trend="up")

    # Set direction_mode = 2 (Reversal on Loss)
    # 1. Order Pertama BUY (Saldo 1000)
    strat.bind_runtime(
        positions=[],
        account={"balance": 1000.0},
        tick={"bid": 84250.0, "ask": 84260.0},
        spec={"point": 0.01, "digits": 2},
    )
    sig1 = strat.generate_signal(df)
    assert sig1["action"] == "BUY"

    # 2. Posisi BUY selesai LOSS -> Order recovery otomatis berbalik arah menjadi SELL!
    strat.bind_runtime(
        positions=[],
        account={"balance": 995.0},
        tick={"bid": 84250.0, "ask": 84260.0},
        spec={"point": 0.01, "digits": 2},
    )
    sig2 = strat.generate_signal(df)
    assert sig2["action"] == "SELL", "Saat direction_mode=2 dan trade BUY loss, recovery harus balik ke SELL"
    assert sig2["volume"] == 0.02


def test_anti_invalid_stops_scaling(btc_source):
    """Audit: Skala SL/TP selalu mematuhi batas aman stops-level & spread BTC (bebas Error #10016)."""
    strat = ScriptStrategy(btc_source)
    df = create_df(40)

    # Skenario spread melebar hingga 1500 pts pada BTC
    ctx = ScriptContext(
        df,
        {"tp_points": 2000, "sl_points": 3000},  # User pasang parameter terlalu sempit
        tick={"bid": 84250.0, "ask": 84265.0},   # spread = 1500 pts ($15.00)
        spec={"point": 0.01, "digits": 2},
    )
    sig = strat._on_bar(ctx)
    assert sig is not None
    # tp_pts harus di-clamp: max(2000, 1500 * 2.0 = 3000, 2500) = 3000 pts
    assert sig["tp_points"] >= 3000
    # sl_pts harus di-clamp: max(3000, 1500 * 3.0 = 4500, 4000) = 4500 pts
    assert sig["sl_points"] >= 4500
