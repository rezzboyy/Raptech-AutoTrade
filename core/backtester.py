from __future__ import annotations

"""
Raptech Autotrade CLI — Production-Grade Backtesting Engine (v3.0).
Provides realistic, reproducible historical simulation:
- Anti-lookahead bias (strict historical candle slicing)
- Spread, commission, and slippage simulation
- Virtual SL/TP and Dynamic Trailing Stop tracking
- Robust metrics calculation (Win Rate, Profit Factor, Expectancy, Max Drawdown)
- Safe zero-division & edge-case handling
"""

from dataclasses import dataclass, field
from datetime import datetime
import math
from typing import Dict, List, Optional, Tuple

from backend.base import Candle, SymbolSpec
from core.config_store import RiskSettings
from strategies import SIGNAL_BUY, SIGNAL_HOLD, SIGNAL_SELL, Strategy


@dataclass
class BacktestTrade:
    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # BUY | SELL
    lot: float
    entry_price: float
    exit_price: float
    pnl: float
    pnl_points: float
    exit_reason: str  # Virtual SL | Virtual TP | Trailing Stop | Signal Exit | End of Data
    holding_bars: int
    commission: float = 0.0


@dataclass
class BacktestMetrics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_percent: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    expectancy_per_trade: float = 0.0
    max_drawdown_dollars: float = 0.0
    max_drawdown_percent: float = 0.0
    avg_holding_bars: float = 0.0
    total_commission: float = 0.0
    trades: List[BacktestTrade] = field(default_factory=list)


