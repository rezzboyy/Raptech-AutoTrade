from __future__ import annotations

"""
Raptech Autotrade CLI — Typer Subcommands.
Provides discrete command line operations (status, positions, order, close, backup, export).
"""

import asyncio
from datetime import datetime
import os
from pathlib import Path
import shutil
from typing import Optional
import zipfile

from rich import box
from rich.console import Console
from rich.table import Table
import typer

from backend.base import Candle
from core.config_store import AccountProfile, list_profiles, load_profile, save_profile
from core.secure_store import mask_token
from core.controller import TradeController
from core.logger import get_logger

logger = get_logger("cli.commands")
console = Console()
app = typer.Typer(help="Raptech Autotrade CLI — Algorithmic MT5 Trading Tool")


@app.command()
def status(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil akun"),
) -> None:
    """Tampilkan status akun, saldo, equity, dan posisi saat ini lalu keluar."""
    prof = load_profile(profile)
    console.print(f"[bold cyan]Memeriksa status akun untuk profil: [white]{prof.profile_name}[/white]...[/bold cyan]")

    controller = TradeController(prof)
    async def _do_status():
        ok = await controller.connect()
        if not ok:
            console.print("[bold red]Gagal terhubung ke broker.[/bold red]")
            return

        acc = await asyncio.to_thread(controller.backend.account_info)
        positions = await asyncio.to_thread(controller.backend.positions)
        telemetry = controller.get_telemetry()
        await controller.disconnect()

        # Render Table
        table = Table(title=f"Ringkasan Akun MT5 ({prof.server})", box=box.ROUNDED)
        table.add_column("Parameter", style="cyan")
        table.add_column("Nilai", style="bold white")

        acc_type = acc.account_type if acc else "N/A"
        bal_str = (
            f"{acc.balance:,.2f} {acc.currency} (≈ ${acc.balance/100:,.2f} USD)"
            if acc and getattr(acc, "is_cent", False)
            else (f"${acc.balance:,.2f}" if acc and acc.currency == "USD" else (f"{acc.balance:,.2f} {acc.currency}" if acc else "N/A"))
        )
        eq_str = (
            f"{acc.equity:,.2f} {acc.currency} (≈ ${acc.equity/100:,.2f} USD)"
            if acc and getattr(acc, "is_cent", False)
            else (f"${acc.equity:,.2f}" if acc and acc.currency == "USD" else (f"{acc.equity:,.2f} {acc.currency}" if acc else "N/A"))
        )
        mgn_str = (
            f"{acc.margin:,.2f} {acc.currency}"
            if acc and acc.currency != "USD"
            else (f"${acc.margin:,.2f}" if acc else "N/A")
        )
        fm_str = (
            f"{acc.free_margin:,.2f} {acc.currency}"
            if acc and acc.currency != "USD"
            else (f"${acc.free_margin:,.2f}" if acc else "N/A")
        )

        table.add_row("Login MT5", str(acc.login) if acc else "N/A")
        table.add_row("Tipe Akun", acc_type)
        table.add_row("Saldo (Balance)", bal_str)
        table.add_row("Ekuitas (Equity)", eq_str)
        table.add_row("Margin Terpakai", mgn_str)
        table.add_row("Free Margin", fm_str)
        table.add_row("Margin Level", f"{acc.margin_level:,.1f}%" if acc and acc.margin > 0 else "N/A")
        table.add_row("Posisi Terbuka", str(len(positions)))
        table.add_row("RAM Bot", f"{telemetry.ram_mb} MB")

        console.print(table)

        if positions:
            p_table = Table(title="Posisi Terbuka Saat Ini", box=box.SIMPLE_HEAVY)
            p_table.add_column("Ticket", justify="right")
            p_table.add_column("Symbol")
            p_table.add_column("Side")
            p_table.add_column("Volume", justify="right")
            p_table.add_column("Open Price", justify="right")
            p_table.add_column("Profit", justify="right")
            for p in positions:
                side_str = f"[green]{p.type}[/green]" if p.type == "BUY" else f"[red]{p.type}[/red]"
                p_style = "green" if p.profit >= 0 else "red"
                p_table.add_row(
                    f"#{p.ticket}",
                    p.symbol,
                    side_str,
                    f"{p.volume:.2f}",
                    f"{p.price_open:.5f}",
                    f"[{p_style}]${p.profit:,.2f}[/{p_style}]",
                )
            console.print(p_table)

    asyncio.run(_do_status())


