from __future__ import annotations

"""Unit tests for GitHub OTA Auto-Updater Engine."""

from core.updater import UpdateInfo, is_newer_version, parse_semver


def test_semver_parsing_and_comparison():
    assert parse_semver("3.1.0") == (3, 1, 0)
    assert parse_semver("v3.1.0") == (3, 1, 0)
    assert parse_semver("V3.2.1") == (3, 2, 1)
    assert parse_semver("3.1") == (3, 1)

    # Comparisons
    assert is_newer_version("v3.1.1", "3.1.0") is True
    assert is_newer_version("3.2.0", "3.1.9") is True
    assert is_newer_version("4.0.0", "3.9.9") is True
    assert is_newer_version("3.1.0", "3.1.0") is False
    assert is_newer_version("3.0.9", "3.1.0") is False
    assert is_newer_version("v3.1.0", "3.1.0") is False


def test_update_info_properties():
    info = UpdateInfo(
        tag_name="v3.2.0",
        version="3.2.0",
        title="Raptech AutoTrade v3.2.0",
        changelog="New features and fixes",
        published_at="2026-11-16T12:00:00Z",
        exe_download_url="https://github.com/example/exe",
        exe_size_bytes=47800000,
    )
    assert info.exe_size_mb > 40.0
    assert info.version == "3.2.0"
