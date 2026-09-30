"""Property 3: normalisasi konsisten lintas-backend + bentuk data MCP benar.

Tidak butuh koneksi MCP; memakai klien palsu (fake) dan mock MetaTrader5.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.backends.mcp_backend import (
    McpBackend,
    _normalize_position,
    _normalize_deal,
    _parse_mt5_time,
)

# Kunci kontrak (harus sama di kedua backend).
ACCOUNT_KEYS = {
    "login", "balance", "equity", "margin", "free_margin", "profit",
    "currency", "server", "account_type", "trade_allowed", "server_connected",
}
POSITION_KEYS = {
    "ticket", "symbol", "type", "volume", "price_open", "price_current",
    "sl", "tp", "profit", "magic",
}
DEAL_KEYS = {"ticket", "time", "symbol", "magic", "net_profit", "profit"}


class FakeClient:
    """McpClient palsu yang mengembalikan payload kalengan."""

    def __init__(self, responses):
        self._responses = responses

    def initialize(self):
        return {}

    def call_tool(self, name, arguments=None):
        return self._responses.get(name, {})

    def close(self):
        pass


def make_mcp_backend(responses):
    be = McpBackend.__new__(McpBackend)  # lewati __init__ (hindari koneksi nyata)
    be._client = FakeClient(responses)
    be.connected = False
    be._trade_allowed = False
    be._server_connected = False
    be._symbol_cache = {}
    return be


class TestNormalizationShapes(unittest.TestCase):

    def test_position_normalization_keys_and_types(self):
        raw = {"ticket": 123, "symbol": "EURUSD", "type": "buy", "volume": 0.1,
               "price_open": 1.1, "price_current": 1.105, "sl": 1.09, "tp": 1.12,
               "profit": 5.0, "magic": 100200}
        pos = _normalize_position(raw)
        self.assertEqual(set(pos.keys()), POSITION_KEYS)
        self.assertEqual(pos["type"], "BUY")
        self.assertIsInstance(pos["ticket"], int)
        self.assertIsInstance(pos["volume"], float)

    def test_position_type_sell_variants(self):
        for raw_type in ("sell", "SELL", "1", "POSITION_TYPE_SELL"):
            pos = _normalize_position({"type": raw_type, "symbol": "X"})
            self.assertEqual(pos["type"], "SELL")

    def test_deal_normalization_net_profit(self):
        raw = {"ticket": 9, "symbol": "EURUSD", "magic": 100200,
               "profit": 10.0, "commission": -1.0, "swap": -0.5, "fee": 0.0}
        deal = _normalize_deal(raw)
        self.assertEqual(set(deal.keys()), DEAL_KEYS)
        self.assertAlmostEqual(deal["net_profit"], 8.5, places=6)

    def test_position_normalization_mt5_live_payload(self):
        """Uji normalisasi payload posisi asli dari server MCP MT5 build 6182."""
        raw = {
            "position_id": 3873749697,
            "action": "buy",
            "reason": "Expert",
            "symbol": "XAUUSDm",
            "create_time": "2026.09.24 00:34:40",
            "update_time": "2026.09.24 00:34:40",
            "volume": 0.01,
            "price_open": 4292.485,
            "price_last": 4292.907,
            "profit": 0.42,
            "contract_size": 100.0,
            "comment": "manual",
        }
        pos = _normalize_position(raw)
        self.assertEqual(pos["ticket"], 3873749697)
        self.assertEqual(pos["type"], "BUY")
        self.assertEqual(pos["symbol"], "XAUUSDm")
        self.assertEqual(pos["volume"], 0.01)
        self.assertEqual(pos["price_open"], 4292.485)
        self.assertEqual(pos["price_current"], 4292.907)
        self.assertEqual(pos["profit"], 0.42)

    def test_close_position_rejects_invalid_ticket(self):
        """close_position harus langsung menolak ticket 0 atau negatif (fail-safe)."""
        be = make_mcp_backend({})
        res_zero = be.close_position(0, "EURUSDm")
        self.assertFalse(res_zero["ok"])
        self.assertIn("tidak valid", res_zero["message"])

        res_neg = be.close_position(-5, "EURUSDm")
        self.assertFalse(res_neg["ok"])

    def test_parse_mt5_time(self):
        dt = _parse_mt5_time("2024.08.15 01:45:00")
        self.assertEqual((dt.year, dt.month, dt.day, dt.hour, dt.minute), (2024, 8, 15, 1, 45))


class TestCrossBackendAccountParity(unittest.TestCase):
    """Property 3: kunci account_info identik di native & mcp untuk data setara."""

    def test_mcp_account_keys(self):
        resp = {"get_trading_account_info": {
            "account": {"login": 416225730, "balance": 100.0, "equity": 100.0,
                        "margin": 0.0, "margin_free": 100.0, "profit": 0.0,
                        "currency": "USD", "server": "Exness-MT5Trial14"},
            "terminal": {"mcp_trade_allowed": True, "server_connected": True},
        }}
        be = make_mcp_backend(resp)
        acc = be.account_info()
        self.assertEqual(set(acc.keys()), ACCOUNT_KEYS)
        self.assertTrue(acc["trade_allowed"])

    def test_mcp_trade_allowed_requires_algo_trading(self):
        """trade_allowed harus False jika experts_trade_allowed=False (Algo Trading OFF)."""
        resp_off = {"get_trading_account_info": {
            "account": {"login": 416225730, "balance": 100.0, "equity": 100.0,
                        "margin": 0.0, "margin_free": 100.0, "profit": 0.0,
                        "currency": "USD", "server": "Exness-MT5Trial14"},
            "terminal": {"mcp_trade_allowed": True, "experts_trade_allowed": False, "server_connected": True},
        }}
        be_off = make_mcp_backend(resp_off)
        acc_off = be_off.account_info()
        self.assertFalse(acc_off["trade_allowed"])
        self.assertFalse(be_off._experts_trade_allowed)

        resp_on = {"get_trading_account_info": {
            "account": {"login": 416225730, "balance": 100.0, "equity": 100.0,
                        "margin": 0.0, "margin_free": 100.0, "profit": 0.0,
                        "currency": "USD", "server": "Exness-MT5Trial14"},
            "terminal": {"mcp_trade_allowed": True, "experts_trade_allowed": True, "server_connected": True},
        }}
        be_on = make_mcp_backend(resp_on)
        acc_on = be_on.account_info()
        self.assertTrue(acc_on["trade_allowed"])
        self.assertTrue(be_on._experts_trade_allowed)

    @patch("src.connection.MT5Connection")
    def test_native_account_keys_match_mcp(self, _mock_conn):
        from src.backends.native_backend import NativeBackend
        with patch("MetaTrader5.account_info") as m_acc, \
             patch("MetaTrader5.terminal_info") as m_term:
            m_acc.return_value = MagicMock(
                login=416225730, balance=100.0, equity=100.0, margin=0.0,
                margin_free=100.0, profit=0.0, currency="USD", server="Exness-MT5Trial14",
            )
            m_term.return_value = MagicMock(trade_allowed=True, connected=True)
            nb = NativeBackend()
            acc = nb.account_info()
        self.assertEqual(set(acc.keys()), ACCOUNT_KEYS)

    def test_position_and_deal_contract_keys(self):
        # Kedua kontrak (posisi & deal) harus tetap sesuai daftar kunci.
        self.assertEqual(set(_normalize_position({}).keys()), POSITION_KEYS)
        self.assertEqual(set(_normalize_deal({}).keys()), DEAL_KEYS)


if __name__ == "__main__":
    unittest.main()
