from __future__ import annotations

"""
Raptech Autotrade CLI — Ultra-Lightweight Interactive Terminal UI.
Rich-powered live dashboard with low CPU (< 1%) and minimal RAM (< 30 MB).
Provides real-time account telemetry, open positions table, live logs, and responsive keyboard controls.
"""

import asyncio
from collections import deque
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, List, Optional

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from backend.base import AccountInfo, Position, Tick
from core.config_store import AccountProfile, list_profiles, load_profile, save_profile
from core.secure_store import mask_token
from core.controller import TradeController
from core.logger import get_logger, mute_console_logging, unmute_console_logging
from core.market_analyzer import MarketAnalyzer, MarketRecommendation
from strategies import get_registry

logger = get_logger("light_tui")

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


def set_windows_cursor_visible(visible: bool) -> None:
    """Set console cursor visibility via Windows API."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class CONSOLE_CURSOR_INFO(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("bVisible", wintypes.BOOL)]

        kernel32 = ctypes.windll.kernel32
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
            info = CONSOLE_CURSOR_INFO()
            if kernel32.GetConsoleCursorInfo(h_con, ctypes.byref(info)):
                info.bVisible = visible
                kernel32.SetConsoleCursorInfo(h_con, ctypes.byref(info))
            kernel32.CloseHandle(h_con)
    except Exception:
        pass


# Ensure UTF-8 Windows Console and VT mode
setup_windows_console()

for stream_name in ("stdout", "stderr", "__stdout__", "__stderr__"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def poll_key() -> Optional[str]:
    """Non-blocking keyboard character poll for Windows and POSIX."""
    if sys.platform == "win32":
        try:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    if msvcrt.kbhit():
                        msvcrt.getwch()
                    return None
                return ch.lower()
        except Exception:
            return None
    return None


class LightAutotradeApp:
    """Rich Live Terminal UI application for Raptech Autotrade."""

    def __init__(
        self,
        profile_name: Optional[str] = None,
        screen: bool = False,
        mode_override: Optional[str] = None,
    ) -> None:
        self.console = Console(
            legacy_windows=False,
            force_terminal=True,
            color_system="truecolor",
            soft_wrap=False,
        )
        self.screen = screen
        self.profile = load_profile(profile_name)

        # Apply mode override if provided
        if mode_override:
            m_clean = mode_override.strip().lower()
            if m_clean in ("real", "live"):
                self.profile.trading_mode = "real"
            elif m_clean in ("demo", "trial"):
                self.profile.trading_mode = "demo"
            elif m_clean in ("simulasi", "sim", "simulation", "paper"):
                self.profile.trading_mode = "simulasi"

        if not self.profile.symbols:
            self.profile.symbols = ["XAUUSDm", "EURUSDm", "BTCUSDm"]

        self.controller = TradeController(self.profile)
        self.logs: deque[str] = deque(maxlen=24)
        self.status_banner = "Menghubungkan ke backend broker..."
        self.stop_event = asyncio.Event()
        self._tick_cache: Dict[str, Optional[Tick]] = {}
        self._last_tick_time: float = 0.0
        self._dirty: bool = True

        # Dual-View Architecture state: 'overview' (Market & Account Radar) vs 'live' (Clean Live Trading)
        self.active_view: str = "overview"
        self.market_analyzer = MarketAnalyzer(backend=self.controller.backend)
        self._recommendations: List[MarketRecommendation] = []
        self._last_recommendations_time: float = 0.0
        self._last_console_size: tuple[int, int] = (0, 0)

        # Connect controller log listener
        self.controller.add_log_listener(self.add_log)

    @contextmanager
    def _modal_session(self, live: Live):
        """Pause Live render loop, clean screen buffer, and enable cursor for interactive prompts."""
        live.stop()
        set_windows_cursor_visible(True)
        self.console.clear()
        if sys.platform == "win32":
            try:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
            except Exception:
                pass
        try:
            yield
        finally:
            self.console.clear()
            if sys.platform == "win32":
                try:
                    sys.stdout.write("\033[2J\033[H")
                    sys.stdout.flush()
                except Exception:
                    pass
            set_windows_cursor_visible(False)
            live.start()

    def get_clean_strategy_display(self) -> str:
        """Return strategy display name stripped of duplicate timeframe tags like (M1)."""
        import re
        raw = str(self.active_strategy_name or "")
        clean = re.sub(r"\s*\([A-Za-z0-9]+\)\s*$", "", raw).strip()
        return clean if clean else raw

    def refresh_market_recommendations(self) -> None:
        """Scan active symbols and update recommendations cache."""
        try:
            self._recommendations = self.market_analyzer.scan_all(
                self.active_symbols,
                backend=self.controller.backend,
                timeframe=self.active_timeframe,
            )
            self._last_recommendations_time = time.time()
        except Exception as e:
            logger.error(f"Gagal memindai rekomendasi pasar: {e}")

    @property
    def active_strategy_name(self) -> str:
        if self.controller.engine and self.controller.engine.strategy:
            return self.controller.engine.strategy.display_name
        return self.profile.strategy or "Price Action Hybrid"

    @property
    def active_strategy_code(self) -> str:
        if self.controller.engine and self.controller.engine.strategy:
            return self.controller.engine.strategy.name
        return self.profile.strategy or "pa_hybrid"

    @property
    def active_timeframe(self) -> str:
        if getattr(self.profile, "timeframe", ""):
            return self.profile.timeframe
        if self.controller.engine and hasattr(self.controller.engine.strategy, "recommended_timeframe"):
            return self.controller.engine.strategy.recommended_timeframe
        return "M1"

    @property
    def active_symbols(self) -> List[str]:
        if self.controller.engine and hasattr(self.controller.engine, "current_symbols"):
            return self.controller.engine.current_symbols
        return getattr(self.profile, "symbols", ["XAUUSDm", "EURUSDm", "BTCUSDm"])

    def add_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"{ts} {msg}")
        self._dirty = True

    def render_header(self, acc: Optional[AccountInfo], telemetry: Any) -> Panel:
        """Render modern cyberpunk/bloomberg-style telemetry and financial HUD header."""
        is_auto = self.controller.engine and self.controller.engine.auto_trading_enabled
        is_conn = self.controller.is_connected
        cb_tripped = (
            self.controller.engine
            and self.controller.engine.risk_manager.circuit_breaker_tripped
        )

        term_w = max(60, self.console.size.width)
        term_h = max(20, self.console.size.height)
        is_compact = term_w < 100 or term_h <= 26

        # Status badge determination
        if not is_conn:
            status_text = Text.from_markup("[bold white on #b71c1c] ● DISCONNECTED [/bold white on #b71c1c]")
        elif cb_tripped:
            status_text = Text.from_markup("[bold white on #d50000] ! CIRCUIT BREAKER [/bold white on #d50000]")
        elif is_auto:
            status_label = "● AUTO ON" if is_compact else "● AUTO TRADING ACTIVE"
            status_text = Text.from_markup(f"[bold black on #00e676] {status_label} [/bold black on #00e676]")
        else:
            status_label = "● STANDBY" if is_compact else "● STANDBY (MONITORING)"
            status_text = Text.from_markup(f"[bold black on #00b0ff] {status_label} [/bold black on #00b0ff]")

        # Trading Mode Badge (Real, Demo, Simulasi)
        t_mode = getattr(self.profile, "trading_mode", "demo").lower()
        if t_mode == "real":
            env_badge = "[bold white on #d50000] REAL [/bold white on #d50000]"
        elif t_mode == "simulasi":
            env_badge = "[bold black on #00e5ff] SIMULASI [/bold black on #00e5ff]"
        else:
            env_badge = "[bold black on #ffd600] DEMO [/bold black on #ffd600]"

        # Brand Title Bar
        b_mode = self.profile.backend.upper()
        if t_mode == "simulasi":
            b_badge = "[bold black on #00e5ff] PAPER [/bold black on #00e5ff]"
        elif b_mode == "NATIVE":
            b_badge = "[bold black on #00e676] NATIVE [/bold black on #00e676]"
        else:
            b_badge = "[bold black on #ffd600] MCP [/bold black on #ffd600]"

        view_badge = "[bold white on #455a64] VIEW: OVERVIEW [/bold white on #455a64]" if self.active_view == "overview" else "[bold white on #00695c] VIEW: LIVE TRADING [/bold white on #00695c]"

        if is_compact:
            title_text = Text.from_markup(
                f"[bold black on bright_cyan] RAPTECH [/bold black on bright_cyan] "
                f"[bold cyan]AUTOTRADE v3[/bold cyan] "
                f"[bold white on #1e293b] [{self.profile.profile_name}] [/bold white on #1e293b] "
                f"{env_badge} {b_badge}"
            )
        else:
            title_text = Text.from_markup(
                f"[bold black on bright_cyan] RAPTECH [/bold black on bright_cyan] "
                f"[bold cyan]AUTOTRADE v3.1.0[/bold cyan]  "
                f"[bold white on #1e293b] [PROFIL: {self.profile.profile_name}] [/bold white on #1e293b]  "
                f"{env_badge} {b_badge}  {view_badge}"
            )

        # Telemetry metrics
        uptime_str = self.controller.watchdog.format_uptime(telemetry.uptime_seconds)
        mem_str = f"{telemetry.ram_mb:.0f}M" if is_compact else f"{telemetry.ram_mb:.1f} MB"
        cpu_str = f"{telemetry.cpu_percent:.0f}%" if is_compact else f"{telemetry.cpu_percent:.1f}%"

        grid = Table.grid(expand=True)
        grid.add_column(ratio=7)
        grid.add_column(ratio=3, justify="right")
        grid.add_row(title_text, status_text)

        # Metadata row: Server, Login, Account Type, Ping/Latency, System resources
        login_display = str(acc.login) if acc else (str(self.profile.login) if self.profile.login else "Auto/Default")
        acc_type_display = acc.account_type if acc else t_mode.upper()
        if "REAL" in acc_type_display:
            type_style = "bold red"
        elif "SIMULASI" in acc_type_display:
            type_style = "bold cyan"
        elif "CONTEST" in acc_type_display:
            type_style = "bold magenta"
        else:
            type_style = "bold yellow"

        server_display = "Engine Simulasi" if t_mode == "simulasi" else self.profile.server
        algo_status = "[bold green]ON[/bold green]" if getattr(acc, "algo_trading_allowed", True) else "[bold red]OFF (Ctrl+E)[/bold red]"

        if is_compact:
            sub_info = Table.grid(expand=True)
            sub_info.add_column(ratio=65)
            sub_info.add_column(ratio=35, justify="right")
            sub_info.add_row(
                Text.from_markup(
                    f"[dim]Srv:[/dim] [white]{server_display[:16]}[/white] "
                    f"[dim]• Id:[/dim] [white]{login_display}[/white] "
                    f"[dim]• Algo:[/dim] {algo_status}"
                ),
                Text.from_markup(
                    f"[dim]RAM:[/dim] [green]{mem_str}[/green] "
                    f"[dim]CPU:[/dim] [green]{cpu_str}[/green] "
                    f"[dim]Up:[/dim] [white]{uptime_str}[/white]"
                ),
            )
        else:
            sub_info = Table.grid(expand=True)
            sub_info.add_column(ratio=6)
            sub_info.add_column(ratio=4, justify="right")
            sub_info.add_row(
                Text.from_markup(
                    f"[dim]Broker/Server:[/dim] [bold white]{server_display}[/bold white]  "
                    f"[dim]• Login:[/dim] [white]{login_display}[/white]  "
                    f"[dim]• Mode:[/dim] [{type_style}]{acc_type_display}[/{type_style}]  "
                    f"[dim]• Algo MT5:[/dim] {algo_status}"
                ),
                Text.from_markup(
                    f"[dim]RAM:[/dim] [green]{mem_str}[/green] • "
                    f"[dim]CPU:[/dim] [green]{cpu_str}[/green] • "
                    f"[dim]Uptime:[/dim] [white]{uptime_str}[/white]"
                ),
            )

        # Contextual Alert Banner
        alert_widget: Optional[Text] = None
        if t_mode == "real" and is_conn:
            alert_widget = Text.from_markup(
                "[bold white on #d50000] ! PERINGATAN:[/] Mode Real. Tekan [bold yellow][T][/bold yellow] untuk beralih mode."
            )
        elif is_conn and acc and not getattr(acc, "algo_trading_allowed", True) and t_mode != "simulasi":
            alert_widget = Text.from_markup(
                "[bold white on red] ! ALGO MT5 NONAKTIF:[/] Klik tombol Algo Trading (Ctrl+E) di MT5 hingga hijau!"
            )
        elif not is_conn:
            alert_text = (
                f"[bold yellow]! STATUS:[/] Belum terhubung MT5 ({self.profile.server[:12]}). Tekan [P] Login / [T] Simulasi."
                if is_compact
                else f"[bold yellow]! STATUS:[/] Belum terhubung ke broker MT5 ({self.profile.server}). Tekan [bold yellow][P][/bold yellow] login / [bold yellow][T][/bold yellow] simulasi."
            )
            alert_widget = Text.from_markup(alert_text)
        elif cb_tripped:
            reason = self.controller.engine.risk_manager.circuit_breaker_reason
            alert_widget = Text.from_markup(
                f"[bold red]! CIRCUIT BREAKER LOCKOUT:[/] [white]{reason[:40]}[/white] "
            )

        elements = [grid, sub_info]
        if alert_widget:
            elements.append(alert_widget)

        return Panel(Group(*elements), box=box.ROUNDED, style="cyan")

    def render_financial_cards(self, acc: Optional[AccountInfo]) -> Table:
        """Render 4-column balanced financial metric cards grid."""
        # Balances
        if acc:
            if getattr(acc, "is_cent", False):
                balance_val = f"{acc.balance:,.2f} {acc.currency}"
                equity_val = f"{acc.equity:,.2f} {acc.currency}"
            elif acc.currency == "USD":
                balance_val = f"${acc.balance:,.2f}"
                equity_val = f"${acc.equity:,.2f}"
            else:
                balance_val = f"{acc.balance:,.2f} {acc.currency}"
                equity_val = f"{acc.equity:,.2f} {acc.currency}"
        else:
            balance_val = "$0.00"
            equity_val = "$0.00"

        # Equity diff
        if acc and acc.balance > 0:
            eq_diff = acc.equity - acc.balance
            eq_diff_pct = (eq_diff / acc.balance) * 100.0
            eq_sign = "+" if eq_diff >= 0 else ""
            eq_col = "bold green" if eq_diff >= 0 else "bold red"
            equity_sub = f"[{eq_col}]{eq_sign}{eq_diff_pct:.2f}%[/{eq_col}]"
        else:
            equity_sub = "[dim]0.00%[/dim]"

        # Margin health
        if acc and acc.margin > 0:
            m_lvl = acc.margin_level
            m_col = "bold green" if m_lvl >= 500 else ("bold yellow" if m_lvl >= 200 else "bold red")
            margin_lvl = f"[{m_col}]{m_lvl:,.0f}%[/{m_col}]"
            free_mgn = f"${acc.free_margin:,.2f}" if acc.currency == "USD" else f"{acc.free_margin:,.2f}"
            margin_sub = f"[dim]Free: {free_mgn}[/dim]"
        else:
            margin_lvl = "[bold cyan]SAFE (100%)[/bold cyan]"
            free_mgn = f"${acc.free_margin:,.2f}" if (acc and acc.currency == "USD") else "$0.00"
            margin_sub = f"[dim]Free: {free_mgn}[/dim]"

        # Floating profit & positions count
        pos_list = self.controller.backend.positions() if self.controller.is_connected else []
        tot_profit = sum(p.profit for p in pos_list)
        p_col = "bold green" if tot_profit >= 0 else "bold red"
        p_sign = "+" if tot_profit >= 0 else ""
        profit_val = f"[{p_col}]{p_sign}${tot_profit:,.2f}[/{p_col}]"
        pos_sub = f"[white]{len(pos_list)}[/white] / {self.profile.risk.max_open_positions} Posisi"

        # Daily realized PnL
        if self.controller.engine and self.controller.engine.risk_manager:
            rm = self.controller.engine.risk_manager
            start_bal = rm.daily_start_balance if rm.daily_start_balance > 0 else (acc.balance if acc else 1.0)
            daily_pnl = (acc.equity - start_bal) if (acc and start_bal > 0) else 0.0
            d_sign = "+" if daily_pnl >= 0 else ""
            d_col = "green" if daily_pnl >= 0 else "red"
            bal_sub = f"[dim]Net:[/dim] [{d_col}]{d_sign}${daily_pnl:,.2f}[/{d_col}]"
        else:
            bal_sub = "[dim]Net: $0.00[/dim]"

        grid = Table.grid(expand=True)
        grid.add_column(ratio=25)
        grid.add_column(ratio=25)
        grid.add_column(ratio=25)
        grid.add_column(ratio=25)

        c1 = Panel(f"[bold white]{balance_val}[/bold white]\n{bal_sub}", title="[bold cyan]SALDO (BALANCE)[/bold cyan]", box=box.ROUNDED, style="cyan")
        c2 = Panel(f"[bold white]{equity_val}[/bold white]\n{equity_sub}", title="[bold cyan]EKUITAS (EQUITY)[/bold cyan]", box=box.ROUNDED, style="cyan")
        c3 = Panel(f"{margin_lvl}\n{margin_sub}", title="[bold cyan]KESEHATAN MARGIN[/bold cyan]", box=box.ROUNDED, style="cyan")
        c4 = Panel(f"{profit_val}\n{pos_sub}", title="[bold cyan]FLOATING P/L[/bold cyan]", box=box.ROUNDED, style="cyan")

        grid.add_row(c1, c2, c3, c4)
        return grid

    def render_market_radar_table(self) -> Panel:
        """Render multi-market quotes radar table with price action and session statistics."""
        term_w = max(60, self.console.size.width)
        is_compact = term_w < 110

        table = Table(
            box=box.SIMPLE,
            show_edge=False,
            pad_edge=False,
            expand=True,
            padding=(0, 1),
            header_style="bold cyan",
        )
        table.add_column("SIMBOL", style="bold white", width=12)
        table.add_column("BID", justify="right", style="green", width=12)
        table.add_column("ASK", justify="right", style="green", width=12)
        table.add_column("SPREAD", justify="right", style="yellow", width=10)
        if not is_compact:
            table.add_column("HIGH (24H)", justify="right", style="white", width=12)
            table.add_column("LOW (24H)", justify="right", style="white", width=12)
        table.add_column("PERGERAKAN SESI", justify="left", width=22)

        now = time.time()
        if now - self._last_recommendations_time > 15.0 or not self._recommendations:
            self.refresh_market_recommendations()

        for rec in self._recommendations[:6]:
            digits = (
                3 if ("xau" in rec.symbol.lower() or "jpy" in rec.symbol.lower())
                else (2 if "btc" in rec.symbol.lower() else 5)
            )
            bid_s = f"{rec.bid:,.{digits}f}" if rec.bid > 0 else "—"
            ask_s = f"{rec.ask:,.{digits}f}" if rec.ask > 0 else "—"
            spr_s = f"{rec.spread_pts} pts" if rec.spread_pts > 0 else "—"
            hi_s = f"{rec.high_24h:,.{digits}f}" if rec.high_24h > 0 else "—"
            lo_s = f"{rec.low_24h:,.{digits}f}" if rec.low_24h > 0 else "—"

            chg_col = "bold green" if rec.change_pct >= 0 else "bold red"
            chg_arr = "▲" if rec.change_pct >= 0 else "▼"
            chg_sign = "+" if rec.change_pct >= 0 else ""
            sesi_s = f"[{chg_col}]{chg_arr} {chg_sign}{rec.change_pct:.2f}%[/] [dim]({rec.condition[:12]})[/dim]"

            if is_compact:
                table.add_row(rec.symbol, bid_s, ask_s, spr_s, f"[{chg_col}]{chg_arr} {chg_sign}{rec.change_pct:.2f}%[/]")
            else:
                table.add_row(rec.symbol, bid_s, ask_s, spr_s, hi_s, lo_s, sesi_s)

        if not self._recommendations:
            table.add_row("XAUUSDm", "—", "—", "—", "—", "—", "[dim]Memindai pasar...[/dim]")

        return Panel(table, title="RADAR PERGERAKAN PASAR (MARKET WATCH)", box=box.ROUNDED, style="blue")

    def render_market_recommendations_table(self) -> Panel:
        """Render automated algorithmic market recommendations table."""
        term_w = max(60, self.console.size.width)
        is_compact = term_w < 110

        table = Table(
            box=box.SIMPLE,
            show_edge=False,
            pad_edge=False,
            expand=True,
            padding=(0, 1),
            header_style="bold cyan",
        )
        table.add_column("SIMBOL", style="bold white", width=12)
        table.add_column("KONDISI PASAR", style="yellow", width=18)
        table.add_column("VOLATILITAS", style="cyan", width=12)
        table.add_column("REKOMENDASI STRATEGI", style="bold green", width=28)
        table.add_column("SKOR KESIAPAN", justify="right", style="bold yellow", width=18)

        now = time.time()
        if now - self._last_recommendations_time > 15.0 or not self._recommendations:
            self.refresh_market_recommendations()

        for rec in self._recommendations[:4]:
            table.add_row(
                rec.symbol,
                rec.condition,
                rec.volatility,
                rec.strategy_recommended,
                rec.readiness_score,
            )

        if not self._recommendations:
            table.add_row("XAUUSDm", "Monitoring", "Sedang", "Price Action Hybrid Scalper (M1)", "[★★★★☆] SIAP")

        return Panel(table, title="REKOMENDASI PASAR OTOMATIS (ALGORITHMIC SCANNER)", box=box.ROUNDED, style="cyan")

    def render_market_watch(self) -> Panel:
        """Render real-time quotes ticker bar for watched symbols."""
        if self.controller.is_connected:
            now = time.time()
            if now - self._last_tick_time > 1.0:
                self._last_tick_time = now
                for sym in self.active_symbols[:6]:
                    try:
                        t = self.controller.backend.get_tick(sym)
                        if t:
                            self._tick_cache[sym] = t
                    except Exception:
                        pass

        ticker_text = Text()
        ticker_text.append("MARKET WATCH │ ", style="bold cyan")

        term_w = max(60, self.console.size.width)
        term_h = max(20, self.console.size.height)
        max_symbols = 2 if term_w < 105 else (3 if term_w < 135 else 6)

        if not self.controller.is_connected or not self._tick_cache:
            if not self.controller.is_connected:
                ticker_text.append("Menunggu koneksi broker untuk kuotasi harga realtime...", style="dim italic")
            else:
                ticker_text.append(f"Memuat kuotasi pasar ({', '.join(self.active_symbols[:max_symbols])})...", style="dim")
        else:
            items = []
            for sym, tick in list(self._tick_cache.items())[:max_symbols]:
                if not tick:
                    continue
                digits = (
                    3 if ("xau" in sym.lower() or "jpy" in sym.lower())
                    else (2 if "btc" in sym.lower() else 5)
                )
                spread = tick.ask - tick.bid
                spread_pts = int(round(spread / (10 ** -digits))) if digits > 0 else 0

                t_item = Text()
                t_item.append(f"{sym} ", style="bold white")
                t_item.append(f"{tick.bid:,.{digits}f}", style="bold green")
                t_item.append("/", style="dim")
                t_item.append(f"{tick.ask:,.{digits}f} ", style="bold green")
                pts_label = f"({spread_pts}p)" if term_w < 105 else f"({spread_pts} pts)"
                t_item.append(pts_label, style="dim yellow")
                items.append(t_item)

            if items:
                sep = " • " if term_w < 105 else "   •   "
                for idx, itm in enumerate(items):
                    if idx > 0:
                        ticker_text.append(sep, style="dim")
                    ticker_text.append_text(itm)
            else:
                ticker_text.append("Belum ada data tick diterima dari terminal.", style="dim")

        return Panel(ticker_text, box=box.ROUNDED, style="blue")

    def render_positions_table(self, positions: List[Position]) -> Panel:
        """Render active open positions table with clear empty state and protective tags."""
        term_w = max(60, self.console.size.width)
        term_h = max(20, self.console.size.height)
        is_compact = term_w < 100 or term_h <= 26
        r = self.profile.risk
        max_pos = r.max_open_positions

        strat_sl = getattr(self.controller.engine.strategy, "default_sl_points", 0) if (self.controller.engine and self.controller.engine.strategy) else 0
        strat_tp = getattr(self.controller.engine.strategy, "default_tp_points", 0) if (self.controller.engine and self.controller.engine.strategy) else 0
        disp_sl = strat_sl if strat_sl > 0 else r.virtual_sl_points
        disp_tp = strat_tp if strat_tp > 0 else r.virtual_tp_points

        clean_strat = self.get_clean_strategy_display()
        if not positions:
            empty_msg = Text()
            empty_msg.append("● Belum ada posisi terbuka  ", style="bold cyan")
            empty_msg.append(
                f"• Bot standby memindai sinyal [{clean_strat}] ({self.active_timeframe})",
                style="dim italic",
            )
            summary_text = Text.from_markup(
                f"[dim]Total:[/dim] [bold white]0[/bold white] / {max_pos}  •  "
                f"[dim]Net Floating P/L:[/dim] [bold green]+$0.00[/bold green]  •  "
                f"[dim]Proteksi:[/dim] [green]V-SL {disp_sl}p / V-TP {disp_tp}p (Auto-Scale)[/green]"
            )
            content = Group(empty_msg, summary_text)
            return Panel(content, title="POSISI TERBUKA (OPEN POSITIONS)", box=box.ROUNDED, style="cyan")

        table = Table(
            box=box.SIMPLE,
            show_edge=False,
            pad_edge=False,
            expand=True,
            padding=(0, 1),
            show_header=True,
            header_style="bold cyan",
        )
        if is_compact:
            table.add_column("TIKET", style="dim", justify="right", width=9)
            table.add_column("SIMBOL", style="bold white", width=9)
            table.add_column("AKSI", justify="center", width=6)
            table.add_column("LOT", justify="right", width=5)
            table.add_column("BUKA", justify="right", width=9)
            table.add_column("KINI", justify="right", width=9)
            table.add_column("SL (V)", justify="right", width=9)
            table.add_column("TP (V)", justify="right", width=9)
            table.add_column("PROFIT", justify="right", width=10)
        else:
            table.add_column("TIKET", style="dim", justify="right", width=11)
            table.add_column("SIMBOL", style="bold white", width=11)
            table.add_column("AKSI", justify="center", width=8)
            table.add_column("VOLUME", justify="right", width=8)
            table.add_column("HARGA BUKA", justify="right", width=12)
            table.add_column("HARGA KINI", justify="right", width=12)
            table.add_column("SL (VIRT)", justify="right", width=12)
            table.add_column("TP (VIRT)", justify="right", width=12)
            table.add_column("FLOATING P/L", justify="right", width=14)

        total_profit = 0.0
        max_visible_pos = 2 if term_h <= 26 else max(2, min(5, term_h - 22))
        visible_positions = positions[:max_visible_pos]

        for p in visible_positions:
            total_profit += p.profit
            is_buy = p.type.upper() == "BUY"
            side_badge = Text(f" {p.type} ", style="bold white on #0b4f1b" if is_buy else "bold white on #7f0000")
            p_style = "bold green" if p.profit >= 0 else "bold red"
            p_sign = "+" if p.profit >= 0 else ""

            v_state = (
                self.controller.engine.risk_manager.virtual_states.get(p.ticket)
                if self.controller.engine
                else None
            )
            v_sl_str = (
                f"{v_state.virtual_sl:.5f}"
                if v_state and v_state.virtual_sl > 0
                else (f"{p.sl:.5f}" if p.sl > 0 else "—")
            )
            v_tp_str = (
                f"{v_state.virtual_tp:.5f}"
                if v_state and v_state.virtual_tp > 0
                else (f"{p.tp:.5f}" if p.tp > 0 else "—")
            )

            trl_badge = " [bold cyan][T][/bold cyan]" if (v_state and v_state.trailing_active) else ""
            profit_text = Text.from_markup(f"[{p_style}]{p_sign}${p.profit:,.2f}[/{p_style}]{trl_badge}")

            table.add_row(
                f"#{p.ticket}",
                p.symbol,
                side_badge,
                f"{p.volume:.2f}",
                f"{p.price_open:.5f}",
                f"{p.price_current:.5f}",
                v_sl_str,
                v_tp_str,
                profit_text,
            )

        for p in positions[max_visible_pos:]:
            total_profit += p.profit

        if len(positions) > max_visible_pos:
            hidden_cnt = len(positions) - max_visible_pos
            table.add_row("...", f"+{hidden_cnt} lain", "", "", "", "", "", "", "")

        tot_style = "bold green" if total_profit >= 0 else "bold red"
        tot_sign = "+" if total_profit >= 0 else ""
        if is_compact:
            summary_text = Text.from_markup(
                f"[dim]Total:[/dim] [bold white]{len(positions)}[/bold white]/{max_pos} • "
                f"[dim]Net P/L:[/dim] [{tot_style}]{tot_sign}${total_profit:,.2f}[/{tot_style}] • "
                f"[dim]Prot:[/dim] [green]V-SL {disp_sl}p / V-TP {disp_tp}p[/green]"
            )
        else:
            summary_text = Text.from_markup(
                f"[dim]Total Posisi Terbuka:[/dim] [bold white]{len(positions)}[/bold white] / {max_pos}  •  "
                f"[dim]Net Floating P/L:[/dim] [{tot_style}]{tot_sign}${total_profit:,.2f}[/{tot_style}]  •  "
                f"[dim]Proteksi:[/dim] [green]V-SL {disp_sl}p / V-TP {disp_tp}p (Auto-Scale)[/green]"
            )

        return Panel(Group(table, summary_text), title="POSISI TERBUKA (OPEN POSITIONS)", box=box.ROUNDED, style="cyan")

    def render_logs(self, max_lines: Optional[int] = None) -> Panel:
        """Render recent activity logs with structured level badges."""
        log_group = []
        if not self.logs:
            log_group.append(Text("Belum ada log aktivitas...", style="dim italic"))
        else:
            if max_lines is None:
                term_height = max(20, self.console.size.height)
                if term_height > 35:
                    max_lines = 8
                elif term_height < 30:
                    max_lines = max(2, term_height - 22)
                else:
                    max_lines = 5

            for entry in list(self.logs)[-max_lines:]:
                t = Text()
                parts = entry.split(" ", 1)
                ts = parts[0] if len(parts) >= 1 else ""
                rest = parts[1] if len(parts) >= 2 else entry

                t.append(f"{ts} ", style="dim")

                # Strip emojis that break Windows console rendering
                rest_clean = (
                    rest.replace("🛡️", "")
                    .replace("🛡", "")
                    .replace("🎯", "")
                    .replace("⚠️", "")
                    .replace("✅", "")
                    .replace("❌", "")
                    .strip()
                )

                if any(k in rest for k in ("Gagal", "ERROR", "gagal", "ditolak", "❌")):
                    t.append(" ERROR  ", style="bold white on #b71c1c")
                    t.append(f" {rest_clean}", style="bold red")
                elif any(k in rest for k in ("⚠️", "WARN", "Drawdown", "peringatan")):
                    t.append(" WARN   ", style="bold black on #ffd600")
                    t.append(f" {rest_clean}", style="yellow")
                elif any(k in rest for k in ("Sinyal BUY", "Sinyal SELL", "SIGNAL", "Sinyal")):
                    t.append(" SIGNAL ", style="bold black on #00e5ff")
                    t.append(f" {rest_clean}", style="cyan")
                elif any(k in rest for k in ("Order #", "ORDER", "Eksekusi", "buka posisi")):
                    t.append(" ORDER  ", style="bold black on #00e676")
                    t.append(f" {rest_clean}", style="green")
                elif any(k in rest for k in ("PROTEKSI", "Trailing", "PROT", "Stop Loss", "Take Profit")):
                    t.append(" PROT   ", style="bold white on #e65100")
                    t.append(f" {rest_clean}", style="bright_yellow")
                elif any(k in rest for k in ("Terhubung", "INFO", "AUTO TRADING", "✅")):
                    t.append(" INFO   ", style="bold black on #b0bec5")
                    t.append(f" {rest_clean}", style="white")
                else:
                    t.append(" LOG    ", style="dim")
                    t.append(f" {rest_clean}", style="white")

                log_group.append(t)

        return Panel(Group(*log_group), title="LIVE ACTIVITY LOG", box=box.ROUNDED, style="cyan")

    def render_controls(self, mode: Optional[str] = None) -> Panel:
        """Render hotkeys controls bar with sleek tactile keycaps and grouped categories."""
        active_mode = mode or self.active_view
        term_w = max(60, self.console.size.width)
        is_compact = term_w < 110

        is_auto = self.controller.engine and self.controller.engine.auto_trading_enabled
        s_label = "Stop Trading" if is_auto else "Start Session"
        s_bg = "#d50000" if is_auto else "#00e676"
        s_fg = "bold white" if is_auto else "bold black"

        if active_mode == "live":
            # Live Trading Controls
            if is_compact:
                c1 = (
                    f"[{s_fg} on {s_bg}] S [/{s_fg} on {s_bg}] [bold green]{s_label}[/bold green]   "
                    "[bold black on #00e5ff] M [/bold black on #00e5ff] [bold cyan]Order[/bold cyan]   "
                    "[bold white on #c62828] C [/bold white on #c62828] [bold red]Close All[/bold red]   "
                    "[bold white on #ad1457] X [/bold white on #ad1457] [bold magenta]Close 1p1[/bold magenta]"
                )
                c2 = (
                    "[bold white on #455a64] V [/bold white on #455a64] [white]Overview[/white]   "
                    "[bold black on #ea80fc] R [/bold black on #ea80fc] [bold magenta]Risiko[/bold magenta]   "
                    "[bold black on #82b1ff] E [/bold black on #82b1ff] [bold blue]Strategi[/bold blue]   "
                    "[bold black on #cfd8dc] H [/bold black on #cfd8dc] [white]Bantuan[/white]   "
                    "[bold white on #37474f] Q [/bold white on #37474f] [dim white]Keluar[/dim white]"
                )
                controls = Text.from_markup(f"{c1}\n{c2}")
            else:
                controls = Text.from_markup(
                    f"[{s_fg} on {s_bg}] S [/{s_fg} on {s_bg}] [bold green]{s_label}[/bold green]    "
                    "[bold black on #00e5ff] M [/bold black on #00e5ff] [bold cyan]Order Manual[/bold cyan]    "
                    "[bold white on #c62828] C [/bold white on #c62828] [bold red]Tutup SEMUA (Close All)[/bold red]    "
                    "[bold white on #ad1457] X [/bold white on #ad1457] [bold magenta]Tutup 1 per 1[/bold magenta]    "
                    "[bold white on #455a64] V [/bold white on #455a64] [white]Lihat Radar Pasar[/white]    "
                    "[bold black on #ea80fc] R [/bold black on #ea80fc] [bold magenta]Risiko[/bold magenta]    "
                    "[bold black on #82b1ff] E [/bold black on #82b1ff] [bold blue]Strategi[/bold blue]    "
                    "[bold black on #cfd8dc] H [/bold black on #cfd8dc] [white]Bantuan[/white]    "
                    "[bold white on #37474f] Q [/bold white on #37474f] [dim white]Keluar[/dim white]"
                )
        else:
            # Overview Cockpit Controls
            if is_compact:
                c1 = (
                    f"[{s_fg} on {s_bg}] S [/{s_fg} on {s_bg}] [bold green]{s_label}[/bold green]   "
                    "[bold black on #00e5ff] M [/bold black on #00e5ff] [bold cyan]Order[/bold cyan]   "
                    "[bold white on #c62828] C [/bold white on #c62828] [bold red]Close All[/bold red]   "
                    "[bold white on #ad1457] X [/bold white on #ad1457] [bold magenta]Close 1p1[/bold magenta]   "
                    "[bold black on #00e676] K [/bold black on #00e676] [bold green]Simbol[/bold green]"
                )
                c2 = (
                    "[bold white on #00695c] V [/bold white on #00695c] [bold cyan]Live Dash[/bold cyan]   "
                    "[bold black on #ea80fc] R [/bold black on #ea80fc] [bold magenta]Risiko[/bold magenta]   "
                    "[bold black on #82b1ff] E [/bold black on #82b1ff] [bold blue]Strategi[/bold blue]   "
                    "[bold black on #ffab00] T [/bold black on #ffab00] [bold yellow]Mode[/bold yellow]   "
                    "[bold black on #ffd740] P [/bold black on #ffd740] [bold yellow]Profil[/bold yellow]   "
                    "[bold black on #26c6da] A [/bold black on #26c6da] [bold cyan]Scan[/bold cyan]   "
                    "[bold white on #37474f] Q [/bold white on #37474f] [dim white]Keluar[/dim white]"
                )
                controls = Text.from_markup(f"{c1}\n{c2}")
            else:
                c1 = (
                    f"[dim][TRADING][/dim]  [{s_fg} on {s_bg}] S [/{s_fg} on {s_bg}] [bold green]Start Sesi[/bold green]   "
                    "[bold black on #00e5ff] M [/bold black on #00e5ff] [bold cyan]Order Manual[/bold cyan]   "
                    "[bold white on #c62828] C [/bold white on #c62828] [bold red]Tutup SEMUA (Close All)[/bold red]   "
                    "[bold white on #ad1457] X [/bold white on #ad1457] [bold magenta]Tutup 1 per 1[/bold magenta]"
                )
                c2 = (
                    "[dim][CONFIG] [/dim]  [bold black on #00e676] K [/bold black on #00e676] [bold green]Simbol Pasar[/bold green]   "
                    "[bold black on #82b1ff] E [/bold black on #82b1ff] [bold blue]Ganti Strategi[/bold blue]   "
                    "[bold black on #ea80fc] R [/bold black on #ea80fc] [bold magenta]Atur Risiko[/bold magenta]   "
                    "[bold black on #ffab00] T [/bold black on #ffab00] [bold yellow]Mode (Real/Demo/Sim)[/bold yellow]   "
                    "[bold black on #ffd740] P [/bold black on #ffd740] [bold yellow]Profil Akun[/bold yellow]"
                )
                c3 = (
                    "[dim][SYSTEM] [/dim]  [bold white on #00695c] V [/bold white on #00695c] [bold cyan]Live Dashboard[/bold cyan]   "
                    "[bold black on #26c6da] A [/bold black on #26c6da] [bold cyan]Scan Pasar[/bold cyan]   "
                    "[bold black on #cfd8dc] H [/bold black on #cfd8dc] [white]Bantuan & Panduan[/white]   "
                    "[bold white on #37474f] Q [/bold white on #37474f] [dim white]Keluar Aplikasi[/dim white]"
                )
                controls = Text.from_markup(f"{c1}\n{c2}\n{c3}")

        return Panel(controls, box=box.ROUNDED, style="dim white")

    def render_overview_view(self) -> Group:
        """Assemble VIEW 1: Main Overview & Market Intelligence Cockpit."""
        acc = self.controller.backend.account_info() if self.controller.is_connected else None
        telemetry = self.controller.get_telemetry()

        header = self.render_header(acc, telemetry)
        fin_cards = self.render_financial_cards(acc)
        radar_panel = self.render_market_radar_table()
        rec_panel = self.render_market_recommendations_table()
        controls_panel = self.render_controls(mode="overview")

        # Dynamic height calculation to prevent vertical overflow and flicker
        term_h = max(20, self.console.size.height)
        opt = self.console.options
        try:
            h_header = len(list(self.console.render_lines(header, opt)))
            h_fin = len(list(self.console.render_lines(fin_cards, opt)))
            h_radar = len(list(self.console.render_lines(radar_panel, opt)))
            h_rec = len(list(self.console.render_lines(rec_panel, opt)))
            h_ctrl = len(list(self.console.render_lines(controls_panel, opt)))
            used_lines = h_header + h_fin + h_radar + h_rec + h_ctrl
            avail_for_logs = max(2, term_h - used_lines - 1)
        except Exception:
            avail_for_logs = 3

        logs_panel = self.render_logs(max_lines=avail_for_logs)
        return Group(header, fin_cards, radar_panel, rec_panel, logs_panel, controls_panel)

    def render_live_view(self) -> Group:
        """Assemble VIEW 2: Clean Live Trading Execution Dashboard."""
        acc = self.controller.backend.account_info() if self.controller.is_connected else None
        telemetry = self.controller.get_telemetry()
        positions = self.controller.backend.positions() if self.controller.is_connected else []

        header = self.render_header(acc, telemetry)

        # Clean Live Financial Stats Ribbon
        r = self.profile.risk
        t_status = "[bold green]ON[/bold green]" if r.trailing_enabled else "[dim red]OFF[/dim red]"
        t_info = f"{t_status} [dim]({r.trail_start_points}p/{r.trail_step_points}p)[/dim]"

        if self.controller.engine and self.controller.engine.risk_manager:
            rm = self.controller.engine.risk_manager
            start_bal = rm.daily_start_balance if rm.daily_start_balance > 0 else (acc.balance if acc else 1.0)
            daily_pnl = (acc.equity - start_bal) if (acc and start_bal > 0) else 0.0
            daily_loss = abs(daily_pnl) if daily_pnl < 0 else 0.0
        else:
            daily_loss = 0.0

        max_loss = max(1.0, r.max_daily_loss)
        loss_ratio = min(1.0, daily_loss / max_loss)
        bar_len = 8
        filled = int(round(loss_ratio * bar_len))
        dd_bar = "■" * filled + "□" * (bar_len - filled)
        dd_pct = loss_ratio * 100.0
        dd_color = "green" if dd_pct < 40 else ("yellow" if dd_pct < 80 else "red")

        strat_display = self.get_clean_strategy_display()
        curr_tf = self.active_timeframe
        sl_val = r.virtual_sl_points
        tp_val = r.virtual_tp_points

        tot_profit = sum(p.profit for p in positions)
        p_col = "bold green" if tot_profit >= 0 else "bold red"
        p_sign = "+" if tot_profit >= 0 else ""

        bal_str = f"${acc.balance:,.2f}" if acc else "$0.00"
        eq_str = f"${acc.equity:,.2f}" if acc else "$0.00"
        free_str = f"${acc.free_margin:,.2f}" if acc else "$0.00"
        mgn_lvl = f"{acc.margin_level:,.0f}%" if (acc and acc.margin > 0) else "SAFE"

        live_stats_grid = Table.grid(expand=True)
        live_stats_grid.add_column(ratio=6)
        live_stats_grid.add_column(ratio=4, justify="right")

        row1_left = Text.from_markup(
            f"[dim]SALDO:[/dim] [bold white]{bal_str}[/bold white]   "
            f"[dim]EKUITAS:[/dim] [bold white]{eq_str}[/bold white]   "
            f"[dim]FREE MARGIN:[/dim] [white]{free_str}[/white] ({mgn_lvl})   "
            f"[dim]MAX POS:[/dim] [white]{r.max_open_positions}[/white]"
        )
        row1_right = Text.from_markup(
            f"[dim]NET FLOATING P/L:[/dim] [{p_col}]{p_sign}${tot_profit:,.2f}[/{p_col}]"
        )
        live_stats_grid.add_row(row1_left, row1_right)

        row2_left = Text.from_markup(
            f"[dim]STRATEGI:[/dim] [bold yellow]{strat_display}[/bold yellow] [dim]({curr_tf})[/dim]   "
            f"[dim]Lot:[/dim] [bold white]{r.fixed_lot}[/bold white]   "
            f"[dim]V-SL:[/dim] [white]{sl_val}p[/white]   "
            f"[dim]V-TP:[/dim] [white]{tp_val}p[/white]   "
            f"[dim]Trail:[/dim] {t_info}"
        )
        row2_right = Text.from_markup(
            f"[dim]Circuit Breaker:[/dim] [{dd_color}]${daily_loss:,.1f}[/{dd_color}]/[red]${r.max_daily_loss:,.0f}[/red] "
            f"[{dd_color}][{dd_bar}][/{dd_color}] [yellow]{dd_pct:.0f}%[/yellow]"
        )
        live_stats_grid.add_row(row2_left, row2_right)

        live_hud_panel = Panel(live_stats_grid, box=box.ROUNDED, style="cyan")
        pos_table = self.render_positions_table(positions)
        controls_panel = self.render_controls(mode="live")

        term_h = max(20, self.console.size.height)
        opt = self.console.options
        try:
            h_header = len(list(self.console.render_lines(header, opt)))
            h_hud = len(list(self.console.render_lines(live_hud_panel, opt)))
            h_pos = len(list(self.console.render_lines(pos_table, opt)))
            h_ctrl = len(list(self.console.render_lines(controls_panel, opt)))
            used_lines = h_header + h_hud + h_pos + h_ctrl
            avail_for_logs = max(2, term_h - used_lines - 1)
        except Exception:
            avail_for_logs = 3

        logs_panel = self.render_logs(max_lines=avail_for_logs)
        return Group(header, live_hud_panel, pos_table, logs_panel, controls_panel)

    def render_ui(self) -> Group:
        """Assemble full UI screen according to the current active view (Overview vs Live)."""
        # If auto-trading is running and active_view is live, render live dashboard
        if self.active_view == "live":
            return self.render_live_view()
        return self.render_overview_view()

    async def interactive_manual_order(self, live: Live) -> None:
        """Pause Live UI to place manual order with confirmation."""
        with self._modal_session(live):
            self.console.clear()
            self.console.print("[bold cyan]══════════════ ORDER MANUAL CEPAT ══════════════[/bold cyan]\n")

            symbol = Prompt.ask("Masukkan Simbol", default=self.profile.symbols[0]).strip()
            
            # Show live market price if connected
            if self.controller.is_connected:
                tick = self.controller.backend.get_tick(symbol)
                if tick:
                    self.console.print(f"[dim]Harga Pasar Terkini: Bid [bold green]{tick.bid}[/bold green] / Ask [bold green]{tick.ask}[/bold green][/dim]\n")

            side = Prompt.ask("Pilih Aksi (BUY/SELL)", choices=["BUY", "SELL", "buy", "sell"], default="BUY").upper()
            lot_str = Prompt.ask("Volume / Lot", default=str(self.profile.risk.fixed_lot)).strip()
            sl_str = Prompt.ask("Stop Loss (0 = default virtual)", default="0").strip()
            tp_str = Prompt.ask("Take Profit (0 = default virtual)", default="0").strip()

            try:
                lot = float(lot_str)
                sl = float(sl_str)
                tp = float(tp_str)

                self.console.print(f"\n[bold]Konfirmasi Order:[/bold] [yellow]{side}[/yellow] {lot} lot pada [bold white]{symbol}[/bold white]")
                self.console.print(f"[dim]Stop Loss: {sl if sl > 0 else 'Virtual Auto'} | Take Profit: {tp if tp > 0 else 'Virtual Auto'}[/dim]")
                confirm = Prompt.ask("Kirim order ke broker sekarang? (Y/N)", default="Y").upper()
                if confirm != "Y":
                    self.console.print("[yellow]Order dibatalkan oleh pengguna.[/yellow]")
                    await asyncio.sleep(1.0)
                    return

                self.console.print(f"\n[cyan]Mengirim {side} {lot} {symbol}...[/cyan]")
                res = await self.controller.send_manual_order(symbol, side, lot, sl, tp)
                if res.ok:
                    self.console.print(f"[bold green]✔ Order #{res.ticket or res.order} berhasil dibuka![/bold green]")
                else:
                    self.console.print(f"[bold red]✖ Order gagal: {res.message}[/bold red]")
            except Exception as e:
                self.console.print(f"[bold red]Input tidak valid: {e}[/bold red]")
            await asyncio.sleep(1.2)

    async def interactive_close_all(self, live: Live) -> None:
        """Emergency direct close all open positions with confirmation."""
        with self._modal_session(live):
            positions = self.controller.backend.positions() if self.controller.is_connected else []
            self.console.clear()
            self.console.print("[bold red]══════════════ TUTUP SEMUA POSISI (EMERGENCY CLOSE ALL) ══════════════[/bold red]\n")
            if not positions:
                self.console.print("[yellow]Tidak ada posisi terbuka saat ini.[/yellow]")
                await asyncio.sleep(1.0)
                return

            tot_pnl = sum(p.profit for p in positions)
            p_col = "green" if tot_pnl >= 0 else "red"
            p_sign = "+" if tot_pnl >= 0 else ""
            self.console.print(f"Ditemukan [bold white]{len(positions)}[/bold white] posisi terbuka aktif.")
            self.console.print(f"Total Net Floating P/L: [{p_col}]{p_sign}${tot_pnl:,.2f}[/{p_col}]\n")

            confirm = Prompt.ask("[bold red]Apakah Anda yakin ingin menutup SEMUA posisi terbuka sekarang? (Y/N)[/bold red]", default="N").strip().upper()
            if confirm == "Y":
                self.console.print("\n[yellow]Mengirim perintah likuidasi massal ke broker...[/yellow]")
                await self.controller.emergency_close_all()
                self.console.print(f"[bold green]✔ Seluruh ({len(positions)}) posisi telah berhasil ditutup dan direkonsiliasi.[/bold green]")
                self.add_log(f"EMERGENCY CLOSE ALL: {len(positions)} posisi ditutup.")
            else:
                self.console.print("[yellow]Penutupan massal dibatalkan.[/yellow]")
            await asyncio.sleep(1.2)

    async def interactive_close_single(self, live: Live) -> None:
        """Close an individual position 1 per 1 by choosing its index or ticket."""
        with self._modal_session(live):
            positions = self.controller.backend.positions() if self.controller.is_connected else []
            self.console.clear()
            self.console.print("[bold magenta]══════════════ TUTUP POSISI 1 PER 1 ══════════════[/bold magenta]\n")
            if not positions:
                self.console.print("[yellow]Tidak ada posisi terbuka saat ini.[/yellow]")
                await asyncio.sleep(1.0)
                return

            table = Table(box=box.ROUNDED, header_style="bold magenta")
            table.add_column("No", style="bold yellow", width=4)
            table.add_column("Tiket", style="dim", width=12)
            table.add_column("Simbol", style="bold white", width=10)
            table.add_column("Aksi", justify="center", width=8)
            table.add_column("Volume", justify="right", width=8)
            table.add_column("Harga Buka", justify="right", width=12)
            table.add_column("Harga Kini", justify="right", width=12)
            table.add_column("Floating P/L", justify="right", width=14)

            for idx, p in enumerate(positions, 1):
                p_col = "green" if p.profit >= 0 else "red"
                p_sign = "+" if p.profit >= 0 else ""
                table.add_row(
                    str(idx),
                    f"#{p.ticket}",
                    p.symbol,
                    p.type,
                    f"{p.volume:.2f}",
                    f"{p.price_open:.5f}",
                    f"{p.price_current:.5f}",
                    f"[{p_col}]{p_sign}${p.profit:,.2f}[/{p_col}]"
                )

            self.console.print(table)
            self.console.print("[dim]Masukkan [bold white]0[/bold white] untuk batal.[/dim]\n")

            choice = Prompt.ask(f"Pilih nomor urut posisi (1-{len(positions)}) atau nomor tiket", default="1").strip()
            if choice in ("0", "batal", "q", "n"):
                return

            target_p = None
            if choice.isdigit():
                idx_val = int(choice)
                if 1 <= idx_val <= len(positions):
                    target_p = positions[idx_val - 1]
                else:
                    for p in positions:
                        if p.ticket == idx_val:
                            target_p = p
                            break

            if not target_p:
                self.console.print("[yellow]Pilihan tidak ditemukan.[/yellow]")
                await asyncio.sleep(1.0)
                return

            confirm = Prompt.ask(
                f"Tutup posisi #{target_p.ticket} {target_p.symbol} ({target_p.type} {target_p.volume} lot)? (Y/N)",
                default="Y",
            ).strip().upper()

            if confirm == "Y":
                self.console.print(f"[cyan]Menutup #{target_p.ticket}...[/cyan]")
                res = await asyncio.to_thread(
                    self.controller.backend.close_position,
                    target_p.ticket,
                    target_p.symbol,
                    target_p.volume,
                )
                if res.ok:
                    self.console.print(f"[bold green]✔ Posisi #{target_p.ticket} berhasil ditutup.[/bold green]")
                    self.add_log(f"POSISI DITUTUP: #{target_p.ticket} {target_p.symbol}")
                else:
                    self.console.print(f"[bold red]✖ Gagal menutup #{target_p.ticket}: {res.message}[/bold red]")
            else:
                self.console.print("[yellow]Dibatalkan.[/yellow]")
            await asyncio.sleep(1.0)

    async def interactive_start_wizard(self, live: Live) -> None:
        """Launch interactive start trading wizard dialog."""
        with self._modal_session(live):
            self.console.clear()
            self.console.print("[bold green]══════════════ PELUNCURAN SESI TRADING (START WIZARD) ══════════════[/bold green]\n")

            t_mode = getattr(self.profile, "trading_mode", "demo").upper()
            strat_display = self.get_clean_strategy_display()
            r = self.profile.risk

            summary_box = (
                f"[bold]Konfigurasi Sesi Aktif:[/bold]\n"
                f"  • Akun / Profil  : [bold white]{self.profile.profile_name}[/bold white] (Mode: [bold yellow]{t_mode}[/bold yellow] - {self.profile.backend.upper()})\n"
                f"  • Simbol Trading : [bold cyan]{', '.join(self.active_symbols)}[/bold cyan]\n"
                f"  • Strategi       : [bold yellow]{strat_display}[/bold yellow] ({self.active_timeframe})\n"
                f"  • Volume Lot     : [bold white]{r.fixed_lot}[/bold white] (Maksimal: {r.max_open_positions} posisi simultan)\n"
                f"  • Proteksi Risiko: SL {r.virtual_sl_points}p │ TP {r.virtual_tp_points}p │ Trailing {r.trail_start_points}p/{r.trail_step_points}p"
            )
            self.console.print(Panel(summary_box, box=box.ROUNDED, style="green"))

            self.console.print("[bold]PILIHAN TINDAKAN:[/bold]")
            self.console.print("  [bold green]1[/bold green] : Mulai Auto Trading Sekarang (Launch Engine & Masuk Live Dashboard)")
            self.console.print("  [bold cyan]2[/bold cyan] : Pilih / Ubah Simbol Pasar Aktif")
            self.console.print("  [bold blue]3[/bold blue] : Ganti Strategi Trading")
            self.console.print("  [bold magenta]4[/bold magenta] : Sesuaikan Lot & Parameter Risiko")
            self.console.print("  [bold white]0[/bold white] : Batal & Kembali ke Layar Utama\n")

            choice = Prompt.ask("Pilih tindakan (0-4)", default="1").strip()
            if choice == "1":
                self.console.print("\n[bold green]Meluncurkan Bot Trading Engine v3.1.0...[/bold green]")
                if not self.controller.is_connected:
                    await self.controller.connect()
                self.controller.start_auto_trading()
                self.active_view = "live"
                self.add_log(f"Auto Trading DIAKTIFKAN [{strat_display} ({self.active_timeframe})]")
                await asyncio.sleep(1.0)
            elif choice == "2":
                await self._menu_edit_market_symbols()
            elif choice == "3":
                await self._menu_choose_strategy()
            elif choice == "4":
                await self.interactive_risk_menu(live)
            else:
                self.console.print("[yellow]Peluncuran sesi dibatalkan.[/yellow]")
                await asyncio.sleep(0.5)

    async def interactive_position_manager(self, live: Live) -> None:
        """Pause Live UI to manage or close open positions."""
        with self._modal_session(live):
            positions = self.controller.backend.positions() if self.controller.is_connected else []
            self.console.clear()
            self.console.print("[bold cyan]══════════════ KELOLA POSISI TRADING ══════════════[/bold cyan]\n")

            if not positions:
                self.console.print("[yellow]Tidak ada posisi terbuka saat ini.[/yellow]")
                await asyncio.sleep(1.5)
                return

            for idx, p in enumerate(positions, 1):
                p_color = "green" if p.profit >= 0 else "red"
                p_sign = "+" if p.profit >= 0 else ""
                self.console.print(
                    f"  [{idx}] [white]#{p.ticket}[/white] | [bold]{p.symbol:<8}[/bold] | "
                    f"{p.type:<4} {p.volume:.2f} lot | Buka: {p.price_open:.5f} | "
                    f"P/L: [{p_color}]{p_sign}${p.profit:,.2f}[/{p_color}]"
                )

            self.console.print("\n[bold]PILIHAN TINDAKAN:[/bold]")
            self.console.print("  [bold red]1[/bold red] : Tutup SEMUA Posisi Terbuka Sekaligus (Emergency Close All)")
            self.console.print("  [bold cyan]2[/bold cyan] : Tutup Satu Posisi Berdasarkan Nomor Urut")
            self.console.print("  [bold white]0[/bold white] : Batal / Kembali")

            act = Prompt.ask("\nPilih tindakan (0-2)", default="0").strip()
            if act == "1":
                confirm = Prompt.ask(f"[bold red]Yakin ingin menutup SEMUA {len(positions)} posisi terbuka? (Y/N)[/bold red]", default="N").upper()
                if confirm == "Y":
                    self.console.print("[yellow]Menutup seluruh posisi...[/yellow]")
                    await self.controller.emergency_close_all()
                    self.console.print("[bold green]✔ Seluruh posisi telah ditutup.[/bold green]")
                    await asyncio.sleep(1.2)
            elif act == "2":
                num = Prompt.ask(f"Pilih nomor urut posisi (1-{len(positions)})", default="1").strip()
                if num.isdigit() and 1 <= int(num) <= len(positions):
                    target_p = positions[int(num) - 1]
                    confirm = Prompt.ask(f"Tutup posisi #{target_p.ticket} {target_p.symbol} ({target_p.type} {target_p.volume} lot)? (Y/N)", default="Y").upper()
                    if confirm == "Y":
                        res = await asyncio.to_thread(self.controller.backend.close_position, target_p.ticket, target_p.symbol, target_p.volume)
                        if res.ok:
                            self.console.print(f"[bold green]✔ Posisi #{target_p.ticket} berhasil ditutup.[/bold green]")
                        else:
                            self.console.print(f"[bold red]✖ Gagal menutup: {res.message}[/bold red]")
                        await asyncio.sleep(1.2)

    async def interactive_risk_menu(self, live: Live) -> None:
        """Pause Live UI to view and modify risk management safeguards with full explanations."""
        with self._modal_session(live):
            while True:
                self.console.clear()
                self.console.print("[bold cyan]══════════════ PENGATURAN RISIKO & PROTEKSI MODAL ══════════════[/bold cyan]\n")
                r = self.profile.risk

                cb_tripped = (
                    self.controller.engine
                    and self.controller.engine.risk_manager.circuit_breaker_tripped
                )
                cb_label = f"[bold red]TERKUNCI ({self.controller.engine.risk_manager.circuit_breaker_reason})[/bold red]" if cb_tripped else "[green]NORMAL (Aman)[/green]"

                self.console.print("[bold]Parameter Proteksi & Batas Risiko Aktif:[/bold]")
                self.console.print(f"  [bold cyan]1[/bold cyan] : Fixed Lot Per Order      : [bold white]{r.fixed_lot}[/bold white] [dim](Ukuran volume lot setiap posisi baru)[/dim]")
                self.console.print(f"  [bold cyan]2[/bold cyan] : Virtual Stop Loss        : [bold white]{r.virtual_sl_points} pts[/bold white] [dim](SL virtual lokal tidak terlihat oleh broker)[/dim]")
                self.console.print(f"  [bold cyan]3[/bold cyan] : Virtual Take Profit      : [bold white]{r.virtual_tp_points} pts[/bold white] [dim](Target profit virtual otomatis di level lokal)[/dim]")
                t_status = "[green]AKTIF[/green]" if r.trailing_enabled else "[red]NONAKTIF[/red]"
                self.console.print(f"  [bold cyan]4[/bold cyan] : Virtual Trailing Stop    : {t_status} [dim](Start: {r.trail_start_points} pts, Step: {r.trail_step_points} pts)[/dim]")
                self.console.print(f"  [bold cyan]5[/bold cyan] : Batas Rugi Harian (USD)  : [bold red]${r.max_daily_loss:,.2f}[/bold red] [dim](Circuit breaker auto-stop jika rugi harian tercapai)[/dim]")
                self.console.print(f"  [bold cyan]6[/bold cyan] : Maksimal Posisi Terbuka  : [bold white]{r.max_open_positions} order[/bold white] [dim](Batas maksimum trade aktif simultan)[/dim]")
                self.console.print(f"  [bold cyan]7[/bold cyan] : Batas Drawdown Maksimal  : [bold white]{r.max_drawdown_percent:.1f}%[/bold white] [dim](Kunci darurat jika ekuitas turun melampaui limit)[/dim]")
                self.console.print(f"  [bold cyan]8[/bold cyan] : Batas Minimum Margin     : [bold white]{r.min_margin_level:.1f}%[/bold white] [dim](Tolak order baru jika margin level di bawah ini)[/dim]")
                self.console.print(f"  [bold cyan]9[/bold cyan] : Circuit Breaker Lock     : {cb_label} [dim](Buka kunci darurat jika tripped)[/dim]")
                self.console.print("\n  [bold cyan]0[/bold cyan] : Simpan & Kembali ke Dashboard")

                choice = Prompt.ask("\nPilih nomor pengaturan yang ingin diubah (0-9)", default="0").strip()
                if choice == "0" or not choice:
                    save_profile(self.profile)
                    if self.controller.engine:
                        self.controller.engine.risk_manager.settings = self.profile.risk
                    self.console.print("[bold green]✔ Pengaturan risiko berhasil disimpan.[/bold green]")
                    await asyncio.sleep(0.8)
                    break
                elif choice == "1":
                    val = Prompt.ask("Masukkan ukuran lot (contoh: 0.01, 0.02)", default=str(r.fixed_lot)).strip()
                    try:
                        r.fixed_lot = max(0.01, float(val))
                    except Exception:
                        pass
                elif choice == "2":
                    val = Prompt.ask("Masukkan Virtual Stop Loss dalam points (0 = nonaktif)", default=str(r.virtual_sl_points)).strip()
                    if val.isdigit():
                        r.virtual_sl_points = int(val)
                elif choice == "3":
                    val = Prompt.ask("Masukkan Virtual Take Profit dalam points (0 = nonaktif)", default=str(r.virtual_tp_points)).strip()
                    if val.isdigit():
                        r.virtual_tp_points = int(val)
                elif choice == "4":
                    r.trailing_enabled = not r.trailing_enabled
                    if r.trailing_enabled:
                        start_val = Prompt.ask("Trailing Start (points profit minimal untuk aktivasi)", default=str(r.trail_start_points)).strip()
                        step_val = Prompt.ask("Trailing Step (points penguncian jarak trailing)", default=str(r.trail_step_points)).strip()
                        if start_val.isdigit():
                            r.trail_start_points = int(start_val)
                        if step_val.isdigit():
                            r.trail_step_points = int(step_val)
                elif choice == "5":
                    val = Prompt.ask("Masukkan batas rugi harian dalam USD (contoh: 50.0)", default=str(r.max_daily_loss)).strip()
                    try:
                        r.max_daily_loss = float(val)
                    except Exception:
                        pass
                elif choice == "6":
                    val = Prompt.ask("Masukkan batas maksimal order simultan", default=str(r.max_open_positions)).strip()
                    if val.isdigit():
                        r.max_open_positions = max(1, int(val))
                elif choice == "7":
                    val = Prompt.ask("Masukkan batas maksimal drawdown persen (%)", default=str(r.max_drawdown_percent)).strip()
                    try:
                        r.max_drawdown_percent = float(val)
                    except Exception:
                        pass
                elif choice == "8":
                    val = Prompt.ask("Masukkan batas minimum margin level (%)", default=str(r.min_margin_level)).strip()
                    try:
                        r.min_margin_level = float(val)
                    except Exception:
                        pass
                elif choice == "9":
                    if cb_tripped and self.controller.engine:
                        unlock = Confirm.ask("Buka kunci Circuit Breaker sekarang dan izinkan trading kembali?", default=True)
                        if unlock:
                            self.controller.engine.risk_manager.reset_circuit_breaker()
                            self.console.print("[bold green]✔ Circuit Breaker berhasil dibuka kembali![/bold green]")
                            await asyncio.sleep(1.0)
                    else:
                        self.console.print("[green]Circuit Breaker dalam status aman (tidak terkunci).[/green]")
                        await asyncio.sleep(1.0)

    async def interactive_strategy_menu(self, live: Live) -> None:
        """Pause Live UI to view strategy explanations and switch active strategy."""
        with self._modal_session(live):
            self.console.clear()
            self.console.print("[bold cyan]══════════════ KATALOG & PENJELASAN STRATEGI TRADING ══════════════[/bold cyan]\n")

            self.console.print(f"[dim]Strategi Aktif Saat Ini:[/dim] [bold yellow]{self.active_strategy_name}[/bold yellow]\n")

            registry = get_registry()
            strat_list = []
            for code, cls in registry.items():
                title = getattr(cls, "display_name", code)
                tf = getattr(cls, "recommended_timeframe", "M1/M5")
                desc = getattr(cls, "description", "")
                strat_list.append((code, title, tf, desc, cls))

            curr_code = self.active_strategy_code
            for idx, (code, title, tf, desc, _cls) in enumerate(strat_list, 1):
                curr_tag = " [bold green](Sedang Digunakan)[/bold green]" if code == curr_code else ""
                self.console.print(f"  [{idx}] [bold white]{title}[/bold white]{curr_tag}")
                self.console.print(f"      [dim]Kode:[/dim] [yellow]{code}[/yellow] │ [dim]Timeframe Rekomendasi:[/dim] [cyan]{tf}[/cyan]")
                if desc:
                    self.console.print(f"      [dim]{desc}[/dim]\n")
                else:
                    self.console.print()

            self.console.print("  [0] Batal / Kembali")
            choice = Prompt.ask(f"Pilih strategi baru (0-{len(strat_list)})", default="0").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(strat_list):
                selected_code, selected_title, rec_tf, _, strat_cls = strat_list[int(choice) - 1]
                self.profile.strategy = selected_code

                # Opsi sesuaikan timeframe ke rekomendasi strategi
                curr_tf = self.active_timeframe
                if rec_tf and curr_tf.upper() != rec_tf.upper():
                    adjust_tf = Confirm.ask(
                        f"Sesuaikan timeframe trading dari {curr_tf} ke rekomendasi strategi ({rec_tf})?",
                        default=True,
                    )
                    if adjust_tf:
                        self.profile.timeframe = rec_tf
                        self.console.print(f"[cyan]Timeframe disesuaikan ke: {rec_tf}[/cyan]")

                self.console.print(f"[bold green]✔ Strategi aktif diubah ke: {selected_title} ({selected_code})![/bold green]")
                if self.controller.engine:
                    new_strat = strat_cls()
                    self.controller.engine.set_strategy(new_strat)
                    self.add_log(f"Strategi diubah ke {self.controller.engine.strategy.display_name}")
                save_profile(self.profile)
                await asyncio.sleep(1.2)

    async def interactive_market_menu(self, live: Live) -> None:
        """Pause Live UI to select and configure trading markets / symbols via hotkey [K]."""
        with self._modal_session(live):
            await self._menu_select_market()

    async def _apply_symbols(self, new_symbols: List[str]) -> None:
        """Validate, normalize against broker, and persist updated trading symbols."""
        seen = set()
        clean: List[str] = []
        for s in new_symbols:
            s_clean = s.strip()
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                clean.append(s_clean)

        if not clean:
            self.console.print("[bold red]Daftar simbol tidak boleh kosong![/bold red]")
            await asyncio.sleep(1.2)
            return

        # Resolve against broker if connected
        if self.controller.is_connected and hasattr(self.controller.backend, "resolve_symbol"):
            resolved_list = []
            for s in clean:
                r = self.controller.backend.resolve_symbol(s)
                resolved_list.append(r if r else s)
            clean = resolved_list

        self.profile.symbols = clean
        if self.controller.engine and hasattr(self.controller.engine.strategy, "symbols"):
            self.controller.engine.strategy.symbols = clean

        # Clear tick cache to refresh ticker immediately
        self._tick_cache.clear()

        # Update controller and running bot engine
        self.controller.profile.symbols = clean
        if self.controller.engine:
            self.controller.engine.profile.symbols = clean

        # Ensure all symbols are selected in terminal MarketWatch
        if self.controller.is_connected and hasattr(self.controller.backend, "ensure_symbol"):
            for s in clean:
                try:
                    self.controller.backend.ensure_symbol(s)
                except Exception:
                    pass

        self.controller.dispatch_log(f"🎯 Market trading aktif diubah ke: {', '.join(clean)}")
        self.console.print(f"\n[bold green]✔ Market aktif berhasil disimpan:[/bold green] [bold white]{', '.join(clean)}[/bold white]")
        await asyncio.sleep(1.2)

    async def _menu_select_market(self) -> None:
        """Interactive modal menu for selecting trading symbols, presets, and broker search."""
        while True:
            self.console.clear()
            self.console.print("[bold cyan]══════════════ 🎯 MENU PILIH MARKET & SIMBOL TRADING ══════════════[/bold cyan]\n")

            # 1. Tampilkan market aktif saat ini
            self.console.print(f"[bold]Market Aktif Saat Ini ({len(self.profile.symbols)} simbol):[/bold]")
            for idx, sym in enumerate(self.profile.symbols, 1):
                tick = self._tick_cache.get(sym)
                if tick:
                    digits = 3 if ("xau" in sym.lower() or "jpy" in sym.lower()) else (2 if "btc" in sym.lower() else 5)
                    price_str = f"Bid: [green]{tick.bid:,.{digits}f}[/green] / Ask: [green]{tick.ask:,.{digits}f}[/green]"
                else:
                    price_str = "[dim](Menunggu tick kuotasi)[/dim]"
                self.console.print(f"  [bold white]{idx}.[/bold white] [bold cyan]{sym:<10}[/bold cyan] • {price_str}")

            self.console.print("\n[bold]⚡ PILIHAN PAKET PRESET CEPAT (1-Klik):[/bold]")
            self.console.print("  [bold cyan]1[/bold cyan] : [bold white]Emas & Logam Mulia[/bold white]      [dim]• XAUUSDm, XAGUSDm[/dim]")
            self.console.print("  [bold cyan]2[/bold cyan] : [bold white]Forex Major Top 4[/bold white]        [dim]• EURUSDm, GBPUSDm, USDJPYm, AUDUSDm[/dim]")
            self.console.print("  [bold cyan]3[/bold cyan] : [bold white]Forex Scalper Basket (5)[/bold white] [dim]• EURUSDm, GBPUSDm, USDJPYm, EURJPYm, GBPJPYm[/dim]")
            self.console.print("  [bold cyan]4[/bold cyan] : [bold white]Crypto Populer[/bold white]           [dim]• BTCUSDm, ETHUSDm, SOLUSDm[/dim]")
            self.console.print("  [bold cyan]5[/bold cyan] : [bold white]Index & Oil Global[/bold white]       [dim]• US30m, US500m, USOILm[/dim]")
            self.console.print("  [bold cyan]6[/bold cyan] : [bold white]Multi-Asset All-Star[/bold white]     [dim]• XAUUSDm, EURUSDm, BTCUSDm[/dim]")

            self.console.print("\n[bold]🔧 KUSTOMISASI & PENCARIAN MARKET:[/bold]")
            self.console.print("  [bold cyan]7[/bold cyan] : Cari & Tambah Simbol dari Broker (GOLD, JPY, BTC, OIL, USD, dll)")
            self.console.print("  [bold cyan]8[/bold cyan] : Ketik Manual Daftar Simbol (Pisahkan koma, misal: XAUUSDm, GBPJPYm)")
            self.console.print("  [bold cyan]9[/bold cyan] : Tambah 1 Simbol ke Daftar Aktif")
            self.console.print("  [bold cyan]10[/bold cyan]: Hapus 1 Simbol dari Daftar Aktif")
            self.console.print("  [bold cyan]11[/bold cyan]: Reset ke Default (XAUUSDm, EURUSDm, BTCUSDm)")
            self.console.print("\n  [bold cyan]0[/bold cyan] : Selesai & Kembali ke Dashboard")

            choice = Prompt.ask("\nPilih menu (0-11)", default="0").strip()
            if choice == "0" or not choice:
                break
            elif choice == "1":
                await self._apply_symbols(["XAUUSDm", "XAGUSDm"])
            elif choice == "2":
                await self._apply_symbols(["EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm"])
            elif choice == "3":
                await self._apply_symbols(["EURUSDm", "GBPUSDm", "USDJPYm", "EURJPYm", "GBPJPYm"])
            elif choice == "4":
                await self._apply_symbols(["BTCUSDm", "ETHUSDm", "SOLUSDm"])
            elif choice == "5":
                await self._apply_symbols(["US30m", "US500m", "USOILm"])
            elif choice == "6":
                await self._apply_symbols(["XAUUSDm", "EURUSDm", "BTCUSDm"])
            elif choice == "7":
                kw = Prompt.ask("Masukkan kata kunci pencarian (contoh: GOLD, JPY, BTC, OIL, USD)").strip()
                if not kw:
                    continue
                available_syms: List[str] = []
                if self.controller.is_connected and hasattr(self.controller.backend, "list_symbols"):
                    available_syms = self.controller.backend.list_symbols(limit=500)
                if not available_syms:
                    available_syms = [
                        "XAUUSDm", "XAGUSDm", "EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm",
                        "USDCADm", "USDCHFm", "NZDUSDm", "EURJPYm", "GBPJPYm", "BTCUSDm",
                        "ETHUSDm", "SOLUSDm", "XRPUSDm", "US30m", "US500m", "USTECm", "USOILm", "UKOILm"
                    ]

                kw_upper = kw.upper()
                aliases = {"GOLD": "XAU", "SILVER": "XAG", "MINYAK": "OIL"}
                search_term = aliases.get(kw_upper, kw_upper)

                matches = [s for s in available_syms if search_term in s.upper()]
                if not matches:
                    self.console.print(f"[yellow]Tidak ditemukan simbol yang cocok dengan '{kw}'.[/yellow]")
                    await asyncio.sleep(1.5)
                    continue

                self.console.print(f"\n[bold cyan]Ditemukan {len(matches)} simbol cocok:[/bold cyan]")
                display_matches = matches[:15]
                for m_idx, m_sym in enumerate(display_matches, 1):
                    in_active = " [green](Sudah Aktif)[/green]" if m_sym in self.profile.symbols else ""
                    self.console.print(f"  [{m_idx}] [bold white]{m_sym:<14}[/bold white]{in_active}")

                sel = Prompt.ask(f"\nPilih nomor simbol untuk ditambahkan (1-{len(display_matches)}, 0 = batal)", default="0").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(display_matches):
                    chosen_sym = display_matches[int(sel) - 1]
                    if chosen_sym not in self.profile.symbols:
                        new_syms = list(self.profile.symbols) + [chosen_sym]
                        await self._apply_symbols(new_syms)
                    else:
                        self.console.print(f"[yellow]Simbol {chosen_sym} sudah ada di daftar aktif.[/yellow]")
                        await asyncio.sleep(1.2)
            elif choice == "8":
                curr_str = ", ".join(self.profile.symbols)
                val = Prompt.ask("Masukkan daftar simbol pasar (pisahkan koma)", default=curr_str).strip()
                if val:
                    new_syms = [s.strip() for s in val.split(",") if s.strip()]
                    await self._apply_symbols(new_syms)
            elif choice == "9":
                val = Prompt.ask("Masukkan 1 nama simbol baru yang ingin ditambahkan (contoh: GBPJPYm)").strip()
                if val:
                    new_syms = list(self.profile.symbols) + [val]
                    await self._apply_symbols(new_syms)
            elif choice == "10":
                if len(self.profile.symbols) <= 1:
                    self.console.print("[bold red]Harus menyisakan minimal 1 simbol aktif![/bold red]")
                    await asyncio.sleep(1.2)
                    continue
                self.console.print("\nPilih nomor simbol yang ingin dihapus:")
                for s_idx, s_name in enumerate(self.profile.symbols, 1):
                    self.console.print(f"  [{s_idx}] [white]{s_name}[/white]")
                del_choice = Prompt.ask(f"Pilih nomor (1-{len(self.profile.symbols)}, 0 = batal)", default="0").strip()
                if del_choice.isdigit() and 1 <= int(del_choice) <= len(self.profile.symbols):
                    removed = self.profile.symbols[int(del_choice) - 1]
                    new_syms = [s for idx, s in enumerate(self.profile.symbols) if idx != int(del_choice) - 1]
                    await self._apply_symbols(new_syms)
                    self.console.print(f"[green]Simbol {removed} berhasil dihapus.[/green]")
                    await asyncio.sleep(1.0)
            elif choice == "11":
                await self._apply_symbols(["XAUUSDm", "EURUSDm", "BTCUSDm"])

    async def interactive_help_menu(self, live: Live) -> None:
        """Pause Live UI to display keybindings, indicators explanation, and glossary."""
        with self._modal_session(live):
            self.console.clear()
            self.console.print("[bold cyan]══════════════ PANDUAN PENGGUNA & GLOSARIUM FUNGSI ══════════════[/bold cyan]\n")

            self.console.print("[bold]1. Navigasi & Pintasan Keyboard (Hotkeys):[/bold]")
            self.console.print("  [bold green]S[/bold green] : Start / Stop Auto Trading — Mengaktifkan/menonaktifkan evaluasi order otomatis.")
            self.console.print("  [bold cyan]M[/bold cyan] : Order Manual Cepat — Form buka posisi BUY/SELL instan dengan validasi lot broker.")
            self.console.print("  [bold red]C[/bold red] : Kelola Posisi — Menu tutup satu posisi terpilih atau tutup semua (Emergency Close All).")
            self.console.print("  [bold green]K[/bold green] : Pilih Market / Simbol — Menu pilih pasar trading (Gold, Forex, Crypto, Oil, Index, Custom).")
            self.console.print("  [bold yellow]T[/bold yellow] : Mode Trading — Beralih antara REAL (dana riil), DEMO (latihan), dan SIMULASI (paper virtual).")
            self.console.print("  [bold magenta]R[/bold magenta] : Pengaturan Risiko — Atur Virtual SL/TP, Trailing Stop, Max Daily Loss, dan Margin.")
            self.console.print("  [bold blue]E[/bold blue] : Pilih Strategi — Katalog strategi bawaan dengan penjelasan formula dan timeframe.")
            self.console.print("  [bold yellow]P[/bold yellow] : Menu Koneksi & Login — Beralih akun, wizard setup Native MT5 atau Remote MCP.")
            self.console.print("  [bold white]L[/bold white] : Clear Log — Membersihkan tampilan log aktivitas pada dashboard.")
            self.console.print("  [bold white]Q[/bold white] : Keluar Bersih (Graceful Exit) — Menutup sesi aman dan mengembalikan terminal.\n")

            self.console.print("[bold]2. Glosarium & Arti Fitur Proteksi Modal:[/bold]")
            self.console.print("  • [cyan]Virtual SL / TP[/cyan] : Level stop loss/take profit yang dipantau lokal oleh bot. Broker tidak")
            self.console.print("    mengetahui posisi SL Anda, melindungi akun dari praktik pelebaran spread / stop-hunting.")
            self.console.print("  • [cyan]Dynamic Trailing Stop[/cyan] : Mengunci profit saat harga bergerak untung, otomatis menggeser")
            self.console.print("    garis stop loss ke atas/bawah mengikuti puncak harga berjarak trailing step.")
            self.console.print("  • [cyan]Emergency Circuit Breaker[/cyan] : Pengaman darurat. Jika kerugian harian atau drawdown")
            self.console.print("    melampaui batas maksimal, bot otomatis mengunci trading untuk melindungi sisa saldo.")
            self.console.print("  • [cyan]Dual-Backend[/cyan] : Mendukung [green]Native MT5[/green] (koneksi terminal lokal) dan [yellow]Remote MCP[/yellow]")
            self.console.print("    (koneksi via JSON-RPC untuk server VPS Linux tanpa terminal desktop).\n")

            Prompt.ask("Tekan Enter untuk kembali ke dashboard")

    async def interactive_connection_menu(self, live: Live) -> None:
        """Pause Live UI to manage connection methods (Native MT5 / Remote MCP) and profiles."""
        with self._modal_session(live):
            while True:
                self.console.clear()
                self.console.print("[bold cyan]══════════════ SETUP KONEKSI & LOGIN (NATIVE MT5 & MCP) ══════════════[/bold cyan]\n")
                
                backend_type = self.profile.backend.upper()
                t_mode = getattr(self.profile, "trading_mode", "demo").upper()
                mode_color = "red" if t_mode == "REAL" else ("yellow" if t_mode == "DEMO" else "cyan")
                self.console.print(f"[dim]Profil Aktif :[/dim] [bold white]{self.profile.profile_name}[/bold white]")
                self.console.print(f"[dim]Mode Trading :[/dim] [{mode_color}][{t_mode}][/{mode_color}]")
                b_color = "bold green" if backend_type == "NATIVE" else "bold yellow"
                self.console.print(f"[dim]Metode Login :[/dim] [{b_color}]{backend_type}[/{b_color}]")
                if self.profile.backend == "mcp":
                    self.console.print(f"[dim]MCP Endpoint :[/dim] [white]{self.profile.mcp_url}[/white]")
                    self.console.print(f"[dim]MCP API Key  :[/dim] [white]{mask_token(self.profile.mcp_api_key) or '(Tanpa API Key)'}[/white]")
                elif t_mode == "SIMULASI":
                    self.console.print("[dim]Engine Server:[/dim] [cyan]Paper Trading Engine (Simulasi Virtual)[/cyan]")
                else:
                    self.console.print(f"[dim]Login ID MT5 :[/dim] [white]{self.profile.login or '(Auto/Default Terminal)'}[/white]")
                    self.console.print(f"[dim]Broker Server:[/dim] [white]{self.profile.server}[/white]")
                    self.console.print(f"[dim]MT5 Password :[/dim] [white]{mask_token(self.profile.password) or '(Disimpan di Terminal)'}[/white]")

                self.console.print("\n[bold]PILIHAN MENU KONEKSI & MODE:[/bold]")
                self.console.print("  [bold cyan]1[/bold cyan] : Beralih / Pilih Profil Tersimpan")
                self.console.print("  [bold cyan]2[/bold cyan] : Tambah Profil Baru ([green]Native MT5[/green] atau [yellow]Remote MCP Gateway[/yellow])")
                self.console.print("  [bold cyan]3[/bold cyan] : Edit Kredensial Profil Aktif (Ganti Metode / Password / URL)")
                self.console.print("  [bold cyan]4[/bold cyan] : Uji Coba Koneksi (Ping Latency & Diagnostic Report)")
                self.console.print("  [bold cyan]5[/bold cyan] : [bold yellow]Beralih Mode Trading ([red]Real[/red] / [yellow]Demo[/yellow] / [cyan]Simulasi[/cyan])[/bold yellow]")
                self.console.print("\n  [bold cyan]0[/bold cyan] : Selesai & Kembali ke Dashboard")

                choice = Prompt.ask("\nPilih menu (0-5)", default="0").strip()
                if choice == "0" or not choice:
                    break
                elif choice == "1":
                    await self._menu_switch_profile()
                elif choice == "2":
                    await self._menu_add_profile()
                elif choice == "3":
                    await self._menu_edit_credentials()
                elif choice == "4":
                    await self._menu_test_connection()
                elif choice == "5":
                    await self._menu_change_mode()

    async def interactive_mode_menu(self, live: Live) -> None:
        """Pause Live UI to switch between Real, Demo, and Simulation modes via hotkey [T]."""
        with self._modal_session(live):
            await self._menu_change_mode()

    async def _menu_change_mode(self) -> None:
        """Interactive modal menu for switching Real, Demo, and Simulation modes."""
        self.console.clear()
        self.console.print("[bold cyan]══════════════ PILIH MODE LINGKUNGAN TRADING ══════════════[/bold cyan]\n")

        curr_mode = getattr(self.profile, "trading_mode", "demo").lower()
        if curr_mode == "real":
            m_badge = "[bold white on #d50000] 🔥 REAL (MODAL NYATA) [/bold white on #d50000]"
        elif curr_mode == "simulasi":
            m_badge = "[bold black on #00e5ff] 🎮 SIMULASI (PAPER) [/bold black on #00e5ff]"
        else:
            m_badge = "[bold black on #ffd600] 🧪 DEMO (BROKER) [/bold black on #ffd600]"

        self.console.print(f"[dim]Profil Aktif :[/dim] [bold white]{self.profile.profile_name}[/bold white]")
        self.console.print(f"[dim]Mode Saat Ini:[/dim] {m_badge}\n")

        self.console.print("  [bold cyan]1[/bold cyan] : [bold red]REAL[/bold red]     — Akun Nyata MT5 Broker (⚠️ Peringatan: Memakai Dana Riil Broker)")
        self.console.print("  [bold cyan]2[/bold cyan] : [bold yellow]DEMO[/bold yellow]     — Akun Latihan MT5 Broker (Bebas Risiko Modal)")
        self.console.print("  [bold cyan]3[/bold cyan] : [bold cyan]SIMULASI[/bold cyan] — Paper Trading Virtual Lokal (Offline Tanpa Perlu MT5)\n")
        self.console.print("  [bold cyan]0[/bold cyan] : Batal / Kembali")

        choice = Prompt.ask("\nPilih nomor mode (0-3)", default="0").strip()
        new_mode: Optional[str] = None
        if choice == "1":
            confirm = Prompt.ask(
                "[bold red]⚠️ PERINGATAN: Anda memilih MODE REAL dengan dana nyata.[/bold red] Yakin lanjutkan? (y/N)",
                default="n",
            ).strip().lower()
            if confirm in ("y", "ya", "yes"):
                new_mode = "real"
        elif choice == "2":
            new_mode = "demo"
        elif choice == "3":
            new_mode = "simulasi"

        if new_mode and new_mode != curr_mode:
            self.profile.trading_mode = new_mode
            save_profile(self.profile)
            self.console.print(f"\n[bold green]✔ Mode trading berhasil diubah ke {new_mode.upper()}![/bold green]")
            self.console.print("[dim]Menyambungkan controller ke mode baru...[/dim]")
            await self.controller.disconnect()
            self.controller = TradeController(self.profile)
            self.controller.add_log_listener(self.add_log)
            await self.controller.connect()
            await asyncio.sleep(1.2)

    async def _menu_switch_profile(self) -> None:
        self.console.clear()
        self.console.print("[bold cyan]══════════════ PILIH PROFIL AKUN ══════════════[/bold cyan]\n")
        all_profiles = list_profiles()
        if not all_profiles:
            self.console.print("[yellow]Belum ada profil tersimpan.[/yellow]")
            await asyncio.sleep(1.2)
            return

        for idx, p_name in enumerate(all_profiles, 1):
            p_obj = load_profile(p_name)
            curr_tag = " [bold green](Aktif)[/bold green]" if p_name == self.profile.profile_name else ""
            b_tag = f"[{p_obj.backend.upper()}]"
            self.console.print(f"  [{idx}] [white]{p_name:<18}[/white] {b_tag:<10} {curr_tag}")

        self.console.print("\n  [0] Batal / Kembali")
        choice = Prompt.ask("Pilih nomor profil", default="0").strip()
        if choice.isdigit() and int(choice) > 0 and int(choice) <= len(all_profiles):
            selected = all_profiles[int(choice) - 1]
            self.profile = load_profile(selected)
            self.console.print(f"[green]Menghubungkan ke profil: {selected}...[/green]")
            await self.controller.disconnect()
            self.controller = TradeController(self.profile)
            self.controller.add_log_listener(self.add_log)
            await self.controller.connect()
            await asyncio.sleep(1.0)

    async def _menu_add_profile(self) -> None:
        self.console.clear()
        self.console.print("[bold cyan]══════════════ TAMBAH PROFIL KONEKSI BARU ══════════════[/bold cyan]\n")

        p_name = Prompt.ask("1. Nama Profil Baru (misal: Exness-Real-01)").strip()
        if not p_name:
            return

        self.console.print("\n[bold]2. Pilih Metode Koneksi Broker:[/bold]")
        self.console.print("  [bold green]1[/bold green] : Native MT5 (IPC langsung ke Desktop Terminal MetaTrader 5) [Rekomendasi]")
        self.console.print("  [bold yellow]2[/bold yellow] : Remote MCP Gateway (Model Context Protocol JSON-RPC HTTP) [VPS/Linux]")
        b_choice = Prompt.ask("Pilih metode koneksi (1-2)", default="1").strip()

        backend = "mcp" if b_choice == "2" else "native"
        login = 0
        password = ""
        server = "Exness-MT5Trial"
        path = ""
        mcp_url = "http://127.0.0.1:8000/mcp"
        mcp_api_key = ""

        if backend == "native":
            self.console.print("\n[bold]Konfigurasi Akun MetaTrader 5 (Native):[/bold]")
            login_str = Prompt.ask("Nomor Akun MT5 (Login ID, misal 12345678, 0 = default terminal)", default="0").strip()
            login = int(login_str) if login_str.isdigit() else 0
            if login > 0:
                password = Prompt.ask("Password Akun MT5 (akan dienkripsi)", password=True).strip()
                server = Prompt.ask("Nama Server Broker (misal Exness-MT5Trial / Exness-Real)", default="Exness-MT5Trial").strip()
            path = Prompt.ask("Path file terminal64.exe (tekan enter untuk auto-detect)", default="").strip()
        else:
            self.console.print("\n[bold]Konfigurasi Remote MCP Gateway:[/bold]")
            mcp_url = Prompt.ask("Endpoint URL MCP Server", default="http://127.0.0.1:8000/mcp").strip()
            mcp_api_key = Prompt.ask("MCP Bearer API Key (opsional)", password=True).strip()

        symbols_str = Prompt.ask("\n3. Simbol Pasar Trading (pisahkan koma)", default="XAUUSDm, EURUSDm").strip()
        symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
        timeframe = Prompt.ask("4. Timeframe Trading", choices=["M1", "M5", "M15", "M30", "H1", "H4", "D1"], default="M5").upper()
        
        self.console.print("\n[bold]5. Pilih Strategi Trading Bawaan:[/bold]")
        registry = get_registry()
        reg_keys = list(registry.keys())
        for idx, k in enumerate(reg_keys, 1):
            s_name = getattr(registry[k], "display_name", k)
            s_tf = getattr(registry[k], "recommended_timeframe", "")
            tf_badge = f"[{s_tf}] " if s_tf else ""
            self.console.print(f"  [{idx}] {tf_badge}{s_name} ({k})")
        s_choice = Prompt.ask(f"Pilih strategi (1-{len(reg_keys)})", default="1").strip()
        if s_choice.isdigit() and 1 <= int(s_choice) <= len(reg_keys):
            strategy = reg_keys[int(s_choice) - 1]
        else:
            strategy = "fast_gold_scalper"

        new_prof = AccountProfile(
            profile_name=p_name,
            backend=backend,
            login=login,
            password=password,
            server=server,
            path=path,
            mcp_url=mcp_url,
            mcp_api_key=mcp_api_key,
            symbols=symbols,
            timeframe=timeframe,
            strategy=strategy,
        )
        saved_file = save_profile(new_prof)
        self.console.print(f"\n[bold green]✔ Profil '{p_name}' berhasil disimpan ke {saved_file.name}![/bold green]")

        activate = Prompt.ask("\nBeralih dan hubungkan ke profil baru ini sekarang? (Y/N)", default="Y").upper()
        if activate == "Y":
            self.profile = new_prof
            await self.controller.disconnect()
            self.controller = TradeController(self.profile)
            self.controller.add_log_listener(self.add_log)
            await self.controller.connect()
        await asyncio.sleep(1.2)

    async def _menu_edit_credentials(self) -> None:
        self.console.clear()
        self.console.print(f"[bold cyan]══════════════ EDIT KREDENSIAL [{self.profile.profile_name}] ══════════════[/bold cyan]\n")

        b_now = self.profile.backend
        self.console.print(f"[1] Ganti Metode Backend      : [white]{b_now.upper()}[/white]")
        if b_now == "native":
            self.console.print(f"[2] Edit Nomor Akun Login    : [white]{self.profile.login}[/white]")
            self.console.print(f"[3] Edit Password MT5        : [white]{mask_token(self.profile.password)}[/white]")
            self.console.print(f"[4] Edit Server Broker       : [white]{self.profile.server}[/white]")
            self.console.print(f"[5] Edit Path Terminal       : [white]{self.profile.path or '(Auto)'}[/white]")
        else:
            self.console.print(f"[2] Edit Endpoint MCP URL    : [white]{self.profile.mcp_url}[/white]")
            self.console.print(f"[3] Edit MCP API Key / Token : [white]{mask_token(self.profile.mcp_api_key)}[/white]")

        self.console.print(f"[6] Edit Simbol Pasar        : [white]{', '.join(self.profile.symbols)}[/white]")
        self.console.print(f"[7] Edit Timeframe           : [white]{self.profile.timeframe}[/white]")
        self.console.print("\n[0] Batal / Kembali")
        e_choice = Prompt.ask("Pilih nomor yang ingin diubah (0-7)", default="0").strip()

        if e_choice == "0" or not e_choice:
            return

        if e_choice == "1":
            new_b = "mcp" if b_now == "native" else "native"
            self.profile.backend = new_b
            self.console.print(f"[yellow]Metode diubah ke: {new_b.upper()}[/yellow]")
            await asyncio.sleep(1.0)
        elif e_choice == "2":
            if b_now == "native":
                val = Prompt.ask("Nomor Akun Login MT5", default=str(self.profile.login)).strip()
                if val.isdigit():
                    self.profile.login = int(val)
            else:
                self.profile.mcp_url = Prompt.ask("Endpoint MCP URL", default=self.profile.mcp_url).strip()
        elif e_choice == "3":
            if b_now == "native":
                self.profile.password = Prompt.ask("Password MT5 Baru", password=True).strip()
            else:
                self.profile.mcp_api_key = Prompt.ask("MCP API Key Baru", password=True).strip()
        elif e_choice == "4" and b_now == "native":
            self.profile.server = Prompt.ask("Nama Server Broker", default=self.profile.server).strip()
        elif e_choice == "5" and b_now == "native":
            self.profile.path = Prompt.ask("Path terminal64.exe", default=self.profile.path).strip()
        elif e_choice == "6":
            syms_val = Prompt.ask("Masukkan simbol pasar (pisahkan koma)", default=", ".join(self.profile.symbols)).strip()
            self.profile.symbols = [s.strip() for s in syms_val.split(",") if s.strip()]
        elif e_choice == "7":
            self.profile.timeframe = Prompt.ask("Pilih Timeframe", choices=["M1", "M5", "M15", "M30", "H1", "H4", "D1"], default=self.profile.timeframe).upper()

        save_profile(self.profile)
        self.console.print("[bold green]✔ Perubahan kredensial disimpan. Menyambung ulang...[/bold green]")
        await self.controller.disconnect()
        self.controller = TradeController(self.profile)
        self.controller.add_log_listener(self.add_log)
        await self.controller.connect()
        await asyncio.sleep(1.2)

    async def _menu_test_connection(self) -> None:
        self.console.clear()
        self.console.print("[bold cyan]══════════════ UJI COBA KONEKSI & DIAGNOSTIK ══════════════[/bold cyan]\n")
        self.console.print(f"Menguji koneksi ke broker via mode [bold]{self.profile.backend.upper()}[/bold]...")

        diag = await self.controller.test_connection_diagnostics()

        res_table = Table(title="Hasil Diagnostik Koneksi", box=box.ROUNDED)
        res_table.add_column("Parameter", style="cyan")
        res_table.add_column("Status / Nilai", style="bold white")

        status_style = "bold green" if diag.get("ok") else "bold red"
        status_label = "TERHUBUNG (OK)" if diag.get("ok") else "GAGAL"

        res_table.add_row("Status Koneksi", f"[{status_style}]{status_label}[/{status_style}]")
        res_table.add_row("Metode Backend", diag.get("backend", "N/A"))
        res_table.add_row("Latensi Ping", f"{diag.get('latency_ms', 0)} ms")
        res_table.add_row("Server", str(diag.get("server", self.profile.server)))
        res_table.add_row("Login Akun", str(diag.get("login", self.profile.login)))
        res_table.add_row("Tipe Akun", str(diag.get("account_type", "N/A")))
        res_table.add_row("Saldo Terbaca", f"${diag.get('balance', 0.0):,.2f}")
        res_table.add_row("Izin Trading", "YA (Diizinkan)" if diag.get("trade_allowed") else "TIDAK (Investor/Read-only)")
        res_table.add_row("Pesan Sistem", str(diag.get("message", "")))

        self.console.print(res_table)
        # Reconnect controller back to normal operation
        await self.controller.connect()
        Prompt.ask("\nTekan Enter untuk kembali ke menu")

    async def run(self) -> None:
        """Main execution coroutine."""
        setup_windows_console()
        set_windows_cursor_visible(False)
        await self.controller.connect()
        mute_console_logging()

        loop = asyncio.get_running_loop()
        def _handle_signal():
            self.stop_event.set()

        try:
            loop.add_signal_handler(signal.SIGINT, _handle_signal)
            loop.add_signal_handler(signal.SIGTERM, _handle_signal)
        except (NotImplementedError, AttributeError):
            pass

        try:
            with Live(
                self.render_ui(),
                console=self.console,
                screen=self.screen,
                auto_refresh=False,
                vertical_overflow="crop",
            ) as live:
                live.refresh()
                last_render_time = time.time()
                self._dirty = False

                while not self.stop_event.is_set():
                    # Dynamic console resize / maximize detection for zero-distortion layout
                    curr_size = (self.console.size.width, self.console.size.height)
                    if curr_size != self._last_console_size:
                        self._last_console_size = curr_size
                        self.console.clear()
                        if sys.platform == "win32":
                            try:
                                sys.stdout.write("\033[2J\033[H")
                                sys.stdout.flush()
                            except Exception:
                                pass
                        self._dirty = True

                    key = poll_key()
                    if key:
                        if key == "s":
                            if self.active_view == "live" and (self.controller.engine and self.controller.engine.auto_trading_enabled):
                                self.controller.stop_auto_trading()
                                self.active_view = "overview"
                                self.add_log("Auto Trading DIHENTIKAN oleh pengguna (Kembali ke Standby).")
                                self._dirty = True
                            else:
                                await self.interactive_start_wizard(live)
                                self._dirty = True
                        elif key == "v":
                            if self.active_view == "overview":
                                self.active_view = "live"
                            else:
                                self.active_view = "overview"
                            self.add_log(f"Tampilan dialihkan ke: {self.active_view.upper()}")
                            self._dirty = True
                        elif key == "c":
                            await self.interactive_close_all(live)
                            self._dirty = True
                        elif key == "x":
                            await self.interactive_close_single(live)
                            self._dirty = True
                        elif key == "a":
                            self.refresh_market_recommendations()
                            self.add_log("Scanner pasar diperbarui secara manual.")
                            self._dirty = True
                        elif key == "m":
                            await self.interactive_manual_order(live)
                            self._dirty = True
                        elif key in ("k", "w"):
                            await self.interactive_market_menu(live)
                            self._dirty = True
                        elif key == "t":
                            await self.interactive_mode_menu(live)
                            self._dirty = True
                        elif key == "r":
                            await self.interactive_risk_menu(live)
                            self._dirty = True
                        elif key == "e":
                            await self.interactive_strategy_menu(live)
                            self._dirty = True
                        elif key == "p":
                            await self.interactive_connection_menu(live)
                            self._dirty = True
                        elif key in ("h", "?"):
                            await self.interactive_help_menu(live)
                            self._dirty = True
                        elif key == "l":
                            self.logs.clear()
                            self._dirty = True
                        elif key == "q":
                            self.stop_event.set()
                            break

                    now = time.time()
                    if self._dirty or (now - last_render_time >= 0.8):
                        live.update(self.render_ui(), refresh=True)
                        last_render_time = now
                        self._dirty = False

                    await asyncio.sleep(0.04)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            set_windows_cursor_visible(True)
            unmute_console_logging()
            await self.controller.disconnect()
            self.console.print("\n[bold green]✔ Raptech AutoTrade berhenti dengan aman. Sampai jumpa![/bold green]")


async def run_light_app(
    profile: Optional[str] = None,
    inline: bool = True,
    mode_override: Optional[str] = None,
) -> None:
    """Entry point for ultra-light terminal UI."""
    setup_windows_console()
    app = LightAutotradeApp(profile_name=profile, screen=not inline, mode_override=mode_override)
    await app.run()
