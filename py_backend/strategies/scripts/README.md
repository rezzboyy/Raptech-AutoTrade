# Skrip Mode Programmer (Fast Scalper - Semua Market)

Koleksi skrip strategi scalping super cepat (**Anti-Bengong / Fast OP**) yang dirancang agar bot **langsung membuka posisi tanpa menunggu berjam-jam**, kompatibel untuk seluruh kelas pasar trading broker MT5 (Exness, dsb).

Format: **Python (`.py`)** — dieksekusi langsung secara native oleh Trading Engine Bot (`py_backend` / `script_runtime.py`).

---

## ⚡ Daftar Skrip Strategi Kilat

| Nama Skrip | Pasar Target | Timeframe | Karakteristik Utama |
|---|---|---|---|
| [**`brutal_cent_scalper.py`**](brutal_cent_scalper.py) | **Akun Cent / Semua Market** (Forex, Gold, Kripto) | **M1** | 🔥 **Brutal Instant OP & Martingale Recovery**: Langsung OP seketika saat start (anti-bengong), scalping kilat TP 50 pts, siklus recovery agresif (1.75x-2.0x), reset ke Base Lot saat profit! Cocok untuk testing bot di akun cent. |
| [**`universal_fast_scalper.py`**](universal_fast_scalper.py) | **Semua Market** (Forex, Emas, Kripto, Indeks) | **M1 / M5** | **Multi-Market Master Engine**: Otomatis mendeteksi instrumen, auto-scaling spread, TP/SL dinamis, dan soft recovery. |
| [**`fast_forex_scalper.py`**](fast_forex_scalper.py) | **Forex** (EURUSDm, GBPUSDm, USDJPYm, dsb) | **M1 / M5** | Micro-momentum ultra-cepat, target 8 pips TP, proteksi spread ketat. |
| [**`fast_gold_scalper.py`**](fast_gold_scalper.py) | **Logam/Gold** (XAUUSDm / XAUUSD) | **M1 / M5** | Volatilitas tinggi emas, target 12 pips ($1.20), break-even cepat & trailing lock. |
| [**`fast_crypto_scalper.py`**](fast_crypto_scalper.py) | **Kripto** (BTCUSDm, ETHUSDm, dsb) | **M1 / M5** | Toleransi spread kripto lebar, TP cepat $45 di BTC, aktif 24/7. |
| [**`fast_indices_scalper.py`**](fast_indices_scalper.py) | **Indeks** (US30m, USTECm, US500m) | **M1 / M5** | Penangkapan ledakan momentum indeks bursa, target TP 350 pts. |

---

## 🚀 Mengapa Skrip Ini "Open Posisi Cepat Ngga Kelamaan"?

1. **State-Based Micro Momentum (Bukan Crossover Statis)**:
   Strategi biasa menunggu peristiwa crossover langka (bisa berjam-jam tidak terjadi). Skrip Fast Scalper membaca status bias momentum terkini (Micro-EMA + Micro-RSI) saat posisi kosong dan **langsung masuk pasar pada bar pertama**!
2. **One-Trade-Per-Bar Disabled**:
   Begitu satu posisi selesai mencapai TP atau tertutup, skrip langsung siap membuka siklus berikutnya tanpa jeda bar yang panjang.
3. **Smart Quick Scalping**:
   TP terukur rapat (cepat menyentuh target), Break-Even mengunci modal saat running profit, dan Trailing Stop mengamankan profit jika pergerakan melesat jauh.
4. **Soft Recovery Terukur**:
   Jika terjadi loss, volume lot disesuaikan secara bertahap lembut (1.25x - 1.30x, maks 4 tahap), dan langsung di-reset ke Base Lot (0.01) begitu siklus menang.

---

## 🛠️ Cara Penggunaan di Aplikasi

1. Buka tab **Programmer** di panel kiri aplikasi.
2. Pada dropdown skrip, pilih salah satu skrip cepat di atas (misal `universal_fast_scalper`).
3. Klik **Muat** lalu **Validasi**.
4. Klik **Terapkan sebagai Strategi** dan klik **Start**.
5. Bot akan langsung membuka posisi begitu bar candle M1/M5 terbentuk!
