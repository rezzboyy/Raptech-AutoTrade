from __future__ import annotations

"""
Raptech Autotrade CLI — Standalone Offline Simulation Backend (Paper Trading).
Provides 100% realistic, zero-network simulated trading environment:
- Synthetic realistic price walk with spread & tick volume
- Instant virtual order fills, margin calculation & equity tracking
- Automatic Stop Loss & Take Profit execution
- Local state persistence in data/simulation_state.json
- Full compliance with TradingBackend Protocol
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import random
import tempfile
import time
from typing import Any, Dict, List, Optional

from backend.base import (
    AccountInfo,
    Candle,
    OrderResult,
    OrderState,
    Position,
    SymbolSpec,
    Tick,
    TradingBackend,
    map_timeframe_to_period,
    resolve_symbol_name,
)
from core.logger import get_logger

logger = get_logger("backend.simulation")

SIMULATION_STATE_FILE = Path("data/simulation_state.json")

# Standard instruments with realistic base market specs
DEFAULT_SPECS: Dict[str, Dict[str, Any]] = {
    "XAUUSDm": {
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "volume_min": 0.01,
        "volume_max": 50.0,
        "volume_step": 0.01,
        "stop_level": 10,
        "base_price": 2735.50,
        "spread_pts": 25.0,
        "volatility": 0.0004,
        "contract_size": 100.0,
    },
    "EURUSDm": {
        "digits": 5,
        "point": 0.00001,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 5,
        "base_price": 1.08450,
        "spread_pts": 12.0,
        "volatility": 0.0002,
        "contract_size": 100000.0,
    },
    "GBPUSDm": {
        "digits": 5,
        "point": 0.00001,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 8,
        "base_price": 1.29820,
        "spread_pts": 15.0,
        "volatility": 0.00025,
        "contract_size": 100000.0,
    },
    "BTCUSDm": {
        "digits": 2,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "volume_min": 0.01,
        "volume_max": 20.0,
        "volume_step": 0.01,
        "stop_level": 50,
        "base_price": 68500.00,
        "spread_pts": 280.0,
        "volatility": 0.0008,
        "contract_size": 1.0,
    },
    "USDJPYm": {
        "digits": 3,
        "point": 0.001,
        "tick_size": 0.001,
        "tick_value": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "stop_level": 10,
        "base_price": 152.450,
        "spread_pts": 14.0,
        "volatility": 0.0003,
        "contract_size": 100000.0,
    },
}


class SimulationBackend:
    """Offline Paper Trading Backend conforming to TradingBackend Protocol."""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        state_file: Path = SIMULATION_STATE_FILE,
        seed: Optional[int] = None,
    ) -> None:
        self.state_file = state_file
        self.initial_balance = initial_balance
        self._connected = False
        self._next_ticket = 90001

        if seed is not None:
            random.seed(seed)

        # In-memory account & position state
        self.balance: float = initial_balance
        self.currency: str = "USD"
        self.leverage: int = 100
        self._positions: Dict[int, Position] = {}
        self._pending_orders: Dict[int, Dict[str, Any]] = {}
        self._closed_history: List[Dict[str, Any]] = []

        # Current synthetic prices (symbol -> current_mid_price)
        self._prices: Dict[str, float] = {}
        for sym, cfg in DEFAULT_SPECS.items():
            self._prices[sym] = float(cfg["base_price"])
            # Alias without 'm' suffix
            root = sym.rstrip("m")
            self._prices[root] = float(cfg["base_price"])

        # Load persisted simulation state if exists
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.balance = float(data.get("balance", self.initial_balance))
            self._next_ticket = int(data.get("next_ticket", 90001))

            raw_pos = data.get("positions", [])
            for p in raw_pos:
                pos = Position(
                    ticket=p["ticket"],
                    symbol=p["symbol"],
                    type=p["type"],
                    volume=p["volume"],
                    price_open=p["price_open"],
                    price_current=p.get("price_current", p["price_open"]),
                    sl=p.get("sl", 0.0),
                    tp=p.get("tp", 0.0),
                    profit=p.get("profit", 0.0),
                    magic=p.get("magic", 0),
                    comment=p.get("comment", "sim_order"),
                    time=datetime.fromisoformat(p["time"]) if "time" in p else datetime.now(timezone.utc),
                    virtual_sl=p.get("virtual_sl", 0.0),
                    virtual_tp=p.get("virtual_tp", 0.0),
                )
                self._positions[pos.ticket] = pos
            logger.info(f"Loaded simulation state: Saldo ${self.balance:,.2f}, {len(self._positions)} posisi aktif.")
        except Exception as e:
            logger.warning(f"Gagal memuat simulation state: {e}. Menggunakan state awal.")

    def _save_state(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            pos_list = []
            for p in self._positions.values():
                d = asdict(p)
                if isinstance(d.get("time"), datetime):
                    d["time"] = d["time"].isoformat()
                pos_list.append(d)

            data = {
                "balance": round(self.balance, 2),
                "next_ticket": self._next_ticket,
                "positions": pos_list,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            temp_fd, temp_name = tempfile.mkstemp(
                dir=self.state_file.parent, prefix="sim_", suffix=".tmp"
            )
            with open(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_name, self.state_file)
        except Exception as e:
            logger.error(f"Gagal menyimpan simulation state: {e}")

    # =========================================================================
    # Connection Lifecycle
    # =========================================================================

    def connect(self) -> bool:
        self._connected = True
        logger.info("SimulationBackend terhubung (Paper Trading Engine aktif).")
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._save_state()
        logger.info("SimulationBackend terputus (State tersimpan).")

    # =========================================================================
    # Account & Market Info
    # =========================================================================

    def account_info(self) -> Optional[AccountInfo]:
        if not self._connected:
            return None

        # Recompute positions PnL and total margin
        floating_profit = 0.0
        used_margin = 0.0

        # Update ticks & check SL/TP for open positions
        self._check_and_update_positions()

        for p in self._positions.values():
            floating_profit += p.profit
            cfg = self._get_cfg(p.symbol)
            contract = cfg["contract_size"]
            # Standard leverage-based margin: (volume * contract * price) / leverage
            pos_mgn = (p.volume * contract * p.price_open) / max(1, self.leverage)
            used_margin += pos_mgn

        equity = self.balance + floating_profit
        free_margin = max(0.0, equity - used_margin)
        margin_level = (equity / used_margin * 100.0) if used_margin > 0 else 0.0

        return AccountInfo(
            login=999999,
            server="Raptech-Simulation",
            currency=self.currency,
            balance=round(self.balance, 2),
            equity=round(equity, 2),
            margin=round(used_margin, 2),
            free_margin=round(free_margin, 2),
            margin_level=round(margin_level, 1),
            profit=round(floating_profit, 2),
            trade_allowed=True,
            server_connected=True,
            account_type="SIMULASI",
            leverage=self.leverage,
            is_cent=False,
        )

    def list_symbols(self, limit: int = 60) -> List[str]:
        return list(DEFAULT_SPECS.keys())[:limit]

    def _get_cfg(self, symbol: str) -> Dict[str, Any]:
        sym_clean = symbol.strip()
        if sym_clean in DEFAULT_SPECS:
            return DEFAULT_SPECS[sym_clean]
        # Match alias with or without m
        for k, v in DEFAULT_SPECS.items():
            if k.rstrip("m").upper() == sym_clean.rstrip("m").upper():
                return v
        return DEFAULT_SPECS["XAUUSDm"]

    def symbol_spec(self, symbol: str) -> Optional[SymbolSpec]:
        cfg = self._get_cfg(symbol)
        return SymbolSpec(
            symbol=symbol,
            digits=cfg["digits"],
            point=cfg["point"],
            volume_min=cfg["volume_min"],
            volume_max=cfg["volume_max"],
            volume_step=cfg["volume_step"],
            tick_value=cfg["tick_value"],
            tick_size=cfg["tick_size"],
            stop_level=cfg["stop_level"],
        )

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        return resolve_symbol_name(symbol, list(DEFAULT_SPECS.keys())) or symbol

    def ensure_symbol(self, symbol: str) -> bool:
        return True

    # =========================================================================
    # Market Data & Price Engine
    # =========================================================================

    def _step_price(self, symbol: str) -> float:
        cfg = self._get_cfg(symbol)
        curr = self._prices.get(symbol, cfg["base_price"])
        # Micro Gaussian step
        drift = random.gauss(0, cfg["volatility"])
        new_price = max(curr * 0.5, curr * (1.0 + drift))
        new_price = round(new_price, cfg["digits"])
        self._prices[symbol] = new_price
        return new_price

    def get_tick(self, symbol: str) -> Optional[Tick]:
        if not self._connected:
            return None

        cfg = self._get_cfg(symbol)
        mid = self._step_price(symbol)
        half_spread = (cfg["spread_pts"] * cfg["point"]) / 2.0
        bid = round(mid - half_spread, cfg["digits"])
        ask = round(mid + half_spread, cfg["digits"])

        return Tick(
            bid=bid,
            ask=ask,
            time=datetime.now(timezone.utc),
            last=mid,
            volume=random.randint(1, 20),
        )

    def spread_points(self, symbol: str) -> Optional[float]:
        cfg = self._get_cfg(symbol)
        return float(cfg["spread_pts"])

    def get_candles(self, symbol: str, timeframe_str: str, count: int = 200) -> List[Candle]:
        """Generate realistic synthetic candle series backward from current time."""
        cfg = self._get_cfg(symbol)
        digits = cfg["digits"]
        period = map_timeframe_to_period(timeframe_str)

        # Minutes per candle
        mins_map = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}
        bar_mins = mins_map.get(period, 5)
        bar_delta = timedelta(minutes=bar_mins)

        now = datetime.now(timezone.utc)
        curr_price = self._prices.get(symbol, cfg["base_price"])

        # Generate price backward or forward
        candles: List[Candle] = []
        p = curr_price
        start_time = now - (bar_delta * count)

        # Fixed deterministic pseudo-walk for consistent indicator curves
        vol = cfg["volatility"] * math.sqrt(bar_mins)
        p_walk = p * (1.0 - (count * 0.0002))  # slight trend

        for i in range(count):
            c_time = start_time + (bar_delta * i)
            # Candle open
            o = p_walk
            step = random.gauss(0, vol * p_walk)
            c = round(max(o * 0.5, o + step), digits)
            h = round(max(o, c) + abs(random.gauss(0, vol * p_walk * 0.6)), digits)
            l = round(min(o, c) - abs(random.gauss(0, vol * p_walk * 0.6)), digits)
            vol_val = random.randint(15, 250)

            candles.append(Candle(time=c_time, open=o, high=h, low=l, close=c, tick_volume=vol_val))
            p_walk = c

        return candles

    # =========================================================================
    # Position Tracking & Auto SL/TP Engine
    # =========================================================================

    def _check_and_update_positions(self) -> None:
        """Update floating PnL and trigger SL/TP hits automatically."""
        tickets_to_close: List[int] = []

        for ticket, p in list(self._positions.items()):
            cfg = self._get_cfg(p.symbol)
            mid = self._prices.get(p.symbol, cfg["base_price"])
            half_spread = (cfg["spread_pts"] * cfg["point"]) / 2.0
            bid = round(mid - half_spread, cfg["digits"])
            ask = round(mid + half_spread, cfg["digits"])

            contract = cfg["contract_size"]

            if p.type.upper() == "BUY":
                p.price_current = bid
                p.profit = round((bid - p.price_open) * contract * p.volume, 2)
                # Check Hard SL
                if p.sl > 0.0 and bid <= p.sl:
                    logger.info(f"🛑 [SIM] Position #{ticket} BUY hit Stop Loss at {bid:.{cfg['digits']}f} (SL: {p.sl})")
                    tickets_to_close.append(ticket)
                # Check Hard TP
                elif p.tp > 0.0 and bid >= p.tp:
                    logger.info(f"🎯 [SIM] Position #{ticket} BUY hit Take Profit at {bid:.{cfg['digits']}f} (TP: {p.tp})")
                    tickets_to_close.append(ticket)
            else:  # SELL
                p.price_current = ask
                p.profit = round((p.price_open - ask) * contract * p.volume, 2)
                # Check Hard SL
                if p.sl > 0.0 and ask >= p.sl:
                    logger.info(f"🛑 [SIM] Position #{ticket} SELL hit Stop Loss at {ask:.{cfg['digits']}f} (SL: {p.sl})")
                    tickets_to_close.append(ticket)
                # Check Hard TP
                elif p.tp > 0.0 and ask <= p.tp:
                    logger.info(f"🎯 [SIM] Position #{ticket} SELL hit Take Profit at {ask:.{cfg['digits']}f} (TP: {p.tp})")
                    tickets_to_close.append(ticket)

        for t in tickets_to_close:
            p = self._positions.get(t)
            if p:
                self.close_position(ticket=t, symbol=p.symbol)

    def positions(self, symbol: Optional[str] = None) -> List[Position]:
        self._check_and_update_positions()
        if not symbol:
            return list(self._positions.values())
        sym_clean = symbol.strip().upper()
        return [p for p in self._positions.values() if p.symbol.upper() == sym_clean]

    # =========================================================================
    # Order Execution (Market, Close, Modify, Pending)
    # =========================================================================

    def send_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "raptech_cli",
    ) -> OrderResult:
        if not self._connected:
            return OrderResult(ok=False, message="Simulation backend not connected")

        cfg = self._get_cfg(symbol)
        digits = cfg["digits"]
        mid = self._step_price(symbol)
        half_spread = (cfg["spread_pts"] * cfg["point"]) / 2.0
        bid = round(mid - half_spread, digits)
        ask = round(mid + half_spread, digits)

        order_side = side.strip().upper()
        fill_price = ask if order_side == "BUY" else bid

        ticket = self._next_ticket
        self._next_ticket += 1

        pos = Position(
            ticket=ticket,
            symbol=symbol,
            type=order_side,
            volume=round(volume, 2),
            price_open=fill_price,
            price_current=fill_price,
            sl=round(sl, digits) if sl > 0 else 0.0,
            tp=round(tp, digits) if tp > 0 else 0.0,
            profit=0.0,
            magic=magic,
            comment=comment or "sim_market",
            time=datetime.now(timezone.utc),
        )

        self._positions[ticket] = pos
        self._save_state()

        logger.info(
            f"✅ [SIM] Order #{ticket} {order_side} {volume} lot on {symbol} filled at {fill_price} "
            f"(SL: {pos.sl}, TP: {pos.tp})"
        )

        return OrderResult(
            ok=True,
            ticket=ticket,
            order=ticket,
            message="Simulated market order filled successfully",
            price=fill_price,
            volume=volume,
            state=OrderState.FILLED,
        )

    def close_position(
        self, ticket: int, symbol: str, volume: Optional[float] = None
    ) -> OrderResult:
        if ticket not in self._positions:
            return OrderResult(ok=False, message=f"Position #{ticket} not found in simulation")

        pos = self._positions[ticket]
        cfg = self._get_cfg(pos.symbol)
        mid = self._step_price(pos.symbol)
        half_spread = (cfg["spread_pts"] * cfg["point"]) / 2.0
        bid = round(mid - half_spread, cfg["digits"])
        ask = round(mid + half_spread, cfg["digits"])

        close_price = bid if pos.type.upper() == "BUY" else ask
        contract = cfg["contract_size"]

        close_vol = volume if volume and volume < pos.volume else pos.volume

        if pos.type.upper() == "BUY":
            pnl = (close_price - pos.price_open) * contract * close_vol
        else:
            pnl = (pos.price_open - close_price) * contract * close_vol

        pnl = round(pnl, 2)
        self.balance = round(self.balance + pnl, 2)

        # Partial vs full close
        if close_vol < pos.volume:
            pos.volume = round(pos.volume - close_vol, 2)
        else:
            del self._positions[ticket]

        self._closed_history.append({
            "ticket": ticket,
            "symbol": pos.symbol,
            "type": pos.type,
            "volume": close_vol,
            "open_price": pos.price_open,
            "close_price": close_price,
            "pnl": pnl,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        })

        self._save_state()

        logger.info(
            f"🏁 [SIM] Closed #{ticket} {pos.symbol} {close_vol} lot at {close_price} "
            f"PnL: {'+' if pnl >= 0 else ''}${pnl:,.2f} -> Balance: ${self.balance:,.2f}"
        )

        return OrderResult(
            ok=True,
            ticket=ticket,
            price=close_price,
            volume=close_vol,
            message=f"Simulated position #{ticket} closed with PnL ${pnl:,.2f}",
            state=OrderState.FILLED,
        )

    def modify_sl_tp(
        self, ticket: int, symbol: str, sl: Optional[float] = None, tp: Optional[float] = None
    ) -> bool:
        if ticket not in self._positions:
            return False
        pos = self._positions[ticket]
        cfg = self._get_cfg(pos.symbol)
        if sl is not None:
            pos.sl = round(sl, cfg["digits"])
        if tp is not None:
            pos.tp = round(tp, cfg["digits"])
        self._save_state()
        logger.info(f"✏️ [SIM] Modified #{ticket} SL: {pos.sl}, TP: {pos.tp}")
        return True

    def send_pending_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "raptech_cli",
    ) -> OrderResult:
        ticket = self._next_ticket
        self._next_ticket += 1
        cfg = self._get_cfg(symbol)
        self._pending_orders[ticket] = {
            "ticket": ticket,
            "symbol": symbol,
            "type": order_type,
            "volume": volume,
            "price": round(price, cfg["digits"]),
            "sl": round(sl, cfg["digits"]) if sl > 0 else 0.0,
            "tp": round(tp, cfg["digits"]) if tp > 0 else 0.0,
            "magic": magic,
            "comment": comment,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return OrderResult(
            ok=True,
            ticket=ticket,
            price=price,
            volume=volume,
            message="Simulated pending order created",
            state=OrderState.CREATED,
        )

    def delete_pending_order(self, ticket: int) -> OrderResult:
        if ticket in self._pending_orders:
            del self._pending_orders[ticket]
            return OrderResult(ok=True, ticket=ticket, message="Pending order deleted")
        return OrderResult(ok=False, message=f"Pending order #{ticket} not found")
