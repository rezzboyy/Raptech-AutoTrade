# 🤖 Raptech MT5 Bot — PRODUCTION DOCUMENT

> **Diperbarui:** 2026-09-09 | **Versi:** 1.0.0-production | **Status:** ✅ Siap Produksi

---

## 📋 Ringkasan Proyek

**Raptech MT5 Bot** adalah aplikasi trading otomatis untuk platform MetaTrader 5 (MT5) berbasis Python dengan antarmuka grafis (GUI) menggunakan PySide6 + QML. Aplikasi dapat dijalankan dalam dua mode:

| Mode | Entry Point | Keterangan |
|------|-------------|------------|
| **GUI** | `app.py` | Antarmuka lengkap dengan chart, posisi, login panel |
| **CLI / Headless** | `main.py` | Loop trading tanpa UI, cocok untuk server |

---

## 🗂️ Struktur Proyek

```
Bot Trading  MT5Raptech/
├── app.py                      # Entry point GUI (PySide6 + QML)
├── main.py                     # Entry point CLI/headless
├── requirements.txt            # Dependensi Python
├── build.ps1                   # Build script PowerShell → EXE
├── raptech_bot.spec            # Konfigurasi PyInstaller
├── .env.example                # Template konfigurasi environment
├── config.json                 # (runtime) Konfigurasi trading tersimpan
│
├── config/
│   └── settings.py             # Settings terpusat (env + runtime)
│
├── src/
│   ├── controller.py           # BotController — jembatan QML ↔ Python
│   ├── bot_engine.py           # Engine MT5: operasi granular (connect, poll, trade)
│   ├── connection.py           # MT5Connection: init & symbol select
│   ├── market_data.py          # Ambil candle (get_rates) & tick (get_tick)
│   ├── order_manager.py        # open_position / close_position
│   ├── risk_manager.py         # calculate_lot + can_open_new_position
│   ├── config_store.py         # Simpan/muat config.json (parameter trading)
│   ├── credential_store.py     # Profil login JSON di folder profiles/
│   ├── strategy_loader.py      # Discovery + factory strategi dari folder
│   └── logger.py               # Logger terpusat (mt5bot)
│
├── strategies/
│   ├── base.py                 # Interface Strategy + registry @register
│   ├── ma_cross.py             # Strategi MA Crossover (2 SMA)
│   └── rsi.py                  # Strategi RSI Oversold/Overbought
│
├── ui/
│   ├── assets/                 # Ikon SVG (18 ikon line-style) + icon.ico
│   └── qml/
│       ├── main.qml            # Window utama (2-kolom layout)
│       ├── Theme.qml           # Singleton tema warna soft-dark
│       ├── qmldir              # Deklarasi modul QML
│       └── components/
│           ├── AccountBar.qml  # Chip info akun di header
│           ├── LoginPanel.qml  # Form login + profil kredensial
│           ├── ConfigPanel.qml # Pengaturan trading + parameter strategi dinamis
│           ├── CandleChart.qml # Candlestick chart berbasis Canvas
│           ├── PositionsPanel.qml # Tabel posisi terbuka + tutup manual
│           ├── LogPanel.qml    # Panel log (collapsible)
│           ├── CCombo.qml      # Komponen ComboBox kustom
│           └── CField.qml      # Komponen TextField kustom
│
├── tools/
│   └── make_icon.py            # Generator ikon .ico dari SVG
│
├── profiles/                   # (runtime, .gitignore) Profil kredensial JSON
├── logs/                       # (runtime) File log harian
├── dist/                       # (build output) EXE standalone
└── build/                      # (build temp) Artefak PyInstaller
```

---

## ⚙️ Arsitektur Sistem

```
┌─────────────────────────────────────────────────────┐
│                    QML UI Layer                      │
│  main.qml → LoginPanel | ConfigPanel | CandleChart  │
│             PositionsPanel | LogPanel | AccountBar   │
└────────────────────┬────────────────────────────────┘
                     │ signals/slots (Qt)
┌────────────────────▼────────────────────────────────┐
│              BotController (Main Thread)             │
│  - Properti Qt: connected, trading, balance, dll.   │
│  - Slot: connectBot, disconnectBot, setTrading,     │
│    saveConfig, loginAndConnect, listProfiles, dll.   │
│  - Queue thread-safe untuk tutup posisi             │
└────────────────────┬────────────────────────────────┘
                     │ QThread (1 thread tunggal)
┌────────────────────▼────────────────────────────────┐
│            _Worker + BotEngine (Worker Thread)       │
│  Loop 1 detik:                                       │
│  1. poll_account()    → accountUpdated signal        │
│  2. poll_positions()  → positionsUpdated signal      │
│  3. poll_candles()    → candlesUpdated signal (5dtk) │
│  4. _drain_close_queue()  → close_ticket()           │
│  5. process_trading_step() [bila trading=True]       │
│       → get_rates() → strategy.generate_signal()    │
│       → calculate_lot() → open_position()            │
└────────────────────┬────────────────────────────────┘
                     │ MetaTrader5 Python API
┌────────────────────▼────────────────────────────────┐
│              MetaTrader 5 Terminal (Windows)         │
└─────────────────────────────────────────────────────┘
```

