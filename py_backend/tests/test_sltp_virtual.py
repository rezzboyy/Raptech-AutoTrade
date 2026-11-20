"""Test SL/TP mode percent + deteksi exit virtual/hidden."""

import types
import unittest

from src import trade_rules


class TestPercentSLTP(unittest.TestCase):
    def test_buy_percent(self):
        sl, tp = trade_rules.compute_percent_sl_tp("buy", 1.10000, 0.5, 1.0, digits=5)
        self.assertAlmostEqual(sl, 1.09450, places=5)  # -0.5%
        self.assertAlmostEqual(tp, 1.11100, places=5)  # +1.0%

    def test_sell_percent(self):
        sl, tp = trade_rules.compute_percent_sl_tp("sell", 1.10000, 0.5, 1.0, digits=5)
        self.assertAlmostEqual(sl, 1.10550, places=5)  # +0.5%
        self.assertAlmostEqual(tp, 1.08900, places=5)  # -1.0%


class TestVirtualExit(unittest.TestCase):
    def test_buy_sl_hit(self):
        # BUY ditutup di bid; SL 1.0950, bid turun ke 1.0949 -> SL
        self.assertEqual(trade_rules.virtual_exit_hit("BUY", 1.0950, 1.1100, 1.0949, 1.0950), "SL")

    def test_buy_tp_hit(self):
        self.assertEqual(trade_rules.virtual_exit_hit("BUY", 1.0950, 1.1100, 1.1101, 1.1102), "TP")

    def test_buy_no_hit(self):
        self.assertIsNone(trade_rules.virtual_exit_hit("BUY", 1.0950, 1.1100, 1.1000, 1.1001))

    def test_sell_sl_hit(self):
        # SELL ditutup di ask; SL 1.1050, ask naik ke 1.1051 -> SL
        self.assertEqual(trade_rules.virtual_exit_hit("SELL", 1.1050, 1.0900, 1.1049, 1.1051), "SL")

    def test_sell_tp_hit(self):
        self.assertEqual(trade_rules.virtual_exit_hit("SELL", 1.1050, 1.0900, 1.0898, 1.0899), "TP")

    def test_zero_levels_skipped(self):
        self.assertIsNone(trade_rules.virtual_exit_hit("BUY", 0.0, 0.0, 1.0, 1.0))


class TestEnginePercentBranch(unittest.TestCase):
    def test_compute_sl_tp_percent(self):
        from src.bot_engine import BotEngine
        import src.bot_engine as be_mod
        from strategies.base import SIGNAL_BUY

        class FakeBE:
            def symbol_spec(self, s):
                return {"symbol": s, "point": 0.00001, "digits": 5}

        eng = BotEngine.__new__(BotEngine)
        eng.backend = FakeBE()
        eng.strategy = types.SimpleNamespace(params={})
        orig = be_mod.settings
        be_mod.settings = types.SimpleNamespace(
            sl_tp_mode="percent", sl_percent=0.5, tp_percent=1.0,
            sl_points=300, tp_points=600,
        )
        try:
            sl, tp = eng._compute_sl_tp("EURUSD", SIGNAL_BUY, 1.10000)
        finally:
            be_mod.settings = orig
        self.assertAlmostEqual(sl, 1.09450, places=5)
        self.assertAlmostEqual(tp, 1.11100, places=5)


if __name__ == "__main__":
    unittest.main()
