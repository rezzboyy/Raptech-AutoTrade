from __future__ import annotations

"""Unit tests for CLI commands and dispatcher."""

import pytest
from typer.testing import CliRunner

from cli.commands import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Raptech Autotrade CLI" in result.output


def test_cli_profiles():
    result = runner.invoke(app, ["profiles"])
    assert result.exit_code == 0
    assert "profil akun" in result.output


def test_cli_backup():
    result = runner.invoke(app, ["backup"])
    assert result.exit_code == 0
    assert "Backup berhasil dibuat" in result.output


def test_cli_login_native(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config_store.PROFILES_DIR", tmp_path)
    res = runner.invoke(app, [
        "login",
        "--backend", "native",
        "--profile", "cli_test_native",
        "--login", "88888",
        "--password", "secretpass",
        "--server", "Exness-Trial",
    ])
    assert res.exit_code == 0
    assert "Kredensial NATIVE berhasil disimpan" in res.output


def test_cli_login_mcp(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config_store.PROFILES_DIR", tmp_path)
    res = runner.invoke(app, [
        "login",
        "--backend", "mcp",
        "--profile", "cli_test_mcp",
        "--url", "http://localhost:8000/mcp",
        "--api-key", "my_token",
    ])
    assert res.exit_code == 0
    assert "Kredensial MCP berhasil disimpan" in res.output


def test_cli_test_connection():
    res = runner.invoke(app, ["test-connection", "--profile", "default_example"])
    assert res.exit_code == 0
    assert "Hasil Uji Koneksi" in res.output


def test_cli_market_commands(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config_store.PROFILES_DIR", tmp_path)
    # 1. Default view
    res = runner.invoke(app, ["market", "--profile", "test_prof"])
    assert res.exit_code == 0
    assert "Market / Simbol Aktif" in res.output
    assert "Preset Paket Simbol Siap Pakai" in res.output

    # 2. Preset
    res = runner.invoke(app, ["market", "--profile", "test_prof", "--preset", "crypto"])
    assert res.exit_code == 0
    assert "Preset 'crypto' berhasil diterapkan" in res.output

    # 3. Add
    res = runner.invoke(app, ["market", "--profile", "test_prof", "--add", "XAUUSDm"])
    assert res.exit_code == 0
    assert "Simbol XAUUSDm berhasil ditambahkan" in res.output

    # 4. Remove
    res = runner.invoke(app, ["market", "--profile", "test_prof", "--remove", "BTCUSDm"])
    assert res.exit_code == 0
    assert "Simbol BTCUSDm berhasil dihapus" in res.output

    # 5. Set
    res = runner.invoke(app, ["market", "--profile", "test_prof", "--set", "EURUSDm,GBPUSDm"])
    assert res.exit_code == 0
    assert "Daftar simbol berhasil diperbarui" in res.output

