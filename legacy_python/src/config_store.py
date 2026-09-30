"""Persistensi konfigurasi trading (bukan kredensial) ke config.json.

Kredensial akun tetap di .env dan TIDAK disimpan di sini.
Field di sini adalah parameter yang boleh diubah pengguna dari UI.
"""

import json
import os

from config.settings import settings
from src import strategy_loader
from src.logger import get_logger

logger = get_logger(__name__)

CONFIG_FILE = "config.json"

# Field konfigurasi yang dikelola dari UI (tanpa kredensial).
_FIELDS = (
    "symbol",
    "timeframe_str",
    "magic_number",
    "risk_per_trade",
    "max_open_positions",
    "sl_tp_mode",
    "sl_points",
    "tp_points",
    "sl_percent",
    "tp_percent",
    "virtual_sltp_enabled",
    "trailing_stop_enabled",
    "trailing_stop_points",
    "trailing_step_points",
    "break_even_enabled",
    "break_even_trigger_points",
    "break_even_offset_points",
    "daily_drawdown_limit",
    "max_daily_trades",
    "max_spread_points",
    "max_exposure_lots",
    "equity_stop_loss",
    "max_consecutive_losses",
    "strategy_name",
    "strategy_params",
    "script_name",
    "script_source",
    "loop_interval",
    "backend",
    "mcp_endpoint",
)
# CATATAN: "mcp_api_key" sengaja TIDAK dimasukkan ke _FIELDS agar tidak tersimpan
# ke config.json (rawan ter-commit). Sumbernya env MCP_API_KEY atau mcp_secret.json.

# Batasan validasi sederhana.
_VALID_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def as_dict() -> dict:
    """Kembalikan konfigurasi saat ini sebagai dict siap dikirim ke UI."""
    return {field: getattr(settings, field) for field in _FIELDS}


def apply(data: dict) -> list:
    """Terapkan dict konfigurasi ke settings dengan validasi.

    Args:
        data: pasangan field->nilai.

    Returns:
        Daftar pesan error (kosong bila semua valid & diterapkan).
    """
    errors = validate(data)
    if errors:
        return errors

    for field in _FIELDS:
        if field in data and data[field] is not None:
            setattr(settings, field, _coerce(field, data[field]))
    return []


