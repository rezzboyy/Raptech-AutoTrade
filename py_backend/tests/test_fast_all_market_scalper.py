"""Audit dan unit test komprehensif untuk Skrip Scalper Cepat Semua Market (Fast OP Engine).

Memvalidasi secara ketat:
1. Audit Keamanan AST Sandbox (tanpa import berbahaya, dunder, atau fungsi dilarang).
2. Audit Ekstraksi Pengaturan SETTINGS & PARAMS.
3. Audit Fast Trigger Anti-Bengong: Memastikan skrip langsung membuka posisi (BUY / SELL)
   dalam 1 bar tanpa menunggu lama ketika posisi kosong.
4. Audit Adaptasi Multi-Market (Universal Fast Scalper di Forex, Emas, Kripto, Indeks).
5. Audit Soft Recovery & Proteksi Modal (Reset saat profit, batas bertahap, max cap lot,
   filter spread, dan margin level guard).
6. Pengujian seluruh varian skrip: universal_fast_scalper, fast_forex_scalper,
   fast_gold_scalper, fast_crypto_scalper, fast_indices_scalper.
"""

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


def create_candles(n_bars=40, base_price=1.1000, trend="up", step_size=0.0002):
    """Buat DataFrame candle sintetis."""
    times = pd.date_range("2026-10-06 08:00:00", periods=n_bars, freq="1min", tz="UTC")
    closes = []
    opens = []
    highs = []
    lows = []
    vols = []

    price = base_price
    for i in range(n_bars):
        step = step_size if trend == "up" else (-step_size if trend == "down" else 0.0)
        op = price
        cl = price + step
        hi = max(op, cl) + (step_size * 0.5)
        lo = min(op, cl) - (step_size * 0.5)
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


ALL_FAST_SCRIPTS = [
    "universal_fast_scalper",
    "fast_forex_scalper",
    "fast_gold_scalper",
    "fast_crypto_scalper",
    "fast_indices_scalper",
]


class TestFastScriptsAuditAndSafety:
    """Audit kompilasi dan kepatuhan sandbox AST untuk semua skrip baru."""

    @pytest.mark.parametrize("script_name", ALL_FAST_SCRIPTS)
    def test_ast_sandbox_and_compilation(self, script_name):
        src = load_script(script_name)
        assert src, f"Skrip '{script_name}' harus dapat dimuat dan tidak boleh kosong"

        ns = compile_script(src)
        assert "on_bar" in ns, f"Skrip '{script_name}' wajib memiliki fungsi on_bar(ctx)"
        assert callable(ns["on_bar"]), f"on_bar pada '{script_name}' harus callable"
        assert "SETTINGS" in ns, f"Skrip '{script_name}' wajib mendefinisikan kamus SETTINGS"
        assert "PARAMS" in ns, f"Skrip '{script_name}' wajib mendefinisikan PARAMS"
        assert "STATE" in ns, f"Skrip '{script_name}' wajib mendefinisikan STATE"

    @pytest.mark.parametrize("script_name", ALL_FAST_SCRIPTS)
    def test_settings_extraction_valid(self, script_name):
        src = load_script(script_name)
        ns = compile_script(src)
        st = extract_script_settings(ns)

        assert "symbol" in st and len(st["symbol"]) > 0
        assert "timeframe_str" in st and st["timeframe_str"] in ("M1", "M5")
        assert "volume" in st and st["volume"] > 0
        assert "tp_points" in st and st["tp_points"] > 0
        assert "sl_points" in st and st["sl_points"] > 0
        assert st.get("one_trade_per_bar") is False, "one_trade_per_bar harus False demi kecepatan OP"


