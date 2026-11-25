# XAVIQ Trading Engine — Versi C++ (Qt 6)

Port lengkap bot trading MT5 dari Python/PySide6 ke **C++/Qt 6** agar ringan
(RAM kecil, startup cepat, EXE mandiri). Backend **MCP-only**; bahasa skrip Mode
Programmer = **JavaScript (QJSEngine)**.

## Prasyarat (toolchain, tanpa Visual Studio)
- Qt **6.8.1** (kit `win64_mingw`) di `C:\Qt\6.8.1\mingw_64`
- MinGW g++ **13.1.0** (`C:\Qt\Tools\mingw1310_64`)
- CMake **3.30.5** (`C:\Qt\Tools\CMake_64`), Ninja (`C:\Qt\Tools\Ninja`)

## ⚠️ Aturan build penting
`qmlimportscanner` Qt GAGAL bila path build mengandung spasi (folder "Bot Trading").
Solusi: source diedit di `Bot Trading\cpp\`, tapi **BUILD lewat junction tanpa spasi**:

```
cmd /c mklink /J C:\XaviqCpp "C:\Users\Administrator\Desktop\Bot Trading\cpp"
```

## Perintah
```
# Build (Ninja + MinGW, Release)
powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1

# Unit test (QtTest via ctest) — 7 suite
powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\runtests.ps1

# Smoke test QML offscreen (muat UI, keluar 0)
powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\smoke.ps1

# Paketkan rilis mandiri (windeployqt) -> C:\XaviqCppDist\XAVIQTradingEngine\
powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\deploy.ps1

# Verifikasi rilis mandiri (PATH terbatas, tanpa Qt bin)
powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\verify_dist.ps1
```

## Arsitektur (`cpp/src/`)
```
core/        Logger, Settings, ConfigStore, SecureStore
net/         McpClient (JSON-RPC 2.0 via HTTP, SSE, sesi, auth Bearer)
backend/     Models, SymbolUtils, McpParse, TradingBackend (interface), McpBackend
indicators/  Indicators (22 indikator; hasil dicocokkan dgn versi Python 1e-6)
strategy/    Strategy + Command + 5 strategi bawaan (ma_cross/rsi/bollinger/macd/multi)
engine/      TradeRules (risiko/lot/proteksi), BotEngine (loop, SL/TP, virtual, eksekusi)
script/      ScriptContext (ctx), ScriptStrategy (QJSEngine + sandbox + watchdog)
app/         Worker (QThread loop), BotController (Q_PROPERTY/slot/sinyal ke QML)
ui/          JsHighlighter (QSyntaxHighlighter JS untuk editor)
main.cpp     entry: register `bot`, QML, mode --smoke
qml/         UI (main + AccountBar/Login/Manual/Programmer/Stats/Positions/Chart/Log/Journal)
```

**Thread-safety:** semua panggilan MCP terjadi di SATU worker thread (`Worker` di
`QThread`). QML memanggil slot di main thread; perintah manual diantrikan (QMutex) ke
worker; worker mengirim data ke UI via sinyal queued.

## Mode Programmer
Kontrak: `SETTINGS` (opsional), `PARAMS` (opsional),
`function on_bar(ctx)`. `ctx` menyediakan data harga, indikator, akun/posisi, dan
perintah `buy/sell/close_position/close_all/modify`. Sandbox QJSEngine (tanpa akses
file/OS) + watchdog anti loop tak terbatas.

## Checklist paritas fitur vs versi Python
| Fitur | Python | C++ | Catatan |
|---|---|---|---|
| Backend MCP (connect, akun, simbol, chart, posisi, histori) | ✅ | ✅ | `McpBackend` |
| Backend native (library MetaTrader5) | ✅ | ❌ | sengaja ditinggalkan (MCP-only) |
| 22 indikator | ✅ | ✅ | dicocokkan 1e-6 (test_indicators) |
| 5 strategi bawaan | ✅ | ✅ | ma_cross/rsi/bollinger/macd/multi |
| Strategi stochastic (file terpisah) | ❌ | ❌ | tak ada di Python |
| Manajemen risiko/proteksi (DD, equity stop, spread, exposure, loss beruntun) | ✅ | ✅ | `TradeRules` |
| SL/TP points & percent + proteksi min-stop | ✅ | ✅ | `BotEngine::computeSlTp` |
| Trailing / Break-Even / Virtual SL/TP | ✅ | ✅ | broker & virtual |
| Order manual + pending + close all | ✅ | ✅ | via antrian worker |
| Mode Programmer (skrip) | Python (sandbox AST) | JavaScript (QJSEngine) | skrip lama DITULIS ULANG ke JS |
| Editor Pro (highlight, nomor baris, error real-time) | ✅ | ✅ | `JsHighlighter` |
| Panel Bantuan API + Sisipkan | ✅ | ✅ | `apiReference()` |
| Jurnal aksi + ekspor CSV | ✅ | ✅ | `exportJournalCsv` |
| Statistik + chart candle | ✅ | ✅ | StatsPanel / ChartPanel |
| UI tab (Login/Manual/Programmer/Statistik/Jurnal) | ✅ | ✅ | UI baru, ramping |
| Profil kredensial/MCP dari file (simpan/muat terenkripsi) | ✅ | ⏳ | belum di-port (SecureStore siap) |
| Packaging EXE + ikon | ✅ | ✅ | windeployqt + app.rc |

## Status audit otomatis
- Build: OK (Ninja/MinGW, Release).
- Unit test: **7/7 PASS** (test_core, test_mcp, test_backend, test_indicators,
  test_engine, test_script, test_controller).
- Smoke QML offscreen: **exit 0** (tanpa error QML).
- Rilis mandiri: **exit 0** dengan PATH terbatas (self-contained).

## Uji end-to-end DEMO (manual — butuh MT5 Exness aktif)
Belum dapat diotomatiskan di sini (perlu terminal MT5 login broker). Langkah manual:
1. Jalankan `XAVIQTradingEngine.exe`, tab Login → isi endpoint + API Key MCP → Connect.
2. Pastikan akun DEMO, lot kecil (0.01). Cek AccountBar (balance/equity/broker OK).
3. Tab Manual → BUY/SELL kecil → cek Posisi Terbuka & tombol Tutup.
4. Tab Programmer → Muat Template → Validasi → Simpan → Start Trading → amati Jurnal.
5. Cek chart candle & Statistik.

## Sisa pekerjaan (opsional)
- Port store profil kredensial/MCP (enkripsi Fernet/AES) + slot UI terkait.
- Installer (NSIS/Inno) + kompres (UPX).
- Paritas visual penuh dengan UI Python (komponen tambahan).