def validate(data: dict) -> list:
    """Validasi nilai konfigurasi. Kembalikan daftar pesan error."""
    errors = []

    tf = str(data.get("timeframe_str", settings.timeframe_str)).upper()
    if tf not in _VALID_TIMEFRAMES:
        errors.append(f"Timeframe tidak valid: {tf}")

    try:
        risk = float(data.get("risk_per_trade", settings.risk_per_trade))
        if not (0 < risk <= 1):
            errors.append("Risiko per trade harus antara 0 dan 1 (mis. 0.01 = 1%).")
    except (TypeError, ValueError):
        errors.append("Risiko per trade harus berupa angka.")

    # Validasi strategi + parameternya lewat loader.
    strat_name = str(data.get("strategy_name", settings.strategy_name))
    strat_params = data.get("strategy_params", settings.strategy_params) or {}
    if not isinstance(strat_params, dict):
        errors.append("Parameter strategi harus berupa objek/dict.")
    elif strat_name == "custom_script":
        # Validasi skrip kustom: harus kompilasi & punya on_bar.
        src = data.get("script_source", settings.script_source)
        try:
            from strategies.script_runtime import compile_script, ScriptError
            try:
                compile_script(src)
            except ScriptError as exc:
                errors.append(f"Skrip strategi tidak valid: {exc}")
        except Exception:  # noqa: BLE001
            pass
    else:
        errors.extend(strategy_loader.validate(strat_name, strat_params))

    try:
        if int(data.get("max_open_positions", settings.max_open_positions)) < 1:
            errors.append("Maksimum posisi harus >= 1.")
    except (TypeError, ValueError):
        errors.append("Maksimum posisi harus berupa bilangan bulat.")

    try:
        if int(data.get("loop_interval", settings.loop_interval)) < 1:
            errors.append("Interval loop harus >= 1 detik.")
    except (TypeError, ValueError):
        errors.append("Interval loop harus berupa bilangan bulat.")

    mode = str(data.get("sl_tp_mode", settings.sl_tp_mode)).lower()
    if mode not in ("points", "percent"):
        errors.append("Mode SL/TP harus 'points' atau 'percent'.")
    if mode == "percent":
        try:
            slp = float(data.get("sl_percent", settings.sl_percent))
            tpp = float(data.get("tp_percent", settings.tp_percent))
            if slp <= 0 or tpp <= 0:
                errors.append("SL% dan TP% harus > 0 saat mode percent.")
        except (TypeError, ValueError):
            errors.append("SL% dan TP% harus berupa angka.")
    else:
        try:
            sl = int(data.get("sl_points", settings.sl_points))
            tp = int(data.get("tp_points", settings.tp_points))
            if sl < 10 or tp < 10:
                errors.append("SL dan TP points minimal 10 points.")
        except (TypeError, ValueError):
            errors.append("SL dan TP points harus berupa bilangan bulat.")

    try:
        dd = float(data.get("daily_drawdown_limit", settings.daily_drawdown_limit))
        if dd < 0 or dd > 1:
            errors.append("Batas drawdown harian harus antara 0 dan 1 (0 untuk nonaktif).")
    except (TypeError, ValueError):
        errors.append("Batas drawdown harian harus berupa angka.")

    try:
        mdt = int(data.get("max_daily_trades", settings.max_daily_trades))
        if mdt < 0:
            errors.append("Batas trade harian harus >= 0 (0 untuk nonaktif).")
    except (TypeError, ValueError):
        errors.append("Batas trade harian harus berupa bilangan bulat.")

    if not str(data.get("symbol", settings.symbol)).strip():
        errors.append("Simbol tidak boleh kosong.")

    # Validasi proteksi lanjutan.
    try:
        if int(data.get("max_spread_points", settings.max_spread_points)) < 0:
            errors.append("Max spread points harus >= 0 (0 = nonaktif).")
    except (TypeError, ValueError):
        errors.append("Max spread points harus bilangan bulat.")
    try:
        if float(data.get("max_exposure_lots", settings.max_exposure_lots)) < 0:
            errors.append("Max exposure lots harus >= 0 (0 = tanpa batas).")
    except (TypeError, ValueError):
        errors.append("Max exposure lots harus berupa angka.")
    try:
        esl = float(data.get("equity_stop_loss", settings.equity_stop_loss))
        if esl < 0 or esl > 1:
            errors.append("Equity stop loss harus antara 0 dan 1 (0 = nonaktif).")
    except (TypeError, ValueError):
        errors.append("Equity stop loss harus berupa angka.")
    try:
        if int(data.get("max_consecutive_losses", settings.max_consecutive_losses)) < 0:
            errors.append("Max consecutive losses harus >= 0 (0 = nonaktif).")
    except (TypeError, ValueError):
        errors.append("Max consecutive losses harus bilangan bulat.")

    # Validasi backend koneksi.
    backend = str(data.get("backend", settings.backend)).lower()
    if backend not in ("native", "mcp"):
        errors.append("Backend harus 'native' atau 'mcp'.")
    elif backend == "mcp":
        api_key = data.get("mcp_api_key", settings.mcp_api_key)
        if not str(api_key or "").strip():
            errors.append(
                "Backend 'mcp' membutuhkan API Key. Set env MCP_API_KEY atau isi "
                "mcp_secret.json (salin dari MT5 -> Options -> tab MCP)."
            )
        if not str(data.get("mcp_endpoint", settings.mcp_endpoint) or "").strip():
            errors.append("Endpoint MCP tidak boleh kosong.")

    return errors


def _coerce(field: str, value):
    """Ubah nilai ke tipe yang benar sesuai field."""
    if field in (
        "magic_number", "max_open_positions", "loop_interval",
        "sl_points", "tp_points", "trailing_stop_points", "trailing_step_points",
        "break_even_trigger_points", "break_even_offset_points", "max_daily_trades",
        "max_spread_points", "max_consecutive_losses"
    ):
        return int(value)
    if field in ("risk_per_trade", "daily_drawdown_limit", "max_exposure_lots",
                 "equity_stop_loss", "sl_percent", "tp_percent"):
        return float(value)
    if field in ("trailing_stop_enabled", "break_even_enabled", "virtual_sltp_enabled"):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)
    if field == "sl_tp_mode":
        v = str(value).lower()
        return v if v in ("points", "percent") else "points"
    if field == "timeframe_str":
        return str(value).upper()
    if field == "strategy_params":
        return dict(value) if value else {}
    if field == "backend":
        return str(value).lower()
    return str(value)


def save() -> None:
    """Simpan konfigurasi saat ini ke config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(as_dict(), f, indent=2)
        logger.info("Konfigurasi disimpan ke %s.", CONFIG_FILE)
    except OSError as exc:
        logger.error("Gagal menyimpan konfigurasi: %s", exc)


def load() -> None:
    """Muat konfigurasi dari config.json bila ada."""
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        errors = apply(data)
        if errors:
            logger.warning("config.json memuat nilai tidak valid: %s", "; ".join(errors))
        else:
            logger.info("Konfigurasi dimuat dari %s.", CONFIG_FILE)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Gagal memuat konfigurasi: %s", exc)
