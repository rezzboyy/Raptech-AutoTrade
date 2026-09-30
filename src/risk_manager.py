"""Manajemen risiko: perhitungan lot, SL/TP dinamis, Trailing Stop, Break-Even, dan batas proteksi harian."""

from datetime import datetime
import MetaTrader5 as mt5

from src.logger import get_logger
from src.order_manager import modify_position_sl

logger = get_logger(__name__)


def calculate_lot(symbol: str, risk_percent: float, sl_price: float, entry_price: float) -> float:
    """Hitung ukuran lot berdasarkan risiko per trade dan jarak stop loss.

    Rumus: risiko_uang = balance * risk_percent
           lot = risiko_uang / (jarak_sl_dalam_tick * nilai_per_tick)

    Args:
        symbol: nama simbol.
        risk_percent: fraksi balance yang dirisikokan (mis. 0.01 = 1%).
        sl_price: harga stop loss.
        entry_price: harga entry.

    Returns:
        Ukuran lot yang sudah dibulatkan ke step broker, dibatasi min/max.
        0.0 bila data tidak valid.
    """
    account = mt5.account_info()
    info = mt5.symbol_info(symbol)
    if account is None or info is None:
        logger.error("Tidak bisa menghitung lot: account/symbol info kosong.")
        return 0.0

    risk_money = account.balance * risk_percent
    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= 0:
        logger.error("Jarak SL tidak valid (%.5f).", sl_distance)
        return 0.0

    tick_size = info.trade_tick_size or info.point
    tick_value = info.trade_tick_value
    if tick_size <= 0 or tick_value <= 0:
        logger.error("tick_size/tick_value tidak valid untuk %s.", symbol)
        return 0.0

    ticks = sl_distance / tick_size
    loss_per_lot = ticks * tick_value
    if loss_per_lot <= 0:
        return 0.0

    raw_lot = risk_money / loss_per_lot

    # Bulatkan ke step volume broker dan batasi min/max.
    step = info.volume_step or 0.01
    lot = round(raw_lot / step) * step
    lot = max(info.volume_min, min(lot, info.volume_max))

    logger.info(
        "Lot dihitung: %.2f (risiko %.2f, jarak SL %.5f)", lot, risk_money, sl_distance
    )
    return round(lot, 2)


def can_open_new_position(symbol: str, magic: int, max_positions: int) -> bool:
    """Cek apakah masih boleh membuka posisi baru untuk simbol/magic ini.

    Args:
        symbol: nama simbol.
        magic: magic number bot.
        max_positions: jumlah maksimum posisi terbuka yang diizinkan.

    Returns:
        True jika jumlah posisi masih di bawah batas.
    """
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return True
    count = sum(1 for p in positions if p.magic == magic)
    return count < max_positions


# ----- Trailing Stop & Break-Even -----

def apply_break_even(position, trigger_points: int, offset_points: int = 10) -> bool:
    """Pindahkan Stop Loss ke harga entry (+ offset) bila profit sudah mencapai trigger.

    Args:
        position: objek posisi dari mt5.positions_get().
        trigger_points: jarak keuntungan dalam points untuk memicu BE.
        offset_points: jarak tambahan points di atas entry (mengunci sedikit profit/komisi).

    Returns:
        True jika SL berhasil dimodifikasi ke BE, selain itu False.
    """
    if trigger_points <= 0:
        return False

    symbol = position.symbol
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None or info.point <= 0:
        return False

    point = info.point

    if position.type == mt5.POSITION_TYPE_BUY:
        profit_pts = (tick.bid - position.price_open) / point
        target_sl = round(position.price_open + (offset_points * point), info.digits)

        # Picu jika profit cukup dan SL belum aman di atas harga entry
        if profit_pts >= trigger_points and (position.sl == 0 or position.sl < target_sl):
            logger.info(
                "Memicu Break-Even BUY posisi %s (Profit: +%.1f pts, Entry: %.5f, SL baru: %.5f)",
                position.ticket, profit_pts, position.price_open, target_sl,
            )
            return modify_position_sl(position, target_sl)

    elif position.type == mt5.POSITION_TYPE_SELL:
        profit_pts = (position.price_open - tick.ask) / point
        target_sl = round(position.price_open - (offset_points * point), info.digits)

        # Picu jika profit cukup dan SL belum aman di bawah harga entry
        if profit_pts >= trigger_points and (position.sl == 0 or position.sl > target_sl):
            logger.info(
                "Memicu Break-Even SELL posisi %s (Profit: +%.1f pts, Entry: %.5f, SL baru: %.5f)",
                position.ticket, profit_pts, position.price_open, target_sl,
            )
            return modify_position_sl(position, target_sl)

    return False


