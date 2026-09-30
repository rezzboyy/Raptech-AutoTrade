# AGENTS.md — Aturan & Konteks Proyek (XAVIQ Trading Engine)

> File ini adalah panduan untuk **asisten AI** yang bekerja di proyek ini.
> Baca dari atas ke bawah sebelum mengerjakan apa pun. Tujuannya: AI lain bisa
> langsung bekerja dengan gaya, konvensi, dan kehati-hatian yang sama.

---

## 1. Ringkasan Proyek

**XAVIQ Trading Engine** = bot trading MetaTrader 5 (MT5).
- **Mesin Utama (C++ / Qt 6.8.1)** di folder `cpp/`: GUI desktop C++ native, ringan (~45 MB RAM),
  backend **MCP-only** (kebal versi MT5), Mode Programmer JavaScript (`QJSEngine`), standalone EXE.
- **Arsip Python (PySide6)** di folder `legacy_python/`: implementasi referensi original (264 unit tests).
- Fitur utama: auto-trading (strategi bawaan + **Mode Programmer**/skrip kustom),
  order manual, manajemen risiko & proteksi, chart candle, statistik, jurnal aksi.

Lingkungan: **Windows Server/VPS**, akun **Exness** (MT5), akun uji = DEMO.

---

## 2. Aturan Interaksi (WAJIB)

1. **Balas dalam Bahasa Indonesia** (santai, to the point). Istilah teknis boleh Inggris.
2. **Kerjakan bertahap** ("kerjakan bertahap"): tiap tahap diakhiri **audit** (test + smoke),
   antar tahap harus nyambung, prinsip **fail-safe**, jangan rusak fitur yang sudah jalan.
3. **Selalu audit setiap perubahan**: jalankan `pytest` + smoke test QML. Jangan
   menyatakan "selesai" tanpa bukti test lolos.
4. **Jujur**: kalau belum diverifikasi, katakan. Jangan mengklaim yang belum dicek.
5. **Koreksi bila user keliru** (mis. salah paham fitur), dengan sopan dan berbasis fakta.
6. **Bersihkan file sementara** (skrip diagnostik/probe/smoke) setelah dipakai.
7. **Jangan echo nilai rahasia** (API key, password) di jawaban. Rujuk lewat nama.
8. User sering minta gaya "pelan-pelan" untuk hal setup → beri langkah bernomor sederhana.

---

## 3. Lingkungan & Perintah (Windows / PowerShell)

- Shell: PowerShell/cmd di Windows. **Terminal sering meng-echo perintah secara
  teracak**, dan **"Exit Code: -1" adalah artefak tooling — BUKAN error nyata**.
- **Output perintah sering tidak tertangkap** kalau di-pipe. **Trik andal:** tulis
  output ke file lalu baca:
  ```
  python script.py > _out.txt 2>&1
  ```
  lalu baca `_out.txt`. Hapus file setelah dipakai.
- **Long-running** (dev server, build): jalankan sebagai background/proses lama, atau
  gunakan timeout besar. Build EXE ~2 menit.
