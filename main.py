from __future__ import annotations

"""
Raptech Autotrade CLI — Main Entry Point.
Dispatches between interactive Ultra-Light TUI, Textual TUI, and Headless daemon.
"""

import os
import sys
from typing import Optional

def setup_windows_console() -> None:
    """Configure Windows console for UTF-8 and native Virtual Terminal (VT100) processing."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32

        # 1. Set console code page to UTF-8
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)

        # 2. Enable Virtual Terminal Processing (VT100)
        ENABLE_PROCESSED_OUTPUT = 0x0001
        ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        vt_flags = ENABLE_PROCESSED_OUTPUT | ENABLE_WRAP_AT_EOL_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING

        for std_id in (-11, -12):
            h = kernel32.GetStdHandle(std_id)
            if h and h != -1:
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(h, mode.value | vt_flags)

        # Also activate VT on active CONOUT$ handle directly
        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 1
        FILE_SHARE_WRITE = 2
        OPEN_EXISTING = 3
        h_con = kernel32.CreateFileW(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if h_con and h_con != -1:
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_con, ctypes.byref(mode)):
                kernel32.SetConsoleMode(h_con, mode.value | vt_flags)
            kernel32.CloseHandle(h_con)
    except Exception:
        pass


# Force Windows Console Code Page to UTF-8 and Virtual Terminal mode
if sys.platform == "win32":
    setup_windows_console()

os.environ["PYTHONIOENCODING"] = "utf-8"

# Ensure working directory is always the application root directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
os.chdir(APP_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

for stream_name in ("stdout", "stderr", "__stdout__", "__stderr__"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import typer
from cli.commands import app


@app.callback(invoke_without_command=True)
def default_entry(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Nama profil akun di data/profiles/"
    ),
    mode: Optional[str] = typer.Option(
        None, "--mode", "-m", help="Pilih mode trading: real, demo, atau simulasi"
    ),
    headless: bool = typer.Option(
        False, "--headless", help="Jalankan sebagai background daemon tanpa UI"
    ),
    tui: bool = typer.Option(
        False, "--tui", help="Jalankan Textual TUI fullscreen (opsional)"
    ),
    inline: bool = typer.Option(
        True, "--inline", help="Jalankan terminal UI mode inline tanpa alternate buffer (default: True)"
    ),
) -> None:
    """Raptech Autotrade CLI default entry dispatcher."""
    if ctx.invoked_subcommand is None:
        if headless:
            import asyncio
            from cli.headless import run_headless_daemon
            asyncio.run(run_headless_daemon(profile, mode=mode))
        else:
            import asyncio
            from tui.light_app import run_light_app
            asyncio.run(run_light_app(profile=profile, inline=inline, mode_override=mode))


if __name__ == "__main__":
    app()
