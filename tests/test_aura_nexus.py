from __future__ import annotations

"""Unit tests for Aura Nexus (Enhanced) v1.20 Strategy Replica."""

from datetime import datetime, timedelta, timezone
import pytest

from backend.base import Candle, Position
from strategies import (
    SIGNAL_BUY,
    SIGNAL_SELL,
    get_registry,
)
from strategies.aura_nexus import (
    AuraNexusScalper,
    _calc_adx,
    _calc_atr,
    _calc_ema,
    _is_in_red_zone,
    _resample_to_m15,
)


def test_aura_nexus_registration_and_invariants():
    reg = get_registry()
    assert "aura_nexus" in reg
    strat = AuraNexusScalper()
    assert strat.name == "aura_nexus"
    assert strat.timeframe == "M1"
    assert strat.recommended_timeframe == "M1"
    assert "XAUUSDm" in strat.symbols
    assert strat.max_open_positions == 16
    assert strat.fixed_lot == 0.01
    assert strat.allow_hedging is True
    assert strat.trailing_enabled is False
    assert strat.default_tp_points == 100


def test_indicator_math_adx_and_ema():
    # Test EMA
    prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    emas = _calc_ema(prices, 3)
    assert emas[-1] is not None
    assert emas[-1] > emas[-2]

    # Test ATR
    highs = [10.0, 11.0, 12.0, 13.0]
    lows = [9.0, 10.0, 11.0, 12.0]
    closes = [9.5, 10.5, 11.5, 12.5]
    atrs = _calc_atr(highs, lows, closes, 3)
    assert atrs[-1] is not None
    assert atrs[-1] > 0.0

    # Test ADX on trending sequence
    t_highs = [100.0 + i * 2.0 + 0.5 for i in range(40)]
    t_lows = [100.0 + i * 2.0 - 0.5 for i in range(40)]
    t_closes = [100.0 + i * 2.0 for i in range(40)]
    adx_vals = _calc_adx(t_highs, t_lows, t_closes, 14)
    assert adx_vals[-1] is not None
    assert adx_vals[-1] > 20.0  # Strong trend


def test_candle_resampling_m1_to_m15():
    t0 = datetime(2026, 3, 24, 14, 0, 0, tzinfo=timezone.utc)
    m1_candles = []
    for i in range(30):
        t = t0 + timedelta(minutes=i)
        p = 2000.0 + i
        m1_candles.append(
            Candle(
                time=t,
                open=p,
                high=p + 1.0,
                low=p - 1.0,
                close=p + 0.5,
                tick_volume=50,
            )
        )

    m15_candles = _resample_to_m15(m1_candles)
    assert len(m15_candles) == 2
    # First 15 bars (14:00 to 14:14)
    assert m15_candles[0].time == datetime(2026, 3, 24, 14, 0, 0, tzinfo=timezone.utc)
    assert m15_candles[0].open == 2000.0
    # Second 15 bars (14:15 to 14:29)
    assert m15_candles[1].time == datetime(2026, 3, 24, 14, 15, 0, tzinfo=timezone.utc)


def test_red_zone_filter():
    # 22:30 is in Red Zone (22:00 - 03:00)
    t_red1 = datetime(2026, 3, 24, 22, 30, 0)
    assert _is_in_red_zone(t_red1, 22, 3) is True

    # 02:15 is in Red Zone
    t_red2 = datetime(2026, 3, 25, 2, 15, 0)
    assert _is_in_red_zone(t_red2, 22, 3) is True

    # 14:30 is NOT in Red Zone
    t_clear = datetime(2026, 3, 24, 14, 30, 0)
    assert _is_in_red_zone(t_clear, 22, 3) is False


