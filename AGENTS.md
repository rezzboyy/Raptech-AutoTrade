# AGENTS.md — Aturan & Konteks Proyek (XAVIQ Trading Engine)

> File ini adalah panduan untuk **asisten AI** yang bekerja di proyek ini.
> Baca dari atas ke bawah sebelum mengerjakan apa pun. Tujuannya: AI lain bisa
> langsung bekerja dengan gaya, konvensi, dan kehati-hatian yang sama.

---

## 1. Ringkasan Proyek

**XAVIQ Trading Engine** = bot trading MetaTrader 5 (MT5).
- **Mesin Utama (C++ / Qt 6.8.1)** di folder `cpp/`: GUI desktop C++ native, ringan (~45 MB RAM),
  backend **MCP-only** (kebal versi MT5), Mode Programmer JavaScript (`QJSEngine`), standalone EXE (~94 MB).
- **Arsip Python (PySide6)** di folder `legacy_python/`: implementasi referensi original (264 unit tests).
- Fitur utama: auto-trading (strategi bawaan + **Mode Programmer**/skrip kustom JS),
  order manual & pending, manajemen risiko & proteksi, chart candle & equity, statistik, jurnal aksi.

Lingkungan: **Windows Server/VPS**, akun **Exness** (MT5), akun uji = DEMO.

---

## 2. Aturan Interaksi (WAJIB)

1. **Balas dalam Bahasa Indonesia** (santai, to the point). Istilah teknis boleh Inggris.
2. **Kerjakan bertahap**: tiap tahap diakhiri **audit** (test + smoke),
   antar tahap harus nyambung, prinsip **fail-safe**, jangan rusak fitur yang sudah jalan.
3. **Selalu audit setiap perubahan**: jalankan `run_cpp_tests.bat` + smoke test C++ QML. Jangan
   menyatakan "selesai" tanpa bukti test lolos.
4. **Jujur**: kalau belum diverifikasi, katakan. Jangan mengklaim yang belum dicek.
5. **Koreksi bila user keliru** (mis. salah paham fitur), dengan sopan dan berbasis fakta.
6. **Bersihkan file sementara** (skrip diagnostik/probe/smoke) setelah dipakai.
7. **Jangan echo nilai rahasia** (API key, password) di jawaban. Rujuk lewat nama.
8. User sering minta gaya "pelan-pelan" untuk hal setup → beri langkah bernomor sederhana.

---

## 3. Lingkungan & Perintah Cepat (Root Batches)

