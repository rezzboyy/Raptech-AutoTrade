"""Test order lanjutan: pending order, fail-safe, normalisasi order, close-all."""

import types
import unittest

from src.backends.mcp_backend import McpBackend, _normalize_order


class SpyClient:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return {"success": True, "ticket": 555}

    def initialize(self):
        return {}

    def close(self):
        pass


def make_backend(trade_allowed=True, server_connected=True):
    be = McpBackend.__new__(McpBackend)
    be._client = SpyClient()
    be.connected = True
    be._trade_allowed = trade_allowed
    be._server_connected = server_connected
    be._symbol_cache = {}
    return be


class TestPendingOrder(unittest.TestCase):

    def test_valid_pending_sends(self):
        be = make_backend()
        res = be.send_pending_order("EURUSD", "buy_limit", 0.01, 1.0900)
        self.assertTrue(res["ok"])
        self.assertEqual(be._client.calls[-1][0], "trade_send_pending_order")

    def test_invalid_type_rejected(self):
        be = make_backend()
        res = be.send_pending_order("EURUSD", "banana", 0.01, 1.09)
        self.assertFalse(res["ok"])
        self.assertEqual(be._client.calls, [])  # tidak ada panggilan tool

    def test_zero_price_rejected(self):
        be = make_backend()
        res = be.send_pending_order("EURUSD", "buy_stop", 0.01, 0.0)
        self.assertFalse(res["ok"])
        self.assertEqual(be._client.calls, [])

    def test_failsafe_blocks_pending(self):
        be = make_backend(server_connected=False)
        res = be.send_pending_order("EURUSD", "buy_limit", 0.01, 1.09)
        self.assertFalse(res["ok"])
        self.assertEqual(be._client.calls, [])

    def test_comment_clamped_on_pending(self):
        be = make_backend()
        be.send_pending_order("EURUSD", "sell_stop", 0.01, 1.05, comment="Z" * 90)
        args = be._client.calls[-1][1]
        self.assertLessEqual(len(args["comment"]), 31)


class TestNormalizeOrder(unittest.TestCase):

    def test_keys(self):
        raw = {"ticket": 7, "symbol": "EURUSD", "type": "BUY_LIMIT",
               "volume_current": 0.1, "price_open": 1.09, "sl": 1.08, "tp": 1.11, "magic": 100200}
        o = _normalize_order(raw)
        self.assertEqual(set(o.keys()), {"ticket", "symbol", "type", "volume", "price", "sl", "tp", "magic"})
        self.assertEqual(o["type"], "buy_limit")
        self.assertEqual(o["ticket"], 7)


class FakeBackend:
    def __init__(self, positions):
        self._positions = positions
        self.closed = []

    def positions(self, symbol=None):
        return list(self._positions)

    def close_position(self, ticket, symbol):
        self.closed.append(ticket)
        return {"ok": True, "ticket": ticket, "message": ""}


class TestCloseAll(unittest.TestCase):

    def test_close_all_respects_magic(self):
        from src.bot_engine import BotEngine
        from config.settings import settings
        settings.magic_number = 100200
        eng = BotEngine.__new__(BotEngine)
        eng.backend = FakeBackend([
            {"ticket": 1, "symbol": "EURUSD", "magic": 100200},
            {"ticket": 2, "symbol": "GBPUSD", "magic": 999},  # magic beda -> dilewati
            {"ticket": 3, "symbol": "EURUSD", "magic": 100200},
        ])
        n = eng.close_all()
        self.assertEqual(n, 2)
        self.assertEqual(sorted(eng.backend.closed), [1, 3])


if __name__ == "__main__":
    unittest.main()
