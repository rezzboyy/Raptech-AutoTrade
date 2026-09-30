# tasks_cpp.md — Rewrite Raptech/XAVIQ Bot ke C++ (Qt 6)

Tujuan: menulis ulang bot dari **Python + PySide6** ke **C++ + Qt 6** agar lebih
ringan (RAM kecil, startup cepat, EXE kecil), tetap fitur setara.
Prinsip (wajib): **bertahap · audit tiap tahap (build + unit test) · fail-safe ·
paritas fitur dengan versi Python · dokumen Bahasa Indonesia**.

> ⚠️ **Peringatan skala:** ini proyek besar (perkiraan berminggu-minggu). Sebagian
> besar QML BISA dipakai ulang, tapi seluruh logika Python (engine, indikator,
> sandbox skrip, MCP client) harus ditulis ulang di C++.

---

## Keputusan Desain (finalkan di Tahap 0)

1. **Framework:** Qt 6 (Widgets tidak dipakai; **QML/Qt Quick** untuk UI — reuse QML lama).
2. **Build system:** CMake + compiler MSVC (Windows) / atau MinGW. Qt 6.6+.
3. **Backend koneksi:** **MCP-only** (HTTP/JSON-RPC via `QNetworkAccessManager`).
   Native `MetaTrader5` DITINGGALKAN (itu library Python; tak ada padanan C++ resmi).
4. **Bahasa skrip Mode Programmer:** **QJSEngine (JavaScript)** — bawaan Qt, ringan,
   tanpa dependency. (Alternatif: Lua via sol2, atau embed Python — TIDAK disarankan
   karena mengembalikan berat.) **Konsekuensi: skrip Python lama harus ditulis ulang ke JS.**
5. **JSON:** `QJsonDocument`/`QJsonObject`. **HTTP:** Qt Network. **Enkripsi:** QCryptographic
   + AES via OpenSSL/libsodium (atau simpan sederhana bila cukup).
6. **Test:** QtTest (atau Catch2/GoogleTest). **Packaging:** `windeployqt` + installer.
7. **Threading:** semua panggilan MCP di **satu worker thread** (QThread), UI via signal/slot.

---

## TAHAP 0 — Setup Toolchain & Skeleton [fondasi] — SELESAI ✅

- [x] Toolchain terpasang via `aqtinstall`:
  - Qt **6.8.1** (kit `win64_mingw`) di `C:\Qt\6.8.1\mingw_64`
  - MinGW **g++ 13.1.0** (`C:\Qt\Tools\mingw1310_64`)
  - CMake **3.30.5** (`C:\Qt\Tools\CMake_64`), Ninja **1.12.1** (`C:\Qt\Tools\Ninja`)
- [x] Struktur proyek `cpp/`: `CMakeLists.txt`, `src/main.cpp`, `qml/main.qml`,
  `resources.qrc` (QML via Qt resource), `build.ps1`.
- [x] Skeleton: QGuiApplication + QQmlApplicationEngine memuat `qrc:/qml/main.qml`
  (window Material dark). Build sukses → `xaviq.exe`; jalan offscreen tanpa crash.
- [x] **Audit 0:** configure + build (Ninja/MinGW) OK; EXE berjalan.

