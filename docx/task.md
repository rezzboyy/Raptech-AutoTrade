# Task & Roadmap — Raptech Autotrade CLI (TUI Edition)

> 📌 **Navigasi Dokumentasi**:  
> [📋 Task & Roadmap](task.md) • [📐 System Design](design.md) • [🛡️ Engineering Rules](rules.md) • [🚀 Production Guide](production.md) • [🤖 Agents Playbook](agents.md)

Dokumen ini memuat rencana kerja, tahapan pengembangan, dan daftar tugas (checklist) untuk pembangunan **Raptech Autotrade CLI** berbasis **Rich** & **Textual (TUI)** serta **Typer CLI**, diadaptasi dari engine trading MT5 berperforma tinggi dengan fitur manajemen risiko ketat, dual-backend (Native MT5 + MCP Gateway), seleksi multi-profil, dan runtime skrip strategi. Seluruh implementasi harus mematuhi [rules.md](rules.md) dan mengacu pada arsitektur [design.md](design.md).

---

## 1. Roadmap & Milestone Overview

```
[Phase 1: Environment & Project Scaffolding]
       │
       ▼
[Phase 2: Core Trading Engine & Dual-Backend Abstraction]
       │
       ▼
[Phase 3: Risk Management & Virtual Protection Engine]
       │
       ▼
[Phase 4: Multi-Profile & Secure Credential Store]
       │
       ▼
[Phase 5: Terminal UI Implementation (Rich Live & Textual)]
       │
       ▼
[Phase 6: Strategy Engine & Python Script Runtime]
       │
       ▼
[Phase 7: Headless CLI Mode & Typer Subcommands]
       │
       ▼
[Phase 8: Comprehensive Verification & Unit Testing]
       │
       ▼
[Phase 9: Slim Production Packaging (PyInstaller)]
       │
       ▼
[Phase 10: Production Upgrade v3.0 (Capital Safety & Reconciliation)]
       │
       ▼
[Phase 11: Mode Simulasi (Paper Trading) & Menu Real / Demo / Simulasi]
       │
       ▼
[Phase 12: Universal M1 Price Action Scalper Suite (All-Market Ready)]
       │
       ▼
[Phase 13: Stabilisasi UI TUI, Eliminasi Screen Flicker & Sinkronisasi Batas Posisi]
       │
       ▼
[Phase 14: Dual-View Terminal, Auto-Market Scanner, Anti-Flicker & Resize Engine]
       │
       ▼
[Phase 15: Production Release v3.1.0 (Modular Per-Strategy Risk & Customer Pack)]
```

---

## 2. Rincian Checklist Pekerjaan

### Phase 1: Environment & Project Scaffolding
- [x] Inisialisasi struktur direktori proyek:
  - `core/` (BotEngine, controller, risk manager, order manager, watchdog)
  - `backend/` (TradingBackend interface, Native MT5 IPC, MCP JSON-RPC client)
  - `strategies/` (Katalog strategi bawaan & runtime loader)
  - `scripts/` (Folder strategi skrip kustom pengguna)
  - `tui/` (Ultra-Light Rich Live app, Textual TUI app, widgets, layout)
  - `cli/` (Argument parser Typer, subcommands, headless runner)
  - `data/` (Penyimpanan profil akun, settings global, riwayat order, sesi terenkripsi)
  - `tests/` (Test suite pytest)
  - `docx/` (Dokumentasi lengkap proyek)
- [x] Setup `requirements.txt` minimalis tanpa dependensi GUI (PySide6/Qt dihapus total):
  - `rich>=13.7.0`
  - `textual>=0.80.0`
  - `typer>=0.9.0`
  - `MetaTrader5>=5.0.45` (Windows native MT5)
  - `aiohttp>=3.9.0`
  - `requests>=2.31.0`
  - `pytest>=8.0.0` (dev)
  - `pyinstaller>=6.0.0` (build)
- [x] Konfigurasi `.gitignore` untuk melindungi folder `data/profiles/`, `.secret_key`, log, venv, dan build artifacts.
- [x] Buat `main.py` dengan penanganan UTF-8 console code page otomatis (CP 65001) dan dispatcher fleksibel (Light TUI vs Textual TUI vs Headless).