@app.command()
def positions(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil akun"),
) -> None:
    """Tampilkan daftar detail seluruh posisi terbuka."""
    prof = load_profile(profile)
    controller = TradeController(prof)

    async def _do():
        ok = await controller.connect()
        if not ok:
            console.print("[bold red]Gagal terhubung ke broker.[/bold red]")
            return
        pos = await asyncio.to_thread(controller.backend.positions)
        await controller.disconnect()

        if not pos:
            console.print("[yellow]Tidak ada posisi terbuka saat ini.[/yellow]")
            return

        table = Table(title="Daftar Posisi Terbuka", box=box.ROUNDED)
        table.add_column("Ticket", justify="right")
        table.add_column("Symbol")
        table.add_column("Side")
        table.add_column("Volume", justify="right")
        table.add_column("Open", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("SL", justify="right")
        table.add_column("TP", justify="right")
        table.add_column("Floating PnL", justify="right")

        for p in pos:
            p_color = "green" if p.profit >= 0 else "red"
            table.add_row(
                f"#{p.ticket}",
                p.symbol,
                p.type,
                f"{p.volume:.2f}",
                f"{p.price_open:.5f}",
                f"{p.price_current:.5f}",
                f"{p.sl:.5f}" if p.sl > 0 else "—",
                f"{p.tp:.5f}" if p.tp > 0 else "—",
                f"[{p_color}]${p.profit:,.2f}[/{p_color}]",
            )
        console.print(table)

    asyncio.run(_do())


@app.command()
def order(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Nama simbol pasar (misal: XAUUSDm)"),
    side: str = typer.Option(..., "--side", help="BUY atau SELL"),
    lot: float = typer.Option(0.01, "--lot", "-l", help="Ukuran volume/lot"),
    sl: float = typer.Option(0.0, "--sl", help="Harga Stop Loss (0 = none)"),
    tp: float = typer.Option(0.0, "--tp", help="Harga Take Profit (0 = none)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil akun"),
) -> None:
    """Eksekusi order market baru secara langsung via CLI."""
    prof = load_profile(profile)
    controller = TradeController(prof)

    async def _do():
        ok = await controller.connect()
        if not ok:
            console.print("[bold red]Gagal terhubung ke broker.[/bold red]")
            return
        res = await controller.send_manual_order(symbol, side.upper(), lot, sl, tp)
        await controller.disconnect()
        if res.ok:
            console.print(f"[bold green]✔ Order #{res.ticket} {side.upper()} {lot} {symbol} Berhasil![/bold green]")
        else:
            console.print(f"[bold red]✖ Order Gagal: {res.message}[/bold red]")

    asyncio.run(_do())


@app.command()
def close(
    all_positions: bool = typer.Option(False, "--all", "-a", help="Tutup SEMUA posisi terbuka"),
    ticket: Optional[int] = typer.Option(None, "--ticket", "-t", help="Nomor tiket posisi yang ditutup"),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Filter simbol"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil akun"),
) -> None:
    """Tutup posisi trading (satu tiket tertentu atau sekaligus semua)."""
    if not all_positions and not ticket:
        console.print("[bold red]Tentukan --all untuk menutup semua posisi, atau --ticket <id>[/bold red]")
        return

    prof = load_profile(profile)
    controller = TradeController(prof)

    async def _do():
        ok = await controller.connect()
        if not ok:
            console.print("[bold red]Gagal terhubung ke broker.[/bold red]")
            return

        if all_positions:
            results = await controller.emergency_close_all()
            console.print(f"[bold green]✔ Selesai menutup {len(results)} posisi.[/bold green]")
        elif ticket:
            res = await asyncio.to_thread(controller.backend.close_position, ticket, symbol or "")
            if res.ok:
                console.print(f"[bold green]✔ Posisi #{ticket} berhasil ditutup.[/bold green]")
            else:
                console.print(f"[bold red]✖ Gagal menutup #{ticket}: {res.message}[/bold red]")

        await controller.disconnect()

    asyncio.run(_do())


@app.command()
def profiles() -> None:
    """Tampilkan daftar semua profil akun yang tersedia di data/profiles/."""
    all_prof = list_profiles()
    console.print(f"[bold cyan]Ditemukan {len(all_prof)} profil akun:[/bold cyan]")
    for p in all_prof:
        prof_obj = load_profile(p)
        t_mode = getattr(prof_obj, "trading_mode", "demo").upper()
        mode_color = "red" if t_mode == "REAL" else ("yellow" if t_mode == "DEMO" else "cyan")
        console.print(f"  • [bold white]{p:<16}[/bold white] [{mode_color}][{t_mode}][/{mode_color}] (Backend: {prof_obj.backend})")


