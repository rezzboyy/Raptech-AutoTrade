"""sim_backend.py — Backend Simulasi / Paper-Trading Mandiri & Fast Script Verifier.

Digunakan untuk menguji strategi Mode Programmer dan operasi trading (market order,
pending order, SL/TP, recovery grid, basket trail, spread filter) secara terisolasi
tanpa menyentuh terminal MT5 atau saldo akun Demo/Real.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from src.backends.base import PENDING_ORDER_TYPES, _TIMEFRAME_MINUTES, resolve_symbol_name


_SIM_SYMBOLS: Dict[str, Dict[str, Any]] = {
    "XAUUSDm": {
        "digits": 2,
        "point": 0.01,
        "tick_value": 1.0,
        "tick_size": 0.01,
        "contract_size": 100.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 50,
        "base_price": 2650.00,
        "bar_range": 1.80,
        "margin_per_lot": 1325.0,
    },
    "EURUSDm": {
        "digits": 5,
        "point": 0.00001,
        "tick_value": 1.0,
        "tick_size": 0.00001,
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 10,
        "base_price": 1.08500,
        "bar_range": 0.00080,
        "margin_per_lot": 1085.0,
    },
    "GBPUSDm": {
        "digits": 5,
        "point": 0.00001,
        "tick_value": 1.0,
        "tick_size": 0.00001,
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 10,
        "base_price": 1.26800,
        "bar_range": 0.00100,
        "margin_per_lot": 1268.0,
    },
    "USDJPYm": {
        "digits": 3,
        "point": 0.001,
        "tick_value": 0.65,
        "tick_size": 0.001,
        "contract_size": 100000.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 10,
        "base_price": 154.200,
        "bar_range": 0.120,
        "margin_per_lot": 1000.0,
    },
    "BTCUSDm": {
        "digits": 2,
        "point": 0.01,
        "tick_value": 0.01,
        "tick_size": 0.01,
        "contract_size": 1.0,
        "volume_min": 0.01,
        "volume_max": 20.0,
        "volume_step": 0.01,
        "stop_level": 500,
        "base_price": 92500.00,
        "bar_range": 140.00,
        "margin_per_lot": 925.0,
    },
}

VALID_SCENARIOS = ("volatile", "uptrend", "downtrend", "sideways", "spread_spike")


class SimBackend:
    """Simulator broker MT5 lengkap untuk paper-trading & verifikasi skrip."""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        symbol: str = "XAUUSDm",
        scenario: str = "volatile",
        spread_points: int = 25,
        history_bars: int = 4200,
    ):
        self.initial_balance = max(100.0, float(initial_balance or 10000.0))
        self.balance = self.initial_balance
        self.default_symbol = self._pick_symbol(symbol)
        sc = str(scenario or "volatile").strip().lower()
        self.scenario = sc if sc in VALID_SCENARIOS else "volatile"
        self.base_spread_points = max(1, int(spread_points or 25))
        self._history_bars = max(300, int(history_bars))

        self.connected = False
        self._experts_trade_allowed = True
        self._next_ticket = 900001
        self._bar_index = 0
        self._positions: List[Dict[str, Any]] = []
        self._pending: List[Dict[str, Any]] = []
        self._deals: List[Dict[str, Any]] = []
        self._bars_m1: Dict[str, List[Dict[str, Any]]] = {}

        self._t0 = datetime.now(timezone.utc) - timedelta(minutes=self._history_bars)
        self._ensure_series(self.default_symbol)

    # ----- Koneksi & Info Akun -----

    def connect(self) -> bool:
        self._ensure_series(self.default_symbol)
        self.connected = True
        return True

    def disconnect(self) -> None:
        self.connected = False

    def account_info(self) -> Optional[dict]:
        if not self.connected:
            return None
        floating = 0.0
        margin = 0.0
        for p in self._positions:
            self._refresh_position_pnl(p)
            floating += float(p["profit"])
            spec = self._spec_for(p["symbol"])
            margin += float(p["volume"]) * float(spec.get("margin_per_lot", 1000.0))

        equity = self.balance + floating
        margin_level = (equity / margin * 100.0) if margin > 0 else 99999.0
        return {
            "balance": round(self.balance, 2),
            "equity": round(equity, 2),
            "margin": round(margin, 2),
            "free_margin": round(max(0.0, equity - margin), 2),
            "profit": round(floating, 2),
            "margin_level": round(margin_level, 2),
            "currency": "USD",
            "login": 999000,
            "server": f"XAVIQ-Simulator ({self.scenario})",
            "account_type": "SIMULASI",
            "server_connected": True,
            "trade_allowed": True,
            "experts_trade_allowed": True,
            "mcp_trade_allowed": True,
            "account_trade_allowed": True,
        }

    # ----- Simbol & Data Harga -----

    @staticmethod
    def _pick_symbol(symbol: str) -> str:
        req = str(symbol or "").strip() or "XAUUSDm"
        resolved = resolve_symbol_name(req, list(_SIM_SYMBOLS.keys()))
        return resolved or req

    def list_symbols(self, limit: int = 60) -> list:
        syms = list(_SIM_SYMBOLS.keys())
        if self.default_symbol not in syms:
            syms.insert(0, self.default_symbol)
        return syms[:limit]

    def _spec_for(self, symbol: str) -> Dict[str, Any]:
        resolved = self.resolve_symbol(symbol) or symbol
        if resolved in _SIM_SYMBOLS:
            return _SIM_SYMBOLS[resolved]
        u = resolved.upper()
        if "XAU" in u or "GOLD" in u:
            return _SIM_SYMBOLS["XAUUSDm"]
        if "BTC" in u:
            return _SIM_SYMBOLS["BTCUSDm"]
        if "JPY" in u:
            return _SIM_SYMBOLS["USDJPYm"]
        return _SIM_SYMBOLS["EURUSDm"]

    def symbol_spec(self, symbol: str) -> Optional[dict]:
        resolved = self.resolve_symbol(symbol) or symbol
        s = self._spec_for(resolved)
        return {
            "symbol": resolved,
            "digits": s["digits"],
            "point": s["point"],
            "volume_min": s["volume_min"],
            "volume_max": s["volume_max"],
            "volume_step": s["volume_step"],
            "tick_value": s["tick_value"],
            "tick_size": s["tick_size"],
            "stop_level": s["stop_level"],
        }

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        return resolve_symbol_name(symbol, self.list_symbols(limit=100)) or (str(symbol or "").strip() or None)

    def ensure_symbol(self, symbol: str) -> bool:
        self._ensure_series(self.resolve_symbol(symbol) or symbol)
        return True

    def _generate_bar(self, sym: str, idx: int, prev_close: float) -> Dict[str, Any]:
        spec = self._spec_for(sym)
        step = float(spec["bar_range"])
        digits = int(spec["digits"])

        if self.scenario == "uptrend":
            delta = step * (0.28 + 0.65 * math.sin(idx * 0.23) + 0.30 * math.cos(idx * 0.61))
        elif self.scenario == "downtrend":
            delta = step * (-0.28 + 0.65 * math.sin(idx * 0.23) + 0.30 * math.cos(idx * 0.61))
        elif self.scenario == "sideways":
            delta = step * (0.85 * math.sin(idx * 0.37) - 0.35 * math.sin(idx * 0.79))
        elif self.scenario == "spread_spike":
            delta = step * (0.55 * math.sin(idx * 0.29) + 0.25 * math.cos(idx * 0.53))
        else:  # volatile
            delta = step * (1.35 * math.sin(idx * 0.17) + 0.85 * math.cos(idx * 0.43) + 0.40 * math.sin(idx * 0.91))

        o = round(prev_close, digits)
        c = round(max(spec["point"] * 100, o + delta), digits)
        wick_up = abs(step * (0.30 + 0.25 * abs(math.cos(idx * 0.73))))
        wick_dn = abs(step * (0.30 + 0.25 * abs(math.sin(idx * 0.87))))
        h = round(max(o, c) + wick_up, digits)
        l = round(max(spec["point"] * 50, min(o, c) - wick_dn), digits)
        t = int((self._t0 + timedelta(minutes=idx)).timestamp())
        return {"time": t, "open": o, "high": h, "low": l, "close": c, "tick_volume": 100 + (idx % 90)}

    def _ensure_series(self, symbol: str) -> List[Dict[str, Any]]:
        sym = self.resolve_symbol(symbol) or symbol
        if sym in self._bars_m1:
            return self._bars_m1[sym]
        spec = self._spec_for(sym)
        price = float(spec["base_price"])
        bars: List[Dict[str, Any]] = []
        for idx in range(self._history_bars):
            bar = self._generate_bar(sym, idx, price)
            bars.append(bar)
            price = bar["close"]
        self._bars_m1[sym] = bars
        return bars

    def get_rates(self, symbol: str, timeframe_str: str, count: int = 200) -> Optional[pd.DataFrame]:
        sym = self.resolve_symbol(symbol) or symbol
        m1_bars = self._ensure_series(sym)
        minutes = _TIMEFRAME_MINUTES.get(str(timeframe_str or "M5").upper(), 5)
        cnt = max(1, int(count))

        if minutes <= 1:
            sliced = m1_bars[-cnt:]
            df = pd.DataFrame(sliced)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df[["time", "open", "high", "low", "close", "tick_volume"]].reset_index(drop=True)

        needed_m1 = min(len(m1_bars), cnt * minutes + minutes)
        sub = m1_bars[-needed_m1:]
        grouped: List[Dict[str, Any]] = []
        bucket_sec = minutes * 60
        cur_bucket: Optional[int] = None
        agg: Optional[Dict[str, Any]] = None
        for b in sub:
            bk = (int(b["time"]) // bucket_sec) * bucket_sec
            if cur_bucket != bk:
                if agg is not None:
                    grouped.append(agg)
                cur_bucket = bk
                agg = {
                    "time": bk,
                    "open": b["open"],
                    "high": b["high"],
                    "low": b["low"],
                    "close": b["close"],
                    "tick_volume": b["tick_volume"],
                }
            else:
                assert agg is not None
                if b["high"] > agg["high"]:
                    agg["high"] = b["high"]
                if b["low"] < agg["low"]:
                    agg["low"] = b["low"]
                agg["close"] = b["close"]
                agg["tick_volume"] += b["tick_volume"]
        if agg is not None:
            grouped.append(agg)

        df = pd.DataFrame(grouped[-cnt:])
        if df.empty:
            return df
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df[["time", "open", "high", "low", "close", "tick_volume"]].reset_index(drop=True)

    def spread_points(self, symbol: str) -> Optional[float]:
        if self.scenario == "spread_spike" and (self._bar_index % 20) in (15, 16, 17, 18, 19):
            return float(self.base_spread_points * 5)
        return float(self.base_spread_points)

    def get_tick(self, symbol: str) -> Optional[dict]:
        sym = self.resolve_symbol(symbol) or symbol
        bars = self._ensure_series(sym)
        last = bars[-1]
        spec = self._spec_for(sym)
        digits = int(spec["digits"])
        sp_pts = self.spread_points(sym) or float(self.base_spread_points)
        spread_val = sp_pts * float(spec["point"])
        bid = round(float(last["close"]), digits)
        ask = round(bid + spread_val, digits)
        return {"bid": bid, "ask": ask, "time": int(last["time"])}

    # ----- Kalkulasi PnL & Step Simulasi -----

    def _refresh_position_pnl(self, pos: Dict[str, Any]) -> None:
        tick = self.get_tick(pos["symbol"])
        if not tick:
            return
        spec = self._spec_for(pos["symbol"])
        pv_per_unit = float(spec["tick_value"]) / max(float(spec["tick_size"]), 1e-12)
        side = str(pos.get("type", "BUY")).upper()
        cur_price = float(tick["bid"]) if side == "BUY" else float(tick["ask"])
        pos["price_current"] = cur_price
        diff = (cur_price - float(pos["price_open"])) if side == "BUY" else (float(pos["price_open"]) - cur_price)
        pos["profit"] = round(diff * pv_per_unit * float(pos["volume"]), 2)

    def _close_at_price(self, pos: Dict[str, Any], close_price: float, comment: str = "") -> Dict[str, Any]:
        spec = self._spec_for(pos["symbol"])
        pv_per_unit = float(spec["tick_value"]) / max(float(spec["tick_size"]), 1e-12)
        side = str(pos.get("type", "BUY")).upper()
        diff = (close_price - float(pos["price_open"])) if side == "BUY" else (float(pos["price_open"]) - close_price)
        net_profit = round(diff * pv_per_unit * float(pos["volume"]), 2)
        self.balance = round(self.balance + net_profit, 2)

        last_t = self._ensure_series(pos["symbol"])[-1]["time"]
        deal = {
            "ticket": int(pos["ticket"]),
            "time": int(last_t),
            "symbol": pos["symbol"],
            "magic": int(pos.get("magic", 0)),
            "type": side,
            "volume": float(pos["volume"]),
            "price": float(close_price),
            "net_profit": net_profit,
            "profit": net_profit,
            "comment": comment or pos.get("comment", ""),
        }
        self._deals.append(deal)
        return deal

    def step_bar(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Majukan pasar simulasi 1 bar M1, aktifkan pending order & cek SL/TP."""
        self._bar_index += 1
        targets = list(self._bars_m1.keys()) if not symbol else [self.resolve_symbol(symbol) or symbol]
        if not targets:
            targets = [self.default_symbol]

        for sym in targets:
            bars = self._ensure_series(sym)
            last = bars[-1]
            idx = len(bars)
            new_bar = self._generate_bar(sym, idx, float(last["close"]))
            bars.append(new_bar)
            if len(bars) > self._history_bars + 500:
                del bars[0]

            spec = self._spec_for(sym)
            sp_val = (self.spread_points(sym) or self.base_spread_points) * float(spec["point"])
            bar_low = float(new_bar["low"])
            bar_high = float(new_bar["high"])

            # 1. Cek aktivasi pending orders pada bar baru
            remaining_pending: List[Dict[str, Any]] = []
            for po in self._pending:
                if po["symbol"] != sym:
                    remaining_pending.append(po)
                    continue
                otype = str(po["type"]).upper()
                trig = float(po["price_open"])
                triggered = False
                if otype == "BUY_STOP" and (bar_high + sp_val) >= trig:
                    triggered = True
                elif otype == "BUY_LIMIT" and (bar_low + sp_val) <= trig:
                    triggered = True
                elif otype == "SELL_STOP" and bar_low <= trig:
                    triggered = True
                elif otype == "SELL_LIMIT" and bar_high >= trig:
                    triggered = True

                if triggered:
                    side = "BUY" if otype.startswith("BUY") else "SELL"
                    self._positions.append({
                        "ticket": int(po["ticket"]),
                        "symbol": sym,
                        "type": side,
                        "volume": float(po["volume"]),
                        "price_open": trig,
                        "price_current": trig,
                        "sl": float(po.get("sl", 0.0)),
                        "tp": float(po.get("tp", 0.0)),
                        "profit": 0.0,
                        "magic": int(po.get("magic", 0)),
                        "comment": str(po.get("comment", "")),
                        "time": int(new_bar["time"]),
                    })
                else:
                    remaining_pending.append(po)
            self._pending = remaining_pending

            # 2. Cek SL / TP pada posisi terbuka
            still_open: List[Dict[str, Any]] = []
            for pos in self._positions:
                if pos["symbol"] != sym:
                    still_open.append(pos)
                    continue
                side = str(pos["type"]).upper()
                sl = float(pos.get("sl") or 0.0)
                tp = float(pos.get("tp") or 0.0)
                hit_price: Optional[float] = None
                hit_reason = ""

                if side == "BUY":
                    if sl > 0 and bar_low <= sl:
                        hit_price, hit_reason = sl, "SL"
                    elif tp > 0 and bar_high >= tp:
                        hit_price, hit_reason = tp, "TP"
                else:
                    ask_high = bar_high + sp_val
                    ask_low = bar_low + sp_val
                    if sl > 0 and ask_high >= sl:
                        hit_price, hit_reason = sl, "SL"
                    elif tp > 0 and ask_low <= tp:
                        hit_price, hit_reason = tp, "TP"

                if hit_price is not None:
                    self._close_at_price(pos, hit_price, comment=f"sim_{hit_reason.lower()}")
                else:
                    self._refresh_position_pnl(pos)
                    still_open.append(pos)
            self._positions = still_open

        return self.account_info() or {}

    # ----- Posisi, Pending Orders & Deals -----

    def positions(self, symbol: Optional[str] = None) -> list:
        res_sym = self.resolve_symbol(symbol) if symbol else None
        out = []
        for p in self._positions:
            if res_sym and p["symbol"] != res_sym:
                continue
            self._refresh_position_pnl(p)
            out.append(dict(p))
        return out

    def pending_orders(self, symbol: Optional[str] = None) -> list:
        res_sym = self.resolve_symbol(symbol) if symbol else None
        return [dict(o) for o in self._pending if not res_sym or o["symbol"] == res_sym]

    def history_deals(self, dt_from: datetime, dt_to: datetime) -> list:
        t_from = int(dt_from.timestamp()) if isinstance(dt_from, datetime) else 0
        t_to = int(dt_to.timestamp()) if isinstance(dt_to, datetime) else 2**31
        return [dict(d) for d in self._deals if t_from <= int(d.get("time", 0)) <= t_to]

    # ----- Eksekusi Order -----

    def send_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "mt5bot",
    ) -> dict:
        if not self.connected:
            return {"ok": False, "ticket": None, "message": "Simulator belum terhubung."}
        sym = self.resolve_symbol(symbol) or symbol
        self._ensure_series(sym)
        tick = self.get_tick(sym)
        if not tick:
            return {"ok": False, "ticket": None, "message": f"Harga simulasi {sym} tidak tersedia."}
        s_up = str(side).upper()
        if s_up not in ("BUY", "SELL"):
            return {"ok": False, "ticket": None, "message": f"Sisi tidak valid: {side}"}

        price = float(tick["ask"]) if s_up == "BUY" else float(tick["bid"])
        ticket = self._next_ticket
        self._next_ticket += 1
        pos = {
            "ticket": ticket,
            "symbol": sym,
            "type": s_up,
            "volume": round(float(volume), 2),
            "price_open": price,
            "price_current": price,
            "sl": float(sl or 0.0),
            "tp": float(tp or 0.0),
            "profit": 0.0,
            "magic": int(magic or 0),
            "comment": str(comment or "mt5bot"),
            "time": int(tick["time"]),
        }
        self._refresh_position_pnl(pos)
        self._positions.append(pos)
        return {"ok": True, "ticket": ticket, "message": f"[SIM] {s_up} {volume:.2f} {sym} @ {price}"}

    def close_position(self, ticket: int, symbol: str = "") -> dict:
        if not self.connected:
            return {"ok": False, "ticket": ticket, "message": "Simulator belum terhubung."}
        t_int = int(ticket)
        for idx, p in enumerate(self._positions):
            if int(p["ticket"]) == t_int:
                tick = self.get_tick(p["symbol"]) or {"bid": p["price_current"], "ask": p["price_current"]}
                close_px = float(tick["bid"]) if p["type"] == "BUY" else float(tick["ask"])
                self._positions.pop(idx)
                deal = self._close_at_price(p, close_px, comment="sim_close")
                return {
                    "ok": True,
                    "ticket": t_int,
                    "message": f"[SIM] Posisi #{t_int} ditutup ({deal['net_profit']:+.2f})",
                }
        return {"ok": False, "ticket": t_int, "message": f"Posisi #{t_int} tidak ditemukan."}

    def modify_sl_tp(
        self,
        ticket: int,
        symbol: str,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> bool:
        t_int = int(ticket)
        for p in self._positions:
            if int(p["ticket"]) == t_int:
                if sl is not None:
                    p["sl"] = float(sl)
                if tp is not None:
                    p["tp"] = float(tp)
                return True
        return False

    def send_pending_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "mt5bot",
    ) -> dict:
        if not self.connected:
            return {"ok": False, "ticket": None, "message": "Simulator belum terhubung."}
        ot = str(order_type).strip().lower()
        if ot not in PENDING_ORDER_TYPES:
            return {"ok": False, "ticket": None, "message": f"Tipe pending order tidak dikenal: {order_type}"}
        sym = self.resolve_symbol(symbol) or symbol
        self._ensure_series(sym)
        ticket = self._next_ticket
        self._next_ticket += 1
        last_t = self._ensure_series(sym)[-1]["time"]
        self._pending.append({
            "ticket": ticket,
            "symbol": sym,
            "type": ot.upper(),
            "volume": round(float(volume), 2),
            "price_open": float(price),
            "sl": float(sl or 0.0),
            "tp": float(tp or 0.0),
            "magic": int(magic or 0),
            "comment": str(comment or "mt5bot"),
            "time": int(last_t),
        })
        return {"ok": True, "ticket": ticket, "message": f"[SIM] Pending {ot.upper()} {volume:.2f} {sym} @ {price}"}

    def modify_pending_order(
        self,
        ticket: int,
        price: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> dict:
        t_int = int(ticket)
        for po in self._pending:
            if int(po["ticket"]) == t_int:
                po["price_open"] = float(price)
                if sl is not None:
                    po["sl"] = float(sl)
                if tp is not None:
                    po["tp"] = float(tp)
                return {"ok": True, "ticket": t_int, "message": f"[SIM] Pending #{t_int} diubah @ {price}"}
        return {"ok": False, "ticket": t_int, "message": f"Pending #{t_int} tidak ditemukan."}

    def delete_pending_order(self, ticket: int) -> bool:
        t_int = int(ticket)
        for idx, po in enumerate(self._pending):
            if int(po["ticket"]) == t_int:
                self._pending.pop(idx)
                return True
        return False


def run_script_replay(
    source: str,
    symbol: str = "XAUUSDm",
    timeframe: str = "M5",
    scenario: str = "volatile",
    bars: int = 120,
    initial_balance: float = 10000.0,
    spread_points: int = 25,
) -> Dict[str, Any]:
    """Jalankan uji cepat skrip Mode Programmer di SimBackend terisolasi.

    Tidak mengubah `script_state.json`, config user, ataupun koneksi MT5 aktif.
    """
    from config.settings import settings
    from src.bot_engine import BotEngine
    from strategies import script_runtime
    import logging

    try:
        script_runtime.compile_script(source)
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "trades_count": 0,
            "open_positions": 0,
            "pending_orders": 0,
            "net_profit": 0.0,
            "win_rate": 0.0,
            "max_drawdown_pct": 0.0,
            "final_balance": float(initial_balance),
            "final_equity": float(initial_balance),
            "actions": [],
            "deals": [],
        }

    # Simpan & pulihkan pengaturan global di sekitar replay agar terisolasi penuh.
    snapshot = {
        "strategy_name": settings.strategy_name,
        "script_source": settings.script_source,
        "symbol": settings.symbol,
        "timeframe_str": settings.timeframe_str,
        "max_open_positions": settings.max_open_positions,
        "magic_number": settings.magic_number,
        "max_spread_points": settings.max_spread_points,
        "daily_drawdown_limit": settings.daily_drawdown_limit,
        "equity_stop_loss": settings.equity_stop_loss,
        "max_daily_trades": settings.max_daily_trades,
    }
    actions_log: List[Dict[str, Any]] = []
    runtime_errors: List[str] = []

    class _ReplayErrorTrap(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            if record.levelno >= logging.ERROR:
                msg = record.getMessage()
                if "on_bar" in msg or "Skrip strategi error" in msg:
                    runtime_errors.append(msg)

    mt5_logger = logging.getLogger("mt5bot")
    err_trap = _ReplayErrorTrap()
    mt5_logger.addHandler(err_trap)
    try:
        settings.strategy_name = "custom_script"
        settings.script_source = source
        settings.symbol = str(symbol or "XAUUSDm").strip() or "XAUUSDm"
        settings.timeframe_str = str(timeframe or "M5").strip().upper() or "M5"

        sim = SimBackend(
            initial_balance=initial_balance,
            symbol=settings.symbol,
            scenario=scenario,
            spread_points=spread_points,
        )
        sim.connect()
        engine = BotEngine(backend=sim, persist_state=False)
        engine.on_journal = lambda entry: actions_log.append(dict(entry))

        peak_equity = float(sim.initial_balance)
        max_dd_pct = 0.0
        n_bars = max(10, min(500, int(bars or 120)))

        for _ in range(n_bars):
            sim.step_bar()
            engine.check_virtual_exits()
            ok = engine.process_trading_step()
            if runtime_errors:
                return {
                    "ok": False,
                    "error": runtime_errors[0],
                    "trades_count": 0,
                    "open_positions": len(sim.positions()),
                    "pending_orders": len(sim.pending_orders()),
                    "net_profit": 0.0,
                    "win_rate": 0.0,
                    "max_drawdown_pct": round(max_dd_pct, 2),
                    "final_balance": round(sim.balance, 2),
                    "final_equity": round(sim.balance, 2),
                    "actions": actions_log[-20:],
                    "deals": [],
                }
            acc = sim.account_info() or {}
            eq = float(acc.get("equity", sim.balance))
            if eq > peak_equity:
                peak_equity = eq
            if peak_equity > 0:
                dd = (peak_equity - eq) / peak_equity * 100.0
                if dd > max_dd_pct:
                    max_dd_pct = dd
            if ok is False:
                break

        acc_end = sim.account_info() or {}
        deals = sim.history_deals(datetime.fromtimestamp(0, tz=timezone.utc), datetime.now(timezone.utc) + timedelta(days=365))
        wins = sum(1 for d in deals if float(d.get("net_profit", 0.0)) > 0)
        losses = sum(1 for d in deals if float(d.get("net_profit", 0.0)) < 0)
        closed_cnt = len(deals)
        win_rate = round((wins / closed_cnt * 100.0), 1) if closed_cnt > 0 else 0.0
        net_profit = round(float(acc_end.get("equity", sim.balance)) - sim.initial_balance, 2)

        return {
            "ok": True,
            "error": "",
            "symbol": settings.symbol,
            "timeframe": settings.timeframe_str,
            "scenario": sim.scenario,
            "bars": n_bars,
            "initial_balance": round(sim.initial_balance, 2),
            "final_balance": round(float(acc_end.get("balance", sim.balance)), 2),
            "final_equity": round(float(acc_end.get("equity", sim.balance)), 2),
            "net_profit": net_profit,
            "trades_count": closed_cnt,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "max_drawdown_pct": round(max_dd_pct, 2),
            "open_positions": len(sim.positions()),
            "pending_orders": len(sim.pending_orders()),
            "actions_count": len(actions_log),
            "actions": actions_log[-40:],
            "deals": deals[-40:],
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Simulasi gagal: {exc}",
            "trades_count": 0,
            "open_positions": 0,
            "pending_orders": 0,
            "net_profit": 0.0,
            "win_rate": 0.0,
            "max_drawdown_pct": 0.0,
            "final_balance": float(initial_balance),
            "final_equity": float(initial_balance),
            "actions": actions_log[-20:],
            "deals": [],
        }
    finally:
        mt5_logger.removeHandler(err_trap)
        for k, v in snapshot.items():
            setattr(settings, k, v)
