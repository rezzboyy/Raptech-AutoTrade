"""Pengambilan data pasar: candle historis dan harga terkini."""

import MetaTrader5 as mt5
import pandas as pd

from src.logger import get_logger

logger = get_logger(__name__)


def get_rates(symbol: str, timeframe: int, count: int = 200) -> pd.DataFrame:
    """Ambil sejumlah candle terakhir sebagai DataFrame.

    Args:
        symbol: nama simbol.
        timeframe: konstanta timeframe MT5.
        count: jumlah candle yang diambil.

    Returns:
        DataFrame dengan kolom OHLCV dan index waktu.
        DataFrame kosong bila gagal.
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning("Tidak ada data candle untuk %s, error=%s", symbol, mt5.last_error())
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    return df


def get_tick(symbol: str):
    """Ambil tick (harga bid/ask) terkini untuk simbol.

    Returns:
        Objek tick MT5 atau None bila gagal.
    """
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.warning("Gagal mengambil tick untuk %s, error=%s", symbol, mt5.last_error())
    return tick
