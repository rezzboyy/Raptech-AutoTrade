"""Entry point bot trading MT5.

Alur loop utama:
    1. Ambil data candle terbaru.
    2. Minta sinyal dari strategi.
    3. Jika ada sinyal dan slot posisi masih tersedia:
         - hitung SL/TP dan ukuran lot,
         - kirim order.
    4. Ulangi setiap `loop_interval` detik.

Jalankan: python main.py
Hentikan: Ctrl+C
"""

import time

import MetaTrader5 as mt5

from config.settings import settings
from src.connection import MT5Connection
from src.logger import get_logger
from src.market_data import get_rates, get_tick
from src.order_manager import open_position
from src.risk_manager import calculate_lot, can_open_new_position
from src import strategy_loader
from strategies.base import SIGNAL_BUY, SIGNAL_SELL

logger = get_logger("mt5bot")

# Jarak SL/TP dalam "points" (contoh sederhana; sesuaikan dengan strategi Anda).
SL_POINTS = 300
TP_POINTS = 600


def compute_sl_tp(symbol: str, signal: str, entry_price: float):
    """Hitung harga SL dan TP berbasis jarak points tetap.

    Returns:
        Tuple (sl, tp).
    """
    info = mt5.symbol_info(symbol)
    point = info.point
    if signal == SIGNAL_BUY:
        sl = entry_price - SL_POINTS * point
        tp = entry_price + TP_POINTS * point
    else:
        sl = entry_price + SL_POINTS * point
        tp = entry_price - TP_POINTS * point
    return round(sl, info.digits), round(tp, info.digits)


def handle_signal(signal: str) -> None:
    """Proses sinyal menjadi order jika kondisi risiko terpenuhi."""
    symbol = settings.symbol

    if not can_open_new_position(symbol, settings.magic_number, settings.max_open_positions):
        logger.info("Batas posisi tercapai, sinyal %s dilewati.", signal)
        return

    tick = get_tick(symbol)
    if tick is None:
        return

    if signal == SIGNAL_BUY:
        order_type = mt5.ORDER_TYPE_BUY
        entry_price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        entry_price = tick.bid

    sl, tp = compute_sl_tp(symbol, signal, entry_price)
    lot = calculate_lot(symbol, settings.risk_per_trade, sl, entry_price)
    if lot <= 0:
        logger.warning("Ukuran lot tidak valid, order dibatalkan.")
        return

    open_position(symbol, order_type, lot, sl, tp, settings.magic_number)


def run() -> None:
    """Jalankan loop utama bot."""
    from src import config_store
    config_store.load()

    conn = MT5Connection()
    if not conn.connect():
        logger.error("Gagal terhubung ke MT5. Bot berhenti.")
        return

    if not conn.ensure_symbol(settings.symbol):
        conn.disconnect()
        return

    strategy = strategy_loader.create(settings.strategy_name, settings.strategy_params)
    logger.info(
        "Bot berjalan | Simbol=%s | TF=%s | Strategi=%s | Risiko/trade=%.1f%%",
        settings.symbol, settings.timeframe_str, strategy.display_name,
        settings.risk_per_trade * 100,
    )

    try:
        while True:
            df = get_rates(settings.symbol, settings.timeframe, count=200)
            if not df.empty:
                signal = strategy.generate_signal(df)
                if signal in (SIGNAL_BUY, SIGNAL_SELL):
                    handle_signal(signal)
            time.sleep(settings.loop_interval)
    except KeyboardInterrupt:
        logger.info("Dihentikan oleh pengguna (Ctrl+C).")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    run()