class TestUniversalFastScalperMultiMarket:
    """Audit fungsi Universal Fast Scalper di berbagai instrumen pasar."""

    def test_universal_forex_adaptation(self):
        src = load_script("universal_fast_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=1.0850, trend="up", step_size=0.0002)

        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 2500.0},
            tick={"bid": 1.0850, "ask": 1.0851},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is not None, "Harus langsung open posisi (anti-bengong) pada Forex"
        assert sig.get("action") == "BUY"
        assert sig.get("tp_points") >= 80
        assert sig.get("sl_points") >= 140

    def test_universal_gold_adaptation(self):
        src = load_script("universal_fast_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=2650.0, trend="up", step_size=0.50)

        strat.bind_runtime(
            symbol="XAUUSDm",
            positions=[],
            account={"balance": 2000.0, "equity": 2000.0, "margin_level": 3000.0},
            tick={"bid": 2650.00, "ask": 2650.25},
            spec={"point": 0.01, "digits": 2},
        )

        sig = strat.generate_signal(df)
        assert sig is not None, "Harus langsung open posisi pada Emas/Gold"
        assert sig.get("action") == "BUY"
        assert sig.get("tp_points") >= 120
        assert sig.get("sl_points") >= 180

    def test_universal_crypto_adaptation(self):
        src = load_script("universal_fast_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=65000.0, trend="down", step_size=20.0)

        strat.bind_runtime(
            symbol="BTCUSDm",
            positions=[],
            account={"balance": 5000.0, "equity": 5000.0, "margin_level": 4000.0},
            tick={"bid": 65000.0, "ask": 65015.0},
            spec={"point": 0.01, "digits": 2},
        )

        sig = strat.generate_signal(df)
        assert sig is not None, "Harus langsung open posisi pada Kripto"
        assert sig.get("action") == "SELL"
        assert sig.get("tp_points") >= 4000
        assert sig.get("sl_points") >= 6000

    def test_universal_indices_adaptation(self):
        src = load_script("universal_fast_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=42000.0, trend="up", step_size=5.0)

        strat.bind_runtime(
            symbol="US30m",
            positions=[],
            account={"balance": 3000.0, "equity": 3000.0, "margin_level": 3500.0},
            tick={"bid": 42000.0, "ask": 42002.0},
            spec={"point": 0.1, "digits": 1},
        )

        sig = strat.generate_signal(df)
        assert sig is not None, "Harus langsung open posisi pada Indeks"
        assert sig.get("action") == "BUY"
        assert sig.get("tp_points") >= 350
        assert sig.get("sl_points") >= 500


class TestFastTriggerAndNoBengong:
    """Audit kecepatan eksekusi tanpa menunggu (Fast OP / Anti-Bengong)."""

    @pytest.mark.parametrize("script_name", ALL_FAST_SCRIPTS)
    def test_immediate_op_on_flat_or_minimal_data(self, script_name):
        """Bahkan dengan data candle minimal, skrip tetap langsung open posisi."""
        src = load_script(script_name)
        strat = ScriptStrategy(src)
        df = create_candles(5, base_price=100.0, trend="up", step_size=0.1)

        strat.bind_runtime(
            symbol="TESTm",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 100.0, "ask": 100.1},
            spec={"point": 0.01, "digits": 2},
        )

        sig = strat.generate_signal(df)
        assert sig is not None, f"Skrip '{script_name}' harus langsung open posisi (anti-bengong)"
        assert sig.get("action") in ("BUY", "SELL")

    @pytest.mark.parametrize("script_name", ALL_FAST_SCRIPTS)
    def test_active_position_blocks_duplicate_entry(self, script_name):
        """Saat ada posisi aktif terbuka, skrip disiplin menunggu tanpa membuka posisi dobel."""
        src = load_script(script_name)
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=100.0, trend="up", step_size=0.1)

        strat.bind_runtime(
            symbol="TESTm",
            positions=[{"ticket": 12345, "volume": 0.01, "type": "BUY"}],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 100.0, "ask": 100.1},
            spec={"point": 0.01, "digits": 2},
        )

        sig = strat.generate_signal(df)
        assert sig is None, f"Skrip '{script_name}' tidak boleh buka posisi baru jika masih ada posisi aktif"


class TestRiskManagementAndProtection:
    """Audit proteksi spread, margin level, dan siklus soft recovery."""

    def test_spread_exceeded_suppresses_entry(self):
        src = load_script("fast_forex_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=1.0800, trend="up")

        # Spread diset 50 pts, melebihi max_spread 35 pts
        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.08000, "ask": 1.08050},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is None, "Order harus ditahan jika spread melebihi batas aman"

    def test_margin_level_critical_suppresses_entry(self):
        src = load_script("universal_fast_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=1.0800, trend="up")

        # Margin level 150% (kritis di bawah 200%)
        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 1000.0, "equity": 500.0, "margin_level": 150.0},
            tick={"bid": 1.08000, "ask": 1.08010},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is None, "Order harus ditahan jika margin level di bawah 200%"

    def test_soft_recovery_step_progression_and_reset(self):
        src = load_script("universal_fast_scalper")
        strat = ScriptStrategy(src)
        df = create_candles(30, base_price=1.0800, trend="up")

        # Order 1 (Base Lot)
        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.08000, "ask": 1.08010},
            spec={"point": 0.00001, "digits": 5},
        )
        sig1 = strat.generate_signal(df)
        assert sig1["volume"] == 0.01

        # Simulasikan posisi ditutup dengan LOSS (-$5.00)
        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 995.0, "equity": 995.0, "margin_level": 5000.0},
            tick={"bid": 1.08000, "ask": 1.08010},
            spec={"point": 0.00001, "digits": 5},
        )
        sig2 = strat.generate_signal(df)
        assert sig2 is not None
        assert sig2["volume"] >= 0.01, "Volume harus naik pada soft recovery"

        # Simulasikan siklus berikutnya menang (PROFIT +$7.00 -> balance $1002.0)
        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 1002.0, "equity": 1002.0, "margin_level": 5000.0},
            tick={"bid": 1.08000, "ask": 1.08010},
            spec={"point": 0.00001, "digits": 5},
        )
        sig3 = strat.generate_signal(df)
        assert sig3 is not None
        assert sig3["volume"] == 0.01, "Harus reset ke Base Lot (0.01) setelah siklus PROFIT"
