"""Unit test untuk API Mode Programmer lanjutan (Pending, Multi-TF, State) & GMG XAUUSDm V1.1."""

from pathlib import Path
import pandas as pd
import pytest

from config.settings import settings
from src import bot_engine as be_mod
from src.bot_engine import BotEngine
from src.backends.mcp_backend import McpBackend
from strategies.script_runtime import (
    ScriptContext,
    ScriptStrategy,
    compile_script,
    extract_script_settings,
)


def _make_df(closes, freq="1min", step_hl=0.5):
    n = len(closes)
    times = pd.date_range("2026-11-25 08:00:00", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + step_hl for c in closes],
            "low": [c - step_hl for c in closes],
            "close": closes,
            "tick_volume": [100] * n,
        },
        index=times,
    )


class _MockGridBackend:
    def __init__(self, m1_df, h1_df=None, m15_df=None):
        self._rates = {"M1": m1_df, "H1": h1_df if h1_df is not None else m1_df, "M15": m15_df if m15_df is not None else m1_df}
        self._positions = []
        self._pending = []
        self._account = {"balance": 10000.0, "equity": 10000.0, "margin": 0.0, "free_margin": 10000.0, "profit": 0.0}
        self._tick = {"bid": 2650.00, "ask": 2650.30, "time": 1700000000}
        self._spec = {
            "symbol": "XAUUSDm", "digits": 2, "point": 0.01,
            "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
            "stop_level": 20, "freeze_level": 0, "contract_size": 100.0,
        }
        self.sent_pending = []
        self.modified_pending = []
        self.deleted_pending = []
        self.closed_positions = []
        self._next_ticket = 5000

    def get_rates(self, symbol, tf, count=200):
        return self._rates.get(tf.upper(), self._rates["M1"]).tail(count)

    def positions(self, symbol=None):
        return list(self._positions)

    def pending_orders(self, symbol=None):
        return list(self._pending)

    def account_info(self):
        return dict(self._account)

    def get_tick(self, symbol):
        return dict(self._tick)

    def symbol_spec(self, symbol):
        return dict(self._spec)

    def spread_points(self, symbol):
        return 30.0

    def history_deals(self, dt_from, dt_to):
        return []

    def send_pending_order(self, symbol, order_type, volume, price, sl=0.0, tp=0.0, magic=0, comment="mt5bot"):
        self._next_ticket += 1
        rec = {
            "ticket": self._next_ticket, "symbol": symbol, "type": order_type,
            "volume": volume, "price": price, "sl": sl, "tp": tp, "magic": magic, "comment": comment,
        }
        self.sent_pending.append(rec)
        self._pending.append(rec)
        return {"ok": True, "ticket": self._next_ticket, "message": ""}

    def modify_pending_order(self, ticket, price, sl=None, tp=None):
        self.modified_pending.append((int(ticket), float(price), sl, tp))
        for o in self._pending:
            if int(o["ticket"]) == int(ticket):
                o["price"] = float(price)
        return {"ok": True, "ticket": ticket, "message": ""}

    def delete_pending_order(self, ticket):
        self.deleted_pending.append(int(ticket))
        self._pending = [o for o in self._pending if int(o["ticket"]) != int(ticket)]
        return {"ok": True, "ticket": ticket, "message": ""}

    def close_position(self, ticket, symbol):
        self.closed_positions.append((int(ticket), symbol))
        self._positions = [p for p in self._positions if int(p["ticket"]) != int(ticket)]
        return {"ok": True, "ticket": ticket, "message": ""}


