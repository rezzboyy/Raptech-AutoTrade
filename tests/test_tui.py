from __future__ import annotations

"""Unit tests for LightAutotradeApp terminal rendering and HUD."""

from datetime import datetime
import pytest
from rich.panel import Panel
from rich.console import Group

from backend.base import AccountInfo, Position, Tick
from core.config_store import AccountProfile, RiskSettings
from tui.light_app import LightAutotradeApp


def test_light_app_init():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    assert app.profile is not None
    assert app.controller is not None
    assert len(app.logs) == 0


def test_light_app_render_header():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    acc = AccountInfo(login=123456, server="Exness-Trial", balance=1000.0, equity=1050.0, margin=50.0, free_margin=1000.0, margin_level=2100.0, profit=50.0)
    telemetry = app.controller.get_telemetry()
    panel = app.render_header(acc, telemetry)
    assert isinstance(panel, Panel)


def test_light_app_render_market_watch():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    # Mock tick cache
    app._tick_cache["XAUUSDm"] = Tick(bid=2735.40, ask=2735.65, time=datetime.now())
    panel = app.render_market_watch()
    assert isinstance(panel, Panel)


def test_light_app_render_positions_empty():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    panel = app.render_positions_table([])
    assert isinstance(panel, Panel)


def test_light_app_render_positions_with_data():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    mock_pos = [
        Position(
            ticket=482910,
            symbol="XAUUSDm",
            type="BUY",
            volume=0.01,
            price_open=2735.40,
            price_current=2737.50,
            profit=21.0,
        )
    ]
    panel = app.render_positions_table(mock_pos)
    assert isinstance(panel, Panel)


def test_light_app_render_logs():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    app.add_log("Menghubungkan ke broker...")
    app.add_log("❌ Gagal terhubung ke broker.")
    app.add_log("Order #12345 Berhasil dibuka.")
    panel = app.render_logs()
    assert isinstance(panel, Panel)


def test_light_app_render_controls():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    panel = app.render_controls()
    assert isinstance(panel, Panel)


def test_light_app_render_ui():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    ui_group = app.render_ui()
    assert isinstance(ui_group, Group)


@pytest.mark.asyncio
async def test_light_app_menu_change_mode(monkeypatch):
    from unittest.mock import MagicMock
    from rich.prompt import Prompt

    app = LightAutotradeApp(profile_name="default_example", screen=False)
    # Simulate choosing '3' (SIMULASI)
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "3")

    await app._menu_change_mode()
    assert app.profile.trading_mode == "simulasi"
    assert app.controller is not None
    assert app.controller.profile.trading_mode == "simulasi"


@pytest.mark.asyncio
async def test_light_app_interactive_mode_menu(monkeypatch):
    from unittest.mock import MagicMock
    from rich.prompt import Prompt

    app = LightAutotradeApp(profile_name="default_example", screen=False)
    mock_live = MagicMock()
    # Simulate choosing '2' (DEMO)
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "2")

    await app.interactive_mode_menu(mock_live)
    mock_live.stop.assert_called_once()
    mock_live.start.assert_called_once()
    assert app.profile.trading_mode == "demo"


@pytest.mark.asyncio
async def test_light_app_apply_symbols(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config_store.PROFILES_DIR", tmp_path)
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    assert "BTCUSDm" in app.profile.symbols or len(app.profile.symbols) > 0

    await app._apply_symbols(["XAUUSDm", "EURUSDm"])
    assert app.profile.symbols == ["XAUUSDm", "EURUSDm"]
    assert app.controller.profile.symbols == ["XAUUSDm", "EURUSDm"]


@pytest.mark.asyncio
async def test_light_app_interactive_market_menu(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from rich.prompt import Prompt

    monkeypatch.setattr("core.config_store.PROFILES_DIR", tmp_path)
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    mock_live = MagicMock()

    # Sequence of prompts: first choose "1" (preset Emas), then choose "0" (exit menu)
    answers = iter(["1", "0"])
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: next(answers))

    await app.interactive_market_menu(mock_live)
    mock_live.stop.assert_called_once()
    mock_live.start.assert_called_once()
    assert app.profile.symbols == ["XAUUSDm", "XAGUSDm"]


def test_light_app_clean_strategy_display():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    app.profile.strategy = "Price Action Hybrid Scalper (M1)"
    clean = app.get_clean_strategy_display()
    assert not clean.endswith("(M1)")
    assert "Price Action Hybrid Scalper" in clean


def test_light_app_dual_view_rendering():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    # Test overview view
    app.active_view = "overview"
    overview_group = app.render_ui()
    assert isinstance(overview_group, Group)

    # Test live view
    app.active_view = "live"
    live_group = app.render_ui()
    assert isinstance(live_group, Group)


def test_light_app_render_tables_and_cards():
    app = LightAutotradeApp(profile_name="default_example", screen=False)
    acc = AccountInfo(login=123456, server="Exness-Trial", balance=5000.0, equity=5020.0, margin=20.0, free_margin=5000.0, margin_level=25000.0, profit=20.0)
    
    fin_cards = app.render_financial_cards(acc)
    assert fin_cards is not None

    radar_table = app.render_market_radar_table()
    assert isinstance(radar_table, Panel)

    rec_table = app.render_market_recommendations_table()
    assert isinstance(rec_table, Panel)


@pytest.mark.asyncio
async def test_light_app_interactive_start_wizard(monkeypatch):
    from unittest.mock import MagicMock
    from rich.prompt import Prompt

    app = LightAutotradeApp(profile_name="default_example", screen=False)
    app.controller.engine = MagicMock()
    app.controller.engine.auto_trading_enabled = False

    def fake_start():
        app.controller.engine.auto_trading_enabled = True

    app.controller.engine.start_auto_trading.side_effect = fake_start
    mock_live = MagicMock()
    # Choose "1" to start auto trading
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "1")

    await app.interactive_start_wizard(mock_live)
    mock_live.stop.assert_called_once()
    mock_live.start.assert_called_once()
    assert app.active_view == "live"
    assert app.controller.engine.auto_trading_enabled is True


@pytest.mark.asyncio
async def test_light_app_interactive_close_all(monkeypatch):
    from unittest.mock import MagicMock
    from rich.prompt import Prompt

    app = LightAutotradeApp(profile_name="default_example", screen=False)
    mock_live = MagicMock()
    # Confirm "Y"
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "Y")

    await app.interactive_close_all(mock_live)
    mock_live.stop.assert_called_once()
    mock_live.start.assert_called_once()


@pytest.mark.asyncio
async def test_light_app_interactive_close_single(monkeypatch):
    from unittest.mock import MagicMock
    from rich.prompt import Prompt

    app = LightAutotradeApp(profile_name="default_example", screen=False)
    mock_live = MagicMock()

    # Cancel with "0"
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "0")
    await app.interactive_close_single(mock_live)
    mock_live.stop.assert_called_once()
    mock_live.start.assert_called_once()



