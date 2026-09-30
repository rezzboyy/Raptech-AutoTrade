# Panduan Trading — Raptech MT5 Bot

Panduan langkah demi langkah cara memakai **Auto Trading** dan **Manual Trading**
di bot. Baca bagian Persiapan dulu, karena keduanya butuh koneksi yang aktif.

> ⚠️ **Selalu uji di akun DEMO dulu.** Trading otomatis berisiko kehilangan dana.

---

## 0) Persiapan (WAJIB sebelum trading)

Rantai koneksi: **Bot → MT5 → Broker**. Ketiganya harus hidup.

1. **Buka MetaTrader 5** dan login ke akun (mis. `File → Login to Trade Account`).
   - Pastikan pojok **kanan bawah MT5** menunjukkan **angka kbps** (mis. `45/12 kb`),
     BUKAN `0 / 0 Kb` atau "No connection". Ini artinya terminal tersambung broker.
   - Market forex tutup Sabtu–Minggu; sebagian data/koneksi baru penuh saat market buka.
2. **Aktifkan server MCP** di MT5: `Tools → Options → tab MCP → centang "Enable
   internal server"`. Salin **API Key** bila belum tersimpan.
3. **Buka bot** (`RaptechMT5Bot.exe` atau `python app.py`).
4. Di tab **Login**:
   - Pilih **Metode koneksi**: `MCP (Server MT5)` (disarankan) atau `Native`.
   - Untuk MCP: isi **API Key** (atau pilih profil tersimpan), lalu **Login & Connect**.
5. **Cek indikator di header bot:**
   - **Broker: Terhubung** (hijau) + **saldo/currency muncul** + badge **DEMO/REAL**
     → siap trading.
   - **Broker: Menunggu broker** (oranye) + saldo `—` → terminal belum tersambung
     broker. Order akan **ditolak otomatis (fail-safe)**. Perbaiki dulu langkah 1.

> Bila status "Menunggu broker": kembali ke MT5, pastikan kbps aktif. Kalau akun
> demo tidak mau connect, kemungkinan akun trial kedaluwarsa → buat demo baru
> (`File → Open an Account`).

---

## A) AUTO TRADING (bot buka order otomatis sesuai strategi)

Bot mengevaluasi strategi tiap interval, lalu membuka/menutup order sendiri.

### Langkah
1. Selesaikan **Persiapan** di atas (status harus **Broker: Terhubung**).
2. Buka tab **Konfigurasi**, atur lalu **Simpan Konfigurasi**:
   - **Simbol** (Exness Standard pakai suffix 'm'; multi pisah koma: `EURUSDm, GBPUSDm`)
   - **Timeframe** (M1/M5/M15/M30/H1/H4/D1)
   - **Strategi** + parameternya (MA Cross, RSI, Bollinger, MACD, Stochastic, Multi-indikator)
   - **Risiko per trade** (0.01 = 1% dari balance)
   - **Max posisi**
   - **SL/TP** — pilih mode **Points** (jarak) atau **Percent** (% dari harga entry)
   - Opsional: **Trailing stop**, **Break-even**
   - **Proteksi Harian**: Daily drawdown limit, Max trade/hari
   - **Proteksi Lanjutan** (lihat bagian C): Max spread, Max exposure, Equity cut-loss,
     Safety guard (loss beruntun), Virtual/Hidden SL/TP
3. Kembali ke tab **Login**, nyalakan sakelar **Auto Trading**.
4. Bot mulai bekerja:
   - Membaca candle → menghitung sinyal strategi → membuka order dengan lot otomatis
     (berdasarkan risiko) + SL/TP.
   - Mengelola posisi: trailing stop & break-even (bila diaktifkan).
   - Menegakkan proteksi: berhenti bila **drawdown harian** atau **batas trade/hari**
     tercapai.
5. Pantau di panel kanan: **chart**, **Posisi Terbuka**, dan tab **Statistik**
   (winrate, profit factor, dll.).

### Menghentikan
- Matikan sakelar **Auto Trading** → bot berhenti membuka order baru (posisi yang
  ada tetap terbuka; tutup manual bila perlu).
- **Disconnect** → menghentikan koneksi sepenuhnya.

### Catatan penting
- Auto trading **tidak** akan mengirim order bila `Broker: Menunggu broker`
  (fail-safe). Pastikan hijau.
- Perubahan konfigurasi diterapkan setelah **Simpan Konfigurasi**.

---

## B) MANUAL TRADING (kamu yang buka/tutup order)

Lewat tab **Order**. Cocok untuk entry manual atau memasang pending order.

### Kirim Market Order (eksekusi harga sekarang)
1. Selesaikan **Persiapan** (status **Broker: Terhubung**).
2. Buka tab **Order**.
3. Isi:
   - **Simbol** (mis. `EURUSDm`)
   - **Tipe**: `Market Buy` atau `Market Sell`
   - **Volume (lot)**: mis. `0.01`
   - **SL (harga)** & **TP (harga)**: opsional (isi `0`/kosong = tanpa SL/TP)
4. Klik **Kirim Market Order**. Posisi muncul di tabel **Posisi Terbuka** (panel kanan).

