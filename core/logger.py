from __future__ import annotations

"""
Raptech Autotrade CLI — Centralized Logging Engine.
Outputs formatted logs to terminal via Rich Console and to rotating file.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
from typing import Optional

# Ensure UTF-8 console output encoding on Windows across all modules
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

for stream_name in ("stdout", "stderr", "__stdout__", "__stderr__"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from rich.console import Console
from rich.logging import RichHandler

_LOGGER_INITIALIZED = False
_LOG_DIR = Path("logs")
_LOG_FILE = _LOG_DIR / "autotrade.log"
console = Console()


def mask_secret(text: str) -> str:
    """Mask passwords and tokens in log strings."""
    if not text:
        return text
    # Mask password=..., token=..., key=...
    masked = re.sub(r"(password|token|api_key|secret)\s*[:=]\s*['\"]?([^'\"\s]+)['\"]?", r"\1=***", text, flags=re.IGNORECASE)
    return masked


class SecretMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_secret(record.msg)
        return True


def setup_logger(log_level: int = logging.INFO, log_file: Optional[Path] = None) -> logging.Logger:
    global _LOGGER_INITIALIZED
    logger = logging.getLogger("raptech")
    
    if _LOGGER_INITIALIZED:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    target_file = log_file or _LOG_FILE
    target_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Console Rich Handler
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    rich_handler.setLevel(log_level)
    rich_handler.addFilter(SecretMaskingFilter())

    # 2. Rotating File Handler (5 MB, up to 3 backups)
    file_handler = RotatingFileHandler(
        target_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(SecretMaskingFilter())

    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)
    _LOGGER_INITIALIZED = True
    return logger


def mute_console_logging() -> None:
    """Mute RichHandler console output during interactive TUI to prevent screen tearing/flicker."""
    logger = logging.getLogger("raptech")
    for handler in logger.handlers:
        if isinstance(handler, RichHandler):
            handler.setLevel(logging.CRITICAL + 10)


def unmute_console_logging(log_level: int = logging.INFO) -> None:
    """Restore RichHandler console output when exiting TUI."""
    logger = logging.getLogger("raptech")
    for handler in logger.handlers:
        if isinstance(handler, RichHandler):
            handler.setLevel(log_level)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    setup_logger()
    if name:
        return logging.getLogger(f"raptech.{name}")
    return logging.getLogger("raptech")
