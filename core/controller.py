from __future__ import annotations

"""
Raptech Autotrade CLI — Central Trade Controller.
Coordinates backend connections, bot engine lifecycle, profile switches, and manual commands.
"""

import asyncio
from typing import Callable, List, Optional

from backend.base import AccountInfo, OrderResult, Position, TradingBackend
from backend.mcp_backend import McpBackend
from backend.native_backend import NativeBackend
from backend.simulation_backend import SimulationBackend
from core.bot_engine import BotEngine
from core.config_store import AccountProfile, load_profile, save_profile
from core.logger import get_logger
from core.watchdog import TelemetryData, Watchdog

logger = get_logger("controller")


class TradeController:
    """High-level system coordinator connecting UI/CLI with BotEngine and TradingBackend."""

    def __init__(self, profile: Optional[AccountProfile] = None) -> None:
        self.profile = profile or load_profile()
        self.backend: Optional[TradingBackend] = None
        self.engine: Optional[BotEngine] = None
        self.watchdog = Watchdog()
        self.is_connected = False
        self.on_log_callbacks: List[Callable[[str], None]] = []
        self._bg_task: Optional[asyncio.Task] = None

    def add_log_listener(self, cb: Callable[[str], None]) -> None:
        self.on_log_callbacks.append(cb)

    def dispatch_log(self, msg: str) -> None:
        for cb in self.on_log_callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def initialize_backend(self) -> TradingBackend:
        mode = getattr(self.profile, "trading_mode", "demo").lower()
        backend_type = self.profile.backend.lower()

        if mode == "simulasi" or backend_type in ("simulation", "simulasi"):
            self.backend = SimulationBackend()
        elif backend_type == "mcp":
            self.backend = McpBackend(
                endpoint_url=self.profile.mcp_url,
                api_key=self.profile.mcp_api_key,
            )
        else:
            self.backend = NativeBackend(
                login=self.profile.login,
                password=self.profile.password,
                server=self.profile.server,
                path=self.profile.path,
            )
        return self.backend

    async def connect(self) -> bool:
        if self.backend is None:
            self.initialize_backend()

        mode = getattr(self.profile, "trading_mode", "demo").lower()
        if mode == "simulasi" or isinstance(self.backend, SimulationBackend):
            self.dispatch_log("🎮 Mengaktifkan Mode SIMULASI (Paper Trading Offline)...")
        elif mode == "real":
            self.dispatch_log("🔥 PERINGATAN: MODE REAL AKTIF (Menggunakan Dana Modal Nyata)!")
            self.dispatch_log(f"Menghubungkan ke broker ({self.profile.server}) via {self.profile.backend.upper()}...")
        else:
            self.dispatch_log(f"🧪 Menghubungkan ke broker DEMO ({self.profile.server}) via {self.profile.backend.upper()}...")

        ok = await asyncio.to_thread(self.backend.connect)
        if ok:
            self.is_connected = True
            if isinstance(self.backend, SimulationBackend):
                self.dispatch_log("✅ Engine Simulasi Siap & Aktif!")
            else:
                self.dispatch_log("✅ Terhubung ke Broker!")
            self.engine = BotEngine(
                backend=self.backend,
                profile=self.profile,
                on_log=self.dispatch_log,
            )
            # Start background loop
            self._bg_task = asyncio.create_task(self.engine.run_loop(poll_interval=1.0))
            if self.profile.auto_start:
                self.engine.start_auto_trading()
            return True
        else:
            self.is_connected = False
            self.dispatch_log("❌ Gagal terhubung ke broker.")
            mode = getattr(self.profile, "trading_mode", "demo").lower()
            if mode != "simulasi":
                self.dispatch_log("💡 Tip: Tekan [T] untuk Mode SIMULASI (offline) atau [P] untuk atur akun MT5.")
            return False

    async def disconnect(self) -> None:
        if self.engine:
            self.engine.stop()
        if self._bg_task:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
        if self.backend:
            await asyncio.to_thread(self.backend.disconnect)
        self.is_connected = False
        self.dispatch_log("Koneksi ditutup.")

    def start_auto_trading(self) -> bool:
        if not self.engine:
            return False
        self.engine.start_auto_trading()
        return self.engine.auto_trading_enabled

    def stop_auto_trading(self) -> bool:
        if not self.engine:
            return False
        self.engine.stop_auto_trading()
        return not self.engine.auto_trading_enabled

    def toggle_auto_trading(self) -> bool:
        if not self.engine:
            return False
        if self.engine.auto_trading_enabled:
            self.engine.stop_auto_trading()
            return False
        else:
            self.engine.start_auto_trading()
            return True

    async def emergency_close_all(self) -> List[OrderResult]:
        if not self.engine:
            return []
        self.dispatch_log("🚨 PERINTAH DARURAT: Menutup seluruh posisi terbuka...")
        results, remaining = await asyncio.to_thread(
            self.engine.order_manager.verified_emergency_close_all
        )
        if not remaining:
            self.dispatch_log(f"✔ Berhasil menutup {len(results)} posisi. Terverifikasi 0 posisi tersisa.")
        else:
            self.dispatch_log(f"⚠️ PERINGATAN: {len(remaining)} posisi masih terbuka di broker setelah retry!")
        return results

    async def send_manual_order(
        self, symbol: str, side: str, lot: float, sl: float = 0.0, tp: float = 0.0
    ) -> OrderResult:
        if not self.engine:
            return OrderResult(ok=False, message="Bot belum terhubung")

        # Invariant 4.4: Validate manual order against RiskManager
        account = await asyncio.to_thread(self.backend.account_info)
        positions = await asyncio.to_thread(self.backend.positions)
        allowed, reason = self.engine.risk_manager.check_pre_trade_risk(
            symbol=symbol,
            side=side,
            volume=lot,
            account=account,
            current_positions=positions,
        )
        if not allowed:
            self.dispatch_log(f"✖ Order manual ditolak RiskManager: {reason}")
            return OrderResult(ok=False, message=f"Ditolak RiskManager: {reason}")

        res = await asyncio.to_thread(
            self.engine.order_manager.send_market_order,
            symbol=symbol,
            side=side,
            lot=lot,
            sl=sl,
            tp=tp,
        )
        if res.ok and self.engine:
            ticket_id = res.ticket or res.order or 0
            spec = await asyncio.to_thread(self.backend.symbol_spec, symbol)
            new_pos = Position(
                ticket=ticket_id,
                symbol=symbol,
                type=side.upper(),
                volume=res.volume or lot,
                price_open=res.price or 0.0,
                price_current=res.price or 0.0,
                sl=sl,
                tp=tp,
            )
            self.engine.risk_manager.register_position(new_pos, spec)

        return res

    def get_telemetry(self) -> TelemetryData:
        return self.watchdog.get_telemetry()

    async def test_connection_diagnostics(self) -> dict:
        """Run connection diagnostics and benchmark latency."""
        import time
        if self.backend is None:
            self.initialize_backend()

        was_connected = self.is_connected
        if not was_connected:
            t0 = time.perf_counter()
            ok = await asyncio.to_thread(self.backend.connect)
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

            if not ok:
                return {
                    "ok": False,
                    "backend": self.profile.backend.upper(),
                    "latency_ms": latency_ms,
                    "message": "Gagal inisialisasi / otentikasi ke broker.",
                }
        else:
            t0 = time.perf_counter()
            _ = await asyncio.to_thread(self.backend.account_info)
            latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        acc = await asyncio.to_thread(self.backend.account_info)
        symbols = await asyncio.to_thread(self.backend.list_symbols, 10)
        if not was_connected:
            await asyncio.to_thread(self.backend.disconnect)

        return {
            "ok": True,
            "backend": self.profile.backend.upper(),
            "latency_ms": latency_ms,
            "login": acc.login if acc else self.profile.login,
            "server": acc.server if acc else self.profile.server,
            "account_type": acc.account_type if acc else "N/A",
            "balance": acc.balance if acc else 0.0,
            "equity": acc.equity if acc else 0.0,
            "trade_allowed": acc.trade_allowed if acc else False,
            "algo_trading_allowed": getattr(acc, "algo_trading_allowed", True) if acc else True,
            "symbols_count": len(symbols),
            "message": "Koneksi berhasil dan responsif.",
        }
