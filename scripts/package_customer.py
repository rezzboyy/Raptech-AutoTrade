from __future__ import annotations

"""
Raptech Autotrade CLI — Customer Package Builder & Zipping Automation.
Creates a 100% clean, minimal distribution package for customers containing strictly:
1. RaptechAutoTradeCLI.exe (Executable mandiri terbaru v3.0)
2. penggunaan.txt (Panduan lengkap & ringkas penggunaan dalam bahasa Indonesia)
3. data/ (Profil akun & preset bawaan: default, Demo, Real, Simulasi, XAU, BTC, Forex)
4. strategies/ (Strategi trading modular: Fast Gold Scalper, PA Hybrid, Breakout, dll)
   - strategies/market/ & market/ (Preset pasar & parameter risiko XAU, BTC, Forex)
"""

import json
import os
from pathlib import Path
import shutil
import zipfile

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "release"
EXE_PATH = DIST_DIR / "RaptechAutoTrade.exe"
if not EXE_PATH.exists() and (DIST_DIR / "RaptechAutoTradeCLI.exe").exists():
    EXE_PATH = DIST_DIR / "RaptechAutoTradeCLI.exe"

STAGING_DIR = BASE_DIR / "dist_customer" / "Raptech_AutoTrade_v3.1.0"
ZIP_OUTPUT = DIST_DIR / "Raptech_AutoTrade_v3.1.0.zip"


