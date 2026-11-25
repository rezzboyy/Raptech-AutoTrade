"""Uji runtime skrip strategi kustom (Programmer Mode).

Cakupan:
    - kompilasi/validasi skrip (valid, kosong, sintaks error),
    - keamanan sandbox (import, dunder, eval/exec/open/__import__ ditolak),
    - indikator (sma/ema/rsi/crossover/crossunder),
    - ScriptStrategy menghasilkan sinyal benar dari skrip contoh,
    - skrip error saat on_bar ditangani (return None, tidak crash),
    - simpan/muat/daftar skrip.
"""

import os

import pandas as pd
import pytest

from strategies import script_runtime as sr
from strategies.script_runtime import (
    ScriptError, ScriptStrategy, ScriptContext, compile_script,
    sma, ema, rsi, crossover, crossunder,
    wma, stochastic, adx, cci, vwap,
    williams_r, obv, mfi, donchian, parabolic_sar, supertrend, ichimoku, pivot_points,
)


def _make_df(closes):
    n = len(closes)
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "tick_volume": [100] * n,
    })


# ----- Kompilasi & validasi -----

def test_compile_valid_script():
    ns = compile_script(sr.DEFAULT_TEMPLATE)
    assert callable(ns["on_bar"])
    assert isinstance(ns.get("PARAMS", []), list)


def test_compile_empty_script_rejected():
    with pytest.raises(ScriptError):
        compile_script("")
    with pytest.raises(ScriptError):
        compile_script("   \n  ")


def test_compile_syntax_error_rejected():
    with pytest.raises(ScriptError):
        compile_script("def on_bar(ctx)\n    return None")  # tanpa ':'


def test_compile_requires_on_bar():
    with pytest.raises(ScriptError):
        compile_script("PARAMS = []\n")


def test_validate_detail_ok():
    from strategies.script_runtime import validate_detail
    d = validate_detail(sr.DEFAULT_TEMPLATE)
    assert d["ok"] is True and d["line"] == 0


def test_validate_detail_syntax_error_lineno():
    from strategies.script_runtime import validate_detail
    # 'def' tanpa ':' di baris 2 -> error dengan lineno.
    src = "x = 1\ndef on_bar(ctx)\n    return None\n"
    d = validate_detail(src)
    assert d["ok"] is False
    assert d["line"] == 2
    assert d["message"]


def test_validate_detail_missing_on_bar():
    from strategies.script_runtime import validate_detail
    d = validate_detail("PARAMS = []\n")
    assert d["ok"] is False


def test_params_must_be_list():
    src = "PARAMS = 5\n\ndef on_bar(ctx):\n    return None\n"
    with pytest.raises(ScriptError):
        compile_script(src)


# ----- Keamanan sandbox -----

@pytest.mark.parametrize("bad_source", [
    "import os\n\ndef on_bar(ctx):\n    return None\n",
    "from os import path\n\ndef on_bar(ctx):\n    return None\n",
    "def on_bar(ctx):\n    return __import__('os')\n",
    "def on_bar(ctx):\n    return eval('1+1')\n",
    "def on_bar(ctx):\n    return exec('x=1')\n",
    "def on_bar(ctx):\n    return open('x.txt')\n",
    "def on_bar(ctx):\n    return ctx.__class__\n",
    "def on_bar(ctx):\n    return globals()\n",
    "def on_bar(ctx):\n    return getattr(ctx, 'x')\n",
])
def test_dangerous_scripts_blocked(bad_source):
    with pytest.raises(ScriptError):
        compile_script(bad_source)


# ----- Indikator -----

def test_sma_ema_basic():
    data = [1, 2, 3, 4, 5]
    assert sma(data, 2)[-1] == pytest.approx(4.5)
    # EMA harus mengembalikan nilai numerik tanpa None untuk seri penuh.
    e = ema(data, 3)
    assert e[-1] is not None


def test_rsi_bounds():
    data = list(range(1, 40))  # naik terus -> RSI tinggi
    r = rsi(data, 14)
    assert 0 <= r[-1] <= 100
    assert r[-1] > 70


