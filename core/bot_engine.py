from __future__ import annotations

"""
Raptech Autotrade CLI — Production-Grade Trading Bot Engine (v3.0).
Key Reliability Features:
1. Anti-lookahead & Closed Bar Confirmation (No intrabar flickering)
2. Risk-Based Position Sizing (Fixed Lot vs Risk Percent)
3. Dual-Layer Protection Dispatch (Broker Hard SL + Local Virtual SL/TP)
4. Periodic Broker Reconciliation & Crash Recovery
5. Signal Cooldown & Exposure Safeguards
"""

import asyncio
from datetime import datetime
import time
from typing import Callable, Dict, List, Optional

from backend.base import AccountInfo, Candle, Position, TradingBackend
from core.config_store import AccountProfile
from core.logger import get_logger
from core.order_manager import OrderManager
from core.risk_manager import RiskManager
from core.state_store import StateStore
from strategies import SIGNAL_BUY, SIGNAL_SELL, Strategy, get_registry

logger = get_logger("bot_engine")


class BotEngine:
    """Core Trading Engine running the strategy evaluation and protection loop."""

    def __init__(
        self,
        backend: TradingBackend,
        profile: AccountProfile,
        on_log: Optional[Callable[[str], None]] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        self.backend = backend
        self.profile = profile
        self.on_log = on_log
        self.state_store = state_store or StateStore()

        # Instantiate strategy first
        registry = get_registry()
        strat_key = getattr(profile, "strategy", "") or "pa_hybrid"
        strat_cls = registry.get(strat_key, registry.get("pa_hybrid", registry.get("fast_gold_scalper")))
        strat_params = getattr(profile, "strategy_params", {}) or {}
        if strat_cls:
            self._strategy: Strategy = strat_cls(**strat_params)
        else:
            from strategies.fast_gold_scalper import FastGoldScalper
            self._strategy = FastGoldScalper(**strat_params)

        # Sinkronisasi pengaturan risiko bawaan strategi (max_daily_loss, max_open_positions, dll)
        strat_risk = self._strategy.get_risk_settings() if hasattr(self._strategy, "get_risk_settings") else None
        if strat_risk and hasattr(profile, "risk") and profile.risk:
            for attr in (
                "max_open_positions", "max_daily_loss", "virtual_sl_points", "virtual_tp_points",
                "trailing_enabled", "trail_start_points", "trail_step_points",
                "fixed_lot", "risk_percent", "sizing_mode"
            ):
                if hasattr(strat_risk, attr):
                    val = getattr(strat_risk, attr)
                    if val is not None:
                        setattr(profile.risk, attr, val)
            effective_risk = profile.risk
        else:
            effective_risk = strat_risk or getattr(profile, "risk", None)

        self.order_manager = OrderManager(backend)
        self.risk_manager = RiskManager(backend, effective_risk, self.state_store)
        self.auto_trading_enabled = False
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Anti-flicker / Closed bar confirmation tracking
        self._last_bar_time: Dict[str, datetime] = {}
        self._last_entry_time: Dict[str, float] = {}
        self._last_reconcile_time: float = 0.0
        self._last_logged_time: Dict[str, float] = {}

    @property
    def strategy(self) -> Strategy:
        return self._strategy

    @strategy.setter
    def strategy(self, new_strategy: Strategy) -> None:
        self.set_strategy(new_strategy)

    @property
    def current_symbols(self) -> List[str]:
        if getattr(self.profile, "symbols", None):
            return self.profile.symbols
        if hasattr(self.strategy, "symbols") and self.strategy.symbols:
            return self.strategy.symbols
        if hasattr(self.strategy, "recommended_symbols") and self.strategy.recommended_symbols:
            return self.strategy.recommended_symbols
        return ["XAUUSDm", "EURUSDm", "BTCUSDm"]

    @property
    def current_timeframe(self) -> str:
        if getattr(self.profile, "timeframe", ""):
            return self.profile.timeframe
        return getattr(self.strategy, "recommended_timeframe", "M1")

    @property
    def allow_hedging(self) -> bool:
        if hasattr(self.strategy, "allow_hedging"):
            return self.strategy.allow_hedging
        return getattr(self.profile, "allow_hedging", False)

    @property
    def close_on_opposite_signal(self) -> bool:
        if hasattr(self.strategy, "close_on_opposite_signal"):
            return self.strategy.close_on_opposite_signal
        return getattr(self.profile, "close_on_opposite_signal", True)

    def set_strategy(self, strategy: Strategy) -> None:
        self._strategy = strategy
        if hasattr(strategy, "get_risk_settings"):
            strat_risk = strategy.get_risk_settings()
            if strat_risk and hasattr(self.profile, "risk") and self.profile.risk:
                for attr in (
                    "max_open_positions", "virtual_sl_points", "virtual_tp_points",
                    "trailing_enabled", "trail_start_points", "trail_step_points",
                    "max_daily_loss", "max_drawdown_percent", "min_margin_level",
                    "max_symbol_exposure_lots", "fixed_lot", "risk_percent", "sizing_mode"
                ):
                    if hasattr(strat_risk, attr):
                        setattr(self.profile.risk, attr, getattr(strat_risk, attr))
                self.risk_manager.settings = self.profile.risk
            elif strat_risk:
                self.risk_manager.settings = strat_risk
        elif hasattr(self.profile, "risk") and self.profile.risk:
            self.risk_manager.settings = self.profile.risk

        if hasattr(self, "risk_manager") and hasattr(self.risk_manager, "settings"):
            r = self.risk_manager.settings
            self.log(
                f"⚡ Sinkronisasi Risiko [{strategy.display_name}]: Max Loss ${r.max_daily_loss:,.1f} | Max Pos: {r.max_open_positions} | Lot: {r.fixed_lot}"
            )

    def log(self, msg: str) -> None:
        now = time.time()
        # Deduplicate warnings and rejection notices within 15 seconds to prevent log flooding
        if any(w in msg for w in ("Menolak Entry", "⚠️", "Batas maksimum", "diabaikan")):
            last_t = self._last_logged_time.get(msg, 0.0)
            if now - last_t < 15.0:
                return
            self._last_logged_time[msg] = now
            if len(self._last_logged_time) > 200:
                self._last_logged_time.clear()

        logger.info(msg)
        if self.on_log:
            try:
                self.on_log(msg)
            except Exception:
                pass

    def start_auto_trading(self) -> None:
        # Check if date has changed to allow daily circuit breaker auto-reset
        acc = self.backend.account_info() if hasattr(self.backend, "account_info") else None
        if acc and acc.balance > 0:
            self.risk_manager.reset_daily_metrics_if_new_day(acc.balance, acc.equity)

        # Check circuit breaker before allowing auto trading
        if self.risk_manager.circuit_breaker_tripped:
            self.log(
                f"🚨 AUTO TRADING DITOLAK: Circuit Breaker Terkunci! ({self.risk_manager.circuit_breaker_reason})"
            )
            return
        self.auto_trading_enabled = True
        self.log(f"● AUTO TRADING DIAKTIFKAN [Strategi: {self.strategy.display_name}]")

        # Notify strategy timeframe compatibility
        rec_tf = getattr(self.strategy, "recommended_timeframe", "")
        if rec_tf and self.current_timeframe.upper() != rec_tf.upper():
            self.log(
                f"ℹ️ Optimasi Strategi: {self.strategy.display_name} disarankan di {rec_tf} (saat ini: {self.current_timeframe})"
            )

    def stop_auto_trading(self) -> None:
        self.auto_trading_enabled = False
        self.log("● AUTO TRADING DIHENTIKAN")

    async def run_loop(self, poll_interval: float = 1.0) -> None:
        """Main async bot loop."""
        self._running = True
        self.log(
            f"Bot Engine v3.1.0 dimulai. Monitoring: {', '.join(self.current_symbols)} ({self.current_timeframe})"
        )

        # Initial startup broker reconciliation
        try:
            report = await asyncio.to_thread(
                self.order_manager.reconcile_positions,
                list(self.risk_manager.virtual_states.keys()),
            )
            self.log(f"🔄 Status Rekonsiliasi Awal: {report.details}")
        except Exception as exc:
            logger.error(f"Error rekonsiliasi awal: {exc}")

        while self._running:
            try:
                await self.tick_step()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error pada loop tick: {exc}")

            await asyncio.sleep(poll_interval)

        self.log("Bot Engine loop selesai.")

    async def tick_step(self) -> None:
        """Single tick step execution."""
        # 1. Fetch current broker positions
        positions = await asyncio.to_thread(self.backend.positions)

        # 2. Virtual SL/TP & Trailing Stop Protections (Always active for capital safety)
        actions = self.risk_manager.evaluate_virtual_protections(positions)
        for pos, reason in actions:
            self.log(f"PROTEKSI: Menutup #{pos.ticket} {pos.symbol} - Alasan: {reason}")
            await asyncio.to_thread(
                self.order_manager.close_position, pos.ticket, pos.symbol
            )

        # 3. Periodic Broker Reconciliation (every 15 seconds)
        now = time.time()
        if now - self._last_reconcile_time > 15.0:
            self._last_reconcile_time = now
            report = await asyncio.to_thread(
                self.order_manager.reconcile_positions,
                list(self.risk_manager.virtual_states.keys()),
            )
            if report.reconciliation_required:
                self.log(f"🔄 Rekonsiliasi Rutin: {report.details}")

        # 4. Strategy evaluation & order opening (Only if auto_trading is ON)
        if not self.auto_trading_enabled:
            return

        account = await asyncio.to_thread(self.backend.account_info)
        if not account or account.equity <= 0:
            return

        # Synchronize daily baseline and auto-reset circuit breaker on date rollover
        self.risk_manager.reset_daily_metrics_if_new_day(account.balance, account.equity)

        # Double check circuit breaker lock
        if self.risk_manager.circuit_breaker_tripped:
            self.auto_trading_enabled = False
            self.log(
                f"🚨 AUTO TRADING DIKUNCI: Circuit Breaker aktif ({self.risk_manager.circuit_breaker_reason})"
            )
            return

        for symbol in self.current_symbols:
            spec = await asyncio.to_thread(self.backend.symbol_spec, symbol)
            if not spec:
                continue

            # Fetch candles for symbol
            candles = await asyncio.to_thread(
                self.backend.get_candles, symbol, self.current_timeframe, 150
            )
            if len(candles) < 25:
                continue

            # Anti-flicker / Closed bar confirmation:
            # We strictly evaluate confirmed closed bar (candles[-2]) to prevent intrabar repainting!
            confirmed_closed_bar = candles[-2]
            last_seen_time = self._last_bar_time.get(symbol)
            if last_seen_time == confirmed_closed_bar.time:
                # Already evaluated on this closed candle, skip until next bar closes
                continue

            # Pass strictly confirmed closed candles to strategy so indicators compute on closed bars
            confirmed_candles = candles[:-1] if len(candles) > 1 else candles
            signal = self.strategy.generate_signal(confirmed_candles)

            if signal not in (SIGNAL_BUY, SIGNAL_SELL):
                self._last_bar_time[symbol] = confirmed_closed_bar.time
                continue

            # Existing active positions on this symbol
            sym_positions = [p for p in positions if p.symbol == symbol]
            has_same_direction = any(p.type == signal for p in sym_positions)
            opposing_positions = [p for p in sym_positions if p.type != signal]

            # Rule 1: Prevent duplicate stacking in same direction (single active trade discipline per strategy)
            if not self.allow_hedging and has_same_direction:
                self._last_bar_time[symbol] = confirmed_closed_bar.time
                continue

            # Rule 2: Reversal signal handling (close opposite direction if configured)
            if self.close_on_opposite_signal and opposing_positions:
                for opp_pos in opposing_positions:
                    self.log(
                        f"🔄 REVERSAL [{self.strategy.display_name}]: Menutup #{opp_pos.ticket} {opp_pos.type} "
                        f"pada {symbol} karena sinyal berbalik ke {signal}"
                    )
                    await asyncio.to_thread(
                        self.order_manager.close_position, opp_pos.ticket, symbol
                    )
                    self.risk_manager.unregister_position(opp_pos.ticket)
                # Refresh positions after closing opposite
                positions = await asyncio.to_thread(self.backend.positions)

            # Check entry cooldown (minimum 10 seconds between trades on same symbol)
            last_entry = self._last_entry_time.get(symbol, 0.0)
            if now - last_entry < 10.0:
                self._last_bar_time[symbol] = confirmed_closed_bar.time
                continue

            # SL & TP points: Use strategy defaults first, fallback to profile only if strategy doesn't set it
            raw_sl = getattr(self.strategy, "default_sl_points", 0)
            if raw_sl <= 0:
                raw_sl = self.profile.risk.virtual_sl_points

            raw_tp = getattr(self.strategy, "default_tp_points", 0)
            if raw_tp <= 0:
                raw_tp = self.profile.risk.virtual_tp_points

            # Adapt points to symbol for sizing and execution
            sl_pts = self.risk_manager.adapt_points_to_symbol(symbol, raw_sl, spec)
            tp_pts = self.risk_manager.adapt_tp_points(symbol, raw_tp, sl_pts, spec)

            # Calculate risk-based lot sizing (Fixed Lot vs Risk Percent)
            sizing_mode = getattr(self.strategy, "sizing_mode", getattr(self.profile.risk, "sizing_mode", "fixed_lot"))
            fixed_lot = getattr(self.strategy, "fixed_lot", getattr(self.profile.risk, "fixed_lot", 0.01))
            risk_percent = getattr(self.strategy, "risk_percent", getattr(self.profile.risk, "risk_percent", 1.0))

            target_lot, sizing_info = self.order_manager.calculate_risk_based_lot(
                symbol=symbol,
                sizing_mode=sizing_mode,
                fixed_lot=fixed_lot,
                risk_percent=risk_percent,
                stop_loss_points=float(sl_pts),
                account=account,
            )

            if target_lot <= 0.0:
                self.log(f"⚠️ Sinyal {signal} {symbol} diabaikan: {sizing_info}")
                self._last_bar_time[symbol] = confirmed_closed_bar.time
                continue

            # Check pre-trade risk with the ACTUAL side and symbol-adapted SL
            allowed, risk_reason = self.risk_manager.check_pre_trade_risk(
                symbol=symbol,
                side=signal,
                volume=target_lot,
                account=account,
                current_positions=positions,
                sl_points=sl_pts,
            )
            if not allowed:
                self.log(f"Proteksi Risiko Menolak Entry {signal} {symbol}: {risk_reason}")
                self._last_bar_time[symbol] = confirmed_closed_bar.time
                continue

            self._last_bar_time[symbol] = confirmed_closed_bar.time
            self._last_entry_time[symbol] = now
            self.log(
                f"Sinyal {signal} [{self.strategy.display_name}] terkonfirmasi pada {symbol} ({self.current_timeframe}) • {sizing_info}"
            )

            # Calculate optional Server-Side Hard SL / TP
            tick = await asyncio.to_thread(self.backend.get_tick, symbol)
            if tick:
                entry_ref = tick.ask if signal == SIGNAL_BUY else tick.bid
            else:
                entry_ref = confirmed_closed_bar.close if confirmed_closed_bar else 0.0
            server_sl, server_tp = self.risk_manager.calculate_server_sl_tp(
                side=signal,
                price_open=entry_ref,
                spec=spec,
                symbol=symbol,
                sl_points=sl_pts,
                tp_points=tp_pts,
            )

            res = await asyncio.to_thread(
                self.order_manager.send_market_order,
                symbol=symbol,
                side=signal,
                lot=target_lot,
                sl=server_sl,
                tp=server_tp,
            )

            if res.ok:
                ticket_id = res.ticket or res.order or 0
                self.log(
                    f"✅ Order #{ticket_id} {signal} {target_lot} {symbol} FILLED! (Server SL: {server_sl})"
                )

                # Immediately register virtual SL/TP protection
                new_pos = Position(
                    ticket=ticket_id,
                    symbol=symbol,
                    type=signal,
                    volume=target_lot,
                    price_open=res.price or entry_ref,
                    price_current=res.price or entry_ref,
                    sl=server_sl,
                    tp=server_tp,
                )
                self.risk_manager.register_position(
                    new_pos, spec, sl_points=sl_pts, tp_points=tp_pts
                )

                # Refresh positions list for subsequent symbols in this loop
                positions = await asyncio.to_thread(self.backend.positions)
            else:
                self.log(f"❌ Order {signal} {symbol} Gagal: {res.message}")

    def stop(self) -> None:
        self._running = False
        self.auto_trading_enabled = False
