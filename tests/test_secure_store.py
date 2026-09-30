"""Test enkripsi at-rest (secure_store): roundtrip, marker, fallback base64."""

import base64
import random
import string
import unittest

from src import secure_store


class TestSecureStore(unittest.TestCase):

    def test_roundtrip(self):
        for text in ["Selokerto-1", "API+KEY/with=chars", "", "x", "π unicode ✓"]:
            token = secure_store.encrypt(text)
            self.assertEqual(secure_store.decrypt(token), text)

    def test_encrypted_marker_and_not_plaintext(self):
        token = secure_store.encrypt("RAHASIA123")
        self.assertTrue(token.startswith("enc:v1:"))
        self.assertNotIn("RAHASIA123", token)
        self.assertTrue(secure_store.is_encrypted(token))

    def test_empty_stays_empty(self):
        self.assertEqual(secure_store.encrypt(""), "")
        self.assertEqual(secure_store.decrypt(""), "")

    def test_legacy_base64_fallback(self):
        # Nilai lama tersandi base64 murni (tanpa penanda) harus tetap terbaca.
        legacy = base64.b64encode("PasswordLama".encode("utf-8")).decode("ascii")
        self.assertFalse(secure_store.is_encrypted(legacy))
        self.assertEqual(secure_store.decrypt(legacy), "PasswordLama")

    def test_property_random_roundtrip(self):
        random.seed(42)
        alphabet = string.printable
        for _ in range(200):
            n = random.randint(1, 120)
            text = "".join(random.choice(alphabet) for _ in range(n))
            token = secure_store.encrypt(text)
            self.assertTrue(secure_store.is_encrypted(token))
            self.assertNotIn(text, token)  # plaintext tak muncul di token
            self.assertEqual(secure_store.decrypt(token), text)


if __name__ == "__main__":
    unittest.main()
