"""Uji pemilihan filling mode order agar kompatibel dengan berbagai broker."""

import unittest
from unittest.mock import MagicMock, patch

import MetaTrader5 as _mt5real
from src import order_manager


class TestFillingMode(unittest.TestCase):
    """get_filling_type harus memilih mode yang didukung simbol."""

    # Nilai bitmask simbol (literal MQL5): FOK=1, IOC=2
    SYM_FOK = 1
    SYM_IOC = 2

    def _fake_mt5(self):
        m = MagicMock()
        # Konstanta ORDER_FILLING_* nyata dari MT5 (ini memang diekspos package).
        m.ORDER_FILLING_FOK = _mt5real.ORDER_FILLING_FOK
        m.ORDER_FILLING_IOC = _mt5real.ORDER_FILLING_IOC
        m.ORDER_FILLING_RETURN = _mt5real.ORDER_FILLING_RETURN
        return m

    def test_prefers_ioc_when_supported(self):
        m = self._fake_mt5()
        info = MagicMock()
        info.filling_mode = self.SYM_IOC | self.SYM_FOK
        m.symbol_info.return_value = info
        with patch.object(order_manager, "mt5", m):
            self.assertEqual(order_manager.get_filling_type("EURUSD"), _mt5real.ORDER_FILLING_IOC)

    def test_falls_back_to_fok(self):
        m = self._fake_mt5()
        info = MagicMock()
        info.filling_mode = self.SYM_FOK  # hanya FOK
        m.symbol_info.return_value = info
        with patch.object(order_manager, "mt5", m):
            self.assertEqual(order_manager.get_filling_type("XAUUSD"), _mt5real.ORDER_FILLING_FOK)

    def test_falls_back_to_return(self):
        m = self._fake_mt5()
        info = MagicMock()
        info.filling_mode = 0  # tidak mendukung FOK/IOC
        m.symbol_info.return_value = info
        with patch.object(order_manager, "mt5", m):
            self.assertEqual(order_manager.get_filling_type("US30"), _mt5real.ORDER_FILLING_RETURN)

    def test_symbol_info_none_safe(self):
        m = self._fake_mt5()
        m.symbol_info.return_value = None
        with patch.object(order_manager, "mt5", m):
            # Tidak boleh error; kembalikan default IOC.
            self.assertEqual(order_manager.get_filling_type("???"), _mt5real.ORDER_FILLING_IOC)


if __name__ == "__main__":
    unittest.main()
