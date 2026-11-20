"""Unit & property test untuk McpClient (parser & keamanan token).

Tidak butuh MT5 maupun koneksi jaringan.
"""

import random
import string
import unittest

from src.mcp_client import _extract_json_payload, mask_token, McpClient


class TestMcpParser(unittest.TestCase):
    """Parsing respons JSON biasa maupun SSE."""

    def test_parse_plain_json(self):
        body = '{"jsonrpc":"2.0","id":1,"result":{"ok":true}}'
        obj = _extract_json_payload(body)
        self.assertEqual(obj.get("result", {}).get("ok"), True)

    def test_parse_sse(self):
        body = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":1,"result":{"value":42}}\n\n'
        )
        obj = _extract_json_payload(body)
        self.assertEqual(obj.get("result", {}).get("value"), 42)

    def test_parse_sse_takes_last_data(self):
        body = (
            'data: {"result":{"n":1}}\n\n'
            'data: {"result":{"n":2}}\n\n'
        )
        obj = _extract_json_payload(body)
        self.assertEqual(obj.get("result", {}).get("n"), 2)

    def test_parse_empty(self):
        self.assertEqual(_extract_json_payload(""), {})
        self.assertEqual(_extract_json_payload("bukan json"), {})


class TestTokenMasking(unittest.TestCase):
    """Property 4: token tidak pernah tampil utuh dalam bentuk ter-mask/log."""

    def _random_token(self, n):
        alphabet = string.ascii_letters + string.digits + "+/="
        return "".join(random.choice(alphabet) for _ in range(n))

    def test_mask_never_reveals_full_token(self):
        random.seed(1234)
        for _ in range(200):
            length = random.randint(9, 80)
            token = self._random_token(length)
            masked = mask_token(token)
            # Token utuh tidak boleh muncul dalam hasil mask.
            self.assertNotEqual(masked, token)
            self.assertNotIn(token, masked)
            # Tidak membocorkan bagian tengah.
            self.assertIn("...", masked)

    def test_repr_client_masks_token(self):
        token = "SUPERSECRETTOKENVALUE1234567890"
        c = McpClient("http://127.0.0.1:22346/mcp", token)
        r = repr(c)
        self.assertNotIn(token, r)

    def test_short_and_empty_tokens(self):
        self.assertEqual(mask_token(""), "<kosong>")
        self.assertEqual(mask_token("abc"), "****")


if __name__ == "__main__":
    unittest.main()