---

### Phase 2: Core Trading Engine & Dual-Backend Abstraction
> *Referensi Desain*: [design.md §3 (Dual-Backend Connectivity)](design.md#3-dual-backend-connectivity--thread-safety) & [rules.md §2 (Aturan MT5)](rules.md#2-aturan-thread-safety--konektivitas-metatrader-5)
- [x] **Abstraksi Base Backend (`backend/base.py`)**:
  - Definisikan dataclass standar: `AccountInfo`, `Position`, `OrderResult`, `Candle`, `SymbolInfo`.
  - Definisikan abstract class `TradingBackend` (metode sinkron/asinkron terstandarisasi).
- [x] **Native MT5 Backend (`backend/native_backend.py`)**:
  - Implementasikan koneksi terminal `MetaTrader5.initialize()`, `login()`, `positions_get()`, `order_send()`, `copy_rates_from_pos()`.
  - Penanganan dedicated worker thread untuk menjamin thread-safety mutlak.
- [x] **Remote MCP Gateway Backend (`backend/mcp_backend.py`)**:
  - Implementasikan protokol JSON-RPC 2.0 via HTTP POST & SSE listener.
  - Normalisasi respons alat (*tool results*) ke dataclass standar.
- [x] **Order Manager (`core/order_manager.py`)**:
  - Validasi lot otomatis terhadap limit broker (`volume_min`, `volume_max`, `volume_step`).
  - Eksekusi order instan, pending order (Buy Limit, Sell Limit, Buy Stop, Sell Stop), dan batch close.
- [x] **Trade Controller (`core/controller.py`)**:
  - Mengelola state bot (`DISCONNECTED`, `CONNECTED`, `AUTO_TRADING_ON`, `PAUSED`).
  - Menghubungkan antarmuka UI dengan event engine dan backend worker.

---

### Phase 3: Risk Management & Virtual Protection Engine
> *Referensi Desain*: [design.md §6 (Manajemen Risiko)](design.md#6-manajemen-risiko--proteksi-virtual-sltp) & [rules.md §1 (Aturan Modal)](rules.md#1-aturan-keamanan-modal--finansial-capital-protection-invariants)
- [x] **Virtual SL / TP Local Monitor**:
  - Pelacakan harga real-time tanpa mengekspos level SL/TP ke server broker.
  - Eksekusi `order_close` otomatis saat harga pasar menyentuh ambang batas virtual.
- [x] **Virtual Dynamic Trailing Stop**:
  - Menggeser level Stop Loss ke titik impas (Break-Even) saat profit mencapai target awal.
  - Trailing otomatis mengikuti pergerakan harga puncak (*high water mark*).
- [x] **Emergency Circuit Breaker**:
  - Pemantauan kerugian harian (`max_daily_loss`).
  - Pemantauan batas penurunan ekuitas akun (`max_drawdown_percent`).
  - Penguncian auto-trading otomatis saat batas terlampaui.
- [x] **Fail-Safe Emergency Close All (`[C]`)**:
  - Penutupan massal seluruh posisi terbuka secara simultan dalam 1 klik/perintah.

---

### Phase 4: Multi-Profile & Secure Credential Store
> *Referensi Desain*: [design.md §7 (Format Konfigurasi)](design.md#7-format-konfigurasi--profil-akun) & [rules.md §4 (Integritas Data)](rules.md#4-aturan-integritas-data--penyimpanan-rahasia)
- [x] **Penyimpanan Kredensial Terenkripsi (`core/secure_store.py`)**:
  - Master key mesin lokal `.secret_key` dengan algoritma keystream CTR SHA-256.
  - Enkripsi password MT5 dan token API MCP dengan prefix `v1:`.
- [x] **Profile Manager (`core/config_store.py`)**:
  - Dukungan multiple account profiles di `data/profiles/<id>.json`.
  - Operasi atomic write untuk mencegah korupsi data profil.
  - Profil aktif dapat dipilih dinamis melalui argumen `--profile <name>` atau switcher di TUI.

---

### Phase 5: Terminal UI Presentation Layer (Rich Live & Textual)
> *Referensi Desain*: [design.md §2 (Sinergi UI)](design.md#2-sinergi-antarmuka-terminal-rich--textual) & [design.md §4 (Wireframe)](design.md#4-visual-render-antarmuka-terminal-unicode-wireframe)
- [x] **Ultra-Light TUI (`tui/light_app.py`) [Mode Utama - Upgraded Modern Terminal]**:
  - Render loop berbasis `rich.live.Live` (< 30 MB RAM, < 1% CPU).
  - Telemetri status bar: Status koneksi, RAM/CPU usage, MT5 ping latency, profit/loss harian, contextual alert banner.
  - Market Watch real-time quotes ticker bar untuk monitored symbols (Bid/Ask & Spread points).
  - Financial metric cards & Risk Drawdown progress bar meter.
  - Strategy & Protection HUD (Lot, V-SL, V-TP, Trailing, Max Pos).
  - Tabel interaktif open positions: High-contrast badges (BUY hijau, SELL merah, floating profit & pts, TRL status), clean empty state.
  - Stream live activity log dengan badge level terstruktur (ERROR, WARN, SIGNAL, ORDER, PROT, INFO).
  - Tactile keycaps hotkey bar (`[S]`, `[M]`, `[C]`, `[R]`, `[E]`, `[P]`, `[H]`, `[Q]`).
- [x] **Fullscreen Interactive Textual TUI (`tui/app.py`) [Mode `--tui`]**:
  - Layout tab interaktif: Dashboard, Positions, Manual Trade, Strategies, Settings, Live Logs.
  - Modal dialog: Ganti profil akun (`[P]`), dialog buka posisi manual (`[M]`), dialog emergency close (`[C]`).
  - Tema visual: Modern Dark Terminal Theme (Cyan / Emerald Green accents).

---

### Phase 6: Strategy Engine & Python Script Runtime
> *Referensi Desain*: [design.md §5 (Subsistem Strategi)](design.md#5-subsistem-strategi--skrip-trading)
- [x] **Katalog Strategi Bawaan (`strategies/`)**:
  - `fast_gold_scalper.py` (Scalper XAUUSD TF M1/M5)
  - `brutal_cent_scalper.py` (Scalper akun mikro / cent frekuensi tinggi)
  - `fast_forex_scalper.py` (Multi-pair Forex EURUSD / GBPUSD)
  - `fast_crypto_scalper.py` (Scalper BTCUSDm / ETHUSDm)
  - `fast_cycle_recovery.py` (Smart cycle recovery non-martingale)
  - `stochastic_adx.py` & `ma_cross.py`
- [x] **Sandbox Skrip Kustom & Indikator Murni**:
  - Penghitungan indikator pure Python list (`sma`, `ema`, `rsi`, `atr`) tanpa dependensi C/pandas berat.
  - Dukungan parameter dinamis per-strategi.

---

### Phase 7: Headless CLI Mode & Typer Subcommands
> *Referensi Desain*: [design.md §8 (Mode Typer CLI)](design.md#8-mode-typer-cli--perintah-subcommand)
- [x] Perintah `python main.py` -> Membuka Ultra-Light TUI default.
- [x] Perintah `python main.py --tui` -> Membuka Fullscreen Textual TUI.
- [x] Perintah `python main.py --headless` -> Menjalankan daemon background (cocok untuk VPS).
- [x] Subcommand `python main.py status` -> Cetak status akun dan posisi terbuka lalu exit.
- [x] Subcommand `python main.py positions` -> Cetak tabel posisi terbuka lengkap.
- [x] Subcommand `python main.py order` -> Buka posisi baru secara instan via CLI.
- [x] Subcommand `python main.py close --all` / `--ticket <id>` -> Eksekusi penutupan order via CLI.
- [x] Subcommand `python main.py backup` & `restore` -> Kompresi dan pemulihan folder `data/`.
- [x] Subcommand `python main.py profiles` -> Tampilkan daftar profil akun aktif.
- [x] Subcommand `python main.py login` -> Setup kredensial akun Native MT5 atau Remote MCP Gateway via CLI.
- [x] Subcommand `python main.py test-connection` -> Uji diagnostik koneksi broker dan benchmark latensi ping (ms).

---

### Phase 8: Comprehensive Verification & Unit Testing
> *Referensi Aturan*: [rules.md §5 (Standar Pengujian)](rules.md#5-standar-kode-python--lingkungan-windows) & [agents.md §4 (Verification Checklist)](agents.md#4-alur-verifikasi-pekerjaan-verification-checklist)
- [x] Unit test autentikasi & backend mock (Native & MCP).
- [x] Unit test validasi lot, margin level, dan eksekusi order.
- [x] Unit test proteksi Virtual SL/TP, Trailing Stop, dan Circuit Breaker.
- [x] Unit test runtime skrip strategi dan indikator math.
- [x] Unit test antarmuka CLI subcommands via Typer runner.
- [x] Verifikasi seluruh test suite lulus 100% (37 passed).

---

### Phase 9: Slim Production Packaging (PyInstaller)
> *Referensi Produksi*: [production.md §3 (Konfigurasi Slim Spec)](production.md#3-konfigurasi-pyinstaller-slim-spec)
- [x] Susun skrip build otomatis `scripts/build.py` dengan pembuangan seluruh modul GUI (`PySide6`, `PyQt5`, `tkinter`).
- [x] Batch file 1-klik untuk pengguna: `Run_CLI.bat`, `Run_Headless.bat`, `Run_Tests.bat`, `Build_EXE.bat`.
- [x] Kompilasi dan verifikasi executable mandiri `release/RaptechAutoTradeCLI.exe` (42 MB, portable dengan icon Logo R, 0 dependensi eksternal).

---

### Phase 10: Production Upgrade v3.0 (Capital Protection, Broker Reconciliation & Backtesting Engine)
> *Referensi Upgrade*: [up.md](up.md) — Production-Grade Trading Safety, Execution Reliability & Strategy Validation
- [x] **Dual-Layer Capital Protection (`core/risk_manager.py`)**:
  - Broker-side Hard SL disinkronkan langsung saat pengiriman order.
  - Virtual SL/TP & Trailing Stop dengan tracking high-water mark / low-water mark dinamis.
  - Circuit Breakers: Max Daily Net Loss ($/%) dan Max Peak Equity Drawdown.
- [x] **Persistent State & Crash Recovery (`core/state_store.py`)**:
  - Penyimpanan atomic `data/trading_state.json` untuk mencegah korupsi data saat crash.
  - Pemulihan state proteksi virtual, metrik harian, dan status circuit breaker setelah restart.
  - Automatic rollover & reset metrik saat pergantian tanggal kalender.
- [x] **Order State Machine & Broker Reconciliation (`core/order_manager.py`)**:
  - Explicit Order State Machine (`CREATED`, `VALIDATING`, `SUBMITTED`, `FILLED`, `REJECTED`, `UNKNOWN`, `RECONCILIATION_REQUIRED`).
  - Pelacakan pesanan berbasis Operation ID (UUID4) anti-duplikasi order ganda.
  - Verifikasi emergency close all dengan rekonsiliasi posisi aktual.
- [x] **Periodic Broker Reconciliation (`core/bot_engine.py`)**:
  - Background task rekonsiliasi posisi lokal vs server broker setiap interval waktu.
  - Deteksi dan adopsi otomatis posisi asing (*untracked broker positions*) ke dalam proteksi virtual.
- [x] **Modular Historical Backtesting Engine (`core/backtester.py`)**:
  - Simulasi backtesting strategi historis M1/M5 bebas lookahead bias.
  - Pemodelan spread, slippage, komisi broker, dan metrik performa (Win Rate, Profit Factor, Max Drawdown).
  - Subcommand CLI baru: `python main.py backtest --strategy fast_gold_scalper --symbol XAUUSDm --timeframe M5`.
- [x] **Comprehensive Test Suite Upgrade (54/54 Tests Passed - 100%)**:
  - Test suite diperluas dari 37 menjadi 54 automated unit tests:
    - `test_persistence.py` (atomic save/load, corrupt recovery, removal).
    - `test_reconciliation.py` (order state transitions, broker mismatch detection).
    - `test_risk_engine_v3.py` (dual-layer stop loss, circuit breaker locks).
    - `test_backtester.py` (candle parsing, trade execution simulation).
  - Seluruh 54 test terverifikasi lulus 100%.

---

### Phase 11: Mode Simulasi (Paper Trading) & Menu Real / Demo / Simulasi
- [x] **11.1 Backend Engine Simulasi Offline (`backend/simulation_backend.py`)**:
  - [x] Implementasi protokol `TradingBackend` murni offline tanpa dependensi MetaTrader 5 atau jaringan internet.
  - [x] Generator harga pasar real-time & candle sintetis deterministik (GBM/Random Walk) untuk multi-simbol (`XAUUSDm`, `EURUSDm`, `GBPUSDm`, `BTCUSDm`, dll).
  - [x] Virtual Paper Trading Execution: eksekusi instan order market, pending order, kalkulasi margin, floating PnL, equity, serta eksekusi otomatis SL/TP saat harga menyentuh level.
  - [x] Penyimpanan saldo dan riwayat trade virtual lokal di `data/simulation_state.json`.
- [x] **11.2 Integrasi Konfigurasi & Profil Akun (`core/config_store.py`)**:
  - [x] Tambahkan atribut `trading_mode: str = "demo"` (`"real"` | `"demo"` | `"simulasi"`) pada `AccountProfile`.
  - [x] Dukungan migrasi profil otomatis dan backward compatibility.
- [x] **11.3 Integrasi Controller & Dispatcher Backend (`core/controller.py`)**:
  - [x] Penentuan backend dinamis: Jika `trading_mode == "simulasi"` atau `backend == "simulation"`, alihkan ke `SimulationBackend`.
  - [x] Safety guard modal nyata: Alert proteksi tegas jika berjalan pada mode `real`.
- [x] **11.4 Menu Interaktif Pemilih Mode (`cli/commands.py` & `main.py`)**:
  - [x] Tambahkan subcommand `python main.py mode` untuk menampilkan wizard pemilihan lingkungan:
    - `[1] Real (Akun Nyata MT5 Broker - Peringatan Risiko Modal Nyata)`
    - `[2] Demo (Akun Latihan MT5 Broker - Bebas Risiko Modal)`
    - `[3] Simulasi (Paper Trading Virtual Lokal - Tanpa Perlu MT5)`
  - [x] Tambahkan opsi parameter `--mode` / `-m` pada entry point CLI (`python main.py --mode simulasi`).
- [x] **11.5 Menu & Indikator Visual di Terminal UI (`tui/light_app.py`)**:
  - [x] Tambahkan badge high-contrast di Header UI:
    - Mode Real: `[bold white on #d50000] 🔥 REAL (MODAL NYATA) [/bold white on #d50000]`
    - Mode Demo: `[bold black on #ffd600] 🧪 DEMO (BROKER) [/bold black on #ffd600]`
    - Mode Simulasi: `[bold black on #00e5ff] 🎮 SIMULASI (PAPER) [/bold black on #00e5ff]`
  - [x] Tambahkan hotkey `[T]` di bar navigasi untuk membuka dialog pergantian mode instan (Real / Demo / Simulasi).
- [x] **11.6 Suite Pengujian Unit (`tests/test_simulation.py`)**:
  - [x] Test lifecycle `SimulationBackend`: connect, tick feed, candle generation, spread, margin calculation.
  - [x] Test order execution, virtual SL/TP hit, position closing, and profit realization.
  - [x] Test mode switching and profile persistence.
  - [x] Seluruh 60 test terverifikasi lulus 100%.
- [x] **11.7 Verifikasi & Kompilasi Ulang Executable (`scripts/build.py`)**:
  - [x] Update hidden imports `backend.simulation_backend` di spec / build script.
  - [x] Kompilasi biner `release/RaptechAutoTradeCLI.exe` (42.1 MB) dan verifikasi seluruh mode (Real, Demo, Simulasi) berjalan lancar.

---

### Phase 12: Universal M1 Price Action Scalper Suite (All-Market Ready)
- [x] **12.1 Strategi Momentum Breakout M1 (`strategies/pa_breakout.py`)**:
  - [x] Deteksi penembusan swing High/Low N-bar tanpa indikator.
  - [x] Validasi rasio body candle (>60%) dan filter fakeout rejection wick.
  - [x] Formula matematis tanpa dimensi (persentase murni), 100% universal untuk Gold, Forex, Crypto, dan Akun Cent.
- [x] **12.2 Strategi Pin Bar Rejection M1 (`strategies/pa_rejection.py`)**:
  - [x] Deteksi pola Hammer & Shooting Star di batas swing ekstrem.
  - [x] Syarat ekor (wick) $\ge$ 50% dari total candle dan minimal 2x ukuran body.
- [x] **12.3 Strategi Master Hybrid Scalper M1 (`strategies/pa_hybrid.py`)**:
  - [x] Penyatuan terpadu pola Breakout, Pin Bar Rejection, dan Bullish/Bearish Engulfing.
  - [x] Pengaturan modul independen via parameter strategi.
- [x] **12.4 Dinamisasi Katalog Terminal UI (`tui/light_app.py`)**:
  - [x] Menu hotkey `[E]` dan wizard koneksi profil membaca registry strategi secara dinamis.
  - [x] Opsi sinkronisasi otomatis timeframe profil ke rekomendasi strategi (M1).
- [x] **12.5 Suite Pengujian Unit & Backtest (`tests/test_pa_strategies.py`)**:
  - [x] 10 unit test komprehensif untuk pengujian multi-pasar (Gold, Forex, Crypto), zero-division safety, dan filter doji.
  - [x] Seluruh 76 unit test sistem lulus 100%.

---

### Phase 13: Stabilisasi UI TUI, Eliminasi Screen Flicker & Sinkronisasi Batas Posisi
- [x] **13.1 Eliminasi Screen Flickering ("Kedip-Kedip") di Windows Terminal/ConHost (`tui/light_app.py` & `core/logger.py`)**:
  - [x] Implementasi `mute_console_logging()` dan `unmute_console_logging()` untuk mengisolasi ANSI stream `RichHandler` dari `sys.stdout` saat TUI aktif, mencegah tubrukan render buffer.
  - [x] Konfigurasi `Live(auto_refresh=False, vertical_overflow="crop")` dengan loop render stabil ~3 FPS (0.35s) dan non-blocking key poll (50ms).
  - [x] Dynamic log height capping pada `render_logs()` agar layout tidak pernah melompati batas tinggi jendela console.
- [x] **13.2 Sinkronisasi Penuh Batas Maksimal Posisi Terbuka (`core/bot_engine.py` & `tui/light_app.py`)**:
  - [x] Hubungkan instance `effective_risk` langsung ke `profile.risk` pada `BotEngine.__init__`.
  - [x] Implementasi property setter `BotEngine.strategy` dan pembaruan `set_strategy()` untuk menyinkronkan `max_open_positions` dan parameter risiko profil secara otomatis saat strategi diganti via menu `[E]`.
  - [x] Sinkronisasi `risk_manager.settings` secara real-time saat pengguna mengubah parameter via dialog risiko `[R]`.
- [x] **13.3 Eliminasi Log Spamming Penolakan Risiko & Closed-Bar Tracking (`core/bot_engine.py`)**:
  - [x] Catat `_last_bar_time[symbol] = confirmed_closed_bar.time` ketika bar selesai dievaluasi, termasuk saat order ditolak oleh `check_pre_trade_risk` atau berstatus HOLD.
  - [x] Tambahkan deduplikasi log cerdas (15s throttle) pada `BotEngine.log()` untuk mencegah flooding pesan warning berulang dalam 1 detik.
- [x] **13.4 Verifikasi Unit Test & Kompilasi Executable (`scripts/build.py`)**:
  - [x] Tambahkan 2 unit test baru di `tests/test_auto_trade_flow.py` (`test_strategy_switch_synchronizes_risk_settings` & `test_rejected_entry_updates_last_bar_time_and_does_not_spam`).
  - [x] Seluruh 82/82 automated tests terverifikasi lulus 100%.
  - [x] Kompilasi ulang biner `release/RaptechAutoTradeCLI.exe` (43.0 MB) sukses tanpa kendala.

---

### Phase 14: Dual-View Terminal Architecture, Automated Market Scanner & Advanced Position Management
> *Referensi Desain*: [design.md §4 (Arsitektur Dual-View & Design System v3.0)](design.md#4-visual-render-antarmuka-terminal-arsitektur-dual-view--design-system-v30)
- [x] **14.1 Pemisahan Arsitektur Layar Dual-View (`tui/light_app.py`)**:
  - [x] Implementasikan **VIEW 1 (Main Overview & Market Intelligence)**: Berfungsi saat standby untuk menyajikan informasi akun lengkap, radar pergerakan harga per-market (Bid, Ask, Spread, High, Low, Perubahan Sesi), dan Rekomendasi Pasar Otomatis.
  - [x] Implementasikan **VIEW 2 (Live Trading Execution Dashboard)**: Berfungsi saat auto trading aktif dengan tampilan *clean stats* (Saldo, Ekuitas, Floating P/L besar kontras tinggi, Circuit Breaker bar, Tabel Posisi presisi, dan Live Activity Stream).
  - [x] Tambahkan hotkey **`[V]` (Switch View)** untuk berpindah tampilan antara Layar Utama dan Layar Live kapan saja tanpa menghentikan proses trading.
- [x] **14.2 Mesin Rekomendasi Pasar Otomatis (`core/market_analyzer.py`)**:
  - [x] Bangun engine penganalisis multi-timeframe (M1 & M5) untuk menghitung Dynamic ATR (volatilitas), arah dan kekuatan tren (EMA slope), serta filter keamanan spread.
  - [x] Klasifikasi otomatis kondisi pasar (*Strong Bullish/Bearish Trend*, *Range-Bound/Rejection*, *Expansion Volatile*, *High Spread Warning*).
  - [x] Integrasikan rekomendasi strategi spesifik (Breakout, Pin Bar Rejection, Hybrid Scalper, atau Hold) beserta skor kesiapan trading `[★★★★★]`.
  - [x] Tambahkan pintasan hotkey **`[A]`** untuk memicu pemindaian ulang scanner pasar secara real-time.
- [x] **14.3 Dialog Wizard Peluncuran Sesi Trading saat Tekan `[S]` (`tui/light_app.py`)**:
  - [x] Saat menekan `[S]` di Layar Utama, tampilkan menu interaktif konfirmasi sesi trading (ringkasan profil akun, simbol aktif, strategi terpilih, dan lot).
  - [x] Berikan opsi instan: [1] Mulai Sekarang & Masuk ke Live Dashboard, [2] Ubah Simbol, [3] Ganti Strategi, [4] Sesuaikan Risiko/Lot, [0] Batal.
  - [x] Saat menekan `[S]` di Layar Live Dashboard, hentikan auto-trading dengan aman dan kembalikan layar ke Layar Utama (*Standby*).
- [x] **14.4 Tombol Fungsi Baru: Tutup Posisi 1 per 1 (`[X]`) & Tutup SEMUA (`[C]`) (`tui/light_app.py`)**:
  - [x] Implementasikan hotkey **`[C]` (Close All Positions)** dengan popup verifikasi darurat cepat `[Y/N]` dan rekonsiliasi server broker.
  - [x] Implementasikan hotkey **`[X]` (Close Individual Position)** dengan menyajikan daftar bernomor `[1], [2], ...` dari posisi terbuka aktif (memuat tiket, simbol, side, lot, dan floating profit). Operator cukup memasukkan nomor urut posisi untuk menutup tiket tersebut seketika.
- [x] **14.5 Perapihan Visual Dashboard, Eliminasi Redundansi & Anti-Ghost Buffer (`tui/light_app.py`)**:
  - [x] Pisahkan kolom `Ticket` dan `Symbol` menjadi 2 kolom tersendiri di tabel posisi terbuka dengan perataan desimal angka yang presisi.
  - [x] Bersihkan string redundansi pada nama strategi (eliminasi tag ganda `(M1) (M1)`).
  - [x] Terapkan full screen buffer wipe (`\033[2J\033[H` / `os.system('cls')`) saat keluar dari menu/dialog interaktif agar tidak meninggalkan artefak teks pada baris teratas console.
  - [x] Restrukturisasi bar pintasan navigasi menjadi kelompok taktil rapi: `[TRADING]`, `[CONFIG]`, `[SYSTEM]`.
- [x] **14.6 Eliminasi Kedip-Kedip Mutlak (Zero-Flicker) & Adaptasi Dinamis Resize / Bigsize (`tui/light_app.py`)**:
  - [x] Terapkan *mathematical height clamping* ketat ($\text{Total Lines} \le \text{console.size.height} - 1$) dengan baris log aktivitas sebagai peredam elastis dinamis agar console tidak pernah melakukan hardware auto-scrolling (penyebab utama kedip-kedip).
  - [x] Implementasikan listener deteksi perubahan ukuran terminal real-time (`console.size != last_size`). Saat jendela di-resize atau di-maximize (*bigsize*), lakukan reset buffer seketika via `console.clear()` dan render ulang proporsional tanpa distorsi UI.
  - [x] Konfigurasi layout adaptif: Mode Layar Lebar (*Bigsize*) memanfaatkan lebar penuh untuk menampilkan 4 kartu KPI, radar pasar lengkap, dan log hingga 18 baris, sedangkan Mode Kompak mempertahankan kerapihan tanpa teks terlipat (*word-wrap distortion*).
- [x] **14.7 Pengembangan Test Suite Unit (`tests/test_market_analyzer.py` & `tests/test_tui.py`)**:
  - [x] Buat unit test komprehensif untuk pengujian `MarketAnalyzer` (kalkulasi ATR, tren, spread, penentuan rekomendasi).
  - [x] Perbarui pengujian `test_tui.py` untuk menguji alur dual-view switching `[V]`, dialog start wizard `[S]`, menu close 1 per 1 `[X]`, close all `[C]`, dan resize adaptation.
  - [x] Pastikan seluruh test suite lolos 100% (99/99 passed).
- [x] **14.8 Kompilasi Biner Executable & Verifikasi Live (`scripts/build.py`)**:
  - [x] Sertakan modul baru `core.market_analyzer` ke dalam build spec PyInstaller.
  - [x] Kompilasi ulang executable mandiri `release/RaptechAutoTrade.exe` dan uji coba interaktif di Windows Terminal.

---

### Phase 15: Production Release v3.1.0 (Modular Per-Strategy Risk & Customer Pack)
- [x] **15.1 Parameter Risiko Mandiri di Setiap File Strategi**:
  - [x] Tambahkan blok konfigurasi risiko `max_daily_loss` dan `max_open_positions` langsung di dalam kelas 7 strategi bawaan (`fast_gold_scalper`, `pa_hybrid`, `pa_breakout`, `pa_rejection`, `brutal_cent_scalper`, `ma_cross`, `rsi_reversal`).
  - [x] Dukungan override parameter dinamis via constructor kwargs dan `strategy_params`.
- [x] **15.2 Eliminasi Parameter Max dari Seluruh File JSON**:
  - [x] Hapus `max_daily_loss` dan `max_open_positions` dari seluruh file profil JSON (`default.json`, `Akun_Real.json`, dsb.) dan preset pasar. File JSON kini murni hanya menyimpan kredensial koneksi dan simbol pasar.
- [x] **15.3 Sinkronisasi Otomatis Engine & Bot**:
  - [x] Engine trading membaca `max_daily_loss` dan `max_open_positions` langsung dari strategi aktif saat startup dan saat pemilihan strategi lewat menu `[E]`.
- [x] **15.4 Penamaan & Packaging Distribusi Versi 3.1.0**:
  - [x] Pembaruan penamaan executable mandiri menjadi `RaptechAutoTrade.exe` (tanpa kata "CLI").
  - [x] Target ZIP rilis bersih di `release/Raptech_AutoTrade_v3.1.0.zip` (42.7 MB) dengan panduan resmi `penggunaan.txt` dan batch file `1_Mulai_Raptech_AutoTrade.bat`.