def test_crossover_crossunder():
    a = [1, 2, 3]
    b = [3, 2, 1]
    assert crossover(a, b) is True
    assert crossunder(a, b) is False
    assert crossunder(b, a) is True


def test_crossover_short_series():
    assert crossover([1], [1]) is False


# ----- Indikator ekstra: WMA, Stochastic, ADX, CCI, VWAP -----

def test_wma_basic():
    # WMA([1,2,3], 3) = (1*1 + 2*2 + 3*3)/(1+2+3) = 14/6.
    out = wma([1, 2, 3], 3)
    assert out[-1] == pytest.approx(14.0 / 6.0)
    assert out[0] is None  # window belum penuh


def test_wma_more_weight_recent():
    # WMA harus lebih dekat ke nilai terbaru dibanding SMA saat tren naik.
    data = [1, 2, 3, 4, 5]
    assert wma(data, 3)[-1] > sma(data, 3)[-1]


def test_stochastic_bounds_and_high():
    highs = [i + 1 for i in range(1, 40)]
    lows = [i - 1 for i in range(1, 40)]
    closes = list(range(1, 40))  # naik terus -> %K tinggi
    k, d = stochastic(highs, lows, closes, k=14, d=3, smooth=3)
    assert 0 <= k[-1] <= 100
    assert k[-1] > 70


def test_stochastic_flat_series_neutral():
    n = 20
    k, d = stochastic([5.0] * n, [5.0] * n, [5.0] * n, k=14, d=3, smooth=3)
    assert k[-1] == pytest.approx(50.0)


def test_adx_uptrend_positive_di_dominates():
    closes = list(range(1, 40))
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    a, plus_di, minus_di = adx(highs, lows, closes, n=14)
    assert 0 <= a[-1] <= 100
    assert plus_di[-1] > minus_di[-1]  # tren naik -> +DI dominan


def test_cci_positive_on_uptrend():
    closes = list(range(1, 40))
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    out = cci(highs, lows, closes, n=20)
    assert out[-1] > 0


def test_vwap_between_low_and_high():
    highs = [10, 11, 12, 13, 14]
    lows = [8, 9, 10, 11, 12]
    closes = [9, 10, 11, 12, 13]
    vols = [100, 100, 100, 100, 100]
    out = vwap(highs, lows, closes, vols, n=3)
    assert lows[-1] <= out[-1] <= highs[-1]


def test_ctx_exposes_new_indicators():
    df = _make_df(list(range(1, 60)))
    ctx = ScriptContext(df, {})
    assert ctx.wma(ctx.close, 5)[-1] is not None
    k, d = ctx.stochastic(14, 3, 3)
    assert k[-1] is not None
    a, p, m = ctx.adx(14)
    assert a[-1] is not None
    assert ctx.cci(20)[-1] is not None
    assert ctx.vwap(14)[-1] is not None


def test_script_uses_new_indicator():
    src = ("def on_bar(ctx):\n"
           "    k, d = ctx.stochastic(14, 3, 3)\n"
           "    a, pdi, mdi = ctx.adx(14)\n"
           "    if k[-1] is None or a[-1] is None:\n"
           "        return None\n"
           "    if k[-1] > 50 and a[-1] > 15 and pdi[-1] > mdi[-1]:\n"
           "        return 'BUY'\n"
           "    return None\n")
    strat = ScriptStrategy(src)
    sig = strat.generate_signal(_make_df(list(range(1, 60))))
    assert sig in (None, "BUY")


# ----- Indikator ekstra Tahap 1: Williams %R, OBV, MFI, Donchian, PSAR, SuperTrend,
#       Ichimoku, Pivot Points -----

def test_williams_r_bounds_and_direction():
    closes = list(range(1, 40))  # naik terus -> mendekati 0 (jenuh beli)
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    out = williams_r(highs, lows, closes, 14)
    assert -100.0 <= out[-1] <= 0.0
    assert out[-1] > -30.0


def test_williams_r_flat_neutral():
    n = 20
    out = williams_r([5.0] * n, [5.0] * n, [5.0] * n, 14)
    assert out[-1] == pytest.approx(-50.0)