> ⚠️ **PENTING (workflow build):** `qmlimportscanner` Qt GAGAL bila path build
> mengandung spasi (folder "Bot Trading"). Solusi: source diedit di
> `Bot Trading\cpp\` (workspace), tapi BUILD lewat **junction tanpa spasi**:
> ```
> cmd /c mklink /J C:\XaviqCpp "C:\Users\Administrator\Desktop\Bot Trading\cpp"
> powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1
> ```
> Junction `C:\XaviqCpp` sudah dibuat & menunjuk ke folder cpp.

## TAHAP 1 — Infra Inti [logging, config, settings, secure] ✅ SELESAI

- [x] `Logger` (wrapper qInstallMessageHandler + file rotasi) → setara `src/logger.py`.
- [x] `Settings` (struct + load dari env/JSON) → setara `config/settings.py`.
      (`symbolsList()` TIDAK uppercase, dukung multi-simbol pisah ',' / ';').
- [x] `ConfigStore` (baca/tulis/validasi `config.json` via QJsonDocument, dukung partial apply).
      (kredensial & `mcp_api_key` TIDAK dipersist).
- [x] `SecureStore` (enkripsi API key/kredensial; keystream CTR SHA-256 + prefix `v1:`,
      kompat mundur base64). Auto-load/save `mcp_secret.json` menyusul di tahap MCP.
- [x] **Audit 1:** unit test QtTest (`cpp/tests/test_core.cpp`) — 13 kasus, `ctest` 1/1 PASS:
      symbolsList (default/no-upper/multi), config toJson (tanpa secret)/validate/apply
      partial/apply invalid no-change/save+load roundtrip, secure roundtrip/empty/base64.
      Build lib `xaviq_core` + exe `xaviq` OK.

## TAHAP 2 — MCP Client [jaringan] ✅ SELESAI

- [x] `McpClient` (`cpp/src/net/McpClient.{h,cpp}`): QNetworkAccessManager, JSON-RPC 2.0,
      header Authorization Bearer, MCP-Protocol-Version, sesi Mcp-Session-Id.
      SINKRON via QEventLoop lokal (dipakai di worker thread). Parsing respons JSON
      biasa & SSE ('data: {..}').
- [x] `initialize()` (handshake + notifications/initialized), `callTool(name, args)`
      (ekstrak result.content[].text -> JSON; re-init sekali bila sesi kedaluwarsa).
- [x] Penanganan error terpisah (`McpErrorType`: Connection/Auth/Timeout/Tool/Protocol)
      + `maskToken`.
- [x] **Audit 2:** unit test QtTest dgn mock server QTcpServer (`cpp/tests/test_mcp.cpp`) —
      9 kasus, `ctest` 2/2 PASS: maskToken, initialize (session+auth header), callTool
      JSON, callTool SSE, tool error, 401 auth, connection refused, timeout, session
      expired -> re-init & retry.

## TAHAP 3 — Backend Abstraksi + Model [data] ✅ SELESAI

- [x] Struct model (`cpp/src/backend/Models.h`): `Account`, `SymbolSpec`, `Position`,
      `Order`, `Deal`, `Candle`, `Tick`, `OrderResult`.
- [x] Util pure (`cpp/src/backend/SymbolUtils.{h,cpp}`): classifyAccountType,
      mapTimeframeToPeriod, candleTimeRange, candidateSymbolVariations, resolveSymbolName.
- [x] Parser pure (`cpp/src/backend/McpParse.{h,cpp}`): num, parseMt5TimeEpoch, sideToMcp,
      clampComment, parseOrderResult, normalizePosition/Order/Deal, friendlyTradeError.
- [x] `TradingBackend` (interface, `TradingBackend.h`) + `McpBackend` (`McpBackend.{h,cpp}`):
      connect, accountInfo, listSymbols, symbolSpec, resolveSymbol, ensureSymbol, getRates,
      getTick, spreadPoints, positions, historyDeals, sendMarketOrder, closePosition,
      modifySlTp, sendPendingOrder, deletePendingOrder, pendingOrders.
- [x] Normalisasi respons MCP + `friendlyTradeError` + gerbang `tradingBlockedReason()`
      (experts_trade_allowed / mcp_trade_allowed / server_connected; pesan RDP Ctrl+E).
- [x] **Audit 3:** unit test QtTest (`cpp/tests/test_backend.cpp`) — 18 kasus, `ctest`
      3/3 PASS: util simbol, parser/normalisasi, dan McpBackend end-to-end via mock server
      (accountInfo dibulatkan + DEMO detect, gate experts-off memblok order, market order
      sukses, positions, listSymbols).

## TAHAP 4 — Pustaka Indikator [port 22 indikator] ✅ SELESAI

- [x] Port SEMUA indikator ke C++ (`cpp/src/indicators/Indicators.{h,cpp}`, `QVector<double>`,
      NaN untuk nilai kosong): sma, ema, wma, rsi, atr, stdev, highest, lowest, bbands,
      macd, stochastic, adx, cci, vwap, williams_r, obv, mfi, donchian, parabolic_sar,
      supertrend, ichimoku, pivot_points, crossover, crossunder.
      (Helper: rollMean/Std/Max/Min/Sum, ewmSeed & ewmSkipLeadingNan meniru pandas
      ewm adjust=False + penanganan NaN Wilder.)
- [x] **Audit 4:** unit test QtTest (`cpp/tests/test_indicators.cpp`) — membandingkan nilai
      akhir tiap indikator dengan REFERENSI dari implementasi Python (dataset 30 bar,
      toleransi 1e-6). `ctest` 4/4 PASS. crossover/crossunder diuji logikanya + guard NaN.

## TAHAP 5 — Engine Strategi + Risiko [inti trading] ✅ SELESAI

- [x] `TradeRules` (`cpp/src/engine/TradeRules.{h,cpp}`): calcLotFromSpec, count/canOpen
      posisi, applyBreakEven/applyTrailingStop, virtualExitHit, computePercentSlTp,
      currentExposure, consecutiveLosses, dailyTradeCount, dailyDrawdownBreached,
      passesRiskGates (posisi/trade harian/DD/spread+adaptasi BTC/loss beruntun),
      openOrderIfAllowed (+ batas eksposur).
- [x] Strategi bawaan (`cpp/src/strategy/Strategy.h` + `Strategies.cpp`) + factory:
      ma_cross, rsi (SMA-RSI), bollinger (std sampel ddof=1), macd, multi_indicator.
      (Catatan: tidak ada file strategi 'stochastic' di versi Python; dilewati.)
- [x] `BotEngine` (`cpp/src/engine/BotEngine.{h,cpp}`): manageOpenPositions (BE/trailing),
      computeSlTp (points/percent + proteksi min-stop #10016), handleSignal (sizing risiko,
      validasi jarak SL/TP), checkVirtualExits + updateVirtualSl, processTradingStep
      (equity cut-loss, DD harian, batas trade harian, evaluasi strategi per simbol),
      executeCommand (BUY/SELL/CLOSE/CLOSE_ALL/MODIFY, close-on-reversal, one-trade-per-bar),
      closeAll.
- [x] **Audit 5:** unit test QtTest (`cpp/tests/test_engine.cpp`) dgn FakeBackend in-memory —
      12 kasus, `ctest` 5/5 PASS: factory, sinyal ma_cross BUY/SELL, calcLot, gerbang max
      posisi, openOrder allowed/blok-eksposur, processStep buka pada sinyal & hormati max
      posisi, equity cut-loss tutup+stop, virtual TP exit.

## TAHAP 6 — Engine Skrip (Mode Programmer) via QJSEngine [paling menantang] ✅ SELESAI

- [x] `ScriptContext` (`cpp/src/script/ScriptContext.{h,cpp}`): QObject ctx yang diekspos
      ke JS — data harga (open/high/low/close/volume), params, position/positions,
      balance/equity/margin/marginLevel, bid/ask/spread/point/digits/symbol,
      hour/minute/weekday, SEMUA indikator, `buy/sell/close_position/close_all/modify`, `log`.
- [x] `ScriptStrategy` (`cpp/src/script/ScriptStrategy.{h,cpp}`): berbasis `QJSEngine`;
      compile+evaluate, baca `SETTINGS`/`PARAMS` global, jalankan `on_bar(ctx)`.
- [x] Sandbox: QJSEngine tanpa akses file/OS/jaringan (hanya ctx + JS standar); watchdog
      anti loop tak terbatas via `QJSEngine::setInterrupted` (thread pengawas + timeout);
      error skrip fail-safe (ditangkap → tanpa sinyal). Integrasi engine: `Strategy::onBar`
      generik + `BotEngine` mengisi RuntimeContext & mengeksekusi perintah.
- [x] Kontrak `on_bar(ctx)` → string / objek / array perintah (setara versi Python).
- [x] **Konversi skrip contoh** Python → JS (`cpp/scripts/`): ema_cross.js, cbot_style.js,
      managed_exit.js + README.md (dokumentasi API JS).
- [x] **Audit 6:** unit test QtTest (`cpp/tests/test_script.cpp`) — 14 kasus, `ctest` 6/6 PASS:
      validasi (ok/missing on_bar/syntax), sinyal BUY, null, intent eksplisit & dari SETTINGS,
      array perintah, close_all, modify posisi aktif, indikator dari skrip, data ctx,
      runtime error tanpa crash, infinite loop diinterupsi watchdog.

## TAHAP 7 — Controller + Worker Thread [jembatan QML] ✅ SELESAI

- [x] `BotController : QObject` (`cpp/src/app/BotController.{h,cpp}`): Q_PROPERTY (connected,
      trading, status, backend, akun lengkap, chartSymbol, stats) + slot (connectBot,
      disconnectBot, setTrading, closePosition, openManualOrder, placePendingOrder,
      closeAllPositions, deletePendingOrder, setChartSymbol, setBackend, getConfig,
      applyConfig, getStrategies, scriptTemplate, validateScript) + sinyal ke QML.
- [x] `Worker : QObject` (`cpp/src/app/Worker.{h,cpp}`) di QThread: loop tunggal
      monitoring (akun/posisi/order/chart/stats) + trading (processTradingStep), antrian
      perintah manual thread-safe (QMutex), kontrol via atomic; komunikasi ke UI via sinyal
      queued. Ekstensi BotEngine: connect/pollAccount/pollPositions/pollOrders/pollCandles/
      listSymbols/pollStats + manualMarketOrder/placePendingOrder/closeTicket/deletePending.
- [x] **Audit 7:** unit test QtTest (`cpp/tests/test_controller.cpp`) dgn FakeBackend
      thread-safe — `ctest` 7/7 PASS: connect->connectedChanged & akun terisi, setTrading,
      order manual dieksekusi di worker thread (antrian), disconnect bersih, order ditolak
      saat belum connect, config roundtrip, validateScript.
      (Catatan: slot profil kredensial/MCP dari file ditunda ke tahap store terkait.)

## TAHAP 8 — UI (QML) [fungsional, terikat ke BotController] ✅ SELESAI

- [x] UI QML fungsional baru di `cpp/qml/` (Material dark) terikat ke `bot` (BotController)
      via `setContextProperty`. Panel: `AccountBar` (balance/equity/profit/status/broker),
      `LoginPanel` (MCP endpoint+API key → connect), `ManualPanel` (BUY/SELL/close all),
      `ProgrammerPanel` (editor skrip + Validasi + Simpan + Start/Stop), `StatsPanel`,
      `PositionsPanel` (list + tombol tutup), `ChartPanel` (Canvas candle), `LogPanel`.
      TabBar: Login / Manual / Programmer / Statistik + chart/posisi/log di kanan.
- [x] `main.cpp`: register `bot`, `Logger::init()`, mode `XAVIQ_SMOKE` (muat lalu keluar 0).
      Slot controller tambahan: `setMcpConfig`, `setScript`, `currentScript`.
- [x] **Audit 8:** smoke test offscreen (`cpp/smoke.ps1`, `QT_QPA_PLATFORM=offscreen`,
      `XAVIQ_SMOKE=1`) → **SMOKE_EXIT=0** (rootObjects tidak kosong, tanpa error QML;
      hanya warning font offscreen yang wajar). Build 7/7 test tetap hijau.
      CATATAN JUJUR: ini UI fungsional baru yang ramping, BUKAN salinan pixel-perfect 18
      komponen QML Python (yang bergantung banyak slot controller belum di-port: profil
      kredensial/MCP dari file, apiReference, skema PARAMS strategi, dsb). Polish visual &
      paritas penuh diiterasi di Tahap 9+.

## TAHAP 9 — Journal + Editor Pro [polish] ✅ SELESAI

- [x] Jurnal aksi skrip: `BotController` mengumpulkan entri (time/action/symbol/detail/ok)
      dari sinyal worker, property `journal` (QVariantList) + `journalEntry` signal;
      slot `exportJournalCsv(path)` (CSV valid, escaping) & `clearJournal()`.
      `JournalPanel.qml` (tab Jurnal) + tombol Ekspor CSV / Bersihkan.
- [x] Editor Pro: `JsHighlighter` (C++ `QSyntaxHighlighter`, `cpp/src/ui/`) untuk JS —
      keyword/string/angka/komentar/ctx/Math + tanda baris error (garis merah bergelombang,
      warna sintaks dipertahankan). Terdaftar sebagai tipe QML `Xaviq.JsHighlighter`,
      dipasang ke `TextArea.textDocument`. Nomor baris (gutter) + validasi real-time
      (debounce 400ms → `errorLine`).
- [x] Panel Bantuan API (`ctx.*`): `BotController::apiReference()` (grup + signature/desc/
      snippet); panel di ProgrammerPanel dengan tombol ＋ Sisipkan ke posisi kursor editor.
- [x] **Audit 9:** build OK, `ctest` 7/7 PASS, smoke offscreen SMOKE_EXIT=0 (UI dgn Editor
      Pro + tab Jurnal dimuat tanpa error QML). Highlighter/gutter/API help/jurnal aktif.

## TAHAP 10 — Packaging & Ikon [rilis] ✅ SELESAI

- [x] Ikon: `cpp/app.ico` (multi-ukuran 16..256) dibuat dari `iconnew.png`; `cpp/app.rc`
      (`IDI_ICON1 ICON "app.ico"`) dikompilasi via windres (MinGW) → tertanam di EXE.
      CMake: `enable_language(RC)` + `app.rc` di sumber `xaviq` (guard WIN32).
- [x] `cpp/deploy.ps1`: `windeployqt --release --compiler-runtime --qmldir` → folder rilis
      mandiri `C:\XaviqCppDist\XAVIQTradingEngine\` (EXE + DLL Qt + plugin QML + runtime
      MinGW), plus salin `qoffscreen.dll` untuk uji headless. Total ~91 MB.
- [x] `main.cpp`: mode smoke via argumen `--smoke` (lebih andal dari env untuk verifikasi).
- [x] **Audit 10:** `cpp/verify_dist.ps1` menjalankan EXE dari folder dist dengan PATH
      TERBATAS (tanpa Qt bin) → **DIST_EXIT=0** (UI dimuat, semua DLL/plugin terkumpul,
      tanpa error platform plugin). Rilis terbukti mandiri.
      (Opsional installer NSIS/Inno + kompres UPX: belum, bisa ditambah nanti.)

## TAHAP 11 — Paritas & Audit Akhir ✅ SELESAI

- [x] Checklist paritas fitur lawan versi Python → di `cpp/README.md` (tabel lengkap).
      Yang belum: backend native (sengaja drop), store profil kredensial/MCP dari file.
- [x] Bandingkan output indikator C++ vs Python → sudah di Tahap 4 (toleransi 1e-6, PASS).
- [x] Audit akhir otomatis: build OK, `ctest` **7/7 PASS**, smoke offscreen exit 0,
      rilis mandiri exit 0 (PATH terbatas).
- [x] Dokumentasi: `cpp/README.md` (build/test/deploy, arsitektur, paritas, panduan DEMO),
      `cpp/scripts/README.md` (API skrip JS), catatan varian C++ di `AGENTS.md`.
- [ ] Uji end-to-end di DEMO (connect MCP, chart, order, skrip): **manual** — butuh terminal
      MT5 Exness login broker; langkah tercantum di `cpp/README.md` (tak bisa diotomatiskan
      tanpa MT5 live).

---

## STATUS AKHIR: Rewrite C++ Tahap 0–11 SELESAI ✅

Semua tahap tuntas & lolos audit (build + 7 suite QtTest + smoke + rilis mandiri).
EXE rilis: `C:\XaviqCppDist\XAVIQTradingEngine\XAVIQTradingEngine.exe` (~91 MB, self-contained).
Sisa opsional: store profil kredensial/MCP terenkripsi, installer, uji DEMO end-to-end manual.

---

## Risiko & Catatan

- **Skrip Python lama tidak kompatibel** → harus ditulis ulang ke JavaScript (QJSEngine).
  Ini kehilangan terbesar; pertimbangkan matang-matang.
- **pandas/numpy hilang** → indikator ditulis manual di C++ (butuh test ketat agar cocok).
- **Native MT5 backend hilang** → hanya MCP (sebenarnya sudah jadi jalur utama, jadi OK).
- **Waktu pengembangan jauh lebih lama** dari Python; keuntungan utama hanya "ringan".
- **Alternatif hemat effort:** optimasi EXE PySide6 (exclude modul, UPX, trim Qt plugins)
  bisa memangkas ukuran/startup tanpa rewrite — pertimbangkan sebelum commit penuh ke C++.

---

## Urutan Eksekusi yang Disarankan

Tahap 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11.
Tahap 6 (skrip QJSEngine) paling berisiko — bisa dibuat proof-of-concept lebih awal
(setelah Tahap 3) untuk memastikan pendekatan JS layak sebelum lanjut jauh.

---

## PARITAS LANJUTAN — TAHAP A (fitur SETTINGS engine + strategi stochastic) ✅ SELESAI

Hasil audit paritas vs versi Python menemukan fitur SETTINGS lanjutan (per-skrip,
dibaca dari `strategy.script_settings`) belum ter-port. Ditambahkan bertahap:

- **A1 — Filter waktu/sesi** (`BotEngine::processTradingStep`): `close_friday_hour`,
  `active_days` (0=Senin..6=Minggu), `trade_start_time`/`trade_end_time` ("HH:mm").
  Ditambah seam `setNowOverrideForTest()` untuk uji deterministik.
- **A2 — Manajemen entry/posisi**: `max_holding_bars` (auto-close umur posisi, di
  `manageOpenPositions` — perlu field baru `Position.time`, diisi `normalizePosition`),
  `min_margin_level` & `cooldown_bars` (di `executeCommand`), plus menghormati flag
  `close_on_reversal`/`one_trade_per_bar` dari SETTINGS. Catatan: cooldown diperbaiki
  agar entry PERTAMA tidak ikut terblok (bug laten di versi Python).
- **A3 — SL/TP dinamis + strategi**: `atr_sl_mult`, `atr_tp_mult`, `risk_reward_ratio`
  di `computeSlTp` (prioritas mengikuti Python: intent → ATR → RR → param → SETTINGS →
  settings), plus dukungan `sl_points`/`tp_points` dari SETTINGS. Strategi bawaan baru
  **`stochastic`** (Stochastic Oscillator) di `Strategies.cpp` + skema `getStrategies()`.
- Infrastruktur: `Strategy::scriptSettings()` (virtual) di-expose; `ScriptStrategy`
  meng-override mengembalikan SETTINGS skrip.

**Audit A1–A3:** build OK, `ctest` **7/7 PASS** (test_engine ditambah 11 kasus baru:
active_days blok/izin, jam trading, close_friday, max_holding tutup/tahan, min_margin,
cooldown, risk_reward, sl/tp dari SETTINGS, factory stochastic), smoke offscreen
**SMOKE_EXIT=0**.

---

## PARITAS LANJUTAN — TAHAP B (Mode Programmer: file skrip, ctx, SETTINGS) ✅ SELESAI

- **B1 — Properti ctx skrip** (`ScriptContext`): `ctx.time` (epoch bar terakhir),
  `ctx.now` (epoch sekarang), `ctx.settings` (objek SETTINGS), `ctx.unrealizedProfit`
  (alias floatingProfit).
- **B2 — Manajemen file skrip** (`BotController`): `listScripts()`, `loadScript(name)`,
  `loadScriptFile(url)`, `saveScript(name, source)` (folder `scripts/`, ekstensi `.js`).
  UI `ProgrammerPanel`: dropdown skrip + tombol Muat / File... / Simpan File + FileDialog.
- **B3 — Bantuan SETTINGS**: `settingsReference()` (6 grup: order dasar, SL/TP dinamis,
  filter waktu/sesi, manajemen entry/posisi, proteksi) + `settingsTemplate()`. UI dialog
  "Variabel SETTINGS" dengan tombol Sisipkan per-item + "Sisipkan Template SETTINGS Lengkap".

**Audit B1–B3:** build OK, `ctest` **7/7 PASS** (test_script +2: ctx.settings/time;
test_controller +2: roundtrip file skrip, settingsReference/template), smoke
**SMOKE_EXIT=0**.

**DITUNDA (opsional, nilai rendah):** PARAMS dinamis `custom_script` masuk ke tab Manual
(scriptParams/applyScript) — skrip sudah mengelola PARAMS/SETTINGS-nya sendiri di tab
Programmer, jadi ini tidak mendesak.

---

## PARITAS LANJUTAN — TAHAP C (mcp_secret.json + exportLogs) ✅ SELESAI

- **C1 — Auto-load/save `mcp_secret.json`** (`ConfigStore::loadMcpSecret`/`saveMcpSecret`):
  auto-load API key + endpoint MCP saat startup (di `BotController` ctor, tidak menimpa
  nilai yang sudah diset); auto-save saat connect MCP sukses (`onWorkerConnected`, teks
  biasa, berkas gitignored). Setara `_load_mcp_secret`/`save_secret_file` versi Python.
- **C2 — `exportLogs(path)`** (`BotController`): ekspor `logs/bot.log` ke file pilihan;
  format CSV (`time,level,message`, parse "HH:mm:ss | LEVEL | pesan") bila `.csv`, atau
  teks apa adanya. UI `LogPanel`: tombol "Ekspor" + FileDialog (SaveFile, .csv/.txt).

**Audit C1–C2:** build OK, `ctest` **7/7 PASS** (test_core +2: mcp_secret save/load &
tidak menimpa key, tolak key kosong), smoke **SMOKE_EXIT=0**. (exportLogs diverifikasi
lewat build+smoke+review; membaca berkas log runtime, tidak diuji unit terpisah.)

---

## STATUS PARITAS: Tahap A + B + C SELESAI ✅
Fitur SETTINGS engine (waktu/sesi, cooldown, margin, holding, ATR SL/TP, RR), strategi
stochastic, manajemen file skrip, properti ctx (time/now/settings), Bantuan SETTINGS,
auto-load API key MCP, dan export log — sudah setara versi Python.
Sisa opsional (nilai rendah): PARAMS dinamis custom_script di tab Manual; konversi sisa
skrip contoh ke JS; AnalyzeHUD/Splash; SecureStore AES penuh; re-deploy EXE rilis.
