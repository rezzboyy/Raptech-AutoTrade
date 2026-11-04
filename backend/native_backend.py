from __future__ import annotations

"""
Raptech Autotrade CLI — Native MetaTrader 5 Backend.
Communicates directly with desktop terminal via official MetaTrader5 Python IPC.
Enforces thread-safety by routing all MT5 API calls through a dedicated worker thread.
"""

from concurrent.futures import Future
from datetime import datetime, timezone
import queue
import threading
from typing import Any, Callable, Dict, List, Optional

from backend.base import (
    AccountInfo,
    Candle,
    OrderResult,
    Position,
    SymbolSpec,
    Tick,
    classify_account_type,
    resolve_symbol_name,
)
from core.logger import get_logger

logger = get_logger("backend.native")

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    mt5 = None  # type: ignore
    HAS_MT5 = False


class NativeBackendWorker(threading.Thread):
    """Dedicated single worker thread for all MT5 API operations to guarantee thread-safety."""

    def __init__(self) -> None:
        super().__init__(name="MT5NativeWorker", daemon=True)
        self._task_queue: queue.Queue[tuple[Callable, tuple, dict, Future]] = queue.Queue()
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                task = self._task_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            func, args, kwargs, future = task
            try:
                result = func(*args, **kwargs)
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
            finally:
                self._task_queue.task_done()

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        if not self._running:
            raise RuntimeError("MT5 worker thread is not running.")
        if threading.current_thread() is self:
            return func(*args, **kwargs)
        future: Future = Future()
        self._task_queue.put((func, args, kwargs, future))
        return future.result(timeout=15.0)

    def stop(self) -> None:
        self._running = False


