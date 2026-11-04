# AGENTS.md — AI Agent Playbook & Engineering Guide

> 📌 **Navigasi Dokumentasi**:  
> [📋 Task & Roadmap](task.md) • [📐 System Design](design.md) • [🛡️ Engineering Rules](rules.md) • [🚀 Production Guide](production.md) • [🤖 Agents Playbook](agents.md)

> **Target Audience**: AI Coding Assistants & Agents (Antigravity, Cursor, Windsurf, Claude Code, Trae, GitHub Copilot, Codex, etc.).  
> **Project**: Raptech Autotrade CLI (Terminal UI & Headless Edition).  
> **Domain**: MetaTrader 5 (MT5) Automated Algorithmic Trading.  
> **Environment**: Windows 10/11 / Windows Server x64, Python 3.10+ (Rich, Textual, Typer, MetaTrader5).

---

## 1. Core Agent Philosophy & Thinking Model

Setiap AI Agent yang berinteraksi dengan repositori ini **WAJIB** menerapkan 4 pilar kerja fundamental:

1. **Capital Safety & Risk-First**:
   - Kode ini mengelola dana finansial riil pengguna di broker (Exness, dll).
   - **JANGAN PERNAH** menghapus atau melemahkan filter proteksi Stop Loss, validasi lot, margin level check, atau limit daily drawdown.
   - Selalu perlakukan bug trading sebagai insiden berisiko tinggi.
2. **Evidence-Based & Context-First**:
   - **JANGAN PERNAH** berasumsi tentang format return value MetaTrader 5 atau model data.
   - Selalu baca file terkait sebelum menyarankan modifikasi.
   - Pahami keterkaitan antara antarmuka TUI (`tui/`), controller dispatcher (`core/controller.py`), dan backend worker thread (`backend/`) sesuai [design.md §1](design.md#1-arsitektur-tingkat-tinggi-high-level-architecture).
3. **Surgical & Non-Destructive**:
   - Terapkan modifikasi bertarget (*targeted edits*).
   - Pertahankan seluruh komentar teknis, docstring, dan deklarasi tipe (`from __future__ import annotations`).
   - Dilarang menimpa atau mengosongkan folder `data/` pengguna.
4. **Rigorous Verification**:
   - Pekerjaan Anda **BELUM SELESAI** jika belum diverifikasi.
   - Setiap modifikasi pada engine order, kalkulasi lot, atau parser backend **WAJIB** diverifikasi menggunakan test suite `pytest tests/`.

---

## 2. Peta Arsitektur & Tanggung Jawab Modul

| Direktori / File | Tanggung Jawab & Peran | Dokumen Referensi |
|---|---|---|
| `main.py` | Entry point tunggal. Mengatur UTF-8 console Windows dan dispatching antara Ultra-Light TUI, Textual TUI, atau Headless Daemon. | [design.md §1](design.md#1-arsitektur-tingkat-tinggi-high-level-architecture) |
| `tui/` | Lapisan antarmuka terminal interaktif: <br>• `light_app.py`: Mesin Rich Live ultra-ringan (< 30 MB RAM) [Default].<br>• `app.py`: Fullscreen Textual TUI dengan multi-tab (`--tui`).<br>• `widgets/`: Komponen UI (tabel open positions, panel telemetri, live logs). | [design.md §2](design.md#2-sinergi-antarmuka-terminal-rich--textual) & [design.md §4](design.md#4-visual-render-antarmuka-terminal-unicode-wireframe) |
| `cli/` | Penanganan command line via **Typer**: <br>• `commands.py`: Definisi subcommands (`status`, `order`, `positions`, `close`, `backup`, `export`).<br>• `headless.py`: Background runner tanpa rendering UI. | [design.md §8](design.md#8-mode-typer-cli--perintah-subcommand) |
| `core/` | Logika bisnis otomasi trading: <br>• `bot_engine.py`: Loop evaluasi tick & eksekusi strategi.<br>• `controller.py`: Pengendali state bot (`CONNECTED`, `AUTO_TRADING_ON`, dll).<br>• `risk_manager.py`: Virtual SL/TP, trailing stop, max daily loss.<br>• `order_manager.py`: Normalisasi lot broker & eksekusi order.<br>• `secure_store.py`: Enkripsi password & token kredensial. | [design.md §3](design.md#3-dual-backend-connectivity--thread-safety) & [design.md §6](design.md#6-manajemen-risiko--proteksi-virtual-sltp) |
| `backend/` | Konektivitas pasar: <br>• `native_backend.py`: Dedicated worker thread ke library `MetaTrader5` IPC.<br>• `mcp_backend.py`: Client remote HTTP/SSE JSON-RPC 2.0. | [rules.md §2](rules.md#2-aturan-thread-safety--konektivitas-metatrader-5) |
| `strategies/` | Katalog strategi bawaan (`fast_gold_scalper`, `brutal_cent_scalper`, `fast_forex_scalper`, dll). | [design.md §5](design.md#5-subsistem-strategi--skrip-trading) |
| `scripts/` | Tempat skrip trading kustom pengguna dan build tooling (`build.py`). | [production.md §4](production.md#4-pipeline-build-otomatis) |
| `data/` | Data persisten pengguna (`profiles/`, `history/`, `settings.json`). | [rules.md §4](rules.md#4-aturan-integritas-data--penyimpanan-rahasia) |
| `tests/` | Unit test suite (pytest) dengan mock backend. | [task.md §Phase 8](task.md#phase-8-comprehensive-verification--unit-testing) |
| `docx/` | Master dokumentasi sistem. | [task.md](task.md) • [rules.md](rules.md) • [design.md](design.md) • [production.md](production.md) |

---

## 3. Strict Engineering Guardrails (Pantangan Khusus)

### 3.1 Nol Dependensi Qt / PySide
- Proyek ini adalah versi **CLI murni**.
- **JANGAN PERNAH** mengimpor `PySide6`, `PyQt5`, `shiboken6`, atau komponen GUI desktop ke dalam kode repositori ini.
- Gunakan `rich` dan `textual` untuk seluruh presentasi terminal.

### 3.2 Thread-Safety MetaTrader 5
- Panggilan ke `MetaTrader5` **HARUS** diisolasi dalam satu dedicated worker thread.
- **DILARANG** memanggil fungsi `MetaTrader5` langsung dari coroutine async atau thread UI Textual.

### 3.3 Event Loop Asyncio Non-Blocking
- **JANGAN PERNAH** memanggil fungsi sinkron pemblokir (`time.sleep()`, file IO lambat, atau pemanggilan socket sinkron) di dalam thread UI.
- Gunakan `await asyncio.sleep()` dan bungkus pemanggilan worker dengan `asyncio.to_thread`.

---

## 4. Alur Verifikasi Pekerjaan (Verification Checklist)

Sebelum menyatakan bahwa tugas selesai kepada user, AI Agent **WAJIB** mengecek daftar berikut:

1. [ ] **Syntax & Import Check**: Jalankan file atau compiler check untuk memastikan tidak ada syntax error / import error.
2. [ ] **Unit Testing**: Jalankan `pytest tests/` dan pastikan seluruh test suite lolos (100% PASS).
3. [ ] **Smoke Test Booting**: Jalankan boot test `python main.py --help` untuk memverifikasi CLI dispatcher berfungsi normal.
4. [ ] **UTF-8 Compatibility**: Pastikan output teks terminal tidak menghasilkan encoding crash (*UnicodeEncodeError*) pada command prompt Windows.
5. [ ] **Data Safety Audit**: Pastikan tidak ada berkas di dalam `data/` yang terhapus atau tertimpa data kosong.
