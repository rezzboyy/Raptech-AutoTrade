"""Runtime skrip strategi kustom (Programmer Mode).

Pengguna menulis skrip Python berisi `PARAMS` (opsional) + fungsi `on_bar(ctx)`
yang mengembalikan "BUY", "SELL", atau None. Skrip dijalankan dalam SANDBOX:
    - Tanpa import, akses file/OS, eval/exec, atau atribut dunder (__xxx__).
    - Hanya builtins aman + API indikator lewat objek `ctx`.

Skrip error (sintaks/runtime) TIDAK membuat bot crash: ditangkap, dilog, dan
diperlakukan sebagai "tanpa sinyal" (fail-safe).
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone

import pandas as pd

from strategies.base import Strategy, SIGNAL_BUY, SIGNAL_SELL
from src.logger import get_logger

# Aksi perintah yang dikenali engine dari skrip.
_VALID_ACTIONS = {
    SIGNAL_BUY, SIGNAL_SELL,
    "CLOSE", "CLOSE_ALL", "CLOSE_SIDE", "MODIFY",
    "PENDING", "DELETE_ORDER", "MODIFY_ORDER",
}

logger = get_logger("mt5bot")


class ScriptError(Exception):
    """Kesalahan kompilasi/keamanan skrip strategi."""


class ScriptTimeout(Exception):
    """Skrip melebihi batas langkah eksekusi (dugaan loop tak terbatas)."""


# Batas jumlah baris yang dieksekusi dalam satu panggilan on_bar. Melindungi
# dari loop tak terbatas (mis. `while True`). Nilai besar agar skrip normal
# (indikator, iterasi wajar) tetap lolos.
_MAX_EXEC_LINES = 2_000_000


def _run_guarded(fn, ctx):
    """Jalankan `fn(ctx)` dengan pengawas jumlah langkah (anti loop tak terbatas).

    Memakai sys.settrace untuk menghitung event 'line'; bila melebihi batas,
    memicu ScriptTimeout yang menghentikan eksekusi skrip. Trace hanya aktif
    selama pemanggilan ini dan hanya di thread saat ini.
    """
    import sys

    counter = {"n": 0}

    def _tracer(frame, event, arg):
        if event == "line":
            counter["n"] += 1
            if counter["n"] > _MAX_EXEC_LINES:
                raise ScriptTimeout(
                    f"melebihi {_MAX_EXEC_LINES} langkah (kemungkinan loop tak terbatas)")
        return _tracer

    old = sys.gettrace()
    sys.settrace(_tracer)
    try:
        return fn(ctx)
    finally:
        sys.settrace(old)


# ----- Builtins aman yang diizinkan di dalam skrip -----
_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "round": round, "len": len,
    "range": range, "sum": sum, "float": float, "int": int, "bool": bool,
    "str": str, "enumerate": enumerate, "sorted": sorted, "zip": zip,
    "map": map, "filter": filter, "all": all, "any": any,
    "True": True, "False": False, "None": None,
}

# Node AST yang DILARANG (keamanan).
_FORBIDDEN_NODES = (ast.Import, ast.ImportFrom)
if hasattr(ast, "Exec"):  # py2 safety, tak relevan di 3
    _FORBIDDEN_NODES = _FORBIDDEN_NODES + (ast.Exec,)


def _audit_ast(tree: ast.AST) -> None:
    """Tolak konstruksi berbahaya: import, dunder, fungsi terlarang."""
    banned_calls = {"eval", "exec", "compile", "__import__", "open", "globals",
                    "locals", "vars", "getattr", "setattr", "delattr", "input",
                    "exit", "quit", "help", "memoryview", "type"}
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODES):
            raise ScriptError("Dilarang: 'import' tidak diizinkan di skrip.")
        # Larang akses/nama dunder (mis. __globals__, __class__).
        if isinstance(node, ast.Name) and node.id.startswith("__") and node.id.endswith("__"):
            raise ScriptError(f"Dilarang: penggunaan '{node.id}'.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
            raise ScriptError(f"Dilarang: akses atribut '{node.attr}'.")
        # Larang pemanggilan fungsi berbahaya.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in banned_calls:
                raise ScriptError(f"Dilarang: memanggil '{node.func.id}'.")


def compile_script(source: str) -> dict:
    """Kompilasi + audit skrip. Kembalikan namespace berisi PARAMS & on_bar.

    Raise ScriptError bila tidak aman / tidak valid.
    """
    if not source or not source.strip():
        raise ScriptError("Skrip kosong.")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise ScriptError(f"Sintaks error baris {exc.lineno}: {exc.msg}") from exc

    _audit_ast(tree)

    namespace = {"__builtins__": _SAFE_BUILTINS}
    try:
        code = compile(tree, "<strategy_script>", "exec")
        exec(code, namespace)  # noqa: S102 - dijalankan dalam sandbox terbatas
    except Exception as exc:  # noqa: BLE001
        raise ScriptError(f"Error saat memuat skrip: {exc}") from exc

    if "on_bar" not in namespace or not callable(namespace["on_bar"]):
        raise ScriptError("Skrip harus mendefinisikan fungsi on_bar(ctx).")

    params = namespace.get("PARAMS", None)
    if params is not None and not isinstance(params, (list, dict)):
        raise ScriptError("PARAMS harus berupa dict atau list (atau dihilangkan).")

    return namespace


class ParamDict(dict):
    """Dictionary yang mendukung akses lewat dot notation (ctx.params.fast) dan key (ctx.params['fast'])."""

    def __getattr__(self, name: str):
        if name in self:
            val = self[name]
            if isinstance(val, dict) and not isinstance(val, ParamDict):
                return ParamDict(val)
            return val
        raise AttributeError(f"Parameter/setting '{name}' tidak ditemukan.")

    def __setattr__(self, name: str, value):
        self[name] = value

    def __delattr__(self, name: str):
        if name in self:
            del self[name]
        else:
            raise AttributeError(f"Parameter/setting '{name}' tidak ditemukan.")


def extract_script_settings(namespace: dict) -> dict:
    """Ekstrak konfigurasi trading yang didefinisikan langsung di dalam skrip.

    Mendukung kamus terpusat SETTINGS = {...} maupun konstanta huruf besar
    level-atas (mis. SYMBOL = "EURUSDm", TIMEFRAME = "M5", LOT = 0.01,
    SL_POINTS = 300, TP_POINTS = 600, MAX_POSITIONS = 1, dll).
    """
    settings_out = {}

    # 1. Baca dari kamus SETTINGS bila ada
    raw_dict = namespace.get("SETTINGS", {})
    if isinstance(raw_dict, dict):
        settings_out.update(raw_dict)

    # 2. Baca dari konstanta huruf besar level-atas (override / lengkapi)
    for k, v in namespace.items():
        if k.startswith("_"):
            continue
        if k in ("PARAMS", "SETTINGS", "on_bar"):
            continue
        if k.isupper():
            settings_out[k.lower()] = v

    normalized = {}

    def _to_int(val, default=None):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def _to_float(val, default=None):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def _to_bool(val, default=None):
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val) if val is not None else default

    # Symbol
    sym = settings_out.get("symbol")
    if sym and isinstance(sym, str) and sym.strip():
        normalized["symbol"] = sym.strip()

    # Timeframe
    tf = settings_out.get("timeframe") or settings_out.get("timeframe_str")
    if tf and isinstance(tf, str) and tf.strip():
        normalized["timeframe_str"] = tf.strip().upper()

    # Volume / Lot
    vol = settings_out.get("volume") if settings_out.get("volume") is not None else settings_out.get("lot")
    if vol is not None:
        v_float = _to_float(vol)
        if v_float is not None and v_float > 0:
            normalized["volume"] = v_float
            normalized["lot"] = v_float

    # Risk per trade
    risk = settings_out.get("risk") if settings_out.get("risk") is not None else settings_out.get("risk_per_trade")
    if risk is not None:
        r_float = _to_float(risk)
        if r_float is not None and 0 < r_float <= 1:
            normalized["risk_per_trade"] = r_float
            normalized["risk"] = r_float

    # SL / TP Points
    sl = settings_out.get("sl_points") if settings_out.get("sl_points") is not None else settings_out.get("sl")
    if sl is not None:
        sl_int = _to_int(sl)
        if sl_int is not None and sl_int >= 0:
            normalized["sl_points"] = sl_int
            normalized["sl"] = sl_int

    tp = settings_out.get("tp_points") if settings_out.get("tp_points") is not None else settings_out.get("tp")
    if tp is not None:
        tp_int = _to_int(tp)
        if tp_int is not None and tp_int >= 0:
            normalized["tp_points"] = tp_int
            normalized["tp"] = tp_int

    # SL / TP Percent & Mode
    sl_pct = settings_out.get("sl_percent")
    if sl_pct is not None:
        sl_pct_f = _to_float(sl_pct)
        if sl_pct_f is not None and sl_pct_f > 0:
            normalized["sl_percent"] = sl_pct_f

    tp_pct = settings_out.get("tp_percent")
    if tp_pct is not None:
        tp_pct_f = _to_float(tp_pct)
        if tp_pct_f is not None and tp_pct_f > 0:
            normalized["tp_percent"] = tp_pct_f

    mode = settings_out.get("sl_tp_mode")
    if mode and str(mode).lower() in ("points", "percent"):
        normalized["sl_tp_mode"] = str(mode).lower()

    # Max Positions
    max_pos = settings_out.get("max_positions") if settings_out.get("max_positions") is not None else settings_out.get("max_open_positions")
    if max_pos is not None:
        mp_int = _to_int(max_pos)
        if mp_int is not None and mp_int >= 1:
            normalized["max_open_positions"] = mp_int
            normalized["max_positions"] = mp_int

    # Magic Number
    magic = settings_out.get("magic_number") if settings_out.get("magic_number") is not None else settings_out.get("magic")
    if magic is not None:
        mg_int = _to_int(magic)
        if mg_int is not None:
            normalized["magic_number"] = mg_int

    # Trailing Stop
    tr_pts = settings_out.get("trailing_stop_points") if settings_out.get("trailing_stop_points") is not None else settings_out.get("trailing_stop")
    if tr_pts is not None:
        tr_int = _to_int(tr_pts)
        if tr_int is not None and tr_int > 0:
            normalized["trailing_stop_points"] = tr_int
            if "trailing_stop_enabled" not in settings_out:
                normalized["trailing_stop_enabled"] = True

    tr_step = settings_out.get("trailing_step_points") if settings_out.get("trailing_step_points") is not None else settings_out.get("trailing_step")
    if tr_step is not None:
        trs_int = _to_int(tr_step)
        if trs_int is not None and trs_int > 0:
            normalized["trailing_step_points"] = trs_int

    if "trailing_stop_enabled" in settings_out:
        normalized["trailing_stop_enabled"] = _to_bool(settings_out["trailing_stop_enabled"], False)

    # Break-Even
    be_pts = settings_out.get("break_even_trigger_points") or settings_out.get("break_even_points") or settings_out.get("break_even")
    if be_pts is not None:
        be_int = _to_int(be_pts)
        if be_int is not None and be_int > 0:
            normalized["break_even_trigger_points"] = be_int
            normalized["break_even_points"] = be_int
            if "break_even_enabled" not in settings_out:
                normalized["break_even_enabled"] = True

    be_off = settings_out.get("break_even_offset_points") or settings_out.get("break_even_offset")
    if be_off is not None:
        beo_int = _to_int(be_off)
        if beo_int is not None:
            normalized["break_even_offset_points"] = beo_int

    if "break_even_enabled" in settings_out:
        normalized["break_even_enabled"] = _to_bool(settings_out["break_even_enabled"], False)

    # Proteksi
    max_sp = settings_out.get("max_spread_points") if settings_out.get("max_spread_points") is not None else settings_out.get("max_spread")
    if max_sp is not None:
        msp_int = _to_int(max_sp)
        if msp_int is not None and msp_int >= 0:
            normalized["max_spread_points"] = msp_int

    dd_lim = settings_out.get("daily_drawdown_limit")
    if dd_lim is not None:
        dd_f = _to_float(dd_lim)
        if dd_f is not None and 0 <= dd_f <= 1:
            normalized["daily_drawdown_limit"] = dd_f

    esl = settings_out.get("equity_stop_loss")
    if esl is not None:
        esl_f = _to_float(esl)
        if esl_f is not None and 0 <= esl_f <= 1:
            normalized["equity_stop_loss"] = esl_f

    mcl = settings_out.get("max_consecutive_losses")
    if mcl is not None:
        mcl_int = _to_int(mcl)
        if mcl_int is not None and mcl_int >= 0:
            normalized["max_consecutive_losses"] = mcl_int

    mdt = settings_out.get("max_daily_trades")
    if mdt is not None:
        mdt_int = _to_int(mdt)
        if mdt_int is not None and mdt_int >= 0:
            normalized["max_daily_trades"] = mdt_int

    mel = settings_out.get("max_exposure_lots")
    if mel is not None:
        mel_f = _to_float(mel)
        if mel_f is not None and mel_f >= 0:
            normalized["max_exposure_lots"] = mel_f

    vsltp = settings_out.get("virtual_sltp_enabled")
    if vsltp is not None:
        normalized["virtual_sltp_enabled"] = _to_bool(vsltp, False)

    loop_iv = settings_out.get("loop_interval")
    if loop_iv is not None:
        li_int = _to_int(loop_iv)
        if li_int is not None and li_int >= 1:
            normalized["loop_interval"] = li_int

    comment = settings_out.get("comment")
    if comment is not None:
        normalized["comment"] = str(comment).strip()

    name = settings_out.get("name") or settings_out.get("strategy_name")
    if name and isinstance(name, str) and name.strip():
        normalized["name"] = name.strip()

    # --- 1. Filter Waktu & Sesi Pasar ---
    t_start = settings_out.get("trade_start_time") or settings_out.get("start_time")
    if t_start and isinstance(t_start, str) and ":" in t_start:
        normalized["trade_start_time"] = t_start.strip()

    t_end = settings_out.get("trade_end_time") or settings_out.get("end_time")
    if t_end and isinstance(t_end, str) and ":" in t_end:
        normalized["trade_end_time"] = t_end.strip()

    cfh = settings_out.get("close_friday_hour")
    if cfh is not None:
        cfh_int = _to_int(cfh)
        if cfh_int is not None and 0 <= cfh_int <= 23:
            normalized["close_friday_hour"] = cfh_int

    act_days = settings_out.get("active_days")
    if act_days is not None:
        if isinstance(act_days, (list, tuple)):
            days = []
            for d in act_days:
                d_int = _to_int(d)
                if d_int is not None and 0 <= d_int <= 6:
                    days.append(d_int)
            normalized["active_days"] = sorted(set(days))
        elif isinstance(act_days, str):
            days = []
            for d in act_days.replace(";", ",").split(","):
                d_int = _to_int(d.strip())
                if d_int is not None and 0 <= d_int <= 6:
                    days.append(d_int)
            if days:
                normalized["active_days"] = sorted(set(days))

    # --- 2. Sizing & SL/TP Dinamis (Rasio & ATR) ---
    rr = settings_out.get("risk_reward_ratio") or settings_out.get("rr_ratio") or settings_out.get("risk_reward")
    if rr is not None:
        rr_f = _to_float(rr)
        if rr_f is not None and rr_f > 0:
            normalized["risk_reward_ratio"] = rr_f

    asl = settings_out.get("atr_sl_mult") or settings_out.get("atr_sl_multiplier")
    if asl is not None:
        asl_f = _to_float(asl)
        if asl_f is not None and asl_f > 0:
            normalized["atr_sl_mult"] = asl_f

    atp = settings_out.get("atr_tp_mult") or settings_out.get("atr_tp_multiplier")
    if atp is not None:
        atp_f = _to_float(atp)
        if atp_f is not None and atp_f > 0:
            normalized["atr_tp_mult"] = atp_f

    slip = settings_out.get("max_slippage_points") or settings_out.get("slippage")
    if slip is not None:
        slip_int = _to_int(slip)
        if slip_int is not None and slip_int >= 0:
            normalized["max_slippage_points"] = slip_int

    # --- 3. Kontrol Entry & Anti-Spam Bar ---
    cd = settings_out.get("cooldown_bars") or settings_out.get("min_bars_between_trades")
    if cd is not None:
        cd_int = _to_int(cd)
        if cd_int is not None and cd_int >= 0:
            normalized["cooldown_bars"] = cd_int

    if "one_trade_per_bar" in settings_out:
        normalized["one_trade_per_bar"] = _to_bool(settings_out["one_trade_per_bar"], True)

    if "close_on_reversal" in settings_out:
        normalized["close_on_reversal"] = _to_bool(settings_out["close_on_reversal"], True)

    mml = settings_out.get("min_margin_level")
    if mml is not None:
        mml_f = _to_float(mml)
        if mml_f is not None and mml_f >= 0:
            normalized["min_margin_level"] = mml_f

    # --- 4. Exit Lanjutan & Holding ---
    mhb = settings_out.get("max_holding_bars") or settings_out.get("holding_bars")
    if mhb is not None:
        mhb_int = _to_int(mhb)
        if mhb_int is not None and mhb_int > 0:
            normalized["max_holding_bars"] = mhb_int

    return normalized


def validate_detail(source: str) -> dict:
    """Validasi skrip + kembalikan detail untuk editor: {ok, line, message}.

    `line` = nomor baris error (0 bila tidak diketahui). Dipakai editor untuk
    menandai baris merah secara real-time.
    """
    try:
        compile_script(source)
        return {"ok": True, "line": 0, "message": ""}
    except ScriptError as exc:
        msg = str(exc)
        m = re.search(r"baris (\d+)", msg)
        return {"ok": False, "line": int(m.group(1)) if m else 0, "message": msg}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "line": 0, "message": str(exc)}


# ----- Indikator (dihitung memakai pandas, diekspos sebagai list) -----

def _series(src) -> pd.Series:
    return pd.Series(src, dtype="float64")


def _to_list(s: pd.Series) -> list:
    return [None if pd.isna(x) else float(x) for x in s]


def sma(src, n):
    return _to_list(_series(src).rolling(int(n)).mean())


def ema(src, n):
    return _to_list(_series(src).ewm(span=int(n), adjust=False).mean())


def stdev(src, n):
    return _to_list(_series(src).rolling(int(n)).std(ddof=0))


def rsi(src, n):
    s = _series(src)
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / int(n), adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / int(n), adjust=False).mean()
    rs = gain / loss
    out = 100 - (100 / (1 + rs))
    # loss == 0 (tren naik murni) -> RSI 100; gain & loss 0 -> netral 50.
    out = out.where(loss != 0, other=100.0)
    out = out.where(~((loss == 0) & (gain == 0)), other=50.0)
    return _to_list(out.fillna(50.0))


def atr(high, low, close, n):
    h, l, c = _series(high), _series(low), _series(close)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return _to_list(tr.ewm(alpha=1 / int(n), adjust=False).mean())


def highest(src, n):
    return _to_list(_series(src).rolling(int(n)).max())


def lowest(src, n):
    return _to_list(_series(src).rolling(int(n)).min())


def bbands(src, n, mult):
    mid = _series(src).rolling(int(n)).mean()
    sd = _series(src).rolling(int(n)).std(ddof=0)
    upper = mid + float(mult) * sd
    lower = mid - float(mult) * sd
    return _to_list(upper), _to_list(mid), _to_list(lower)


def macd(src, fast=12, slow=26, signal=9):
    s = _series(src)
    macd_line = s.ewm(span=int(fast), adjust=False).mean() - s.ewm(span=int(slow), adjust=False).mean()
    signal_line = macd_line.ewm(span=int(signal), adjust=False).mean()
    hist = macd_line - signal_line
    return _to_list(macd_line), _to_list(signal_line), _to_list(hist)


def wma(src, n):
    """Weighted Moving Average (bobot linier 1..n; bar terbaru bobot terbesar)."""
    n = int(n)

    def _w(x):  # x: numpy array panjang n (raw=True)
        total = 0.0
        wsum = 0.0
        for i, val in enumerate(x, start=1):
            total += val * i
            wsum += i
        return total / wsum if wsum else float("nan")

    return _to_list(_series(src).rolling(n).apply(_w, raw=True))


def stochastic(high, low, close, k=14, d=3, smooth=3):
    """Stochastic Oscillator. Kembalikan (%K, %D) dalam rentang 0..100."""
    h, l, c = _series(high), _series(low), _series(close)
    ll = l.rolling(int(k)).min()
    hh = h.rolling(int(k)).max()
    rng = hh - ll
    raw_k = 100.0 * (c - ll) / rng
    raw_k = raw_k.where(rng != 0, other=50.0)  # datar -> netral (hindari bagi 0)
    k_line = raw_k.rolling(int(smooth)).mean()
    d_line = k_line.rolling(int(d)).mean()
    return _to_list(k_line), _to_list(d_line)


def adx(high, low, close, n=14):
    """Average Directional Index (Wilder). Kembalikan (ADX, +DI, -DI)."""
    h, l, c = _series(high), _series(low), _series(close)
    up = h.diff()
    down = -l.diff()
    plus_dm = ((up > down) & (up > 0)).astype("float64") * up
    minus_dm = ((down > up) & (down > 0)).astype("float64") * down
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    alpha = 1.0 / int(n)
    atr_ = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_)
    minus_di = 100.0 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr_)
    di_sum = plus_di + minus_di
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    dx = dx.where(di_sum != 0, other=0.0)
    adx_line = dx.ewm(alpha=alpha, adjust=False).mean()
    return _to_list(adx_line), _to_list(plus_di), _to_list(minus_di)


def cci(high, low, close, n=20):
    """Commodity Channel Index (periode n)."""
    tp = (_series(high) + _series(low) + _series(close)) / 3.0
    ma = tp.rolling(int(n)).mean()

    def _mad(x):  # mean absolute deviation (raw numpy array)
        m = x.mean()
        return (abs(x - m)).mean()

    md = tp.rolling(int(n)).apply(_mad, raw=True)
    out = (tp - ma) / (0.015 * md)
    out = out.where(md != 0, other=0.0)
    return _to_list(out)


def vwap(high, low, close, volume, n=14):
    """Volume Weighted Average Price bergulir (window n bar)."""
    tp = (_series(high) + _series(low) + _series(close)) / 3.0
    v = _series(volume)
    pv = (tp * v).rolling(int(n)).sum()
    vv = v.rolling(int(n)).sum()
    out = pv / vv
    out = out.where(vv != 0)  # volume 0 -> NaN -> None
    return _to_list(out)


def williams_r(high, low, close, n=14):
    """Williams %R (rentang -100..0). -100 = jenuh jual, 0 = jenuh beli."""
    h, l, c = _series(high), _series(low), _series(close)
    hh = h.rolling(int(n)).max()
    ll = l.rolling(int(n)).min()
    rng = hh - ll
    out = -100.0 * (hh - c) / rng
    out = out.where(rng != 0, other=-50.0)  # datar -> netral
    return _to_list(out)


def obv(close, volume):
    """On-Balance Volume (kumulatif). Naik saat close naik, turun saat close turun."""
    c = _series(close)
    v = _series(volume)
    direction = c.diff().apply(lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))
    return _to_list((direction * v).fillna(0.0).cumsum())


def mfi(high, low, close, volume, n=14):
    """Money Flow Index (0..100) — RSI berbobot volume."""
    tp = (_series(high) + _series(low) + _series(close)) / 3.0
    v = _series(volume)
    rmf = tp * v
    delta = tp.diff()
    pos_flow = rmf.where(delta > 0, other=0.0).rolling(int(n)).sum()
    neg_flow = rmf.where(delta < 0, other=0.0).rolling(int(n)).sum()
    ratio = pos_flow / neg_flow
    out = 100.0 - (100.0 / (1.0 + ratio))
    out = out.where(neg_flow != 0, other=100.0)          # tak ada arus turun -> 100
    out = out.where(~((neg_flow == 0) & (pos_flow == 0)), other=50.0)
    return _to_list(out)


def donchian(high, low, n=20):
    """Donchian Channel. Kembalikan (upper, mid, lower) periode n."""
    upper = _series(high).rolling(int(n)).max()
    lower = _series(low).rolling(int(n)).min()
    mid = (upper + lower) / 2.0
    return _to_list(upper), _to_list(mid), _to_list(lower)


def parabolic_sar(high, low, step=0.02, max_step=0.2):
    """Parabolic SAR (Wilder). Kembalikan list nilai SAR per bar."""
    h = [float(x) for x in high]
    l = [float(x) for x in low]
    n = len(h)
    if n < 2:
        return [None] * n
    sar = [None] * n
    step = float(step)
    max_step = float(max_step)
    # Inisialisasi: tentukan arah dari dua bar pertama.
    uptrend = h[1] >= h[0]
    af = step
    ep = h[1] if uptrend else l[1]  # extreme point
    sar[1] = l[0] if uptrend else h[0]
    for i in range(2, n):
        prev = sar[i - 1]
        cur = prev + af * (ep - prev)
        if uptrend:
            # SAR tak boleh di atas dua low terakhir.
            cur = min(cur, l[i - 1], l[i - 2])
            if l[i] < cur:  # balik arah -> turun
                uptrend = False
                cur = ep            # SAR = EP lama
                ep = l[i]
                af = step
            else:
                if h[i] > ep:
                    ep = h[i]
                    af = min(af + step, max_step)
        else:
            cur = max(cur, h[i - 1], h[i - 2])
            if h[i] > cur:  # balik arah -> naik
                uptrend = True
                cur = ep
                ep = h[i]
                af = step
            else:
                if l[i] < ep:
                    ep = l[i]
                    af = min(af + step, max_step)
        sar[i] = cur
    return [None if v is None else round(float(v), 8) for v in sar]


def supertrend(high, low, close, n=10, mult=3.0):
    """SuperTrend. Kembalikan (garis_supertrend, arah) — arah +1 naik, -1 turun."""
    h, l, c = _series(high), _series(low), _series(close)
    hl2 = (h + l) / 2.0
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1.0 / int(n), adjust=False).mean()
    m = float(mult)
    upper = (hl2 + m * atr_).tolist()
    lower = (hl2 - m * atr_).tolist()
    close_v = c.tolist()
    size = len(close_v)
    st = [None] * size
    direction = [None] * size
    final_upper = [None] * size
    final_lower = [None] * size
    for i in range(size):
        if i == 0 or pd.isna(atr_.iloc[i]):
            final_upper[i] = upper[i]
            final_lower[i] = lower[i]
            direction[i] = 1
            st[i] = lower[i]
            continue
        fu = upper[i] if (upper[i] < final_upper[i - 1] or close_v[i - 1] > final_upper[i - 1]) else final_upper[i - 1]
        fl = lower[i] if (lower[i] > final_lower[i - 1] or close_v[i - 1] < final_lower[i - 1]) else final_lower[i - 1]
        final_upper[i] = fu
        final_lower[i] = fl
        if close_v[i] > fu:
            direction[i] = 1
        elif close_v[i] < fl:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
        st[i] = fl if direction[i] == 1 else fu
    st_out = [None if (v is None or pd.isna(v)) else round(float(v), 8) for v in st]
    return st_out, direction


def ichimoku(high, low, close, tenkan=9, kijun=26, senkou=52):
    """Ichimoku Kinko Hyo. Kembalikan (tenkan, kijun, senkou_a, senkou_b, chikou).

    Catatan: senkou_a/b DIGESER MAJU `kijun` bar; chikou DIGESER MUNDUR `kijun` bar
    (konvensi standar). Nilai di ujung yang belum tersedia menjadi None.
    """
    h, l, c = _series(high), _series(low), _series(close)

    def _mid(period):
        return (h.rolling(int(period)).max() + l.rolling(int(period)).min()) / 2.0

    tenkan_line = _mid(tenkan)
    kijun_line = _mid(kijun)
    senkou_a = ((tenkan_line + kijun_line) / 2.0).shift(int(kijun))
    senkou_b = _mid(senkou).shift(int(kijun))
    chikou = c.shift(-int(kijun))
    return (_to_list(tenkan_line), _to_list(kijun_line),
            _to_list(senkou_a), _to_list(senkou_b), _to_list(chikou))


def pivot_points(high, low, close):
    """Pivot Points klasik dari bar TERAKHIR. Kembalikan dict {pivot,r1,s1,r2,s2,r3,s3}."""
    if len(high) == 0:
        return {}
    hi, lo, cl = float(high[-1]), float(low[-1]), float(close[-1])
    p = (hi + lo + cl) / 3.0
    r1 = 2 * p - lo
    s1 = 2 * p - hi
    r2 = p + (hi - lo)
    s2 = p - (hi - lo)
    r3 = hi + 2 * (p - lo)
    s3 = lo - 2 * (hi - p)
    return {"pivot": p, "r1": r1, "s1": s1, "r2": r2, "s2": s2, "r3": r3, "s3": s3}


def crossover(a, b) -> bool:
    """True bila deret a memotong ke ATAS deret b pada bar terakhir."""
    if len(a) < 2 or len(b) < 2:
        return False
    a0, a1, b0, b1 = a[-2], a[-1], b[-2], b[-1]
    if None in (a0, a1, b0, b1):
        return False
    return a0 <= b0 and a1 > b1


def crossunder(a, b) -> bool:
    """True bila deret a memotong ke BAWAH deret b pada bar terakhir."""
    if len(a) < 2 or len(b) < 2:
        return False
    a0, a1, b0, b1 = a[-2], a[-1], b[-2], b[-1]
    if None in (a0, a1, b0, b1):
        return False
    return a0 >= b0 and a1 < b1


class ScriptContext:
    """API yang tersedia untuk skrip lewat objek `ctx`."""

    def __init__(self, df: pd.DataFrame, params: dict, position=None,
                 positions=None, account=None, symbol="", tick=None, spec=None,
                 settings: dict = None, pending_orders=None, rates_provider=None,
                 state=None):
        self.open = [float(x) for x in df["open"]] if "open" in df else []
        self.high = [float(x) for x in df["high"]] if "high" in df else []
        self.low = [float(x) for x in df["low"]] if "low" in df else []
        self.close = [float(x) for x in df["close"]] if "close" in df else []
        vol_col = "tick_volume" if "tick_volume" in df else ("volume" if "volume" in df else None)
        self.volume = [float(x) for x in df[vol_col]] if vol_col else []
        self.params = ParamDict(params or {})
        st = dict(settings or {})
        if "volume" in st and "lot" not in st:
            st["lot"] = st["volume"]
        elif "lot" in st and "volume" not in st:
            st["volume"] = st["lot"]
        self.settings = ParamDict(st)
        # Konteks runtime (diisi engine tiap bar).
        self.symbol = symbol or str(st.get("symbol", ""))
        self.positions = list(positions or [])
        # Posisi tunggal (pertama) untuk kemudahan; None bila tak ada posisi terbuka.
        self.position = position if position is not None else (self.positions[0] if self.positions else None)
        self.pending_orders = list(pending_orders or [])
        self._rates_provider = rates_provider
        self.state = state if isinstance(state, dict) else {}
        acc = account or {}
        self.balance = float(acc.get("balance", 0.0))
        self.equity = float(acc.get("equity", 0.0))
        self.margin = float(acc.get("margin", 0.0))
        self.free_margin = float(acc.get("free_margin", 0.0))
        margin_lvl = acc.get("margin_level")
        if margin_lvl is not None and float(margin_lvl) > 0:
            self.margin_level = float(margin_lvl)
        elif self.margin > 0:
            self.margin_level = round((self.equity / self.margin) * 100.0, 2)
        else:
            self.margin_level = 99999.0
        self.floating_profit = float(acc.get("profit", 0.0))
        self.unrealized_profit = self.floating_profit

        # Harga & spread live + spesifikasi simbol (dari tick + spec).
        tk = tick or {}
        sp = spec or {}
        self.bid = float(tk.get("bid", 0.0))
        self.ask = float(tk.get("ask", 0.0))
        self.point = float(sp.get("point", 0.0))
        self.digits = int(sp.get("digits", 5))
        self.volume_min = float(sp.get("volume_min", 0.01) or 0.01)
        self.volume_max = float(sp.get("volume_max", 100.0) or 100.0)
        self.volume_step = float(sp.get("volume_step", 0.01) or 0.01)
        self.stop_level = int(sp.get("stop_level", 0) or 0)
        self.freeze_level = int(sp.get("freeze_level", 0) or 0)
        self.contract_size = float(sp.get("contract_size", 0.0) or 0.0)
        self.spread = round((self.ask - self.bid) / self.point) if self.point > 0 else 0

        # Waktu bar terakhir (broker) & waktu sekarang (UTC) + pintasan sesi.
        self.time = None
        try:
            idx = df.index[-1]
            if hasattr(idx, "to_pydatetime"):
                self.time = idx.to_pydatetime()
        except Exception:  # noqa: BLE001
            self.time = None
        self.now = datetime.now(timezone.utc)
        _base = self.time or self.now
        self.hour = _base.hour
        self.minute = _base.minute
        self.weekday = _base.weekday()  # 0=Senin .. 6=Minggu

    def log(self, msg):
        logger.info("[script] %s", msg)

    def rates(self, timeframe: str, count: int = 200) -> dict:
        """Ambil OHLCV multi-timeframe (mis. 'H1', 'M15') sebagai dict list."""
        tf = str(timeframe or "").strip().upper()
        if not tf or not callable(self._rates_provider):
            return {}
        try:
            df_tf = self._rates_provider(tf, int(count))
        except Exception:  # noqa: BLE001
            return {}
        if df_tf is None:
            return {}
        if isinstance(df_tf, dict):
            return df_tf
        if getattr(df_tf, "empty", True):
            return {}
        vol_col = "tick_volume" if "tick_volume" in df_tf else ("volume" if "volume" in df_tf else None)
        return {
            "open": [float(x) for x in df_tf["open"]] if "open" in df_tf else [],
            "high": [float(x) for x in df_tf["high"]] if "high" in df_tf else [],
            "low": [float(x) for x in df_tf["low"]] if "low" in df_tf else [],
            "close": [float(x) for x in df_tf["close"]] if "close" in df_tf else [],
            "volume": [float(x) for x in df_tf[vol_col]] if vol_col else [],
        }

    # Indikator (delegasi ke fungsi modul).
    def sma(self, src, n): return sma(src, n)
    def ema(self, src, n): return ema(src, n)
    def rsi(self, src, n): return rsi(src, n)
    def stdev(self, src, n): return stdev(src, n)
    def atr(self, n, high=None, low=None, close=None):
        h = self.high if high is None else high
        l = self.low if low is None else low
        c = self.close if close is None else close
        return atr(h, l, c, n)
    def highest(self, src, n): return highest(src, n)
    def lowest(self, src, n): return lowest(src, n)
    def bbands(self, src, n, mult): return bbands(src, n, mult)
    def macd(self, src, fast=12, slow=26, signal=9): return macd(src, fast, slow, signal)
    def wma(self, src, n): return wma(src, n)
    def stochastic(self, k=14, d=3, smooth=3): return stochastic(self.high, self.low, self.close, k, d, smooth)
    def adx(self, n=14, high=None, low=None, close=None):
        h = self.high if high is None else high
        l = self.low if low is None else low
        c = self.close if close is None else close
        return adx(h, l, c, n)
    def cci(self, n=20): return cci(self.high, self.low, self.close, n)
    def vwap(self, n=14): return vwap(self.high, self.low, self.close, self.volume, n)
    def williams_r(self, n=14): return williams_r(self.high, self.low, self.close, n)
    def obv(self): return obv(self.close, self.volume)
    def mfi(self, n=14): return mfi(self.high, self.low, self.close, self.volume, n)
    def donchian(self, n=20): return donchian(self.high, self.low, n)
    def parabolic_sar(self, step=0.02, max_step=0.2): return parabolic_sar(self.high, self.low, step, max_step)
    def supertrend(self, n=10, mult=3.0): return supertrend(self.high, self.low, self.close, n, mult)
    def ichimoku(self, tenkan=9, kijun=26, senkou=52): return ichimoku(self.high, self.low, self.close, tenkan, kijun, senkou)
    def pivot_points(self): return pivot_points(self.high, self.low, self.close)
    def crossover(self, a, b): return crossover(a, b)
    def crossunder(self, a, b): return crossunder(a, b)

    # ----- Perintah order gaya cBot (dikontrol dari dalam skrip) -----
    # Kembalikan objek "intent" yang dibaca engine untuk menempatkan order
    # dengan SL/TP/volume/risk sesuai keinginan skrip. Contoh:
    #     return ctx.buy(volume=0.1, sl_points=300, tp_points=600)
    #     return ctx.sell(sl=1.2345, tp=1.2000)   # SL/TP sebagai HARGA absolut
    #     return ctx.buy()                        # otomatis baca SETTINGS skrip!

    def _order(self, action, volume=None, sl_points=None, tp_points=None,
               sl=None, tp=None, risk=None, comment=None):
        intent = {"action": action}
        # Fallback ke settings skrip bila tidak dispesifikasikan di panggilan
        if volume is None:
            volume = self.settings.get("volume", self.settings.get("lot"))
        if sl_points is None and sl is None:
            sl_points = self.settings.get("sl_points", self.settings.get("sl"))
        if tp_points is None and tp is None:
            tp_points = self.settings.get("tp_points", self.settings.get("tp"))
        if risk is None:
            risk = self.settings.get("risk_per_trade", self.settings.get("risk"))
        if comment is None:
            comment = self.settings.get("comment")

        if volume is not None:
            intent["volume"] = float(volume)
        if sl_points is not None:
            intent["sl_points"] = int(sl_points)
        if tp_points is not None:
            intent["tp_points"] = int(tp_points)
        if sl is not None:
            intent["sl"] = float(sl)
        if tp is not None:
            intent["tp"] = float(tp)
        if risk is not None:
            intent["risk"] = float(risk)
        if comment is not None:
            intent["comment"] = str(comment)
        return intent

    def buy(self, volume=None, sl_points=None, tp_points=None, sl=None, tp=None, risk=None, comment=None):
        return self._order(SIGNAL_BUY, volume, sl_points, tp_points, sl, tp, risk, comment)

    def sell(self, volume=None, sl_points=None, tp_points=None, sl=None, tp=None, risk=None, comment=None):
        return self._order(SIGNAL_SELL, volume, sl_points, tp_points, sl, tp, risk, comment)

    @staticmethod
    def _ticket_of(target, fallback):
        """Ambil nomor tiket dari dict posisi / int / posisi aktif (fallback)."""
        if isinstance(target, dict):
            t = target.get("ticket") or target.get("position_id") or target.get("id")
        elif target is not None:
            t = target
        elif fallback:
            t = fallback.get("ticket") or fallback.get("position_id") or fallback.get("id")
        else:
            t = None
        try:
            return int(t) if t is not None else None
        except (TypeError, ValueError):
            return None

    def close_position(self, position=None):
        """Tutup satu posisi (default: posisi aktif simbol ini).

        Catatan: dinamai close_position (bukan close) agar tidak bentrok dengan
        deret harga ctx.close.
        """
        ticket = self._ticket_of(position, self.position)
        return {"action": "CLOSE", "ticket": ticket} if ticket is not None else None

    def close_all(self):
        """Tutup semua posisi simbol ini."""
        return {"action": "CLOSE_ALL"}

    def close_side(self, side: str):
        """Tutup semua posisi satu sisi ('BUY' atau 'SELL') pada simbol ini."""
        s = str(side or "").strip().upper()
        if s not in ("BUY", "SELL"):
            return None
        return {"action": "CLOSE_SIDE", "side": s}

    def _pending(self, order_type: str, price: float, volume=None, sl: float = 0.0,
                 tp: float = 0.0, comment=None):
        if price is None or float(price) <= 0.0:
            return None
        if volume is None:
            volume = self.settings.get("volume", self.settings.get("lot"))
        if volume is None or float(volume) <= 0.0:
            return None
        if comment is None:
            comment = self.settings.get("comment")
        cmd = {
            "action": "PENDING",
            "order_type": order_type,
            "price": float(price),
            "volume": float(volume),
            "sl": float(sl or 0.0),
            "tp": float(tp or 0.0),
        }
        if comment is not None:
            cmd["comment"] = str(comment)
        return cmd

    def buy_stop(self, price: float, volume=None, sl: float = 0.0, tp: float = 0.0, comment=None):
        return self._pending("buy_stop", price, volume, sl, tp, comment)

    def sell_stop(self, price: float, volume=None, sl: float = 0.0, tp: float = 0.0, comment=None):
        return self._pending("sell_stop", price, volume, sl, tp, comment)

    def buy_limit(self, price: float, volume=None, sl: float = 0.0, tp: float = 0.0, comment=None):
        return self._pending("buy_limit", price, volume, sl, tp, comment)

    def sell_limit(self, price: float, volume=None, sl: float = 0.0, tp: float = 0.0, comment=None):
        return self._pending("sell_limit", price, volume, sl, tp, comment)

    def delete_order(self, order):
        """Hapus pending order (dict order atau int ticket)."""
        ticket = self._ticket_of(order, None)
        return {"action": "DELETE_ORDER", "ticket": ticket} if ticket is not None else None

    def modify_order(self, order, price: float, sl=None, tp=None):
        """Ubah harga/SL/TP pending order (dict order atau int ticket)."""
        ticket = self._ticket_of(order, None)
        if ticket is None or price is None or float(price) <= 0.0:
            return None
        cmd = {"action": "MODIFY_ORDER", "ticket": ticket, "price": float(price)}
        if sl is not None:
            cmd["sl"] = float(sl)
        if tp is not None:
            cmd["tp"] = float(tp)
        return cmd

    def modify(self, position=None, sl=None, tp=None):
        """Ubah SL/TP satu posisi (harga absolut)."""
        ticket = self._ticket_of(position, self.position)
        if ticket is None:
            return None
        cmd = {"action": "MODIFY", "ticket": ticket}
        if sl is not None:
            cmd["sl"] = float(sl)
        if tp is not None:
            cmd["tp"] = float(tp)
        return cmd


class ScriptStrategy(Strategy):
    """Strategi berbasis skrip pengguna (Programmer Mode)."""

    name = "custom_script"
    display_name = "Custom Script (Programmer)"
    PARAMS = []

    def __init__(self, source: str, params: dict = None):
        self.source = source or ""
        self._ns = compile_script(self.source)  # raise ScriptError bila gagal
        self.script_settings = extract_script_settings(self._ns)
        # PARAMS instance dari skrip (bisa dict atau list skema).
        raw_params = self._ns.get("PARAMS", None)
        self.PARAMS = {} if raw_params is None else raw_params
        self.params = ParamDict(self._resolve(params or {}))
        self._on_bar = self._ns["on_bar"]
        # Konteks runtime yang diisi engine tiap bar (posisi, pending, akun, tick, dll).
        self._state = {}
        self.state_key = str(self.script_settings.get("name") or self._ns.get("NAME") or "custom_script").strip() or "custom_script"
        self._runtime = {
            "symbol": "", "positions": [], "pending_orders": [],
            "account": {}, "tick": {}, "spec": {}, "rates_provider": None,
        }

    def bind_runtime(self, symbol: str = "", positions=None, account=None,
                     tick=None, spec=None, pending_orders=None,
                     rates_provider=None, state=None) -> None:
        """Terima konteks runtime dari engine sebelum generate_signal dipanggil.

        Mengisi ctx.position/positions/pending_orders/balance/equity/bid/ask/spread/waktu/state
        agar skrip bisa cek posisi, pending order, multi-timeframe, dan sizing berbasis saldo.
        """
        if isinstance(state, dict):
            self._state = state
        self._runtime = {
            "symbol": symbol or "",
            "positions": list(positions or []),
            "pending_orders": list(pending_orders or []),
            "account": dict(account or {}),
            "tick": dict(tick or {}),
            "spec": dict(spec or {}),
            "rates_provider": rates_provider,
        }

    def _resolve(self, params: dict) -> dict:
        resolved = {}
        if isinstance(self.PARAMS, dict):
            resolved.update(self.PARAMS)
            if isinstance(params, dict):
                resolved.update(params)
        elif isinstance(self.PARAMS, list):
            for spec in self.PARAMS:
                if not isinstance(spec, dict):
                    continue
                key = spec.get("key")
                if not key:
                    continue
                raw = params.get(key, spec.get("default")) if params else spec.get("default")
                t = spec.get("type", "float")
                try:
                    resolved[key] = int(raw) if t == "int" else (float(raw) if t == "float" else raw)
                except (TypeError, ValueError):
                    resolved[key] = spec.get("default")
            if isinstance(params, dict):
                for k, v in params.items():
                    if k not in resolved:
                        resolved[k] = v
        elif isinstance(params, dict):
            resolved.update(params)
        return resolved

    def generate_signal(self, df: pd.DataFrame):
        """Hasilkan sinyal/perintah dari skrip.

        Skrip boleh mengembalikan:
            - "BUY" / "SELL" / None (sederhana), atau
            - dict perintah dari ctx.buy()/sell()/close()/close_all()/modify(), atau
            - list dari beberapa dict perintah (dieksekusi berurutan oleh engine).
        """
        try:
            rt = self._runtime
            ctx = ScriptContext(df, self.params, positions=rt.get("positions"),
                                account=rt.get("account"), symbol=rt.get("symbol", ""),
                                tick=rt.get("tick"), spec=rt.get("spec"),
                                settings=self.script_settings,
                                pending_orders=rt.get("pending_orders"),
                                rates_provider=rt.get("rates_provider"),
                                state=self._state)
            sig = _run_guarded(self._on_bar, ctx)
        except ScriptTimeout as exc:
            logger.error("Skrip strategi dihentikan: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 - fail-safe
            logger.error("Skrip strategi error saat on_bar: %s", exc)
            return None

        if sig is None:
            return None
        if isinstance(sig, str):
            return sig if sig in (SIGNAL_BUY, SIGNAL_SELL) else None
        if isinstance(sig, dict):
            return sig if sig.get("action") in _VALID_ACTIONS else None
        if isinstance(sig, (list, tuple)):
            cmds = [c for c in sig if isinstance(c, dict) and c.get("action") in _VALID_ACTIONS]
            return cmds or None
        return None


# ----- Penyimpanan skrip (folder strategies/scripts) -----

import os
import re
import sys

def _get_scripts_dir() -> str:
    env_dir = os.environ.get("XAVIQ_SCRIPTS_DIR")
    if env_dir:
        return env_dir
    local_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
    if os.path.exists(local_dir):
        return local_dir
    candidates = [
        os.path.join(os.getcwd(), "scripts"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
    ]
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "scripts"))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return local_dir

SCRIPTS_DIR = _get_scripts_dir()
_EXCLUDE = {"__init__", "README"}


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip())
    return (base or "skrip")


def list_scripts() -> list:
    """Daftar nama skrip tersimpan (tanpa ekstensi)."""
    sdir = _get_scripts_dir()
    try:
        files = os.listdir(sdir)
    except OSError:
        return []
    out = []
    for f in sorted(files):
        if f.endswith(".py"):
            stem = f[:-3]
            if stem not in _EXCLUDE and not stem.startswith("_"):
                out.append(stem)
    return out


def load_script(name: str) -> str:
    """Muat isi skrip berdasarkan nama. Kembalikan "" bila gagal."""
    sdir = _get_scripts_dir()
    path = os.path.join(sdir, _safe_name(name) + ".py")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def save_script(name: str, source: str) -> str:
    """Simpan skrip ke folder. Kembalikan path, atau "" bila gagal."""
    sdir = _get_scripts_dir()
    os.makedirs(sdir, exist_ok=True)
    path = os.path.join(sdir, _safe_name(name) + ".py")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source or "")
        return path
    except OSError as exc:
        logger.error("Gagal menyimpan skrip: %s", exc)
        return ""


# Template default untuk skrip baru di editor (Full Script Settings Mode).
DEFAULT_TEMPLATE = '''"""Strategi kustom saya (Mode Programmer Full Settings).