### Prinsip Thread-Safety
- **Semua panggilan MT5 terjadi di satu worker thread** — tidak ada race condition.
- QML memanggil slot di main thread; permintaan tutup posisi diantrikan via `queue.Queue`.
- Worker mengirim data ke UI lewat **Qt signals** (queued connection antar-thread otomatis aman).

---

## 🔌 Dependensi

| Paket | Versi Min | Fungsi |
|-------|-----------|--------|
| `MetaTrader5` | ≥ 5.0.45 | Koneksi & API MT5 |
| `pandas` | ≥ 2.0.0 | Pengolahan data candle (DataFrame) |
| `numpy` | ≥ 1.24.0 | Kalkulasi numerik |
| `python-dotenv` | ≥ 1.0.0 | Baca file `.env` |
| `PySide6` | ≥ 6.6.0 | GUI Qt (QML, QThread, Signals/Slots) |
| `PyInstaller` | (build only) | Bundling ke EXE |
| `Pillow` | (build only) | Generate ikon `.ico` |

> **Python:** 3.10+ disarankan (diuji pada 3.11/3.12). MT5 hanya tersedia di **Windows**.

---

## ⚙️ Konfigurasi

### 1. File `.env` (Kredensial)

Salin `.env.example` ke `.env`, lalu isi:

```env
MT5_LOGIN=123456
MT5_PASSWORD=password
MT5_SERVER=BrokerName-Live
MT5_PATH=

SYMBOL=EURUSDm
TIMEFRAME=M5
MAGIC_NUMBER=100200
RISK_PER_TRADE=0.01
MAX_OPEN_POSITIONS=1
STRATEGY=ma_cross
LOOP_INTERVAL=15
```

> ⚠️ Jangan commit `.env` — sudah masuk `.gitignore`.

### 2. File `config.json` (Parameter Trading — Runtime)

Dibuat otomatis saat user klik **Simpan** di panel Config. Berisi semua parameter trading (bukan kredensial).

```json
{
  "symbol": "EURUSDm",
  "timeframe_str": "M5",
  "magic_number": 100200,
  "risk_per_trade": 0.01,
  "max_open_positions": 1,
  "strategy_name": "ma_cross",
  "strategy_params": { "fast_period": 10, "slow_period": 30 },
  "loop_interval": 15
}
```

### 3. Profil Kredensial (`profiles/*.json` — Runtime)

Disimpan otomatis setelah login sukses. Password di-obfuscate base64 (bukan enkripsi—jangan dibagikan).

---

## 📈 Strategi Trading

### Sistem Plugin Strategi

| Langkah | Detail |
|---------|--------|
| Subclass `Strategy` | Dari `strategies/base.py` |
| Dekorasi `@register` | Auto-daftarkan ke registry global |
| Definisi `PARAMS` | Skema untuk form UI dinamis |
| `generate_signal(df)` | Return `SIGNAL_BUY` / `SIGNAL_SELL` / `None` |

### Strategi Tersedia

| Nama | `name` | Parameter Default |
|------|--------|-------------------|
| MA Crossover | `ma_cross` | fast=10, slow=30 |
| RSI Oversold/Overbought | `rsi` | period=14, oversold=30, overbought=70 |

### Menambah Strategi Baru

```python
# strategies/nama_baru.py
from strategies.base import Strategy, register, SIGNAL_BUY, SIGNAL_SELL
import pandas as pd

@register
class StrategiBaru(Strategy):
    name = "nama_baru"
    display_name = "Nama di UI"
    PARAMS = [
        {"key": "param1", "label": "Label", "type": "int", "default": 20, "min": 1},
    ]

    def generate_signal(self, df: pd.DataFrame):
        # Logika sinyal...
        return None
```

Strategi baru **langsung muncul di dropdown UI** tanpa perubahan kode lain.

---

## 🏗️ Build EXE (Production)

### Prasyarat

```powershell
pip install -r requirements.txt
pip install pyinstaller pillow
```

### Jalankan Build

```powershell
.\build.ps1
```

Build script:
1. Hapus folder `build/` dan `dist/` lama
2. Generate `ui/assets/icon.ico` via `tools/make_icon.py`
3. Jalankan `pyinstaller raptech_bot.spec --noconfirm`

### Output

```
dist/
└── RaptechMT5Bot/
    ├── RaptechMT5Bot.exe   (~498 MB termasuk PySide6 + Qt runtime)
    ├── ui/                 (QML + SVG ter-bundle)
    └── ...
```

### Deploy ke Mesin Lain

1. Salin seluruh folder `dist/RaptechMT5Bot/` ke mesin target.
2. Buat file `.env` berisi kredensial di folder yang sama dengan EXE.
3. Pastikan **MetaTrader 5 terminal** sudah terinstal di mesin target.
4. Jalankan `RaptechMT5Bot.exe`.

> 💡 EXE tidak butuh Python di mesin target, namun **MT5 terminal harus ada**.

---

## 🔒 Catatan Keamanan

