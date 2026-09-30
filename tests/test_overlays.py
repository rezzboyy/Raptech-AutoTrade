"""Uji compute_overlays: strategi harga menghasilkan garis selaras candle."""

import unittest
import numpy as np
import pandas as pd

from src import strategy_loader


def _df(n=60):
    base = np.linspace(1.10, 1.12, n)
    return pd.DataFrame({
        "open": base, "high": base + 0.0005,
        "low": base - 0.0005, "close": base,
    })


class TestOverlays(unittest.TestCase):

    def test_ma_cross_overlays(self):
        s = strategy_loader.create("ma_cross", {"fast_period": 5, "slow_period": 20})
        ov = s.compute_overlays(_df())
        self.assertEqual(len(ov), 2, "MA cross harus 2 garis overlay")
        for line in ov:
            self.assertIn("name", line); self.assertIn("color", line)
            self.assertEqual(len(line["points"]), 60, "points selaras jumlah candle")
        # nilai terakhir bukan None (sudah melewati warmup)
        self.assertIsNotNone(ov[0]["points"][-1])

    def test_bollinger_overlays(self):
        s = strategy_loader.create("bollinger", {"period": 20, "std_dev": 2.0})
        ov = s.compute_overlays(_df())
        names = [x["name"] for x in ov]
        self.assertEqual(len(ov), 3, "Bollinger harus 3 garis (upper/sma/lower)")
        self.assertTrue(any("Lower" == n for n in names))
        self.assertTrue(any("Upper" == n for n in names))

    def test_multi_indicator_overlays(self):
        s = strategy_loader.create("multi_indicator", {"ma_fast": 20, "ma_slow": 50})
        ov = s.compute_overlays(_df(80))
        self.assertEqual(len(ov), 2, "Multi-indicator overlay = 2 MA")

    def test_oscillator_no_overlay(self):
        # RSI/MACD/Stochastic tidak punya overlay harga -> kosong (aman).
        for name in ("rsi", "macd", "stochastic"):
            s = strategy_loader.create(name, {})
            self.assertEqual(s.compute_overlays(_df()), [], f"{name} seharusnya tanpa overlay harga")


if __name__ == "__main__":
    unittest.main()
