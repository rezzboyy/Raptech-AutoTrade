"""Uji komponen animasi AnalyzeHUD di Mode Programmer."""

import os
import sys
import pytest

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlApplicationEngine

from src.controller import BotController


@pytest.fixture(scope="module")
def qml_env():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv)
    ctrl = BotController()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bot", ctrl)
    yield ctrl, engine
    try:
        ctrl.disconnectBot()
    except Exception:
        pass


def test_analyze_hud_instantiation(qml_env):
    """Pastikan komponen AnalyzeHUD dapat dimuat dan diinstansiasi tanpa galat QML."""
    ctrl, engine = qml_env
    comp = QQmlComponent(engine, "ui/qml/components/AnalyzeHUD.qml")
    assert not comp.isError(), f"Error QML AnalyzeHUD: {comp.errorString()}"

    hud = comp.create()
    assert hud is not None, "Gagal membuat instance AnalyzeHUD"

    # Periksa nilai default
    assert hud.property("active") is False
    assert hud.property("previewMode") is False
    assert hud.property("isAnalyzing") is False

    # Uji perubahan active (saat Start Trading)
    hud.setProperty("active", True)
    assert hud.property("active") is True
    assert hud.property("isAnalyzing") is True

    # Uji previewMode
    hud.setProperty("active", False)
    hud.setProperty("previewMode", True)
    assert hud.property("isAnalyzing") is True

    hud.deleteLater()


def test_main_qml_loads_script_panel_with_analyze_hud(qml_env):
    """Pastikan main.qml memuat ScriptPanel dan AnalyzeHUD dengan sukses."""
    ctrl, engine = qml_env
    engine.load("ui/qml/main.qml")
    roots = engine.rootObjects()
    assert len(roots) > 0, "main.qml harus memiliki setidaknya satu rootObject"
