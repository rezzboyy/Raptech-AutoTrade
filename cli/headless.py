from __future__ import annotations

"""
Raptech Autotrade CLI — Headless Daemon Runner.
Runs without interactive UI for low-overhead background operation (VPS/Linux/Services).
"""

import asyncio
from datetime import datetime
import signal
from typing import Optional

from rich.console import Console

from core.config_store import load_profile
from core.controller import TradeController
from core.logger import get_logger

logger = get_logger("headless")
console = Console()


async def run_headless_daemon(profile_name: Optional[str] = None, mode: Optional[str] = None) -> None:
    """Run bot as headless background service."""
    console.print("[bold cyan]══════════════ RAPTECH AUTOTRADE DAEMON ══════════════[/bold cyan]")
    profile = load_profile(profile_name)
    if mode:
        profile.trading_mode = mode.lower()
    t_mode = getattr(profile, "trading_mode", "demo").upper()
    console.print(f"[dim]Memuat Profil:[/dim] [white]{profile.profile_name}[/white] • [dim]Mode:[/dim] [bold yellow]{t_mode}[/bold yellow] • [dim]Backend:[/dim] [white]{profile.backend.upper()}[/white]")

    controller = TradeController(profile)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    def _sig_handler():
        console.print("\n[yellow]Menerima sinyal shutdown, menghentikan daemon...[/yellow]")
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT, _sig_handler)
        loop.add_signal_handler(signal.SIGTERM, _sig_handler)
    except (NotImplementedError, AttributeError):
        pass

    connected = await controller.connect()
    if not connected:
        console.print("[bold red]Gagal terhubung ke broker. Daemon keluar.[/bold red]")
        return

    # Automatically enable auto-trading in headless mode
    controller.start_auto_trading()
    console.print(f"[bold green]✔ Daemon berjalan. Strategi: {profile.strategy} (Tekan Ctrl+C untuk berhenti).[/bold green]\n")

    try:
        counter = 0
        while not stop_event.is_set():
            await asyncio.sleep(5.0)
            counter += 1
            if counter % 6 == 0:  # Every 30s print status heartbeat
                acc = await asyncio.to_thread(controller.backend.account_info) if controller.backend else None
                telemetry = controller.get_telemetry()
                pos = await asyncio.to_thread(controller.backend.positions) if controller.backend else []
                bal_str = f"${acc.balance:,.2f}" if acc else "N/A"
                eq_str = f"${acc.equity:,.2f}" if acc else "N/A"
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                console.print(
                    f"[dim]{ts}[/dim] [green]Heartbeat OK[/green] • "
                    f"Pos: [bold white]{len(pos)}[/bold white] • "
                    f"Bal: [bold white]{bal_str}[/bold white] • "
                    f"Eq: [bold white]{eq_str}[/bold white] • "
                    f"RAM: [cyan]{telemetry.ram_mb} MB[/cyan]"
                )
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await controller.disconnect()
        console.print("[bold green]✔ Raptech Autotrade Daemon berhenti bersih.[/bold green]")
