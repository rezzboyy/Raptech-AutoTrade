"""Test verifikasi branding dan nama aplikasi XAVIQ Trading Engine."""

import os
from pathlib import Path
import pytest


def test_main_qml_title():
    """Memastikan title jendela di main.qml adalah 'XAVIQ Trading Engine'."""
    main_qml = Path("ui/qml/main.qml").read_text(encoding="utf-8")
    assert 'title: "XAVIQ Trading Engine"' in main_qml


def test_splash_qml_text():
    """Memastikan teks judul di Splash.qml adalah 'XAVIQ Trading Engine'."""
    splash_qml = Path("ui/qml/Splash.qml").read_text(encoding="utf-8")
    assert 'text: "XAVIQ Trading Engine"' in splash_qml


def test_app_py_application_name():
    """Memastikan app.py mengonfigurasi ApplicationName 'XAVIQ Trading Engine'."""
    app_code = Path("app.py").read_text(encoding="utf-8")
    assert 'app.setApplicationName("XAVIQ Trading Engine")' in app_code
    assert 'app.setOrganizationName("XAVIQ")' in app_code


def test_mcp_client_info_name():
    """Memastikan mcp_client mengirimkan clientInfo name xaviq-trading-engine."""
    mcp_code = Path("src/mcp_client.py").read_text(encoding="utf-8")
    assert '"clientInfo": {"name": "xaviq-trading-engine", "version": "1.0"}' in mcp_code


def test_runtime_window_title_offscreen():
    """Memastikan secara runtime saat QML dimuat, window title adalah 'XAVIQ Trading Engine'."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from src.controller import BotController

    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    controller = BotController()
    engine.rootContext().setContextProperty("bot", controller)
    engine.load("ui/qml/main.qml")

    root_objs = engine.rootObjects()
    assert len(root_objs) > 0
    window = root_objs[0]
    assert window.property("title") == "XAVIQ Trading Engine"
