# Raptech AutoTrade v3.1.0

> High-Performance MetaTrader 5 Algorithmic Trading Tool — Terminal UI, Headless Edition & Production-Grade Capital Protection Engine.

---

## ⚡ Panduan Cepat (Quick Start)

### 1. Jalankan Terminal UI Interaktif
Klik ganda file **`Run_CLI.bat`** atau jalankan perintah:
```bash
python main.py
```

### 2. Jalankan Headless Daemon (Background VPS)
Klik ganda file **`Run_Headless.bat`** atau jalankan:
```bash
python main.py --headless --profile default_example
```

### 3. Jalankan Pengujian Unit (Test Suite)
Klik ganda file **`Run_Tests.bat`** atau jalankan:
```bash
python -m pytest tests/ -v
```
*(54/54 unit test lolos 100%).*

### 4. Jalankan Backtest Modular (Tanpa Lookahead Bias)
```bash
python main.py backtest --strategy fast_gold_scalper --symbol XAUUSDm --timeframe M5 --bars 500
```

---

## 🤖 Untuk Analisis AI / ChatGPT
Jika Anda ingin menganalisis proyek ini menggunakan **ChatGPT** atau AI Coding Assistant lainnya, gunakan file panduan lengkap:
👉 **[`CHATGPT_CONTEXT.md`](CHATGPT_CONTEXT.md)**

File tersebut memuat:
- Arsitektur sistem & alur kerja (*lifecycle execution*)
- Peta direktori dan tanggung jawab modul
- Aturan ketat proteksi modal (*capital protection invariants*)
- Kontrak API model data & backend protocol
- Panduan pembuatan strategi kustom baru
- Standar rekayasa perangkat lunak

---

## 📚 Master Dokumentasi Teknis
Dokumentasi mendalam tersedia di folder [`docx/`](docx/):
* [📋 **task.md**](docx/task.md) — Roadmap pengembangan 9 fase & checklist pekerjaan.
* [📐 **design.md**](docx/design.md) — Arsitektur sistem, wireframe TUI, & diagram alur.
* [🛡️ **rules.md**](docx/rules.md) — Standar rekayasa ketat, thread-safety MT5, & proteksi modal.
* [🚀 **production.md**](docx/production.md) — Panduan build slim executable (~30 MB) & deploy VPS.
* [🤖 **agents.md**](docx/agents.md) — AI Agent Playbook & thinking model.