def test_ctx_pending_close_side_rates_and_spec():
    m1 = _make_df([2650.0 + i * 0.1 for i in range(40)])
    h1 = _make_df([2600.0 + i * 1.0 for i in range(150)], freq="1h")
    m15 = _make_df([2640.0 + i * 0.3 for i in range(60)], freq="15min")

    def provider(tf, count):
        return h1 if tf == "H1" else (m15 if tf == "M15" else m1)

    ctx = ScriptContext(
        m1, {},
        symbol="XAUUSDm",
        tick={"bid": 2650.0, "ask": 2650.3},
        spec={"point": 0.01, "digits": 2, "volume_min": 0.01, "volume_max": 50.0, "volume_step": 0.01, "stop_level": 30},
        pending_orders=[{"ticket": 101, "type": "buy_stop", "volume": 0.05, "price": 2652.0}],
        rates_provider=provider,
        state={"recovery_level": 2},
    )
    assert ctx.volume_min == 0.01 and ctx.volume_max == 50.0 and ctx.volume_step == 0.01
    assert ctx.stop_level == 30
    assert len(ctx.pending_orders) == 1
    assert ctx.state["recovery_level"] == 2

    h1_data = ctx.rates("H1", 150)
    assert len(h1_data["close"]) == 150
    m15_data = ctx.rates("M15", 60)
    assert len(ctx.atr(14, m15_data["high"], m15_data["low"], m15_data["close"])) == 60
    a, pdi, mdi = ctx.adx(14, m15_data["high"], m15_data["low"], m15_data["close"])
    assert a[-1] is not None and pdi[-1] > mdi[-1]

    assert ctx.buy_stop(2652.0, volume=0.05)["order_type"] == "buy_stop"
    assert ctx.sell_stop(2648.0, volume=0.05)["order_type"] == "sell_stop"
    assert ctx.buy_limit(2647.0, volume=0.08)["order_type"] == "buy_limit"
    assert ctx.sell_limit(2653.0, volume=0.08)["order_type"] == "sell_limit"
    assert ctx.modify_order({"ticket": 101}, 2651.5) == {"action": "MODIFY_ORDER", "ticket": 101, "price": 2651.5}
    assert ctx.delete_order(101) == {"action": "DELETE_ORDER", "ticket": 101}
    assert ctx.close_side("BUY") == {"action": "CLOSE_SIDE", "side": "BUY"}


def test_engine_executes_pending_close_side_and_persists_state(tmp_path, monkeypatch):
    state_file = tmp_path / "script_state.json"
    monkeypatch.setattr(be_mod, "SCRIPT_STATE_FILE", str(state_file))
    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "symbol", "XAUUSDm")
    monkeypatch.setattr(settings, "timeframe_str", "M1")
    monkeypatch.setattr(settings, "magic_number", 0)
    monkeypatch.setattr(settings, "daily_drawdown_limit", 0.0)
    monkeypatch.setattr(settings, "max_daily_trades", 0)
    monkeypatch.setattr(settings, "break_even_enabled", False)
    monkeypatch.setattr(settings, "trailing_stop_enabled", False)
    monkeypatch.setattr(settings, "strategy_name", "custom_script")

    src = """
NAME = "StateTest"
def on_bar(ctx):
    cnt = ctx.state.get("runs", 0) + 1
    ctx.state["runs"] = cnt
    if cnt == 1:
        return [ctx.buy_stop(2655.0, volume=0.05), ctx.close_side("BUY")]
    if cnt == 2 and ctx.pending_orders:
        return ctx.modify_order(ctx.pending_orders[0], 2654.0)
    if cnt == 3 and ctx.pending_orders:
        return ctx.delete_order(ctx.pending_orders[0])
    return None
"""
    monkeypatch.setattr(settings, "script_source", src)

    backend = _MockGridBackend(_make_df([2650.0] * 25))
    backend._positions = [
        {"ticket": 1, "symbol": "XAUUSDm", "type": "BUY", "volume": 0.05, "price_open": 2650.0, "sl": 0.0, "tp": 0.0, "magic": 0},
        {"ticket": 2, "symbol": "XAUUSDm", "type": "SELL", "volume": 0.05, "price_open": 2650.0, "sl": 0.0, "tp": 0.0, "magic": 0},
    ]

    eng = BotEngine(backend=backend)
    assert eng.process_trading_step() is True
    assert len(backend.sent_pending) == 1
    assert backend.closed_positions == [(1, "XAUUSDm")]  # Hanya BUY, SELL tetap aman
    assert state_file.exists()

    # Simulasikan restart engine: state "runs" harus tetap terbaca dari disk
    eng2 = BotEngine(backend=backend)
    assert eng2._script_state["runs"] == 1
    assert eng2.process_trading_step() is True
    assert len(backend.modified_pending) == 1 and backend.modified_pending[0][1] == 2654.0
    assert eng2.process_trading_step() is True
    assert len(backend.deleted_pending) == 1


def test_mcp_backend_modify_pending_order_cancel_and_replace():
    calls = []

    class FakeClient:
        def call_tool(self, name, arguments=None):
            calls.append((name, arguments))
            if name == "get_trading_open_positions":
                return {
                    "positions": [],
                    "orders": [{"ticket": 77, "symbol": "XAUUSDm", "type": "buy_stop", "volume": 0.05, "price": 2655.0, "sl": 0.0, "tp": 0.0, "magic": 0}],
                }
            return {"success": True, "ticket": 88}

    be = McpBackend.__new__(McpBackend)
    be._client = FakeClient()
    be.connected = True
    be._trade_allowed = True
    be._experts_trade_allowed = True
    be._server_connected = True
    be._symbol_cache = {}

    res = be.modify_pending_order(77, 2653.5)
    assert res["ok"] is True
    assert res["ticket"] == 88
    assert calls[1][0] == "trade_delete_order"
    assert calls[2][0] == "trade_send_pending_order"
    assert calls[2][1]["price"] == 2653.5


