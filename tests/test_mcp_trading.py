"""Property test operasi trading MCP + gerbang risiko (Tahap 3).

Property 5: arah order BUY->buy, SELL->sell.
Property 6: komentar order selalu <= 31 karakter.
Property 7: bila gerbang risiko terlanggar, tidak ada send_market_order.
Property 8: bila trade_allowed/server_connected false, tidak ada order terkirim.
"""

import random
import string
import types
import unittest

from src.backends.mcp_backend import (
    McpBackend, _side_to_mcp, _clamp_comment,
)
from src import trade_rules
from strategies.base import SIGNAL_BUY, SIGNAL_SELL


class SpyClient:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return {"success": True, "ticket": 999}

    def initialize(self):
        return {}

    def close(self):
        pass


def make_backend(trade_allowed, server_connected):
    be = McpBackend.__new__(McpBackend)
    be._client = SpyClient()
    be.connected = True
    be._trade_allowed = trade_allowed
    be._server_connected = server_connected
    be._symbol_cache = {}
    return be


class TestOrderDirection(unittest.TestCase):
    """Property 5."""

    def test_side_mapping(self):
        self.assertEqual(_side_to_mcp("BUY"), "buy")
        self.assertEqual(_side_to_mcp("SELL"), "sell")
        self.assertEqual(trade_rules.map_signal_to_side(SIGNAL_BUY), "buy")
        self.assertEqual(trade_rules.map_signal_to_side(SIGNAL_SELL), "sell")

    def test_invalid_side_is_none(self):
        for bad in ("", "hold", "xyz", None):
            self.assertIsNone(_side_to_mcp(bad))


class TestCommentLimit(unittest.TestCase):
    """Property 6: comment <= 31 karakter untuk input sepanjang apa pun."""

    def test_clamp_random_lengths(self):
        random.seed(7)
        for _ in range(300):
            n = random.randint(0, 200)
            s = "".join(random.choice(string.printable) for _ in range(n))
            self.assertLessEqual(len(_clamp_comment(s)), 31)
            self.assertLessEqual(len(trade_rules.clamp_comment(s)), 31)

    def test_order_sends_clamped_comment(self):
        be = make_backend(True, True)
        long_comment = "X" * 100
        be.send_market_order("EURUSD", "BUY", 0.01, comment=long_comment)
        # Argumen comment yang dikirim ke tool harus <= 31.
        name, args = be._client.calls[-1]
        self.assertEqual(name, "trade_send_market_order")
        self.assertLessEqual(len(args["comment"]), 31)


class TestFailSafe(unittest.TestCase):
    """Property 8: order tidak terkirim bila trading diblokir."""

    def test_no_order_when_trade_not_allowed(self):
        be = make_backend(trade_allowed=False, server_connected=True)
        res = be.send_market_order("EURUSD", "BUY", 0.01)
        self.assertFalse(res["ok"])
        self.assertEqual(be._client.calls, [])  # tidak ada panggilan tool

    def test_no_order_when_server_disconnected(self):
        be = make_backend(trade_allowed=True, server_connected=False)
        res = be.send_market_order("EURUSD", "SELL", 0.01)
        self.assertFalse(res["ok"])
        self.assertEqual(be._client.calls, [])

    def test_close_and_modify_blocked(self):
        be = make_backend(trade_allowed=False, server_connected=False)
        self.assertFalse(be.close_position(1, "EURUSD")["ok"])
        self.assertFalse(be.modify_sl_tp(1, "EURUSD", sl=1.0))
        self.assertEqual(be._client.calls, [])

    def test_no_order_when_algo_trading_disabled(self):
        """Bila experts_trade_allowed=False (Algo Trading OFF di MT5), order diblokir dengan pesan edukatif."""
        be = make_backend(trade_allowed=True, server_connected=True)
        be._experts_trade_allowed = False
        res = be.send_market_order("EURUSD", "BUY", 0.01)
        self.assertFalse(res["ok"])
        self.assertIn("Algo Trading", res["message"])
        self.assertIn("Ctrl+E", res["message"])
        self.assertEqual(be._client.calls, [])

    def test_friendly_trade_error_message(self):
        """Pesan error teknis 'trading is not permitted' harus diubah menjadi panduan jelas."""
        from src.backends.mcp_backend import _friendly_trade_error
        raw = "Tool 'trade_send_market_order' gagal: Tool 'trade_send_market_order' trading is not permitted"
        friendly = _friendly_trade_error(raw)
        self.assertIn("Algo Trading", friendly)
        self.assertIn("Ctrl+E", friendly)
        self.assertIn("trading is not permitted", friendly)

    def test_order_rejected_with_friendly_message(self):
        """Bila MT5 mengembalikan error 'trading is not permitted', response order harus memuat pesan panduan."""
        from src.mcp_client import McpError
        be = make_backend(trade_allowed=True, server_connected=True)
        be._client.call_tool = lambda *args, **kwargs: (_ for _ in ()).throw(
            McpError("Tool 'trade_send_market_order' trading is not permitted")
        )
        res = be.send_market_order("EURUSD", "BUY", 0.01)
        self.assertFalse(res["ok"])
        self.assertIn("Algo Trading", res["message"])
        self.assertIn("Ctrl+E", res["message"])


