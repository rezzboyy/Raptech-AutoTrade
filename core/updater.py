from __future__ import annotations

"""
Raptech Autotrade CLI — GitHub OTA Auto-Updater Engine.
Checks GitHub Releases API, compares semver, and performs seamless in-place updates.
"""

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Optional, Tuple
import urllib.request

from core.logger import get_logger
from core.version import GITHUB_REPO_FULL, __version__

logger = get_logger("updater")


@dataclass
class UpdateInfo:
    tag_name: str
    version: str
    title: str
    changelog: str
    published_at: str
    exe_download_url: Optional[str] = None
    exe_size_bytes: int = 0
    zip_download_url: Optional[str] = None
    zip_size_bytes: int = 0

    @property
    def exe_size_mb(self) -> float:
        return round(self.exe_size_bytes / (1024 * 1024), 2)


def parse_semver(v_str: str) -> Tuple[int, ...]:
    """Parse string version like 'v3.1.0' or '3.2.1' into tuple of integers."""
    clean = v_str.strip().lstrip("vV")
    parts = []
    for chunk in clean.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer_version(remote_v: str, current_v: str) -> bool:
    """Compare two semantic versions. Returns True if remote is strictly newer."""
    remote_parts = parse_semver(remote_v)
    curr_parts = parse_semver(current_v)
    # Pad shorter version with zeros
    max_len = max(len(remote_parts), len(curr_parts))
    r_padded = remote_parts + (0,) * (max_len - len(remote_parts))
    c_padded = curr_parts + (0,) * (max_len - len(curr_parts))
    return r_padded > c_padded


def check_for_update(timeout: float = 8.0) -> Optional[UpdateInfo]:
    """
    Check GitHub Releases API for latest published release.
    Returns UpdateInfo if newer release exists, otherwise None.
    """
    api_url = f"https://api.github.com/repos/{GITHUB_REPO_FULL}/releases/latest"
    req = urllib.request.Request(
        api_url,
        headers={
            "User-Agent": "Raptech-AutoTrade-OTA",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                logger.debug(f"GitHub API status: {response.status}")
                return None
            data = json.loads(response.read().decode("utf-8"))

        tag_name = data.get("tag_name", "").strip()
        version_num = tag_name.lstrip("vV")
        if not tag_name or not is_newer_version(tag_name, __version__):
            return None

        # Look for executable and zip in assets
        exe_url = None
        exe_size = 0
        zip_url = None
        zip_size = 0

        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe"):
                exe_url = asset.get("browser_download_url")
                exe_size = asset.get("size", 0)
            elif name.endswith(".zip"):
                zip_url = asset.get("browser_download_url")
                zip_size = asset.get("size", 0)

        return UpdateInfo(
            tag_name=tag_name,
            version=version_num,
            title=data.get("name") or f"Raptech AutoTrade {tag_name}",
            changelog=data.get("body", "Pembaruan performa dan stabilitas."),
            published_at=data.get("published_at", ""),
            exe_download_url=exe_url,
            exe_size_bytes=exe_size,
            zip_download_url=zip_url,
            zip_size_bytes=zip_size,
        )

    except Exception as exc:
        logger.debug(f"Gagal memeriksa pembaruan: {exc}")
        return None


def download_file_with_progress(
    url: str,
    dest_path: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    timeout: float = 30.0,
) -> bool:
    """Download file streaming with optional progress callback (downloaded_bytes, total_bytes)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Raptech-AutoTrade-OTA"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 64 * 1024  # 64 KB chunks

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        return True
    except Exception as exc:
        logger.error(f"Gagal mengunduh berkas update: {exc}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def apply_windows_update(
    new_binary_path: Path,
    target_binary_name: str = "RaptechAutoTrade.exe",
    restart: bool = True,
) -> None:
    """
    Apply executable update in-place on Windows using a detached self-cleaning batch script.
    """
    app_dir = Path(os.getcwd()).resolve()
    target_path = app_dir / target_binary_name
    batch_file = app_dir / "_finish_update.bat"

    restart_cmd = f'start "" "{target_binary_name}"' if restart else ""

    batch_content = f"""@echo off
chcp 65001 >nul
timeout /t 1 /nobreak >nul
:retry
move /y "{new_binary_path.name}" "{target_binary_name}" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto retry
)
{restart_cmd}
del "%~f0"
"""
    batch_file.write_text(batch_content, encoding="utf-8")

    # Spawn batch file detached and exit
    subprocess.Popen(
        ["cmd.exe", "/c", str(batch_file.name)],
        cwd=str(app_dir),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0x00000008),
        close_fds=True,
    )
    sys.exit(0)
