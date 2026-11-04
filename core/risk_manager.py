from __future__ import annotations

"""
Raptech Autotrade CLI — Production-Grade Risk & Protection Manager (v3.0).
Enforces Absolute Capital Safety Invariants:
1. Dual-Layer Protection: Server-side Broker Hard SL + Virtual Local SL/TP
2. Crash & Restart Persistence via StateStore (High-Water Mark, Circuit Breaker, Virtual States)
3. Dynamic Virtual Trailing Stop with water-mark protection
4. Net Daily Loss & Peak High-Water Mark Drawdown Circuit Breakers
5. Maximum Position, Margin, and Symbol Exposure Safeguards
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from backend.base import AccountInfo, Position, SymbolSpec, Tick, TradingBackend
from core.config_store import RiskSettings
from core.logger import get_logger
from core.state_store import PersistedVirtualProtection, StateStore

logger = get_logger("risk_manager")


def classify_market_symbol(symbol: str) -> str:
    """Classify symbol into 'forex' | 'metal' | 'crypto' | 'index' | 'oil'."""
    s = str(symbol or "").strip().upper()
    if any(k in s for k in ("BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "BNB", "ADA", "DOT", "AVAX")):
        return "crypto"
    if any(k in s for k in ("XAU", "GOLD", "XAG", "SILVER", "PLAT", "PALL")):
        return "metal"
    if any(k in s for k in ("US30", "US500", "USTEC", "NAS100", "DJ30", "GER40", "UK100", "JPN225")):
        return "index"
    if any(k in s for k in ("USOIL", "UKOIL", "BRENT", "WTI")):
        return "oil"
    return "forex"


@dataclass
class VirtualProtectionState:
    ticket: int
    symbol: str
    side: str
    price_open: float
    virtual_sl: float = 0.0
    virtual_tp: float = 0.0
    trailing_active: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0


class RiskManager:
    """Monitors capital limits, virtual stop levels, and enforces safety locks."""

    def __init__(
        self,
        backend: TradingBackend,
        settings: RiskSettings,
        state_store: Optional[StateStore] = None,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.state_store = state_store or StateStore()
        self.virtual_states: Dict[int, VirtualProtectionState] = {}
        self.current_trade_date: Optional[date] = None

        # Load persisted metrics to survive crashes / reboots
        p_state = self.state_store.state
        self.daily_start_balance: float = p_state.daily_start_balance
        self.high_water_mark_equity: float = p_state.high_water_mark_equity
        self.circuit_breaker_tripped: bool = p_state.circuit_breaker_tripped
        self.circuit_breaker_reason: str = p_state.circuit_breaker_reason

        # Restore virtual protection states from disk
        self._restore_persisted_virtual_states()

    def _restore_persisted_virtual_states(self) -> None:
        """Restore virtual SL/TP tracking for positions that were open before restart."""
        saved_prots = self.state_store.state.virtual_protections
        for t_str, data in saved_prots.items():
            try:
                ticket = int(t_str)
                self.virtual_states[ticket] = VirtualProtectionState(
                    ticket=ticket,
                    symbol=str(data.get("symbol", "")),
                    side=str(data.get("side", "BUY")).upper(),
                    price_open=float(data.get("price_open", 0.0)),
                    virtual_sl=float(data.get("virtual_sl", 0.0)),
                    virtual_tp=float(data.get("virtual_tp", 0.0)),
                    trailing_active=bool(data.get("trailing_active", False)),
                    highest_price=float(data.get("highest_price", 0.0)),
                    lowest_price=float(data.get("lowest_price", 0.0)),
                )
            except Exception as e:
                logger.error(f"Gagal restore virtual protection #{t_str}: {e}")

        if self.virtual_states:
            logger.info(
                f"✔ State Recovery: {len(self.virtual_states)} state proteksi virtual berhasil dipulihkan dari disk."
            )
        if self.circuit_breaker_tripped:
            logger.warning(
                f"🚨 State Recovery: Circuit Breaker TETAP TERKUNCI setelah restart! Alasan: {self.circuit_breaker_reason}"
            )

    def reset_daily_metrics_if_new_day(
        self, current_balance: float, current_equity: Optional[float] = None
    ) -> None:
        """Evaluate date change and synchronize daily baselines with persistent store."""
        today = date.today()
        today_str = today.isoformat()
        eq = current_equity if current_equity is not None else current_balance

        if self.current_trade_date != today:
            self.current_trade_date = today
            # If starting fresh or calendar day rolled over
            if self.state_store.state.trade_date != today_str:
                self.daily_start_balance = current_balance
                self.high_water_mark_equity = max(current_balance, eq)
                self.circuit_breaker_tripped = False
                self.circuit_breaker_reason = ""
                logger.info(
                    f"Reset harian: Tanggal baru {today}, Saldo awal = ${current_balance:,.2f}"
                )
            else:
                # Same day restart: maintain persisted daily baseline!
                if self.state_store.state.daily_start_balance > 0:
                    self.daily_start_balance = self.state_store.state.daily_start_balance
                else:
                    self.daily_start_balance = current_balance

                if self.state_store.state.high_water_mark_equity > 0:
                    self.high_water_mark_equity = self.state_store.state.high_water_mark_equity
                else:
                    self.high_water_mark_equity = max(current_balance, eq)

            self.state_store.update_daily_metrics(
                today_str=today_str,
                start_balance=self.daily_start_balance,
                current_equity=self.high_water_mark_equity,
            )
        else:
            # Update high water mark if equity pushed higher
            if eq > self.high_water_mark_equity:
                self.high_water_mark_equity = eq
                self.state_store.update_daily_metrics(
                    today_str=today_str,
                    start_balance=self.daily_start_balance,
                    current_equity=self.high_water_mark_equity,
                )

    def check_pre_trade_risk(
        self,
        symbol: str,
        side: str,
        volume: float,
        account: Optional[AccountInfo],
        current_positions: List[Position],
        sl_points: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """Comprehensive pre-trade risk verification before any order is submitted."""
        # 1. Circuit breaker lock
        if self.circuit_breaker_tripped:
            return False, self.circuit_breaker_reason

        # 2. Account data freshness
        if account is None or account.equity <= 0:
            return False, "Data akun tidak tersedia atau ekuitas <= 0"

        self.reset_daily_metrics_if_new_day(account.balance, account.equity)

        # 3. Check max open positions (total concurrent portfolio exposure)
        if len(current_positions) >= self.settings.max_open_positions:
            return False, (
                f"Batas maksimum posisi terbuka tercapai "
                f"({len(current_positions)}/{self.settings.max_open_positions})"
            )

        # 4. Check symbol-specific exposure limit
        curr_sym_vol = sum(p.volume for p in current_positions if p.symbol == symbol)
        if (curr_sym_vol + volume) > self.settings.max_symbol_exposure_lots:
            return False, (
                f"Eksposur simbol {symbol} melampaui limit "
                f"({curr_sym_vol + volume:.2f} lot > maks {self.settings.max_symbol_exposure_lots:.2f} lot)"
            )

        # 5. Check minimum margin level
        if account.margin > 0 and account.margin_level > 0:
            if account.margin_level < self.settings.min_margin_level:
                return False, (
                    f"Margin level terlalu rendah "
                    f"({account.margin_level:.1f}% < min {self.settings.min_margin_level}%)"
                )

        # 6. Check free margin deficit (when margin is in use)
        if account.margin > 0 and account.free_margin > 0:
            if account.free_margin <= (account.equity * 0.05):
                return False, f"Free margin kritis (${account.free_margin:,.2f}), tolak order baru"

        # 7. Check daily net loss limit (Realized + Floating)
        current_daily_pnl = account.equity - self.daily_start_balance
        if current_daily_pnl < 0 and abs(current_daily_pnl) >= self.settings.max_daily_loss:
            self.trip_circuit_breaker(
                f"Kerugian harian (-${abs(current_daily_pnl):,.2f}) melampaui limit (-${self.settings.max_daily_loss:,.2f})"
            )
            return False, self.circuit_breaker_reason

        # 8. Check Peak High-Water Mark Drawdown percentage
        if self.high_water_mark_equity > 0:
            dd_pct = (
                (self.high_water_mark_equity - account.equity)
                / self.high_water_mark_equity
            ) * 100.0
            if dd_pct >= self.settings.max_drawdown_percent:
                self.trip_circuit_breaker(
                    f"Drawdown ekuitas puncak ({dd_pct:.2f}%) melampaui limit ({self.settings.max_drawdown_percent:.1f}%)"
                )
                return False, self.circuit_breaker_reason

        # 9. Check Spread vs Stop Loss safety (Anti-Instant Stop-out)
        if hasattr(self.backend, "spread_points"):
            try:
                spread_pts = self.backend.spread_points(symbol)
                if spread_pts is not None and spread_pts > 0:
                    raw_sl = sl_points if (sl_points is not None and sl_points > 0) else self.settings.virtual_sl_points
                    spec = self.backend.symbol_spec(symbol) if hasattr(self.backend, "symbol_spec") else None
                    base_scaled_sl = self.adapt_points_to_symbol(symbol, raw_sl, spec, spread_pts=0.0)
                    if base_scaled_sl > 0 and spread_pts >= (base_scaled_sl * 0.8):
                        return False, (
                            f"Spread pasar {symbol} ({spread_pts:.0f} pts) terlalu lebar "
                            f"relatif terhadap Stop Loss ({base_scaled_sl} pts). Entry ditolak demi proteksi modal."
                        )
            except Exception as e:
                logger.debug(f"Error checking spread pre-trade: {e}")

        return True, "Risk check passed"

    def trip_circuit_breaker(self, reason: str) -> None:
        """Lock trading and persist lock to disk."""
        self.circuit_breaker_tripped = True
        self.circuit_breaker_reason = f"Circuit Breaker Aktif: {reason}"
        logger.warning(f"🚨 {self.circuit_breaker_reason}")
        self.state_store.record_circuit_breaker(True, self.circuit_breaker_reason)

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker lock and clear persisted state."""
        self.circuit_breaker_tripped = False
        self.circuit_breaker_reason = ""
        self.state_store.record_circuit_breaker(False, "")
        logger.info("✔ Circuit Breaker berhasil di-reset.")

    def adapt_points_to_symbol(
        self,
        symbol: str,
        base_points: int,
        spec: Optional[SymbolSpec] = None,
        spread_pts: Optional[float] = None,
    ) -> int:
        """
        Adapt generic/forex base points to the specific symbol class (Crypto, Gold, Indices, Forex).
        Guarantees that Stop Loss is NEVER placed inside the broker's spread.
        """
        if not symbol or base_points <= 0:
            return base_points

        cat = classify_market_symbol(symbol)
        sym_clean = str(symbol).strip().upper()
        multiplier = 1.0
        min_floor = base_points

        if spec is None and hasattr(self.backend, "symbol_spec"):
            try:
                spec = self.backend.symbol_spec(symbol)
            except Exception:
                spec = None

        digits = spec.digits if spec else 5

        if cat == "crypto":
            if "BTC" in sym_clean:
                # Bitcoin: ~$80,000, 2 digits, 1 pt = $0.01.
                # Base 150 pts ($1.50) is smaller than spread (~$6.40 - $8.50).
                # Normal scalp SL is $50 - $120 (5,000 - 12,000 points).
                multiplier = 40.0
                min_floor = 4000
            elif "ETH" in sym_clean:
                # Ethereum: ~$2,600, 2 digits. Scalp SL ~$10 - $25 (1,000 - 2,500 points).
                multiplier = 10.0
                min_floor = 1000
            else:
                multiplier = 6.0
                min_floor = 600
        elif cat == "metal":
            if digits >= 3:
                # 3-digit Gold (e.g. Exness XAUUSDm 4043.203): 1 pt = $0.001.
                # Base 150 pts = $0.15 (less than spread $0.24!).
                # Scalp SL should be $1.50 - $3.00 (1,500 - 3,000 points).
                multiplier = 10.0
                min_floor = 1500
            else:
                multiplier = 1.0
                min_floor = 150
        elif cat == "index":
            multiplier = 10.0
            min_floor = 1000
        elif cat == "oil":
            multiplier = 2.0
            min_floor = 200
        else:
            # Forex (EURUSD, GBPUSD, etc.)
            multiplier = 1.0
            min_floor = base_points

        scaled = int(round(base_points * multiplier))
        scaled = max(scaled, min_floor)

        # Spread-based absolute safety floor:
        # Stop Loss MUST be strictly greater than spread (at least 2.5x spread)
        # to prevent instant stop-out on execution fill!
        if spread_pts is None and hasattr(self.backend, "spread_points"):
            try:
                spread_pts = self.backend.spread_points(symbol)
            except Exception:
                spread_pts = None

        if spread_pts is not None and spread_pts > 0:
            spread_floor = int(spread_pts * 2.5)
            if scaled < spread_floor:
                scaled = spread_floor

        return scaled

    def adapt_tp_points(
        self,
        symbol: str,
        base_tp_points: int,
        adapted_sl_points: int,
        spec: Optional[SymbolSpec] = None,
    ) -> int:
        """Adapt TP points proportionally to the adapted SL points."""
        if not symbol or base_tp_points <= 0:
            return base_tp_points

        cat = classify_market_symbol(symbol)
        sym_clean = str(symbol).strip().upper()
        multiplier = 1.0

        if spec is None and hasattr(self.backend, "symbol_spec"):
            try:
                spec = self.backend.symbol_spec(symbol)
            except Exception:
                spec = None
        digits = spec.digits if spec else 5

        if cat == "crypto":
            if "BTC" in sym_clean:
                multiplier = 40.0
            elif "ETH" in sym_clean:
                multiplier = 10.0
            else:
                multiplier = 6.0
        elif cat == "metal":
            multiplier = 10.0 if digits >= 3 else 1.0
        elif cat == "index":
            multiplier = 10.0
        elif cat == "oil":
            multiplier = 2.0

        scaled = int(round(base_tp_points * multiplier))
        if adapted_sl_points > 0:
            scaled = max(scaled, int(adapted_sl_points * 1.2))
        return scaled

    def calculate_server_sl_tp(
        self,
        side: str,
        price_open: float,
        spec: Optional[SymbolSpec],
        symbol: str = "",
        sl_points: Optional[int] = None,
        tp_points: Optional[int] = None,
    ) -> Tuple[float, float]:
        """
        Calculate broker-side hard SL and TP prices for server-side layering.
        Returns (sl_price, tp_price).
        """
        if not self.settings.use_server_sl:
            return 0.0, 0.0

        point = spec.point if spec else 0.00001
        is_buy = side.upper() == "BUY"
        sl_pts = (
            sl_points
            if sl_points is not None and sl_points > 0
            else (
                self.settings.server_sl_points
                if self.settings.server_sl_points > 0
                else self.settings.virtual_sl_points
            )
        )
        tp_pts = (
            tp_points
            if tp_points is not None and tp_points > 0
            else self.settings.virtual_tp_points
        )

        if symbol:
            sl_pts = self.adapt_points_to_symbol(symbol, sl_pts, spec)
            tp_pts = self.adapt_tp_points(symbol, tp_pts, sl_pts, spec)

        server_sl = 0.0
        server_tp = 0.0

        if sl_pts > 0:
            offset = sl_pts * point
            server_sl = price_open - offset if is_buy else price_open + offset
            digits = spec.digits if spec else 5
            server_sl = round(server_sl, digits)

        if tp_pts > 0:
            offset = tp_pts * point
            server_tp = price_open + offset if is_buy else price_open - offset
            digits = spec.digits if spec else 5
            server_tp = round(server_tp, digits)

        return server_sl, server_tp

    def register_position(
        self,
        pos: Position,
        spec: Optional[SymbolSpec],
        sl_points: Optional[int] = None,
        tp_points: Optional[int] = None,
    ) -> None:
        """Register position for virtual SL/TP and dynamic trailing, persisting to disk."""
        if pos.ticket in self.virtual_states:
            return

        point = spec.point if spec else 0.00001
        is_buy = pos.type.upper() == "BUY"
        v_sl = 0.0
        v_tp = 0.0

        raw_sl = sl_points if sl_points is not None else self.settings.virtual_sl_points
        raw_tp = tp_points if tp_points is not None else self.settings.virtual_tp_points

        effective_sl = self.adapt_points_to_symbol(pos.symbol, raw_sl, spec)
        effective_tp = self.adapt_tp_points(pos.symbol, raw_tp, effective_sl, spec)

        if effective_sl > 0:
            offset = effective_sl * point
            v_sl = pos.price_open - offset if is_buy else pos.price_open + offset

        if effective_tp > 0:
            offset = effective_tp * point
            v_tp = pos.price_open + offset if is_buy else pos.price_open - offset

        digits = spec.digits if spec else 5
        v_sl = round(v_sl, digits) if v_sl > 0 else 0.0
        v_tp = round(v_tp, digits) if v_tp > 0 else 0.0

        state = VirtualProtectionState(
            ticket=pos.ticket,
            symbol=pos.symbol,
            side=pos.type.upper(),
            price_open=pos.price_open,
            virtual_sl=v_sl,
            virtual_tp=v_tp,
            highest_price=pos.price_open,
            lowest_price=pos.price_open,
        )
        self.virtual_states[pos.ticket] = state

        # Atomic disk persistence
        self.state_store.set_virtual_protection(
            PersistedVirtualProtection(
                ticket=pos.ticket,
                symbol=pos.symbol,
                side=pos.type.upper(),
                price_open=pos.price_open,
                virtual_sl=v_sl,
                virtual_tp=v_tp,
                highest_price=pos.price_open,
                lowest_price=pos.price_open,
            )
        )
        logger.info(
            f"✔ Proteksi Virtual terdaftar untuk #{pos.ticket} (SL: {v_sl:.5f}, TP: {v_tp:.5f})"
        )

    def unregister_position(self, ticket: int) -> None:
        """Remove virtual protection tracking for a closed position."""
        if ticket in self.virtual_states:
            del self.virtual_states[ticket]
        self.state_store.remove_virtual_protection(ticket)

    def evaluate_virtual_protections(
        self, positions: List[Position]
    ) -> List[Tuple[Position, str]]:
        """Evaluate open positions against virtual SL/TP and trailing stop."""
        actions_to_close: List[Tuple[Position, str]] = []
        active_tickets = {p.ticket for p in positions}

        # 1. Clean up states for closed positions
        for t in list(self.virtual_states.keys()):
            if t not in active_tickets:
                del self.virtual_states[t]
                self.state_store.remove_virtual_protection(t)

        for pos in positions:
            spec = self.backend.symbol_spec(pos.symbol)
            if pos.ticket not in self.virtual_states:
                # Discovered position on broker without local state -> attach protection immediately
                self.register_position(pos, spec)

            state = self.virtual_states[pos.ticket]
            tick = self.backend.get_tick(pos.symbol)
            if not tick or not spec:
                continue

            point = spec.point
            is_buy = pos.type.upper() == "BUY"
            current_price = tick.bid if is_buy else tick.ask

            # 2. Virtual Take Profit Hit
            if state.virtual_tp > 0:
                if is_buy and current_price >= state.virtual_tp:
                    actions_to_close.append(
                        (
                            pos,
                            f"Virtual TP Hit at {current_price:.5f} (Target {state.virtual_tp:.5f})",
                        )
                    )
                    continue
                elif not is_buy and current_price <= state.virtual_tp:
                    actions_to_close.append(
                        (
                            pos,
                            f"Virtual TP Hit at {current_price:.5f} (Target {state.virtual_tp:.5f})",
                        )
                    )
                    continue

            # 3. Virtual Stop Loss Hit
            if state.virtual_sl > 0:
                if is_buy and current_price <= state.virtual_sl:
                    actions_to_close.append(
                        (
                            pos,
                            f"Virtual SL Hit at {current_price:.5f} (Stop {state.virtual_sl:.5f})",
                        )
                    )
                    continue
                elif not is_buy and current_price >= state.virtual_sl:
                    actions_to_close.append(
                        (
                            pos,
                            f"Virtual SL Hit at {current_price:.5f} (Stop {state.virtual_sl:.5f})",
                        )
                    )
                    continue

            # 4. Dynamic Trailing Stop
            if self.settings.trailing_enabled:
                self._update_trailing_stop(pos, state, current_price, point)

        return actions_to_close

    def _update_trailing_stop(
        self,
        pos: Position,
        state: VirtualProtectionState,
        current_price: float,
        point: float,
    ) -> None:
        is_buy = pos.type.upper() == "BUY"
        spec = self.backend.symbol_spec(pos.symbol) if hasattr(self.backend, "symbol_spec") else None
        start_pts = self.adapt_points_to_symbol(pos.symbol, self.settings.trail_start_points, spec)
        step_pts = self.adapt_points_to_symbol(pos.symbol, self.settings.trail_step_points, spec)
        changed = False

        digits = spec.digits if spec else 5

        if is_buy:
            if current_price > state.highest_price:
                state.highest_price = round(current_price, digits)
                changed = True

            profit_points = (current_price - pos.price_open) / point
            if profit_points >= start_pts:
                # Trail only UPWARD to reduce risk
                new_sl = round(state.highest_price - (step_pts * point), digits)
                if new_sl > state.virtual_sl and new_sl > pos.price_open:
                    state.virtual_sl = new_sl
                    state.trailing_active = True
                    changed = True
                    logger.info(f"Trailing SL BUY #{pos.ticket} dinaikkan ke {new_sl:.5f}")
        else:
            if state.lowest_price == 0.0 or current_price < state.lowest_price:
                state.lowest_price = round(current_price, digits)
                changed = True

            profit_points = (pos.price_open - current_price) / point
            if profit_points >= start_pts:
                # Trail only DOWNWARD to reduce risk
                new_sl = round(state.lowest_price + (step_pts * point), digits)
                if (state.virtual_sl == 0.0 or new_sl < state.virtual_sl) and new_sl < pos.price_open:
                    state.virtual_sl = new_sl
                    state.trailing_active = True
                    changed = True
                    logger.info(f"Trailing SL SELL #{pos.ticket} diturunkan ke {new_sl:.5f}")

        # Sync update to disk
        if changed:
            self.state_store.set_virtual_protection(
                PersistedVirtualProtection(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    side=pos.type.upper(),
                    price_open=pos.price_open,
                    virtual_sl=state.virtual_sl,
                    virtual_tp=state.virtual_tp,
                    trailing_active=state.trailing_active,
                    highest_price=state.highest_price,
                    lowest_price=state.lowest_price,
                )
            )
