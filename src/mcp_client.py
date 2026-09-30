"""Klien MCP tingkat rendah untuk terminal MetaTrader 5.

Terminal MT5 (build 61xx+) menyediakan server MCP (Model Context Protocol) lokal,
mis. http://127.0.0.1:22346/mcp, terautentikasi dengan API Key (Bearer). Klien ini
berbicara JSON-RPC 2.0 melalui HTTP "Streamable" (respons bisa JSON biasa atau SSE).

Dipakai oleh McpBackend sebagai transport agar bot tidak bergantung pada library
`MetaTrader5` yang terikat versi build.

Alur pemakaian:
    c = McpClient(endpoint, api_key)
    c.initialize()                      # -> info server, simpan session id
    data = c.call_tool("get_trading_account_info")
"""

import json
import re
import urllib.error
import urllib.request

from src.logger import get_logger

logger = get_logger(__name__)

MCP_PROTOCOL_VERSION = "2025-06-18"


# ----- Error spesifik -----

class McpError(Exception):
    """Kesalahan umum terkait MCP."""


class McpConnectionError(McpError):
    """Endpoint tidak dapat dijangkau (server MCP mati / belum aktif)."""


class McpAuthError(McpError):
    """Autentikasi gagal (HTTP 401) — API Key salah/kedaluwarsa."""


class McpTimeoutError(McpError):
    """Permintaan melebihi batas waktu."""


class McpToolError(McpError):
    """Server mengembalikan error di dalam hasil tool."""


def mask_token(token: str) -> str:
    """Samarkan token untuk keperluan log (tidak pernah tampilkan utuh)."""
    if not token:
        return "<kosong>"
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def _extract_json_payload(body: str) -> dict:
    """Ambil objek JSON dari body respons (JSON biasa maupun SSE 'data: {..}')."""
    body = (body or "").strip()
    if not body:
        return {}
    # Format SSE: cari baris data: {json} terakhir.
    matches = re.findall(r"data:\s*(\{.*\})", body)
    raw = matches[-1] if matches else body
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class McpClient:
    """Klien HTTP/JSON-RPC untuk server MCP MetaTrader 5."""

    def __init__(self, endpoint: str, api_key: str, timeout: float = 15.0):
        self.endpoint = endpoint
        self._api_key = api_key or ""
        self.timeout = timeout
        self.session_id = None
        self._initialized = False

    def __repr__(self) -> str:  # tidak pernah bocorkan token
        return f"McpClient(endpoint={self.endpoint!r}, api_key={mask_token(self._api_key)})"

    # ----- Transport -----

    def _post(self, payload: dict) -> tuple[int, str, dict]:
        """Kirim satu permintaan JSON-RPC. Kembalikan (status, body, headers)."""
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise McpAuthError(
                    "Autentikasi MCP gagal (401). Periksa/salin ulang API Key dari "
                    "MT5 -> Tools -> Options -> tab MCP."
                ) from exc
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                pass
            return exc.code, body, {}
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise McpTimeoutError(f"Permintaan MCP timeout setelah {self.timeout}s.") from exc
            raise McpConnectionError(
                f"Tidak dapat menjangkau server MCP di {self.endpoint}. "
                "Aktifkan 'Enable internal server' di MT5 -> Options -> MCP. "
                f"Detail: {reason}"
            ) from exc
        except TimeoutError as exc:
            raise McpTimeoutError(f"Permintaan MCP timeout setelah {self.timeout}s.") from exc

    def _rpc(self, method: str, params: dict | None = None, is_notification: bool = False) -> dict:
        payload = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            payload["id"] = 1
        if params is not None:
            payload["params"] = params

        status, body, _ = self._post(payload)
        if status >= 400:
            raise McpError(f"MCP '{method}' gagal (HTTP {status}): {body[:200]}")
        if is_notification:
            return {}

        obj = _extract_json_payload(body)
        if "error" in obj and obj["error"]:
            err = obj["error"]
            raise McpToolError(f"MCP '{method}' error: {err}")
        return obj.get("result", obj)

    # ----- API tingkat tinggi -----

    def initialize(self) -> dict:
        """Lakukan handshake MCP: initialize + notifications/initialized."""
        result = self._rpc("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "xaviq-trading-engine", "version": "1.0"},
        })
        # Wajib kirim notifikasi initialized sebelum memanggil tool.
        self._rpc("notifications/initialized", is_notification=True)
        self._initialized = True
        logger.info(
            "MCP terinisialisasi (endpoint=%s, token=%s, session=%s).",
            self.endpoint, mask_token(self._api_key), self.session_id,
        )
        return result

    def is_ready(self) -> bool:
        return self._initialized and bool(self.session_id)

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """Panggil satu tool MCP. Kembalikan payload hasil (dict).

        Tool MT5 mengembalikan teks JSON di result.content[].text; fungsi ini
        mengurainya menjadi dict Python. Bila sesi kedaluwarsa, coba re-inisialisasi
        sekali lalu ulang.
        """
        if not self._initialized:
            self.initialize()

        try:
            return self._call_tool_once(name, arguments)
        except (McpToolError, McpError) as exc:
            # Kemungkinan sesi invalid → coba initialize ulang sekali lalu retry.
            if self._looks_like_session_error(exc):
                logger.warning("Sesi MCP mungkin kedaluwarsa, inisialisasi ulang lalu ulangi '%s'.", name)
                self.session_id = None
                self._initialized = False
                self.initialize()
                return self._call_tool_once(name, arguments)
            raise

    def _call_tool_once(self, name: str, arguments: dict | None) -> dict:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})

        # Cek flag error tool.
        if isinstance(result, dict) and result.get("isError"):
            text = self._first_text(result)
            raise McpToolError(f"Tool '{name}' gagal: {text or result}")

        # Ekstrak teks JSON dari content bila ada.
        text = self._first_text(result)
        if text is not None:
            parsed = self._maybe_json(text)
            # Tool MT5 kadang mengembalikan pesan error sebagai teks biasa.
            if isinstance(parsed, str) and "invalid" in parsed.lower():
                raise McpToolError(f"Tool '{name}': {parsed}")
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        return result if isinstance(result, dict) else {"value": result}

    @staticmethod
    def _first_text(result: dict):
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    return c.get("text", "")
        return None

    @staticmethod
    def _maybe_json(text: str):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    @staticmethod
    def _looks_like_session_error(exc: Exception) -> bool:
        s = str(exc).lower()
        return "session" in s or "not initialized" in s or "http 400" in s

    def close(self) -> None:
        self.session_id = None
        self._initialized = False