### Pasang Pending Order (order menunggu di harga tertentu)
1. Di tab **Order**, pilih **Tipe**: `Buy Limit`, `Sell Limit`, `Buy Stop`, atau `Sell Stop`.
2. Isi **Volume**, **Harga** (harga pending — wajib > 0), dan SL/TP opsional.
3. Klik **Pasang Pending Order**. Order muncul di daftar **Pending Order**.
   - Panduan singkat tipe:
     - **Buy Limit**: beli bila harga TURUN ke level (di bawah harga sekarang).
     - **Sell Limit**: jual bila harga NAIK ke level (di atas harga sekarang).
     - **Buy Stop**: beli bila harga NAIK menembus level.
     - **Sell Stop**: jual bila harga TURUN menembus level.

### Menutup / Membatalkan
- **Tutup satu posisi**: tombol **Tutup** di baris posisi (panel **Posisi Terbuka**).
- **Tutup semua posisi**: tombol **Tutup Semua** di header panel Posisi.
- **Hapus pending order**: tombol **Hapus** di baris order (tab Order).

### Catatan penting
- Sama seperti auto: order manual **ditolak otomatis** bila `Broker: Menunggu broker`.
- **SL/TP diisi sebagai HARGA**, bukan jarak points (mis. SL `1.09500`).
- Untuk demo, mulai dengan volume kecil (`0.01`) untuk uji.

---

## C) PENGATURAN PROTEKSI & RISIKO (tab Konfigurasi)

Semua diatur di tab **Konfigurasi**, lalu **Simpan Konfigurasi**. Isi `0` untuk
menonaktifkan (kecuali disebutkan lain). Semua proteksi bersifat **fail-safe**.

### SL/TP: Points vs Percent
- **Points**: SL/TP sebagai jarak points dari harga (mis. SL 300, TP 600).
- **Percent**: SL/TP sebagai persen dari harga entry (mis. SL `0.5` = 0,5%, TP `1.0` = 1%).
- Pilih di dropdown **Order SL & TP → Points/Percent**.

### Virtual / Hidden SL/TP (anti stop-hunting)
- Switch **Virtual / Hidden SL/TP**.
- Saat aktif: SL/TP **tidak dikirim ke broker** (tersembunyi). Bot memantau harga
  tiap detik dan menutup posisi saat level tercapai. Trailing & break-even juga
  berjalan secara virtual.
- Tetap aktif memantau **walau Auto Trading dimatikan** (selama bot terhubung).
- Catatan: berlaku untuk posisi yang dibuka **auto-trading**. Order manual tetap
  memakai SL/TP biasa (dikirim ke broker).

### Money Management
- **Max Posisi**: jumlah maksimum posisi terbuka bersamaan.
- **Max Eksposur (lot)**: total volume seluruh posisi tidak boleh melebihi ini
  (`0` = tanpa batas). Order yang membuat total lot melewati batas ditolak.
- **Risiko/trade**: lot dihitung otomatis dari % balance (bukan lot tetap).

### Proteksi Ekuitas & Harian
- **Daily Drawdown (%)**: bila rugi harian ≥ batas → auto-trading berhenti.
- **Equity Cut-Loss (%)**: bila drawdown ekuitas (balance→equity) ≥ batas →
  **semua posisi ditutup** dan auto-trading dihentikan. Pengaman modal utama.
- **Max Trade Harian**: batasi jumlah transaksi per hari.

### Filter & Safety
- **Max Spread (pts)**: tolak entry baru bila spread melonjak melebihi batas
  (mis. saat pembukaan sesi / berita). `0` = nonaktif.
- **Max Loss Beruntun (Safety Guard)**: setelah N kerugian berturut-turut, entry
  dijeda otomatis (cegah revenge trading). Rangkaian loss "reset" setelah ada profit.

> Rekomendasi awal (demo): Equity Cut-Loss `10`, Daily Drawdown `5`, Max Loss
> Beruntun `3`, Max Spread sesuai broker (mis. `30`), Max Eksposur sesuai modal.

## Ringkasan Cepat

| Ingin... | Lakukan |
|---|---|
| Bot trading sendiri | Konfigurasi → Simpan → sakelar **Auto Trading** ON |
| Beli/jual sekarang | Tab **Order** → Market Buy/Sell → **Kirim Market Order** |
| Order menunggu di harga | Tab **Order** → Limit/Stop + Harga → **Pasang Pending Order** |
| Tutup 1 posisi | Tombol **Tutup** di tabel posisi |
| Tutup semua | Tombol **Tutup Semua** |
| Batal pending | Tombol **Hapus** di daftar pending |
| Stop bot | **Auto Trading** OFF, lalu **Disconnect** |

## Kalau order tidak jalan / saldo `—`
1. Cek header bot: apakah **Broker: Terhubung**? Kalau **Menunggu broker** → MT5 belum
   tersambung broker.
2. Cek MT5 pojok kanan bawah: ada **kbps**? Kalau `0/0` → login ulang / cek internet /
   akun demo mungkin kedaluwarsa.
3. Cek panel **Log** di bot untuk pesan spesifik (mis. "server_connected=false" atau
   alasan order ditolak).
4. **Order sengaja ditolak oleh proteksi?** Cek Log — bisa jadi kena gerbang:
   spread melebihi batas, total eksposur penuh, drawdown/equity cut-loss tercapai,
   atau safety guard (loss beruntun) sedang menjeda. Sesuaikan di tab Konfigurasi →
   Proteksi Lanjutan bila perlu.
