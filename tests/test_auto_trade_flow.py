from __future__ import annotations

"""Unit tests for Strategy Auto-Trading Flow, Parameters, and Position Lifecycle."""

import asyncio
from datetime import datetime, timedelta, timezone
import pytest

from backend.base import AccountInfo, Candle, OrderResult, Position, SymbolSpec, Tick
from core.bot_engine import BotEngine
from core.config_store import AccountProfile, RiskSettings
from core.state_store import StateStore
from strategies import BrutalCentScalper, FastGoldScalper, MACross, RSIReversal


class MockBackendForFlow:
    def __init__(self):
        self._positions = []
        self._sent_orders = []
        self._closed_positions = []
        self.tick_map = {
            "XAUUSDm": Tick(bid=2735.0, ask=2735.2, time=datetime.now(timezone.utc)),
            "EURUSDm": Tick(bid=1.0850, ask=1.0851, time=datetime.now(timezone.utc)),
        }

    def account_info(self):
        return AccountInfo(
            login=998877,
            server="Exness-Real1",
            currency="USD",
            balance=1000.0,
            equity=1000.0,
            margin=0.0,
            free_margin=1000.0,
            account_type="REAL",
        )

    def symbol_spec(self, symbol: str):
        return SymbolSpec(
            symbol=symbol,
            digits=2 if "XAU" in symbol else 5,
            point=0.01 if "XAU" in symbol else 0.00001,
            volume_min=0.01,
            volume_max=10.0,
            volume_step=0.01,
        )

    def get_tick(self, symbol: str):
        return self.tick_map.get(symbol)

    def positions(self, symbol=None):
        closed_tickets = {c[0] for c in self._closed_positions}
        active = [p for p in self._positions if p.ticket not in closed_tickets]
        if symbol:
            return [p for p in active if p.symbol == symbol]
        return active

    def send_market_order(self, symbol, side, volume=0.01, sl=0.0, tp=0.0, **kwargs):
        lot = volume
        ticket = 1000 + len(self._sent_orders) + 1
        pos = Position(
            ticket=ticket,
            symbol=symbol,
            type=side,
            volume=lot,
            price_open=2735.0,
            price_current=2735.0,
            sl=sl,
            tp=tp,
        )
        self._positions.append(pos)
        self._sent_orders.append((symbol, side, lot, sl, tp))
        return OrderResult(ok=True, ticket=ticket, price=2735.0, volume=lot, message="ok")

    def close_position(self, ticket, symbol, volume=None):
        self._closed_positions.append((ticket, symbol, volume))
        return OrderResult(ok=True, ticket=ticket, message="closed")

    def get_candles(self, symbol, timeframe, count):
        # Generate 50 candles with upward cross at the end
        now = datetime.now(timezone.utc)
        candles = []
        base = 2700.0
        for i in range(count):
            p = base + (i * 0.5)
            candles.append(
                Candle(
                    time=now + timedelta(minutes=i * 5),
                    open=p,
                    high=p + 0.8,
                    low=p - 0.8,
                    close=p + 0.3,
                    tick_volume=100,
                )
            )
        return candles


def test_strategy_metadata_and_recommendations():
    gold = FastGoldScalper()
    assert gold.recommended_timeframe == "M5"
    assert "XAUUSDm" in gold.recommended_symbols
    assert gold.default_sl_points == 200
    assert gold.default_tp_points == 400

    cent = BrutalCentScalper()
    assert cent.recommended_timeframe == "M1"
    assert "EURUSDm" in cent.recommended_symbols
    assert cent.default_sl_points == 100
    assert cent.default_tp_points == 150

    ma = MACross()
    assert ma.recommended_timeframe == "M15"
    assert ma.default_sl_points == 300

    rsi_strat = RSIReversal()
    assert rsi_strat.recommended_timeframe == "M5"
    assert rsi_strat.default_sl_points == 250


def test_bot_engine_custom_strategy_params(tmp_path):
    prof = AccountProfile(
        strategy="fast_gold_scalper",
        strategy_params={"fast_ema": 5, "slow_ema": 15, "rsi_period": 9},
        symbols=["XAUUSDm"],
    )
    store = StateStore(tmp_path / "flow_state.json")
    be = MockBackendForFlow()
    bot = BotEngine(backend=be, profile=prof, state_store=store)

    assert bot.strategy.name == "fast_gold_scalper"
    assert getattr(bot.strategy, "fast_ema") == 5
    assert getattr(bot.strategy, "slow_ema") == 15
    assert getattr(bot.strategy, "rsi_period") == 9


@pytest.mark.asyncio
async def test_reversal_signal_closes_opposite_position(tmp_path):
    store = StateStore(tmp_path / "flow_state.json")
    be = MockBackendForFlow()

    # Pre-populate an existing BUY position
    existing_buy = Position(
        ticket=555,
        symbol="XAUUSDm",
        type="BUY",
        volume=0.01,
        price_open=2730.0,
        price_current=2735.0,
    )
    be._positions.append(existing_buy)

    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
        close_on_opposite_signal=True,
        allow_hedging=False,
    )
    bot = BotEngine(backend=be, profile=prof, state_store=store)
    bot.auto_trading_enabled = True

    # Mock strategy returning SELL (opposite of existing BUY)
    bot.strategy.generate_signal = lambda candles: "SELL"

    await bot.tick_step()

    # Reversal must have closed existing BUY ticket #555
    closed_tickets = [c[0] for c in be._closed_positions]
    assert 555 in closed_tickets