# ----- Uji Strategi Golden Mirror Grid XAUUSDm V1.1 di Sc Pribadi Trader -----

_GMG_PATH = Path(__file__).resolve().parents[2] / "Sc Pribadi Trader" / "golden_mirror_grid_xauusdm_v1_1.py"


@pytest.fixture
def gmg_source():
    if not _GMG_PATH.exists():
        pytest.skip("File GMG V1.1 tidak ditemukan di Sc Pribadi Trader")
    return _GMG_PATH.read_text(encoding="utf-8")


def _gmg_provider(h1_trend="up", m15_adx="strong_up"):
    if h1_trend == "up":
        h1 = _make_df([2550.0 + i * 1.2 for i in range(160)], freq="1h", step_hl=1.0)
    elif h1_trend == "down":
        h1 = _make_df([2750.0 - i * 1.2 for i in range(160)], freq="1h", step_hl=1.0)
    else:
        h1 = _make_df([2650.0 + ((i % 2) - 0.5) * 0.2 for i in range(160)], freq="1h", step_hl=0.5)

    if m15_adx == "strong_up":
        m15 = _make_df([2600.0 + i * 0.8 for i in range(80)], freq="15min", step_hl=0.5)
    elif m15_adx == "strong_down":
        m15 = _make_df([2700.0 - i * 0.8 for i in range(80)], freq="15min", step_hl=0.5)
    else:
        m15 = _make_df([2650.0 for _ in range(80)], freq="15min", step_hl=0.5)

    return lambda tf, count: h1.tail(count) if tf == "H1" else m15.tail(count)


def test_gmg_ast_compile_and_settings(gmg_source):
    ns = compile_script(gmg_source)
    assert callable(ns["on_bar"])
    st = extract_script_settings(ns)
    assert st["symbol"] == "XAUUSDm"
    assert st["timeframe_str"] == "M1"
    assert st["one_trade_per_bar"] is False
    assert st["close_on_reversal"] is False
    assert st["max_open_positions"] == 20


def test_gmg_seed_buy_stop_and_trailing(gmg_source):
    strat = ScriptStrategy(gmg_source)
    m1 = _make_df([2650.0] * 30)
    spec = {"point": 0.01, "digits": 2, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "stop_level": 20}

    # 1. Bullish trend -> pasang BUY_STOP
    strat.bind_runtime(
        symbol="XAUUSDm", positions=[], pending_orders=[],
        account={"balance": 10000.0, "equity": 10000.0},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("up", "strong_up"),
    )
    cmds = strat.generate_signal(m1)
    assert isinstance(cmds, list) and len(cmds) == 1
    assert cmds[0]["action"] == "PENDING"
    assert cmds[0]["order_type"] == "buy_stop"
    assert cmds[0]["volume"] == 0.05
    assert cmds[0]["price"] > 2650.30

    # 2. Harga turun -> seed BUY_STOP harus trail turun
    strat.bind_runtime(
        symbol="XAUUSDm", positions=[],
        pending_orders=[{"ticket": 10, "type": "buy_stop", "volume": 0.05, "price": 2660.0}],
        account={"balance": 10000.0, "equity": 10000.0},
        tick={"bid": 2648.0, "ask": 2648.30}, spec=spec,
        rates_provider=_gmg_provider("up", "strong_up"),
    )
    t_cmds = strat.generate_signal(m1)
    assert t_cmds and t_cmds[0]["action"] == "MODIFY_ORDER"
    assert t_cmds[0]["price"] < 2660.0

    # 3. Tren berubah netral -> hapus seed BUY_STOP
    strat.bind_runtime(
        symbol="XAUUSDm", positions=[],
        pending_orders=[{"ticket": 10, "type": "buy_stop", "volume": 0.05, "price": 2651.0}],
        account={"balance": 10000.0, "equity": 10000.0},
        tick={"bid": 2648.0, "ask": 2648.30}, spec=spec,
        rates_provider=_gmg_provider("neutral", "flat"),
    )
    c_cmds = strat.generate_signal(m1)
    assert c_cmds and c_cmds[0]["action"] == "DELETE_ORDER"


