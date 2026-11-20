"""Test klasifikasi tipe akun (Demo/Real/Contest) resmi dari MT5."""

import unittest

from src.backends.base import classify_account_type


class TestClassifyAccountType(unittest.TestCase):

    def test_server_trial_is_demo(self):
        # Exness Trial melaporkan type 'real' tapi server 'Trial' -> harus DEMO.
        self.assertEqual(classify_account_type("real", "Exness-MT5Trial14"), "DEMO")

    def test_server_demo_is_demo(self):
        self.assertEqual(classify_account_type("real", "MetaQuotes-Demo"), "DEMO")

    def test_real(self):
        self.assertEqual(classify_account_type("real", "Exness-MT5Real8"), "REAL")

    def test_demo_type(self):
        self.assertEqual(classify_account_type("demo", "SomeBroker-Server"), "DEMO")

    def test_contest(self):
        self.assertEqual(classify_account_type("contest", "Broker-Contest"), "CONTEST")

    def test_unknown(self):
        self.assertEqual(classify_account_type("", ""), "?")


if __name__ == "__main__":
    unittest.main()
