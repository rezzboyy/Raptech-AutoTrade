"""Setup logging terpusat untuk bot.

Menghasilkan output ke console dan ke file rotating di folder logs/.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "bot.log")
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str = "mt5bot", level: int = logging.INFO) -> logging.Logger:
    """Buat atau ambil logger yang sudah dikonfigurasi.

    Args:
        name: nama logger.
        level: level logging minimum.

    Returns:
        Instance logging.Logger yang siap pakai.
    """
    logger = logging.getLogger(name)

    # Hindari menambah handler berkali-kali jika dipanggil ulang.
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    # Handler console.
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # Handler file (maks 5 MB, simpan 3 backup).
    os.makedirs(_LOG_DIR, exist_ok=True)
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
