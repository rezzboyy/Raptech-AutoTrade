"""Unit test untuk strategi baru dan manajemen risiko lanjutan."""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd

from config.settings import settings
from src import strategy_loader, config_store
from src.risk_manager import (
    calculate_lot,
    can_open_new_position,
    apply_break_even,
    apply_trailing_stop,
    check_daily_drawdown,
    can_trade_today,
    get_daily_trade_count,
)
from strategies.base import SIGNAL_BUY, SIGNAL_SELL


class TestStrategies(unittest.TestCase):
    """Pengujian untuk strategi-strategi baru."""

    def test_all_strategies_registered(self):
        names = strategy_loader.names()
        expected = ["ma_cross", "rsi", "bollinger", "macd", "stochastic", "multi_indicator"]
        for exp in expected:
            self.assertIn(exp, names, f"Strategi {exp} belum terdaftar di registry!")

    def test_bollinger_bands_signal(self):
        strat = strategy_loader.create("bollinger", {"period": 10, "std_dev": 2.0})
        # Buat dataframe sintetis yang memicu bounce dari lower band
        prices = [100.0] * 20
        # Jatuh tajam menembus lower band
        prices[-2] = 80.0
        # Rebound kembali ke atas lower band
        prices[-1] = 95.0
        df = pd.DataFrame({"close": prices})
        sig = strat.generate_signal(df)
        self.assertEqual(sig, SIGNAL_BUY)

        # Drop dari atas upper band
        prices = [100.0] * 20
        prices[-2] = 120.0
        prices[-1] = 105.0
        df = pd.DataFrame({"close": prices})
        sig = strat.generate_signal(df)
        self.assertEqual(sig, SIGNAL_SELL)

    def test_macd_crossover(self):
        # Validasi parameter
        errs = strategy_loader.validate("macd", {"fast_ema": 30, "slow_ema": 20})
        self.assertTrue(len(errs) > 0, "Fast EMA >= Slow EMA harus menghasilkan error validasi.")

        strat = strategy_loader.create("macd", {"fast_ema": 5, "slow_ema": 10, "signal_period": 3})
        # Tren naik memicu MACD cross up
        prices = list(np.linspace(100, 90, 15)) + list(np.linspace(91, 110, 15))
        df = pd.DataFrame({"close": prices})
        sig = strat.generate_signal(df)
        # Sinyal harus BUY atau None (bukan SELL)
        self.assertIn(sig, [SIGNAL_BUY, None])

    def test_stochastic_oscillator(self):
        errs = strategy_loader.validate("stochastic", {"oversold": 85.0, "overbought": 20.0})
        self.assertTrue(len(errs) > 0, "Oversold >= Overbought harus menghasilkan error validasi.")

        strat = strategy_loader.create("stochastic", {"k_period": 5, "d_period": 3, "oversold": 20, "overbought": 80})
        # Data sideways lalu bounce dari dasar
        n = 30
        lows = [90.0] * n
        highs = [110.0] * n
        closes = [100.0] * n
        # Buat candle oversold lalu naik
        closes[-3] = 91.0
        closes[-2] = 90.5
        closes[-1] = 94.0
        df = pd.DataFrame({"low": lows, "high": highs, "close": closes})
        sig = strat.generate_signal(df)
        self.assertIn(sig, [SIGNAL_BUY, None])

    def test_multi_indicator(self):
        errs = strategy_loader.validate("multi_indicator", {"ma_fast": 50, "ma_slow": 20})
        self.assertTrue(len(errs) > 0, "MA Cepat >= MA Lambat harus menghasilkan error validasi.")

        strat = strategy_loader.create("multi_indicator", {
            "ma_fast": 5, "ma_slow": 15, "rsi_period": 5,
            "rsi_buy_level": 50.0, "rsi_sell_level": 50.0
        })
        # Buat data tren naik kuat
        prices = list(np.linspace(100, 120, 30))
        df = pd.DataFrame({"close": prices})
        sig = strat.generate_signal(df)
        self.assertIn(sig, [SIGNAL_BUY, None])


