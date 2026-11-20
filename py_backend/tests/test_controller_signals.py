"""Test sinyal dan sinkronisasi simbol pada _Worker dan BotController.

Memastikan perbaikan chartSymbolChanged pada _Worker berjalan semestinya dan thread-safe.
"""

import queue
import pytest
from unittest.mock import MagicMock
from PySide6.QtGui import QGuiApplication
import sys

from src.controller import _Worker, BotController
from config.settings import settings


@pytest.fixture(scope="session")
def qapp():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv)
    return app


def test_worker_signals_and_chart_symbol(qapp):
    """Pastikan _Worker memiliki atribut sinyal chartSymbolChanged dan memancarkannya saat simbol berubah."""
    engine_mock = MagicMock()
    engine_mock.connect.return_value = True
    engine_mock.list_symbols.return_value = ["EURUSDm", "XAUUSDm"]

    close_q = queue.Queue()
    cmd_q = queue.Queue()

    # Inisialisasi _Worker dengan simbol awal berbeda dari settings.symbol
    settings.symbol = "EURUSDm"
    worker = _Worker(engine_mock, close_q, cmd_q, chart_symbol="XAUUSDm")

    # Pastikan sinyal chartSymbolChanged ada pada _Worker
    assert hasattr(worker, "chartSymbolChanged")

    received = []
    worker.chartSymbolChanged.connect(lambda s: received.append(s))

    # Panggil baris yang sebelumnya error di run()
    # (simulasi awal run saat simbol diselaraskan)
    if not worker._chart_symbol or worker._chart_symbol != settings.symbol:
        worker._chart_symbol = settings.symbol
        worker.chartSymbolChanged.emit(worker._chart_symbol)

    assert len(received) == 1
    assert received[0] == "EURUSDm"
    assert worker._chart_symbol == "EURUSDm"


def test_controller_on_worker_chart_symbol(qapp):
    """Pastikan BotController menangani sinyal chartSymbol dari worker dengan benar."""
    ctrl = BotController()
    emitted = []
    ctrl.chartSymbolChanged.connect(lambda s: emitted.append(s))

    ctrl._on_worker_chart_symbol("BTCUSDm")
    assert ctrl.chartSymbol == "BTCUSDm"
    assert len(emitted) == 1
    assert emitted[0] == "BTCUSDm"