PENGGUNAAN_TXT_CONTENT = """================================================================================
             RAPTECH AUTOTRADE v3.1.0 — PANDUAN PENGGUNAAN RESMI
                      Algorithmic Trading & Capital Safeguards
================================================================================

Selamat datang di Raptech AutoTrade v3.1.0!
Software bot trading otomatis MetaTrader 5 (MT5) dengan arsitektur Dual-View,
Zero-Flicker (bebas kedip), pemindai kondisi pasar otomatis (Market Scanner),
serta proteksi modal berlapis (Virtual Stop Loss, Trailing Stop, Daily Drawdown).


--------------------------------------------------------------------------------
1. CARA MENJALANKAN (SANGAT MUDAH)
--------------------------------------------------------------------------------
Cukup KLIK DUA KALI (Double-Click) pada file:
👉 RaptechAutoTrade.exe (atau 1_Mulai_Raptech_AutoTrade.bat)

Aplikasi akan langsung terbuka di jendela Terminal secara interaktif.
Secara bawaan (default), bot langsung berjalan dalam MODE SIMULASI (Paper Trading).
Anda bisa langsung mencoba dan melihat dashboard bergerak tanpa perlu akun broker
dan tanpa risiko modal riil.


--------------------------------------------------------------------------------
2. CARA MENGHUBUNGKAN KE METATRADER 5 (MT5)
--------------------------------------------------------------------------------
Jika Anda ingin trading di akun Demo atau Real broker Anda:

1. Buka aplikasi MetaTrader 5 di PC / Laptop / VPS Anda.
2. Login ke akun broker Anda (Exness, XM, IC Markets, dll).
3. PENTING: Pastikan tombol "Algo Trading" di toolbar atas MT5 menyala HIJAU.
   (Jika masih MERAH / tanda larang, klik tombol tersebut atau tekan Ctrl+E di MT5).
4. Jalankan RaptechAutoTrade.exe, lalu:
   - Tekan huruf [P] pada keyboard untuk mengisi Nomor Akun (Login), Password,
     dan Nama Server broker Anda (misal: Exness-Demo atau Exness-Real).
   - Tekan huruf [T] untuk memilih Mode: DEMO atau REAL.


--------------------------------------------------------------------------------
3. ARSITEKTUR DUAL-VIEW (DUA LAYAR) & NAVIGASI
--------------------------------------------------------------------------------
Bot v3.1.0 memiliki 2 tampilan layar yang terpisah rapi:

1. LAYAR 1 (MAIN OVERVIEW & MARKET INTELLIGENCE) - Aktif saat Standby:
   - 4 Kartu Finansial: Saldo, Ekuitas, Margin Health, Floating P/L.
   - Market Radar: Pergerakan harga multi-pair, spread, dan rentang harian.
   - Rekomendasi Pasar Otomatis: Rekomendasi strategi (Breakout, Pinbar, Scalper,
     Hold) berdasarkan indikator tren EMA, volatilitas ATR, dan spread safety.

2. LAYAR 2 (LIVE TRADING EXECUTION DASHBOARD) - Aktif saat Trading Berjalan:
   - Tampilan bersih tanpa distraksi.
   - Circuit Breaker Bar & Drawdown Risk Gauge.
   - Tabel Posisi Terbuka terpisah presisi (Tiket, Simbol, Side, Volume, Profit).
   - Live Activity Log interaktif untuk memantau order & sinyal.

💡 Tekan tombol [V] untuk berpindah bolak-balik antara Layar 1 dan Layar 2
   kapan saja tanpa menghentikan trading!


--------------------------------------------------------------------------------
4. PINTASAN TOMBOL KEYBOARD LENGKAP (HOTKEYS)
--------------------------------------------------------------------------------
[TRADING CONTROLS]
  [S] : Mulai / Stop Trading (Launch Wizard)
        - Pada Layar Standby: Membuka Wizard Ringkasan Sesi Trading untuk
          memilih Mulai [1], Ubah Simbol [2], Ganti Strategi [3], atau Atur Risiko [4].
        - Pada Layar Live: Menghentikan auto-trading dengan aman.
  [V] : Beralih Tampilan (Switch View: Layar Utama <-> Layar Live).
  [C] : Tutup SEMUA Posisi Terbuka (Emergency Close All) dengan konfirmasi [Y/N].
  [X] : Tutup Posisi 1 per 1 (Pilih nomor urut posisi untuk menutup tiket tertentu).
  [M] : Order Manual Cepat (Buka order BUY atau SELL manual dengan proteksi virtual).

[CONFIG CONTROLS]
  [K] : Pilih Pasar / Simbol Trading (XAUUSD, BTCUSD, Forex, atau Custom).
  [E] : Pilih Strategi Trading (Fast Gold Scalper, PA Hybrid, Breakout, dll).
  [R] : Pengaturan Risiko (Lot, Virtual SL/TP, Trailing Stop, Max Daily Loss).
  [P] : Pengaturan Akun & Profil Broker MT5.
  [T] : Ubah Mode Trading (REAL / DEMO / SIMULASI).
  [A] : Scan Ulang Rekomendasi Pasar Otomatis (Market Scanner Refresh).

[SYSTEM CONTROLS]
  [H] : Panduan & Glosarium Fitur Lengkap.
  [L] : Bersihkan Layar Log Aktivitas.
  [Q] : Keluar Aplikasi dengan Aman (Graceful Shutdown).


--------------------------------------------------------------------------------
5. PRESET PASAR & STRATEGI (XAU, BTC, FOREX)
--------------------------------------------------------------------------------
Folder "strategies/market/" dan "data/profiles/" telah dilengkapi preset siap pakai:

A. EMAS / GOLD (XAUUSDm):
   - File Preset : data/profiles/XAU_Gold_Scalper.json & market/xau_gold.json
   - Strategi    : Fast Gold Scalper atau Price Action Hybrid Scalper
   - Timeframe   : M1 / M5
   - Konfigurasi : Lot 0.01 | Virtual SL 150p | Virtual TP 250p | Trailing 80p

B. BITCOIN / CRYPTO (BTCUSDm):
   - File Preset : data/profiles/BTC_Crypto_Scalper.json & market/btc_crypto.json
   - Strategi    : Price Action Momentum Breakout atau PA Hybrid
   - Timeframe   : M5 / M15
   - Konfigurasi : Lot 0.01 | Virtual SL 3000p | Virtual TP 6000p | Trailing 2000p

C. FOREX MAJOR (EURUSDm, GBPUSDm, USDJPYm):
   - File Preset : data/profiles/Forex_Major.json & market/forex_major.json
   - Strategi    : Brutal Cent Scalper atau Price Action Pin Bar Rejection
   - Timeframe   : M1 / M5
   - Konfigurasi : Lot 0.01 | Virtual SL 100p | Virtual TP 150p | Trailing 60p


--------------------------------------------------------------------------------
6. FITUR PROTEKSI MODAL (CAPITAL SAFEGUARDS)
--------------------------------------------------------------------------------
1. Virtual SL/TP (Anti-Stop Hunting):
   Tingkat Stop Loss dan Take Profit dikelola secara lokal di software tanpa
   dikirim ke broker, melindungi posisi Anda dari manipulasi spread broker.
2. Dynamic Trailing Stop:
   Otomatis mengunci profit yang sedang berjalan dan memajukan batas trailing.
3. Daily Drawdown Circuit Breaker:
   Jika kerugian harian mencapai batas (contoh: $50), bot seketika menolak order
   baru untuk menyelamatkan modal Anda dari margin call.
4. Auto-Resize & Zero-Flicker:
   Jendela terminal dapat diperbesar (Maximize / Bigsize) atau diubah ukurannya
   secara bebas tanpa merusak tata letak dan tanpa kedip.


--------------------------------------------------------------------------------
7. PENGATURAN STOP LOSS HARIAN & POSISI MAKSIMAL PER STRATEGI
--------------------------------------------------------------------------------
Nilai "max_daily_loss" (Batas Kerugian Harian dalam USD) dan "max_open_positions"
(Maksimal Posisi Terbuka Simultan) kini diatur langsung secara mandiri di masing-masing
file strategi di dalam folder:
👉 strategies/ (contoh: fast_gold_scalper.py, pa_hybrid.py, brutal_cent_scalper.py)

Cukup buka file strategi dengan Notepad / Text Editor apa saja, Anda bisa langsung mengubah:
  max_daily_loss = 50.0      # Batas Rugi Harian ($ USD)
  max_open_positions = 2     # Batas Order Terbuka Sekaligus
Bot akan otomatis membaca pengaturan dari strategi yang sedang aktif.

================================================================================
             Raptech Automation — Solusi Algoritmik Trading Terpercaya
================================================================================
"""