class Backtester:
    """Modular historical strategy backtester without lookahead bias."""

    def __init__(
        self,
        strategy: Strategy,
        initial_balance: float = 1000.0,
        spread_points: float = 20.0,
        slippage_points: float = 5.0,
        commission_per_lot: float = 4.0,  # $4 per round-turn standard lot
        risk_settings: Optional[RiskSettings] = None,
        spec: Optional[SymbolSpec] = None,
    ) -> None:
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.spread_points = spread_points
        self.slippage_points = slippage_points
        self.commission_per_lot = commission_per_lot
        self.risk_settings = risk_settings or RiskSettings()
        self.spec = spec or SymbolSpec(
            symbol="XAUUSDm",
            digits=3,
            point=0.001,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            tick_value=1.0,
            tick_size=0.001,
        )

    def run(self, candles: List[Candle], symbol: str = "XAUUSDm") -> BacktestMetrics:
        """Run backtest simulation on historical candles."""
        if len(candles) < 30:
            return BacktestMetrics()

        point = self.spec.point if self.spec.point > 0 else 0.001
        tick_ratio = (self.spec.point / self.spec.tick_size) if self.spec.tick_size > 0 else 1.0
        tick_value = self.spec.tick_value if self.spec.tick_value > 0 else 1.0

        spread_offset = self.spread_points * point
        slip_offset = self.slippage_points * point

        balance = self.initial_balance
        equity = balance
        peak_equity = equity
        max_dd_dollars = 0.0
        max_dd_percent = 0.0

        closed_trades: List[BacktestTrade] = []

        # Current active trade state
        active_trade: Optional[Dict] = None

        # Minimum warmup bars before generating signals
        warmup = 25

        for i in range(warmup, len(candles)):
            # Strictly slice history up to candle i-1 to prevent LOOKAHEAD BIAS!
            history_slice = candles[:i]
            curr_bar = candles[i]
            prev_bar = candles[i - 1]

            # 1. Evaluate open trade exits against current bar prices
            if active_trade is not None:
                is_buy = active_trade["side"] == "BUY"
                trade_lot = active_trade["lot"]
                entry_price = active_trade["entry_price"]
                sl = active_trade["sl"]
                tp = active_trade["tp"]
                highest = active_trade["highest"]
                lowest = active_trade["lowest"]

                exit_triggered = False
                exit_price = 0.0
                exit_reason = ""

                # Track high-water marks for trailing stop
                if is_buy:
                    if curr_bar.high > highest:
                        highest = curr_bar.high
                        active_trade["highest"] = highest

                    # Update trailing stop
                    if self.risk_settings.trailing_enabled:
                        profit_pts = (curr_bar.high - entry_price) / point
                        if profit_pts >= self.risk_settings.trail_start_points:
                            new_sl = highest - (self.risk_settings.trail_step_points * point)
                            if new_sl > sl and new_sl > entry_price:
                                sl = new_sl
                                active_trade["sl"] = sl

                    # Check TP hit
                    if tp > 0 and curr_bar.high >= tp:
                        exit_triggered = True
                        exit_price = tp
                        exit_reason = "Virtual TP Hit"
                    # Check SL hit
                    elif sl > 0 and curr_bar.low <= sl:
                        exit_triggered = True
                        exit_price = sl
                        exit_reason = "Virtual SL / Trailing Stop"

                else:  # SELL
                    if lowest == 0.0 or curr_bar.low < lowest:
                        lowest = curr_bar.low
                        active_trade["lowest"] = lowest

                    # Update trailing stop
                    if self.risk_settings.trailing_enabled:
                        profit_pts = (entry_price - curr_bar.low) / point
                        if profit_pts >= self.risk_settings.trail_start_points:
                            new_sl = lowest + (self.risk_settings.trail_step_points * point)
                            if (sl == 0.0 or new_sl < sl) and new_sl < entry_price:
                                sl = new_sl
                                active_trade["sl"] = sl

                    # Check TP hit
                    if tp > 0 and curr_bar.low <= tp:
                        exit_triggered = True
                        exit_price = tp
                        exit_reason = "Virtual TP Hit"
                    # Check SL hit
                    elif sl > 0 and curr_bar.high >= sl:
                        exit_triggered = True
                        exit_price = sl
                        exit_reason = "Virtual SL / Trailing Stop"

                if exit_triggered:
                    # Apply slippage on exit
                    actual_exit = exit_price - slip_offset if is_buy else exit_price + slip_offset
                    pts_diff = (actual_exit - entry_price) / point if is_buy else (entry_price - actual_exit) / point
                    gross_pnl = pts_diff * tick_ratio * tick_value * trade_lot
                    comm = trade_lot * self.commission_per_lot
                    net_pnl = gross_pnl - comm

                    balance += net_pnl
                    equity = balance
                    if equity > peak_equity:
                        peak_equity = equity

                    dd_dol = peak_equity - equity
                    if dd_dol > max_dd_dollars:
                        max_dd_dollars = dd_dol
                    if peak_equity > 0:
                        dd_pct = (dd_dol / peak_equity) * 100.0
                        if dd_pct > max_dd_percent:
                            max_dd_percent = dd_pct

                    closed_trades.append(
                        BacktestTrade(
                            entry_time=active_trade["entry_time"],
                            exit_time=curr_bar.time,
                            symbol=symbol,
                            side=active_trade["side"],
                            lot=trade_lot,
                            entry_price=entry_price,
                            exit_price=actual_exit,
                            pnl=round(net_pnl, 2),
                            pnl_points=round(pts_diff, 1),
                            exit_reason=exit_reason,
                            holding_bars=i - active_trade["entry_bar_idx"],
                            commission=comm,
                        )
                    )
                    active_trade = None

            # 2. Evaluate Strategy Signal on confirmed closed slice
            if active_trade is None:
                signal = self.strategy.generate_signal(history_slice)
                if signal in (SIGNAL_BUY, SIGNAL_SELL):
                    is_buy = signal == SIGNAL_BUY
                    raw_entry = curr_bar.open
                    # Add spread on BUY entry & slippage
                    actual_entry = (raw_entry + spread_offset + slip_offset) if is_buy else (raw_entry - slip_offset)

                    # Calculate SL / TP
                    sl_pts = self.risk_settings.virtual_sl_points
                    tp_pts = self.risk_settings.virtual_tp_points

                    sl_price = 0.0
                    tp_price = 0.0
                    if sl_pts > 0:
                        sl_price = actual_entry - (sl_pts * point) if is_buy else actual_entry + (sl_pts * point)
                    if tp_pts > 0:
                        tp_price = actual_entry + (tp_pts * point) if is_buy else actual_entry - (tp_pts * point)

                    trade_lot = self.risk_settings.fixed_lot

                    active_trade = {
                        "side": signal,
                        "lot": trade_lot,
                        "entry_price": actual_entry,
                        "entry_time": curr_bar.time,
                        "entry_bar_idx": i,
                        "sl": sl_price,
                        "tp": tp_price,
                        "highest": actual_entry,
                        "lowest": actual_entry,
                    }

        # Close any lingering trade at end of data
        if active_trade is not None:
            last_bar = candles[-1]
            is_buy = active_trade["side"] == "BUY"
            exit_price = last_bar.close
            pts_diff = (exit_price - active_trade["entry_price"]) / point if is_buy else (active_trade["entry_price"] - exit_price) / point
            gross_pnl = pts_diff * tick_ratio * tick_value * active_trade["lot"]
            comm = active_trade["lot"] * self.commission_per_lot
            net_pnl = gross_pnl - comm
            balance += net_pnl

            closed_trades.append(
                BacktestTrade(
                    entry_time=active_trade["entry_time"],
                    exit_time=last_bar.time,
                    symbol=symbol,
                    side=active_trade["side"],
                    lot=active_trade["lot"],
                    entry_price=active_trade["entry_price"],
                    exit_price=exit_price,
                    pnl=round(net_pnl, 2),
                    pnl_points=round(pts_diff, 1),
                    exit_reason="End of Data",
                    holding_bars=len(candles) - 1 - active_trade["entry_bar_idx"],
                    commission=comm,
                )
            )

        # 3. Calculate Comprehensive Metrics
        return self._compute_metrics(closed_trades, max_dd_dollars, max_dd_percent)

    def _compute_metrics(
        self, trades: List[BacktestTrade], max_dd_dollars: float, max_dd_percent: float
    ) -> BacktestMetrics:
        """Compute statistical and risk metrics from closed trades."""
        if not trades:
            return BacktestMetrics()

        total = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total * 100.0) if total > 0 else 0.0

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        net_profit = sum(t.pnl for t in trades)

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0

        expectancy = (net_profit / total) if total > 0 else 0.0
        avg_holding = sum(t.holding_bars for t in trades) / total if total > 0 else 0.0
        total_comm = sum(t.commission for t in trades)

        return BacktestMetrics(
            total_trades=total,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate_percent=round(win_rate, 2),
            net_profit=round(net_profit, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            profit_factor=round(profit_factor, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            expectancy_per_trade=round(expectancy, 2),
            max_drawdown_dollars=round(max_dd_dollars, 2),
            max_drawdown_percent=round(max_dd_percent, 2),
            avg_holding_bars=round(avg_holding, 1),
            total_commission=round(total_comm, 2),
            trades=trades,
        )