- Build & Run C++ DEV: `run_cpp_dev.bat` (atau `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1`)
- Test C++: `run_cpp_tests.bat` (atau `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\runtests.ps1`) — 7 suite ctest
- Smoke C++ UI: `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\smoke.ps1` (offscreen, mode `--smoke`)
- Deploy Standalone C++: `deploy_cpp.bat` (hasil di `C:\XaviqCppDist\XAVIQTradingEngine\`)
- Test Python (Legacy): `legacy_python\run_tests.bat` (atau dari folder `legacy_python`: `python -m pytest -q`)

---

## 4. Arsitektur & Struktur

```
run_cpp_dev.bat           # Launcher C++ dev (build + jalankan GUI)
run_cpp_tests.bat         # Runner 7 unit test suite C++
deploy_cpp.bat            # Pemaket rilis mandiri C++
cpp/                      # Sumber C++ (Qt 6.8.1 / MinGW)
  CMakeLists.txt          # Build via junction C:\XaviqCpp
  src/
    core/                 # Logger, Settings, ConfigStore, SecureStore
    net/                  # McpClient (HTTP JSON-RPC)
    backend/              # Models, SymbolUtils, McpParse, McpBackend
    indicators/           # 22 Indikator matematis murni
    strategy/             # Strategy base & built-in strategies
    engine/               # TradeRules (risiko) & BotEngine (trading loop)
    script/               # ScriptContext & ScriptStrategy (QJSEngine)
    app/                  # Worker (QThread) & BotController (QObject QML bridge)
    ui/                   # JsHighlighter (QSyntaxHighlighter native)
    main.cpp              # Entry point C++
  qml/                    # UI QML native C++
  scripts/                # Contoh skrip JavaScript Mode Programmer
docs/                     # Dokumentasi trading, script, MCP
legacy_python/            # Arsip referensi kode Python (PySide6)
  app.py / main.py        # Entry GUI / CLI Python lama
  src/ , ui/ , strategies/
  tests/                  # 264 unit tests pytest
```

**Thread-safety:** SEMUA panggilan MT5/MCP terjadi di **satu worker thread**. QML
memanggil slot di main thread; permintaan yang butuh MT5 diantrikan (queue) ke worker.
Worker kirim data ke UI lewat sinyal Qt (queued). Jangan panggil MT5 dari main thread.

---

## 5. GOTCHAS PENTING (sering bikin bingung — baca!)

1. **Versi MT5 vs library:** terminal sering auto-update ke build **6182**, tapi paket
   pip `MetaTrader5` mentok **6180** → `initialize()` gagal **(-10005 IPC timeout)**.
   Artinya **backend `native` TIDAK bisa dipakai** sampai pip update / terminal
   di-downgrade. **Solusi: pakai backend `mcp`.** (Default `config.json` = `mcp`.)

2. **Simbol Exness pakai suffix huruf kecil `m`**: `EURUSDm`, `XAUUSDm`, `BTCUSDm`.
   - `EURUSD` polos → "symbol not found".
   - **JANGAN uppercase nama simbol** — `settings.symbols_list` sengaja TIDAK
     `.upper()` (kalau di-upper, `EURUSDm`→`EURUSDM` jadi tak cocok). Jaga ini.

3. **API Key MCP unik per instalasi terminal.** Ganti terminal = key baru
   (MT5 → Tools → Options → tab MCP → Enable internal server). Endpoint default
   `http://127.0.0.1:22346/mcp`.

4. **`mcp_secret.json`** (gitignored) = `{"mcp_endpoint":..., "mcp_api_key":<teks biasa>}`.
   - Di-**auto-load** saat startup (`settings._load_mcp_secret`).
   - Di-**auto-save** tiap connect MCP sukses (`mcp_profile_store.save_secret_file`),
     dan saat frozen ditulis ke folder EXE (`secret_file_path()`).
   - Berbeda dari **profil MCP** (`mcp_profiles/*.json`, `api_key` TERENKRIPSI).
     `load_profile()` mendukung KEDUA format.

5. **`server_connected=False` / indikator "0/0 kb"** = terminal MT5 belum tersambung
   ke broker (bukan bug bot). Penyebab umum: **weekend/market tutup**, belum login di
   terminal, akun trial kedaluwarsa, atau salah instalasi MT5 (harus MT5 dari **Exness**).

6. **`connect()` tidak boleh gagal-total** kalau simbol tak ditemukan — tetap connect,
   beri warning, biar daftar simbol termuat & user bisa pilih yang benar. Jaga perilaku ini.

---

## 6. Mode Programmer — Kontrak API Skrip (SANDBOX)

Skrip Python tersandbox: definisikan `PARAMS` (opsional) + `on_bar(ctx)`.
`on_bar` mengembalikan: `"BUY"`/`"SELL"`/`None`, **atau** perintah dari `ctx.*`,
**atau list** beberapa perintah.

**Sandbox (keamanan):** blokir `import`, `eval/exec/compile`, `open`, `__import__`,
dunder, `getattr/globals/...` (audit AST). Ada **watchdog anti loop tak terbatas**
(`sys.settrace`). Error skrip TIDAK meng-crash bot (fail-safe → dianggap tanpa sinyal).

**`ctx` menyediakan:**
- Harga: `ctx.open/high/low/close/volume` (list, lama→baru)
- Live: `ctx.bid/ask/spread(points)/point/digits/symbol`
- Akun/posisi: `ctx.balance/equity`, `ctx.position` (posisi aktif), `ctx.positions`
- Waktu/sesi: `ctx.time/now/hour/minute/weekday` (0=Senin..6=Minggu)
- `ctx.params[...]`, `ctx.log(msg)`
- Indikator: `sma, ema, wma, rsi, atr, stdev, highest, lowest, bbands, macd,
  stochastic, adx, cci, vwap, williams_r, obv, mfi, donchian, parabolic_sar,
  supertrend, ichimoku, pivot_points, crossover, crossunder`
- Order (gaya cBot):
  - `ctx.buy(volume, sl_points, tp_points, sl, tp, risk, comment)`
  - `ctx.sell(...)` (arg sama)
  - `ctx.close_position(pos=None)`, `ctx.close_all()`, `ctx.modify(pos, sl, tp)`

**Prioritas nilai order:** intent skrip → `strategy_params` → pengaturan global (tab Manual).
Engine: OPEN dibatasi "Maks Posisi"; CLOSE/MODIFY selalu dieksekusi.
Runtime diisi engine tiap bar lewat `ScriptStrategy.bind_runtime(...)`.

Kalau menambah indikator baru: buat fungsi modul di `script_runtime.py` +
metode `ctx.*` + test correctness + update `docs/PANDUAN_SCRIPT.md` & `scripts/README.md`.

---

## 7. UI / QML Konvensi

- Panel modular di `ui/qml/components/`. Warna/tema via singleton `Theme` (import `".."`).
- Pakai komponen bersama: `CField`, `CCombo`, `ThinScrollBar` (scrollbar tipis auto-hide),
  `RiskConfigForm` (form risiko dipakai tab Manual & Programmer).
- Tab kiri: **Login, Manual, Order, Programmer, Statistik**. Kanan: chart + Posisi Terbuka.
- Metrik seragam: tinggi kontrol ~34px, label width tetap agar rata. Jarak seksi konsisten.
- Auto-trading dikendalikan **hanya** dari tab Programmer (Start/Stop). Jangan tambah
  kontrol trading ganda di Login.
- Setelah edit QML, WAJIB smoke test offscreen (QML error tidak muncul di pytest).

---

## 8. Testing & Build (WAJIB tiap perubahan)

1. `python -m pytest -q` → semua lolos (saat ini 150+ test).
2. Smoke QML offscreen → `rootObjects()` tidak kosong (tak ada error QML).
3. Untuk perubahan indikator/engine: tambah test correctness + test alur (pakai
   backend palsu untuk `_handle_signal`/`_execute_command`).
4. Build EXE hanya bila diminta user. Verifikasi `dist/RaptechMT5Bot/RaptechMT5Bot.exe` ada.
5. Bersihkan semua file sementara (`_smoke_qml.py`, `_diag_*.txt`, `_build.txt`).

---

## 9. Keamanan Trading (fail-safe)

- Selalu sarankan **uji di DEMO** dulu, **lot kecil (0.01)**.
- Aktifkan proteksi: `daily_drawdown_limit`, `equity_stop_loss`, `max_consecutive_losses`,
  `max_spread_points`, `max_exposure_lots`. Semua bersifat GLOBAL (dipakai skrip juga).
- Order butuh `server_connected=True` (terminal tersambung broker) + market buka.
- Jangan pernah commit kredensial: `.env`, `account.txt`, `mcp_secret.json`,
  `mcp_profiles/`, `.secret_key`, `config.json` (semua sudah di `.gitignore`).

---

## 10. Konvensi Kode

- Python: komentar/docstring **Bahasa Indonesia**, gaya ringkas, fail-safe
  (tangkap exception di batas yang tepat, jangan bikin bot crash).
- Ikuti pola file yang ada (jangan perkenalkan library/gaya baru tanpa alasan).
- Perubahan minimal & terfokus pada tugas; jangan "rapikan" hal di luar scope.
- Tambah/ubah fitur → tambah test + update dokumen terkait.
```
```

---

## 11. Varian C++ (Qt 6) — folder `cpp/`

Selain versi Python (utama), ada port **C++/Qt 6** di folder `cpp/` (lihat `cpp/README.md`).
- Tujuan: lebih ringan (RAM/startup/EXE), backend **MCP-only**, skrip Mode Programmer
  memakai **JavaScript (QJSEngine)** (skrip Python lama harus ditulis ulang ke JS).
- **Build HARUS lewat junction tanpa spasi** `C:\XaviqCpp` (qmlimportscanner gagal bila
  path ber-spasi): `powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1`.
- Test: `C:\XaviqCpp\runtests.ps1` (QtTest/ctest, 7 suite). Smoke UI: `C:\XaviqCpp\smoke.ps1`
  (offscreen, mode `--smoke`). Rilis: `deploy.ps1` (+`verify_dist.ps1`).
- Alat file (`fs_write`/`read_file`) hanya bekerja di workspace `Bot Trading`, BUKAN di
  `C:\XaviqCpp` — edit source di `cpp/`, build via junction.
- Status: Tahap 0–10 SELESAI (lihat `tasks_cpp.md`). Sisa: port store profil kredensial/MCP,
  installer, uji end-to-end DEMO manual.
