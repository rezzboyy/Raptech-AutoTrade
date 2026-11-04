from __future__ import annotations

"""Unit tests for configuration and profile management."""

import os
from pathlib import Path
import pytest

from core.config_store import AccountProfile, RiskSettings, list_profiles, load_profile, save_profile


def test_profile_serialization():
    p = AccountProfile(
        profile_name="Test-Profile",
        backend="native",
        login=99999,
        password="my_password",
        server="TestServer",
        symbols=["XAUUSDm"],
        strategy="fast_gold_scalper",
        risk=RiskSettings(fixed_lot=0.05, max_daily_loss=100.0),
    )
    d = p.to_dict(encrypt_password=True)
    assert d["password"].startswith(("enc:v1:", "enc:v2:"))
    # Strategy and risk settings are strictly kept out of profile serialization
    assert "strategy" not in d
    assert "risk" not in d
    assert "allow_hedging" not in d
    assert "close_on_opposite_signal" not in d

    loaded = AccountProfile.from_dict(d)
    assert loaded.profile_name == "Test-Profile"
    assert loaded.password == "my_password"


def test_save_and_load_profile(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config_store.PROFILES_DIR", tmp_path)
    p = AccountProfile(profile_name="Unit_Test_Prof", login=777)
    saved_path = save_profile(p, "Unit_Test_Prof")
    assert saved_path.exists()

    all_p = list_profiles()
    assert "Unit_Test_Prof" in all_p

    loaded = load_profile("Unit_Test_Prof")
    assert loaded.login == 777
