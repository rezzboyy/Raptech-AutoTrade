"""Test adaptasi otomatis simbol akun broker Exness (Standard 'm', Pro polos, Cent 'c', dll)."""

import pytest
from unittest.mock import MagicMock

from src.backends.base import candidate_symbol_variations, resolve_symbol_name
from src.backends.mcp_backend import McpBackend
from src.bot_engine import BotEngine
from config.settings import settings


class TestCandidateSymbolVariations:
    def test_standard_with_m_suffix(self):
        """Simbol berakhiran 'm' (Exness Standard) menghasilkan root polos dan variasi lain."""
        vars_ = candidate_symbol_variations("EURUSDm")
        assert "EURUSDm" in vars_
        assert "EURUSD" in vars_
        assert "EURUSDc" in vars_
        assert "EURUSD.pro" in vars_
        assert "EURUSDraw" in vars_

    def test_plain_symbol_without_suffix(self):
        """Simbol tanpa suffix (Exness Pro/Raw) menghasilkan kandidat 'm', 'c', dsb."""
        vars_ = candidate_symbol_variations("EURUSD")
        assert "EURUSD" in vars_
        assert "EURUSDm" in vars_
        assert "EURUSDc" in vars_
        assert "EURUSD.pro" in vars_

    def test_commodity_and_crypto(self):
        """Mendukung instrumen emas (XAUUSD) dan kripto (BTCUSD)."""
        gold_vars = candidate_symbol_variations("XAUUSDm")
        assert "XAUUSD" in gold_vars
        assert "XAUUSDm" in gold_vars

        btc_vars = candidate_symbol_variations("BTCUSD")
        assert "BTCUSDm" in btc_vars

    def test_empty_string(self):
        assert candidate_symbol_variations("") == []
        assert candidate_symbol_variations("   ") == []


class TestResolveSymbolName:
    def test_exact_match(self):
        avail = ["EURUSDm", "GBPUSDm", "XAUUSDm"]
        assert resolve_symbol_name("EURUSDm", avail) == "EURUSDm"

    def test_exness_real_standard_to_pro(self):
        """Config diset EURUSDm tapi akun Real bertipe Pro (tersedia EURUSD polos)."""
        avail = ["EURUSD", "GBPUSD", "XAUUSD"]
        assert resolve_symbol_name("EURUSDm", avail) == "EURUSD"

    def test_exness_real_pro_to_standard(self):
        """Config diset EURUSD tapi akun Real bertipe Standard (tersedia EURUSDm)."""
        avail = ["EURUSDm", "GBPUSDm", "XAUUSDm"]
        assert resolve_symbol_name("EURUSD", avail) == "EURUSDm"

    def test_exness_cent_account(self):
        """Config diset EURUSD tapi akun bertipe Standard Cent (tersedia EURUSDc)."""
        avail = ["EURUSDc", "GBPUSDc"]
        assert resolve_symbol_name("EURUSD", avail) == "EURUSDc"

    def test_case_insensitivity(self):
        """Menangani input huruf kecil seperti eurusdm atau eurusd."""
        avail = ["EURUSDm", "XAUUSDm"]
        assert resolve_symbol_name("eurusdm", avail) == "EURUSDm"
        assert resolve_symbol_name("eurusd", avail) == "EURUSDm"
        assert resolve_symbol_name("xauusd", avail) == "XAUUSDm"

    def test_unknown_symbol(self):
        avail = ["EURUSDm", "GBPUSDm"]
        assert resolve_symbol_name("UNKNOWNCOIN", avail) is None


class TestMcpBackendSymbolResolution:
    def test_resolve_from_cache(self):
        backend = McpBackend("http://127.0.0.1:22346/mcp", "secret")
        backend._symbol_cache = {
            "EURUSDm": {"symbol": "EURUSDm", "digits": 5},
            "XAUUSDm": {"symbol": "XAUUSDm", "digits": 2},
        }

        # Kasus 1: exact match
        assert backend.resolve_symbol("EURUSDm") == "EURUSDm"
        # Kasus 2: user minta polos, akun punya 'm'
        assert backend.resolve_symbol("EURUSD") == "EURUSDm"
        # Kasus 3: user minta XAUUSD, akun punya XAUUSDm
        assert backend.resolve_symbol("XAUUSD") == "XAUUSDm"

    def test_symbol_spec_auto_resolves(self):
        backend = McpBackend("http://127.0.0.1:22346/mcp", "secret")
        backend._symbol_cache = {
            "EURUSDm": {"symbol": "EURUSDm", "digits": 5, "point": 0.00001},
        }

        # Request symbol_spec('EURUSD') berhasil membaca spec 'EURUSDm'
        spec = backend.symbol_spec("EURUSD")
        assert spec is not None
        assert spec["symbol"] == "EURUSDm"
        assert spec["digits"] == 5


class TestBotEngineAutoAdaptation:
    def test_engine_connect_adapts_settings_symbol(self, monkeypatch):
        """Saat connect, BotEngine otomatis menyelaraskan settings.symbol ke simbol valid akun."""
        engine = BotEngine()
        mock_backend = MagicMock()
        mock_backend.connect.return_value = True

        # Misalkan akun hanya memiliki simbol EURUSD (akun Pro/Raw)
        def fake_resolve(sym):
            return "EURUSD" if "EURUSD" in sym else None

        mock_backend.resolve_symbol.side_effect = fake_resolve
        mock_backend.ensure_symbol.side_effect = lambda s: s == "EURUSD"

        engine.backend = mock_backend

        # Konfigurasi awal bot diset EURUSDm
        monkeypatch.setattr(settings, "symbol", "EURUSDm")

        ok = engine.connect()
        assert ok is True
        # settings.symbol otomatis diadaptasi ke EURUSD
        assert settings.symbol == "EURUSD"