def test_gmg_neutral_recovery_grid_and_caps(gmg_source):
    strat = ScriptStrategy(gmg_source)
    m1 = _make_df([2650.0] * 30)
    spec = {"point": 0.01, "digits": 2, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "stop_level": 20}

    # Posisi BUY rugi -$2.00 (< -$0.50) saat tren NETRAL -> grid BUY_LIMIT harus terpasang dengan jarak lebih lebar (x1.5)
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 20, "type": "BUY", "volume": 0.05, "price_open": 2652.0, "profit": -2.0}],
        pending_orders=[],
        account={"balance": 10000.0, "equity": 9998.0},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("neutral", "flat"),
    )
    cmds_neutral = strat.generate_signal(m1)
    assert cmds_neutral and cmds_neutral[0]["order_type"] == "buy_limit"
    assert cmds_neutral[0]["volume"] == 0.08  # round(0.05 * 1.50 = 0.075) -> 0.08
    neutral_dist = 2650.0 - cmds_neutral[0]["price"]

    # Bandingkan saat tren searah bullish (jarak grid lebih rapat daripada neutral x1.5)
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 20, "type": "BUY", "volume": 0.05, "price_open": 2652.0, "profit": -2.0}],
        pending_orders=[],
        account={"balance": 10000.0, "equity": 9998.0},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("up", "strong_up"),
    )
    cmds_trend = strat.generate_signal(m1)
    trend_dist = 2650.0 - cmds_trend[0]["price"]
    assert neutral_dist > trend_dist

    # Jika tren terkonfirmasi BEARISH (berlawanan dengan BUY) -> TIDAK boleh pasang grid BUY_LIMIT
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 20, "type": "BUY", "volume": 0.05, "price_open": 2652.0, "profit": -2.0}],
        pending_orders=[],
        account={"balance": 10000.0, "equity": 9998.0},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("down", "strong_down"),
    )
    assert strat.generate_signal(m1) is None


def test_gmg_basket_tp_tiered_trail_loss_and_daily_dd(gmg_source):
    strat = ScriptStrategy(gmg_source)
    m1 = _make_df([2650.0] * 30)
    spec = {"point": 0.01, "digits": 2, "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "stop_level": 20}

    # 1. Tiered Basket Trailing: balance 10000 -> tier2 start 0.05% ($5.0), lock 0.03% ($3.0)
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 30, "type": "BUY", "volume": 0.05, "price_open": 2649.0, "profit": 6.0}],
        pending_orders=[],
        account={"balance": 10000.0, "equity": 10006.0},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("up", "strong_up"),
    )
    assert strat.generate_signal(m1) is None
    assert strat._state["buy_basket_peak"] == 6.0

    # Profit turun ke $2.50 (<= lock $3.0) -> tutup basket BUY
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 30, "type": "BUY", "volume": 0.05, "price_open": 2649.0, "profit": 2.5}],
        pending_orders=[],
        account={"balance": 10000.0, "equity": 10002.5},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("up", "strong_up"),
    )
    trail_close = strat.generate_signal(m1)
    assert trail_close and trail_close[0] == {"action": "CLOSE_SIDE", "side": "BUY"}

    # 2. Basket Loss Guard (1.50% = -$150) -> naikkan recovery_level = 1 & recovery_debt = 160
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 31, "type": "SELL", "volume": 0.10, "price_open": 2635.0, "profit": -160.0}],
        pending_orders=[],
        account={"balance": 10000.0, "equity": 9840.0},
        tick={"bid": 2650.0, "ask": 2650.30}, spec=spec,
        rates_provider=_gmg_provider("down", "strong_down"),
    )
    loss_close = strat.generate_signal(m1)
    assert loss_close and loss_close[0] == {"action": "CLOSE_SIDE", "side": "SELL"}
    assert strat._state["recovery_level"] == 1
    assert strat._state["recovery_debt"] == 160.0

    # 3. Daily Drawdown Guard (5.0% dari day_start_equity 10000 -> equity 9450) -> lock & close all
    strat.bind_runtime(
        symbol="XAUUSDm",
        positions=[{"ticket": 32, "type": "BUY", "volume": 0.10, "price_open": 2650.0, "profit": -550.0}],
        pending_orders=[{"ticket": 99, "type": "buy_limit", "volume": 0.15, "price": 2645.0}],
        account={"balance": 10000.0, "equity": 9450.0},
        tick={"bid": 2640.0, "ask": 2640.30}, spec=spec,
        rates_provider=_gmg_provider("up", "strong_up"),
    )
    dd_cmds = strat.generate_signal(m1)
    assert dd_cmds and any(c["action"] == "CLOSE_ALL" for c in dd_cmds)
    assert any(c["action"] == "DELETE_ORDER" for c in dd_cmds)
    assert strat._state["daily_locked"] is True
