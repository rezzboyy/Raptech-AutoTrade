"""Entry point aplikasi GUI (PySide6 + QML).

Jalankan (dev):   python app.py
Build EXE:        lihat build.ps1 / raptech_bot.spec

Untuk mode headless/CLI tanpa UI, gunakan main.py.
"""

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from src.controller import BotController
from src.logger import get_logger

logger = get_logger("mt5bot")


def resource_path(relative: str) -> Path:
    """Resolusi path resource untuk mode dev maupun bundel PyInstaller.

    Saat dibundel (frozen), file data ada di folder sementara sys._MEIPASS.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent / relative


def _install_excepthook() -> None:
    """Pasang handler exception global agar error tak tertangani tercatat di log."""

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error("Exception tak tertangani:\n%s", text)

    sys.excepthook = _hook


def main() -> int:
    _install_excepthook()

    # Gunakan Material style agar semua kontrol (input, combo, tombol) bertema
    # gelap yang konsisten & nyaman (bukan putih menyilaukan dari style native).
    # Varian "Dense" membuat kontrol lebih ringkas (hemat ruang).
    os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Dense")
    QQuickStyle.setStyle("Material")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("XAVIQ Trading Engine")
    app.setOrganizationName("XAVIQ")

    icon_path = resource_path("ui/assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        png_icon = resource_path("ui/assets/icon.png")
        if png_icon.exists():
            app.setWindowIcon(QIcon(str(png_icon)))

    splash_file = resource_path("ui/qml/Splash.qml")
    splash_engine = None
    if splash_file.exists():
        try:
            splash_engine = QQmlApplicationEngine()
            splash_engine.load(str(splash_file))
            app.processEvents()
        except Exception as exc:
            logger.debug("Splash screen dilewati: %s", exc)
            splash_engine = None

    # Ekspos controller ke QML sebagai objek `bot`.
    controller = BotController()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bot", controller)

    qml_file = resource_path("ui/qml/main.qml")
    engine.load(str(qml_file))

    if not engine.rootObjects():
        logger.error("Gagal memuat QML dari %s", qml_file)
        if splash_engine:
            for obj in splash_engine.rootObjects():
                obj.close()
        return -1

    # Tutup splash screen setelah main window siap dimuat
    if splash_engine:
        for obj in splash_engine.rootObjects():
            obj.close()
        splash_engine = None

    # Pastikan worker berhenti rapi saat aplikasi ditutup.
    def _cleanup():
        try:
            controller.disconnectBot()
        except Exception:  # noqa: BLE001
            pass

    app.aboutToQuit.connect(_cleanup)

    exit_code = app.exec()
    QCoreApplication.processEvents()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
