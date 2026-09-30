"""Aturan trading backend-agnostik: pemetaan sinyal, gerbang risiko, kalkulasi lot.

Fungsi di sini bekerja pada antarmuka TradingBackend + dict ternormalisasi, sehingga
identik untuk backend native maupun MCP. Dipakai oleh engine saat mengeksekusi order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.logger import get_logger
from strategies.base import SIGNAL_BUY, SIGNAL_SELL

logger = get_logger("mt5bot")


def map_signal_to_side(signal: str) -> Optional[str]:
    """Petakan sinyal strategi ke arah order MCP: BUY->'buy', SELL->'sell'."""
    if signal == SIGNAL_BUY:
        return "buy"
    if signal == SIGNAL_SELL:
        return "sell"
    return None


def clamp_comment(comment: str, limit: int = 31) -> str:
    """Batasi komentar order maksimum `limit` karakter."""
    return str(comment or "")[:limit]


def count_open_positions(backend, symbol: str, magic: int) -> int:
    """Hitung posisi terbuka milik bot (symbol + magic) via backend."""
    positions = backend.positions(symbol) or []
    if magic:
        return sum(1 for p in positions if int(p.get("magic", 0)) == magic)
    return len(positions)


def can_open_new_position(backend, symbol: str, magic: int, max_positions: int) -> bool:
    """True bila jumlah posisi terbuka masih di bawah batas."""
    return count_open_positions(backend, symbol, magic) < max_positions


def calc_lot_from_spec(spec: dict, balance: float, risk_percent: float,
                       sl_price: float, entry_price: float) -> float:
    """Hitung lot dari spesifikasi simbol ternormalisasi + risiko.

    Mengembalikan 0.0 bila data tidak memadai (mis. tick_value 0 saat terminal
    belum tersambung broker).
    """
    if not spec or balance <= 0:
        return 0.0
    sl_distance = abs(entry_price - sl_price)
    if sl_distance <= 0:
        return 0.0
    tick_size = spec.get("tick_size") or spec.get("point") or 0.0
    tick_value = spec.get("tick_value") or 0.0
    if tick_size <= 0 or tick_value <= 0:
        return 0.0

    loss_per_lot = (sl_distance / tick_size) * tick_value
    if loss_per_lot <= 0:
        return 0.0

    raw_lot = (balance * risk_percent) / loss_per_lot
    step = spec.get("volume_step") or 0.01
    vmin = spec.get("volume_min") or 0.01
    vmax = spec.get("volume_max") or raw_lot
    lot = round(raw_lot / step) * step
    lot = max(vmin, min(lot, vmax))
    return round(lot, 2)


def apply_break_even(backend, position: dict, spec: dict,
                     trigger_points: int, offset_points: int = 10) -> bool:
    """Pindahkan SL ke entry (+offset) bila profit mencapai trigger. Backend-agnostik."""
    if trigger_points <= 0 or not spec:
        return False
    point = spec.get("point", 0.0)
    digits = spec.get("digits", 5)
    if point <= 0:
        return False
    tick = backend.get_tick(position["symbol"])
    if not tick:
        return False
    entry = position["price_open"]
    cur_sl = position.get("sl", 0.0)

    if position["type"] == "BUY":
        profit_pts = (tick["bid"] - entry) / point
        target_sl = round(entry + offset_points * point, digits)
        if profit_pts >= trigger_points and (cur_sl == 0 or cur_sl < target_sl):
            logger.info("Break-Even BUY posisi %s -> SL %.5f (profit %.1f pts).",
                        position["ticket"], target_sl, profit_pts)
            return backend.modify_sl_tp(position["ticket"], position["symbol"], sl=target_sl)
    else:  # SELL
        profit_pts = (entry - tick["ask"]) / point
        target_sl = round(entry - offset_points * point, digits)
        if profit_pts >= trigger_points and (cur_sl == 0 or cur_sl > target_sl):
            logger.info("Break-Even SELL posisi %s -> SL %.5f (profit %.1f pts).",
                        position["ticket"], target_sl, profit_pts)
            return backend.modify_sl_tp(position["ticket"], position["symbol"], sl=target_sl)
    return False


def apply_trailing_stop(backend, position: dict, spec: dict,
                        trailing_points: int, step_points: int = 50) -> bool:
    """Geser SL mengikuti harga menguntungkan. Backend-agnostik."""
    if trailing_points <= 0 or not spec:
        return False
    point = spec.get("point", 0.0)
    digits = spec.get("digits", 5)
    if point <= 0:
        return False
    tick = backend.get_tick(position["symbol"])
    if not tick:
        return False
    entry = position["price_open"]
    cur_sl = position.get("sl", 0.0)
    min_dist = max(spec.get("stop_level", 0) or 0, 10) * point

    if position["type"] == "BUY":
        price = tick["bid"]
        ideal = round(price - trailing_points * point, digits)
        if ideal > entry and (cur_sl == 0 or (ideal - cur_sl) >= step_points * point):
            if (price - ideal) >= min_dist:
                logger.info("Trailing BUY posisi %s -> SL %.5f (harga %.5f).",
                            position["ticket"], ideal, price)
                return backend.modify_sl_tp(position["ticket"], position["symbol"], sl=ideal)
    else:  # SELL
        price = tick["ask"]
        ideal = round(price + trailing_points * point, digits)
        if ideal < entry and (cur_sl == 0 or (cur_sl - ideal) >= step_points * point):
            if (ideal - price) >= min_dist:
                logger.info("Trailing SELL posisi %s -> SL %.5f (harga %.5f).",
                            position["ticket"], ideal, price)
                return backend.modify_sl_tp(position["ticket"], position["symbol"], sl=ideal)
    return False


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def daily_trade_count(backend, magic: int) -> int:
    """Jumlah trade tertutup hari ini (via history_deals backend)."""
    deals = backend.history_deals(_today_start(), datetime.now(timezone.utc)) or []
    if magic:
        return sum(1 for d in deals if int(d.get("magic", 0)) == magic)
    return len(deals)


def daily_drawdown_breached(backend, max_drawdown: float, magic: int) -> tuple[bool, float]:
    """Cek apakah rugi harian (closed + floating) melewati batas fraksi."""
    if max_drawdown <= 0:
        return False, 0.0
    deals = backend.history_deals(_today_start(), datetime.now(timezone.utc)) or []
    closed = sum(d.get("net_profit", 0.0) for d in deals
                 if not magic or int(d.get("magic", 0)) == magic)
    positions = backend.positions() or []
    floating = sum(p.get("profit", 0.0) for p in positions
                   if not magic or int(p.get("magic", 0)) == magic)
    total = closed + floating

    acc = backend.account_info() or {}
    balance = float(acc.get("balance", 0.0))
    if balance <= 0:
        return False, 0.0
    start_balance = balance - closed
    if start_balance <= 0:
        start_balance = balance
    if total < 0:
        dd = abs(total) / start_balance
        return (dd >= max_drawdown), dd
    return False, 0.0


def passes_risk_gates(backend, settings, symbol: str) -> tuple[bool, str]:
    """Evaluasi seluruh gerbang risiko sebelum membuka order.

    Kembalikan (True, "") bila boleh; (False, alasan) bila salah satu terlanggar.
    """
    # 1) Batas posisi terbuka.
    if not can_open_new_position(backend, symbol, settings.magic_number, settings.max_open_positions):
        return False, f"Batas posisi ({settings.max_open_positions}) untuk {symbol} tercapai."

    # 2) Batas trade harian.
    if settings.max_daily_trades > 0:
        if daily_trade_count(backend, settings.magic_number) >= settings.max_daily_trades:
            return False, f"Batas trade harian ({settings.max_daily_trades}) tercapai."

    # 3) Drawdown harian.
    if settings.daily_drawdown_limit > 0:
        breached, dd = daily_drawdown_breached(backend, settings.daily_drawdown_limit, settings.magic_number)
        if breached:
            return False, f"Batas drawdown harian terlampaui ({dd*100:.2f}%)."

    # 4) Filter spread: tolak bila spread melonjak melebihi batas.
    max_spread = getattr(settings, "max_spread_points", 0)
    if max_spread and max_spread > 0:
        sp = backend.spread_points(symbol)
        # Adaptasi otomatis bila simbol Crypto bernilai tinggi (mis. BTCUSDm) tapi batas spread diset di skala Forex (< 1000)
        eff_max = max(max_spread, 3000) if ("BTC" in symbol.upper() and max_spread < 1000) else max_spread
        if sp is not None and sp > eff_max:
            return False, f"Spread {sp:.0f} pts melebihi batas {eff_max} pts."

    # 5) Safety guard: pause setelah loss beruntun.
    max_streak = getattr(settings, "max_consecutive_losses", 0)
    if max_streak and max_streak > 0:
        streak = consecutive_losses(backend, settings.magic_number)
        if streak >= max_streak:
            return False, f"Safety guard: {streak} loss beruntun (batas {max_streak}), trading dijeda."

    return True, ""


def virtual_exit_hit(pos_type: str, sl: float, tp: float, bid: float, ask: float):
    """Tentukan apakah level SL/TP virtual tercapai. Kembalikan 'SL'|'TP'|None.

    BUY ditutup pada harga bid; SELL ditutup pada harga ask. Nilai sl/tp = 0
    berarti tidak diset (dilewati).
    """
    if pos_type == "BUY":
        if sl and bid <= sl:
            return "SL"
        if tp and bid >= tp:
            return "TP"
    else:  # SELL
        if sl and ask >= sl:
            return "SL"
        if tp and ask <= tp:
            return "TP"
    return None


def compute_percent_sl_tp(side: str, entry: float, sl_percent: float,
                          tp_percent: float, digits: int = 5):
    """Hitung SL/TP berbasis persen harga. side: 'buy'/'sell' atau BUY/SELL."""
    slp = sl_percent / 100.0
    tpp = tp_percent / 100.0
    is_buy = str(side).upper() in ("BUY", "0", "ORDER_TYPE_BUY", SIGNAL_BUY)
    if is_buy:
        return round(entry * (1 - slp), digits), round(entry * (1 + tpp), digits)
    return round(entry * (1 + slp), digits), round(entry * (1 - tpp), digits)


def current_exposure(backend, magic: int) -> float:
    """Total volume (lot) seluruh posisi terbuka milik bot."""
    positions = backend.positions() or []
    return sum(p.get("volume", 0.0) for p in positions
               if not magic or int(p.get("magic", 0)) == magic)


def consecutive_losses(backend, magic: int) -> int:
    """Hitung jumlah loss beruntun terakhir dari histori (urut waktu menurun)."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    deals = backend.history_deals(now - timedelta(days=30), now) or []
    if magic:
        deals = [d for d in deals if int(d.get("magic", 0)) == magic]
    deals.sort(key=lambda d: d.get("time", 0), reverse=True)
    streak = 0
    for d in deals:
        if d.get("net_profit", 0.0) < 0:
            streak += 1
        elif d.get("net_profit", 0.0) > 0:
            break  # profit memutus rangkaian loss
        # net 0 (breakeven) diabaikan, lanjut
    return streak


def open_order_if_allowed(backend, settings, symbol: str, side: str, volume: float,
                          sl: float = 0.0, tp: float = 0.0, comment: str = "mt5bot") -> dict:
    """Buka order hanya bila seluruh gerbang risiko lolos (Property 7).

    Bila gerbang terlanggar, TIDAK memanggil backend.send_market_order.
    """
    allowed, reason = passes_risk_gates(backend, settings, symbol)
    if not allowed:
        logger.info("Order %s %s dilewati oleh gerbang risiko: %s", side, symbol, reason)
        return {"ok": False, "ticket": None, "message": reason}

    # Batas total eksposur (jumlah lot seluruh posisi).
    max_exp = getattr(settings, "max_exposure_lots", 0.0)
    if max_exp and max_exp > 0:
        if current_exposure(backend, settings.magic_number) + float(volume) > max_exp + 1e-9:
            reason = f"Total eksposur akan melebihi batas {max_exp} lot."
            logger.info("Order %s %s dilewati: %s", side, symbol, reason)
            return {"ok": False, "ticket": None, "message": reason}

    return backend.send_market_order(
        symbol, side, volume, sl=sl, tp=tp,
        magic=settings.magic_number, comment=clamp_comment(comment),
    )
