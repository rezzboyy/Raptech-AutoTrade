"""Backend trading berbasis server MCP MetaTrader 5.

Tahap 1: koneksi + info akun. Operasi data pasar, posisi, histori, dan trading
ditambahkan pada tahap berikutnya (lihat tasks.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.logger import get_logger
from src.mcp_client import (
    McpClient,
    McpError,
    mask_token,
)

logger = get_logger("mt5bot")


def _parse_mt5_time(value):
    """Parse waktu MT5 'YYYY.MM.DD HH:MM:SS' (atau ISO) menjadi datetime.

    Kembalikan datetime; fallback ke epoch 0 bila gagal.
    """
    from datetime import datetime as _dt
    if value is None:
        return _dt.utcfromtimestamp(0)
    if isinstance(value, (int, float)):
        return _dt.utcfromtimestamp(float(value))
    s = str(value).strip()
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return _dt.fromisoformat(s)
    except ValueError:
        return _dt.utcfromtimestamp(0)


def _to_iso(dt) -> str:
    """Ubah datetime menjadi string ISO 8601."""
    try:
        return dt.isoformat()
    except AttributeError:
        return str(dt)


def _num(d: dict, *keys, default=0.0):
    """Ambil nilai numerik pertama yang ada dari beberapa kemungkinan nama kunci."""
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return default


def _side_to_mcp(side: str) -> Optional[str]:
    """Petakan arah sinyal ke nilai `type` MCP: 'buy' / 'sell'. None bila tak valid."""
    s = str(side).strip().upper()
    if s in ("BUY", "0", "ORDER_TYPE_BUY"):
        return "buy"
    if s in ("SELL", "1", "ORDER_TYPE_SELL"):
        return "sell"
    return None


def _clamp_comment(comment: str, limit: int = 31) -> str:
    """Batasi komentar order maksimum `limit` karakter (skema MCP: 31)."""
    return str(comment or "")[:limit]


def _parse_order_result(res: dict) -> dict:
    """Normalkan hasil tool trading menjadi {ok, ticket, message}."""
    if not isinstance(res, dict):
        return {"ok": False, "ticket": None, "message": str(res)}
    # Deteksi sukses dari beberapa kemungkinan bentuk respons.
    retcode = res.get("retcode", res.get("return_code"))
    ok = bool(res.get("success", res.get("ok", False)))
    if not ok and retcode is not None:
        # 10009 = TRADE_RETCODE_DONE di MT5.
        ok = int(retcode) in (10009, 0) if str(retcode).lstrip("-").isdigit() else False
    ticket = (res.get("ticket") or res.get("order") or res.get("position_ticket")
              or res.get("position_id") or res.get("order_id") or res.get("deal"))
    message = (
        res.get("message")
        or res.get("retcode_details")
        or res.get("comment")
        or res.get("description")
        or res.get("error")
        or ""
    )
    if not ok and retcode is not None:
        if not message:
            message = f"retcode {retcode}"
        elif str(retcode) not in str(message):
            message = f"[{retcode}] {message}"
    # Bila tidak ada indikator eksplisit tapi ada ticket, anggap sukses.
    if not ok and ticket:
        ok = True
    try:
        ticket = int(ticket) if ticket is not None else None
    except (TypeError, ValueError):
        ticket = None
    return {"ok": ok, "ticket": ticket, "message": str(message)}



def _history_to_df(history: list, count: int):
    """Ubah daftar candle MCP menjadi DataFrame (index waktu, kolom OHLC + volume)."""
    import pandas as pd
    if not history:
        return pd.DataFrame()
    rows = []
    for h in history[-count:]:
        rows.append({
            "time": _parse_mt5_time(h.get("time")),
            "open": float(h.get("open", 0.0)),
            "high": float(h.get("high", 0.0)),
            "low": float(h.get("low", 0.0)),
            "close": float(h.get("close", 0.0)),
            "tick_volume": int(h.get("tick_volume", 0)),
            "spread": int(h.get("spread", 0)),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df.set_index("time", inplace=True)
    return df


def _normalize_position(p: dict) -> dict:
    """Normalkan satu posisi terbuka MCP ke dict Position (defensif atas nama kunci)."""
    type_raw = p.get("type", p.get("position_type", p.get("action", "")))
    side = str(type_raw).upper()
    if side in ("0", "BUY", "POSITION_TYPE_BUY"):
        side = "BUY"
    elif side in ("1", "SELL", "POSITION_TYPE_SELL"):
        side = "SELL"
    return {
        "ticket": int(_num(p, "ticket", "position", "position_ticket", "position_id")),
        "symbol": p.get("symbol", ""),
        "type": side,
        "volume": _num(p, "volume", "volume_current"),
        "price_open": _num(p, "price_open", "open_price", "price"),
        "price_current": _num(p, "price_current", "current_price", "price_last"),
        "sl": _num(p, "sl", "stop_loss"),
        "tp": _num(p, "tp", "take_profit"),
        "profit": _num(p, "profit"),
        "magic": int(_num(p, "magic", "magic_number")),
    }


def _normalize_order(o: dict) -> dict:
    """Normalkan satu pending order MCP ke dict Order."""
    otype = str(o.get("type", o.get("order_type", o.get("action", "")))).lower()
    return {
        "ticket": int(_num(o, "ticket", "order", "order_ticket", "order_id")),
        "symbol": o.get("symbol", ""),
        "type": otype,
        "volume": _num(o, "volume", "volume_current", "volume_initial"),
        "price": _num(o, "price_open", "price", "price_order"),
        "sl": _num(o, "sl", "stop_loss"),
        "tp": _num(o, "tp", "take_profit"),
        "magic": int(_num(o, "magic", "magic_number")),
    }


def _normalize_deal(d: dict) -> dict:
    """Normalkan satu posisi tertutup (histori) ke dict Deal untuk statistik."""
    profit = _num(d, "profit")
    comm = _num(d, "commission")
    swap = _num(d, "swap")
    fee = _num(d, "fee")
    return {
        "ticket": int(_num(d, "ticket", "position", "position_id")),
        "time": int(_num(d, "time_close", "time", "close_time")),
        "symbol": d.get("symbol", ""),
        "magic": int(_num(d, "magic", "magic_number")),
        "net_profit": profit + comm + swap + fee,
        "profit": profit,
    }


def _friendly_trade_error(raw_msg: str) -> str:
    """Ubah pesan error teknis MT5 menjadi pesan yang jelas dan dapat ditindaklanjuti."""
    text = str(raw_msg or "").strip()
    lower = text.lower()
    if "trading is not permitted" in lower:
        return (
            "Trading tidak diizinkan oleh terminal MT5 ('trading is not permitted'). "
            "Pastikan tombol 'Algo Trading' di toolbar MT5 sudah aktif (ikon hijau / shortcut Ctrl+E) "
            "dan akun tidak berstatus investor/read-only."
        )
    if "invalid stops" in lower or "10016" in text:
        return (
            "Jarak SL/TP terlalu dekat dengan harga pasar / melanggar batas stops-level broker "
            f"(Error #10016: {text}). Gunakan jarak SL/TP yang lebih lebar sesuai skala aset."
        )
    if "market closed" in lower or "10018" in text:
        return (
            "Pasar sedang tutup di broker (Error #10018: Market closed). "
            "Pasar Forex tutup di akhir pekan. Gunakan aset Crypto (BTCUSDm) untuk trading 24/7."
        )
    return text



class McpBackend:
    """Implementasi TradingBackend memakai McpClient.

    Catatan: mengimplementasikan protokol `TradingBackend` (lihat backends/base.py).
    Metode tahap lanjut untuk sementara melempar NotImplementedError.
    """

    def __init__(self, endpoint: str, api_key: str, timeout: float = 15.0):
        self._client = McpClient(endpoint, api_key, timeout=timeout)
        self.connected = False
        self._trade_allowed = False
        self._experts_trade_allowed = True
        self._server_connected = False
        self._symbol_cache: dict = {}

    # ----- Siklus koneksi -----

    def connect(self) -> bool:
        """Inisialisasi MCP lalu baca info akun untuk verifikasi kesiapan."""
        try:
            self._client.initialize()
        except McpError as exc:
            logger.error("Gagal inisialisasi MCP: %s", exc)
            return False

        account = self.account_info()
        if account is None:
            logger.error("MCP terhubung tapi info akun tidak terbaca.")
            return False

        self._trade_allowed = bool(account.get("trade_allowed"))
        self._server_connected = bool(account.get("server_connected"))

        logger.info(
            "Terhubung via MCP. Akun=%s | Balance=%.2f %s | trade_allowed=%s (algo_trading=%s) | server_connected=%s",
            account.get("login", "?"), account.get("balance", 0.0),
            account.get("currency", ""), self._trade_allowed,
            getattr(self, "_experts_trade_allowed", True), self._server_connected,
        )
        if not getattr(self, "_experts_trade_allowed", True):
            logger.warning(
                "[PERINGATAN] Algo Trading NONAKTIF di terminal MT5 (experts_trade_allowed=false). "
                "Order tidak dapat dieksekusi. Cara memperbaiki:\n"
                "  1. Di toolbar MT5 pastikan tombol 'Algo Trading' HIJAU (atau tekan Ctrl+E).\n"
                "  2. Jika sudah hijau tapi masih gagal (umum di RDP/VPS): "
                "disconnect bot → di MT5 klik Algo Trading OFF lalu ON lagi → connect ulang.\n"
                "  3. Di RDP: pastikan sesi tidak ter-lock / sleep, atau aktifkan "
                "'Allow algorithmic trading' di MT5 Tools → Options → Expert Advisors."
            )
        elif not self._trade_allowed:
            logger.warning(
                "MCP melaporkan trade TIDAK diizinkan (mcp_trade_allowed=false). "
                "Order tidak akan bisa dieksekusi sampai diaktifkan di MT5."
            )
        if not self._server_connected:
            logger.warning(
                "Terminal MT5 belum tersambung ke broker (server_connected=false). "
                "Harga & monitoring mungkin kosong; pastikan indikator koneksi (kbps) aktif."
            )

        self.connected = True
        return True

    def disconnect(self) -> None:
        self._client.close()
        self.connected = False

    # ----- Info akun -----

    def account_info(self) -> Optional[dict]:
        """Ambil info akun via get_trading_account_info dan normalkan."""
        try:
            data = self._client.call_tool("get_trading_account_info")
        except McpError as exc:
            logger.error("get_trading_account_info gagal: %s", exc)
            return None

        acc = data.get("account", {}) if isinstance(data, dict) else {}
        term = data.get("terminal", {}) if isinstance(data, dict) else {}
        if not acc:
            return None

        mcp_trade = bool(term.get("mcp_trade_allowed", False))
        experts_trade = bool(term.get("experts_trade_allowed", True)) if "experts_trade_allowed" in term else True
        trade_allowed = mcp_trade and experts_trade
        server_connected = bool(term.get("server_connected", False))

        self._trade_allowed = trade_allowed
        self._experts_trade_allowed = experts_trade
        self._server_connected = server_connected

        from src.backends.base import classify_account_type
        server = acc.get("server", "") or ""
        return {
            "login": acc.get("login", 0),
            "balance": round(float(acc.get("balance", 0.0)), 2),
            "equity": round(float(acc.get("equity", 0.0)), 2),
            "margin": round(float(acc.get("margin", 0.0)), 2),
            "free_margin": round(float(acc.get("margin_free", 0.0)), 2),
            "profit": round(float(acc.get("profit", 0.0)), 2),
            "currency": acc.get("currency", "") or "",
            "server": server,
            "account_type": classify_account_type(acc.get("type", ""), server),
            "trade_allowed": trade_allowed,
            "server_connected": server_connected,
        }

    # ----- Tahap 2: data pasar, posisi, histori -----

    def list_symbols(self, limit: int = 60) -> list:
        """Daftar nama simbol di Market Watch."""
        self._refresh_symbol_cache()
        names = list(self._symbol_cache.keys())
        return names[:limit] if limit else names

    def symbol_spec(self, symbol: str) -> Optional[dict]:
        """Spesifikasi simbol (digits, point, volume_*, tick_*, stop_level)."""
        symbol = (symbol or "").strip()
        if not symbol:
            return None
        if symbol not in self._symbol_cache:
            self._refresh_symbol_cache()
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]
        # Coba resolve bila nama berbeda suffix (mis. akun Exness)
        resolved = self.resolve_symbol(symbol)
        if resolved and resolved in self._symbol_cache:
            return self._symbol_cache[resolved]
        return None

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Cari nama simbol yang valid di broker, menyesuaikan suffix akun Exness (m/c/pro/raw)."""
        from src.backends.base import candidate_symbol_variations, resolve_symbol_name

        symbol = (symbol or "").strip()
        if not symbol:
            return None
        self._refresh_symbol_cache()
        # 1. Cek dari daftar simbol MarketWatch yang sudah ada
        resolved = resolve_symbol_name(symbol, list(self._symbol_cache.keys()))
        if resolved:
            return resolved
        # 2. Jika belum ada di cache, coba tambahkan variasi kandidat ke MarketWatch via MCP tool
        candidates = candidate_symbol_variations(symbol)
        for cand in candidates:
            try:
                self._client.call_tool("add_marketwatch_symbol", {"symbol": cand})
                self._refresh_symbol_cache(force=True)
                if cand in self._symbol_cache:
                    logger.info("Simbol '%s' berhasil ditemukan dan diaktifkan di Market Watch.", cand)
                    return cand
            except Exception:
                continue
        return None

    def ensure_symbol(self, symbol: str) -> bool:
        """Pastikan simbol aktif di Market Watch; tambahkan & adaptasi bila belum ada."""
        symbol = (symbol or "").strip()
        if not symbol:
            return False
        if symbol in self._symbol_cache:
            return True
        # Coba add langsung
        try:
            self._client.call_tool("add_marketwatch_symbol", {"symbol": symbol})
            self._refresh_symbol_cache(force=True)
            if symbol in self._symbol_cache:
                return True
        except McpError as exc:
            logger.debug("Gagal menambah simbol %s langsung: %s", symbol, exc)

        # Jika gagal langsung, coba resolve variasi simbol (suffix Exness dsb)
        resolved = self.resolve_symbol(symbol)
        if resolved and resolved in self._symbol_cache:
            return True

        logger.error("Simbol %s tidak ditemukan di broker/Market Watch.", symbol)
        return False

    def get_rates(self, symbol: str, timeframe_str: str, count: int = 200):
        """Ambil candle historis sebagai DataFrame (kolom OHLC + tick_volume, index waktu).

        Kompatibel dengan strategi yang memakai kolom 'close' dan index waktu.
        """
        import pandas as pd
        from src.backends.base import candle_time_range, map_timeframe_to_period

        period = map_timeframe_to_period(timeframe_str)
        dt_from, dt_to = candle_time_range(timeframe_str, count)
        try:
            res = self._client.call_tool("get_chart_history", {
                "symbol": symbol, "period": period,
                "datetime_from": dt_from, "datetime_to": dt_to, "limit": count,
            })
        except McpError as exc:
            logger.warning("get_chart_history gagal untuk %s: %s", symbol, exc)
            return pd.DataFrame()

        history = res.get("history", []) if isinstance(res, dict) else []
        return _history_to_df(history, count)

    def get_candles(self, symbol: str, timeframe_str: str, count: int = 150) -> list:
        """Candle untuk chart dalam bentuk {t,o,h,l,c} (t = epoch detik)."""
        df = self.get_rates(symbol, timeframe_str, count)
        if df is None or df.empty:
            return []
        out = []
        for ts, row in df.iterrows():
            epoch = int(ts.timestamp()) if hasattr(ts, "timestamp") else 0
            out.append({
                "t": epoch,
                "o": round(float(row["open"]), 5),
                "h": round(float(row["high"]), 5),
                "l": round(float(row["low"]), 5),
                "c": round(float(row["close"]), 5),
            })
        return out

    def get_tick(self, symbol: str) -> Optional[dict]:
        """Perkiraan harga terkini dari candle M1 terakhir dengan estimasi spread."""
        df = self.get_rates(symbol, "M1", count=1)
        if df is None or df.empty:
            return None
        last = df.iloc[-1]
        close = float(last["close"])
        ts = df.index[-1]
        epoch = int(ts.timestamp()) if hasattr(ts, "timestamp") else 0

        sp_pts = float(last.get("spread", 0.0) or 0.0)
        spec = self.symbol_spec(symbol) or {}
        point = float(spec.get("point", 0.0) or 0.0)
        digits = int(spec.get("digits", 5) or 5)

        if sp_pts > 0 and point > 0:
            bid = round(close, digits)
            ask = round(close + sp_pts * point, digits)
        else:
            bid = close
            ask = close

        return {"bid": bid, "ask": ask, "spread": sp_pts, "time": epoch}

    def spread_points(self, symbol: str) -> Optional[float]:
        """Spread terkini (points) dari candle M1 terakhir (field 'spread')."""
        from src.backends.base import candle_time_range, map_timeframe_to_period
        dt_from, dt_to = candle_time_range("M1", 2)
        try:
            res = self._client.call_tool("get_chart_history", {
                "symbol": symbol, "period": "M1",
                "datetime_from": dt_from, "datetime_to": dt_to, "limit": 2,
            })
        except McpError:
            return None
        hist = res.get("history", []) if isinstance(res, dict) else []
        if not hist:
            return None
        return float(hist[-1].get("spread", 0))

    def positions(self, symbol: Optional[str] = None) -> list:
        """Daftar posisi terbuka (ternormalisasi ke dict Position)."""
        try:
            res = self._client.call_tool("get_trading_open_positions")
        except McpError as exc:
            logger.error("get_trading_open_positions gagal: %s", exc)
            return []
        raw = res.get("positions", []) if isinstance(res, dict) else []
        out = [_normalize_position(p) for p in raw]
        if symbol:
            out = [p for p in out if p.get("symbol") == symbol]
        return out

    def history_deals(self, dt_from: datetime, dt_to: datetime) -> list:
        """Riwayat posisi tertutup (ternormalisasi ke dict Deal) untuk statistik."""
        try:
            res = self._client.call_tool("get_trading_history_positions", {
                "datetime_from": _to_iso(dt_from), "datetime_to": _to_iso(dt_to),
            })
        except McpError as exc:
            logger.error("get_trading_history_positions gagal: %s", exc)
            return []
        raw = res.get("positions", []) if isinstance(res, dict) else []
        return [_normalize_deal(d) for d in raw]

    def _refresh_symbol_cache(self, force: bool = False) -> None:
        if self._symbol_cache and not force:
            return
        try:
            res = self._client.call_tool("get_marketwatch_symbols")
        except McpError as exc:
            logger.error("get_marketwatch_symbols gagal: %s", exc)
            return
        cache = {}
        for s in (res.get("symbols", []) if isinstance(res, dict) else []):
            name = s.get("symbol")
            if not name:
                continue
            cache[name] = {
                "symbol": name,
                "digits": int(s.get("digits", 5)),
                "point": float(s.get("point", 0.0) or 0.0),
                "volume_min": float(s.get("volume_min", 0.01) or 0.01),
                "volume_max": float(s.get("volume_max", 0.0) or 0.0),
                "volume_step": float(s.get("volume_step", 0.01) or 0.01),
                "tick_value": float(s.get("tick_value", 0.0) or 0.0),
                "tick_size": float(s.get("tick_size", 0.0) or 0.0),
                "stop_level": int(s.get("trade_stops_level", 0) or 0),
                "freeze_level": int(s.get("trade_freeze_level", 0) or 0),
                "contract_size": float(s.get("trade_contract_size", 0.0) or 0.0),
            }
        if cache:
            self._symbol_cache = cache

    # ----- Tahap 3: trading -----

    def _trading_blocked_reason(self) -> Optional[str]:
        """Kembalikan alasan bila trading tidak boleh (fail-safe), atau None."""
        if not getattr(self, "_experts_trade_allowed", True):
            return (
                "Algo Trading nonaktif di MT5 (experts_trade_allowed=false). "
                "Solusi cepat: tekan Ctrl+E di MT5 untuk toggle Algo Trading. "
                "Solusi RDP/VPS: klik Algo Trading OFF → ON lagi di toolbar MT5, "
                "lalu Disconnect & Connect ulang di bot. "
                "Atau: MT5 Tools → Options → Expert Advisors → centang 'Allow algorithmic trading'."
            )
        if not self._trade_allowed:
            return "MCP tidak mengizinkan trading (mcp_trade_allowed=false)."
        if not self._server_connected:
            return "Terminal MT5 belum tersambung ke broker (server_connected=false)."
        return None

    def send_market_order(self, symbol: str, side: str, volume: float,
                          sl: float = 0.0, tp: float = 0.0, magic: int = 0,
                          comment: str = "mt5bot") -> dict:
        """Kirim market order via MCP. Fail-safe: tolak bila trading tidak diizinkan."""
        blocked = self._trading_blocked_reason()
        if blocked:
            logger.warning("Order %s %s dibatalkan: %s", side, symbol, blocked)
            return {"ok": False, "ticket": None, "message": blocked}

        side_norm = _side_to_mcp(side)
        if side_norm is None:
            msg = f"Arah order tidak valid: {side!r}"
            logger.error(msg)
            return {"ok": False, "ticket": None, "message": msg}

        args = {
            "symbol": symbol,
            "type": side_norm,
            "volume": float(volume),
            "comment": _clamp_comment(comment),
        }
        if sl and sl > 0:
            args["sl"] = float(sl)
        if tp and tp > 0:
            args["tp"] = float(tp)

        try:
            res = self._client.call_tool("trade_send_market_order", args)
        except McpError as exc:
            msg = _friendly_trade_error(str(exc))
            logger.error("trade_send_market_order gagal: %s", msg)
            return {"ok": False, "ticket": None, "message": msg}

        result = _parse_order_result(res)
        if result["ok"]:
            logger.info("Order %s %.2f %s terkirim (ticket=%s).",
                        side_norm, float(volume), symbol, result["ticket"])
        else:
            result["message"] = _friendly_trade_error(result.get("message", ""))
            logger.error("Order %s %s gagal: %s", side_norm, symbol, result["message"])
        return result

    def close_position(self, ticket: int, symbol: str) -> dict:
        """Tutup satu posisi via MCP."""
        if not ticket or int(ticket) <= 0:
            msg = f"Nomor tiket posisi tidak valid ({ticket})."
            logger.warning(msg)
            return {"ok": False, "ticket": ticket, "message": msg}
        blocked = self._trading_blocked_reason()
        if blocked:
            logger.warning("Tutup posisi %s dibatalkan: %s", ticket, blocked)
            return {"ok": False, "ticket": ticket, "message": blocked}
        try:
            res = self._client.call_tool("trade_close_single_position", {
                "symbol": symbol, "position_ticket": int(ticket),
            })
        except McpError as exc:
            msg = _friendly_trade_error(str(exc))
            logger.error("trade_close_single_position gagal: %s", msg)
            return {"ok": False, "ticket": ticket, "message": msg}
        result = _parse_order_result(res)
        result["ticket"] = ticket
        if result["ok"]:
            logger.info("Posisi %s (%s) ditutup.", ticket, symbol)
        else:
            result["message"] = _friendly_trade_error(result.get("message", ""))
            logger.error("Gagal menutup posisi %s: %s", ticket, result["message"])
        return result

    def modify_sl_tp(self, ticket: int, symbol: str,
                     sl: Optional[float] = None, tp: Optional[float] = None) -> bool:
        """Ubah SL/TP posisi via MCP. Hanya kirim nilai yang berubah."""
        if self._trading_blocked_reason():
            return False
        args = {"symbol": symbol, "position_ticket": int(ticket)}
        if sl is not None:
            args["sl"] = float(sl)
        if tp is not None:
            args["tp"] = float(tp)
        try:
            res = self._client.call_tool("trade_modify_sl_tp", args)
        except McpError as exc:
            msg = _friendly_trade_error(str(exc))
            logger.error("trade_modify_sl_tp gagal untuk posisi %s: %s", ticket, msg)
            return False
        result = _parse_order_result(res)
        ok = result["ok"]
        if ok:
            logger.info("SL/TP posisi %s dimodifikasi (sl=%s, tp=%s).", ticket, sl, tp)
        else:
            logger.error("Gagal memodifikasi SL/TP posisi %s: %s", ticket, _friendly_trade_error(result.get("message", "")))
        return ok

    def send_pending_order(self, symbol: str, order_type: str, volume: float,
                           price: float, sl: float = 0.0, tp: float = 0.0,
                           magic: int = 0, comment: str = "mt5bot") -> dict:
        """Pasang pending order (buy_limit/sell_limit/buy_stop/sell_stop) via MCP."""
        blocked = self._trading_blocked_reason()
        if blocked:
            logger.warning("Pending order %s %s dibatalkan: %s", order_type, symbol, blocked)
            return {"ok": False, "ticket": None, "message": blocked}

        from src.backends.base import PENDING_ORDER_TYPES
        ot = str(order_type).strip().lower()
        if ot not in PENDING_ORDER_TYPES:
            return {"ok": False, "ticket": None, "message": f"Tipe pending tidak valid: {order_type!r}"}
        if not price or price <= 0:
            return {"ok": False, "ticket": None, "message": "Harga pending order harus > 0."}

        args = {"symbol": symbol, "type": ot, "volume": float(volume),
                "price": float(price), "comment": _clamp_comment(comment)}
        if sl and sl > 0:
            args["sl"] = float(sl)
        if tp and tp > 0:
            args["tp"] = float(tp)
        try:
            res = self._client.call_tool("trade_send_pending_order", args)
        except McpError as exc:
            msg = _friendly_trade_error(str(exc))
            logger.error("trade_send_pending_order gagal: %s", msg)
            return {"ok": False, "ticket": None, "message": msg}
        result = _parse_order_result(res)
        if result["ok"]:
            logger.info("Pending %s %.2f %s @ %.5f terpasang (ticket=%s).",
                        ot, float(volume), symbol, float(price), result["ticket"])
        else:
            result["message"] = _friendly_trade_error(result.get("message", ""))
            logger.error("Pending order %s %s gagal: %s", ot, symbol, result["message"])
        return result

    def modify_pending_order(self, ticket: int, price: float,
                             sl: Optional[float] = None, tp: Optional[float] = None) -> dict:
        """Ubah harga pending order via MCP (aman dengan cancel + replace bila didukung)."""
        blocked = self._trading_blocked_reason()
        if blocked:
            return {"ok": False, "ticket": ticket, "message": blocked}
        target = None
        for o in self.pending_orders():
            if int(o.get("ticket", 0)) == int(ticket):
                target = o
                break
        if target is None:
            return {"ok": False, "ticket": ticket, "message": "Pending order tidak ditemukan."}
        del_res = self.delete_pending_order(int(ticket))
        if not del_res.get("ok"):
            return {"ok": False, "ticket": ticket, "message": del_res.get("message", "Gagal menghapus pending order lama.")}
        new_sl = float(sl) if sl is not None else float(target.get("sl", 0.0) or 0.0)
        new_tp = float(tp) if tp is not None else float(target.get("tp", 0.0) or 0.0)
        return self.send_pending_order(
            target["symbol"],
            target["type"],
            float(target["volume"]),
            float(price),
            sl=new_sl,
            tp=new_tp,
            magic=int(target.get("magic", 0) or 0),
        )

    def delete_pending_order(self, ticket: int) -> dict:
        """Hapus satu pending order via MCP."""
        if self._trading_blocked_reason():
            return {"ok": False, "ticket": ticket, "message": self._trading_blocked_reason()}
        try:
            res = self._client.call_tool("trade_delete_order", {"order_ticket": int(ticket)})
        except McpError as exc:
            msg = _friendly_trade_error(str(exc))
            logger.error("trade_delete_order gagal: %s", msg)
            return {"ok": False, "ticket": ticket, "message": msg}
        result = _parse_order_result(res)
        result["ticket"] = ticket
        if result["ok"]:
            logger.info("Pending order %s dihapus.", ticket)
        else:
            result["message"] = _friendly_trade_error(result.get("message", ""))
            logger.error("Gagal menghapus pending order %s: %s", ticket, result["message"])
        return result

    def pending_orders(self, symbol: Optional[str] = None) -> list:
        """Daftar pending order (dari get_trading_open_positions -> orders)."""
        try:
            res = self._client.call_tool("get_trading_open_positions")
        except McpError as exc:
            logger.error("get_trading_open_positions (orders) gagal: %s", exc)
            return []
        raw = res.get("orders", []) if isinstance(res, dict) else []
        out = [_normalize_order(o) for o in raw]
        if symbol:
            out = [o for o in out if o.get("symbol") == symbol]
        return out

    def __repr__(self) -> str:
        return f"McpBackend(client={self._client!r})"
