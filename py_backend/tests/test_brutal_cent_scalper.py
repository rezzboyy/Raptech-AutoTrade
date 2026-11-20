"""Unit test komprehensif untuk strategi Brutal Cent Scalper (Mode Programmer).

Memvalidasi:
1. Sandbox AST Audit & Kompilasi Skrip.
2. Ekstraksi Pengaturan SETTINGS & PARAMS.
3. Instant OP saat Start (Anti-Bengong): Langsung eksekusi pada bar pertama (BUY / SELL).
4. Active Position Lock: Menahan order baru selama ada posisi aktif.
5. True Working Recovery Engine (Martingale Cycle):
   - Kenaikan lot bertahap saat Loss.
   - Reset seketika ke Base Lot saat Profit tercapai.
6. Mode Arah Recovery: Auto Momentum, Flip Balik Arah, dan Tetap Searah.
7. Proteksi Max Recovery Steps & Lot Cap.
8. Multi-Market Auto-Scaling (Forex, Gold, Crypto, Index).
9. Filter Proteksi Spread & Margin Level.
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


@pytest.fixture
def brutal_source():
    src = load_script("brutal_cent_scalper")
    assert src, "Skrip brutal_cent_scalper harus dapat dimuat"
    return src


def create_candles(n_bars=30, base_price=1.1000, trend="up", step_size=0.0002):
    """Buat DataFrame candle sintetis sederhana."""
    times = pd.date_range("2026-10-08 10:00:00", periods=n_bars, freq="1min", tz="UTC")
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


class TestBrutalCentSafetyAndSettings:
    """Audit kompilasi, sandbox AST, dan parameter strategi."""

    def test_compilation_and_ast_sandbox(self, brutal_source):
        ns = compile_script(brutal_source)
        assert "on_bar" in ns
        assert callable(ns["on_bar"])
        assert "SETTINGS" in ns
        assert "PARAMS" in ns
        assert "STATE" in ns

    def test_settings_extraction(self, brutal_source):
        ns = compile_script(brutal_source)
        st = extract_script_settings(ns)

        assert st.get("timeframe_str") == "M1"
        assert st.get("volume") == 0.01
        assert st.get("tp_points") == 50
        assert st.get("sl_points") == 100
        assert st.get("one_trade_per_bar") is False, "one_trade_per_bar wajib False untuk kecepatan turnover brutal"
        assert st.get("max_positions") == 1


class TestInstantOpOnStart:
    """Audit Instant OP saat start: bot langsung membuka posisi tanpa bengong."""

    def test_instant_op_bullish(self, brutal_source):
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, trend="up")

        strat.bind_runtime(
            symbol="EURUSDc",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.1000, "ask": 1.10015},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is not None, "Wajib langsung membuka posisi pada bar pertama"
        assert sig["action"] == "BUY"
        assert sig["volume"] == 0.01
        assert "Brutal_B_S0" in sig["comment"]

    def test_instant_op_bearish(self, brutal_source):
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, trend="down")

        strat.bind_runtime(
            symbol="EURUSDc",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.1000, "ask": 1.10015},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is not None
        assert sig["action"] == "SELL"
        assert sig["volume"] == 0.01
        assert "Brutal_S_S0" in sig["comment"]

    def test_instant_op_minimal_candles(self, brutal_source):
        """Bahkan dengan hanya 1 candle, bot tetap langsung OP tanpa menunggu."""
        strat = ScriptStrategy(brutal_source)
        df = create_candles(1, trend="up")

        strat.bind_runtime(
            symbol="EURUSDm",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.1000, "ask": 1.10015},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is not None
        assert sig["action"] in ("BUY", "SELL")

    def test_active_position_lock(self, brutal_source):
        """Saat ada posisi aktif terbuka, jangan buka posisi dobel."""
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, trend="up")

        strat.bind_runtime(
            symbol="EURUSDc",
            positions=[{"ticket": 12345, "type": "BUY", "volume": 0.01}],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.1000, "ask": 1.10015},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is None, "Tidak boleh membuka order saat ada posisi aktif"


class TestRecoveryEngine:
    """Audit fungsi pemulihan Martingale / Cycle Recovery."""

    def test_recovery_lot_progression_on_loss(self, brutal_source):
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, trend="up")

        # 1. Trade Awal (Step 0, Base Lot 0.01)
        strat.bind_runtime(positions=[], account={"balance": 1000.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig1 = strat.generate_signal(df)
        assert sig1["volume"] == 0.01
        assert "Brutal_B_S0" in sig1["comment"]

        # 2. Simulasi Loss 1: Saldo turun dari 1000.0 ke 998.0
        strat.bind_runtime(positions=[], account={"balance": 998.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig2 = strat.generate_signal(df)
        assert sig2 is not None
        # Step 1: Base lot 0.01 * 1.75 = 0.0175 -> round to 0.02
        assert sig2["volume"] >= 0.02
        assert "S1" in sig2["comment"]

        # 3. Simulasi Loss 2: Saldo turun ke 994.5
        strat.bind_runtime(positions=[], account={"balance": 994.5}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig3 = strat.generate_signal(df)
        assert sig3 is not None
        # Step 2: lot harus bertambah lagi
        assert sig3["volume"] > sig2["volume"]
        assert "S2" in sig3["comment"]

        # 4. Simulasi Profit (Siklus Pulih): Saldo naik dari 994.5 ke 1001.0!
        strat.bind_runtime(positions=[], account={"balance": 1001.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig4 = strat.generate_signal(df)
        assert sig4 is not None
        # Wajib reset ke Base Lot 0.01!
        assert sig4["volume"] == 0.01
        assert "S0" in sig4["comment"]

    def test_max_recovery_steps_safety_reset(self, brutal_source):
        """Bila berturut-turut loss melebihi max_recovery_steps (default 5), reset ke base lot."""
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, trend="up")

        # Inisialisasi trade 0
        bal = 1000.0
        strat.bind_runtime(positions=[], account={"balance": bal}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        strat.generate_signal(df)

        # Simulasikan 5x loss berturut-turut
        for step in range(1, 6):
            bal -= 2.0
            strat.bind_runtime(positions=[], account={"balance": bal}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
            sig = strat.generate_signal(df)
            assert sig is not None
            assert f"S{step}" in sig["comment"]

        # Loss ke-6 (melebihi max_recovery_steps = 5) -> Reset ke Base Lot 0.01
        bal -= 2.0
        strat.bind_runtime(positions=[], account={"balance": bal}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig_reset = strat.generate_signal(df)
        assert sig_reset["volume"] == 0.01
        assert "S0" in sig_reset["comment"]

    def test_flip_reversal_recovery_mode(self, brutal_source):
        """Uji mode recovery 1 (Flip Reversal: jika BUY loss, berikutnya SELL)."""
        strat = ScriptStrategy(brutal_source, params={"recovery_direction_mode": 1})
        df = create_candles(20, trend="up")

        # Step 0 BUY
        strat.bind_runtime(positions=[], account={"balance": 1000.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig1 = strat.generate_signal(df)
        assert sig1["action"] == "BUY"

        # Loss -> Recovery Step 1 harus beralih FLIP ke SELL!
        strat.bind_runtime(positions=[], account={"balance": 998.0}, tick={"bid": 1.10, "ask": 1.10015}, spec={"point": 0.00001})
        sig2 = strat.generate_signal(df)
        assert sig2["action"] == "SELL"


class TestMultiMarketAutoScaling:
    """Audit penyesuaian otomatis untuk Forex, Gold, Crypto, dan Index."""

    def test_gold_market_scaling(self, brutal_source):
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, base_price=2650.0, trend="up", step_size=0.5)

        strat.bind_runtime(
            symbol="XAUUSDc",
            positions=[],
            account={"balance": 2000.0, "equity": 2000.0, "margin_level": 5000.0},
            tick={"bid": 2650.0, "ask": 2650.3},
            spec={"point": 0.01, "digits": 2},
        )

        sig = strat.generate_signal(df)
        assert sig is not None
        assert sig["tp_points"] >= 100
        assert sig["sl_points"] >= 180

    def test_crypto_market_scaling(self, brutal_source):
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20, base_price=65000.0, trend="up", step_size=20.0)

        strat.bind_runtime(
            symbol="BTCUSDm",
            positions=[],
            account={"balance": 5000.0, "equity": 5000.0, "margin_level": 5000.0},
            tick={"bid": 65000.0, "ask": 65015.0},
            spec={"point": 0.01, "digits": 2},
        )

        sig = strat.generate_signal(df)
        assert sig is not None
        assert sig["tp_points"] >= 3000
        assert sig["sl_points"] >= 5000


class TestSafetyFilters:
    """Audit proteksi filter spread dan margin level."""

    def test_spread_protection(self, brutal_source):
        strat = ScriptStrategy(brutal_source, params={"max_spread": 40})
        df = create_candles(20)

        # Spread 60 pts > max 40 pts
        strat.bind_runtime(
            symbol="EURUSDc",
            positions=[],
            account={"balance": 1000.0, "equity": 1000.0, "margin_level": 5000.0},
            tick={"bid": 1.1000, "ask": 1.10060},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is None, "Order harus ditahan jika spread melebihi batas aman"

    def test_margin_level_protection(self, brutal_source):
        strat = ScriptStrategy(brutal_source)
        df = create_candles(20)

        # Margin level 120% (< 150%)
        strat.bind_runtime(
            symbol="EURUSDc",
            positions=[],
            account={"balance": 1000.0, "equity": 600.0, "margin_level": 120.0},
            tick={"bid": 1.1000, "ask": 1.10015},
            spec={"point": 0.00001, "digits": 5},
        )

        sig = strat.generate_signal(df)
        assert sig is None, "Order harus ditahan jika margin level di bawah batas aman"
