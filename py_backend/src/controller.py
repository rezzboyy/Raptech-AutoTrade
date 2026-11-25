"""Jembatan antara logika bot (Python) dan antarmuka QML.

Desain thread-safety:
    - SEMUA panggilan MT5 terjadi di satu worker thread (loop tunggal).
    - QML memanggil slot di main thread; permintaan yang butuh MT5 (mis. tutup
      posisi) diantrikan lewat queue thread-safe dan dieksekusi oleh worker.
    - Worker mengirim data ke UI lewat sinyal Qt (koneksi queued antar-thread).

State:
    - connected: worker aktif & terhubung ke MT5 (monitoring berjalan).
    - trading: bila True, worker mengeksekusi strategi (buka order).
"""

import logging
import os
import queue

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot, Property
from PySide6.QtQml import QJSValue

from config.settings import settings
from src.bot_engine import BotEngine
from src import config_store
from src import credential_store
from src import mcp_profile_store
from src import strategy_loader


def _to_py_dict(value) -> dict:
    """Normalkan nilai dari QML menjadi dict Python.

    QML dapat mengirim objek JS sebagai QJSValue (tidak langsung bisa di-dict()),
    QVariantMap, atau dict. Fungsi ini menyeragamkannya.
    """
    if isinstance(value, QJSValue):
        value = value.toVariant()
    if isinstance(value, dict):
        return dict(value)
    return {}


class _SignalEmitter(QObject):
    """Objek kecil untuk memancarkan pesan log sebagai sinyal Qt."""

    message = Signal(str)


class _QtLogHandler(logging.Handler):
    """Handler logging yang meneruskan setiap record ke sinyal Qt."""

    def __init__(self, emitter: _SignalEmitter):
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emitter.message.emit(self.format(record))
        except Exception:
            pass


class _Worker(QObject):
    """Loop tunggal yang menjalankan monitoring + trading di satu thread."""

    accountUpdated = Signal(dict)
    positionsUpdated = Signal(list)
    ordersUpdated = Signal(list)
    journalUpdated = Signal(dict)
    candlesUpdated = Signal(str, "QVariant")
    symbolsListed = Signal(list)
    statsUpdated = Signal(dict)
    equityUpdated = Signal(list)
    autoTradingDisabled = Signal(str)
    connectedChanged = Signal(bool)
    chartSymbolChanged = Signal(str)
    stopped = Signal()

    # Interval refresh chart (detik).
    CHART_INTERVAL = 5

    def __init__(self, engine: BotEngine, close_queue: "queue.Queue",
                 cmd_queue: "queue.Queue" = None, chart_symbol: str = ""):
        super().__init__()
        self._engine = engine
        self._close_queue = close_queue
        self._cmd_queue = cmd_queue if cmd_queue is not None else queue.Queue()
        self._running = False
        self._trading = False
        self._chart_symbol = chart_symbol
        self._chart_dirty = True  # paksa fetch awal

    def set_trading(self, enabled: bool) -> None:
        self._trading = enabled

    def set_chart_symbol(self, symbol: str) -> None:
        self._chart_symbol = symbol
        self._chart_dirty = True  # refresh segera saat simbol berubah

    def request_stop(self) -> None:
        self._running = False

    @Slot()
    def run(self) -> None:
        from config.settings import settings
        from src.logger import get_logger
        _log = get_logger("mt5bot")

        # Bungkus connect agar error/hang tidak membuat UI menggantung di
        # "Menghubungkan..." — thread harus selalu memberi kabar balik.
        try:
            connected = self._engine.connect()
        except Exception as exc:  # noqa: BLE001
            _log.error("Gagal menghubungkan ke MT5: %s", exc)
            connected = False

        if not connected:
            self.connectedChanged.emit(False)
            self.stopped.emit()
            return

        self._running = True
        self.connectedChanged.emit(True)

        tick = 0
        try:
            # Sambungkan jurnal aksi skrip (aman antar-thread lewat sinyal Qt).
            self._engine.on_journal = self.journalUpdated.emit

            # Kirim daftar simbol untuk selektor chart.
            self.symbolsListed.emit(self._engine.list_symbols())
            if not self._chart_symbol or self._chart_symbol != settings.symbol:
                self._chart_symbol = settings.symbol
                self.chartSymbolChanged.emit(self._chart_symbol)

            while self._running:
                # 1) Monitoring akun & posisi.
                account = self._engine.poll_account()
                if account:
                    self.accountUpdated.emit(account)

                # Jika experts_trade_allowed masih false, coba refresh otomatis tiap
                # 10 tick (agar di RDP tidak perlu reconnect manual saat MT5 diperbaiki).
                backend = self._engine.backend
                if (not getattr(backend, "_experts_trade_allowed", True)
                        and tick % 10 == 0):
                    try:
                        backend.account_info()  # memperbarui _experts_trade_allowed
                    except Exception:  # noqa: BLE001
                        pass
                self.positionsUpdated.emit(self._engine.poll_positions())

                # Proteksi SL/TP virtual dipantau tiap detik (aktif walau auto-trading off).
                self._engine.check_virtual_exits()

                # 2) Refresh chart & statistik (throttled / saat simbol berubah).
                if self._chart_dirty or tick % self.CHART_INTERVAL == 0:
                    sym = self._chart_symbol
                    chart_payload = self._engine.poll_chart(sym)
                    self.candlesUpdated.emit(sym, chart_payload)

                    stats = self._engine.poll_stats()
                    self.statsUpdated.emit(stats)

                    self.ordersUpdated.emit(self._engine.poll_orders())

                    bal = account.get("balance", 0.0) if account else 0.0
                    eq = account.get("equity", 0.0) if account else 0.0
                    curve = self._engine.poll_equity_curve(bal, eq)
                    self.equityUpdated.emit(curve)

                    self._chart_dirty = False

                # 3) Proses permintaan tutup posisi + perintah order manual dari UI.
                self._drain_close_requests()
                self._drain_commands()

                # 4) Langkah trading pada kelipatan interval.
                if self._trading and tick % max(1, settings.loop_interval) == 0:
                    ok = self._engine.process_trading_step()
                    if ok is False:
                        self._trading = False
                        self.autoTradingDisabled.emit("Proteksi risiko terpicu (drawdown harian / equity cut-loss). Auto trading dinonaktifkan demi proteksi modal.")

                tick += 1

                # Tidur 1 detik bertahap agar stop cepat direspons.
                QThread.sleep(1)
        except Exception as exc:  # noqa: BLE001
            _log.error("Loop worker berhenti karena error: %s", exc)
        finally:
            try:
                self._engine.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.connectedChanged.emit(False)
            self.stopped.emit()

    def _drain_close_requests(self) -> None:
        while True:
            try:
                ticket = self._close_queue.get_nowait()
            except queue.Empty:
                break
            self._engine.close_ticket(ticket)

    def _drain_commands(self) -> None:
        """Eksekusi perintah order manual dari UI (thread worker)."""
        while True:
            try:
                cmd = self._cmd_queue.get_nowait()
            except queue.Empty:
                break
            try:
                action = cmd.get("action")
                if action == "market":
                    self._engine.manual_market_order(
                        cmd["symbol"], cmd["side"], cmd["volume"],
                        cmd.get("sl", 0.0), cmd.get("tp", 0.0))
                elif action == "pending":
                    self._engine.place_pending_order(
                        cmd["symbol"], cmd["order_type"], cmd["volume"],
                        cmd["price"], cmd.get("sl", 0.0), cmd.get("tp", 0.0))
                elif action == "close_all":
                    self._engine.close_all(cmd.get("symbol", ""))
                elif action == "delete_order":
                    self._engine.delete_pending(cmd["ticket"])
            except Exception as exc:  # noqa: BLE001
                from src.logger import get_logger
                get_logger("mt5bot").error("Perintah '%s' gagal: %s", cmd, exc)


