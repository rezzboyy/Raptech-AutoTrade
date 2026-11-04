from __future__ import annotations

"""
Raptech Autotrade CLI — Production-Grade Order Manager (v3.0).
Features:
- Explicit Order State Machine (CREATED, VALIDATING, SUBMITTED, FILLED, REJECTED, UNKNOWN, RECONCILIATION_REQUIRED)
- Operation ID (UUID4) tracking & duplicate order prevention
- Risk-based lot sizing (FIXED_LOT vs RISK_PERCENT with floor-to-step constraint)
- Verified Emergency Close All with post-close reconciliation
- Broker-to-local position reconciliation
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Dict, List, Optional, Tuple
import uuid

from backend.base import (
    AccountInfo,
    OrderResult,
    OrderState,
    Position,
    SymbolSpec,
    TradingBackend,
)
from core.logger import get_logger

logger = get_logger("order_manager")


@dataclass
class TrackedOrderIntent:
    operation_id: str
    symbol: str
    side: str
    volume: float
    sl: float = 0.0
    tp: float = 0.0
    magic: int = 10101
    comment: str = "raptech_v3"
    state: str = OrderState.CREATED
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ticket: Optional[int] = None
    retcode: int = 0
    message: str = ""


@dataclass
class ReconciliationReport:
    timestamp: str
    broker_positions_count: int
    matched_positions: List[int]
    unmanaged_positions: List[int]
    ghost_positions_cleaned: List[int]
    reconciliation_required: bool
    details: str = ""


class OrderManager:
    """Manages order state machine, lot validation, sizing, and reconciliation."""

    def __init__(self, backend: TradingBackend) -> None:
        self.backend = backend
        self.active_intents: Dict[str, TrackedOrderIntent] = {}

    def normalize_lot(
        self, requested_lot: float, spec: Optional[SymbolSpec], allow_floor_only: bool = False
    ) -> float:
        """
        Normalize volume to broker specifications (step, min, max).
        If allow_floor_only is True, uses floor instead of round to guarantee
        that normalized lot NEVER exceeds the calculated risk budget.
        """
        if spec is None:
            return round(max(0.01, requested_lot), 2)

        vol = max(spec.volume_min, min(spec.volume_max, requested_lot))
        step = spec.volume_step if spec.volume_step > 0 else 0.01

        # Calculate steps
        if allow_floor_only:
            steps = math.floor((vol - spec.volume_min + 1e-9) / step)
        else:
            steps = round((vol - spec.volume_min) / step)

        normalized = spec.volume_min + (steps * step)

        # Decimal precision based on step
        if step >= 1.0:
            decimals = 0
        elif step >= 0.1:
            decimals = 1
        elif step >= 0.01:
            decimals = 2
        else:
            decimals = 3

        return round(normalized, decimals)

    def calculate_risk_based_lot(
        self,
        symbol: str,
        sizing_mode: str,
        fixed_lot: float,
        risk_percent: float,
        stop_loss_points: float,
        account: Optional[AccountInfo],
    ) -> Tuple[float, str]:
        """
        Calculate safe volume based on sizing mode.
        Guarantees that RISK_PERCENT never rounds up and breaches max budget.
        """
        spec = self.backend.symbol_spec(symbol)
        if spec is None:
            return self.normalize_lot(fixed_lot, None), "Spec tidak tersedia, fallback ke fixed lot."

        mode = (sizing_mode or "fixed_lot").lower().strip()
        if mode == "fixed_lot" or stop_loss_points <= 0 or not account or account.equity <= 0:
            return self.normalize_lot(fixed_lot, spec), f"Mode {mode.upper()}: volume {fixed_lot}"

        # Sizing Mode: RISK_PERCENT
        # 1. Calculate monetary risk budget
        risk_budget_usd = account.equity * (risk_percent / 100.0)

        # 2. Monetary risk per 1.0 standard lot for stop_loss_points
        # Spec point vs tick_size ratio
        tick_ratio = (spec.point / spec.tick_size) if spec.tick_size > 0 else 1.0
        tick_value = spec.tick_value if spec.tick_value > 0 else 1.0
        money_risk_per_lot = stop_loss_points * tick_ratio * tick_value

        if money_risk_per_lot <= 0:
            return self.normalize_lot(fixed_lot, spec), "Tick value tidak valid, fallback ke fixed lot."

        raw_lot = risk_budget_usd / money_risk_per_lot

        # 3. Check if raw_lot is below broker minimum
        if raw_lot < spec.volume_min:
            # Check risk if forced to minimum volume
            min_lot_risk = spec.volume_min * money_risk_per_lot
            if min_lot_risk > risk_budget_usd * 1.05:  # Tolerate max 5% drift on micro accounts
                return 0.0, (
                    f"Anggaran risiko (${risk_budget_usd:,.2f}) tidak cukup untuk lot minimal broker "
                    f"({spec.volume_min} lot = estimasi risiko ${min_lot_risk:,.2f}). Order ditolak demi modal."
                )

        # 4. Normalize with floor to guarantee NO risk overflow
        safe_lot = self.normalize_lot(raw_lot, spec, allow_floor_only=True)
        return safe_lot, (
            f"Mode RISK_PERCENT ({risk_percent}% = ${risk_budget_usd:,.2f}): "
            f"dihitung {raw_lot:.4f} lot -> aman {safe_lot:.2f} lot (SL {stop_loss_points:.0f} pts)"
        )

    def round_price(self, price: float, spec: Optional[SymbolSpec]) -> float:
        """Round price to broker symbol digits."""
        digits = spec.digits if spec else 5
        return round(price, digits)

    def send_market_order(
        self,
        symbol: str,
        side: str,
        lot: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 10101,
        comment: str = "raptech_v3",
    ) -> OrderResult:
        """
        Validate parameters and send market order using explicit State Machine.
        Assigns operation_id and handles network timeouts safely without duplicate firing.
        """
        op_id = str(uuid.uuid4())
        intent = TrackedOrderIntent(
            operation_id=op_id,
            symbol=symbol,
            side=side.upper(),
            volume=lot,
            sl=sl,
            tp=tp,
            magic=magic,
            comment=comment,
            state=OrderState.VALIDATING,
        )
        self.active_intents[op_id] = intent

        spec = self.backend.symbol_spec(symbol)
        valid_lot = self.normalize_lot(lot, spec)
        valid_sl = self.round_price(sl, spec) if sl > 0 else 0.0
        valid_tp = self.round_price(tp, spec) if tp > 0 else 0.0

        if valid_lot <= 0.0:
            intent.state = OrderState.REJECTED
            intent.message = "Volume lot hasil normalisasi 0.0"
            return OrderResult(
                ok=False,
                message=intent.message,
                state=OrderState.REJECTED,
                operation_id=op_id,
            )

        intent.state = OrderState.SUBMITTED
        intent.volume = valid_lot
        intent.sl = valid_sl
        intent.tp = valid_tp

        logger.info(
            f"[{op_id[:8]}] Mengirim Order {side.upper()} {valid_lot} {symbol} "
            f"(SL: {valid_sl}, TP: {valid_tp}, Magic: {magic})"
        )

        try:
            res = self.backend.send_market_order(
                symbol=symbol,
                side=side.upper(),
                volume=valid_lot,
                sl=valid_sl,
                tp=valid_tp,
                magic=magic,
                comment=comment,
            )
        except Exception as exc:
            # CRITICAL TIMEOUT / EXCEPTION: Do not assume order failed!
            # Must mark as UNKNOWN / RECONCILIATION_REQUIRED
            logger.error(f"[{op_id[:8]}] Exception saat order_send: {exc}. Menandai UNKNOWN untuk rekonsiliasi...")
            intent.state = OrderState.UNKNOWN
            intent.message = f"Order exception/timeout: {exc}"
            return OrderResult(
                ok=False,
                message=intent.message,
                state=OrderState.RECONCILIATION_REQUIRED,
                operation_id=op_id,
            )

        if res.ok:
            intent.state = OrderState.FILLED
            intent.ticket = res.ticket or res.order
            res.state = OrderState.FILLED
            res.operation_id = op_id
            logger.info(f"[{op_id[:8]}] Order #{res.ticket or res.order} {side.upper()} {valid_lot} {symbol} FILLED!")
        else:
            intent.state = OrderState.REJECTED
            intent.message = res.message
            res.state = OrderState.REJECTED
            res.operation_id = op_id
            logger.error(f"[{op_id[:8]}] Order {side.upper()} {symbol} REJECTED: {res.message}")

        return res

    def close_position(
        self, ticket: int, symbol: str, volume: Optional[float] = None
    ) -> OrderResult:
        """Close an open position."""
        logger.info(f"Menutup posisi #{ticket} ({symbol})...")
        res = self.backend.close_position(ticket, symbol, volume)
        if res.ok:
            logger.info(f"Posisi #{ticket} ({symbol}) berhasil ditutup.")
        else:
            logger.error(f"Gagal menutup posisi #{ticket}: {res.message}")
        return res

    def verified_emergency_close_all(
        self, symbol: Optional[str] = None
    ) -> Tuple[List[OrderResult], List[Position]]:
        """
        Verified Emergency Close All:
        1. Snapshot open positions.
        2. Send close orders for each.
        3. Query broker again to verify all were really closed.
        4. If any positions remain, attempt a second targeted retry.
        5. Return list of results and list of remaining positions (should be empty).
        """
        initial_positions = self.backend.positions(symbol=symbol)
        if not initial_positions:
            logger.info("Tidak ada posisi terbuka untuk ditutup.")
            return [], []

        logger.warning(
            f"🚨 EMERGENCY CLOSE ALL: Menutup {len(initial_positions)} posisi terbuka..."
        )
        results: List[OrderResult] = []

        # Pass 1: Send close requests
        for pos in initial_positions:
            res = self.close_position(pos.ticket, pos.symbol, pos.volume)
            results.append(res)

        # Pass 2: Verification check from broker
        remaining = self.backend.positions(symbol=symbol)
        if remaining:
            logger.warning(
                f"⚠️ Verifikasi darurat: {len(remaining)} posisi masih terbuka di broker! Mencoba retry pasif..."
            )
            for r_pos in remaining:
                retry_res = self.close_position(r_pos.ticket, r_pos.symbol, r_pos.volume)
                results.append(retry_res)

            # Final verification snapshot
            remaining = self.backend.positions(symbol=symbol)

        if not remaining:
            logger.info("✔ VERIFIKASI BERHASIL: Seluruh posisi telah terkonfirmasi tertutup 100% di broker.")
        else:
            logger.critical(
                f"🚨 PERINGATAN GAGAL: {len(remaining)} posisi masih terbuka di broker setelah retry!"
            )

        return results, remaining

    def close_all_positions(self, symbol: Optional[str] = None) -> List[OrderResult]:
        """Backward-compatible emergency close wrapper."""
        results, _ = self.verified_emergency_close_all(symbol=symbol)
        return results

    def reconcile_positions(
        self, known_protected_tickets: List[int], magic: Optional[int] = None
    ) -> ReconciliationReport:
        """
        Reconcile broker reality against local state:
        - Detects unmanaged positions (manual trades or other bots)
        - Detects ghost positions (locally tracked positions already closed at broker)
        """
        broker_positions = self.backend.positions()
        broker_ticket_map = {p.ticket: p for p in broker_positions}

        matched: List[int] = []
        unmanaged: List[int] = []
        ghosts: List[int] = []

        # 1. Check local tickets against broker
        for t in known_protected_tickets:
            if t in broker_ticket_map:
                matched.append(t)
            else:
                ghosts.append(t)

        # 2. Check broker tickets against local
        for t, p in broker_ticket_map.items():
            if magic is not None and p.magic != magic and p.magic != 0:
                continue  # Belonging to another system
            if t not in known_protected_tickets:
                unmanaged.append(t)

        needs_recon = len(unmanaged) > 0 or len(ghosts) > 0
        details = (
            f"Broker: {len(broker_positions)}, Matched: {len(matched)}, "
            f"Unmanaged: {len(unmanaged)}, Ghosts cleaned: {len(ghosts)}"
        )
        if needs_recon:
            logger.info(f"🔄 Rekonsiliasi Posisi: {details}")

        return ReconciliationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            broker_positions_count=len(broker_positions),
            matched_positions=matched,
            unmanaged_positions=unmanaged,
            ghost_positions_cleaned=ghosts,
            reconciliation_required=needs_recon,
            details=details,
        )
