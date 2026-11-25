"""bridge_server.py — Jembatan IPC (JSON-RPC stdio/NDJSON) antara UI C++ dan Python Trading Engine.

Proses ini dijalankan sebagai subproses oleh C++ (QProcess):
- Menerima perintah JSON per baris dari stdin: {"id": 1, "method": "connect", "params": {...}}
- Mengirimkan respons JSON ke stdout: {"id": 1, "result": {...}, "error": null}
- Mengirimkan event live stream ke stdout: {"event": "accountUpdated", "data": {...}}
- Log pesan dikirim ke stderr & via event "logMessage" ke C++ UI.
- Fail-safe & auto-cleanup: bila stdin tertutup (aplikasi C++ keluar/crash), proses ini otomatis mati rapi.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional

# Tambahkan direktori py_backend ke sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from config.settings import settings
from src.bot_engine import BotEngine
from src import config_store
from src import strategy_loader
from strategies import script_runtime


class _BridgeEmitter:
    """Thread-safe emitter untuk mengirim baris JSON ke stdout."""

    def __init__(self):
        self._lock = threading.Lock()

    def send_event(self, event: str, data: Any = None) -> None:
        payload = json.dumps({"event": event, "data": data if data is not None else {}}, ensure_ascii=False)
        with self._lock:
            try:
                sys.stdout.write(payload + "\n")
                sys.stdout.flush()
            except (BrokenPipeError, OSError):
                pass

    def send_response(self, req_id: Any, result: Any = None, error: Optional[str] = None) -> None:
        payload = json.dumps({"id": req_id, "result": result, "error": error}, ensure_ascii=False)
        with self._lock:
            try:
                sys.stdout.write(payload + "\n")
                sys.stdout.flush()
            except (BrokenPipeError, OSError):
                pass


class _BridgeLogHandler(logging.Handler):
    """Meneruskan pesan log logger 'mt5bot' langsung ke C++ UI via event logMessage dengan format rapi."""

    def __init__(self, emitter: _BridgeEmitter):
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            raw_msg = record.getMessage().strip()
            if not raw_msg:
                return

            tag = "INFO"
            msg = raw_msg
            if record.levelno >= logging.ERROR:
                tag = "ERROR"
            elif record.levelno >= logging.WARNING:
                tag = "RISIKO" if any(k in msg for k in ("EQUITY", "Drawdown", "SL", "TP", "Batas")) else "PERINGATAN"
            elif msg.startswith("[script]"):
                tag = "SKRIP"
                msg = msg[len("[script]"):].strip()
            elif "backend native" in msg.lower():
                tag = "MT5"
                msg = "Menggunakan koneksi Native MT5."
            elif "backend mcp" in msg.lower():
                tag = "MT5"
                msg = f"Menggunakan koneksi MCP MT5 ({settings.mcp_endpoint})."
            elif "backend simulasi" in msg.lower():
                tag = "SIMULASI"
                msg = raw_msg
            elif "simbol" in msg.lower() and "disesuaikan" in msg.lower():
                tag = "MT5"
            elif "strategi diperbarui" in msg.lower():
                tag = "SKRIP"
            elif "order manual" in msg.lower():
                tag = "ORDER"
            elif "sinyal buy" in msg.lower() or "sinyal sell" in msg.lower():
                tag = "SINYAL"
            elif "tutup semua" in msg.lower():
                tag = "ORDER"
            elif "trailing stop" in msg.lower() or "break-even" in msg.lower():
                tag = "RISIKO"
            elif "margin level tipis" in msg.lower():
                tag = "RISIKO"
            elif "konfigurasi" in msg.lower():
                tag = "SISTEM"

            if msg.startswith("["):
                clean_line = msg
            else:
                clean_line = f"[{tag}] {msg}"

            self._emitter.send_event("logMessage", {"message": clean_line})
        except Exception:
            pass


class PythonEngineWorker:
    """Thread worker yang menjalankan monitoring akun, chart, order, dan trading loop."""

    CHART_INTERVAL = 5

    def __init__(self, engine: BotEngine, emitter: _BridgeEmitter, chart_symbol: str = ""):
        self.engine = engine
        self.emitter = emitter
        self.close_queue: queue.Queue = queue.Queue()
        self.cmd_queue: queue.Queue = queue.Queue()
        self.running = False
        self.trading = False
        self.chart_symbol = chart_symbol or settings.symbol
        self.chart_dirty = True
        self._thread: Optional[threading.Thread] = None
        self._wake_event = threading.Event()

    def start(self) -> None:
        self.running = True
        self._thread = threading.Thread(target=self._run, name="PythonEngineWorker", daemon=True)
        self._thread.start()

    def request_stop(self) -> None:
        self.running = False
        self.trading = False
        self._wake_event.set()

    def wait(self, timeout: float = 3.0) -> None:
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def set_trading(self, enabled: bool) -> None:
        self.trading = bool(enabled)
        self._wake_event.set()

    def set_chart_symbol(self, symbol: str) -> None:
        if symbol:
            self.chart_symbol = symbol
            self.chart_dirty = True
            self._wake_event.set()

    def wake(self) -> None:
        """Bangunkan worker seketika (sub-milidetik) saat ada perintah order/tutup baru."""
        self._wake_event.set()

    def _run(self) -> None:
        log = logging.getLogger("mt5bot")
        try:
            connected = self.engine.connect()
        except Exception as exc:
            log.error("Gagal menghubungkan ke MT5: %s", exc)
            connected = False

        if not connected:
            self.emitter.send_event("connectedChanged", {"connected": False})
            self.emitter.send_event("stopped", {})
            self.running = False
            return

        self.emitter.send_event("connectedChanged", {"connected": True})

        # Callback jurnal aksi
        def _on_j(entry):
            self.emitter.send_event("journalUpdated", entry)

        self.engine.on_journal = _on_j

        # Kirim daftar simbol
        try:
            symbols = self.engine.list_symbols()
            self.emitter.send_event("symbolsListed", symbols)
        except Exception as exc:
            log.debug("list_symbols error: %s", exc)

        if not self.chart_symbol or self.chart_symbol != settings.symbol:
            self.chart_symbol = settings.symbol
        self.emitter.send_event("chartSymbolChanged", {"symbol": self.chart_symbol})

        tick = 0
        last_poll_time = 0.0
        last_trade_time = 0.0
        try:
            while self.running:
                now = time.time()

                # 1. PRIORITAS TERTINGGI: Segera eksekusi permintaan tutup dan order baru (tanpa tunggu polling)
                did_close = self._drain_close_requests()
                did_cmd = self._drain_commands()
                if did_close or did_cmd:
                    try:
                        positions = self.engine.poll_positions()
                        self.emitter.send_event("positionsUpdated", positions)
                        account = self.engine.poll_account()
                        if account:
                            self.emitter.send_event("accountUpdated", account)
                    except Exception as exc:
                        log.debug("Instant push posisi/akun pasca order error: %s", exc)

                # 2. Monitoring Akun, Posisi, dan Virtual Exits berkala (~1 detik)
                if now - last_poll_time >= 1.0:
                    last_poll_time = now
                    backend = self.engine.backend
                    # Di mode simulasi, majukan pasar sintetis 1 bar tiap detik agar chart & SL/TP hidup
                    if hasattr(backend, "step_bar"):
                        try:
                            backend.step_bar(self.chart_symbol)
                        except Exception:
                            pass
                    account = self.engine.poll_account()
                    if account:
                        self.emitter.send_event("accountUpdated", account)

                    if (not getattr(backend, "_experts_trade_allowed", True) and tick % 10 == 0):
                        try:
                            backend.account_info()
                        except Exception:
                            pass

                    positions = self.engine.poll_positions()
                    self.emitter.send_event("positionsUpdated", positions)

                    # Cek virtual SL/TP tiap detik
                    self.engine.check_virtual_exits()

                    # Refresh chart & statistik tiap CHART_INTERVAL detik
                    if self.chart_dirty or tick % self.CHART_INTERVAL == 0:
                        sym = self.chart_symbol
                        chart_payload = self.engine.poll_chart(sym)
                        self.emitter.send_event("candlesUpdated", {"symbol": sym, "payload": chart_payload})

                        stats = self.engine.poll_stats()
                        self.emitter.send_event("statsUpdated", stats)

                        orders = self.engine.poll_orders()
                        self.emitter.send_event("ordersUpdated", orders)

                        bal = account.get("balance", 0.0) if account else 0.0
                        eq = account.get("equity", 0.0) if account else 0.0
                        curve = self.engine.poll_equity_curve(bal, eq)
                        self.emitter.send_event("equityUpdated", curve)

                        self.chart_dirty = False

                    tick += 1

                # 3. Langkah trading otomatis (berdasarkan interval settings.loop_interval)
                interval_sec = max(1, int(getattr(settings, "loop_interval", 15) or 1))
                if self.trading and (now - last_trade_time >= interval_sec):
                    last_trade_time = now
                    ok = self.engine.process_trading_step()
                    if ok is False:
                        self.trading = False
                        self.emitter.send_event("tradingChanged", {"trading": False})
                        self.emitter.send_event("autoTradingDisabled", {
                            "reason": "Proteksi risiko terpicu (drawdown harian / equity cut-loss). Auto trading dinonaktifkan demi proteksi modal."
                        })

                # 4. Tidur dengan event wakeable (respons seketika saat order tiba, atau periksa kembali maks 150ms)
                self._wake_event.wait(timeout=0.15)
                self._wake_event.clear()
        except Exception as exc:
            log.error("Loop worker Python berhenti: %s", exc)
        finally:
            try:
                self.engine.disconnect()
            except Exception:
                pass
            self.running = False
            self.emitter.send_event("connectedChanged", {"connected": False})
            self.emitter.send_event("stopped", {})

    def _drain_close_requests(self) -> bool:
        any_closed = False
        while True:
            try:
                ticket = self.close_queue.get_nowait()
            except queue.Empty:
                break
            any_closed = True
            self.engine.close_ticket(ticket)
        return any_closed

    def _drain_commands(self) -> bool:
        log = logging.getLogger("mt5bot")
        any_executed = False
        while True:
            try:
                cmd = self.cmd_queue.get_nowait()
            except queue.Empty:
                break
            any_executed = True
            try:
                action = cmd.get("action")
                if action == "market":
                    res = self.engine.manual_market_order(
                        cmd["symbol"], cmd["side"], cmd["volume"],
                        cmd.get("sl", 0.0), cmd.get("tp", 0.0)
                    )
                    self.emitter.send_event("orderFeedback", {
                        "ok": bool(res.get("ok")),
                        "message": str(res.get("message", "Order market berhasil."))
                    })
                elif action == "pending":
                    res = self.engine.place_pending_order(
                        cmd["symbol"], cmd["order_type"], cmd["volume"],
                        cmd["price"], cmd.get("sl", 0.0), cmd.get("tp", 0.0)
                    )
                    self.emitter.send_event("orderFeedback", {
                        "ok": bool(res.get("ok")),
                        "message": str(res.get("message", "Pending order berhasil dipasang."))
                    })
                elif action == "close_all":
                    cnt = self.engine.close_all(cmd.get("symbol", ""))
                    self.emitter.send_event("orderFeedback", {
                        "ok": True,
                        "message": f"Berhasil menutup {cnt} posisi."
                    })
                elif action == "delete_order":
                    ok = self.engine.delete_pending(cmd["ticket"])
                    self.emitter.send_event("orderFeedback", {
                        "ok": ok,
                        "message": "Pending order dihapus." if ok else "Gagal menghapus pending order."
                    })
                elif action == "reset_stats":
                    self.engine.reset_stats()
                    stats = self.engine.poll_stats()
                    self.emitter.send_event("statsUpdated", stats)
            except Exception as exc:
                log.error("Perintah manual '%s' gagal: %s", cmd, exc)
                self.emitter.send_event("orderFeedback", {
                    "ok": False,
                    "message": f"Error: {exc}"
                })
        return any_executed


class BridgeService:
    """Layanan sentral yang menerima pesan JSON-RPC dan mengontrol PythonEngineWorker."""

    def __init__(self, emitter: _BridgeEmitter):
        self.emitter = emitter
        self.engine: Optional[BotEngine] = None
        self.worker: Optional[PythonEngineWorker] = None
        self._lock = threading.Lock()

        # Konfigurasi logging agar tidak mencemari stdout
        logger = logging.getLogger("mt5bot")
        logger.setLevel(logging.INFO)
        # Handler stderr (hanya untuk error kritis agar tidak menduplikasi log UI)
        stderr_h = logging.StreamHandler(sys.stderr)
        stderr_h.setLevel(logging.ERROR)
        stderr_h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s"))
        logger.addHandler(stderr_h)
        # Handler bridge UI
        logger.addHandler(_BridgeLogHandler(self.emitter))

    def dispatch(self, req: Dict[str, Any]) -> None:
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        try:
            handler = getattr(self, f"handle_{method}", None)
            if not handler:
                self.emitter.send_response(req_id, None, f"Method '{method}' tidak dikenali.")
                return
            result = handler(params)
            if req_id is not None:
                self.emitter.send_response(req_id, result, None)
        except Exception as exc:
            logging.getLogger("mt5bot").error("Error memproses request %s: %s", method, exc)
            if req_id is not None:
                self.emitter.send_response(req_id, None, str(exc))

    def handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pong": True,
            "connected": bool(self.worker and self.worker.running),
            "trading": bool(self.worker and self.worker.trading),
            "version": "1.0.0"
        }

    def handle_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            # Terapkan parameter koneksi jika dikirim
            if "backend" in params:
                settings.backend = str(params["backend"]).lower()
            if "login" in params:
                settings.login = int(params["login"])
            if "password" in params:
                settings.password = str(params["password"])
            if "server" in params:
                settings.server = str(params["server"])
            if "path" in params:
                settings.path = str(params["path"])
            if "mcp_endpoint" in params:
                settings.mcp_endpoint = str(params["mcp_endpoint"])
            if "mcp_api_key" in params:
                settings.mcp_api_key = str(params["mcp_api_key"])
            if "symbol" in params and params["symbol"]:
                settings.symbol = str(params["symbol"])
            if "sim_balance" in params:
                settings.sim_balance = max(100.0, float(params["sim_balance"]))
            if "sim_scenario" in params and params["sim_scenario"]:
                settings.sim_scenario = str(params["sim_scenario"]).strip().lower()
            if "sim_spread_points" in params:
                settings.sim_spread_points = max(1, int(params["sim_spread_points"]))

            # Jika worker lama masih aktif, hentikan
            if self.worker and self.worker.running:
                self.worker.request_stop()
                self.worker.wait(2.0)

            self.engine = BotEngine()
            chart_sym = params.get("chart_symbol") or settings.symbol
            self.worker = PythonEngineWorker(self.engine, self.emitter, chart_sym)
            self.worker.start()
            return {"ok": True, "status": "connecting"}

    def handle_disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if self.worker:
                self.worker.request_stop()
                self.worker.wait(2.0)
                self.worker = None
            if self.engine:
                try:
                    self.engine.disconnect()
                except Exception:
                    pass
                self.engine = None
            return {"ok": True}

    def handle_set_trading(self, params: Dict[str, Any]) -> Dict[str, Any]:
        enabled = bool(params.get("enabled", False))
        if self.worker and self.worker.running:
            if enabled:
                self.engine.rebuild_strategy()
            self.worker.set_trading(enabled)
            self.emitter.send_event("tradingChanged", {"trading": enabled})
            return {"ok": True, "trading": enabled}
        return {"ok": False, "error": "Bot belum terhubung"}

    def handle_manual_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.worker or not self.worker.running:
            return {"ok": False, "error": "Bot belum terhubung"}
        self.worker.cmd_queue.put({
            "action": "market",
            "symbol": params.get("symbol", settings.symbol),
            "side": params.get("side", "buy"),
            "volume": float(params.get("volume", 0.01)),
            "sl": float(params.get("sl", 0.0)),
            "tp": float(params.get("tp", 0.0)),
        })
        self.worker.wake()
        return {"ok": True, "queued": True}

    def handle_pending_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.worker or not self.worker.running:
            return {"ok": False, "error": "Bot belum terhubung"}
        self.worker.cmd_queue.put({
            "action": "pending",
            "symbol": params.get("symbol", settings.symbol),
            "order_type": params.get("order_type", "buy_limit"),
            "volume": float(params.get("volume", 0.01)),
            "price": float(params.get("price", 0.0)),
            "sl": float(params.get("sl", 0.0)),
            "tp": float(params.get("tp", 0.0)),
        })
        self.worker.wake()
        return {"ok": True, "queued": True}

    def handle_close_position(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.worker or not self.worker.running:
            return {"ok": False, "error": "Bot belum terhubung"}
        ticket = params.get("ticket")
        if ticket is not None:
            self.worker.close_queue.put(int(ticket))
            self.worker.wake()
        return {"ok": True}

    def handle_close_all(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.worker or not self.worker.running:
            return {"ok": False, "error": "Bot belum terhubung"}
        self.worker.cmd_queue.put({
            "action": "close_all",
            "symbol": params.get("symbol", "")
        })
        self.worker.wake()
        return {"ok": True}

    def handle_delete_order(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.worker or not self.worker.running:
            return {"ok": False, "error": "Bot belum terhubung"}
        ticket = params.get("ticket")
        if ticket is not None:
            self.worker.cmd_queue.put({
                "action": "delete_order",
                "ticket": int(ticket)
            })
            self.worker.wake()
        return {"ok": True}

    def handle_reset_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.worker and self.worker.running:
            self.worker.cmd_queue.put({"action": "reset_stats"})
            self.worker.wake()
        elif hasattr(self, "engine"):
            self.engine.reset_stats()
            stats = self.engine.poll_stats()
            self.emitter.send_event("statsUpdated", stats)
        return {"ok": True}

    def handle_set_chart_symbol(self, params: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(params.get("symbol", "")).strip()
        if symbol:
            settings.symbol = symbol
            if self.worker:
                self.worker.set_chart_symbol(symbol)
            return {"ok": True, "symbol": symbol}
        return {"ok": False, "error": "Simbol kosong"}

    def handle_set_timeframe(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tf = str(params.get("timeframe", "")).strip().upper()
        valid_tfs = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
        if tf in valid_tfs:
            settings.timeframe_str = tf
            config_store.save()
            if self.worker:
                self.worker.chart_dirty = True
                self.worker.wake()
            self.emitter.send_event("timeframeChanged", {"timeframe": tf})
            return {"ok": True, "timeframe": tf}
        return {"ok": False, "error": f"Timeframe tidak valid: {tf}"}

    def handle_reload_strategy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self.engine:
            self.engine.rebuild_strategy()
            return {"ok": True}
        return {"ok": False, "error": "Engine belum dibuat"}

    def handle_get_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return config_store.as_dict()

    def handle_apply_config(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cfg = params.get("config") or {}
        errs = config_store.apply(cfg)
        if errs:
            return {"ok": False, "errors": errs}
        config_store.save()
        if self.engine:
            self.engine.rebuild_strategy()
        return {"ok": True}

    def handle_get_strategies(self, params: Dict[str, Any]) -> list:
        return strategy_loader.available()

    def handle_list_scripts(self, params: Dict[str, Any]) -> list:
        return script_runtime.list_scripts()

    def handle_load_script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        code = script_runtime.load_script(name)
        return {"name": name, "source": code}

    def handle_save_script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        src = params.get("source", "")
        saved_path = script_runtime.save_script(name, src)
        return {"ok": bool(saved_path), "path": saved_path}

    def handle_validate_script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        src = params.get("source", "")
        try:
            script_runtime.compile_script(src)
            return {"ok": True, "message": "Valid"}
        except script_runtime.ScriptError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "message": f"Syntax error: {exc}"}

    def handle_run_script_simulation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from src.backends.sim_backend import run_script_replay
        src = params.get("source", "")
        symbol = params.get("symbol") or settings.symbol or "XAUUSDm"
        timeframe = params.get("timeframe") or settings.timeframe_str or "M5"
        scenario = params.get("scenario") or getattr(settings, "sim_scenario", "volatile") or "volatile"
        bars = int(params.get("bars", 120) or 120)
        initial_balance = float(params.get("initial_balance", getattr(settings, "sim_balance", 10000.0)) or 10000.0)
        spread_points = int(params.get("spread_points", getattr(settings, "sim_spread_points", 25)) or 25)

        res = run_script_replay(
            source=src,
            symbol=symbol,
            timeframe=timeframe,
            scenario=scenario,
            bars=bars,
            initial_balance=initial_balance,
            spread_points=spread_points,
        )
        self.emitter.send_event("simulationResult", res)
        return res

    def handle_verify_algo_trading(self, params: Dict[str, Any]) -> Dict[str, Any]:
        backend = self.engine.backend if self.engine else None
        if not backend:
            return {
                "ok": False,
                "connected": False,
                "status": "OFFLINE",
                "summary": "Bot belum terhubung ke terminal MT5.",
                "issues": ["Koneksi ke MT5 belum aktif."],
                "solutions": ["Buka tab Login dan klik tombol 'Login & Connect'."]
            }
        acc = backend.account_info() or {}
        server_connected = bool(acc.get("server_connected", False))
        experts_allowed = bool(acc.get("experts_trade_allowed", True))
        mcp_allowed = bool(acc.get("mcp_trade_allowed", True))
        account_trade_allowed = bool(acc.get("trade_allowed", True))

        issues = []
        solutions = []
        ok = True

        if not server_connected:
            ok = False
            issues.append("Terminal MT5 belum tersambung ke server broker.")
            solutions.append("Pastikan koneksi internet aktif dan terminal MT5 sudah login.")
        if not experts_allowed:
            ok = False
            issues.append("Tombol 'Algo Trading' di toolbar MT5 NONAKTIF.")
            solutions.append("Klik tombol 'Algo Trading' di toolbar atas MT5 sampai HIJAU (Ctrl+E).")
        if not mcp_allowed:
            ok = False
            issues.append("Server MCP MT5 belum mengizinkan eksekusi trading.")
            solutions.append("Buka MT5 -> Tools -> Options -> tab MCP -> aktifkan 'Enable internal server'.")
        if not account_trade_allowed:
            ok = False
            issues.append("Akun berstatus Read-Only / Investor Password.")
            solutions.append("Login dengan Master Trading Password.")

        return {
            "ok": ok,
            "connected": True,
            "server_connected": server_connected,
            "experts_trade_allowed": experts_allowed,
            "mcp_trade_allowed": mcp_allowed,
            "account_trade_allowed": account_trade_allowed,
            "login": acc.get("login", 0),
            "server": acc.get("server", ""),
            "status": "OK" if ok else "WARNING",
            "summary": "Semua izin aktif!" if ok else "Izin trading belum lengkap.",
            "issues": issues,
            "solutions": solutions,
        }


def main() -> int:
    # Atur encoding UTF-8 untuk I/O
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    emitter = _BridgeEmitter()
    service = BridgeService(emitter)

    # Muat konfigurasi awal
    config_store.load()

    # Sinyalkan bridge siap
    emitter.send_event("ready", {"version": "1.0.0", "pid": os.getpid()})

    # Baca baris request dari stdin sampai EOF (menggunakan readline untuk menghindari buffering pipa)
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line_str = line.strip()
        if not line_str:
            continue
        try:
            req = json.loads(line_str)
        except Exception as exc:
            emitter.send_response(None, None, f"JSON parse error: {exc}")
            continue

        if req.get("method") == "exit":
            service.handle_disconnect({})
            break

        service.dispatch(req)

    # Cleanup saat stdin tertutup (aplikasi C++ quit)
    service.handle_disconnect({})
    return 0


if __name__ == "__main__":
    sys.exit(main())