- Shell: PowerShell/cmd di Windows.
- **Build & Jalankan GUI C++ (DEV):** dobel-klik `run_cpp_dev.bat` (atau `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1`).
- **Jalankan 7 Test Suite C++:** dobel-klik `run_cpp_tests.bat` (atau `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\runtests.ps1`).
- **Smoke UI C++ (Offscreen):** `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\smoke.ps1` (offscreen, mode `--smoke`).
- **Deploy Standalone C++:** `deploy_cpp.bat` (menghasilkan folder mandiri di `C:\XaviqCppDist\XAVIQTradingEngine\` dan verifikasi di PATH terisolasi).
- **Uji Arsip Python (Legacy):** `legacy_python\run_tests.bat` (264 tests).

⚠️ **PENTING (Aturan Junction C++):**
`qmlimportscanner` Qt GAGAL bila path build mengandung spasi (folder "Bot Trading").
Source code diedit di `Bot Trading\cpp\`, namun BUILD selalu dilakukan via junction tanpa spasi:
`C:\XaviqCpp` (sudah tertaut ke folder `cpp`).

---

## 4. Arsitektur & Struktur Direktori

```
run_cpp_dev.bat           # 1-Klik: Build dev + jalankan GUI C++
run_cpp_tests.bat         # 1-Klik: Jalankan 7 unit test suite C++ (QtTest)
deploy_cpp.bat            # 1-Klik: Paketkan rilis mandiri C++ (windeployqt)
cpp/                      # Sumber C++ (Qt 6.8.1 / MinGW 64-bit)
  CMakeLists.txt          # CMake project (target: xaviq_core, xaviq)
  resources.qrc           # Bundle QML & assets langsung ke biner
  src/
    core/                 # Logger, Settings, ConfigStore, SecureStore
    net/                  # McpClient (HTTP JSON-RPC 2.0, SSE, session tracking)
    backend/              # Models, SymbolUtils, McpParse, TradingBackend, McpBackend
    indicators/           # 22 Indikator matematis murni (akurasi 1e-6 vs Python)
    strategy/             # Strategy base & built-in: ma_cross, rsi, bollinger, macd, multi, stochastic
    engine/               # TradeRules (sizing/gates) & BotEngine (trading loop, virtual SL/TP)
    script/               # ScriptContext (ctx JS) & ScriptStrategy (QJSEngine sandbox)
    app/                  # Worker (QThread single loop) & BotController (QObject QML bridge)
    ui/                   # JsHighlighter (QSyntaxHighlighter native C++)
    main.cpp              # Entry point C++
  qml/                    # UI QML native C++
  scripts/                # Contoh skrip JavaScript Mode Programmer (.js)
docs/                     # Dokumentasi trading, script, MCP, proteksi
legacy_python/            # Arsip referensi kode Python (PySide6)
  app.py / main.py        # Entry GUI / CLI Python lama
  src/ , ui/ , strategies/
  tests/                  # 264 unit tests pytest
```

**Thread-safety:** SEMUA panggilan MT5/MCP terjadi di **satu worker thread** (`Worker` di `QThread`).
QML memanggil slot di main thread; permintaan trading diantrikan (`QMutex`) ke worker.
Worker mengirim data ke UI lewat sinyal Qt (queued). Dilarang keras memanggil MCP dari main thread.

---

## 5. GOTCHAS PENTING (Wajib Diingat!)

1. **Versi MT5 vs library:** Terminal sering auto-update ke build baru (mis. **6182**), sedangkan library pip `MetaTrader5` tertinggal (**6180**) sehingga native IPC timeout (-10005). Mesin C++ memakai **MCP-only** yang kebal pembaruan versi terminal.
2. **Simbol Exness pakai suffix huruf kecil `m`**: `EURUSDm`, `XAUUSDm`, `BTCUSDm`.
   - `EURUSD` polos → "symbol not found".
   - **JANGAN PERNAH uppercase nama simbol** — `settings.symbolsList` sengaja TIDAK `.toUpper()` agar kecocokan simbol tetap terjaga.
3. **API Key MCP unik per instalasi terminal.** Ganti terminal = key baru (MT5 → Tools → Options → tab MCP → Enable internal server). Endpoint default: `http://127.0.0.1:22346/mcp`.
4. **`mcp_secret.json`** (gitignored) = `{"mcp_endpoint":..., "mcp_api_key":<teks biasa>}`.
   - Di-auto-load saat startup (`ConfigStore::loadMcpSecret`).
   - Di-auto-save tiap connect MCP sukses (`onWorkerConnected`).
5. **`serverConnected=False` / indikator "0/0 kb"** = terminal MT5 belum tersambung ke broker (bukan bug bot). Penyebab umum: market tutup (weekend), belum login broker di terminal MT5, atau salah instalasi MT5 (harus MT5 dari broker terkait, mis. Exness).
6. **`connectBot()` tidak boleh gagal-total** jika simbol aktif tak ditemukan — tetap connect, beri warning agar daftar simbol termuat dan user bisa memilih simbol yang benar.

---

## 6. Mode Programmer — Kontrak API Skrip JavaScript (QJSEngine)

Skrip JavaScript berjalan di dalam sandbox `QJSEngine`: definisikan `SETTINGS` (opsional), `PARAMS` (opsional), dan fungsi `on_bar(ctx)`.
`on_bar(ctx)` mengembalikan sinyal: `"BUY"`, `"SELL"`, `null`, objek perintah dari `ctx.*`, atau array perintah.

**Sandbox & Keamanan:**
- QJSEngine murni tanpa akses filesystem, socket OS, ataupun eksekusi biner.
- Watchdog anti-infinite-loop ditenagai oleh `QJSEngine::setInterrupted` pada thread pengawas (timeout 2000ms).
- Runtime error ditangkap secara fail-safe (tidak meng-crash bot).

**`ctx` menyediakan:**
- Harga: `ctx.open, ctx.high, ctx.low, ctx.close, ctx.volume` (array angka, lama -> baru).
- Info Live: `ctx.bid, ctx.ask, ctx.spread, ctx.point, ctx.digits, ctx.symbol`.
- Akun & Posisi: `ctx.balance, ctx.equity, ctx.margin, ctx.freeMargin, ctx.marginLevel, ctx.profit, ctx.unrealizedProfit, ctx.position, ctx.positions`.
- Waktu / Sesi: `ctx.time, ctx.now, ctx.hour, ctx.minute, ctx.weekday` (0=Senin..6=Minggu).
- Parameter & Konfigurasi: `ctx.params[key]`, `ctx.settings[key]`, `ctx.log(msg)`.
- 22 Indikator: `sma, ema, wma, rsi, atr, stdev, highest, lowest, bbands, macd, stochastic, adx, cci, vwap, williams_r, obv, mfi, donchian, parabolic_sar, supertrend, ichimoku, pivot_points, crossover, crossunder`.
- Perintah Trading:
  - `ctx.buy(volume, sl_points, tp_points, sl, tp, risk, comment)`
  - `ctx.sell(...)`
  - `ctx.close_position(pos)` / `ctx.close_all()`
  - `ctx.modify(pos, sl, tp)`

---

## 7. UI / QML Konvensi (C++ Native)

- Panel QML di `cpp/qml/`. Komponen dikompilasi via `resources.qrc` ke dalam biner EXE.
- Komponen bersama: `Theme.qml`, `CField.qml`, `CButton.qml`, `CCombo.qml`, `ThinScrollBar.qml`, `RiskConfigForm.qml`.
- Panel utama: `AccountBar`, `LoginPanel`, `ManualTradePanel`, `ProgrammerPanel`, `StatsPanel`, `PositionsPanel`, `LogPanel`, `CandleChart`, `EquityChart`, `ConfigPanel`.
- Editor Pro: `JsHighlighter` (native C++ `QSyntaxHighlighter`), nomor baris (gutter), validasi real-time, panel Bantuan API & template skrip.
- Auto-trading dikendalikan dari tab Programmer (Start/Stop).
- Setiap pengubahan file QML **WAJIB** diikuti pengujian smoke offscreen (`smoke.ps1`).

---

## 8. Checklist Verifikasi & Testing (Checklist Mutlak)

Setiap perubahan kode WAJIB melewati verifikasi:
1. `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1` (Build sukses).
2. `run_cpp_tests.bat` (7 / 7 test suite ctest lulus).
3. `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\smoke.ps1` (SMOKE_EXIT=0).
4. `deploy_cpp.bat` (Standalone build terverifikasi mandiri).
5. Bersihkan semua berkas temporary (`_*.txt`, `*.tmp`).
