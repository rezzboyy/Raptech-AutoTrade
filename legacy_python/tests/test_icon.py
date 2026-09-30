"""Test validitas dan kelengkapan ikon bot (ICO & multi-resolusi PNG)."""

import os
from PIL import Image
import pytest

from tools import make_icon


def test_icon_ico_exists_and_has_all_sizes():
    """Memastikan ui/assets/icon.ico ada dan memiliki semua ukuran standar Windows."""
    ico_path = os.path.join("ui", "assets", "icon.ico")
    assert os.path.exists(ico_path), f"File {ico_path} tidak ditemukan"
    assert os.path.getsize(ico_path) > 1000, f"Ukuran {ico_path} terlalu kecil"

    with Image.open(ico_path) as ico:
        sizes = set(ico.info.get("sizes", []))
        expected_sizes = {
            (16, 16),
            (20, 20),
            (24, 24),
            (32, 32),
            (40, 40),
            (48, 48),
            (64, 64),
            (96, 96),
            (128, 128),
            (256, 256),
        }
        missing = expected_sizes - sizes
        assert not missing, f"Ukuran ICO hilang: {missing}"


def test_icon_png_standard_exists_and_is_256():
    """Memastikan ui/assets/icon.png ada, berformat PNG RGBA 256x256."""
    png_path = os.path.join("ui", "assets", "icon.png")
    assert os.path.exists(png_path), f"File {png_path} tidak ditemukan"

    with Image.open(png_path) as img:
        assert img.format == "PNG"
        assert img.mode == "RGBA"
        assert img.size == (256, 256)


@pytest.mark.parametrize("size", [16, 20, 24, 32, 40, 48, 64, 96, 128, 256, 512])
def test_all_png_sizes_exist_and_match(size):
    """Memastikan setiap variasi icon-{size}.png ada dan berdimensi tepat."""
    file_path = os.path.join("ui", "assets", f"icon-{size}.png")
    assert os.path.exists(file_path), f"File {file_path} tidak ditemukan"

    with Image.open(file_path) as img:
        assert img.size == (size, size)
        assert img.mode == "RGBA"


def test_make_icon_execution():
    """Memastikan skrip make_icon.py dapat dieksekusi tanpa error."""
    make_icon.main()
    assert os.path.exists(os.path.join("ui", "assets", "icon.ico"))
    assert os.path.exists(os.path.join("ui", "assets", "icon.png"))


def test_pyside6_qicon_loads_multi_sizes():
    """Memastikan PySide6 QIcon dapat membaca multi-ukuran dari ui/assets/icon.ico."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QGuiApplication, QIcon

    app = QGuiApplication.instance() or QGuiApplication([])
    ico_path = os.path.join("ui", "assets", "icon.ico")
    icon = QIcon(ico_path)

    assert not icon.isNull(), "QIcon gagal memuat icon.ico"
    available = [(sz.width(), sz.height()) for sz in icon.availableSizes()]
    assert (16, 16) in available
    assert (32, 32) in available
    assert (256, 256) in available
