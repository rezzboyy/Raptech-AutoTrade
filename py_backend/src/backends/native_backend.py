"""Backend trading berbasis library `MetaTrader5` (perilaku lama).

Membungkus logika `mt5.*` yang sudah ada di balik antarmuka TradingBackend dan
menormalkan objek `mt5` menjadi dict sesuai kontrak (lihat backends/base.py).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.logger import get_logger

logger = get_logger("mt5bot")


class NativeBackend:
    """Implementasi TradingBackend memakai library MetaTrader5."""

    def __init__(self):
        # Import ditunda agar modul tetap bisa di-import di lingkungan tanpa MT5.
        from src.connection import MT5Connection
        self._conn = MT5Connection()
        self.connected = False

    # ----- Koneksi -----

    def connect(self) -> bool:
        ok = self._conn.connect()
        self.connected = ok
        return ok

    def disconnect(self) -> None:
        self._conn.disconnect()
        self.connected = False

    def account_info(self) -> Optional[dict]:
        import MetaTrader5 as mt5
        info = mt5.account_info()
        if info is None:
            return None
        term = mt5.terminal_info()
        from src.backends.base import classify_account_type
        server = getattr(info, "server", "")
        # trade_mode MT5: 0=demo, 1=contest, 2=real
        tm = {0: "demo", 1: "contest", 2: "real"}.get(getattr(info, "trade_mode", 2), "real")
        return {
            "login": getattr(info, "login", 0),
            "balance": round(info.balance, 2),
            "equity": round(info.equity, 2),
            "margin": round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "profit": round(info.profit, 2),
            "currency": info.currency,
            "server": server,
            "account_type": classify_account_type(tm, server),
            "trade_allowed": bool(getattr(term, "trade_allowed", True)) if term else True,
            "server_connected": bool(getattr(term, "connected", True)) if term else True,
        }

    # ----- Simbol -----

    def list_symbols(self, limit: int = 60) -> list:
        import MetaTrader5 as mt5
        from config.settings import settings
        symbols = mt5.symbols_get()
        if symbols is None:
            return [settings.symbol] if settings.symbol else []
        visible = [s.name for s in symbols if getattr(s, "visible", False)]
        names = visible if visible else [s.name for s in symbols[:limit]]
        if settings.symbol and settings.symbol not in names:
            names.insert(0, settings.symbol)
        return names[:limit]

    def symbol_spec(self, symbol: str) -> Optional[dict]:
        import MetaTrader5 as mt5
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "symbol": symbol,
            "digits": int(getattr(info, "digits", 5)),
            "point": float(getattr(info, "point", 0.0) or 0.0),
            "volume_min": float(getattr(info, "volume_min", 0.01) or 0.01),
            "volume_max": float(getattr(info, "volume_max", 0.0) or 0.0),
            "volume_step": float(getattr(info, "volume_step", 0.01) or 0.01),
            "tick_value": float(getattr(info, "trade_tick_value", 0.0) or 0.0),
            "tick_size": float(getattr(info, "trade_tick_size", 0.0) or 0.0),
            "stop_level": int(getattr(info, "trade_stops_level", 0) or 0),
            "freeze_level": int(getattr(info, "trade_freeze_level", 0) or 0),
            "contract_size": float(getattr(info, "trade_contract_size", 0.0) or 0.0),
        }

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Cari nama simbol yang valid di broker via MT5, menyesuaikan suffix akun Exness (m/c/pro/raw)."""
        import MetaTrader5 as mt5
        from src.backends.base import candidate_symbol_variations, resolve_symbol_name

        symbol = (symbol or "").strip()
        if not symbol:
            return None
        info = mt5.symbol_info(symbol)
        if info is not None:
            return symbol
        all_syms = mt5.symbols_get()
        if all_syms:
            avail = [s.name for s in all_syms]
            resolved = resolve_symbol_name(symbol, avail)
            if resolved:
                return resolved
        for cand in candidate_symbol_variations(symbol):
            if mt5.symbol_info(cand) is not None:
                return cand
        return None

    def ensure_symbol(self, symbol: str) -> bool:
        """Pastikan simbol aktif di Market Watch; adaptasi otomatis bila ada beda suffix Exness."""
        symbol = (symbol or "").strip()
        if not symbol:
            return False
        if self._conn.ensure_symbol(symbol):
            return True
        resolved = self.resolve_symbol(symbol)
        if resolved and resolved != symbol:
            return self._conn.ensure_symbol(resolved)
        return False

    # ----- Data pasar -----

    def get_rates(self, symbol: str, timeframe_str: str, count: int = 200):
        from src.market_data import get_rates
        from config.settings import settings, _TIMEFRAME_MAP
        tf = _TIMEFRAME_MAP.get(str(timeframe_str or "").upper(), settings.timeframe)
        return get_rates(symbol, tf, count=count)

    def get_tick(self, symbol: str) -> Optional[dict]:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return {"bid": float(tick.bid), "ask": float(tick.ask), "time": int(getattr(tick, "time", 0))}

    def spread_points(self, symbol: str) -> Optional[float]:
        import MetaTrader5 as mt5
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        # MT5 menyediakan spread terkini dalam points.
        sp = getattr(info, "spread", None)
        if sp is not None:
            return float(sp)
        tick = mt5.symbol_info_tick(symbol)
        point = getattr(info, "point", 0.0) or 0.0
        if tick and point > 0:
            return (float(tick.ask) - float(tick.bid)) / point
        return None

    # ----- Posisi & histori -----

    def positions(self, symbol: Optional[str] = None) -> list:
        import MetaTrader5 as mt5
        poss = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if poss is None:
            return []
        out = []
        for p in poss:
            out.append({
                "ticket": int(p.ticket),
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": round(p.volume, 2),
                "price_open": round(p.price_open, 5),
                "price_current": round(p.price_current, 5),
                "sl": round(p.sl, 5),
                "tp": round(p.tp, 5),
                "profit": round(p.profit, 2),
                "magic": int(getattr(p, "magic", 0)),
            })
        return out

    def history_deals(self, dt_from: datetime, dt_to: datetime) -> list:
        import MetaTrader5 as mt5
        deals = mt5.history_deals_get(dt_from, dt_to)
        if not deals:
            return []
        out = []
        for d in deals:
            if getattr(d, "entry", None) not in (1, 2, 3):  # hanya deal penutup
                continue
            profit = float(getattr(d, "profit", 0.0))
            comm = float(getattr(d, "commission", 0.0))
            swap = float(getattr(d, "swap", 0.0))
            fee = float(getattr(d, "fee", 0.0))
            out.append({
                "ticket": int(d.ticket),
                "time": int(d.time),
                "symbol": getattr(d, "symbol", ""),
                "magic": int(getattr(d, "magic", 0)),
                "net_profit": profit + comm + swap + fee,
                "profit": profit,
            })
        return out

    # ----- Trading -----

    def send_market_order(self, symbol: str, side: str, volume: float,
                          sl: float = 0.0, tp: float = 0.0, magic: int = 0,
                          comment: str = "mt5bot") -> dict:
        import MetaTrader5 as mt5
        from src.order_manager import open_position
        order_type = mt5.ORDER_TYPE_BUY if str(side).lower() == "buy" else mt5.ORDER_TYPE_SELL
        result = open_position(symbol, order_type, volume, sl, tp, magic, comment=comment[:31])
        if result is None:
            return {"ok": False, "ticket": None, "message": "order_send mengembalikan None"}
        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        return {
            "ok": ok,
            "ticket": int(getattr(result, "order", 0)) or None,
            "message": "" if ok else f"retcode={result.retcode}",
        }

    def close_position(self, ticket: int, symbol: str) -> dict:
        import MetaTrader5 as mt5
        from src.order_manager import close_position
        poss = mt5.positions_get(ticket=ticket)
        if not poss:
            return {"ok": False, "ticket": ticket, "message": "posisi tidak ditemukan"}
        result = close_position(poss[0])
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        return {"ok": ok, "ticket": ticket, "message": "" if ok else "gagal menutup"}

    def modify_sl_tp(self, ticket: int, symbol: str,
                     sl: Optional[float] = None, tp: Optional[float] = None) -> bool:
        import MetaTrader5 as mt5
        poss = mt5.positions_get(ticket=ticket)
        if not poss:
            return False
        p = poss[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": p.ticket,
            "symbol": p.symbol,
            "sl": float(sl if sl is not None else p.sl),
            "tp": float(tp if tp is not None else p.tp),
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def send_pending_order(self, symbol: str, order_type: str, volume: float,
                           price: float, sl: float = 0.0, tp: float = 0.0,
                           magic: int = 0, comment: str = "mt5bot") -> dict:
        import MetaTrader5 as mt5
        from src.order_manager import get_filling_type
        type_map = {
            "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
            "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
            "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
            "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
        }
        ot = str(order_type).lower()
        if ot not in type_map:
            return {"ok": False, "ticket": None, "message": f"Tipe pending tidak valid: {order_type!r}"}
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": type_map[ot],
            "price": float(price),
            "sl": float(sl),
            "tp": float(tp),
            "magic": magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(symbol),
        }
        result = mt5.order_send(request)
        if result is None:
            return {"ok": False, "ticket": None, "message": "order_send None"}
        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        return {"ok": ok, "ticket": int(getattr(result, "order", 0)) or None,
                "message": "" if ok else f"retcode={result.retcode}"}

    def modify_pending_order(self, ticket: int, price: float,
                             sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
        import MetaTrader5 as mt5
        orders = mt5.orders_get(ticket=int(ticket))
        if not orders:
            return {"ok": False, "ticket": ticket, "message": "pending order tidak ditemukan"}
        o = orders[0]
        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": int(o.ticket),
            "symbol": o.symbol,
            "price": float(price),
            "sl": float(sl if sl is not None else o.sl),
            "tp": float(tp if tp is not None else o.tp),
            "type_time": getattr(o, "type_time", mt5.ORDER_TIME_GTC),
        }
        result = mt5.order_send(request)
        if result is None:
            return {"ok": False, "ticket": ticket, "message": "order_send None"}
        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        return {"ok": ok, "ticket": ticket, "message": "" if ok else f"retcode={result.retcode}"}

    def delete_pending_order(self, ticket: int) -> dict:
        import MetaTrader5 as mt5
        request = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(ticket)}
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        return {"ok": ok, "ticket": ticket, "message": "" if ok else "gagal hapus pending"}

    def pending_orders(self, symbol=None) -> list:
        import MetaTrader5 as mt5
        orders = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
        if not orders:
            return []
        type_name = {
            mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
            mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
            mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
            mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
        }
        out = []
        for o in orders:
            out.append({
                "ticket": int(o.ticket),
                "symbol": o.symbol,
                "type": type_name.get(o.type, str(o.type)),
                "volume": round(getattr(o, "volume_current", 0.0), 2),
                "price": round(getattr(o, "price_open", 0.0), 5),
                "sl": round(o.sl, 5),
                "tp": round(o.tp, 5),
                "magic": int(getattr(o, "magic", 0)),
            })
        return out
