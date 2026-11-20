"""Verifikasi read-only backend MCP (tanpa eksekusi order).

Jalankan dari root proyek: python tools\\verify_mcp.py
Berguna untuk memastikan koneksi MCP + baca data sebelum menyalakan auto-trading.
"""

import os
import sys

# Pastikan root proyek ada di sys.path agar import config/src berhasil
# saat skrip dijalankan dari folder tools/.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.settings import settings

settings.backend = "mcp"

from src.bot_engine import BotEngine  # noqa: E402
from src.mcp_client import mask_token  # noqa: E402


def main():
    print("=" * 56)
    print("  VERIFIKASI BACKEND MCP (READ-ONLY)")
    print("=" * 56)
    print("endpoint :", settings.mcp_endpoint)
    print("api_key  :", mask_token(settings.mcp_api_key))
    if not settings.mcp_api_key:
        print(">> API Key kosong. Isi mcp_secret.json atau env MCP_API_KEY.")
        return

    eng = BotEngine()
    if not eng.connect():
        print(">> GAGAL connect. Pastikan MT5 terbuka & 'Enable internal server' aktif (Options > MCP).")
        return

    acc = eng.poll_account()
    print("\nAkun :", acc)
    print("Simbol:", eng.list_symbols(8))
    print("Posisi:", len(eng.poll_positions()))
    stats = eng.poll_stats()
    print("Statistik: total_trades=%s win_rate=%s net_profit=%s" % (
        stats["total_trades"], stats["win_rate"], stats["net_profit"]))
    chart = eng.poll_chart("EURUSDm")
    print("Chart EURUSDm: %d candle, %d overlay" % (len(chart["candles"]), len(chart["overlays"])))

    eng.disconnect()
    print("\n>> Read-only OK. Untuk auto-trading, pastikan terminal tersambung broker")
    print("   (server_connected=true) lalu jalankan bot seperti biasa.")


if __name__ == "__main__":
    main()