def build_minimal_customer_pack():
    print("=" * 65)
    print(" Raptech AutoTrade v3.1.0 — Customer Package Builder")
    print("=" * 65)

    if not EXE_PATH.exists():
        print(f"[ERROR] Executable {EXE_PATH} tidak ditemukan! Pastikan sudah dibuild.")
        return False

    # 1. Clean & recreate staging directory
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Copy Executable mandiri
    print("[1/5] Menyalin executable RaptechAutoTrade.exe...")
    shutil.copy2(EXE_PATH, STAGING_DIR / "RaptechAutoTrade.exe")

    # 2b. Buat launcher batch script
    launcher_bat = STAGING_DIR / "1_Mulai_Raptech_AutoTrade.bat"
    launcher_bat.write_text(
        '@echo off\nchcp 65001 >nul\nset "PYTHONIOENCODING=utf-8"\ncd /d "%~dp0"\n'
        '"RaptechAutoTrade.exe"\npause\n',
        encoding="utf-8"
    )

    # 3. Buat penggunaan.txt
    print("[2/5] Menulis file penggunaan.txt...")
    (STAGING_DIR / "penggunaan.txt").write_text(PENGGUNAAN_TXT_CONTENT, encoding="utf-8")

    # 4. Buat folder data/ dan data/profiles/ dengan preset lengkap
    print("[3/5] Menyiapkan folder data/ dan preset profil (XAU, BTC, Forex, Demo, Real)...")
    pack_profiles = STAGING_DIR / "data" / "profiles"
    pack_profiles.mkdir(parents=True, exist_ok=True)

    # Base profile template
    base_profile = {
        "profile_name": "default",
        "backend": "simulation",
        "trading_mode": "simulasi",
        "login": 999999,
        "password": "",
        "server": "Engine Simulasi",
        "path": "",
        "mcp_url": "http://127.0.0.1:8000/mcp",
        "mcp_api_key": "",
        "symbols": ["XAUUSDm", "EURUSDm", "BTCUSDm"],
        "timeframe": "M5",
        "strategy": "pa_hybrid",
        "strategy_params": {},
        "allow_hedging": False,
        "close_on_opposite_signal": True,
        "risk": {
            "fixed_lot": 0.01,
            "risk_percent": 1.0,
            "sizing_mode": "fixed_lot",
            "virtual_sl_points": 200,
            "virtual_tp_points": 400,
            "use_server_sl": False,
            "server_sl_points": 0,
            "trailing_enabled": True,
            "trail_start_points": 150,
            "trail_step_points": 50,
            "max_drawdown_percent": 5.0,
            "min_margin_level": 500.0,
            "max_symbol_exposure_lots": 1.0
        },
        "auto_start": False
    }

    # default.json (Simulasi siap pakai)
    with open(pack_profiles / "default.json", "w", encoding="utf-8") as f:
        json.dump(base_profile, f, indent=2)

    # Akun_Demo.json
    demo_prof = dict(base_profile)
    demo_prof["profile_name"] = "Akun_Demo"
    demo_prof["backend"] = "native"
    demo_prof["trading_mode"] = "demo"
    demo_prof["login"] = 0
    demo_prof["server"] = "Exness-Demo"
    with open(pack_profiles / "Akun_Demo.json", "w", encoding="utf-8") as f:
        json.dump(demo_prof, f, indent=2)

    # Akun_Real.json
    real_prof = dict(base_profile)
    real_prof["profile_name"] = "Akun_Real"
    real_prof["backend"] = "native"
    real_prof["trading_mode"] = "real"
    real_prof["login"] = 0
    real_prof["server"] = "Exness-Real"
    real_prof["risk"] = dict(base_profile["risk"])
    with open(pack_profiles / "Akun_Real.json", "w", encoding="utf-8") as f:
        json.dump(real_prof, f, indent=2)

    # Simulasi_Offline.json
    sim_prof = dict(base_profile)
    sim_prof["profile_name"] = "Simulasi_Offline"
    with open(pack_profiles / "Simulasi_Offline.json", "w", encoding="utf-8") as f:
        json.dump(sim_prof, f, indent=2)

    # XAU_Gold_Scalper.json
    xau_prof = dict(base_profile)
    xau_prof["profile_name"] = "XAU_Gold_Scalper"
    xau_prof["backend"] = "native"
    xau_prof["trading_mode"] = "demo"
    xau_prof["login"] = 0
    xau_prof["server"] = "Exness-Demo"
    xau_prof["symbols"] = ["XAUUSDm", "XAGUSDm"]
    xau_prof["strategy"] = "fast_gold_scalper"
    xau_prof["timeframe"] = "M1"
    xau_prof["risk"] = dict(base_profile["risk"])
    xau_prof["risk"]["virtual_sl_points"] = 150
    xau_prof["risk"]["virtual_tp_points"] = 250
    xau_prof["risk"]["trail_start_points"] = 80
    xau_prof["risk"]["trail_step_points"] = 30
    with open(pack_profiles / "XAU_Gold_Scalper.json", "w", encoding="utf-8") as f:
        json.dump(xau_prof, f, indent=2)

    # BTC_Crypto_Scalper.json
    btc_prof = dict(base_profile)
    btc_prof["profile_name"] = "BTC_Crypto_Scalper"
    btc_prof["backend"] = "native"
    btc_prof["trading_mode"] = "demo"
    btc_prof["login"] = 0
    btc_prof["server"] = "Exness-Demo"
    btc_prof["symbols"] = ["BTCUSDm"]
    btc_prof["strategy"] = "pa_breakout"
    btc_prof["timeframe"] = "M5"
    btc_prof["risk"] = dict(base_profile["risk"])
    btc_prof["risk"]["virtual_sl_points"] = 3000
    btc_prof["risk"]["virtual_tp_points"] = 6000
    btc_prof["risk"]["trail_start_points"] = 2000
    btc_prof["risk"]["trail_step_points"] = 500
    with open(pack_profiles / "BTC_Crypto_Scalper.json", "w", encoding="utf-8") as f:
        json.dump(btc_prof, f, indent=2)

    # Forex_Major.json
    fx_prof = dict(base_profile)
    fx_prof["profile_name"] = "Forex_Major"
    fx_prof["backend"] = "native"
    fx_prof["trading_mode"] = "demo"
    fx_prof["login"] = 0
    fx_prof["server"] = "Exness-Demo"
    fx_prof["symbols"] = ["EURUSDm", "GBPUSDm", "USDJPYm"]
    fx_prof["strategy"] = "brutal_cent_scalper"
    fx_prof["timeframe"] = "M1"
    fx_prof["risk"] = dict(base_profile["risk"])
    fx_prof["risk"]["virtual_sl_points"] = 100
    fx_prof["risk"]["virtual_tp_points"] = 150
    fx_prof["risk"]["trail_start_points"] = 60
    fx_prof["risk"]["trail_step_points"] = 20
    with open(pack_profiles / "Forex_Major.json", "w", encoding="utf-8") as f:
        json.dump(fx_prof, f, indent=2)

    # 5. Salin strategies/ dan siapkan market/ (XAU, BTC, Forex)
    print("[4/5] Menyiapkan modul strategies/ dan market presets (xau, btc, forex)...")
    src_strat = BASE_DIR / "strategies"
    dest_strat = STAGING_DIR / "strategies"
    dest_strat.mkdir(parents=True, exist_ok=True)

    # Salin file strategi python murni (tanpa __pycache__)
    for f in src_strat.glob("*.py"):
        shutil.copy2(f, dest_strat / f.name)

    # Siapkan folder market presets
    market_configs = {
        "xau_gold.json": {
            "market": "XAUUSDm",
            "asset_name": "Gold / Emas (Spot)",
            "supported_symbols": ["XAUUSDm", "XAGUSDm"],
            "recommended_timeframes": ["M1", "M5"],
            "recommended_strategies": [
                "fast_gold_scalper",
                "pa_hybrid",
                "pa_breakout"
            ],
            "default_risk": {
                "fixed_lot": 0.01,
                "virtual_sl_points": 150,
                "virtual_tp_points": 250,
                "trailing_enabled": True,
                "trail_start_points": 80,
                "trail_step_points": 30
            },
            "description": "Preset scalping emas XAUUSD dengan proteksi volatilitas tinggi dan trailing dinamis."
        },
        "btc_crypto.json": {
            "market": "BTCUSDm",
            "asset_name": "Bitcoin / USD",
            "supported_symbols": ["BTCUSDm", "ETHUSDm"],
            "recommended_timeframes": ["M5", "M15"],
            "recommended_strategies": [
                "pa_breakout",
                "pa_hybrid"
            ],
            "default_risk": {
                "fixed_lot": 0.01,
                "virtual_sl_points": 3000,
                "virtual_tp_points": 6000,
                "trailing_enabled": True,
                "trail_start_points": 2000,
                "trail_step_points": 500
            },
            "description": "Preset scalping Bitcoin BTCUSD memanfaatkan momentum breakout dan expansion candle."
        },
        "forex_major.json": {
            "market": "EURUSDm",
            "asset_name": "Forex Major Currencies",
            "supported_symbols": ["EURUSDm", "GBPUSDm", "USDJPYm"],
            "recommended_timeframes": ["M1", "M5"],
            "recommended_strategies": [
                "brutal_cent_scalper",
                "pa_rejection",
                "ma_cross"
            ],
            "default_risk": {
                "fixed_lot": 0.01,
                "virtual_sl_points": 100,
                "virtual_tp_points": 150,
                "trailing_enabled": True,
                "trail_start_points": 60,
                "trail_step_points": 20
            },
            "description": "Preset scalping Forex Major pair dengan spread ketat dan frekuensi entry terjaga."
        }
    }

    # Tulis ke strategies/market/
    strat_market_dir = dest_strat / "market"
    strat_market_dir.mkdir(parents=True, exist_ok=True)
    for fname, cfg in market_configs.items():
        with open(strat_market_dir / fname, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    # Tulis juga ke folder market/ di root staging
    root_market_dir = STAGING_DIR / "market"
    root_market_dir.mkdir(parents=True, exist_ok=True)
    for fname, cfg in market_configs.items():
        with open(root_market_dir / fname, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    # 6. Kompresi menjadi file ZIP langsung di folder release/
    print("[5/5] Mengompresi paket distribusi menjadi file ZIP di folder release/...")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()

    # Isi file ZIP langsung di root archive
    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(STAGING_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(STAGING_DIR)
                zf.write(file_path, arcname)

    size_mb = ZIP_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"[OK] ZIP Release Berhasil Dibuat: {ZIP_OUTPUT} ({size_mb:.1f} MB)")

    print("\n" + "=" * 65)
    print(" BUILD & PACKAGING SELESAI DENGAN SUKSES!")
    print(f" Isi ZIP Bersih:")
    print("  - RaptechAutoTrade.exe")
    print("  - 1_Mulai_Raptech_AutoTrade.bat")
    print("  - penggunaan.txt")
    print("  - data/profiles (default, Akun_Demo, Akun_Real, XAU, BTC, Forex)")
    print("  - strategies/ (fast_gold_scalper, pa_hybrid, breakout, dll)")
    print("  - strategies/market/ & market/ (xau_gold, btc_crypto, forex_major)")
    print(f" Lokasi File ZIP: {ZIP_OUTPUT.resolve()}")
    print("=" * 65)
    return True


if __name__ == "__main__":
    build_minimal_customer_pack()
