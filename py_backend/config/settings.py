"""Konfigurasi terpusat untuk bot trading MT5.

Semua nilai dibaca dari environment variables (file .env).
Gunakan .env.example sebagai template.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path=None, override=False):
        """Fallback mandiri jika python-dotenv belum terpasang di runtime Python."""
        try:
            target = None
            if dotenv_path is not None:
                p = Path(dotenv_path)
                if p.is_file():
                    target = p
            else:
                candidates = [
                    Path.cwd() / ".env",
                    Path(__file__).resolve().parent.parent / ".env",
                    Path(__file__).resolve().parent.parent.parent / ".env",
                ]
                for cand in candidates:
                    if cand.is_file():
                        target = cand
                        break
            if not target or not target.is_file():
                return False

            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
                            v = v[1:-1]
                        if override or k not in os.environ:
                            os.environ[k] = v
            return True
        except Exception:
            return False

try:
    import MetaTrader5 as mt5
except ImportError:  # memungkinkan import config tanpa MT5 terpasang (mis. saat test)
    mt5 = None


def _load_env() -> None:
    """Muat .env dari CWD dan dari folder executable (mode frozen/EXE)."""
    # 1) Pencarian default (CWD dan parent).
    load_dotenv()
    # 2) Folder di samping EXE saat dibundel PyInstaller.
    if getattr(sys, "frozen", False):
        exe_env = Path(sys.executable).resolve().parent / ".env"
        if exe_env.exists():
            load_dotenv(exe_env, override=False)


_load_env()


# Pemetaan string timeframe ke konstanta MT5.
_TIMEFRAME_MAP = {
    "M1": getattr(mt5, "TIMEFRAME_M1", 1),
    "M5": getattr(mt5, "TIMEFRAME_M5", 5),
    "M15": getattr(mt5, "TIMEFRAME_M15", 15),
    "M30": getattr(mt5, "TIMEFRAME_M30", 30),
    "H1": getattr(mt5, "TIMEFRAME_H1", 16385),
    "H4": getattr(mt5, "TIMEFRAME_H4", 16388),
    "D1": getattr(mt5, "TIMEFRAME_D1", 16408),
}


def _get_int(key: str, default: int) -> int:
    value = os.getenv(key)
    return int(value) if value not in (None, "") else default


def _get_float(key: str, default: float) -> float:
    value = os.getenv(key)
    return float(value) if value not in (None, "") else default


@dataclass
class Settings:
    """Menampung seluruh konfigurasi bot."""

    # Kredensial akun
    login: int = _get_int("MT5_LOGIN", 0)
    password: str = os.getenv("MT5_PASSWORD", "")
    server: str = os.getenv("MT5_SERVER", "")
    path: str = os.getenv("MT5_PATH", "")

    # Backend koneksi ke MT5: "native" (library MetaTrader5) atau "mcp" (server MCP
    # bawaan terminal). Default "native" agar perilaku lama tidak berubah.
    backend: str = os.getenv("BACKEND", "native")
    mcp_endpoint: str = os.getenv("MCP_ENDPOINT", "http://127.0.0.1:22346/mcp")
    # API Key MCP TIDAK disimpan di config.json (bisa ter-commit). Sumbernya env
    # MCP_API_KEY atau berkas rahasia mcp_secret.json (masuk .gitignore).
    mcp_api_key: str = os.getenv("MCP_API_KEY", "")

    # Parameter trading (default akun Exness Standard: simbol berakhiran 'm')
    symbol: str = os.getenv("SYMBOL", "EURUSDm")
    timeframe_str: str = os.getenv("TIMEFRAME", "M5")
    magic_number: int = _get_int("MAGIC_NUMBER", 100200)

    # Manajemen risiko dasar
    risk_per_trade: float = _get_float("RISK_PER_TRADE", 0.01)
    max_open_positions: int = _get_int("MAX_OPEN_POSITIONS", 1)

    # SL / TP Dinamis
    # Mode SL/TP: "points" (jarak points) atau "percent" (persen dari harga entry).
    sl_tp_mode: str = os.getenv("SL_TP_MODE", "points")
    sl_points: int = _get_int("SL_POINTS", 300)
    tp_points: int = _get_int("TP_POINTS", 600)
    sl_percent: float = _get_float("SL_PERCENT", 0.5)   # 0.5 = 0.5% dari harga
    tp_percent: float = _get_float("TP_PERCENT", 1.0)   # 1.0 = 1.0% dari harga
    # Virtual/Hidden SL/TP: SL/TP tidak dikirim ke broker; dipantau & dieksekusi bot.
    virtual_sltp_enabled: bool = os.getenv("VIRTUAL_SLTP_ENABLED", "false").lower() in ("true", "1", "yes")

    # Trailing Stop Loss
    trailing_stop_enabled: bool = os.getenv("TRAILING_STOP_ENABLED", "false").lower() in ("true", "1", "yes")
    trailing_stop_points: int = _get_int("TRAILING_STOP_POINTS", 200)
    trailing_step_points: int = _get_int("TRAILING_STEP_POINTS", 50)

    # Break-Even Stop
    break_even_enabled: bool = os.getenv("BREAK_EVEN_ENABLED", "false").lower() in ("true", "1", "yes")
    break_even_trigger_points: int = _get_int("BREAK_EVEN_TRIGGER_POINTS", 150)
    break_even_offset_points: int = _get_int("BREAK_EVEN_OFFSET_POINTS", 10)

    # Proteksi Harian
    daily_drawdown_limit: float = _get_float("DAILY_DRAWDOWN_LIMIT", 0.05)  # 0.05 = 5%, 0 = nonaktif
    max_daily_trades: int = _get_int("MAX_DAILY_TRADES", 10)  # 0 = tanpa batas

    # --- Proteksi Lanjutan ---
    # Filter spread: tolak entry bila spread (points) > batas. 0 = nonaktif.
    max_spread_points: int = _get_int("MAX_SPREAD_POINTS", 0)
    # Batas total eksposur (jumlah lot seluruh posisi bot). 0 = tanpa batas.
    max_exposure_lots: float = _get_float("MAX_EXPOSURE_LOTS", 0.0)
    # Equity cut-loss: tutup semua posisi + stop bot bila drawdown ekuitas dari
    # balance >= ambang (fraksi). 0 = nonaktif.
    equity_stop_loss: float = _get_float("EQUITY_STOP_LOSS", 0.0)
    # Safety guard: pause auto-trading setelah N loss beruntun (0 = nonaktif).
    max_consecutive_losses: int = _get_int("MAX_CONSECUTIVE_LOSSES", 0)

    # Strategi terpilih + parameternya (parameter dinamis sesuai strategi).
    strategy_name: str = os.getenv("STRATEGY", "ma_cross")
    strategy_params: dict = field(default_factory=dict)

    # Mode Programmer: skrip strategi kustom (dipakai bila strategy_name == "custom_script").
    script_name: str = os.getenv("SCRIPT_NAME", "")
    script_source: str = ""

    # Interval loop trading (detik)
    loop_interval: int = _get_int("LOOP_INTERVAL", 15)

    @property
    def symbols_list(self) -> list:
        """Daftar simbol trading (mendukung multi-simbol koma/titik-koma)."""
        raw = self.symbol or ""
        # JANGAN paksa huruf besar: broker seperti Exness memakai suffix huruf
        # kecil (mis. 'EURUSDm'). Nama simbol dipakai apa adanya (hanya di-trim).
        items = [s.strip() for s in raw.replace(";", ",").split(",") if s.strip()]
        return items if items else ["EURUSDm"]

    @property
    def timeframe(self) -> int:
        """Konstanta timeframe MT5 dari string yang dikonfigurasi."""
        return _TIMEFRAME_MAP.get(self.timeframe_str.upper(), _TIMEFRAME_MAP["M5"])


MCP_SECRET_FILE = "mcp_secret.json"


def _load_mcp_secret(cfg: "Settings") -> None:
    """Muat endpoint/API Key MCP dari berkas rahasia bila belum diset via env.

    Berkas mcp_secret.json (masuk .gitignore) berbentuk:
        {"mcp_api_key": "...", "mcp_endpoint": "http://127.0.0.1:22346/mcp"}
    Nilai dari environment variable tetap diprioritaskan.
    """
    import json

    path = MCP_SECRET_FILE
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / MCP_SECRET_FILE).exists():
            path = str(exe_dir / MCP_SECRET_FILE)

    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    if not cfg.mcp_api_key and data.get("mcp_api_key"):
        cfg.mcp_api_key = str(data["mcp_api_key"])
    if not os.getenv("MCP_ENDPOINT") and data.get("mcp_endpoint"):
        cfg.mcp_endpoint = str(data["mcp_endpoint"])


# Instance tunggal yang dipakai di seluruh aplikasi.
settings = Settings()
_load_mcp_secret(settings)