| Aspek | Status | Catatan |
|-------|--------|---------|
| File `.env` | ✅ .gitignore | Tidak pernah di-commit |
| Folder `profiles/` | ✅ .gitignore | Profil JSON tidak di-commit |
| Password di profil | ⚠️ Base64 | Hanya obfuscation, BUKAN enkripsi |
| Enkripsi master password | ❌ Belum ada | Rekomendasi: `keyring` atau AES |

---

## 🧩 Komponen UI (QML)

| Komponen | Fungsi |
|----------|--------|
| `AccountBar` | Chip info akun di header (Balance, Equity, Margin, Profit) |
| `LoginPanel` | Form login + manajemen profil tersimpan + FileDialog |
| `ConfigPanel` | Pengaturan simbol, TF, risiko + form parameter strategi dinamis |
| `CandleChart` | Candlestick chart Canvas + selektor simbol + info OHLC |
| `PositionsPanel` | Tabel posisi terbuka + tombol tutup manual per ticket |
| `LogPanel` | Scroll area log real-time (collapsible) |

### Tema Warna (Theme.qml — Soft Dark)

| Token | Nilai | Deskripsi |
|-------|-------|-----------|
| `bg` | `#181b24` | Background utama |
| `panel` | `#222834` | Latar panel |
| `text` | `#dce1ea` | Teks off-white |
| `accent` | `#5bb98c` | Hijau lembut (aksen) |
| `colorUp` | `#5bc48e` | Candle naik |
| `colorDown` | `#e2707a` | Candle turun |

---

## 🔄 Manajemen Risiko

Kalkulasi lot otomatis:

```
risiko_uang  = balance × risk_per_trade
ticks        = jarak_SL / tick_size
loss_per_lot = ticks × tick_value
lot          = risiko_uang / loss_per_lot
```

Lot dibulatkan ke `volume_step` broker dan dibatasi antara `volume_min` dan `volume_max`.

> ⚠️ **SL/TP saat ini hardcoded:** 300 points SL, 600 points TP di `bot_engine.py`.
> Sesuaikan dengan instrumen dan strategi yang dipakai sebelum deploy ke akun live.

---

## 📊 Monitoring Real-time

| Data | Interval | Sumber MT5 |
|------|----------|------------|
| Info Akun | 1 detik | `mt5.account_info()` |
| Posisi Terbuka | 1 detik | `mt5.positions_get()` |
| Candlestick Chart | 5 detik | `mt5.copy_rates_from_pos()` |
| Daftar Simbol | Sekali saat connect | `mt5.symbols_get()` |

---

## 🚀 Cara Menjalankan

### Mode GUI (Development)

```powershell
pip install -r requirements.txt
python app.py
```

### Mode CLI/Headless

```powershell
# Buat .env terlebih dahulu
python main.py
```

### Mode EXE (Production)

```powershell
.\build.ps1
dist\RaptechMT5Bot\RaptechMT5Bot.exe
```

---

## 🐛 Troubleshooting

| Masalah | Penyebab | Solusi |
|---------|----------|--------|
| Gagal connect ke MT5 | Terminal tidak berjalan | Buka MT5 terminal terlebih dahulu |
| Gagal connect ke MT5 | Path terminal salah | Isi kolom Path di UI atau `MT5_PATH` di .env |
| QML tidak termuat | Folder `ui/` tidak ada | Pastikan `ui/` ada di samping `app.py` |
| EXE crash saat start | `.env` tidak ditemukan | Letakkan `.env` di folder yang sama dengan EXE |
| Lot = 0, order dibatalkan | SL terlalu dekat | Periksa `SL_POINTS` di `bot_engine.py` |
| Strategi tidak muncul | Modul belum di-import | Cek `strategies/__init__.py` sudah import file strategi |

---

## 📝 Logging

- **File log:** folder `logs/`
- **Panel log UI:** real-time, menampilkan INFO ke atas
- **Format:** `HH:MM:SS | LEVEL | pesan`

---

## 🗓️ Riwayat Pengembangan

| Fase | Deskripsi | Status |
|------|-----------|--------|
| Fondasi UI & Integrasi | Window QML, Start/Stop, log real-time | ✅ |
| Panel Fitur Lengkap | Config, tabel posisi, info akun, tutup manual | ✅ |
| Packaging EXE | PyInstaller, ikon, build.ps1, ~498 MB | ✅ |
| Sistem Strategi Plugin | `strategies/`, registry, loader dinamis | ✅ |
| Sistem Profil Kredensial | JSON profiles, auto-save, FileDialog | ✅ |
| Form Login di UI | LoginPanel, dropdown, delete profil | ✅ |
| Pemilihan Strategi di UI | Dropdown + form parameter dinamis | ✅ |
| Ikon SVG + Rebuild EXE | 18 ikon line-style, bundling qsvg.dll | ✅ |
| Layout 2-Kolom + Chart | Modular QML, CandleChart Canvas | ✅ |
| Tema Warna Soft Dark | Theme.qml singleton, Material style | ✅ |

---

*Dokumen ini dihasilkan dari analisis kode sumber proyek pada 2026-09-09.*