class BotController(QObject):
    """Antarmuka yang diekspos ke QML untuk mengontrol bot."""

    logMessage = Signal(str)
    statusChanged = Signal(str)
    connectedChanged = Signal(bool)
    tradingChanged = Signal(bool)
    accountChanged = Signal()
    positionsChanged = Signal(list)
    ordersChanged = Signal(list)
    configError = Signal(str)
    profilesChanged = Signal(list)
    mcpProfilesChanged = Signal(list)
    backendChanged = Signal(str)
    chartUpdated = Signal(str, "QVariant")
    symbolsAvailable = Signal(list)
    chartSymbolChanged = Signal(str)
    statsChanged = Signal()
    equityChanged = Signal()
    journalChanged = Signal()

    def __init__(self):
        super().__init__()
        self._connected = False
        self._trading = False
        self._status = "Terputus"

        self._engine = BotEngine()
        self._thread = None
        self._worker = None
        self._close_queue = queue.Queue()
        self._cmd_queue = queue.Queue()

        # Nama profil yang akan disimpan otomatis setelah login sukses.
        self._pending_profile_name = None
        self._pending_mcp_name = None

        # Simbol yang ditampilkan di chart (default = simbol trading).
        self._chart_symbol = settings.symbol

        # Snapshot akun.
        self._balance = 0.0
        self._equity = 0.0
        self._margin = 0.0
        self._free_margin = 0.0
        self._profit = 0.0
        self._currency = ""
        self._account_type = "?"
        self._account_server = ""
        self._server_connected = False
        self._trade_allowed = False

        # Statistik & kurva ekuitas.
        self._stats = {
            "total_trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
            "win_rate": 0.0, "profit_factor": 0.0, "gross_profit": 0.0,
            "gross_loss": 0.0, "net_profit": 0.0, "avg_profit": 0.0,
            "avg_loss": 0.0, "max_profit": 0.0, "max_loss": 0.0,
        }
        self._equity_curve = []
        self._log_history = []
        self._journal = []  # jurnal aksi skrip: [{time, action, symbol, detail, ok}]

        # Muat konfigurasi tersimpan (bila ada).
        config_store.load()

        # Sambungkan logger bot ke UI.
        self._emitter = _SignalEmitter()
        self._emitter.message.connect(self.logMessage)
        self._emitter.message.connect(self._record_log)
        handler = _QtLogHandler(self._emitter)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S")
        )
        logging.getLogger("mt5bot").addHandler(handler)

    def _record_log(self, msg: str) -> None:
        self._log_history.append(msg)
        if len(self._log_history) > 5000:
            self._log_history.pop(0)

    # ----- Properties: state -----

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(bool, notify=tradingChanged)
    def trading(self) -> bool:
        return self._trading

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=backendChanged)
    def backend(self) -> str:
        return getattr(settings, "backend", "native")

    @Slot(str)
    def setBackend(self, name: str) -> None:
        name = (name or "native").lower()
        if name not in ("native", "mcp"):
            return
        if settings.backend != name:
            settings.backend = name
            self.backendChanged.emit(name)

    # ----- Properties: statistik & kurva ekuitas -----

    @Property("QVariant", notify=statsChanged)
    def stats(self) -> dict:
        return self._stats

    @Property("QVariant", notify=equityChanged)
    def equityCurve(self) -> list:
        return self._equity_curve

    # ----- Properties: akun -----

    @Property(float, notify=accountChanged)
    def balance(self) -> float:
        return self._balance

    @Property(float, notify=accountChanged)
    def equity(self) -> float:
        return self._equity

    @Property(float, notify=accountChanged)
    def margin(self) -> float:
        return self._margin

    @Property(float, notify=accountChanged)
    def freeMargin(self) -> float:
        return self._free_margin

    @Property(float, notify=accountChanged)
    def profit(self) -> float:
        return self._profit

    @Property(str, notify=accountChanged)
    def currency(self) -> str:
        return self._currency

    @Property(str, notify=accountChanged)
    def accountType(self) -> str:
        return self._account_type

    @Property(str, notify=accountChanged)
    def accountServer(self) -> str:
        return self._account_server

    @Property(bool, notify=accountChanged)
    def serverConnected(self) -> bool:
        return self._server_connected

    @Property(bool, notify=accountChanged)
    def tradeAllowed(self) -> bool:
        return self._trade_allowed

    # ----- Setter internal -----

    def _set_status(self, value: str) -> None:
        if self._status != value:
            self._status = value
            self.statusChanged.emit(value)

    def _set_connected(self, value: bool) -> None:
        if self._connected != value:
            self._connected = value
            self.connectedChanged.emit(value)

    def _set_trading(self, value: bool) -> None:
        if self._trading != value:
            self._trading = value
            self.tradingChanged.emit(value)

    # ----- Slot kontrol -----

    @Slot()
    def connectBot(self) -> None:
        if self._connected or self._thread is not None:
            return

        self._set_status("Menghubungkan...")

        # Bangun ulang backend sesuai pilihan terkini (native/mcp) sebelum connect.
        self._engine.rebuild_backend()

        self._thread = QThread()
        self._worker = _Worker(self._engine, self._close_queue, self._cmd_queue, self._chart_symbol)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.accountUpdated.connect(self._on_account)
        self._worker.positionsUpdated.connect(self._on_positions)
        self._worker.ordersUpdated.connect(self._on_orders)
        self._worker.journalUpdated.connect(self._on_journal)
        self._worker.candlesUpdated.connect(self._on_candles)
        self._worker.symbolsListed.connect(self._on_symbols)
        self._worker.statsUpdated.connect(self._on_stats)
        self._worker.equityUpdated.connect(self._on_equity)
        self._worker.autoTradingDisabled.connect(self._on_auto_trading_disabled)
        self._worker.connectedChanged.connect(self._on_worker_connected)
        self._worker.chartSymbolChanged.connect(self._on_worker_chart_symbol)
        self._worker.stopped.connect(self._on_worker_stopped)

        self._thread.start()

    @Slot()
    def disconnectBot(self) -> None:
        if self._worker is not None:
            self._set_status("Memutus...")
            self._set_trading(False)
            if self._worker is not None:
                self._worker.set_trading(False)
            self._worker.request_stop()

    @Slot()
    def logoutAccount(self) -> None:
        """Logout dan putuskan akun MT5 secara bersih dari UI."""
        self.disconnectBot()
        self.positionsChanged.emit([])
        self.ordersChanged.emit([])
        self.logMessage.emit("[SISTEM] Akun berhasil logout / terputus.")

    @Slot(bool)
    def setTrading(self, enabled: bool) -> None:
        if not self._connected:
            self.configError.emit("Hubungkan ke MT5 dulu sebelum mengaktifkan trading.")
            return
        self._set_trading(enabled)
        if self._worker is not None:
            self._worker.set_trading(enabled)
        self._set_status("Trading aktif" if enabled else "Terhubung")

    @Slot(int)
    def closePosition(self, ticket: int) -> None:
        if not self._connected:
            self.configError.emit("Tidak terhubung ke MT5.")
            return
        self._close_queue.put(int(ticket))

    # ----- Slot order manual (thread-safe via antrian) -----

    @Slot(str, str, float, float, float)
    def openManualOrder(self, symbol: str, side: str, volume: float,
                        sl: float = 0.0, tp: float = 0.0) -> None:
        if not self._connected:
            self.configError.emit("Hubungkan ke MT5 dulu sebelum kirim order.")
            return
        if volume <= 0:
            self.configError.emit("Volume harus > 0.")
            return
        self._cmd_queue.put({
            "action": "market", "symbol": symbol, "side": str(side).lower(),
            "volume": float(volume), "sl": float(sl), "tp": float(tp),
        })

    @Slot(str, str, float, float, float, float)
    def placePendingOrder(self, symbol: str, order_type: str, volume: float,
                          price: float, sl: float = 0.0, tp: float = 0.0) -> None:
        if not self._connected:
            self.configError.emit("Hubungkan ke MT5 dulu sebelum pasang pending order.")
            return
        if volume <= 0 or price <= 0:
            self.configError.emit("Volume dan harga pending order harus > 0.")
            return
        self._cmd_queue.put({
            "action": "pending", "symbol": symbol, "order_type": str(order_type).lower(),
            "volume": float(volume), "price": float(price), "sl": float(sl), "tp": float(tp),
        })

    @Slot()
    def closeAllPositions(self) -> None:
        if not self._connected:
            self.configError.emit("Tidak terhubung ke MT5.")
            return
        self._cmd_queue.put({"action": "close_all", "symbol": ""})

    @Slot(int)
    def deletePendingOrder(self, ticket: int) -> None:
        if not self._connected:
            self.configError.emit("Tidak terhubung ke MT5.")
            return
        self._cmd_queue.put({"action": "delete_order", "ticket": int(ticket)})

    # ----- Slot chart -----

    @Property(str, notify=chartSymbolChanged)
    def chartSymbol(self) -> str:
        return self._chart_symbol

    @Slot(str)
    def setChartSymbol(self, symbol: str) -> None:
        symbol = (symbol or "").strip()
        if not symbol:
            return
        if self._engine and hasattr(self._engine.backend, "resolve_symbol"):
            try:
                resolved = self._engine.backend.resolve_symbol(symbol)
                if resolved:
                    symbol = resolved
            except Exception:
                pass
        self._chart_symbol = symbol
        from config.settings import settings
        settings.symbol = symbol
        config_store.save()
        if self._worker is not None:
            self._worker.set_chart_symbol(symbol)
        self.chartSymbolChanged.emit(symbol)

    # ----- Slot login & profil kredensial -----

    @Slot(result="QVariant")
    def listProfiles(self) -> list:
        return credential_store.list_profiles()

    @Slot("QVariant", str, result=bool)
    def loginAndConnect(self, creds, save_name: str = "") -> bool:
        """Terapkan kredensial lalu connect. Auto-simpan profil bila sukses.

        Jika password kosong (mis. profil sudah dimuat sebelumnya), password
        yang ada di settings tetap dipakai.
        """
        data = _to_py_dict(creds)
        if not data.get("password"):
            data["password"] = settings.password  # pakai password profil yang dimuat

        errors = credential_store.validate(data)
        if errors:
            self.configError.emit("; ".join(errors))
            return False

        self.setBackend("native")
        credential_store.apply_to_settings(data)
        self._pending_profile_name = (save_name or "").strip() or None
        self.connectBot()
        return True

    # ----- Slot koneksi & profil MCP -----

    @Slot("QVariant", str, result=bool)
    def connectMcp(self, cfg, save_name: str = "") -> bool:
        """Terapkan konfigurasi MCP lalu connect. Auto-simpan profil bila sukses.

        Jika API Key kosong (mis. profil sudah dimuat), pakai yang ada di settings.
        """
        data = _to_py_dict(cfg)
        if not data.get("api_key"):
            data["api_key"] = settings.mcp_api_key
        if not data.get("endpoint"):
            data["endpoint"] = settings.mcp_endpoint

        errors = mcp_profile_store.validate(data)
        if errors:
            self.configError.emit("; ".join(errors))
            return False

        mcp_profile_store.apply_to_settings(data)
        self.backendChanged.emit(settings.backend)
        self._pending_mcp_name = (save_name or "").strip() or None
        self.connectBot()
        return True

    @Slot(result="QVariant")
    def listMcpProfiles(self) -> list:
        return mcp_profile_store.list_profiles()

    @Slot(str, result="QVariant")
    def loadMcpProfileFile(self, url: str) -> dict:
        """Muat profil MCP dari file (path atau file://). Isi form, siap connect."""
        path = QUrl(url).toLocalFile() if str(url).startswith("file:") else url
        cfg = mcp_profile_store.load_profile(path)
        if not cfg:
            self.configError.emit("Gagal memuat profil MCP dari file.")
            return {}
        mcp_profile_store.apply_to_settings(cfg)
        self.backendChanged.emit(settings.backend)
        self.logMessage.emit(f"[UI] Profil MCP '{cfg.get('name','')}' dimuat.")
        return {
            "name": cfg.get("name", ""),
            "endpoint": cfg.get("endpoint", ""),
            "hasKey": bool(cfg.get("api_key")),
        }

    @Slot(str, result=bool)
    def deleteMcpProfile(self, file_path: str) -> bool:
        ok = mcp_profile_store.delete_profile(file_path)
        if ok:
            self.mcpProfilesChanged.emit(mcp_profile_store.list_profiles())
        return ok

    @Slot(str, result="QVariant")
    def loadProfileFile(self, url: str) -> dict:
        """Muat profil dari file (path atau URL file://). Isi form, siap connect."""
        path = QUrl(url).toLocalFile() if str(url).startswith("file:") else url
        creds = credential_store.load_profile(path)
        if not creds:
            self.configError.emit("Gagal memuat profil dari file.")
            return {}
        credential_store.apply_to_settings(creds)
        self.logMessage.emit(f"[UI] Profil '{creds.get('name','')}' dimuat.")
        # Password sengaja tidak dikirim ke UI (dipakai langsung dari settings).
        return {
            "name": creds.get("name", ""),
            "login": creds.get("login", 0),
            "server": creds.get("server", ""),
            "path": creds.get("path", ""),
            "hasPassword": bool(creds.get("password")),
        }

    @Slot(str, result=bool)
    def deleteProfile(self, file_path: str) -> bool:
        ok = credential_store.delete_profile(file_path)
        if ok:
            self.profilesChanged.emit(credential_store.list_profiles())
        return ok

    # ----- Slot konfigurasi -----

    @Slot(result="QVariant")
    def getStrategies(self) -> list:
        """Daftar strategi tersedia + skema parameternya (untuk UI)."""
        return strategy_loader.available()

    @Slot(result="QVariant")
    def getConfig(self) -> dict:
        return config_store.as_dict()

    # ----- Slot Mode Programmer (skrip strategi kustom) -----

    @Slot(result=str)
    def scriptTemplate(self) -> str:
        from strategies import script_runtime
        return script_runtime.DEFAULT_TEMPLATE

    @Slot(result="QVariant")
    def apiReference(self) -> list:
        """Referensi API `ctx.*` untuk panel Bantuan API di tab Programmer.

        Tiap item: {signature, desc, snippet}. `snippet` disisipkan ke editor.
        """
        return [
            {"group": "Data Harga", "items": [
                {"signature": "ctx.close", "desc": "List harga close (lama→baru).", "snippet": "ctx.close"},
                {"signature": "ctx.open / high / low", "desc": "List harga OHLC.", "snippet": "ctx.high"},
                {"signature": "ctx.volume", "desc": "List volume tick.", "snippet": "ctx.volume"},
                {"signature": "ctx.rates(tf, count)", "desc": "OHLCV multi-timeframe ('H1', 'M15').", "snippet": 'ctx.rates("H1", 200)'},
            ]},
            {"group": "Harga Live & Simbol", "items": [
                {"signature": "ctx.bid / ctx.ask", "desc": "Harga live saat ini.", "snippet": "ctx.ask"},
                {"signature": "ctx.spread", "desc": "Spread dalam points.", "snippet": "ctx.spread"},
                {"signature": "ctx.point / ctx.digits", "desc": "Ukuran 1 point & desimal.", "snippet": "ctx.point"},
                {"signature": "ctx.volume_min / step / max", "desc": "Batas & step lot broker.", "snippet": "ctx.volume_step"},
                {"signature": "ctx.stop_level / freeze_level", "desc": "Jarak stop minimal broker (points).", "snippet": "ctx.stop_level"},
                {"signature": "ctx.symbol", "desc": "Nama simbol aktif.", "snippet": "ctx.symbol"},
            ]},
            {"group": "Akun & Posisi", "items": [
                {"signature": "ctx.balance / ctx.equity", "desc": "Saldo & ekuitas akun.", "snippet": "ctx.balance"},
                {"signature": "ctx.position", "desc": "Posisi aktif (dict) atau None.", "snippet": "ctx.position"},
                {"signature": "ctx.positions", "desc": "Semua posisi simbol ini (list).", "snippet": "ctx.positions"},
                {"signature": "ctx.pending_orders", "desc": "Semua pending order aktif (list).", "snippet": "ctx.pending_orders"},
                {"signature": "ctx.state", "desc": "State persisten skrip antar-bar & restart.", "snippet": "ctx.state"},
            ]},
            {"group": "Waktu / Sesi", "items": [
                {"signature": "ctx.hour / ctx.minute", "desc": "Jam & menit bar.", "snippet": "ctx.hour"},
                {"signature": "ctx.weekday", "desc": "0=Senin .. 6=Minggu.", "snippet": "ctx.weekday"},
                {"signature": "ctx.time / ctx.now", "desc": "Waktu bar / sekarang (UTC).", "snippet": "ctx.time"},
            ]},
            {"group": "Indikator", "items": [
                {"signature": "ctx.sma(src, n)", "desc": "Simple Moving Average.", "snippet": "ctx.sma(ctx.close, 20)"},
                {"signature": "ctx.ema(src, n)", "desc": "Exponential MA.", "snippet": "ctx.ema(ctx.close, 20)"},
                {"signature": "ctx.wma(src, n)", "desc": "Weighted MA.", "snippet": "ctx.wma(ctx.close, 20)"},
                {"signature": "ctx.rsi(src, n)", "desc": "RSI 0..100.", "snippet": "ctx.rsi(ctx.close, 14)"},
                {"signature": "ctx.atr(n)", "desc": "Average True Range.", "snippet": "ctx.atr(14)"},
                {"signature": "ctx.stdev(src, n)", "desc": "Standar deviasi.", "snippet": "ctx.stdev(ctx.close, 20)"},
                {"signature": "ctx.highest/lowest(src, n)", "desc": "Nilai tertinggi/terendah n bar.", "snippet": "ctx.highest(ctx.high, 20)"},
                {"signature": "ctx.bbands(src, n, mult)", "desc": "(upper, mid, lower) Bollinger.", "snippet": "upper, mid, lower = ctx.bbands(ctx.close, 20, 2.0)"},
                {"signature": "ctx.macd(src, f, s, sig)", "desc": "(macd, signal, hist).", "snippet": "macd, signal, hist = ctx.macd(ctx.close, 12, 26, 9)"},
                {"signature": "ctx.stochastic(k, d, smooth)", "desc": "(%K, %D) 0..100.", "snippet": "k, d = ctx.stochastic(14, 3, 3)"},
                {"signature": "ctx.adx(n)", "desc": "(ADX, +DI, -DI).", "snippet": "adx, plus_di, minus_di = ctx.adx(14)"},
                {"signature": "ctx.cci(n)", "desc": "Commodity Channel Index.", "snippet": "ctx.cci(20)"},
                {"signature": "ctx.vwap(n)", "desc": "VWAP bergulir.", "snippet": "ctx.vwap(14)"},
                {"signature": "ctx.williams_r(n)", "desc": "Williams %R (-100..0).", "snippet": "ctx.williams_r(14)"},
                {"signature": "ctx.obv()", "desc": "On-Balance Volume.", "snippet": "ctx.obv()"},
                {"signature": "ctx.mfi(n)", "desc": "Money Flow Index 0..100.", "snippet": "ctx.mfi(14)"},
                {"signature": "ctx.donchian(n)", "desc": "(upper, mid, lower).", "snippet": "upper, mid, lower = ctx.donchian(20)"},
                {"signature": "ctx.parabolic_sar(step, max)", "desc": "List nilai Parabolic SAR.", "snippet": "ctx.parabolic_sar(0.02, 0.2)"},
                {"signature": "ctx.supertrend(n, mult)", "desc": "(garis, arah +1/-1).", "snippet": "st, direction = ctx.supertrend(10, 3.0)"},
                {"signature": "ctx.ichimoku(...)", "desc": "(tenkan, kijun, senkou_a, senkou_b, chikou).", "snippet": "tenkan, kijun, sa, sb, chikou = ctx.ichimoku()"},
                {"signature": "ctx.pivot_points()", "desc": "dict {pivot, r1, s1, ...}.", "snippet": "piv = ctx.pivot_points()"},
                {"signature": "ctx.crossover(a, b)", "desc": "True bila a memotong ke atas b.", "snippet": "ctx.crossover(fast, slow)"},
                {"signature": "ctx.crossunder(a, b)", "desc": "True bila a memotong ke bawah b.", "snippet": "ctx.crossunder(fast, slow)"},
            ]},
            {"group": "Perintah Order", "items": [
                {"signature": "ctx.buy(...)", "desc": "Buka BUY (volume/sl_points/tp_points/sl/tp/risk).", "snippet": "return ctx.buy(volume=0.01, sl_points=300, tp_points=600)"},
                {"signature": "ctx.sell(...)", "desc": "Buka SELL (arg sama).", "snippet": "return ctx.sell(volume=0.01, sl_points=300, tp_points=600)"},
                {"signature": "ctx.buy_stop / sell_stop(...)", "desc": "Pasang pending Stop order.", "snippet": "ctx.buy_stop(price, volume=0.05)"},
                {"signature": "ctx.buy_limit / sell_limit(...)", "desc": "Pasang pending Limit order.", "snippet": "ctx.buy_limit(price, volume=0.05)"},
                {"signature": "ctx.modify_order(ord, price)", "desc": "Ubah harga pending order.", "snippet": "ctx.modify_order(ord, new_price)"},
                {"signature": "ctx.delete_order(ord)", "desc": "Hapus pending order.", "snippet": "ctx.delete_order(ord)"},
                {"signature": "ctx.close_position(pos)", "desc": "Tutup posisi (default: posisi aktif).", "snippet": "return ctx.close_position(ctx.position)"},
                {"signature": "ctx.close_side(side)", "desc": "Tutup semua posisi 'BUY' atau 'SELL'.", "snippet": 'ctx.close_side("BUY")'},
                {"signature": "ctx.close_all()", "desc": "Tutup semua posisi simbol ini.", "snippet": "return ctx.close_all()"},
                {"signature": "ctx.modify(pos, sl, tp)", "desc": "Ubah SL/TP (harga absolut).", "snippet": "return ctx.modify(ctx.position, sl=1.2000, tp=1.2600)"},
            ]},
            {"group": "Pengaturan & Parameter", "items": [
                {"signature": "SETTINGS = {...}", "desc": "Pengaturan trading di skrip (symbol, tf, lot, sl, tp, dll).", "snippet": "SETTINGS = {\n    \"symbol\": \"EURUSDm\",\n    \"timeframe\": \"M5\",\n    \"volume\": 0.01,\n    \"sl_points\": 300,\n    \"tp_points\": 600,\n}\n"},
                {"signature": "PARAMS = {...}", "desc": "Parameter strategi (dict atau list skema).", "snippet": "PARAMS = {\n    \"fast\": 12,\n    \"slow\": 26,\n}\n"},
                {"signature": "ctx.params.key / [\"key\"]", "desc": "Baca parameter via dot atau dict indexing.", "snippet": "ctx.params.fast"},
                {"signature": "ctx.settings.key", "desc": "Baca nilai konfigurasi aktif dari SETTINGS.", "snippet": "ctx.settings.symbol"},
            ]},
            {"group": "Lain-lain", "items": [
                {"signature": "ctx.params[\"key\"]", "desc": "Baca parameter dari PARAMS.", "snippet": "ctx.params[\"fast\"]"},
                {"signature": "ctx.log(msg)", "desc": "Tulis pesan ke log bot.", "snippet": "ctx.log(\"pesan\")"},
                {"signature": "kerangka on_bar", "desc": "Kerangka dasar strategi.", "snippet": "def on_bar(ctx):\n    return None\n"},
            ]},
        ]

    @Slot(result="QVariant")
    def settingsReference(self) -> list:
        """Daftar referensi variabel SETTINGS yang didukung bot untuk menu Mode Programmer."""
        return [
            {
                "group": "Pasar & Simbol",
                "items": [
                    {"name": "symbol", "type": "str", "default": '"EURUSDm"', "desc": "Simbol broker aktif (Exness sering berakhiran 'm').", "snippet": '"symbol": "EURUSDm",'},
                    {"name": "timeframe", "type": "str", "default": '"M5"', "desc": "Timeframe candle (M1, M5, M15, M30, H1, H4, D1).", "snippet": '"timeframe": "M5",'},
                    {"name": "volume", "type": "float", "default": "0.01", "desc": "Ukuran lot per order (atau 'lot').", "snippet": '"volume": 0.01,'},
                    {"name": "risk_per_trade", "type": "float", "default": "0.01", "desc": "Fraksi risiko per trade bila lot dihitung dinamis (0.01 = 1%).", "snippet": '"risk_per_trade": 0.01,'},
                    {"name": "max_positions", "type": "int", "default": "1", "desc": "Maksimal posisi terbuka bersamaan pada simbol ini.", "snippet": '"max_positions": 1,'},
                    {"name": "magic_number", "type": "int", "default": "100200", "desc": "ID identifikasi unik order bot ini di MT5.", "snippet": '"magic_number": 100200,'},
                    {"name": "comment", "type": "str", "default": '"XAVIQ Script"', "desc": "Catatan teks pada tiket order broker.", "snippet": '"comment": "XAVIQ Script",'},
                ],
            },
            {
                "group": "Stop Loss, Take Profit & Rasio",
                "items": [
                    {"name": "sl_points", "type": "int", "default": "300", "desc": "Jarak Stop Loss dalam points.", "snippet": '"sl_points": 300,'},
                    {"name": "tp_points", "type": "int", "default": "600", "desc": "Jarak Take Profit dalam points.", "snippet": '"tp_points": 600,'},
                    {"name": "risk_reward_ratio", "type": "float", "default": "2.0", "desc": "Rasio RR: TP otomatis dihitung = SL * rasio (mis. 2.0 = TP 2x SL).", "snippet": '"risk_reward_ratio": 2.0,'},
                    {"name": "atr_sl_mult", "type": "float", "default": "1.5", "desc": "SL dinamis berbasis volatilitas (SL = 1.5 * ATR candle terakhir).", "snippet": '"atr_sl_mult": 1.5,'},
                    {"name": "atr_tp_mult", "type": "float", "default": "3.0", "desc": "TP dinamis berbasis volatilitas (TP = 3.0 * ATR candle terakhir).", "snippet": '"atr_tp_mult": 3.0,'},
                    {"name": "sl_percent", "type": "float", "default": "0.5", "desc": "SL dalam persen harga entry (saat mode percent).", "snippet": '"sl_percent": 0.5,'},
                    {"name": "tp_percent", "type": "float", "default": "1.0", "desc": "TP dalam persen harga entry (saat mode percent).", "snippet": '"tp_percent": 1.0,'},
                    {"name": "sl_tp_mode", "type": "str", "default": '"points"', "desc": "Mode hitung SL/TP: 'points' atau 'percent'.", "snippet": '"sl_tp_mode": "points",'},
                ],
            },
            {
                "group": "Trailing Stop & Break-Even",
                "items": [
                    {"name": "trailing_stop_points", "type": "int", "default": "200", "desc": "Jarak trailing stop (points). Otomatis aktif jika > 0.", "snippet": '"trailing_stop_points": 200,'},
                    {"name": "trailing_step_points", "type": "int", "default": "50", "desc": "Langkah penggeseran SL tiap pergerakan harga baru.", "snippet": '"trailing_step_points": 50,'},
                    {"name": "break_even_points", "type": "int", "default": "150", "desc": "Ambang profit (points) saat SL dipindahkan ke harga entry.", "snippet": '"break_even_points": 150,'},
                    {"name": "break_even_offset_points", "type": "int", "default": "10", "desc": "Jarak profit pengunci di atas/bawah entry saat break-even.", "snippet": '"break_even_offset_points": 10,'},
                    {"name": "virtual_sltp_enabled", "type": "bool", "default": "False", "desc": "Sembunyikan level SL/TP dari broker (Virtual SL/TP).", "snippet": '"virtual_sltp_enabled": True,'},
                ],
            },
            {
                "group": "Waktu & Sesi Pasar",
                "items": [
                    {"name": "trade_start_time", "type": "str", "default": '"13:00"', "desc": "Jam mulai trading (format 'HH:MM' UTC). Di luar jam ini entry ditolak.", "snippet": '"trade_start_time": "13:00",'},
                    {"name": "trade_end_time", "type": "str", "default": '"21:00"', "desc": "Jam selesai trading (format 'HH:MM' UTC).", "snippet": '"trade_end_time": "21:00",'},
                    {"name": "close_friday_hour", "type": "int", "default": "20", "desc": "Jam UTC di hari Jumat untuk menutup semua order sebelum akhir pekan.", "snippet": '"close_friday_hour": 20,'},
                    {"name": "active_days", "type": "list", "default": "[0, 1, 2, 3, 4]", "desc": "Hari aktif trading: 0=Senin, 1=Selasa, .. 4=Jumat, 5=Sabtu, 6=Minggu.", "snippet": '"active_days": [0, 1, 2, 3, 4],'},
                ],
            },
            {
                "group": "Kontrol Entry & Anti-Spam Bar",
                "items": [
                    {"name": "close_on_reversal", "type": "bool", "default": "True", "desc": "Tutup posisi berlawanan saat sinyal arah baru muncul (BUY vs SELL).", "snippet": '"close_on_reversal": True,'},
                    {"name": "one_trade_per_bar", "type": "bool", "default": "True", "desc": "Mencegah pembukaan order ganda pada candle bar yang sama.", "snippet": '"one_trade_per_bar": True,'},
                    {"name": "cooldown_bars", "type": "int", "default": "2", "desc": "Jeda minimal N bar setelah order sebelum boleh membuka posisi baru lagi.", "snippet": '"cooldown_bars": 2,'},
                    {"name": "min_margin_level", "type": "float", "default": "200.0", "desc": "Batas minimal Margin Level (%) akun sebelum entry diizinkan.", "snippet": '"min_margin_level": 200.0,'},
                    {"name": "max_holding_bars", "type": "int", "default": "24", "desc": "Tutup otomatis posisi jika sudah terbuka melebihi N candle bar.", "snippet": '"max_holding_bars": 24,'},
                    {"name": "max_slippage_points", "type": "int", "default": "30", "desc": "Toleransi slippage pergeseran harga saat order dikirim.", "snippet": '"max_slippage_points": 30,'},
                ],
            },
            {
                "group": "Proteksi & Risiko Global",
                "items": [
                    {"name": "max_spread_points", "type": "int", "default": "35", "desc": "Tolak entry saat spread pasar melebihi batas ini (points).", "snippet": '"max_spread_points": 35,'},
                    {"name": "daily_drawdown_limit", "type": "float", "default": "0.05", "desc": "Batas rugi harian (0.05 = 5%). Hentikan auto-trading bila terlampaui.", "snippet": '"daily_drawdown_limit": 0.05,'},
                    {"name": "equity_stop_loss", "type": "float", "default": "0.10", "desc": "Tutup semua order & stop bot bila drawdown ekuitas >= 10%.", "snippet": '"equity_stop_loss": 0.10,'},
                    {"name": "max_consecutive_losses", "type": "int", "default": "3", "desc": "Jeda auto-trading setelah N kali loss beruntun.", "snippet": '"max_consecutive_losses": 3,'},
                    {"name": "max_daily_trades", "type": "int", "default": "10", "desc": "Batas maksimal jumlah order selesai per hari.", "snippet": '"max_daily_trades": 10,'},
                    {"name": "max_exposure_lots", "type": "float", "default": "1.0", "desc": "Batas total lot terbuka seluruh posisi bot.", "snippet": '"max_exposure_lots": 1.0,'},
                ],
            },
        ]

    @Slot(result="QVariant")
    def listScripts(self) -> list:
        from strategies import script_runtime
        return script_runtime.list_scripts()

    @Slot(str, result=str)
    def loadScript(self, name: str) -> str:
        if os.path.isfile(name):
            try:
                with open(name, "r", encoding="utf-8") as f:
                    return f.read()
            except OSError:
                pass
        from strategies import script_runtime
        return script_runtime.load_script(name)

    @Slot(str, result="QVariant")
    def loadScriptFile(self, url: str) -> dict:
        """Muat isi skrip dari file sembarang (path absolut atau URL file://).

        Kembalikan dict: {"name": stem, "path": path, "source": content, "ok": True/False, "error": str}.
        """
        path = QUrl(url).toLocalFile() if str(url).startswith("file:") else str(url)
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        path = os.path.abspath(path)

        if not os.path.isfile(path):
            self.configError.emit(f"File skrip tidak ditemukan: {path}")
            return {"name": "", "path": path, "source": "", "ok": False, "error": "File tidak ditemukan"}

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            stem = os.path.splitext(os.path.basename(path))[0]
            self.logMessage.emit(f"[UI] Skrip '{stem}' dimuat dari file: {os.path.basename(path)}")
            return {
                "name": stem,
                "path": path,
                "source": content,
                "ok": True,
                "error": "",
            }
        except Exception as exc:  # noqa: BLE001
            self.configError.emit(f"Gagal membaca file skrip: {exc}")
            return {"name": "", "path": path, "source": "", "ok": False, "error": str(exc)}

    @Slot(str, str, result=bool)
    def saveScript(self, name: str, source: str) -> bool:
        from strategies import script_runtime
        if not (name or "").strip():
            self.configError.emit("Beri nama skrip sebelum menyimpan.")
            return False
        path = script_runtime.save_script(name, source)
        if path:
            self.logMessage.emit(f"[UI] Skrip '{name}' disimpan.")
            return True
        self.configError.emit("Gagal menyimpan skrip.")
        return False

    @Slot("QVariant")
    def attachHighlighter(self, quick_doc) -> None:
        """Pasang syntax highlighter Python ke QQuickTextDocument editor QML."""
        try:
            from PySide6.QtQuick import QQuickTextDocument
            if isinstance(quick_doc, QQuickTextDocument):
                from src.qml_highlighter import PythonHighlighter
                # Simpan referensi agar tidak di-GC.
                self._highlighter = PythonHighlighter(quick_doc.textDocument())
        except Exception as exc:  # noqa: BLE001 - jangan sampai UI gagal load
            self.logMessage.emit(f"[UI] Highlighter dilewati: {exc}")

    @Slot(str, result="QVariant")
    def validateScriptDetail(self, source: str) -> dict:
        """Validasi skrip untuk editor real-time: {ok, line, message}."""
        from strategies.script_runtime import validate_detail
        return validate_detail(source)

    @Slot(str, result=str)
    def validateScript(self, source: str) -> str:
        """Kompilasi skrip. Kembalikan "" bila valid, atau pesan error."""
        from strategies.script_runtime import compile_script, ScriptError
        try:
            ns = compile_script(source)
            nparams = len(ns.get("PARAMS", []) or [])
            self.logMessage.emit(f"[UI] Skrip valid ({nparams} parameter).")
            return ""
        except ScriptError as exc:
            return str(exc)
        except Exception as exc:  # noqa: BLE001
            return str(exc)

    @Slot(str, result="QVariant")
    def scriptParams(self, source: str) -> list:
        """Kembalikan skema PARAMS skrip (untuk form dinamis di UI).

        Mendukung PARAMS bertipe list skema maupun dict sederhana.
        """
        from strategies.script_runtime import compile_script, ScriptError
        try:
            ns = compile_script(source)
        except (ScriptError, Exception):  # noqa: BLE001
            return []
        params = ns.get("PARAMS")
        if isinstance(params, dict):
            out = []
            for k, v in params.items():
                ptype = "int" if isinstance(v, int) and not isinstance(v, bool) else ("float" if isinstance(v, float) else "str")
                out.append({
                    "key": str(k),
                    "label": str(k).replace("_", " ").title(),
                    "type": ptype,
                    "default": v,
                })
            return out
        if isinstance(params, list):
            return [dict(p) for p in params if isinstance(p, dict)]
        return []

    @Slot(str, result="QVariant")
    def scriptSettings(self, source: str) -> dict:
        """Ekstrak kamus pengaturan trading (SETTINGS/konstanta) dari kode skrip."""
        from strategies.script_runtime import compile_script, extract_script_settings
        try:
            ns = compile_script(source)
            return extract_script_settings(ns)
        except Exception:  # noqa: BLE001
            return {}

    @Slot(str, str, "QVariant", result=bool)
    def applyScript(self, source: str, name: str = "", params=None) -> bool:
        """Jadikan skrip sebagai strategi aktif (custom_script) + selaraskan pengaturan & config.

        `params` (opsional) berisi nilai parameter dari form UI.
        """
        from strategies.script_runtime import compile_script, extract_script_settings, ScriptError
        try:
            ns = compile_script(source)
        except ScriptError as exc:
            self.configError.emit(f"Skrip tidak valid: {exc}")
            return False

        script_cfg = extract_script_settings(ns)

        # 1. Nama skrip
        resolved_name = (name or script_cfg.get("name", "")).strip()
        settings.strategy_name = "custom_script"
        settings.script_source = source
        settings.script_name = resolved_name

        # 2. Parameter strategi
        raw_params = ns.get("PARAMS")
        merged_params = {}
        if isinstance(raw_params, dict):
            merged_params.update(raw_params)
        elif isinstance(raw_params, list):
            for spec in raw_params:
                if isinstance(spec, dict) and "key" in spec:
                    merged_params[spec["key"]] = spec.get("default")

        ui_params = _to_py_dict(params) or {}
        if isinstance(ui_params, dict):
            merged_params.update(ui_params)
        settings.strategy_params = merged_params

        # 3. Sinkronkan pengaturan trading dari skrip ke settings global bila didefinisikan
        cfg_to_settings = {
            "symbol": "symbol",
            "timeframe_str": "timeframe_str",
            "risk_per_trade": "risk_per_trade",
            "max_open_positions": "max_open_positions",
            "sl_tp_mode": "sl_tp_mode",
            "sl_points": "sl_points",
            "tp_points": "tp_points",
            "sl_percent": "sl_percent",
            "tp_percent": "tp_percent",
            "virtual_sltp_enabled": "virtual_sltp_enabled",
            "trailing_stop_enabled": "trailing_stop_enabled",
            "trailing_stop_points": "trailing_stop_points",
            "trailing_step_points": "trailing_step_points",
            "break_even_enabled": "break_even_enabled",
            "break_even_trigger_points": "break_even_trigger_points",
            "break_even_offset_points": "break_even_offset_points",
            "daily_drawdown_limit": "daily_drawdown_limit",
            "max_daily_trades": "max_daily_trades",
            "max_spread_points": "max_spread_points",
            "max_exposure_lots": "max_exposure_lots",
            "equity_stop_loss": "equity_stop_loss",
            "max_consecutive_losses": "max_consecutive_losses",
            "magic_number": "magic_number",
            "loop_interval": "loop_interval",
        }

        synced_fields = []
        for cfg_key, target_field in cfg_to_settings.items():
            if cfg_key in script_cfg and script_cfg[cfg_key] is not None:
                val = script_cfg[cfg_key]
                if target_field == "symbol" and self._engine and hasattr(self._engine.backend, "resolve_symbol"):
                    try:
                        resolved_sym = self._engine.backend.resolve_symbol(str(val))
                        if resolved_sym:
                            val = resolved_sym
                    except Exception:  # noqa: BLE001
                        pass
                setattr(settings, target_field, val)
                synced_fields.append(f"{target_field}={val}")

        config_store.save()
        self._engine.rebuild_strategy()

        # Sinkronkan chart bila skrip mendefinisikan simbol
        if "symbol" in script_cfg and script_cfg["symbol"]:
            sym = settings.symbol
            self._chart_symbol = sym
            if self._worker is not None:
                self._worker.set_chart_symbol(sym)
            self.chartSymbolChanged.emit(sym)

        msg = f"[UI] Strategi skrip '{resolved_name or 'custom_script'}' diterapkan."
        if synced_fields:
            detail = ", ".join(synced_fields[:4]) + ("..." if len(synced_fields) > 4 else "")
            msg += f" Pengaturan diselaraskan dari skrip ({len(synced_fields)} opsi: {detail})."
        self.logMessage.emit(msg)
        return True

    @Slot("QVariant", result=bool)
    def saveConfig(self, cfg) -> bool:
        # cfg dari QML berupa QJSValue/dict; normalkan ke dict Python.
        data = _to_py_dict(cfg)
        errors = config_store.apply(data)
        if errors:
            self.configError.emit("; ".join(errors))
            return False
        config_store.save()
        # Terapkan parameter strategi baru bila engine sudah ada.
        self._engine.rebuild_strategy()
        return True

    # ----- Slot statistik & log -----

    @Slot()
    def refreshStats(self) -> None:
        """Paksa refresh kalkulasi statistik dan kurva ekuitas."""
        if self._connected:
            self._stats = self._engine.poll_stats()
            self.statsChanged.emit()
            self._equity_curve = self._engine.poll_equity_curve(self._balance, self._equity)
            self.equityChanged.emit()

    # ----- Jurnal aksi skrip (Mode Programmer) -----

    @Property("QVariant", notify=journalChanged)
    def journal(self) -> list:
        return self._journal

    @Slot()
    def clearJournal(self) -> None:
        self._journal = []
        self.journalChanged.emit()

    @Slot(str, result=str)
    def exportJournal(self, target_path: str = "") -> str:
        """Ekspor jurnal aksi skrip ke CSV (Waktu, Aksi, Simbol, Detail, Status)."""
        try:
            import os
            from datetime import datetime
            path = (target_path or "").strip()
            if path.startswith("file:"):
                path = QUrl(path).toLocalFile()
            if not path:
                os.makedirs("logs", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.abspath(os.path.join("logs", f"journal_{ts}.csv"))

            def _esc(v):
                return str(v).replace('"', '""')

            with open(path, "w", encoding="utf-8") as f:
                f.write("Waktu,Aksi,Simbol,Detail,Status\n")
                for r in self._journal:
                    f.write('"%s","%s","%s","%s","%s"\n' % (
                        _esc(r.get("time", "")), _esc(r.get("action", "")),
                        _esc(r.get("symbol", "")), _esc(r.get("detail", "")),
                        "OK" if r.get("ok", True) else "GAGAL"))
            self.logMessage.emit(f"[UI] Jurnal diekspor ke: {path}")
            return path
        except Exception as exc:  # noqa: BLE001
            self.configError.emit(f"Gagal mengekspor jurnal: {exc}")
            return ""

    @Slot(str, result=str)
    def exportLogs(self, target_path: str = "") -> str:
        """Ekspor riwayat log ke file .txt atau .csv."""
        try:
            import os
            from datetime import datetime
            path = (target_path or "").strip()
            if path.startswith("file:///"):
                path = QUrl(path).toLocalFile()
            elif path.startswith("file:"):
                path = QUrl(path).toLocalFile()

            if not path:
                os.makedirs("logs", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.abspath(os.path.join("logs", f"export_log_{ts}.txt"))

            is_csv = path.lower().endswith(".csv")

            with open(path, "w", encoding="utf-8") as f:
                if is_csv:
                    f.write("Waktu,Level,Pesan\n")
                    for line in self._log_history:
                        parts = [p.strip() for p in line.split("|", 2)]
                        if len(parts) == 3:
                            time_str, level_str, msg_str = parts
                            msg_str = msg_str.replace('"', '""')
                            f.write(f'"{time_str}","{level_str}","{msg_str}"\n')
                        else:
                            clean_line = line.replace('"', '""')
                            f.write(f'"","","{clean_line}"\n')
                else:
                    for line in self._log_history:
                        f.write(line + "\n")

            msg = f"[UI] Log berhasil diekspor ke: {path}"
            self.logMessage.emit(msg)
            return path
        except Exception as exc:
            err = f"Gagal mengekspor log: {exc}"
            self.configError.emit(err)
            return ""

    # ----- Handler dari worker (dieksekusi di main thread via queued signal) -----

    @Slot(dict)
    def _on_stats(self, data: dict) -> None:
        self._stats = data
        self.statsChanged.emit()

    @Slot(list)
    def _on_equity(self, data: list) -> None:
        self._equity_curve = data
        self.equityChanged.emit()

    @Slot(dict)
    def _on_account(self, data: dict) -> None:
        self._balance = data.get("balance", 0.0)
        self._equity = data.get("equity", 0.0)
        self._margin = data.get("margin", 0.0)
        self._free_margin = data.get("free_margin", 0.0)
        self._profit = data.get("profit", 0.0)
        self._currency = data.get("currency", "")
        self._account_type = data.get("account_type", "?")
        self._account_server = data.get("server", "")
        self._server_connected = bool(data.get("server_connected", False))
        self._trade_allowed = bool(data.get("trade_allowed", False))
        self.accountChanged.emit()

    @Slot(list)
    def _on_positions(self, positions: list) -> None:
        self.positionsChanged.emit(positions)

    @Slot(list)
    def _on_orders(self, orders: list) -> None:
        self.ordersChanged.emit(orders)

    @Slot(dict)
    def _on_journal(self, entry: dict) -> None:
        from datetime import datetime
        rec = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": str(entry.get("action", "")),
            "symbol": str(entry.get("symbol", "")),
            "detail": str(entry.get("detail", "")),
            "ok": bool(entry.get("ok", True)),
        }
        self._journal.append(rec)
        if len(self._journal) > 2000:
            self._journal.pop(0)
        self.journalChanged.emit()

    @Slot(str, "QVariant")
    def _on_candles(self, symbol: str, payload) -> None:
        self.chartUpdated.emit(symbol, payload)

    @Slot(list)
    def _on_symbols(self, symbols: list) -> None:
        self.symbolsAvailable.emit(symbols)

    @Slot(str)
    def _on_worker_chart_symbol(self, symbol: str) -> None:
        if symbol:
            self._chart_symbol = symbol
            self.chartSymbolChanged.emit(symbol)

    @Slot(str)
    def _on_auto_trading_disabled(self, msg: str) -> None:
        self._set_trading(False)
        self._set_status("Terhubung (Proteksi Risiko)")
        self.configError.emit(msg)

    @Slot(bool)
    def _on_worker_connected(self, ok: bool) -> None:
        self._set_connected(ok)
        if ok:
            self._set_status("Terhubung")
            self._auto_save_profile()
        elif self._thread is not None:
            self._set_status("Gagal terhubung")

    def _auto_save_profile(self) -> None:
        """Simpan profil otomatis setelah connect sukses agar bisa dipakai lagi.

        Cabang sesuai backend: MCP menyimpan profil MCP + mcp_secret.json,
        native menyimpan profil kredensial.
        """
        if settings.backend == "mcp":
            name = self._pending_mcp_name or f"MCP_{settings.mcp_endpoint}"
            mcp_profile_store.save_profile(name)
            mcp_profile_store.save_secret_file()
            self._pending_mcp_name = None
            self.mcpProfilesChanged.emit(mcp_profile_store.list_profiles())
            return
        name = self._pending_profile_name
        if not name:
            # Nama default dari login + server bila pengguna tak memberi nama.
            name = f"{settings.login}_{settings.server}"
        credential_store.save_profile(name)
        self._pending_profile_name = None
        self.profilesChanged.emit(credential_store.list_profiles())

    @Slot()
    def _on_worker_stopped(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
            self._worker = None
        self._set_connected(False)
        self._set_trading(False)
        self._account_type = "?"
        self._account_server = ""
        self._server_connected = False
        self._trade_allowed = False
        self._balance = 0.0
        self._equity = 0.0
        self._margin = 0.0
        self._free_margin = 0.0
        self._profit = 0.0
        self._currency = ""
        self.accountChanged.emit()
        self.positionsChanged.emit([])
        self.ordersChanged.emit([])
        self._set_status("Terputus")