@app.command()
def mode(
    target_mode: Optional[str] = typer.Argument(
        None, help="Pilihan mode langsung: real, demo, atau simulasi"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Nama profil target"
    ),
) -> None:
    """Menu konfigurasi & pemilihan mode lingkungan trading: Real, Demo, atau Simulasi."""
    prof = load_profile(profile)
    curr_mode = getattr(prof, "trading_mode", "demo").lower()

    if target_mode:
        sel_mode = target_mode.strip().lower()
        if sel_mode in ("1", "real", "live"):
            prof.trading_mode = "real"
        elif sel_mode in ("2", "demo", "trial"):
            prof.trading_mode = "demo"
        elif sel_mode in ("3", "simulasi", "sim", "simulation", "paper"):
            prof.trading_mode = "simulasi"
        else:
            console.print(f"[bold red]Mode tidak dikenal: '{target_mode}'. Pilihan: real, demo, simulasi[/bold red]")
            raise typer.Exit(code=1)

        save_profile(prof)
        badge = (
            "[bold white on red] 🔥 REAL [/bold white on red]"
            if prof.trading_mode == "real"
            else ("[bold black on yellow] 🧪 DEMO [/bold black on yellow]" if prof.trading_mode == "demo" else "[bold black on cyan] 🎮 SIMULASI [/bold black on cyan]")
        )
        console.print(f"[bold green]✔ Mode trading untuk profil [white]{prof.profile_name}[/white] berhasil diubah ke:[/bold green] {badge}")
        return

    # Interactive Menu
    console.print("[bold cyan]══════════════ MENU PILIH MODE TRADING ══════════════[/bold cyan]\n")
    console.print(f"Profil Aktif: [bold white]{prof.profile_name}[/bold white]")
    console.print(f"Mode Saat Ini: [bold yellow]{curr_mode.upper()}[/bold yellow]\n")

    console.print("  [bold cyan]1[/bold cyan] : [bold red]REAL[/bold red]     — Akun Nyata MT5 Broker (⚠️ Peringatan: Memakai Dana Riil Broker)")
    console.print("  [bold cyan]2[/bold cyan] : [bold yellow]DEMO[/bold yellow]     — Akun Latihan MT5 Broker (Bebas Risiko Modal)")
    console.print("  [bold cyan]3[/bold cyan] : [bold cyan]SIMULASI[/bold cyan] — Paper Trading Virtual Lokal (Offline Tanpa Perlu MT5)\n")
    console.print("  [bold cyan]0[/bold cyan] : Batal / Kembali")

    choice = typer.prompt("\nPilih nomor mode (0-3)", default="0").strip()
    if choice == "1":
        prof.trading_mode = "real"
    elif choice == "2":
        prof.trading_mode = "demo"
    elif choice == "3":
        prof.trading_mode = "simulasi"
    elif choice == "0":
        console.print("[dim]Batal mengubah mode.[/dim]")
        return
    else:
        console.print("[red]Pilihan tidak valid.[/red]")
        return

    save_profile(prof)
    badge = (
        "[bold white on red] 🔥 REAL [/bold white on red]"
        if prof.trading_mode == "real"
        else ("[bold black on yellow] 🧪 DEMO [/bold black on yellow]" if prof.trading_mode == "demo" else "[bold black on cyan] 🎮 SIMULASI [/bold black on cyan]")
    )
    console.print(f"\n[bold green]✔ Mode trading berhasil disimpan:[/bold green] {badge}")