class TestRiskManagement(unittest.TestCase):
    """Pengujian fungsi manajemen risiko dan proteksi order."""

    def test_multi_symbol_settings_parsing(self):
        settings.symbol = "EURUSD, GBPUSD ; USDJPY "
        symbols = settings.symbols_list
        self.assertEqual(symbols, ["EURUSD", "GBPUSD", "USDJPY"])

        settings.symbol = "XAUUSD"
        self.assertEqual(settings.symbols_list, ["XAUUSD"])

    @patch("src.risk_manager.mt5")
    @patch("src.risk_manager.modify_position_sl")
    def test_break_even_buy(self, mock_modify, mock_mt5):
        mock_modify.return_value = True
        pos = MagicMock()
        pos.ticket = 12345
        pos.symbol = "EURUSD"
        pos.type = 0  # POSITION_TYPE_BUY
        pos.price_open = 1.10000
        pos.sl = 1.09700

        mock_tick = MagicMock()
        mock_tick.bid = 1.10200  # profit +200 points (point = 0.00001)
        mock_mt5.symbol_info_tick.return_value = mock_tick

        mock_info = MagicMock()
        mock_info.point = 0.00001
        mock_info.digits = 5
        mock_mt5.symbol_info.return_value = mock_info
        mock_mt5.POSITION_TYPE_BUY = 0
        mock_mt5.POSITION_TYPE_SELL = 1

        # Trigger BE pada 150 points, offset 10 points
        triggered = apply_break_even(pos, trigger_points=150, offset_points=10)
        self.assertTrue(triggered)
        mock_modify.assert_called_once()
        # new_sl should be 1.10000 + 0.00010 = 1.10010
        called_sl = mock_modify.call_args[0][1]
        self.assertAlmostEqual(called_sl, 1.10010, places=5)

    @patch("src.risk_manager.mt5")
    @patch("src.risk_manager.modify_position_sl")
    def test_trailing_stop_buy(self, mock_modify, mock_mt5):
        mock_modify.return_value = True
        pos = MagicMock()
        pos.ticket = 12346
        pos.symbol = "EURUSD"
        pos.type = 0  # POSITION_TYPE_BUY
        pos.price_open = 1.10000
        pos.sl = 1.10010

        mock_tick = MagicMock()
        mock_tick.bid = 1.10400  # harga naik jauh
        mock_mt5.symbol_info_tick.return_value = mock_tick

        mock_info = MagicMock()
        mock_info.point = 0.00001
        mock_info.digits = 5
        mock_info.stop_level = 10
        mock_mt5.symbol_info.return_value = mock_info
        mock_mt5.POSITION_TYPE_BUY = 0
        mock_mt5.POSITION_TYPE_SELL = 1

        # Trailing 200 points (ideal SL = 1.10400 - 0.00200 = 1.10200), step 50 pts
        # (1.10200 - 1.10010 = 190 pts >= 50 pts)
        triggered = apply_trailing_stop(pos, trailing_points=200, step_points=50)
        self.assertTrue(triggered)
        called_sl = mock_modify.call_args[0][1]
        self.assertAlmostEqual(called_sl, 1.10200, places=5)

    @patch("src.risk_manager.mt5")
    def test_daily_drawdown_limit(self, mock_mt5):
        # Akun balance 10000
        mock_acc = MagicMock()
        mock_acc.balance = 10000.0
        mock_mt5.account_info.return_value = mock_acc

        # Deal rugi 600 hari ini
        deal = MagicMock()
        deal.entry = 1
        deal.profit = -600.0
        deal.commission = 0.0
        deal.swap = 0.0
        deal.fee = 0.0
        deal.magic = 100200
        mock_mt5.history_deals_get.return_value = [deal]
        mock_mt5.positions_get.return_value = []

        # Batas 5% (0.05). Rugi 600 / 10600 = ~5.66% -> Harus breached
        breached, pct = check_daily_drawdown(0.05, magic=100200)
        self.assertTrue(breached)
        self.assertGreater(pct, 0.05)


if __name__ == "__main__":
    unittest.main()
