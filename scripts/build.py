from __future__ import annotations

"""
Raptech Autotrade CLI — Production Build Script.
Runs PyInstaller with slim spec, embeds multi-resolution Logo R icon (.ico),
and packages portable release directory.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DIST_DIR = BASE_DIR / "release"
BUILD_DIR = BASE_DIR / "build"
MAIN_FILE = BASE_DIR / "main.py"
ASSETS_DIR = BASE_DIR / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"
EXE_NAME = "RaptechAutoTrade"


def ensure_icon() -> None:
    if not ICON_PATH.exists():
        src_dicebot = BASE_DIR.parent / "Raptech Dicebot Terminal" / "assets" / "icon.png"
        if src_dicebot.exists():
            print("[INFO] Membuat icon dari Raptech Dicebot Terminal...")
            from PIL import Image
            with Image.open(src_dicebot) as img:
                sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                img.save(ICON_PATH, format="ICO", sizes=sizes)
                if not (ASSETS_DIR / "icon.png").exists():
                    shutil.copy2(src_dicebot, ASSETS_DIR / "icon.png")
        else:
            print("[INFO] Icon belum ditemukan, membuat icon default...")
            from scripts.generate_icon import create_raptech_r_icon
            create_raptech_r_icon()


def build_slim_executable() -> None:
    print("=" * 60)
    print(" Raptech AutoTrade v3.1.0 — PyInstaller Slim Production Build")
    print("=" * 60)

    ensure_icon()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name", EXE_NAME,
        "--onefile",
        "--console",
        "--clean",
        "--icon", str(ICON_PATH),
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        # Exclude heavy unnecessary GUI and scientific libraries
        "--exclude-module", "PySide6",
        "--exclude-module", "PyQt5",
        "--exclude-module", "tkinter",
        "--exclude-module", "turtle",
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "OpenGL",
        "--exclude-module", "pandas",
        # Hidden imports
        "--hidden-import", "rich",
        "--hidden-import", "typer",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.hazmat.primitives.ciphers.aead",
        "--hidden-import", "aiohttp",
        "--hidden-import", "requests",
        "--hidden-import", "MetaTrader5",
        "--hidden-import", "core",
        "--hidden-import", "core.state_store",
        "--hidden-import", "core.backtester",
        "--hidden-import", "core.order_manager",
        "--hidden-import", "core.risk_manager",
        "--hidden-import", "core.secure_store",
        "--hidden-import", "core.config_store",
        "--hidden-import", "core.market_analyzer",
        "--hidden-import", "backend",
        "--hidden-import", "backend.native_backend",
        "--hidden-import", "backend.mcp_backend",
        "--hidden-import", "backend.simulation_backend",
        "--hidden-import", "strategies",
        "--hidden-import", "strategies.fast_gold_scalper",
        "--hidden-import", "strategies.brutal_cent_scalper",
        "--hidden-import", "strategies.ma_cross",
        "--hidden-import", "strategies.rsi_reversal",
        "--hidden-import", "strategies.pa_breakout",
        "--hidden-import", "strategies.pa_rejection",
        "--hidden-import", "strategies.pa_hybrid",
        "--hidden-import", "tui",
        "--hidden-import", "tui.light_app",
        str(MAIN_FILE),
    ]

    print(f"Menjalankan build: {' '.join(cmd)}\n")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode == 0:
        exe_path = DIST_DIR / f"{EXE_NAME}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)

            # Copy portable runtime assets and directories to release
            release_assets = DIST_DIR / "assets"
            release_data = DIST_DIR / "data" / "profiles"
            release_assets.mkdir(parents=True, exist_ok=True)
            release_data.mkdir(parents=True, exist_ok=True)

            # Copy icon
            if ICON_PATH.exists():
                shutil.copy2(ICON_PATH, release_assets / "icon.ico")
            if (ASSETS_DIR / "icon.png").exists():
                shutil.copy2(ASSETS_DIR / "icon.png", release_assets / "icon.png")

            # Copy secret key for encrypted credentials
            src_key = BASE_DIR / ".secret_key"
            if src_key.exists():
                shutil.copy2(src_key, DIST_DIR / ".secret_key")

            # Copy example profile if available
            src_profiles = BASE_DIR / "data" / "profiles"
            if src_profiles.exists():
                for pf in src_profiles.glob("*.json"):
                    shutil.copy2(pf, release_data / pf.name)

            # Create quick launcher batch scripts in release directory
            launcher_cli = DIST_DIR / "Jalankan_CLI.bat"
            launcher_cli.write_text(
                '@echo off\nchcp 65001 >nul\nset "PYTHONIOENCODING=utf-8"\ncd /d "%~dp0"\n'
                f'"{EXE_NAME}.exe"\npause\n',
                encoding="utf-8",
            )

            launcher_autotrade = DIST_DIR / "Jalankan_AutoTrade.bat"
            launcher_autotrade.write_text(
                '@echo off\nchcp 65001 >nul\nset "PYTHONIOENCODING=utf-8"\ncd /d "%~dp0"\n'
                f'"{EXE_NAME}.exe"\npause\n',
                encoding="utf-8",
            )

            launcher_backtest = DIST_DIR / "Jalankan_Backtest.bat"
            launcher_backtest.write_text(
                '@echo off\nchcp 65001 >nul\nset "PYTHONIOENCODING=utf-8"\ncd /d "%~dp0"\n'
                f'"{EXE_NAME}.exe" backtest --strategy fast_gold_scalper --symbol XAUUSDm --timeframe M5 --bars 500\n'
                'pause\n',
                encoding="utf-8",
            )

            print("\n" + "=" * 60)
            print(f"[OK] BUILD SUKSES! Binary: {exe_path} ({size_mb:.1f} MB)")
            print(f"[OK] Icon Logo R berhasil disematkan ke dalam executable!")
            print(f"[OK] Release folder siap digunakan: {DIST_DIR}")
            print("=" * 60)

            # Otomatis buat paket customer zip di folder release/
            try:
                from scripts.package_customer import build_minimal_customer_pack
                build_minimal_customer_pack()
            except Exception as e:
                print(f"[WARN] Gagal membuat paket zip customer: {e}")
    else:
        print("\n[ERROR] Build gagal!")
        sys.exit(1)


if __name__ == "__main__":
    build_slim_executable()
