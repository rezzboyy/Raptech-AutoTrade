# X Trading Engine - Visual Layout Redesign Plan

Dokumen ini merangkum rencana visual arsitektur antarmuka desktop baru untuk **X Trading Engine (C++ Qt 6.8.1 / MinGW 64-bit + Python Backend)** yang diadaptasi dari foto referensi workstation pengguna dengan akurasi tata letak 100% dan mengakomodasi seluruh fitur trading bot yang sudah ada.

---

## 1. Daftar Berkas Gambar Rencana (Design Boards)

Semua berkas diagram visual telah digenerate dengan resolusi tinggi (HD / QHD) dan tersimpan di folder ini:

1. **[01_Design_Plan_Mockup_Layout_Baru.png](file:///C:/Users/Administrator/Desktop/My%20Produk/Auto%20Trade/Bot%20Trading/Foto%20Plan/01_Design_Plan_Mockup_Layout_Baru.png)**
   - **Resolusi**: 1920 x 1080 px (Full HD 16:9).
   - **Tujuan**: Mockup realistis antarmuka desktop baru XAVIQ dengan palet warna dark cyber-trading terminal, kartu kontrol di sidebar kiri, dan multi-tab workspace di kanan.

2. **[02_Diagram_Pengukuran_Presisi_Geometri_Layout.png](file:///C:/Users/Administrator/Desktop/My%20Produk/Auto%20Trade/Bot%20Trading/Foto%20Plan/02_Diagram_Pengukuran_Presisi_Geometri_Layout.png)**
   - **Resolusi**: 2560 x 1440 px (2K QHD).
   - **Tujuan**: Blueprint arsitektur geometri dengan penandaan dimensi piksel (width, height, padding, gap, corner radius) pada setiap kontainer UI, tombol aksi cepat, kartu telemetri, tabel grid, dan sistem multi-tab.

3. **[03_Komparasi_Side_By_Side_Desain_Lama_vs_Baru.png](file:///C:/Users/Administrator/Desktop/My%20Produk/Auto%20Trade/Bot%20Trading/Foto%20Plan/03_Komparasi_Side_By_Side_Desain_Lama_vs_Baru.png)**
   - **Resolusi**: 2600 x 1400 px.
   - **Tujuan**: Komparasi langsung 2-panel antara foto referensi asli pengguna (kiri) versus rencana desain adaptasi fitur XAVIQ (kanan), lengkap dengan tabel mapping fitur & audit paritas visual.

---

## 2. Struktur Geometri & Dimensi Layout

### A. Sidebar Kiri: "Controls & Telemetry" (`width: 320px`, `padding: 12px`)
Sidebar kiri dirancang tetap stasioner (pinned/non-collapsible) agar eksekusi manual dan monitoring risiko akun dapat dilakukan seketika tanpa harus berpindah tab:

| Komponen | Dimensi (W x H) | Warna Aksen / Token | Fungsi / Keterangan |
|---|---|---|---|
| **Symbol & Uptime Bar** | 296 x 32 px | `#141A28`, Text `#F8FAFC` | Dropdown simbol aktif (misal `XAUUSD.vx`), tombol refresh, dan jam operasional bot |
| **Trigger Utama (START / STOP)** | 2 tombol x 144 x 36 px | START: `#0288D1`, STOP: `#D32F2F` | Tombol aktivasi dan de-aktivasi bot otomatis instan |
| **Manual Quick Trade (BUY / SELL)** | Lot: 70px, Tombol: 106px x 36px | BUY: `#2E7D32`, SELL: `#C62828` | Eksekusi order manual 1-klik dengan input lot presisi |
| **Hedge Trade Button** | 296 x 36 px | `#7B1FA2` (Purple Accent) | Eksekusi ganda serentak 50% Buy + 50% Sell untuk locking drawdown |
| **Max OP & Emergency Reset** | Stepper: 70px, Button: 216px x 36px | CLOSE ALL: `#E65100` (Dark Orange) | Pembatasan open position simultan & tombol panik tutup semua order |
| **Kartu Market Risk** | 296 x 84 px | Background: `#0E121A`, Border: `#232B3B` | Telemetri Bid/Ask real-time, Spread tick, dan target Trailing SL/TP |
| **Kartu Akun Telemetri** | 296 x 110 px | Background: `#0E121A`, Border: `#232B3B` | Balance, Equity, Floating PnL, Daily Realized PnL, Win Rate (%) |
| **Kartu Momentum Scanner** | 296 x 96 px | Background: `#0E121A`, Border: `#232B3B` | Status sinyal AI multi-timeframe (M5/M15/M30), Trend status, ATR volatility |
| **Engine Status Footer** | 296 x 28 px | Background: `#0A0D14`, Dot: `#00E676` | Indikator latensi bridge NDJSON (0.004 ms) & status koneksi broker |

### B. Workspace Kanan: "Workspace & Multi-Tab Area" (`width: calc(100% - 320px)`)
Area kerja utama yang responsif dan fleksibel dengan sistem navigasi tab:

| Komponen | Dimensi | Fitur & Komponen Terkait |
|---|---|---|
| **Workspace TabBar** | Height: 38 px | 7 Tab utama: `Open Trades`, `Trade History`, `Candlestick Chart`, `Equity Curve`, `Programmer Studio`, `Expert Log`, `Login MT5` |
| **Data Grid / Chart Area** | Dynamic Fill | Tabel order berdesain slate navy dengan row-highlight cyan `#0284C7` untuk order aktif, atau visualisasi candlestick chart dengan MA/RSI |
| **Summary Footer Bar** | Height: 32 px | Rekapitulasi posisi terbuka, total lot, total profit/loss sesi berjalan, dan net drawdown |

---

## 3. Pemetaan Fitur XAVIQ yang Diakomodasi

Semua fitur yang sebelumnya tersebar di berbagai panel QML (`Main.qml`, `StatsPanel.qml`, `PositionsPanel.qml`, `JournalPanel.qml`, `CandleChart.qml`, `ProgrammerPanel.qml`, `ConfigPanel.qml`) terintegrasi tanpa ada fitur yang hilang:

1. **Auto Trade Engine**: Start / Stop bot langsung di sidebar utama.
2. **Manual Trade Suite**: Buy / Sell / Hedge / Close All Reset langsung di sidebar utama.
3. **Multi-Timeframe Scanner**: Momentum Break & EMA Pullback sinyal tertera real-time di sidebar.
4. **Active Orders & Execution History**: Ditampilkan melalui tab `Open Trades` dan `Trade History`.
5. **Interactive Charting**: Tab `Candlestick Chart` menyajikan visualisasi lilin harga lengkap dengan indikator teknikal C++ (EMA, ATR, RSI, Bollinger Bands).
6. **Analytics & Performance**: Tab `Equity Curve` memplot pertumbuhan akun dan drawdown.
7. **Custom Bot Scripting**: Tab `Programmer Studio` memuat IDE scripting JavaScript/Python internal.
8. **Realtime System Logs**: Tab `Expert Log` menampilkan log bridge NDJSON berkecepatan tinggi.

---

## 4. Design Tokens & Palet Warna

- **Background Canvas Utama**: `#0B0E14` (Deep Cyber Black)
- **Container / Card Surface**: `#0E121A` / `#131824`
- **Border & Separator**: `#232B3B` (Muted Slate Navy)
- **Action Buttons**:
  - START: `#0288D1` (Bright Cyan)
  - STOP: `#D32F2F` (Crimson Red)
  - BUY: `#2E7D32` (Emerald Green)
  - SELL: `#C62828` (Dark Red)
  - HEDGE: `#7B1FA2` (Royal Purple)
  - CLOSE ALL RESET: `#E65100` (Amber Orange)
- **Selection Highlight**: `#0284C7` (Sky Blue)
- **Status Positif (Profit)**: `#00E676` / `#34D399`
- **Status Negatif (Loss)**: `#FF5252` / `#F87171`
- **Font Stack**: `Plus Jakarta Sans`, `Segoe UI`, `Consolas` (untuk data angka & log)