def test_obv_rising_on_uptrend():
    closes = [1, 2, 3, 4, 5]
    vols = [10, 10, 10, 10, 10]
    out = obv(closes, vols)
    # Naik terus -> OBV terakhir = jumlah volume bar ke-2..akhir = 40.
    assert out[-1] == pytest.approx(40.0)
    assert out[-1] > out[0]


def test_mfi_bounds_and_high_on_uptrend():
    closes = list(range(1, 40))
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [100] * len(closes)
    out = mfi(highs, lows, closes, vols, 14)
    assert 0.0 <= out[-1] <= 100.0
    assert out[-1] > 70.0


def test_donchian_channel():
    highs = [10, 12, 11, 15, 14]
    lows = [8, 9, 7, 10, 11]
    upper, mid, lower = donchian(highs, lows, 3)
    assert upper[-1] == pytest.approx(15.0)   # max high 3 bar terakhir
    assert lower[-1] == pytest.approx(7.0)    # min low 3 bar terakhir
    assert mid[-1] == pytest.approx(11.0)


def test_parabolic_sar_runs():
    closes = list(range(1, 30))
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    out = parabolic_sar(highs, lows)
    assert len(out) == len(closes)
    # Tren naik: SAR harus di BAWAH harga pada bar terakhir.
    assert out[-1] is not None and out[-1] < closes[-1]


def test_supertrend_direction_uptrend():
    closes = list(range(1, 40))
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    st, direction = supertrend(highs, lows, closes, 10, 3.0)
    assert len(st) == len(closes)
    assert direction[-1] == 1              # tren naik
    assert st[-1] is not None and st[-1] < closes[-1]


def test_ichimoku_shapes():
    closes = list(range(1, 80))
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    tenkan, kijun, senkou_a, senkou_b, chikou = ichimoku(highs, lows, closes)
    for series in (tenkan, kijun, senkou_a, senkou_b, chikou):
        assert len(series) == len(closes)
    assert kijun[-1] is not None


def test_pivot_points_ordering():
    p = pivot_points([12], [8], [11])
    assert p["s3"] < p["s2"] < p["s1"] < p["pivot"] < p["r1"] < p["r2"] < p["r3"]
    assert p["pivot"] == pytest.approx((12 + 8 + 11) / 3.0)


def test_ctx_exposes_tahap1_indicators():
    df = _make_df(list(range(1, 90)))
    ctx = ScriptContext(df, {})
    assert ctx.williams_r(14)[-1] is not None
    assert ctx.obv()[-1] is not None
    assert ctx.mfi(14)[-1] is not None
    up, mid, lo = ctx.donchian(20)
    assert up[-1] is not None
    assert ctx.parabolic_sar()[-1] is not None
    st, d = ctx.supertrend(10, 3.0)
    assert d[-1] in (1, -1)
    t, k, sa, sb, ch = ctx.ichimoku()
    assert k[-1] is not None
    piv = ctx.pivot_points()
    assert "pivot" in piv and "r1" in piv and "s1" in piv


# ----- ScriptStrategy: sinyal -----

def test_script_strategy_ema_cross_buy():
    """Harga naik tajam setelah turun -> EMA cepat memotong ke atas -> BUY."""
    src = sr.DEFAULT_TEMPLATE
    strat = ScriptStrategy(src, {"fast": 3, "slow": 6})
    # Deret turun lalu naik tajam untuk memicu crossover ke atas di bar terakhir.
    closes = [20, 19, 18, 17, 16, 15, 14, 13, 12, 30]
    sig = strat.generate_signal(_make_df(closes))
    assert sig is not None and sig.get("action") == "BUY"


def test_script_strategy_ema_cross_sell():
    src = sr.DEFAULT_TEMPLATE
    strat = ScriptStrategy(src, {"fast": 3, "slow": 6})
    closes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 2]
    sig = strat.generate_signal(_make_df(closes))
    assert sig is not None and sig.get("action") == "SELL"