class SpyBackend:
    """Backend palsu untuk menguji gerbang risiko (Property 7)."""

    def __init__(self, positions=None, deals=None, balance=1000.0):
        self._positions = positions or []
        self._deals = deals or []
        self._balance = balance
        self.sent = 0

    def positions(self, symbol=None):
        if symbol:
            return [p for p in self._positions if p.get("symbol") == symbol]
        return list(self._positions)

    def history_deals(self, dt_from, dt_to):
        return list(self._deals)

    def account_info(self):
        return {"balance": self._balance}

    def send_market_order(self, symbol, side, volume, sl=0.0, tp=0.0, magic=0, comment="mt5bot"):
        self.sent += 1
        return {"ok": True, "ticket": 1, "message": ""}


def _settings(max_pos=1, max_daily=0, dd=0.0, magic=100200):
    return types.SimpleNamespace(
        max_open_positions=max_pos, max_daily_trades=max_daily,
        daily_drawdown_limit=dd, magic_number=magic,
    )


class TestRiskGate(unittest.TestCase):
    """Property 7: gerbang risiko mencegah order."""

    def test_max_positions_blocks_order(self):
        be = SpyBackend(positions=[{"symbol": "EURUSD", "magic": 100200, "profit": 0.0}])
        s = _settings(max_pos=1)
        res = trade_rules.open_order_if_allowed(be, s, "EURUSD", "buy", 0.01)
        self.assertFalse(res["ok"])
        self.assertEqual(be.sent, 0)  # tidak mengirim order

    def test_daily_drawdown_blocks_order(self):
        # Rugi 100 dari balance 1000 = 10% > batas 5%.
        be = SpyBackend(deals=[{"magic": 100200, "net_profit": -100.0}], balance=1000.0)
        s = _settings(max_pos=5, dd=0.05)
        res = trade_rules.open_order_if_allowed(be, s, "EURUSD", "buy", 0.01)
        self.assertFalse(res["ok"])
        self.assertEqual(be.sent, 0)

    def test_max_daily_trades_blocks_order(self):
        be = SpyBackend(deals=[{"magic": 100200, "net_profit": 5.0}] * 3)
        s = _settings(max_pos=5, max_daily=3)
        res = trade_rules.open_order_if_allowed(be, s, "EURUSD", "buy", 0.01)
        self.assertFalse(res["ok"])
        self.assertEqual(be.sent, 0)

    def test_order_sent_when_gates_pass(self):
        be = SpyBackend()
        s = _settings(max_pos=5, max_daily=0, dd=0.0)
        res = trade_rules.open_order_if_allowed(be, s, "EURUSD", "buy", 0.01)
        self.assertTrue(res["ok"])
        self.assertEqual(be.sent, 1)


class TestErrorHandlingAndStopProtection(unittest.TestCase):
    """Pengujian penanganan error MCP dan auto-proteksi SL/TP terhadap batas stop broker."""

    def test_parse_order_result_with_retcode_details(self):
        from src.backends.mcp_backend import _parse_order_result
        # Kasus saat MT5 MCP mengembalikan retcode 10016 dan pesan di retcode_details
        res = {"retcode": 10016, "retcode_details": "Invalid stops", "success": False}
        parsed = _parse_order_result(res)
        self.assertFalse(parsed["ok"])
        self.assertIn("10016", parsed["message"])
        self.assertIn("Invalid stops", parsed["message"])

    def test_friendly_trade_error_invalid_stops(self):
        from src.backends.mcp_backend import _friendly_trade_error
        msg = _friendly_trade_error("Invalid stops (#10016)")
        self.assertIn("terlalu dekat", msg)
        self.assertIn("10016", msg)

    def test_friendly_trade_error_market_closed(self):
        from src.backends.mcp_backend import _friendly_trade_error
        msg = _friendly_trade_error("Market closed (#10018)")
        self.assertIn("tutup", msg)
        self.assertIn("10018", msg)

    def test_engine_compute_sl_tp_auto_clamps_to_spread(self):
        """Uji saat SL diatur 150 pts tapi spread BTCUSDm 1000 pts -> SL otomatis diperlebar."""
        from src.bot_engine import BotEngine
        from strategies.base import SIGNAL_BUY, SIGNAL_SELL

        class MockBackend:
            def symbol_spec(self, sym):
                return {"point": 0.01, "digits": 2, "stop_level": 50}
            def spread_points(self, sym):
                return 1000.0

        engine = BotEngine.__new__(BotEngine)
        engine.backend = MockBackend()
        engine.strategy = types.SimpleNamespace(params={}, script_settings={})

        # Kasus BUY: entry 84250, jika SL 150 pts (1.50) akan melanggar spread 1000 pts (10.00).
        # Harus di-clamp ke minimal max(50, 1500, 1050, 20) = 1500 pts ($15.00).
        sl, tp = engine._compute_sl_tp("BTCUSDm", SIGNAL_BUY, 84250.0, {"sl_points": 150, "tp_points": 100})
        # BUY SL = entry - 15.00 = 84235.00
        # BUY TP = entry + 15.00 = 84265.00
        self.assertLessEqual(sl, 84235.00)
        self.assertGreaterEqual(tp, 84265.00)


if __name__ == "__main__":
    unittest.main()