class NativeBackend:
    """Native MetaTrader 5 Trading Backend."""

    def __init__(
        self,
        login: int = 0,
        password: str = "",
        server: str = "",
        path: str = "",
    ) -> None:
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self._worker: Optional[NativeBackendWorker] = None
        self._connected = False
        self._lock = threading.Lock()
        self._resolved_cache: Dict[str, str] = {}
        self._symbols_cache: Optional[List[str]] = None

    def _ensure_worker(self) -> NativeBackendWorker:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = NativeBackendWorker()
                self._worker.start()
            return self._worker

    def connect(self) -> bool:
        if not HAS_MT5:
            logger.error("Library MetaTrader5 tidak terpasang di sistem ini.")
            return False

        worker = self._ensure_worker()

        def _do_connect() -> bool:
            init_kwargs: dict[str, Any] = {"timeout": 5000}
            if self.path:
                init_kwargs["path"] = self.path
            has_credentials = bool(self.login and self.password and self.server)
            if has_credentials:
                try:
                    init_kwargs["login"] = int(str(self.login).strip())
                except (ValueError, TypeError):
                    pass
                init_kwargs["password"] = str(self.password).strip()
                init_kwargs["server"] = str(self.server).strip()

            initialized = mt5.initialize(**init_kwargs)
            if not initialized and not self.path and has_credentials:
                import os
                candidate_paths = [
                    r"C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
                    r"C:\Program Files\MetaTrader 5\terminal64.exe",
                    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe",
                ]
                for p in candidate_paths:
                    if os.path.isfile(p):
                        init_kwargs["path"] = p
                        if mt5.initialize(**init_kwargs):
                            initialized = True
                            self.path = p
                            break

            if not initialized:
                err = mt5.last_error()
                logger.error(f"mt5.initialize() gagal: {err}")
                if err and isinstance(err, (tuple, list)) and len(err) > 0 and err[0] == -6:
                    logger.warning(
                        f"Otorisasi MT5 gagal (-6: Authorization failed). Terminal MT5 belum login atau akun belum aktif. "
                        f"(Login: {self.login or 'Belum diisi/Default'}). "
                        f"Silakan periksa kredensial di menu [P] (Edit Kredensial) atau login langsung di terminal MT5."
                    )
                return False

            if self.login and self.password and self.server:
                try:
                    login_int = int(str(self.login).strip())
                except (ValueError, TypeError):
                    login_int = 0
                authorized = mt5.login(
                    login=login_int,
                    password=str(self.password).strip(),
                    server=str(self.server).strip(),
                )
                if not authorized:
                    err = mt5.last_error()
                    logger.error(f"mt5.login() gagal untuk {self.login} @ {self.server}: {err}")
                    return False

            term_info = mt5.terminal_info()
            if term_info:
                logger.info(f"Terhubung ke MT5 Terminal Build {term_info.build} ({term_info.name})")
                if not getattr(term_info, "trade_allowed", True):
                    logger.warning(
                        "⚠️ PERHATIAN: Tombol 'Algo Trading' di MetaTrader 5 sedang NONAKTIF (merah). "
                        "Silakan buka MT5 dan tekan Ctrl+E atau klik tombol 'Algo Trading' di toolbar hingga HIJAU agar bot diizinkan membuka posisi."
                    )
            return True

        try:
            self._connected = worker.execute(_do_connect)
            return self._connected
        except Exception as exc:
            logger.error(f"Eksepsi saat connect MT5: {exc}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._worker and self._worker.is_alive():
            try:
                if HAS_MT5:
                    self._worker.execute(mt5.shutdown)
            except Exception:
                pass
            self._worker.stop()
            self._worker = None
        self._connected = False
        self._symbols_cache = None
        self._resolved_cache.clear()
        logger.info("MT5 Native Backend terputus.")

    def account_info(self) -> Optional[AccountInfo]:
        if not self._connected or not HAS_MT5:
            return None
        worker = self._ensure_worker()

        def _do_get_account() -> Optional[AccountInfo]:
            info = mt5.account_info()
            if not info:
                return None
            trade_mode_val = getattr(info, "trade_mode", None)
            currency_str = str(getattr(info, "currency", "USD"))
            server_str = str(getattr(info, "server", self.server or ""))
            acc_type = classify_account_type(trade_mode_val, server_str, currency_str)
            is_cent = "CENT" in acc_type or "cent" in server_str.lower() or currency_str.upper() in ("USC", "USCC")

            term = mt5.terminal_info()
            server_conn = bool(getattr(term, "connected", True)) if term else True
            term_algo_allowed = bool(getattr(term, "trade_allowed", True)) if term else True
            acc_trade_expert = bool(getattr(info, "trade_expert", True)) if info else True
            algo_allowed = term_algo_allowed and acc_trade_expert

            return AccountInfo(
                login=int(info.login),
                server=server_str,
                currency=currency_str,
                balance=float(info.balance),
                equity=float(info.equity),
                margin=float(info.margin),
                free_margin=float(info.margin_free),
                margin_level=float(info.margin_level) if info.margin_level else 0.0,
                profit=float(info.profit),
                trade_allowed=bool(info.trade_allowed),
                server_connected=server_conn,
                account_type=acc_type,
                leverage=int(getattr(info, "leverage", 100)),
                is_cent=is_cent,
                algo_trading_allowed=algo_allowed,
            )

        try:
            return worker.execute(_do_get_account)
        except Exception as exc:
            logger.error(f"Gagal mengambil account_info: {exc}")
            return None

    def list_symbols(self, limit: int = 60) -> List[str]:
        if not self._connected or not HAS_MT5:
            return []
        if self._symbols_cache is not None:
            return self._symbols_cache[:limit]
        worker = self._ensure_worker()

        def _do_list_symbols() -> List[str]:
            symbols = mt5.symbols_get()
            if not symbols:
                return []
            return [s.name for s in symbols]

        try:
            res = worker.execute(_do_list_symbols)
            self._symbols_cache = res
            return res[:limit]
        except Exception:
            return []

    def symbol_spec(self, symbol: str) -> Optional[SymbolSpec]:
        if not self._connected or not HAS_MT5:
            return None
        worker = self._ensure_worker()

        def _do_spec() -> Optional[SymbolSpec]:
            s_info = mt5.symbol_info(symbol)
            if not s_info:
                return None
            return SymbolSpec(
                symbol=s_info.name,
                digits=int(s_info.digits),
                point=float(s_info.point),
                volume_min=float(s_info.volume_min),
                volume_max=float(s_info.volume_max),
                volume_step=float(s_info.volume_step),
                tick_value=float(s_info.trade_tick_value) if s_info.trade_tick_value else 1.0,
                tick_size=float(s_info.trade_tick_size) if s_info.trade_tick_size else float(s_info.point),
                stop_level=int(s_info.trade_stops_level),
            )

        try:
            return worker.execute(_do_spec)
        except Exception:
            return None

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        if symbol in self._resolved_cache:
            return self._resolved_cache[symbol]
        all_syms = self.list_symbols(limit=500)
        res = resolve_symbol_name(symbol, all_syms)
        if res:
            self._resolved_cache[symbol] = res
        return res

    def ensure_symbol(self, symbol: str) -> bool:
        if not self._connected or not HAS_MT5:
            return False
        worker = self._ensure_worker()

        def _do_ensure() -> bool:
            s_info = mt5.symbol_info(symbol)
            if not s_info:
                return False
            if not s_info.visible:
                return bool(mt5.symbol_select(symbol, True))
            return True

        try:
            return worker.execute(_do_ensure)
        except Exception:
            return False

    def get_tick(self, symbol: str) -> Optional[Tick]:
        if not self._connected or not HAS_MT5:
            return None
        worker = self._ensure_worker()

        def _do_tick() -> Optional[Tick]:
            t = mt5.symbol_info_tick(symbol)
            if not t:
                s_info = mt5.symbol_info(symbol)
                if s_info and not s_info.visible:
                    mt5.symbol_select(symbol, True)
                    t = mt5.symbol_info_tick(symbol)
            if not t:
                return None
            return Tick(
                bid=float(t.bid),
                ask=float(t.ask),
                time=datetime.fromtimestamp(t.time, tz=timezone.utc),
                last=float(t.last) if hasattr(t, "last") else 0.0,
                volume=int(t.volume) if hasattr(t, "volume") else 0,
            )

        try:
            return worker.execute(_do_tick)
        except Exception:
            return None

    def spread_points(self, symbol: str) -> Optional[float]:
        tick = self.get_tick(symbol)
        spec = self.symbol_spec(symbol)
        if tick and spec and spec.point > 0:
            return round((tick.ask - tick.bid) / spec.point, 1)
        return None

    def get_candles(self, symbol: str, timeframe_str: str, count: int = 200) -> List[Candle]:
        if not self._connected or not HAS_MT5:
            return []
        worker = self._ensure_worker()

        # MT5 Timeframe Constants
        tf_map = {
            "M1": mt5.TIMEFRAME_M1 if HAS_MT5 else 1,
            "M5": mt5.TIMEFRAME_M5 if HAS_MT5 else 5,
            "M15": mt5.TIMEFRAME_M15 if HAS_MT5 else 15,
            "M30": mt5.TIMEFRAME_M30 if HAS_MT5 else 30,
            "H1": mt5.TIMEFRAME_H1 if HAS_MT5 else 60,
            "H4": mt5.TIMEFRAME_H4 if HAS_MT5 else 240,
            "D1": mt5.TIMEFRAME_D1 if HAS_MT5 else 1440,
        }
        mt5_tf = tf_map.get(timeframe_str.upper(), mt5.TIMEFRAME_M5 if HAS_MT5 else 5)

        def _do_rates() -> List[Candle]:
            s_info = mt5.symbol_info(symbol)
            if s_info and not s_info.visible:
                mt5.symbol_select(symbol, True)
            rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
            if rates is None or len(rates) == 0:
                return []
            result = []
            for r in rates:
                result.append(
                    Candle(
                        time=datetime.fromtimestamp(int(r["time"]), tz=timezone.utc),
                        open=float(r["open"]),
                        high=float(r["high"]),
                        low=float(r["low"]),
                        close=float(r["close"]),
                        tick_volume=int(r["tick_volume"]),
                    )
                )
            return result

        try:
            return worker.execute(_do_rates)
        except Exception as exc:
            logger.error(f"Gagal mengambil rates {symbol} ({timeframe_str}): {exc}")
            return []

    def positions(self, symbol: Optional[str] = None) -> List[Position]:
        if not self._connected or not HAS_MT5:
            return []
        worker = self._ensure_worker()

        def _do_positions() -> List[Position]:
            kwargs = {}
            if symbol:
                kwargs["symbol"] = symbol
            raw_pos = mt5.positions_get(**kwargs)
            if raw_pos is None:
                return []
            res = []
            for p in raw_pos:
                side_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                open_time = datetime.fromtimestamp(p.time, tz=timezone.utc) if p.time else None
                res.append(
                    Position(
                        ticket=int(p.ticket),
                        symbol=p.symbol,
                        type=side_str,
                        volume=float(p.volume),
                        price_open=float(p.price_open),
                        price_current=float(p.price_current),
                        sl=float(p.sl),
                        tp=float(p.tp),
                        profit=float(p.profit),
                        magic=int(p.magic),
                        comment=str(p.comment or ""),
                        time=open_time,
                    )
                )
            return res

        try:
            return worker.execute(_do_positions)
        except Exception:
            return []

    def _get_filling_type(self, symbol: str) -> int:
        if not HAS_MT5:
            return 1
        s_info = mt5.symbol_info(symbol)
        if s_info:
            f_mode = getattr(s_info, "filling_mode", 0)
            if f_mode & 2:
                return mt5.ORDER_FILLING_IOC
            elif f_mode & 1:
                return mt5.ORDER_FILLING_FOK
            elif f_mode == 0:
                return mt5.ORDER_FILLING_RETURN
        return mt5.ORDER_FILLING_IOC

    def send_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "raptech_cli",
    ) -> OrderResult:
        if not self._connected or not HAS_MT5:
            return OrderResult(ok=False, message="Backend tidak terhubung ke MT5")
        worker = self._ensure_worker()

        def _do_send() -> OrderResult:
            self.ensure_symbol(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return OrderResult(ok=False, message=f"Gagal mendapatkan tick untuk {symbol}")

            is_buy = side.upper() == "BUY"
            order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            price = tick.ask if is_buy else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(volume),
                "type": order_type,
                "price": float(price),
                "sl": float(sl),
                "tp": float(tp),
                "deviation": 20,
                "magic": int(magic),
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_type(symbol),
            }

            result = mt5.order_send(request)
            if result is None:
                err = mt5.last_error()
                return OrderResult(ok=False, message=f"order_send mengembalikan None: {err}")

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                err_detail = f"retcode={result.retcode} ({result.comment})"
                if result.retcode == 10027 or "client" in str(result.comment).lower():
                    err_detail = (
                        "retcode=10027 (AutoTrading di MT5 dinonaktifkan). "
                        "Solusi: Buka MetaTrader 5 lalu klik tombol 'Algo Trading' di toolbar atas hingga HIJAU (atau tekan Ctrl+E di MT5)"
                    )
                return OrderResult(
                    ok=False,
                    retcode=result.retcode,
                    message=f"Order ditolak: {err_detail}",
                )

            return OrderResult(
                ok=True,
                ticket=int(result.order),
                order=int(result.order),
                price=float(result.price),
                volume=float(result.volume),
                message="Order sukses",
            )

        try:
            return worker.execute(_do_send)
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi order_send: {exc}")

    def close_position(self, ticket: int, symbol: str, volume: Optional[float] = None) -> OrderResult:
        if not self._connected or not HAS_MT5:
            return OrderResult(ok=False, message="Backend tidak terhubung ke MT5")
        worker = self._ensure_worker()

        def _do_close() -> OrderResult:
            pos_list = mt5.positions_get(ticket=ticket)
            if not pos_list:
                return OrderResult(ok=False, message=f"Posisi #{ticket} tidak ditemukan")
            pos = pos_list[0]
            close_vol = float(volume if volume is not None else pos.volume)

            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return OrderResult(ok=False, message=f"Gagal mendapatkan tick {symbol}")

            is_buy = pos.type == mt5.ORDER_TYPE_BUY
            close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
            price = tick.bid if is_buy else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_vol,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": pos.magic,
                "comment": f"close #{ticket}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_type(symbol),
            }

            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                err_msg = result.comment if result else str(mt5.last_error())
                return OrderResult(ok=False, message=f"Tutup posisi gagal: {err_msg}")

            return OrderResult(ok=True, ticket=ticket, price=price, volume=close_vol, message="Posisi ditutup")

        try:
            return worker.execute(_do_close)
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi close_position: {exc}")

    def modify_sl_tp(
        self, ticket: int, symbol: str, sl: Optional[float] = None, tp: Optional[float] = None
    ) -> bool:
        if not self._connected or not HAS_MT5:
            return False
        worker = self._ensure_worker()

        def _do_modify() -> bool:
            pos_list = mt5.positions_get(ticket=ticket)
            if not pos_list:
                return False
            pos = pos_list[0]
            new_sl = float(sl if sl is not None else pos.sl)
            new_tp = float(tp if tp is not None else pos.tp)

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": ticket,
                "sl": new_sl,
                "tp": new_tp,
            }
            res = mt5.order_send(request)
            return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE

        try:
            return worker.execute(_do_modify)
        except Exception:
            return False

    def send_pending_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        sl: float = 0.0,
        tp: float = 0.0,
        magic: int = 0,
        comment: str = "raptech_cli",
    ) -> OrderResult:
        if not self._connected or not HAS_MT5:
            return OrderResult(ok=False, message="Backend tidak terhubung ke MT5")
        worker = self._ensure_worker()

        type_map = {
            "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT if HAS_MT5 else 2,
            "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT if HAS_MT5 else 3,
            "buy_stop": mt5.ORDER_TYPE_BUY_STOP if HAS_MT5 else 4,
            "sell_stop": mt5.ORDER_TYPE_SELL_STOP if HAS_MT5 else 5,
        }
        mt5_order_type = type_map.get(order_type.lower())
        if mt5_order_type is None:
            return OrderResult(ok=False, message=f"Tipe pending order tidak didukung: {order_type}")

        def _do_pending() -> OrderResult:
            self.ensure_symbol(symbol)
            request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": float(volume),
                "type": mt5_order_type,
                "price": float(price),
                "sl": float(sl),
                "tp": float(tp),
                "deviation": 20,
                "magic": int(magic),
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_type(symbol),
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                comment_msg = result.comment if result else str(mt5.last_error())
                return OrderResult(ok=False, message=f"Pending order gagal: {comment_msg}")
            return OrderResult(ok=True, order=int(result.order), price=price, volume=volume, message="Pending order berhasil")

        try:
            return worker.execute(_do_pending)
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi send_pending_order: {exc}")

    def delete_pending_order(self, ticket: int) -> OrderResult:
        if not self._connected or not HAS_MT5:
            return OrderResult(ok=False, message="Backend tidak terhubung ke MT5")
        worker = self._ensure_worker()

        def _do_delete() -> OrderResult:
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                comment_msg = result.comment if result else str(mt5.last_error())
                return OrderResult(ok=False, message=f"Hapus pending order gagal: {comment_msg}")
            return OrderResult(ok=True, order=ticket, message="Pending order dihapus")

        try:
            return worker.execute(_do_delete)
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi delete_pending_order: {exc}")