def test_script_strategy_no_signal_returns_none():
    src = "def on_bar(ctx):\n    return None\n"
    strat = ScriptStrategy(src)
    assert strat.generate_signal(_make_df([1, 2, 3, 4, 5])) is None


def test_script_strategy_runtime_error_is_safe():
    """Error saat on_bar tidak boleh crash; harus mengembalikan None."""
    src = "def on_bar(ctx):\n    return ctx.close[999999]\n"  # IndexError
    strat = ScriptStrategy(src)
    assert strat.generate_signal(_make_df([1, 2, 3])) is None


def test_script_strategy_invalid_signal_becomes_none():
    src = "def on_bar(ctx):\n    return 'MAYBE'\n"
    strat = ScriptStrategy(src)
    assert strat.generate_signal(_make_df([1, 2, 3])) is None


def test_script_strategy_params_resolved():
    src = ("PARAMS = [{'key': 'p', 'type': 'int', 'default': 5}]\n\n"
           "def on_bar(ctx):\n    return None\n")
    strat = ScriptStrategy(src, {"p": "9"})
    assert strat.params["p"] == 9


# ----- Simpan / muat / daftar skrip -----

def test_save_load_list_script(tmp_path, monkeypatch):
    monkeypatch.setenv("XAVIQ_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(sr, "SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(sr, "_get_scripts_dir", lambda: str(tmp_path))
    src = sr.DEFAULT_TEMPLATE
    path = sr.save_script("uji coba!", src)
    assert path and os.path.exists(path)
    # Nama disanitasi -> spasi/tanda seru menjadi underscore.
    names = sr.list_scripts()
    assert any("uji" in n for n in names)
    loaded = sr.load_script("uji coba!")
    assert loaded == src


def test_load_missing_script_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("XAVIQ_SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(sr, "SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(sr, "_get_scripts_dir", lambda: str(tmp_path))
    assert sr.load_script("tidak_ada") == ""


# ----- Proteksi loop tak terbatas -----

def test_infinite_loop_is_stopped(monkeypatch):
    """Skrip dengan loop tak terbatas dihentikan watchdog -> return None."""
    monkeypatch.setattr(sr, "_MAX_EXEC_LINES", 5000)
    src = "def on_bar(ctx):\n    while True:\n        pass\n"
    strat = ScriptStrategy(src)
    assert strat.generate_signal(_make_df([1, 2, 3])) is None


# ----- Integrasi engine: skrip aktif dipakai engine (kolom script berfungsi) -----

def test_engine_builds_script_strategy_from_settings(monkeypatch):
    """settings custom_script -> BotEngine membangun ScriptStrategy yang benar."""
    from config.settings import settings
    from src.bot_engine import BotEngine

    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "strategy_name", "custom_script")
    monkeypatch.setattr(settings, "script_source", sr.DEFAULT_TEMPLATE)
    monkeypatch.setattr(settings, "strategy_params", {"fast": 3, "slow": 6})

    engine = BotEngine()
    assert isinstance(engine.strategy, ScriptStrategy)
    # Deret turun lalu melonjak -> crossover ke atas -> BUY.
    closes = [20, 19, 18, 17, 16, 15, 14, 13, 12, 30]
    sig = engine.strategy.generate_signal(_make_df(closes))
    assert sig is not None and sig.get("action") == "BUY"


def test_engine_invalid_script_falls_back(monkeypatch):
    """Skrip rusak -> engine fallback ke safe template Mode Programmer (tidak crash)."""
    from config.settings import settings
    from src.bot_engine import BotEngine

    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "strategy_name", "custom_script")
    monkeypatch.setattr(settings, "script_source", "def on_bar(ctx)\n  return None")  # sintaks error
    monkeypatch.setattr(settings, "strategy_params", {})

    engine = BotEngine()
    # Engine fallback ke safe template default ScriptStrategy tanpa crash
    assert isinstance(engine.strategy, ScriptStrategy)
    assert engine.strategy.name == "custom_script"


# ----- Order intent gaya cBot (skrip mengontrol SL/TP/volume) -----