def apply_trailing_stop(position, trailing_points: int, step_points: int = 50) -> bool:
    """Geser Stop Loss mengikuti pergerakan harga yang menguntungkan.

    Args:
        position: objek posisi dari mt5.positions_get().
        trailing_points: jarak SL dari harga saat ini (points).
        step_points: jarak minimum pergeseran sebelum update SL dikirim (points).

    Returns:
        True jika SL berhasil digeser, selain itu False.
    """
    if trailing_points <= 0:
        return False

    symbol = position.symbol
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None or info.point <= 0:
        return False

    point = info.point
    min_stop_distance = max(getattr(info, "stop_level", 0) or 0, 10) * point

    if position.type == mt5.POSITION_TYPE_BUY:
        current_price = tick.bid
        ideal_sl = round(current_price - (trailing_points * point), info.digits)

        # Hanya geser ke atas
        if ideal_sl > position.price_open:
            if position.sl == 0 or (ideal_sl - position.sl) >= (step_points * point):
                if (current_price - ideal_sl) >= min_stop_distance:
                    logger.info(
                        "Menerapkan Trailing Stop BUY posisi %s: SL baru %.5f (Harga: %.5f)",
                        position.ticket, ideal_sl, current_price,
                    )
                    return modify_position_sl(position, ideal_sl)

    elif position.type == mt5.POSITION_TYPE_SELL:
        current_price = tick.ask
        ideal_sl = round(current_price + (trailing_points * point), info.digits)

        # Hanya geser ke bawah
        if ideal_sl < position.price_open:
            if position.sl == 0 or (position.sl - ideal_sl) >= (step_points * point):
                if (ideal_sl - current_price) >= min_stop_distance:
                    logger.info(
                        "Menerapkan Trailing Stop SELL posisi %s: SL baru %.5f (Harga: %.5f)",
                        position.ticket, ideal_sl, current_price,
                    )
                    return modify_position_sl(position, ideal_sl)

    return False


# ----- Proteksi Risiko Harian (Daily Drawdown & Max Daily Trades) -----

def check_daily_drawdown(max_drawdown_percent: float, magic: int = 0) -> tuple[bool, float]:
    """Cek apakah akumulasi kerugian hari ini (closed + floating) melebihi batas.

    Args:
        max_drawdown_percent: fraksi batas drawdown (mis. 0.05 = 5%).
        magic: magic number bot (0 untuk cek seluruh akun).

    Returns:
        tuple (is_breached, current_drawdown_fraction).
    """
    if max_drawdown_percent <= 0:
        return False, 0.0

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, datetime.now())

    closed_pl = 0.0
    if deals:
        for d in deals:
            if getattr(d, "entry", None) in (1, 2, 3):
                if magic == 0 or getattr(d, "magic", 0) == magic:
                    profit = float(getattr(d, "profit", 0.0))
                    comm = float(getattr(d, "commission", 0.0))
                    swap = float(getattr(d, "swap", 0.0))
                    fee = float(getattr(d, "fee", 0.0))
                    closed_pl += (profit + comm + swap + fee)

    floating_pl = 0.0
    positions = mt5.positions_get()
    if positions:
        for p in positions:
            if magic == 0 or p.magic == magic:
                floating_pl += float(p.profit)

    total_today_pl = closed_pl + floating_pl

    account = mt5.account_info()
    if account is None or account.balance <= 0:
        return False, 0.0

    # Estimasi saldo awal hari ini
    start_day_balance = account.balance - closed_pl
    if start_day_balance <= 0:
        start_day_balance = account.balance

    if total_today_pl < 0:
        drawdown_pct = abs(total_today_pl) / start_day_balance
        if drawdown_pct >= max_drawdown_percent:
            logger.warning(
                "PERINGATAN: Batas Daily Drawdown tercapai: %.2f%% >= %.2f%% (Rugi hari ini: %.2f)",
                drawdown_pct * 100, max_drawdown_percent * 100, abs(total_today_pl),
            )
            return True, drawdown_pct
        return False, drawdown_pct

    return False, 0.0


def get_daily_trade_count(magic: int = 0) -> int:
    """Hitung jumlah trade yang ditutup hari ini."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, datetime.now())
    if not deals:
        return 0

    count = 0
    for d in deals:
        if getattr(d, "entry", None) in (1, 2, 3):
            if magic == 0 or getattr(d, "magic", 0) == magic:
                count += 1
    return count


def can_trade_today(max_daily_trades: int, magic: int = 0) -> bool:
    """Cek apakah jumlah trade hari ini belum melebihi batas maksimum.

    Args:
        max_daily_trades: batas maksimum trade per hari (0 = tanpa batas).
        magic: magic number bot.

    Returns:
        True jika masih boleh membuka order hari ini.
    """
    if max_daily_trades <= 0:
        return True
    count = get_daily_trade_count(magic)
    if count >= max_daily_trades:
        logger.info("Batas trade harian (%d trade) telah tercapai hari ini.", max_daily_trades)
        return False
    return True
