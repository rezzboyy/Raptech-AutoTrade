"""Unit tests untuk SimBackend (Simulation Mode), Fast Script Replay, dan theme config."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import settings
from src import config_store
from src.backends.sim_backend import SimBackend, run_script_replay
from src.bot_engine import make_backend


def test_sim_backend_connect_and_account():
    sim = SimBackend(initial_balance=5000.0, symbol="XAUUSDm", scenario="uptrend", spread_points=20)
    assert sim.account_info() is None
    assert sim.connect() is True
    acc = sim.account_info()
    assert acc is not None
    assert acc["account_type"] == "SIMULASI"
    assert acc["balance"] == 5000.0
    assert acc["equity"] == 5000.0
    assert acc["trade_allowed"] is True
    assert acc["server_connected"] is True
    assert "XAUUSDm" in sim.list_symbols()


def test_sim_backend_market_order_sl_tp_and_close():
    sim = SimBackend(initial_balance=10000.0, symbol="EURUSDm", scenario="uptrend", spread_points=10)
    sim.connect()

    res = sim.send_market_order("EURUSDm", "BUY", 0.10, magic=77, comment="test_mkt")
    assert res["ok"] is True
    ticket = res["ticket"]
    assert isinstance(ticket, int)

    positions = sim.positions("EURUSDm")
    assert len(positions) == 1
    assert positions[0]["type"] == "BUY"
    assert positions[0]["magic"] == 77

    assert sim.modify_sl_tp(ticket, "EURUSDm", sl=positions[0]["price_open"] - 0.005, tp=positions[0]["price_open"] + 0.01) is True
    sim.step_bar("EURUSDm")

    closed = sim.close_position(ticket, "EURUSDm")
    assert closed["ok"] is True
    assert sim.positions("EURUSDm") == []

    deals = sim.history_deals(datetime.fromtimestamp(0, tz=timezone.utc), datetime.now(timezone.utc) + timedelta(days=30))
    assert len(deals) == 1
    assert deals[0]["ticket"] == ticket
    assert sim.balance == round(10000.0 + deals[0]["net_profit"], 2)


def test_sim_backend_pending_orders_lifecycle_and_trigger():
    sim = SimBackend(initial_balance=10000.0, symbol="XAUUSDm", scenario="volatile", spread_points=25)
    sim.connect()
    tick = sim.get_tick("XAUUSDm")
    assert tick is not None

    # 1. Pending order jauh -> modify & delete
    far_buy_limit = round(tick["bid"] - 50.0, 2)
    r1 = sim.send_pending_order("XAUUSDm", "buy_limit", 0.05, far_buy_limit, magic=123)
    assert r1["ok"] is True
    assert len(sim.pending_orders("XAUUSDm")) == 1

    mod = sim.modify_pending_order(r1["ticket"], far_buy_limit - 5.0)
    assert mod["ok"] is True
    assert sim.pending_orders("XAUUSDm")[0]["price_open"] == far_buy_limit - 5.0

    assert sim.delete_pending_order(r1["ticket"]) is True
    assert sim.pending_orders("XAUUSDm") == []

    # 2. Pending buy_stop tepat di harga saat ini -> terpicu oleh pergerakan bar
    near_stop = round(tick["ask"] + 0.01, 2)
    r2 = sim.send_pending_order("XAUUSDm", "buy_stop", 0.05, near_stop, magic=123)
    assert r2["ok"] is True
    for _ in range(10):
        sim.step_bar("XAUUSDm")
        if len(sim.positions("XAUUSDm")) >= 1:
            break
    assert len(sim.positions("XAUUSDm")) >= 1
    assert len(sim.pending_orders("XAUUSDm")) == 0


def test_sim_backend_multi_tf_rates_and_spread_spike():
    sim = SimBackend(initial_balance=10000.0, symbol="XAUUSDm", scenario="spread_spike", spread_points=20)
    sim.connect()

    for tf, cnt in (("M1", 60), ("M15", 30), ("H1", 20)):
        df = sim.get_rates("XAUUSDm", tf, count=cnt)
        assert df is not None
        assert not df.empty
        assert len(df) <= cnt
        assert list(df.columns) == ["time", "open", "high", "low", "close", "tick_volume"]
        assert df["time"].is_monotonic_increasing

    spreads = set()
    for _ in range(25):
        sim.step_bar("XAUUSDm")
        spreads.add(sim.spread_points("XAUUSDm"))
    assert 20.0 in spreads
    assert 100.0 in spreads


def test_make_backend_sim_and_config_store_theme_and_sim():
    orig_backend = settings.backend
    orig_theme = settings.theme
    try:
        errs = config_store.apply({"theme": "LIGHT", "backend": "SIM"})
        assert errs == []
        assert settings.theme == "light"
        assert settings.backend == "sim"

        b = make_backend()
        assert isinstance(b, SimBackend)

        bad_errs = config_store.apply({"theme": "sepia", "backend": "invalid_mode"})
        assert len(bad_errs) == 2
    finally:
        settings.backend = orig_backend
        settings.theme = orig_theme


def test_run_script_replay_valid_invalid_and_gmg():
    simple_script = '''
SETTINGS = {
    "symbol": "XAUUSDm",
    "timeframe": "M5",
    "volume": 0.02,
    "sl_points": 300,
    "tp_points": 500,
    "max_positions": 2,
    "one_trade_per_bar": False,
}

def on_bar(ctx):
    if len(ctx.positions) == 0:
        return ctx.buy()
    return None
'''
    res = run_script_replay(simple_script, symbol="XAUUSDm", timeframe="M5", scenario="uptrend", bars=30)
    assert res["ok"] is True
    assert res["actions_count"] >= 1
    assert (res["trades_count"] + res["open_positions"]) >= 1

    bad = run_script_replay("def on_bar(ctx)\n    return None", symbol="XAUUSDm")
    assert bad["ok"] is False
    assert bad["error"]

    runtime_bad = run_script_replay("def on_bar(ctx):\n    return 1 / 0\n", symbol="XAUUSDm")
    assert runtime_bad["ok"] is False
    assert runtime_bad["error"]

    gmg_path = Path(__file__).resolve().parents[2] / "Sc Pribadi Trader" / "golden_mirror_grid_xauusdm_v1_1.py"
    assert gmg_path.is_file(), f"Skrip GMG tidak ditemukan: {gmg_path}"
    gmg_source = gmg_path.read_text(encoding="utf-8")

    orig_script = settings.script_source
    orig_sym = settings.symbol
    gmg_res = run_script_replay(gmg_source, symbol="XAUUSDm", timeframe="M1", scenario="volatile", bars=60)
    assert gmg_res["ok"] is True, f"Replay GMG error: {gmg_res.get('error')}"
    assert settings.script_source == orig_script
    assert settings.symbol == orig_sym


def test_bridge_service_run_script_simulation_event():
    import bridge_server

    events = []

    class FakeEmitter:
        def send_event(self, event, data=None):
            events.append((event, data))

        def send_response(self, req_id, result=None, error=None):
            pass

    svc = bridge_server.BridgeService(FakeEmitter())
    script = "def on_bar(ctx):\n    return ctx.buy() if len(ctx.positions) == 0 else None\n"
    res = svc.handle_run_script_simulation({
        "source": script,
        "symbol": "EURUSDm",
        "timeframe": "M5",
        "scenario": "uptrend",
        "bars": 20,
        "initial_balance": 5000.0,
        "spread_points": 15,
    })
    assert res["ok"] is True
    assert any(ev == "simulationResult" and payload["ok"] is True for ev, payload in events)


def test_inspect_script_variables_valid_and_warnings():
    from strategies.script_runtime import inspect_script_variables

    valid_src = '''
SETTINGS = {"symbol": "XAUUSDm", "volume": 0.05, "max_spread_points": 50}
PARAMS = [{"key": "ema_fast", "default": 12}]

def on_bar(ctx):
    f = ctx.ema(ctx.close, ctx.params.ema_fast)
    if len(ctx.positions) == 0 and f:
        return ctx.buy()
    return None
'''
    r_ok = inspect_script_variables(valid_src)
    assert r_ok["ok"] is True
    assert r_ok["has_warnings"] is False
    assert r_ok["status"] == "VALID"

    warn_src = '''
SETTINGS = {"unknown_opt": 123}
PARAMS = []

def on_bar(ctx):
    x = ctx.params.missing_param
    return ctx.unknown_method()
'''
    r_warn = inspect_script_variables(warn_src)
    assert r_warn["ok"] is True
    assert r_warn["has_warnings"] is True
    assert r_warn["status"] == "PERINGATAN"
    assert "unknown_opt" in r_warn["unknown_settings"]
    assert "unknown_method" in r_warn["unknown_ctx"]
    assert "missing_param" in r_warn["undeclared_params"]

    # Verifikasi script pribadi GMG V1.1 (format PARAMS = {...} dict) -> VALID 0 warning
    gmg_path = Path(__file__).resolve().parents[2] / "Sc Pribadi Trader" / "golden_mirror_grid_xauusdm_v1_1.py"
    r_gmg = inspect_script_variables(gmg_path.read_text(encoding="utf-8"))
    assert r_gmg["ok"] is True
    assert r_gmg["has_warnings"] is False
    assert r_gmg["status"] == "VALID"
    assert r_gmg["unknown_settings"] == []
    assert r_gmg["unknown_ctx"] == []
    assert r_gmg["undeclared_params"] == []