Anda dapat mengatur SEMUA konfigurasi trading langsung dari skrip ini
tanpa harus mengisi kolom form satu per satu di UI!
"""

# Pengaturan trading lengkap (opsional, otomatis diselaraskan ke bot)
SETTINGS = {
    "symbol": "EURUSDm",          # Simbol aktif (mis. EURUSDm untuk Exness)
    "timeframe": "M5",            # M1, M5, M15, M30, H1, H4, D1
    "volume": 0.01,               # Ukuran lot per order (atau 'lot')
    "sl_points": 300,             # Stop Loss dalam points
    "tp_points": 600,             # Take Profit dalam points
    "max_positions": 1,           # Maksimal posisi terbuka bersamaan
    "trailing_stop_points": 200,  # Trailing stop points (0 = nonaktif)
    "trailing_step_points": 50,
    "break_even_points": 150,     # Break-even stop points (0 = nonaktif)
    "break_even_offset_points": 10,
    "max_spread_points": 35,      # Batas maksimal spread points (0 = nonaktif)
}

# Parameter strategi (bisa berupa list skema di bawah, atau dict sederhana {"fast": 12, "slow": 26})
PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 26, "min": 2},
]


def on_bar(ctx):
    # Akses parameter via ctx.params.fast atau ctx.params["fast"]
    fast = ctx.ema(ctx.close, ctx.params.fast)
    slow = ctx.ema(ctx.close, ctx.params.slow)

    # ctx.buy() & ctx.sell() otomatis memakai volume, sl, dan tp dari SETTINGS
    if ctx.crossover(fast, slow):
        return ctx.buy()
    if ctx.crossunder(fast, slow):
        return ctx.sell()

    return None
'''