@app.command()
def backup() -> None:
    """Buat arsip ZIP backup untuk seluruh data konfigurasi dan profil."""
    backup_dir = Path("backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = backup_dir / f"raptech_backup_{ts}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        data_dir = Path("data")
        if data_dir.exists():
            for root, _, files in os.walk(data_dir):
                for f in files:
                    fp = Path(root) / f
                    arcname = fp.relative_to(Path("."))
                    zf.write(fp, arcname)

    console.print(f"[bold green]✔ Backup berhasil dibuat: {zip_path}[/bold green]")


@app.command("test-connection")
@app.command("check-connection")
def test_connection_cmd(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil akun yang akan diuji"),
) -> None:
    """Uji koneksi dan latensi ping ke broker MT5 (Native atau MCP)."""
    prof = load_profile(profile)
    console.print(f"[bold cyan]Menguji koneksi untuk profil: [white]{prof.profile_name}[/white] (Mode: {prof.backend.upper()})...[/bold cyan]")

    controller = TradeController(prof)
    diag = asyncio.run(controller.test_connection_diagnostics())

    table = Table(title=f"Hasil Uji Koneksi — {prof.profile_name}", box=box.ROUNDED)
    table.add_column("Parameter", style="cyan")
    table.add_column("Nilai / Status", style="bold white")

    status_style = "bold green" if diag.get("ok") else "bold red"
    status_label = "TERHUBUNG (OK)" if diag.get("ok") else "GAGAL"

    table.add_row("Status Koneksi", f"[{status_style}]{status_label}[/{status_style}]")
    table.add_row("Metode Backend", diag.get("backend", "N/A"))
    table.add_row("Latensi Ping", f"{diag.get('latency_ms', 0)} ms")
    table.add_row("Server", str(diag.get("server", prof.server)))
    table.add_row("Nomor Login MT5", str(diag.get("login", prof.login)))
    table.add_row("Tipe Akun", str(diag.get("account_type", "N/A")))
    table.add_row("Saldo Terbaca", f"${diag.get('balance', 0.0):,.2f}")
    table.add_row("Ekuitas Terbaca", f"${diag.get('equity', 0.0):,.2f}")
    table.add_row("Izin Trading", "YA" if diag.get("trade_allowed") else "TIDAK (Investor/Read-only)")
    algo_ok = diag.get("algo_trading_allowed", True)
    algo_style = "green" if algo_ok else "bold red"
    algo_label = "AKTIF (Bisa Buka Posisi)" if algo_ok else "NONAKTIF (Tombol 'Algo Trading' di MT5 merah, tekan Ctrl+E)"
    table.add_row("Izin Algo Trading", f"[{algo_style}]{algo_label}[/{algo_style}]")
    table.add_row("Pesan Sistem", str(diag.get("message", "")))

    console.print(table)


@app.command()
def backtest(
    strategy: str = typer.Option("fast_gold_scalper", "--strategy", "-s", help="Nama strategi katalog"),
    symbol: str = typer.Option("XAUUSDm", "--symbol", help="Simbol pasar"),
    timeframe: str = typer.Option("M5", "--timeframe", "-tf", help="Timeframe candle (M1, M5, M15, H1)"),
    bars: int = typer.Option(500, "--bars", "-n", help="Jumlah bar candle yang diuji"),
    balance: float = typer.Option(1000.0, "--balance", help="Modal awal simulasi USD"),
    spread: float = typer.Option(20.0, "--spread", help="Spread simulasi dalam points"),
    slippage: float = typer.Option(5.0, "--slippage", help="Slippage simulasi dalam points"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil konfigurasi risiko"),
) -> None:
    """Jalankan simulasi backtesting strategi historis modular tanpa lookahead bias."""
    from core.backtester import Backtester
    from strategies import get_registry

    reg = get_registry()
    strat_cls = reg.get(strategy)
    if not strat_cls:
        console.print(f"[bold red]Strategi '{strategy}' tidak ditemukan di katalog.[/bold red]")
        console.print(f"[dim]Pilihan strategi: {', '.join(reg.keys())}[/dim]")
        return

    strat = strat_cls()
    prof = load_profile(profile)

    console.print(f"[bold cyan]Memulai Backtest: [white]{strat.display_name}[/white] pada [yellow]{symbol} ({timeframe})[/yellow][/bold cyan]")
    console.print(f"[dim]Modal Awal: ${balance:,.2f} • Spread: {spread} pts • Slippage: {slippage} pts • Bars: {bars}[/dim]")

    controller = TradeController(prof)
    candles = []

    async def _fetch():
        nonlocal candles
        ok = await controller.connect()
        if ok:
            candles = await asyncio.to_thread(controller.backend.get_candles, symbol, timeframe, bars)
            await controller.disconnect()

    try:
        asyncio.run(_fetch())
    except Exception:
        candles = []

    if not candles or len(candles) < 30:
        console.print("[yellow]Data candle dari broker tidak tersedia. Menggunakan generator bar historis deterministik...[/yellow]")
        # Deterministic wave generator for offline backtesting
        from datetime import timedelta
        base_time = datetime.now() - timedelta(minutes=bars * 5)
        price = 2700.0 if "xau" in symbol.lower() else (1.0800 if "eur" in symbol.lower() else 65000.0)
        import math
        for idx in range(bars):
            wave = math.sin(idx / 12.0) * (3.5 if "xau" in symbol.lower() else 0.0015)
            open_p = price + wave
            high_p = open_p + (1.2 if "xau" in symbol.lower() else 0.0006)
            low_p = open_p - (1.1 if "xau" in symbol.lower() else 0.0005)
            close_p = open_p + (math.cos(idx / 8.0) * (1.0 if "xau" in symbol.lower() else 0.0004))
            candles.append(
                Candle(
                    time=base_time + timedelta(minutes=idx * 5),
                    open=round(open_p, 3),
                    high=round(high_p, 3),
                    low=round(low_p, 3),
                    close=round(close_p, 3),
                    tick_volume=100,
                )
            )

    bt = Backtester(
        strategy=strat,
        initial_balance=balance,
        spread_points=spread,
        slippage_points=slippage,
        risk_settings=prof.risk,
    )
    res = bt.run(candles, symbol=symbol)

    table = Table(title=f"Hasil Backtest — {strat.display_name} ({symbol})", box=box.ROUNDED)
    table.add_column("Metrik Kinerja", style="cyan")
    table.add_column("Nilai Hasil", style="bold white")

    pnl_style = "bold green" if res.net_profit >= 0 else "bold red"
    pnl_sign = "+" if res.net_profit >= 0 else ""

    table.add_row("Total Transaksi", str(res.total_trades))
    table.add_row("Transaksi Menang (Win)", f"{res.winning_trades} ({res.win_rate_percent:.1f}%)")
    table.add_row("Transaksi Kalah (Loss)", f"{res.losing_trades}")
    table.add_row("Net Profit Setelah Biaya", f"[{pnl_style}]{pnl_sign}${res.net_profit:,.2f}[/{pnl_style}]")
    table.add_row("Profit Factor", f"{res.profit_factor:.2f}")
    table.add_row("Rata-rata Menang (Avg Win)", f"${res.avg_win:,.2f}")
    table.add_row("Rata-rata Kalah (Avg Loss)", f"-${res.avg_loss:,.2f}")
    table.add_row("Expectancy Per Trade", f"${res.expectancy_per_trade:,.2f}")
    table.add_row("Drawdown Maksimal ($)", f"${res.max_drawdown_dollars:,.2f}")
    table.add_row("Drawdown Maksimal (%)", f"{res.max_drawdown_percent:.2f}%")
    table.add_row("Rata-rata Durasi Tahan", f"{res.avg_holding_bars:.1f} bar")
    table.add_row("Total Biaya & Komisi", f"${res.total_commission:,.2f}")

    console.print(table)


@app.command()
def login(
    backend: str = typer.Option("native", "--backend", "-b", help="Pilihan metode: native atau mcp"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil target"),
    acc_login: Optional[int] = typer.Option(None, "--login", help="Nomor Akun MT5 (khusus Native)"),
    password: Optional[str] = typer.Option(None, "--password", help="Password Akun MT5 (khusus Native)"),
    server: Optional[str] = typer.Option(None, "--server", help="Server Broker (misal: Exness-MT5Trial)"),
    path: Optional[str] = typer.Option(None, "--path", help="Path terminal64.exe (khusus Native)"),
    url: Optional[str] = typer.Option(None, "--url", help="Endpoint MCP Gateway URL (khusus MCP)"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Bearer API Key (khusus MCP)"),
) -> None:
    """Setup kredensial login akun MT5 (Native) atau Remote MCP Gateway."""
    from rich.prompt import Prompt

    target_name = profile or "default"
    prof = load_profile(target_name)
    prof.profile_name = target_name

    b_type = backend.lower().strip()
    if b_type not in ("native", "mcp"):
        console.print("[yellow]Pilihan backend tidak valid, menggunakan default 'native'.[/yellow]")
        b_type = "native"

    prof.backend = b_type

    if b_type == "native":
        console.print(f"[bold cyan]── Konfigurasi Login Native MT5 untuk [{target_name}] ──[/bold cyan]")
        if acc_login is None:
            l_val = Prompt.ask("Nomor Akun Login MT5", default=str(prof.login or 0)).strip()
            prof.login = int(l_val) if l_val.isdigit() else 0
        else:
            prof.login = acc_login

        if password is None:
            prof.password = Prompt.ask("Password MT5 (akan dienkripsi)", password=True, default=prof.password).strip()
        else:
            prof.password = password

        if server is None:
            prof.server = Prompt.ask("Server Broker", default=prof.server or "Exness-Real").strip()
        else:
            prof.server = server

        if path is not None:
            prof.path = path
    else:
        console.print(f"[bold yellow]── Konfigurasi Login Remote MCP Gateway untuk [{target_name}] ──[/bold yellow]")
        if url is None:
            prof.mcp_url = Prompt.ask("Endpoint MCP Server URL", default=prof.mcp_url or "http://127.0.0.1:8000/mcp").strip()
        else:
            prof.mcp_url = url

        if api_key is None:
            prof.mcp_api_key = Prompt.ask("MCP API Key (opsional)", password=True, default=prof.mcp_api_key).strip()
        else:
            prof.mcp_api_key = api_key

    saved_path = save_profile(prof, target_name)
    console.print(f"\n[bold green]✔ Kredensial {b_type.upper()} berhasil disimpan ke {saved_path}![/bold green]")
    console.print(f"[dim]Jalankan 'python main.py check-connection --profile {target_name}' untuk verifikasi koneksi.[/dim]")


@app.command("setup")
@app.command("setup-account")
def setup_account(
    profile: Optional[str] = typer.Option("default", "--profile", "-p", help="Nama profil yang dikonfigurasi"),
) -> None:
    """Wizard interaktif 1-klik untuk mengatur data akun MT5 & preferensi trading customer."""
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table

    target_name = profile or "default"
    prof = load_profile(target_name)
    prof.profile_name = target_name

    console.clear()
    console.print(
        Panel(
            "[bold cyan]RAPTECH AUTOTRADE v3.1.0 — WIZARD PENGATURAN AKUN BROKER[/bold cyan]\n"
            "[dim]Panduan langkah demi langkah untuk menghubungkan bot ke akun MetaTrader 5 Anda.[/dim]\n"
            "[green]Data akun Anda dienkripsi aman secara lokal di komputer ini.[/green]",
            border_style="cyan",
            expand=False,
        )
    )

    # 1. Pilih Lingkungan / Mode
    console.print("\n[bold yellow][Langkah 1/5] Pilih Lingkungan / Mode Trading:[/bold yellow]")
    console.print("  [bold white][1][/bold white] Demo     : Akun Latihan Broker (Bebas Risiko Uang Nyata)")
    console.print("  [bold white][2][/bold white] Real     : Akun Dana Riil Broker (Menggunakan Modal Nyata)")
    console.print("  [bold white][3][/bold white] Simulasi : Paper Trading Virtual Lokal (Tanpa Perlu MT5)")

    mode_choice = Prompt.ask("Pilihan Mode [1/2/3]", choices=["1", "2", "3"], default="1")
    if mode_choice == "2":
        prof.trading_mode = "real"
        prof.backend = "native"
        console.print("[bold red]Mode REAL dipilih: Proteksi modal ketat akan diaktifkan secara otomatis.[/bold red]")
    elif mode_choice == "3":
        prof.trading_mode = "simulasi"
        prof.backend = "simulation"
        prof.server = "Engine Simulasi"
        prof.login = 999999
        prof.password = ""
    else:
        prof.trading_mode = "demo"
        prof.backend = "native"
        console.print("[bold green]Mode DEMO dipilih: Aman untuk pengujian akun broker.[/bold green]")

    # 2. Server Broker (jika bukan simulasi)
    if prof.trading_mode != "simulasi":
        console.print("\n[bold yellow][Langkah 2/5] Server Broker MT5:[/bold yellow]")
        console.print("[dim]Tips: Buka aplikasi MT5 -> Klik File -> 'Login to Trade Account' -> lihat nama Server.[/dim]")
        default_srv = prof.server if prof.server and prof.server != "Engine Simulasi" else "Exness-Real"
        srv_val = Prompt.ask("Nama Server Broker", default=default_srv).strip()
        prof.server = srv_val

        # 3. Nomor Akun MT5
        console.print("\n[bold yellow][Langkah 3/5] Nomor Akun MT5 (Login ID):[/bold yellow]")
        cur_login = str(prof.login) if (prof.login and prof.login != 999999) else "0"
        l_val = Prompt.ask("Nomor Akun MT5", default=cur_login).strip()
        prof.login = int(l_val) if l_val.isdigit() else 0

        # 4. Password MT5
        console.print("\n[bold yellow][Langkah 4/5] Password Akun MT5:[/bold yellow]")
        console.print("[dim]Karakter password tidak akan ditampilkan di layar demi keamanan.[/dim]")
        pass_val = Prompt.ask("Password MT5", password=True, default=prof.password).strip()
        prof.password = pass_val

    # 5. Pilihan Pasar / Simbol & Strategi
    console.print("\n[bold yellow][Langkah 5/5] Pasar Trading Pilihan:[/bold yellow]")
    console.print("  [bold white][1][/bold white] Emas (XAUUSD / Gold) [Direkomendasikan untuk Scalper]")
    console.print("  [bold white][2][/bold white] Forex Major (EURUSD, GBPUSD, USDJPY, AUDUSD)")
    console.print("  [bold white][3][/bold white] Crypto (BTCUSD, ETHUSD)")
    console.print("  [bold white][4][/bold white] Gabungan Semua Pasar (XAUUSD, EURUSD, BTCUSD)")

    market_choice = Prompt.ask("Pilihan Pasar [1/2/3/4]", choices=["1", "2", "3", "4"], default="1")
    if market_choice == "1":
        prof.symbols = ["XAUUSDm"]
        prof.timeframe = "M5"
        prof.strategy = "fast_gold_scalper"
    elif market_choice == "2":
        prof.symbols = ["EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm"]
        prof.timeframe = "M1"
        prof.strategy = "pa_hybrid"
    elif market_choice == "3":
        prof.symbols = ["BTCUSDm", "ETHUSDm"]
        prof.timeframe = "M5"
        prof.strategy = "pa_breakout"
    else:
        prof.symbols = ["XAUUSDm", "EURUSDm", "BTCUSDm"]
        prof.timeframe = "M5"
        prof.strategy = "fast_gold_scalper"

    # Ringkasan
    summary_table = Table(title="Ringkasan Konfigurasi Akun", show_header=True, header_style="bold cyan")
    summary_table.add_column("Parameter", style="cyan")
    summary_table.add_column("Nilai Konfigurasi", style="bold white")

    summary_table.add_row("Nama Profil", prof.profile_name)
    summary_table.add_row("Mode Trading", prof.trading_mode.upper())
    summary_table.add_row("Metode Backend", prof.backend.upper())
    summary_table.add_row("Server Broker", prof.server)
    summary_table.add_row("Nomor Login MT5", str(prof.login))
    summary_table.add_row("Password MT5", "****** (Tersimpan Terenkripsi)" if prof.password else "(Kosong)")
    summary_table.add_row("Simbol Trading", ", ".join(prof.symbols))
    summary_table.add_row("Timeframe", prof.timeframe)
    summary_table.add_row("Strategi Default", prof.strategy)
    summary_table.add_row("Ukuran Lot", f"{prof.risk.fixed_lot} Lot (Aman)")

    console.print("\n")
    console.print(summary_table)

    confirm = Confirm.ask("\nSimpan pengaturan ini sekarang?", default=True)
    if not confirm:
        console.print("[yellow]Pengaturan dibatalkan. Tidak ada perubahan yang disimpan.[/yellow]")
        return

    saved_path = save_profile(prof, target_name)
    console.print(f"\n[bold green]✔ Pengaturan akun berhasil disimpan ke {saved_path}![/bold green]")
    console.print("\n[bold cyan]Langkah Selanjutnya:[/bold cyan]")
    if prof.trading_mode != "simulasi":
        console.print(" 1. Pastikan aplikasi MetaTrader 5 di komputer Anda telah dibuka dan login.")
        console.print(" 2. Pastikan tombol 'Algo Trading' di toolbar atas MT5 berwarna [bold green]HIJAU[/bold green].")
    console.print(" 3. Klik ganda file [bold yellow]1_Mulai_Raptech_Autotrade.bat[/bold yellow] untuk menjalankan bot!")


@app.command()
def market(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Nama profil target"),
    set_symbols: Optional[str] = typer.Option(None, "--set", "-s", help="Set daftar simbol baru (pisahkan koma, misal: XAUUSDm,EURUSDm)"),
    add_symbol: Optional[str] = typer.Option(None, "--add", "-a", help="Tambah simbol ke daftar aktif"),
    remove_symbol: Optional[str] = typer.Option(None, "--remove", "-r", help="Hapus simbol dari daftar aktif"),
    preset: Optional[str] = typer.Option(None, "--preset", help="Pilih preset simbol (emas, forex, scalper, crypto, index, allstar)"),
    search: Optional[str] = typer.Option(None, "--search", "-q", help="Cari ketersediaan simbol di broker"),
    list_all: bool = typer.Option(False, "--list", "-l", help="Tampilkan daftar lengkap simbol yang tersedia di broker"),
) -> None:
    """Kelola dan pilih market / simbol trading untuk profil akun."""
    target_name = profile or "default"
    prof = load_profile(target_name)
    prof.profile_name = target_name

    presets_map = {
        "emas": ["XAUUSDm", "XAGUSDm"],
        "gold": ["XAUUSDm", "XAGUSDm"],
        "forex": ["EURUSDm", "GBPUSDm", "USDJPYm", "AUDUSDm"],
        "scalper": ["EURUSDm", "GBPUSDm", "USDJPYm", "EURJPYm", "GBPJPYm"],
        "crypto": ["BTCUSDm", "ETHUSDm", "SOLUSDm"],
        "index": ["US30m", "US500m", "USOILm"],
        "oil": ["US30m", "US500m", "USOILm"],
        "allstar": ["XAUUSDm", "EURUSDm", "BTCUSDm"],
    }

    def _clean_sym(s: str) -> str:
        s = s.strip()
        if s.endswith("m") or s.endswith("c"):
            return s[:-1].upper() + s[-1]
        return s.upper()

    # 1. Preset
    if preset:
        key = preset.strip().lower()
        if key not in presets_map:
            console.print(f"[bold red]Preset '{preset}' tidak dikenali.[/bold red]")
            console.print("Pilihan preset tersedia: [cyan]" + ", ".join(sorted(presets_map.keys())) + "[/cyan]")
            raise typer.Exit(code=1)
        prof.symbols = list(presets_map[key])
        save_profile(prof, target_name)
        console.print(f"[bold green]✔ Preset '{key}' berhasil diterapkan untuk profil [bold white]{target_name}[/bold white]:[/bold green] {prof.symbols}")
        return

    # 2. Set Symbols
    if set_symbols:
        tokens = [_clean_sym(s) for s in set_symbols.split(",") if s.strip()]
        if not tokens:
            console.print("[bold red]Daftar simbol tidak boleh kosong.[/bold red]")
            raise typer.Exit(code=1)
        seen = []
        for sym in tokens:
            if sym not in seen:
                seen.append(sym)
        prof.symbols = seen
        save_profile(prof, target_name)
        console.print(f"[bold green]✔ Daftar simbol berhasil diperbarui untuk profil [bold white]{target_name}[/bold white]:[/bold green] {prof.symbols}")
        return

    # 3. Add Symbol
    if add_symbol:
        sym = _clean_sym(add_symbol)
        if any(s.upper() == sym.upper() for s in prof.symbols):
            console.print(f"[yellow]Simbol {sym} sudah ada di profil [bold white]{target_name}[/bold white].[/yellow]")
        else:
            prof.symbols.append(sym)
            save_profile(prof, target_name)
            console.print(f"[bold green]✔ Simbol {sym} berhasil ditambahkan ke profil [bold white]{target_name}[/bold white].[/bold green]")
        return

    # 4. Remove Symbol
    if remove_symbol:
        sym = _clean_sym(remove_symbol)
        matched = [s for s in prof.symbols if s.upper() == sym.upper()]
        if not matched:
            console.print(f"[yellow]Simbol {sym} tidak ditemukan dalam profil [bold white]{target_name}[/bold white].[/yellow]")
        elif len(prof.symbols) <= 1:
            console.print("[bold red]Gagal: Minimal harus ada 1 simbol aktif untuk trading.[/bold red]")
            raise typer.Exit(code=1)
        else:
            prof.symbols = [s for s in prof.symbols if s.upper() != sym.upper()]
            save_profile(prof, target_name)
            console.print(f"[bold green]✔ Simbol {sym} berhasil dihapus dari profil [bold white]{target_name}[/bold white].[/bold green]")
        return

    # 5. Search / List Symbols dari broker
    if search or list_all:
        controller = TradeController(prof)

        async def _do_search():
            console.print(f"[cyan]Menghubungkan ke broker ({prof.server}) untuk mengambil daftar simbol...[/cyan]")
            ok = await controller.connect()
            if not ok:
                console.print("[bold red]Gagal terhubung ke broker untuk mencari simbol.[/bold red]")
                return
            try:
                query = (search or "").strip()
                all_symbols = await asyncio.to_thread(controller.backend.list_symbols, 1000)
                symbols = all_symbols
                if query:
                    aliases = {"GOLD": "XAU", "SILVER": "XAG", "MINYAK": "OIL"}
                    target_q = aliases.get(query.upper(), query.upper())
                    symbols = [s for s in all_symbols if target_q in s.upper()]

                if not symbols:
                    console.print(f"[yellow]Tidak ada simbol yang cocok dengan query '{query}'.[/yellow]")
                    return

                table = Table(title=f"Daftar Simbol Broker ({prof.server}) — Query: '{query or 'SEMUA'}'", box=box.ROUNDED)
                table.add_column("No", justify="right", style="cyan")
                table.add_column("Simbol Market", style="bold white")
                table.add_column("Status Trading", justify="center")

                for i, sym in enumerate(symbols[:60], 1):
                    is_active = "[bold green]AKTIF[/bold green]" if sym in prof.symbols else "[dim]—[/dim]"
                    table.add_row(str(i), sym, is_active)
                console.print(table)
                if len(symbols) > 60:
                    console.print(f"[dim]Menampilkan 60 dari total {len(symbols)} simbol. Gunakan --search <kata_kunci> untuk hasil lebih spesifik.[/dim]")
            finally:
                await controller.disconnect()

        asyncio.run(_do_search())
        return

    # 6. Default view: Tampilkan tabel simbol aktif dan panduan preset
    table = Table(title=f"Market / Simbol Aktif — Profil: [{prof.profile_name}]", box=box.ROUNDED)
    table.add_column("No", justify="right", style="cyan")
    table.add_column("Simbol Market", style="bold white")
    table.add_column("Status Monitoring", style="green")

    for idx, sym in enumerate(prof.symbols, 1):
        table.add_row(str(idx), sym, "Siap Dianalisis & Auto-Trade")
    console.print(table)

    console.print("\n[bold]⚡ Preset Paket Simbol Siap Pakai:[/bold]")
    console.print("  • [cyan]emas[/cyan]     : XAUUSDm, XAGUSDm")
    console.print("  • [cyan]forex[/cyan]    : EURUSDm, GBPUSDm, USDJPYm, AUDUSDm")
    console.print("  • [cyan]scalper[/cyan]  : EURUSDm, GBPUSDm, USDJPYm, EURJPYm, GBPJPYm")
    console.print("  • [cyan]crypto[/cyan]   : BTCUSDm, ETHUSDm, SOLUSDm")
    console.print("  • [cyan]index[/cyan]    : US30m, US500m, USOILm")
    console.print("  • [cyan]allstar[/cyan]  : XAUUSDm, EURUSDm, BTCUSDm")

    console.print("\n[dim]Tips Penggunaan CLI:[/dim]")
    console.print("  [white]python main.py market --preset crypto[/white]")
    console.print("  [white]python main.py market --set XAUUSDm,EURUSDm,BTCUSDm[/white]")
    console.print("  [white]python main.py market --add ETHUSDm[/white]")
    console.print("  [white]python main.py market --remove SOLUSDm[/white]")
    console.print("  [white]python main.py market --search GOLD[/white]")