def test_shared_basket_tp_calculation():
    strat = AuraNexusScalper(default_tp_points=100)
    # BUY basket with 4 layers at different entry prices (as in video)
    positions = [
        Position(ticket=2252, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=4425.56, price_current=4422.0),
        Position(ticket=2253, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=4424.55, price_current=4422.0),
        Position(ticket=2254, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=4423.55, price_current=4422.0),
        Position(ticket=2255, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=4422.54, price_current=4422.0),
    ]
    # Average open price = (4425.56 + 4424.55 + 4423.55 + 4422.54) / 4 = 4424.05
    # TP at 100 points (point = 0.01 for gold) -> 4424.05 + 1.00 = 4425.05
    basket_tp = strat.calculate_basket_tp(positions, symbol_point=0.01)
    assert round(basket_tp, 2) == round(4424.05 + 1.00, 2)


def test_generate_signal_buy_scenario():
    strat = AuraNexusScalper(
        m15_adx_threshold=15.0,
        enable_red_zone=0,  # Disable red zone for controlled signal test
    )
    t0 = datetime(2026, 3, 24, 14, 0, 0, tzinfo=timezone.utc)
    candles = []
    base_p = 2000.0

    # Create 35 candles with clear uptrend
    for i in range(34):
        p = base_p + (i * 0.5)
        candles.append(
            Candle(
                time=t0 + timedelta(minutes=i),
                open=p,
                high=p + 0.8,
                low=p - 0.2,
                close=p + 0.6,
                tick_volume=100,
            )
        )

    # 35th candle: Pullback that touches lower channel band and bounces up
    last_p = base_p + (34 * 0.5)
    candles.append(
        Candle(
            time=t0 + timedelta(minutes=34),
            open=last_p - 0.2,
            high=last_p + 0.5,
            low=last_p - 3.0,  # Deep lower wick touching lower band
            close=last_p + 0.3, # Bullish recovery
            tick_volume=150,
        )
    )

    sig = strat.generate_signal(candles)
    assert sig in (SIGNAL_BUY, None)

    hud = strat.get_hud_info()
    assert hud["ea_name"] == "AURA NEXUS"
    assert hud["version"] == "v1.20 | Tester"
    assert "BUY only" in hud["trend_bias"]


def test_aura_nexus_update_tick_telemetry():
    strat = AuraNexusScalper(max_ema_distance=70.0)
    strat.last_ema100_val = 2700.0

    # Test tick during Red Zone (23:00)
    t_red = datetime(2026, 3, 24, 23, 0, 0, tzinfo=timezone.utc)
    strat.update_tick_telemetry(current_price=2715.50, current_time=t_red)
    hud = strat.get_hud_info()
    assert "[BLOCKED]" in hud["red_zone"]
    assert "+15.50 / 70" in hud["ema_distance"]

    # Test tick outside Red Zone (15:00)
    t_open = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
    strat.update_tick_telemetry(current_price=2690.00, current_time=t_open)
    hud = strat.get_hud_info()
    assert "[OPEN]" in hud["red_zone"]
    assert "-10.00 / 70" in hud["ema_distance"]


def test_bot_engine_basket_tp_sync_and_grid_spacing(tmp_path):
    from unittest.mock import MagicMock
    from backend.base import SymbolSpec
    from core.bot_engine import BotEngine
    from core.config_store import AccountProfile
    from core.state_store import StateStore

    mock_backend = MagicMock()
    mock_backend.symbol_spec.return_value = SymbolSpec(
        symbol="XAUUSDm", digits=2, point=0.01, volume_min=0.01, volume_max=100.0,
        volume_step=0.01, tick_value=1.0, tick_size=0.01
    )

    prof = AccountProfile(strategy="aura_nexus")
    store = StateStore(tmp_path / "test_state1.json")
    engine = BotEngine(backend=mock_backend, profile=prof, state_store=store)

    # Buka 2 layer posisi BUY
    pos1 = Position(ticket=101, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2700.0, price_current=2699.0)
    pos2 = Position(ticket=102, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2698.0, price_current=2699.0)
    positions = [pos1, pos2]

    # Daftarkan ke risk manager
    engine.risk_manager.register_position(pos1, mock_backend.symbol_spec.return_value)
    engine.risk_manager.register_position(pos2, mock_backend.symbol_spec.return_value)

    # Sinkronkan Shared Basket TP
    actions = engine._sync_basket_protections(positions)
    assert len(actions) == 0  # Belum hit profit

    # Rata-rata open = (2700 + 2698)/2 = 2699.00
    # TP 100 points = +1.00 USD -> 2700.00
    expected_tp = 2700.00
    assert engine.risk_manager.virtual_states[101].virtual_tp == expected_tp
    assert engine.risk_manager.virtual_states[102].virtual_tp == expected_tp


