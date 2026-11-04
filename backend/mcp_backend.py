from __future__ import annotations

"""
Raptech Autotrade CLI — MCP (Model Context Protocol) Backend.
Communicates with MT5 MCP Server via JSON-RPC 2.0 HTTP protocol.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

from backend.base import (
    AccountInfo,
    Candle,
    OrderResult,
    Position,
    SymbolSpec,
    Tick,
    candidate_symbol_variations,
    classify_account_type,
    resolve_symbol_name,
)
from core.logger import get_logger

logger = get_logger("backend.mcp")


class McpBackend:
    """MCP JSON-RPC Trading Backend."""

    def __init__(self, endpoint_url: str = "http://127.0.0.1:8000/mcp", api_key: str = "") -> None:
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self._connected = False
        self._request_id = 1
        self._session_id: Optional[str] = None

    def _call_json_rpc(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Any:
        req_id = self._request_id
        self._request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "RaptechAutoTrade/3.1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.endpoint_url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            sess_hdr = response.headers.get("Mcp-Session-Id")
            if sess_hdr:
                self._session_id = sess_hdr
            resp_body = response.read().decode("utf-8")
            result_json = json.loads(resp_body)

        if "error" in result_json:
            raise RuntimeError(f"JSON-RPC Error: {result_json['error']}")
        return result_json.get("result")

    def _call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        res = self._call_json_rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if isinstance(res, dict) and "content" in res:
            for item in res["content"]:
                if item.get("type") == "text":
                    try:
                        return json.loads(item["text"])
                    except Exception:
                        return item["text"]
        return res

    def connect(self) -> bool:
        try:
            init_res = self._call_json_rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "RaptechAutoTrade", "version": "3.1.0"},
            })
            self._call_json_rpc("notifications/initialized")
            self._connected = True
            logger.info("Terhubung ke remote MCP Server")
            return True
        except Exception as exc:
            logger.error(f"Gagal koneksi ke MCP Gateway {self.endpoint_url}: {exc}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        self._connected = False
        self._session_id = None
        logger.info("MCP Backend terputus.")

    def account_info(self) -> Optional[AccountInfo]:
        if not self._connected:
            return None
        try:
            raw = self._call_tool("mt5_account_info")
            if not isinstance(raw, dict):
                return None
            trade_mode_val = raw.get("trade_mode")
            currency_str = str(raw.get("currency", "USD"))
            server_str = str(raw.get("server", ""))
            acc_type = classify_account_type(trade_mode_val, server_str, currency_str)
            is_cent = "CENT" in acc_type or "cent" in server_str.lower() or currency_str.upper() in ("USC", "USCC")

            return AccountInfo(
                login=int(raw.get("login", 0)),
                server=server_str,
                currency=currency_str,
                balance=float(raw.get("balance", 0.0)),
                equity=float(raw.get("equity", 0.0)),
                margin=float(raw.get("margin", 0.0)),
                free_margin=float(raw.get("margin_free", 0.0)),
                margin_level=float(raw.get("margin_level", 0.0)),
                profit=float(raw.get("profit", 0.0)),
                trade_allowed=bool(raw.get("trade_allowed", False)),
                server_connected=bool(raw.get("connected", True)),
                account_type=acc_type,
                leverage=int(raw.get("leverage", 100)),
                is_cent=is_cent,
            )
        except Exception as exc:
            logger.error(f"Gagal mengambil MCP account_info: {exc}")
            return None

    def list_symbols(self, limit: int = 60) -> List[str]:
        if not self._connected:
            return []
        try:
            raw = self._call_tool("mt5_symbols_get", {"limit": limit})
            if isinstance(raw, list):
                return [s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in raw[:limit]]
            return []
        except Exception:
            return []

    def symbol_spec(self, symbol: str) -> Optional[SymbolSpec]:
        if not self._connected:
            return None
        try:
            raw = self._call_tool("mt5_symbol_info", {"symbol": symbol})
            if not isinstance(raw, dict):
                return None
            return SymbolSpec(
                symbol=str(raw.get("name", symbol)),
                digits=int(raw.get("digits", 5)),
                point=float(raw.get("point", 0.00001)),
                volume_min=float(raw.get("volume_min", 0.01)),
                volume_max=float(raw.get("volume_max", 100.0)),
                volume_step=float(raw.get("volume_step", 0.01)),
                tick_value=float(raw.get("trade_tick_value", 1.0)),
                tick_size=float(raw.get("trade_tick_size", 0.00001)),
                stop_level=int(raw.get("trade_stops_level", 0)),
            )
        except Exception:
            return None

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        syms = self.list_symbols(limit=500)
        return resolve_symbol_name(symbol, syms)

    def ensure_symbol(self, symbol: str) -> bool:
        if not self._connected:
            return False
        try:
            res = self._call_tool("mt5_symbol_select", {"symbol": symbol, "enable": True})
            return bool(res)
        except Exception:
            return False

    def get_tick(self, symbol: str) -> Optional[Tick]:
        if not self._connected:
            return None
        try:
            raw = self._call_tool("mt5_symbol_info_tick", {"symbol": symbol})
            if not isinstance(raw, dict):
                return None
            epoch = int(raw.get("time", 0))
            dt = datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else datetime.now(timezone.utc)
            return Tick(
                bid=float(raw.get("bid", 0.0)),
                ask=float(raw.get("ask", 0.0)),
                time=dt,
                last=float(raw.get("last", 0.0)),
                volume=int(raw.get("volume", 0)),
            )
        except Exception:
            return None

    def spread_points(self, symbol: str) -> Optional[float]:
        tick = self.get_tick(symbol)
        spec = self.symbol_spec(symbol)
        if tick and spec and spec.point > 0:
            return round((tick.ask - tick.bid) / spec.point, 1)
        return None

    def get_candles(self, symbol: str, timeframe_str: str, count: int = 200) -> List[Candle]:
        if not self._connected:
            return []
        try:
            raw = self._call_tool("mt5_copy_rates_from_pos", {
                "symbol": symbol,
                "timeframe": timeframe_str.upper(),
                "start_pos": 0,
                "count": count,
            })
            if not isinstance(raw, list):
                return []
            res = []
            for r in raw:
                epoch = int(r.get("time", 0))
                res.append(
                    Candle(
                        time=datetime.fromtimestamp(epoch, tz=timezone.utc),
                        open=float(r.get("open", 0.0)),
                        high=float(r.get("high", 0.0)),
                        low=float(r.get("low", 0.0)),
                        close=float(r.get("close", 0.0)),
                        tick_volume=int(r.get("tick_volume", 0)),
                    )
                )
            return res
        except Exception as exc:
            logger.error(f"Gagal mengambil candles MCP: {exc}")
            return []

    def positions(self, symbol: Optional[str] = None) -> List[Position]:
        if not self._connected:
            return []
        try:
            params = {}
            if symbol:
                params["symbol"] = symbol
            raw = self._call_tool("mt5_positions_get", params)
            if not isinstance(raw, list):
                return []
            res = []
            for p in raw:
                epoch = int(p.get("time", 0))
                open_time = datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else None
                side_str = "BUY" if int(p.get("type", 0)) == 0 else "SELL"
                res.append(
                    Position(
                        ticket=int(p.get("ticket", 0)),
                        symbol=str(p.get("symbol", "")),
                        type=side_str,
                        volume=float(p.get("volume", 0.0)),
                        price_open=float(p.get("price_open", 0.0)),
                        price_current=float(p.get("price_current", 0.0)),
                        sl=float(p.get("sl", 0.0)),
                        tp=float(p.get("tp", 0.0)),
                        profit=float(p.get("profit", 0.0)),
                        magic=int(p.get("magic", 0)),
                        comment=str(p.get("comment", "")),
                        time=open_time,
                    )
                )
            return res
        except Exception:
            return []

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
        if not self._connected:
            return OrderResult(ok=False, message="MCP backend tidak terhubung")
        try:
            res = self._call_tool("mt5_order_send", {
                "symbol": symbol,
                "action": "market",
                "side": side.lower(),
                "volume": volume,
                "sl": sl,
                "tp": tp,
                "magic": magic,
                "comment": comment,
            })
            if isinstance(res, dict) and res.get("retcode") == 10009:
                return OrderResult(
                    ok=True,
                    ticket=int(res.get("order", 0)),
                    price=float(res.get("price", 0.0)),
                    volume=volume,
                    message="Order sukses",
                )
            msg = res.get("comment") if isinstance(res, dict) else str(res)
            return OrderResult(ok=False, message=f"Order gagal: {msg}")
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi MCP order_send: {exc}")

    def close_position(self, ticket: int, symbol: str, volume: Optional[float] = None) -> OrderResult:
        if not self._connected:
            return OrderResult(ok=False, message="MCP backend tidak terhubung")
        try:
            res = self._call_tool("mt5_order_close", {"ticket": ticket, "symbol": symbol, "volume": volume})
            if isinstance(res, dict) and res.get("retcode") == 10009:
                return OrderResult(ok=True, ticket=ticket, message="Posisi ditutup")
            return OrderResult(ok=False, message="Tutup posisi gagal")
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi MCP close: {exc}")

    def modify_sl_tp(
        self, ticket: int, symbol: str, sl: Optional[float] = None, tp: Optional[float] = None
    ) -> bool:
        if not self._connected:
            return False
        try:
            res = self._call_tool("mt5_order_modify", {"ticket": ticket, "symbol": symbol, "sl": sl, "tp": tp})
            return bool(isinstance(res, dict) and res.get("retcode") == 10009)
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
        if not self._connected:
            return OrderResult(ok=False, message="MCP backend tidak terhubung")
        try:
            res = self._call_tool("mt5_order_send", {
                "symbol": symbol,
                "action": "pending",
                "order_type": order_type.lower(),
                "volume": volume,
                "price": price,
                "sl": sl,
                "tp": tp,
                "magic": magic,
                "comment": comment,
            })
            if isinstance(res, dict) and res.get("retcode") == 10009:
                return OrderResult(ok=True, order=int(res.get("order", 0)), message="Pending order berhasil")
            return OrderResult(ok=False, message="Pending order gagal")
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi MCP pending: {exc}")

    def delete_pending_order(self, ticket: int) -> OrderResult:
        if not self._connected:
            return OrderResult(ok=False, message="MCP backend tidak terhubung")
        try:
            res = self._call_tool("mt5_order_delete", {"ticket": ticket})
            return OrderResult(ok=True, order=ticket, message="Pending order dihapus")
        except Exception as exc:
            return OrderResult(ok=False, message=f"Eksepsi MCP delete: {exc}")
