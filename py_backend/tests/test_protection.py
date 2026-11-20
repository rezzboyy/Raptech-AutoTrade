"""Test proteksi lanjutan: spread filter, max exposure, safety guard, equity cut-loss."""

import types
import unittest

import pandas as pd

from src import trade_rules


class FakeBackend:
    def __init__(self, positions=None, deals=None, account=None,
                 spread=0.0):
        self._positions = positions or []
        self._deals = deals or []
        self._account = account or {"balance": 1000.0, "equity": 1000.0}
        self._spread = spread
        self.sent = 0
        self.closed = []

    def positions(self, symbol=None):
        p = list(self._positions)
        return [x for x in p if x.get("symbol") == symbol] if symbol else p

    def history_deals(self, dt_from, dt_to):
        return list(self._deals)

    def account_info(self):
        return dict(self._account)

    def spread_points(self, symbol):
        return self._spread

    def symbol_spec(self, symbol):
        return {"symbol": symbol, "point": 0.00001, "digits": 5,
                "volume_min": 0.01, "volume_step": 0.01, "volume_max": 100,
                "tick_value": 1.0, "tick_size": 0.00001, "stop_level": 0}

    def get_tick(self, symbol):
        return {"bid": 1.1, "ask": 1.1, "time": 0}

    def get_rates(self, symbol, tf, count=200):
        return pd.DataFrame()

    def close_position(self, ticket, symbol):
        self.closed.append(ticket)
        return {"ok": True, "ticket": ticket, "message": ""}

    def send_market_order(self, symbol, side, volume, sl=0.0, tp=0.0, magic=0, comment="mt5bot"):
        self.sent += 1
        return {"ok": True, "ticket": 1, "message": ""}


def _settings(**kw):
    base = dict(max_open_positions=10, max_daily_trades=0, daily_drawdown_limit=0.0,
                magic_number=100200, max_spread_points=0, max_exposure_lots=0.0,
                equity_stop_loss=0.0, max_consecutive_losses=0, timeframe_str="M5")
    base.update(kw)
    return types.SimpleNamespace(**base)


class TestSpreadFilter(unittest.TestCase):
    def test_reject_high_spread(self):
        be = FakeBackend(spread=45.0)
        ok, reason = trade_rules.passes_risk_gates(be, _settings(max_spread_points=20), "EURUSD")
        self.assertFalse(ok)
        self.assertIn("Spread", reason)

    def test_allow_normal_spread(self):
        be = FakeBackend(spread=8.0)
        ok, _ = trade_rules.passes_risk_gates(be, _settings(max_spread_points=20), "EURUSD")
        self.assertTrue(ok)

    def test_disabled_when_zero(self):
        be = FakeBackend(spread=999.0)
        ok, _ = trade_rules.passes_risk_gates(be, _settings(max_spread_points=0), "EURUSD")
        self.assertTrue(ok)


class TestMaxExposure(unittest.TestCase):
    def test_reject_when_exceeds(self):
        be = FakeBackend(positions=[{"symbol": "EURUSD", "magic": 100200, "volume": 0.9}])
        res = trade_rules.open_order_if_allowed(be, _settings(max_exposure_lots=1.0), "EURUSD", "buy", 0.2)
        self.assertFalse(res["ok"])
        self.assertEqual(be.sent, 0)

    def test_allow_within_limit(self):
        be = FakeBackend(positions=[{"symbol": "EURUSD", "magic": 100200, "volume": 0.5}])
        res = trade_rules.open_order_if_allowed(be, _settings(max_exposure_lots=1.0), "EURUSD", "buy", 0.2)
        self.assertTrue(res["ok"])
        self.assertEqual(be.sent, 1)


class TestSafetyGuard(unittest.TestCase):
    def test_consecutive_losses_count(self):
        deals = [
            {"time": 1, "magic": 100200, "net_profit": 5.0},   # profit (paling lama)
            {"time": 2, "magic": 100200, "net_profit": -3.0},
            {"time": 3, "magic": 100200, "net_profit": -2.0},
            {"time": 4, "magic": 100200, "net_profit": -1.0},  # terbaru
        ]
        be = FakeBackend(deals=deals)
        self.assertEqual(trade_rules.consecutive_losses(be, 100200), 3)

    def test_guard_blocks(self):
        deals = [{"time": i, "magic": 100200, "net_profit": -1.0} for i in range(4)]
        be = FakeBackend(deals=deals)
        ok, reason = trade_rules.passes_risk_gates(be, _settings(max_consecutive_losses=3), "EURUSD")
        self.assertFalse(ok)
        self.assertIn("Safety guard", reason)

    def test_profit_breaks_streak(self):
        deals = [
            {"time": 1, "magic": 100200, "net_profit": -1.0},
            {"time": 2, "magic": 100200, "net_profit": 2.0},   # profit terbaru -> streak 0
        ]
        be = FakeBackend(deals=deals)
        self.assertEqual(trade_rules.consecutive_losses(be, 100200), 0)


class TestEquityCutLoss(unittest.TestCase):
    def _engine(self, backend, settings_ns):
        from src.bot_engine import BotEngine
        eng = BotEngine.__new__(BotEngine)
        eng.backend = backend
        eng.strategy = types.SimpleNamespace(generate_signal=lambda df: None)
        # patch modul settings global yang dipakai bot_engine
        import src.bot_engine as be_mod
        self._orig_settings = be_mod.settings
        be_mod.settings = settings_ns
        return eng, be_mod

    def test_cut_loss_closes_all_and_stops(self):
        be = FakeBackend(
            positions=[{"symbol": "EURUSD", "magic": 100200, "volume": 0.1, "ticket": 11},
                       {"symbol": "GBPUSD", "magic": 100200, "volume": 0.1, "ticket": 12}],
            account={"balance": 1000.0, "equity": 850.0},  # dd 15%
        )
        s = _settings(equity_stop_loss=0.10, symbols_list=["EURUSD"])
        # symbols_list dipakai sebagai property di Settings asli; di SimpleNamespace jadi atribut.
        s.symbols_list = ["EURUSD"]
        s.trailing_stop_enabled = False
        s.break_even_enabled = False
        eng, be_mod = self._engine(be, s)
        try:
            result = eng.process_trading_step()
        finally:
            be_mod.settings = self._orig_settings
        self.assertFalse(result)  # auto trading harus berhenti
        self.assertEqual(sorted(be.closed), [11, 12])  # semua posisi ditutup

    def test_no_cut_loss_when_safe(self):
        be = FakeBackend(
            positions=[{"symbol": "EURUSD", "magic": 100200, "volume": 0.1, "ticket": 11}],
            account={"balance": 1000.0, "equity": 980.0},  # dd 2% < 10%
        )
        s = _settings(equity_stop_loss=0.10)
        s.symbols_list = ["EURUSD"]
        s.trailing_stop_enabled = False
        s.break_even_enabled = False
        eng, be_mod = self._engine(be, s)
        try:
            result = eng.process_trading_step()
        finally:
            be_mod.settings = self._orig_settings
        self.assertTrue(result)
        self.assertEqual(be.closed, [])


if __name__ == "__main__":
    unittest.main()