@pytest.mark.asyncio
async def test_same_direction_does_not_open_duplicate(tmp_path):
    store = StateStore(tmp_path / "flow_state.json")
    be = MockBackendForFlow()

    # Pre-populate an existing BUY position
    existing_buy = Position(
        ticket=666,
        symbol="XAUUSDm",
        type="BUY",
        volume=0.01,
        price_open=2730.0,
        price_current=2735.0,
    )
    be._positions.append(existing_buy)

    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
        allow_hedging=False,
    )
    bot = BotEngine(backend=be, profile=prof, state_store=store)
    bot.auto_trading_enabled = True

    # Strategy signals BUY again (same as existing)
    bot.strategy.generate_signal = lambda candles: "BUY"

    await bot.tick_step()

    # Should NOT have sent another market order (prevent duplicate overtrading)
    assert len(be._sent_orders) == 0


@pytest.mark.asyncio
async def test_strategy_switch_synchronizes_risk_settings(tmp_path):
    from strategies.pa_breakout import PABreakoutScalper
    store = StateStore(tmp_path / "flow_state.json")
    be = MockBackendForFlow()
    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
        risk=RiskSettings(max_open_positions=2),
    )
    bot = BotEngine(backend=be, profile=prof, state_store=store)
    assert bot.risk_manager.settings.max_open_positions == 2

    # Switch strategy to PA Breakout (which has max_open_positions = 3)
    bot.strategy = PABreakoutScalper()
    assert bot.risk_manager.settings.max_open_positions == 3
    assert prof.risk.max_open_positions == 3


@pytest.mark.asyncio
async def test_rejected_entry_updates_last_bar_time_and_does_not_spam(tmp_path):
    store = StateStore(tmp_path / "flow_state.json")
    be = MockBackendForFlow()

    # Pre-populate max open positions
    be._positions = [
        Position(ticket=101, symbol="EURUSDm", type="BUY", volume=0.01, price_open=1.08, price_current=1.08),
        Position(ticket=102, symbol="GBPUSDm", type="BUY", volume=0.01, price_open=1.33, price_current=1.33),
    ]

    captured_logs = []
    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
        risk=RiskSettings(max_open_positions=2),
    )
    bot = BotEngine(backend=be, profile=prof, state_store=store, on_log=lambda m: captured_logs.append(m))
    bot.auto_trading_enabled = True

    # Mock signal BUY on XAUUSDm
    bot.strategy.generate_signal = lambda candles: "BUY"

    # First tick: Should evaluate, get rejected by max_positions (2/2), and log ONCE
    await bot.tick_step()
    assert any("Batas maksimum posisi terbuka tercapai" in m for m in captured_logs)
    warn_count_step1 = sum(1 for m in captured_logs if "Batas maksimum posisi" in m)
    assert warn_count_step1 == 1
    assert "XAUUSDm" in bot._last_bar_time

    # Second tick on exact same candle: Must skip because bar already evaluated, NO DUPLICATE LOG!
    await bot.tick_step()
    warn_count_step2 = sum(1 for m in captured_logs if "Batas maksimum posisi" in m)
    assert warn_count_step2 == 1  # Still 1, zero spam!


@pytest.mark.asyncio
async def test_controller_start_stop_auto_trading(tmp_path):
    from core.controller import TradeController

    be = MockBackendForFlow()
    be.connect = lambda: True
    be.disconnect = lambda: True
    store = StateStore(tmp_path / "test_state.json")

    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
        auto_start=False,
    )
    ctrl = TradeController(profile=prof)
    ctrl.backend = be
    await ctrl.connect()

    assert ctrl.engine.auto_trading_enabled is False

    # Explicit start
    assert ctrl.start_auto_trading() is True
    assert ctrl.engine.auto_trading_enabled is True

    # Explicit stop
    assert ctrl.stop_auto_trading() is True
    assert ctrl.engine.auto_trading_enabled is False

    await ctrl.disconnect()


@pytest.mark.asyncio
async def test_controller_manual_order_registers_virtual_protection(tmp_path):
    from core.controller import TradeController

    be = MockBackendForFlow()
    be.connect = lambda: True
    be.disconnect = lambda: True
    store = StateStore(tmp_path / "test_state.json")

    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
    )
    ctrl = TradeController(profile=prof)
    ctrl.backend = be
    await ctrl.connect()

    res = await ctrl.send_manual_order("XAUUSDm", "BUY", 0.05, sl=2710.0, tp=2760.0)
    assert res.ok is True
    ticket = res.ticket

    # Verify position is immediately registered in risk manager
    assert ticket in ctrl.engine.risk_manager.virtual_states
    v_state = ctrl.engine.risk_manager.virtual_states[ticket]
    assert v_state.symbol == "XAUUSDm"
    assert v_state.side == "BUY"
    assert v_state.price_open == 2735.0

    await ctrl.disconnect()


@pytest.mark.asyncio
async def test_bot_engine_start_auto_trading_timeframe_log(tmp_path):
    be = MockBackendForFlow()
    store = StateStore(tmp_path / "test_state.json")
    captured_logs = []

    # Profile timeframe is empty string -> defaults to strategy timeframe (M5)
    prof = AccountProfile(
        strategy="fast_gold_scalper",
        symbols=["XAUUSDm"],
        timeframe="",
    )
    bot = BotEngine(backend=be, profile=prof, state_store=store, on_log=lambda m: captured_logs.append(m))
    bot.start_auto_trading()

    # Since current_timeframe is M5 (same as fast_gold_scalper recommendation),
    # it should NOT log an unnecessary warning with blank "(saat ini: )"
    assert not any("disarankan di" in m and "(saat ini: )" in m for m in captured_logs)