def test_ctx_buy_sell_intent():
    ctx = ScriptContext(_make_df([1, 2, 3]), {})
    b = ctx.buy(volume=0.2, sl_points=100, tp_points=200)
    assert b == {"action": "BUY", "volume": 0.2, "sl_points": 100, "tp_points": 200}
    s = ctx.sell(sl=1.2, tp=1.1, risk=0.02, comment="x")
    assert s["action"] == "SELL" and s["sl"] == 1.2 and s["tp"] == 1.1
    assert s["risk"] == 0.02 and s["comment"] == "x"


def test_script_returns_intent_dict():
    src = ("def on_bar(ctx):\n"
           "    return ctx.buy(volume=0.3, sl_points=150, tp_points=300)\n")
    strat = ScriptStrategy(src)
    sig = strat.generate_signal(_make_df([1, 2, 3, 4, 5]))
    assert isinstance(sig, dict)
    assert sig["action"] == "BUY" and sig["volume"] == 0.3


def test_script_intent_invalid_action_becomes_none():
    src = "def on_bar(ctx):\n    return {'action': 'HOLD'}\n"
    strat = ScriptStrategy(src)
    assert strat.generate_signal(_make_df([1, 2, 3])) is None


class _FakeBackend:
    """Backend palsu minimal untuk menguji _handle_signal tanpa MT5."""
    def get_tick(self, symbol):
        return {"bid": 1.1000, "ask": 1.1002}
    def symbol_spec(self, symbol):
        return {"point": 0.0001, "digits": 5}
    def account_info(self):
        return {"balance": 10000.0}
    def positions(self, symbol=None):
        return []


def test_engine_uses_script_volume_and_sltp(monkeypatch):
    """Intent skrip (volume + sl/tp points) dipakai engine saat order."""
    from config.settings import settings
    from src.bot_engine import BotEngine
    from src import trade_rules

    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "strategy_name", "custom_script")
    monkeypatch.setattr(settings, "script_source", sr.DEFAULT_TEMPLATE)
    monkeypatch.setattr(settings, "strategy_params", {})
    monkeypatch.setattr(settings, "virtual_sltp_enabled", False)

    engine = BotEngine()
    engine.backend = _FakeBackend()

    captured = {}
    def _fake_open(backend, settings_, symbol, side, volume, sl=0.0, tp=0.0, comment="mt5bot"):
        captured.update({"symbol": symbol, "side": side, "volume": volume, "sl": sl, "tp": tp})
        return {"ok": True, "ticket": 1}
    monkeypatch.setattr(trade_rules, "open_order_if_allowed", _fake_open)

    engine._handle_signal("EURUSD", "BUY", {"action": "BUY", "volume": 0.5,
                                            "sl_points": 100, "tp_points": 200})

    assert captured["volume"] == 0.5
    assert captured["side"] == "buy"
    # entry ask=1.1002; SL 100 pts (0.01) di bawah, TP 200 pts di atas.
    assert abs(captured["sl"] - (1.1002 - 100 * 0.0001)) < 1e-9
    assert abs(captured["tp"] - (1.1002 + 200 * 0.0001)) < 1e-9


def test_engine_script_absolute_sltp(monkeypatch):
    """Intent skrip dengan SL/TP HARGA absolut dipakai apa adanya."""
    from config.settings import settings
    from src.bot_engine import BotEngine
    from src import trade_rules

    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "strategy_name", "custom_script")
    monkeypatch.setattr(settings, "script_source", sr.DEFAULT_TEMPLATE)
    monkeypatch.setattr(settings, "strategy_params", {})
    monkeypatch.setattr(settings, "virtual_sltp_enabled", False)

    engine = BotEngine()
    engine.backend = _FakeBackend()

    captured = {}
    def _fake_open(backend, settings_, symbol, side, volume, sl=0.0, tp=0.0, comment="mt5bot"):
        captured.update({"sl": sl, "tp": tp, "volume": volume})
        return {"ok": True, "ticket": 1}
    monkeypatch.setattr(trade_rules, "open_order_if_allowed", _fake_open)

    engine._handle_signal("EURUSD", "SELL", {"action": "SELL", "volume": 0.1,
                                             "sl": 1.2000, "tp": 1.0500})
    assert captured["sl"] == 1.2000 and captured["tp"] == 1.0500


