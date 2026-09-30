"""Eksekusi order: buka posisi market, tutup posisi, ambil posisi terbuka."""

import MetaTrader5 as mt5

from src.logger import get_logger

logger = get_logger(__name__)


def get_filling_type(symbol: str):
    """Pilih filling mode yang didukung simbol.

    Broker berbeda mendukung filling mode berbeda. Menghardcode IOC sering
    menyebabkan order gagal (retcode 10030) di broker yang hanya mendukung
    FOK/Return. Fungsi ini membaca kapabilitas simbol dan memilih yang cocok.

    Prioritas: IOC -> FOK -> Return.
    """
    # Nilai bitmask filling mode simbol (konstanta MQL5, TIDAK diekspos oleh
    # package MetaTrader5 Python, jadi dipakai sebagai literal):
    #   SYMBOL_FILLING_FOK = 1, SYMBOL_FILLING_IOC = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2

    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC
    mode = getattr(info, "filling_mode", 0) or 0
    if mode & SYMBOL_FILLING_IOC:
        return mt5.ORDER_FILLING_IOC
    if mode & SYMBOL_FILLING_FOK:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def open_position(
    symbol: str,
    order_type: int,
    lot: float,
    sl: float,
    tp: float,
    magic: int,
    deviation: int = 20,
    comment: str = "mt5bot",
):
    """Buka posisi market (BUY/SELL).

    Args:
        symbol: nama simbol.
        order_type: mt5.ORDER_TYPE_BUY atau mt5.ORDER_TYPE_SELL.
        lot: ukuran volume.
        sl: harga stop loss (0 untuk tanpa SL).
        tp: harga take profit (0 untuk tanpa TP).
        magic: magic number bot.
        deviation: slippage maksimum dalam points.
        comment: komentar order.

    Returns:
        Objek hasil order_send, atau None bila gagal mengambil harga.
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error("Gagal ambil harga untuk order %s.", symbol)
        return None

    price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": price,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_type(symbol),
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error("Order gagal: %s | last_error=%s", result, mt5.last_error())
    else:
        side = "BUY" if order_type == mt5.ORDER_TYPE_BUY else "SELL"
        logger.info(
            "Order %s terbuka: %.2f lot %s @ %.5f (ticket=%s)",
            side, lot, symbol, price, result.order,
        )
    return result


def close_position(position, deviation: int = 20):
    """Tutup satu posisi terbuka.

    Args:
        position: objek posisi dari mt5.positions_get().
        deviation: slippage maksimum dalam points.

    Returns:
        Objek hasil order_send atau None.
    """
    tick = mt5.symbol_info_tick(position.symbol)
    if tick is None:
        logger.error("Gagal ambil harga untuk menutup posisi %s.", position.ticket)
        return None

    if position.type == mt5.POSITION_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "position": position.ticket,
        "price": price,
        "deviation": deviation,
        "magic": position.magic,
        "comment": "close by bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": get_filling_type(position.symbol),
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error("Gagal menutup posisi %s: %s", position.ticket, result)
    else:
        logger.info("Posisi %s ditutup @ %.5f.", position.ticket, price)
    return result


def get_open_positions(symbol: str, magic: int):
    """Ambil daftar posisi terbuka milik bot (berdasarkan simbol + magic)."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    return [p for p in positions if p.magic == magic]


def modify_position_sl(position, new_sl: float) -> bool:
    """Ubah harga Stop Loss posisi yang terbuka menggunakan TRADE_ACTION_SLTP.

    Args:
        position: objek posisi dari mt5.positions_get().
        new_sl: harga SL baru yang sudah dibulatkan.

    Returns:
        True jika berhasil, False jika gagal.
    """
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "symbol": position.symbol,
        "sl": float(new_sl),
        "tp": float(position.tp),
    }
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(
            "Gagal ubah SL posisi %s ke %.5f: %s | last_error=%s",
            position.ticket, new_sl, result, mt5.last_error(),
        )
        return False
    logger.info(
        "SL posisi %s (%s) dimodifikasi: %.5f -> %.5f",
        position.ticket, position.symbol, position.sl, new_sl,
    )
    return True
