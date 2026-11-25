# XAVIQ Trading Engine (C++ / Qt 6)

Bot trading MetaTrader 5 (MT5) berperforma tinggi berbasis **C++ & Qt 6.8.1 (MinGW)**.
Ringan (RAM ~45–70 MB), responsif, backend **MCP-only** (kebal masalah versi terminal MT5),
dan Mode Programmer bertenaga **JavaScript (QJSEngine)**.

> ⚠️ **Peringatan risiko:** Trading otomatis berisiko kehilangan dana. Selalu uji di
> **akun demo** terlebih dahulu dengan lot kecil (0.01).

---

## Cara Menjalankan C++ (Sangat Mudah)

Di folder root tersedia berkas `.bat` praktis (cukup dobel-klik):

1. **`run_cpp_dev.bat`**: Build otomatis & jalankan GUI XAVIQ C++ mode DEV.
2. **`run_cpp_tests.bat`**: Jalankan seluruh 7 unit test suite C++ (QtTest/ctest).
3. **`deploy_cpp.bat`**: Buat rilis mandiri (standalone ~94 MB) di `C:\XaviqCppDist\XAVIQTradingEngine\`.

---

## Arsip Kode Python (Legacy)

Implementasi referensi versi Python lama disimpan rapi di folder [`legacy_python/`](legacy_python/).
Untuk menjalankan 264 unit test Python:
```bash
legacy_python\run_tests.bat
```

Alur pemakaian di panel:
1. **Connect** — terhubung ke MT5 dan mulai monitoring (info akun & posisi tampil real-time).
2. Atur parameter di panel **Konfigurasi**, klik **Simpan Konfigurasi** (tersimpan ke `config.json`).
3. Aktifkan **Auto Trading** untuk mulai eksekusi order otomatis sesuai strategi.
4. Posisi terbuka bisa ditutup manual lewat tombol **Tutup** di tabel.
5. **Disconnect** untuk menghentikan.

> Dua state terpisah: **Connected** (monitoring saja) dan **Auto Trading** (eksekusi order).
> Anda bisa memantau akun tanpa mengaktifkan trading otomatis.

**Mode CLI (headless, tanpa UI):**

```bash
python main.py
```

Hentikan dengan `Ctrl+C`.

### Catatan arsitektur (thread-safety)

Library `MetaTrader5` tidak thread-safe, jadi **semua panggilan MT5 dijalankan di satu
worker thread**. UI berkomunikasi dengan worker lewat sinyal Qt; permintaan tutup posisi
dari UI diantrikan (thread-safe queue) dan dieksekusi oleh worker.

## Struktur Proyek

```
.
├── app.py                  # entry point GUI (PySide6 + QML)
├── main.py                 # runner CLI/headless
├── config/
│   └── settings.py         # konfigurasi dari .env
├── src/
│   ├── logger.py            # logging ke console + file (rotasi)
│   ├── connection.py        # koneksi/login terminal MT5 (native)
│   ├── market_data.py       # ambil candle & tick (native)
│   ├── order_manager.py     # buka/tutup posisi (native)
│   ├── risk_manager.py      # hitung lot & kontrol posisi (native)
│   ├── strategy_loader.py   # penemu & pembuat strategi (plugin)
│   ├── credential_store.py  # profil login JSON (terenkripsi)
│   ├── mcp_profile_store.py # profil koneksi MCP (terenkripsi)
│   ├── secure_store.py      # enkripsi rahasia at-rest (Fernet/AES)
│   ├── mcp_client.py        # klien MCP (HTTP/JSON-RPC ke terminal)
│   ├── trade_rules.py       # aturan trading backend-agnostik
│   ├── config_store.py      # simpan/muat + validasi config.json
│   ├── bot_engine.py        # operasi tingkat tinggi (pakai backend)
│   ├── controller.py        # jembatan QML <-> bot (worker thread)
│   └── backends/            # abstraksi backend koneksi MT5
│       ├── base.py          # antarmuka TradingBackend + util
│       ├── native_backend.py# backend library MetaTrader5
│       └── mcp_backend.py    # backend server MCP (kebal versi)
├── strategies/              # paket strategi (plugin)
│   ├── base.py              # interface + registry + skema parameter
│   ├── ma_cross.py, rsi.py, bollinger.py, macd.py,
│   ├── stochastic.py, multi_indicator.py
│   └── script_runtime.py    # runtime skrip kustom (Mode Programmer, sandbox)
├── tools/                   # utilitas & diagnostik (dijalankan dari root)
│   ├── make_icon.py         # generator ikon (dari icon.ico sumber)
│   ├── CekVersi.py/.bat     # cek kecocokan versi terminal MT5 vs paket Python
│   └── verify_mcp.py        # verifikasi read-only koneksi backend MCP
├── ui/
│   ├── qml/                 # main.qml + components/ (panel modular)
│   └── assets/              # ikon .ico/.png + aset .svg
├── docs/                    # dokumentasi tambahan (MCP, produksi)
└── tests/                   # unit & property tests
```

> **Backend koneksi:** bot mendukung dua backend — **native** (library
> `MetaTrader5`) dan **MCP** (server bawaan terminal, kebal masalah versi
> library). Lihat `docs/MCP_BACKEND.md` untuk mengaktifkan MCP.

## Build ke EXE

Bot bisa dibungkus jadi aplikasi Windows standalone dengan PyInstaller.

```bash
pip install -r requirements.txt   # termasuk pyinstaller & pillow
.\build.ps1
```

Hasil: `dist\RaptechMT5Bot\RaptechMT5Bot.exe` (mode onedir).

Untuk menjalankan hasil build:
1. Salin file `.env` (berisi kredensial) ke folder `dist\RaptechMT5Bot\` di samping EXE.
2. Jalankan `RaptechMT5Bot.exe`.

Catatan:
- Mode **onedir** dipakai (folder berisi EXE + dependensi) karena paling andal untuk
  aplikasi PySide6/QML. Untuk distribusi, zip seluruh folder `RaptechMT5Bot`.
- Library berat yang tidak dipakai (torch, scipy, dll.) dikecualikan di `raptech_bot.spec`
  agar ukuran tetap wajar.
- Terminal **MetaTrader 5** tetap harus terpasang di mesin target — library `MetaTrader5`
  berkomunikasi dengan terminal, bukan menggantikannya.
- **Uji di akun demo** dulu, dan idealnya uji EXE di mesin bersih sebelum distribusi.

## Membuat Strategi Sendiri (Sistem Plugin)

Strategi kini berbasis folder `strategies/`. Untuk menambah strategi baru:

1. Buat file baru, mis. `strategies/my_strategy.py`.
2. Subclass `Strategy`, beri `name`, `display_name`, `PARAMS`, dan implementasikan
   `generate_signal(df)` (kembalikan `"BUY"`, `"SELL"`, atau `None`).
3. Tambahkan dekorator `@register`.

```python
from strategies.base import Strategy, register, SIGNAL_BUY, SIGNAL_SELL