# ----- Konteks runtime: ctx.position / balance -----

def test_bind_runtime_exposes_position_and_balance():
    src = ("def on_bar(ctx):\n"
           "    if ctx.position and ctx.position.get('volume', 0) > 0:\n"
           "        return None\n"
           "    if ctx.balance > 5000:\n"
           "        return 'BUY'\n"
           "    return None\n")
    strat = ScriptStrategy(src)

    # Tanpa posisi + saldo cukup -> BUY.
    strat.bind_runtime(symbol="EURUSD", positions=[], account={"balance": 10000.0})
    assert strat.generate_signal(_make_df([1, 2, 3])) == "BUY"

    # Ada posisi terbuka -> guard aktif -> None (anti tumpuk posisi).
    strat.bind_runtime(symbol="EURUSD", positions=[{"volume": 0.1, "type": "BUY"}],
                       account={"balance": 10000.0})
    assert strat.generate_signal(_make_df([1, 2, 3])) is None


def test_context_position_defaults_none():
    """Tanpa bind_runtime, ctx.position None & balance 0 (aman)."""
    strat = ScriptStrategy("def on_bar(ctx):\n    return 'BUY' if ctx.position is None else None\n")
    assert strat.generate_signal(_make_df([1, 2, 3])) == "BUY"


# ----- Harga/spread live + waktu/sesi -----

def test_context_tick_spread_and_time():
    ctx = ScriptContext(_make_df([1, 2, 3]), {},
                        tick={"bid": 1.1000, "ask": 1.1003},
                        spec={"point": 0.0001, "digits": 5})
    assert ctx.bid == 1.1000 and ctx.ask == 1.1003
    assert ctx.spread == 3  # (0.0003 / 0.0001)
    assert ctx.point == 0.0001 and ctx.digits == 5
    # Waktu selalu terisi (bar time bila ada, else now).
    assert 0 <= ctx.hour <= 23
    assert 0 <= ctx.weekday <= 6


def test_bind_runtime_passes_tick_to_script():
    src = ("def on_bar(ctx):\n"
           "    if ctx.spread > 50:\n"
           "        return None\n"
           "    return 'BUY'\n")
    strat = ScriptStrategy(src)
    strat.bind_runtime(symbol="EURUSD", tick={"bid": 1.0, "ask": 1.02},
                       spec={"point": 0.0001, "digits": 5})  # spread 200 -> tolak
    assert strat.generate_signal(_make_df([1, 2, 3])) is None
    strat.bind_runtime(symbol="EURUSD", tick={"bid": 1.0, "ask": 1.0002},
                       spec={"point": 0.0001, "digits": 5})  # spread 2 -> BUY
    assert strat.generate_signal(_make_df([1, 2, 3])) == "BUY"


# ----- Perintah close / close_all / modify -----

def test_ctx_close_and_modify_commands():
    ctx = ScriptContext(_make_df([1, 2, 3]), {},
                        positions=[{"ticket": 55, "type": "BUY", "volume": 0.1}])
    assert ctx.close_position() == {"action": "CLOSE", "ticket": 55}
    assert ctx.close_position({"ticket": 77}) == {"action": "CLOSE", "ticket": 77}
    assert ctx.close_position({"position_id": 88}) == {"action": "CLOSE", "ticket": 88}
    assert ctx.close_position(99) == {"action": "CLOSE", "ticket": 99}
    assert ctx.close_all() == {"action": "CLOSE_ALL"}
    m = ctx.modify(sl=1.2, tp=1.3)
    assert m == {"action": "MODIFY", "ticket": 55, "sl": 1.2, "tp": 1.3}


def test_ctx_close_none_when_no_position():
    ctx = ScriptContext(_make_df([1, 2, 3]), {}, positions=[])
    assert ctx.close_position() is None
    assert ctx.modify(sl=1.2) is None