def test_aura_nexus_initial_entry_with_m15_feed():
    strat = AuraNexusScalper(m15_adx_threshold=10.0, max_ema_distance=200.0, enable_red_zone=0)
    t0 = datetime(2026, 3, 24, 14, 0, 0, tzinfo=timezone.utc)
    
    # 30 M15 candles in uptrend
    m15_candles = [
        Candle(time=t0 + timedelta(minutes=15*i), open=2600.0 + i*2.0, high=2603.0 + i*2.0, low=2599.0 + i*2.0, close=2602.0 + i*2.0, tick_volume=200)
        for i in range(30)
    ]
    
    # 30 M1 candles
    m1_candles = [
        Candle(time=t0 + timedelta(minutes=i), open=2650.0 + i*0.2, high=2651.0 + i*0.2, low=2649.5 + i*0.2, close=2650.5 + i*0.2, tick_volume=100)
        for i in range(30)
    ]
    
    # Test initial entry when existing_positions is empty
    sig = strat.generate_signal(m1_candles, m15_candles=m15_candles, existing_positions=[])
    assert sig == SIGNAL_BUY
    assert "BUY only" in strat.get_hud_info()["trend_bias"]


@pytest.mark.asyncio
async def test_bot_engine_intrabar_dca_trigger(tmp_path):
    from unittest.mock import MagicMock
    from backend.base import SymbolSpec, Tick, OrderResult
    from core.bot_engine import BotEngine
    from core.config_store import AccountProfile
    from core.state_store import StateStore

    mock_backend = MagicMock()
    mock_backend.symbol_spec.return_value = SymbolSpec(
        symbol="XAUUSDm", digits=2, point=0.01, volume_min=0.01, volume_max=100.0,
        volume_step=0.01, tick_value=1.0, tick_size=0.01
    )
    mock_backend.get_candles.return_value = [
        Candle(time=datetime(2026, 3, 24, 14, i), open=2700.0, high=2701.0, low=2699.0, close=2700.5, tick_volume=100)
        for i in range(30)
    ]
    # Posisi awal BUY di 2700.0
    pos1 = Position(ticket=5001, symbol="XAUUSDm", type="BUY", volume=0.01, price_open=2700.0, price_current=2698.5)
    mock_backend.positions.return_value = [pos1]
    
    # Harga saat ini turun 150 poin (1.50 USD) menjadi 2698.50 -> memicu grid DCA (grid_step_points=100)
    mock_backend.get_tick.return_value = Tick(
        bid=2698.30,
        ask=2698.50,
        time=datetime(2026, 3, 24, 14, 30),
    )
    from backend.base import AccountInfo
    mock_backend.account_info.return_value = AccountInfo(
        login=12345, server="Demo", balance=1000.0, equity=1000.0, profit=0.0, margin=0.0, free_margin=1000.0, margin_level=9999.0, currency="USD"
    )
    mock_backend.send_order.return_value = OrderResult(ok=True, ticket=5002, price=2698.50, volume=0.01)

    prof = AccountProfile(strategy="aura_nexus")
    store = StateStore(tmp_path / "test_state2.json")
    engine = BotEngine(backend=mock_backend, profile=prof, state_store=store)
    engine.auto_trading_enabled = True
    engine.strategy.last_hud_info["trend_bias"] = "BUY only"
    engine.order_manager.send_market_order = MagicMock(
        return_value=OrderResult(ok=True, ticket=5002, price=2698.50, volume=0.01)
    )

    # Jalankan tick_step
    await engine.tick_step()
    
    # Pastikan order manager dipanggil untuk mengirim order DCA layer kedua
    assert engine.order_manager.send_market_order.called


