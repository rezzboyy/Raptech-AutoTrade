"""Test penyimpanan profil MCP: validate + roundtrip save/list/load/apply/delete."""

import os
import shutil
import tempfile
import unittest

from config.settings import settings
from src import mcp_profile_store as store


class TestMcpProfileStore(unittest.TestCase):

    def setUp(self):
        self._orig_dir = store.PROFILES_DIR
        self._tmp = tempfile.mkdtemp(prefix="mcp_prof_")
        store.PROFILES_DIR = self._tmp
        # Simpan state settings untuk dipulihkan.
        self._orig = (settings.backend, settings.mcp_endpoint, settings.mcp_api_key)

    def tearDown(self):
        store.PROFILES_DIR = self._orig_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        settings.backend, settings.mcp_endpoint, settings.mcp_api_key = self._orig

    def test_validate(self):
        self.assertTrue(store.validate({"endpoint": "", "api_key": ""}))
        self.assertTrue(store.validate({"endpoint": "http://x", "api_key": ""}))
        self.assertEqual(store.validate({"endpoint": "http://x", "api_key": "k"}), [])

    def test_roundtrip_save_list_load(self):
        cfg = {"endpoint": "http://127.0.0.1:22346/mcp", "api_key": "SECRET123+/="}
        path = store.save_profile("Akun MCP Ku", cfg)
        self.assertTrue(os.path.exists(path))

        profiles = store.list_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["name"], "Akun MCP Ku")
        # list tidak boleh membocorkan api_key.
        self.assertNotIn("api_key", profiles[0])

        loaded = store.load_profile(path)
        self.assertEqual(loaded["endpoint"], cfg["endpoint"])
        self.assertEqual(loaded["api_key"], cfg["api_key"])  # dibuka kembali dgn benar

    def test_api_key_obfuscated_on_disk(self):
        cfg = {"endpoint": "http://x", "api_key": "PLAINTEXTKEY"}
        path = store.save_profile("p", cfg)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        self.assertNotIn("PLAINTEXTKEY", raw)  # tidak tersimpan sebagai teks polos

    def test_apply_to_settings(self):
        settings.backend = "native"
        store.apply_to_settings({"endpoint": "http://ep", "api_key": "KK"})
        self.assertEqual(settings.backend, "mcp")
        self.assertEqual(settings.mcp_endpoint, "http://ep")
        self.assertEqual(settings.mcp_api_key, "KK")

    def test_delete(self):
        path = store.save_profile("hapus", {"endpoint": "http://x", "api_key": "k"})
        self.assertTrue(store.delete_profile(path))
        self.assertEqual(len(store.list_profiles()), 0)

    def test_load_mcp_secret_format(self):
        """Memilih mcp_secret.json (format mcp_*, teks biasa) harus terbaca penuh."""
        import json
        path = os.path.join(self._tmp, "mcp_secret.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "mcp_endpoint": "http://127.0.0.1:22346/mcp",
                "mcp_api_key": "EXNESS_KEY_ABC+/=",
            }, f)
        loaded = store.load_profile(path)
        self.assertEqual(loaded["endpoint"], "http://127.0.0.1:22346/mcp")
        self.assertEqual(loaded["api_key"], "EXNESS_KEY_ABC+/=")  # teks biasa, tak di-decrypt

    def test_load_profile_format_still_works(self):
        """Format profil normal (api_key terenkripsi) tetap terbaca benar."""
        path = store.save_profile("normal", {"endpoint": "http://ep", "api_key": "KEY123"})
        loaded = store.load_profile(path)
        self.assertEqual(loaded["api_key"], "KEY123")

    def test_save_secret_file_roundtrip(self):
        """save_secret_file menulis JSON yang bisa dibaca ulang (auto-save API key)."""
        path = os.path.join(self._tmp, "mcp_secret.json")
        cfg = {"endpoint": "http://127.0.0.1:22346/mcp", "api_key": "NEW_EXNESS_KEY+/="}
        out = store.save_secret_file(cfg, path=path)
        self.assertEqual(out, path)
        self.assertTrue(os.path.exists(path))
        loaded = store.load_profile(path)
        self.assertEqual(loaded["endpoint"], cfg["endpoint"])
        self.assertEqual(loaded["api_key"], cfg["api_key"])


if __name__ == "__main__":
    unittest.main()