@register
class MyStrategy(Strategy):
    name = "my_strat"
    display_name = "Strategi Saya"
    PARAMS = [
        {"key": "period", "label": "Periode", "type": "int", "default": 14, "min": 1},
    ]
    def generate_signal(self, df):
        # gunakan self.period ...
        return None
```

Strategi otomatis muncul di dropdown UI beserta form parameternya. Untuk build EXE,
tambahkan import file baru ke `strategies/__init__.py` agar ikut ter-bundle.

## Profil Login (Kredensial)

Bot punya form login. Setelah login sukses, kredensial otomatis disimpan sebagai
profil JSON di folder `profiles/` sehingga bisa dipakai lagi tanpa mengetik ulang:

- **Muat** profil dari dropdown, atau **Pilih File...** untuk memuat file profil.
- Password diisi otomatis dari profil (kolom password boleh dikosongkan).

> ⚠️ **Keamanan:** password profil kini **dienkripsi** (Fernet/AES via
> `src/secure_store.py`), tidak lagi base64. Kunci disimpan lokal di `.secret_key`
> (atau turunan `MASTER_PASSWORD` bila diset). Folder `profiles/`, `mcp_profiles/`,
> `.secret_key`, dan `mcp_secret.json` sudah masuk `.gitignore` — jangan dibagikan.

## Sudah Tersedia

- Backend MCP (kebal versi library) + native, sakelar dari UI.
- Trailing stop, break-even, drawdown harian, batas trade/hari.
- Multi-simbol, banyak strategi (MA, RSI, Bollinger, MACD, Stochastic, multi-indikator).
- Order manual & pending (limit/stop), tutup semua posisi.
- Enkripsi kredensial (Fernet/AES), profil login & MCP (pilih file).
- Badge Demo/Real + indikator koneksi broker.

## Langkah Pengembangan Berikutnya

- Backtesting sebelum live (memakai tester MCP bawaan).
- Notifikasi (Telegram/email).
- Filter sesi/jam trading.
```