def test_script_returns_list_of_commands():
    src = ("def on_bar(ctx):\n"
           "    return [ctx.close_position(ctx.position), ctx.buy(volume=0.1)]\n")
    strat = ScriptStrategy(src)
    strat.bind_runtime(symbol="EURUSD", positions=[{"ticket": 9, "type": "SELL", "volume": 0.1}])
    out = strat.generate_signal(_make_df([1, 2, 3]))
    assert isinstance(out, list) and len(out) == 2
    assert out[0]["action"] == "CLOSE" and out[1]["action"] == "BUY"


# ----- Engine: normalisasi & eksekusi perintah -----

def test_engine_normalize_commands():
    from src.bot_engine import BotEngine
    assert BotEngine._normalize_commands(None) == []
    assert BotEngine._normalize_commands("BUY") == [{"action": "BUY"}]
    assert BotEngine._normalize_commands("HOLD") == []
    assert BotEngine._normalize_commands({"action": "CLOSE", "ticket": 1}) == [{"action": "CLOSE", "ticket": 1}]
    lst = BotEngine._normalize_commands([{"action": "BUY"}, {"nope": 1}, {"action": "CLOSE"}])
    assert lst == [{"action": "BUY"}, {"action": "CLOSE"}]


class _RecordBackend(_FakeBackend):
    def __init__(self):
        self.closed = []
        self.modified = []
        self._positions = [{"ticket": 10, "symbol": "EURUSD", "magic": 0, "volume": 0.1}]
    def positions(self, symbol=None):
        return list(self._positions)
    def close_position(self, ticket, symbol):
        self.closed.append((int(ticket), symbol))
        return {"ok": True}
    def modify_sl_tp(self, ticket, symbol, sl=None, tp=None):
        self.modified.append((int(ticket), symbol, sl, tp))
        return True


def test_engine_executes_close_and_modify(monkeypatch):
    from config.settings import settings
    from src.bot_engine import BotEngine

    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "strategy_name", "custom_script")
    monkeypatch.setattr(settings, "script_source", sr.DEFAULT_TEMPLATE)
    monkeypatch.setattr(settings, "strategy_params", {})
    monkeypatch.setattr(settings, "magic_number", 0)

    engine = BotEngine()
    rec = _RecordBackend()
    engine.backend = rec

    engine._execute_command("EURUSD", {"action": "CLOSE", "ticket": 10})
    assert rec.closed == [(10, "EURUSD")]

    engine._execute_command("EURUSD", {"action": "MODIFY", "ticket": 10, "sl": 1.23, "tp": 1.30})
    assert rec.modified == [(10, "EURUSD", 1.23, 1.30)]

    rec.closed.clear()
    engine._execute_command("EURUSD", {"action": "CLOSE_ALL"})
    assert rec.closed == [(10, "EURUSD")]


def test_engine_journal_callback(monkeypatch):
    """_execute_command memancarkan entri jurnal untuk CLOSE/MODIFY/CLOSE_ALL."""
    from config.settings import settings
    from src.bot_engine import BotEngine

    monkeypatch.setattr(settings, "backend", "native")
    monkeypatch.setattr(settings, "strategy_name", "custom_script")
    monkeypatch.setattr(settings, "script_source", sr.DEFAULT_TEMPLATE)
    monkeypatch.setattr(settings, "strategy_params", {})
    monkeypatch.setattr(settings, "magic_number", 0)

    engine = BotEngine()
    engine.backend = _RecordBackend()
    entries = []
    engine.on_journal = entries.append

    engine._execute_command("EURUSDm", {"action": "CLOSE", "ticket": 10})
    engine._execute_command("EURUSDm", {"action": "MODIFY", "ticket": 10, "sl": 1.2, "tp": 1.3})
    engine._execute_command("EURUSDm", {"action": "CLOSE_ALL"})

    actions = [e["action"] for e in entries]
    assert "CLOSE" in actions and "MODIFY" in actions and "CLOSE_ALL" in actions
    for e in entries:
        assert e["symbol"] == "EURUSDm" and "detail" in e and "ok" in e
