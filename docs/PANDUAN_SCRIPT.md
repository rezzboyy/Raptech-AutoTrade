# Panduan Mode Programmer (Skrip Strategi Kustom)

Mode Programmer memungkinkan Anda menulis strategi trading sendiri dalam bentuk
skrip **Python tersandbox**, mirip kolom script di cBot/cTrader namun disesuaikan
untuk bot ini. Skrip dijalankan bot pada setiap bar untuk menghasilkan sinyal
**BUY / SELL / tanpa aksi**.

---

## 1. Cara Pakai (UI)

1. Buka tab **Programmer** di panel kiri.
2. Tulis skrip di editor, atau klik **Template** untuk kerangka awal, atau pilih
   skrip tersimpan dari dropdown lalu **Muat**.
3. Gunakan tombol **Bantuan API** untuk membuka referensi cepat syntax `ctx.*`. Klik **Sisipkan**
   pada item mana pun untuk langsung menaruh snippet kode ke posisi kursor editor.
4. Manfaatkan fitur **Editor Pro**:
   - **Syntax Highlighting**: Pewarnaan kode Python terintegrasi (keyword, builtin, string, angka, komentar).
   - **Nomor Baris (Gutter)**: Kolom nomor baris di sisi kiri yang sinkron saat scrolling.
   - **Validasi Real-time**: Secara otomatis memeriksa sintaks saat Anda mengetik (debounce ~500ms).
     Jika ada galat sintaks, nomor baris akan ditandai **merah** dan border editor berubah merah.
5. Klik **Validasi** untuk pemeriksaan manual menyeluruh (status hijau = valid, merah = ada error).
6. Bila skrip mendefinisikan `PARAMS`, sesuaikan nilai parameter pada kartu **Parameter** dinamis.
7. Sesuaikan pengaturan proteksi di seksi **Risiko & Proteksi** bila diperlukan.
8. Klik **Simpan** untuk menyimpan skrip ke folder `strategies/scripts/` (beri Nama dulu).
9. Klik **Terapkan sebagai Strategi** lalu klik tombol **Start** untuk mengaktifkan auto-trading.
10. Pantau aktivitas di seksi **Jurnal Aksi** (klik *Tampilkan* untuk membuka tabel riwayat aksi
    BUY, SELL, CLOSE, MODIFY real-time). Gunakan tombol **Ekspor CSV** untuk mengunduh log jurnal.

> Uji selalu di akun **demo** dulu sebelum dipakai di akun riil.

---

## 2. Kontrak Skrip & Mode Full Script Settings

Setiap skrip minimal mendefinisikan fungsi `on_bar(ctx)`:

```python
def on_bar(ctx):
    return None   # "BUY", "SELL", intent ctx.buy()/ctx.sell(), atau None
```

### Mode Full Script Settings (Tanpa Input Form Manual)
Anda dapat mengatur **seluruh konfigurasi trading langsung di dalam skrip** via kamus `SETTINGS` terpusat atau konstanta huruf besar. Bot akan otomatis menyinkronkan pengaturan ini saat skrip diterapkan atau trading dimulai!

```python
SETTINGS = {
    # Pasar & Simbol
    "symbol": "EURUSDm",          # Simbol Exness (suffix "m")
    "timeframe": "M5",            # Timeframe: M1, M5, M15, M30, H1, H4, D1
    "volume": 0.01,               # Ukuran lot per order (atau 'lot')
    "max_positions": 1,           # Maksimal posisi terbuka bersamaan

    # Stop Loss & Take Profit
    "sl_points": 300,             # Stop Loss dalam points
    "tp_points": 600,             # Take Profit dalam points
    "risk_reward_ratio": 2.0,     # Hitung TP = SL * 2.0 (rasio RR)
    "atr_sl_mult": 1.5,           # SL dinamis = 1.5 * ATR candle terakhir
    "atr_tp_mult": 3.0,           # TP dinamis = 3.0 * ATR candle terakhir

    # Trailing Stop & Break-Even
    "trailing_stop_points": 200,  # Trailing stop aktif di 200 pts (0 = off)
    "trailing_step_points": 50,   # Step pergerakan trailing
    "break_even_points": 150,     # Geser SL ke entry saat profit 150 pts
    "break_even_offset_points": 10,# Lock profit 10 pts di atas entry

    # Waktu & Sesi Trading
    "trade_start_time": "13:00",  # Jam buka trading (format "HH:MM" UTC)
    "trade_end_time": "21:00",    # Jam tutup trading (format "HH:MM" UTC)
    "close_friday_hour": 20,      # Tutup posisi Jumat jam 20 UTC (anti-gap akhir pekan)
    "active_days": [0, 1, 2, 3, 4], # Hari trading aktif: 0=Senin .. 4=Jumat

    # Kontrol Entry & Anti-Spam
    "close_on_reversal": True,    # Tutup posisi berlawanan saat sinyal baru muncul
    "one_trade_per_bar": True,    # Maksimal 1 trade per bar candle
    "cooldown_bars": 2,           # Jeda 2 bar sebelum order baru boleh dibuka
    "min_margin_level": 200.0,    # Batas minimal Margin Level (%) untuk buka order
    "max_holding_bars": 24,       # Auto exit posisi jika terbuka > 24 bar
    "max_spread_points": 35,      # Toleransi spread maksimum (points)
}
```

#### Tabel Variabel `SETTINGS` Lengkap:
| Kategori | Nama Variabel | Tipe | Contoh / Default | Penjelasan |
|---|---|---|---|---|
| **Pasar & Simbol** | `symbol` | `str` | `"EURUSDm"` | Simbol broker aktif (Exness berakhiran `m`) |
| | `timeframe` | `str` | `"M5"` | Timeframe candle (`M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`) |
| | `volume` / `lot` | `float` | `0.01` | Ukuran lot tetap per order |
| | `risk_per_trade` | `float` | `0.01` | Fraksi risiko per trade jika lot dihitung dari SL (1% = 0.01) |
| | `max_positions` | `int` | `1` | Maksimal posisi terbuka bersamaan pada simbol ini |
| | `magic_number` | `int` | `100200` | ID unik bot pada tiket MT5 |
| | `comment` | `str` | `"XAVIQ Script"` | Label komentar order di terminal broker |
| **SL / TP & Rasio** | `sl_points` | `int` | `300` | Jarak Stop Loss dalam points |
| | `tp_points` | `int` | `600` | Jarak Take Profit dalam points |
| | `risk_reward_ratio`| `float` | `2.0` | Menghitung otomatis TP = SL * rasio |
| | `atr_sl_mult` | `float` | `1.5` | SL dinamis berbasis volatilitas (`SL = mult * ATR`) |
| | `atr_tp_mult` | `float` | `3.0` | TP dinamis berbasis volatilitas (`TP = mult * ATR`) |
| | `sl_tp_mode` | `str` | `"points"` | `"points"` atau `"percent"` |
| **Trailing & BE** | `trailing_stop_points`| `int`| `200` | Jarak trailing stop points (0 = nonaktif) |
| | `trailing_step_points`| `int`| `50` | Step penggeseran trailing stop |
| | `break_even_points`| `int` | `150` | Ambang batas profit points untuk geser SL ke entry |
| | `break_even_offset_points`|`int`|`10` | Jarak pengunci profit di atas/bawah harga entry |
| | `virtual_sltp_enabled`| `bool`| `False` | Virtual SL/TP (sembunyi dari broker) |
| **Waktu & Sesi** | `trade_start_time` | `str` | `"13:00"` | Jam mulai trading (format `"HH:MM"` UTC) |
| | `trade_end_time` | `str` | `"21:00"` | Jam selesai trading (format `"HH:MM"` UTC) |
| | `close_friday_hour`| `int` | `20` | Tutup semua posisi pada jam UTC hari Jumat sebelum libur |
| | `active_days` | `list` | `[0,1,2,3,4]` | Hari aktif trading (0=Senin, 4=Jumat, dll) |
| **Kontrol & Anti-Spam**| `close_on_reversal`|`bool`| `True` | Tutup posisi lama yang berlawanan saat ada sinyal baru |
| | `one_trade_per_bar`|`bool`| `True` | Batasi maksimal 1 trade per bar candle |
| | `cooldown_bars` | `int` | `2` | Jeda candle bar antar pembukaan order |
| | `min_margin_level` | `float`| `200.0` | Margin level minimum akun (%) untuk boleh entry |
| | `max_holding_bars`| `int` | `24` | Auto exit posisi jika berumur lebih dari N bar |
| | `max_slippage_points`| `int`| `30` | Toleransi slippage pergeseran harga |
| **Proteksi Global** | `max_spread_points`| `int`| `35` | Filter spread maksimal (points) |
| | `daily_drawdown_limit`|`float`| `0.05` | Batas rugi harian (5%) |
| | `equity_stop_loss` | `float`| `0.10` | Drawdown equity maksimal sebelum stop bot (10%) |
| | `max_consecutive_losses`|`int`| `3` | Batas rugi berturut-turut |
| | `max_daily_trades` | `int` | `10` | Batas total trade per hari |
| | `max_exposure_lots`| `float`| `1.0` | Batas total lot terbuka seluruh posisi bot |

> **Keuntungan**: Saat Anda memanggil `return ctx.buy()` atau `return ctx.sell()`, bot secara otomatis menggunakan `volume`, `sl_points`, dan `tp_points` yang telah didefinisikan di `SETTINGS`. Anda tidak perlu lagi mengisi kolom input form satu per satu di UI! Anda juga bisa membuka tombol **Variabel SETTINGS** di UI editor untuk melihat referensi dan menyisipkannya langsung.

### Parameter Strategi (`PARAMS`)
Anda dapat mendefinisikan parameter strategi menggunakan salah satu dari dua cara:

**Opsi 1: Kamus Python Sederhana (Direkomendasikan)**:
```python
PARAMS = {
    "fast": 12,
    "slow": 26,
    "threshold": 0.5,
}
```
Diakses di skrip dengan sangat fleksibel via dot notation (`ctx.params.fast`) ataupun dict indexing (`ctx.params["fast"]`).

**Opsi 2: Skema List (Format Form UI Tradisional)**:
```python
PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int",   "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int",   "default": 26, "min": 2},
]
```

---

## 3. Objek `ctx`

Deret harga (urutan **lama → baru**, elemen terakhir = bar terbaru):

| Properti | Keterangan |
|----------|------------|
| `ctx.open`   | daftar harga open |
| `ctx.high`   | daftar harga high |
| `ctx.low`    | daftar harga low |
| `ctx.close`  | daftar harga close |
| `ctx.volume` | daftar tick volume |
| `ctx.params` | parameter strategi (`ctx.params.fast` atau `ctx.params["fast"]`) |
| `ctx.settings` | konfigurasi aktif (`ctx.settings.symbol`, `ctx.settings.volume`, dll) |
| `ctx.position` | info posisi simbol ini (dict) atau `None` |
| `ctx.positions`| daftar seluruh posisi aktif simbol ini |
| `ctx.balance`  | saldo akun terkini (balance) |
| `ctx.equity`   | ekuitas akun terkini (equity) |
| `ctx.margin`   | margin terpakai (used margin) |
| `ctx.free_margin`| margin bebas (free margin) |
| `ctx.margin_level`| rasio margin level akun dalam % (`equity / margin * 100`) |
| `ctx.floating_profit` / `ctx.unrealized_profit` | total floating profit/loss posisi saat ini |
| `ctx.log(msg)` | tulis pesan ke log bot |

### Indikator (mengembalikan list selaras `close`)

| Fungsi | Hasil |
|--------|-------|
| `ctx.sma(src, n)` | Simple Moving Average |
| `ctx.ema(src, n)` | Exponential Moving Average |
| `ctx.rsi(src, n)` | RSI (0–100) |
| `ctx.atr(n)` | Average True Range (pakai high/low/close internal) |
| `ctx.stdev(src, n)` | standar deviasi bergulir |
| `ctx.highest(src, n)` | nilai tertinggi n bar |
| `ctx.lowest(src, n)` | nilai terendah n bar |
| `ctx.bbands(src, n, mult)` | tuple `(upper, mid, lower)` Bollinger Bands |
| `ctx.macd(src, fast, slow, signal)` | tuple `(macd, signal, hist)` |
| `ctx.wma(src, n)` | Weighted Moving Average (bobot linier) |
| `ctx.stochastic(k=14, d=3, smooth=3)` | tuple `(%K, %D)` Stochastic (0–100) |
| `ctx.adx(n=14)` | tuple `(ADX, +DI, -DI)` kekuatan & arah tren |
| `ctx.cci(n=20)` | Commodity Channel Index |
| `ctx.vwap(n=14)` | Volume Weighted Average Price (bergulir n bar) |
| `ctx.williams_r(n=14)` | Williams %R (-100..0) |
| `ctx.obv()` | On-Balance Volume (kumulatif) |
| `ctx.mfi(n=14)` | Money Flow Index (0..100) |
| `ctx.donchian(n=20)` | tuple `(upper, mid, lower)` Donchian Channel |
| `ctx.parabolic_sar(step=0.02, max_step=0.2)` | list nilai Parabolic SAR |
| `ctx.supertrend(n=10, mult=3.0)` | tuple `(garis, arah)` (arah +1 naik / -1 turun) |
| `ctx.ichimoku(tenkan=9, kijun=26, senkou=52)` | tuple `(tenkan, kijun, senkou_a, senkou_b, chikou)` |
| `ctx.pivot_points()` | dict `{pivot, r1, s1, r2, s2, r3, s3}` (dari bar terakhir) |

> `stochastic`, `adx`, `cci`, `vwap` memakai high/low/close/volume internal
> (tidak perlu argumen `src`).

### Deteksi silang (bool, pada bar terakhir)

| Fungsi | Arti |
|--------|------|
| `ctx.crossover(a, b)` | `True` bila `a` memotong ke **atas** `b` |
| `ctx.crossunder(a, b)` | `True` bila `a` memotong ke **bawah** `b` |

### Perintah order (kontrol dari dalam skrip — gaya cBot)

Skrip bisa mengontrol SL/TP, volume, dan risiko langsung dari kode (mirip
`ExecuteMarketOrder` di cBot), lewat `ctx.buy(...)` / `ctx.sell(...)`:

| Parameter | Arti |
|-----------|------|
| `volume` | lot tetap (mis. `0.1`). Bila diisi, mengabaikan perhitungan risiko. |
| `risk` | fraksi risiko (mis. `0.01` = 1%) untuk menghitung lot dari jarak SL. |
| `sl_points` / `tp_points` | SL/TP dalam points relatif dari harga entry. |
| `sl` / `tp` | SL/TP sebagai **harga absolut** (mengalahkan points). |
| `comment` | komentar order (opsional). |

Contoh:
```python
def on_bar(ctx):
    if ctx.crossover(ctx.ema(ctx.close, 12), ctx.ema(ctx.close, 26)):
        return ctx.buy(volume=0.1, sl_points=300, tp_points=600)
    if ctx.crossunder(ctx.ema(ctx.close, 12), ctx.ema(ctx.close, 26)):
        return ctx.sell(risk=0.01, sl=1.2345, tp=1.2000)  # lot dari 1% risiko, SL/TP harga
    return None
```

**Prioritas nilai:** intent skrip → parameter strategi → pengaturan global (tab Manual).
Jadi kalau skrip tidak menyebut `volume`/`sl`/`tp`, bot memakai pengaturan risiko
global. Kamu tetap bisa pakai gaya sederhana `return "BUY"` / `"SELL"` yang
sepenuhnya mengikuti pengaturan global.

### Menutup & memodifikasi posisi dari skrip

| Fungsi | Arti |
|--------|------|
| `ctx.close_position(pos=None)` | tutup satu posisi (default: posisi aktif simbol ini) |
| `ctx.close_all()` | tutup semua posisi simbol ini |
| `ctx.modify(pos=None, sl=..., tp=...)` | ubah SL/TP posisi (harga absolut) |

Kembalikan **satu** perintah, atau **list** perintah untuk beberapa aksi sekaligus:
```python
def on_bar(ctx):
    # keluar saat sinyal berbalik, lalu buka arah baru
    if ctx.position and kondisi_balik:
        return [ctx.close_position(ctx.position), ctx.sell(volume=0.1)]
    ...
```
Catatan: perintah CLOSE/MODIFY dijalankan walau batas posisi tercapai; hanya
BUY/SELL yang dibatasi "Maks Posisi".

### Harga live & waktu/sesi

| Properti | Arti |
|----------|------|
| `ctx.bid`, `ctx.ask` | harga live saat ini |
| `ctx.spread` | spread dalam points |
| `ctx.point`, `ctx.digits` | ukuran 1 point & jumlah desimal simbol |
| `ctx.time` | waktu bar terakhir (datetime broker) atau None |
| `ctx.now` | waktu sekarang (UTC) |
| `ctx.hour`, `ctx.minute`, `ctx.weekday` | pintasan sesi (weekday: 0=Senin..6=Minggu) |

Contoh filter sesi & spread:
```python
def on_bar(ctx):
    if ctx.weekday >= 5:            # hindari akhir pekan
        return None
    if ctx.spread > 30:            # tolak saat spread lebar
        return None
    ...
```

> Nilai indikator bisa berisi `None` di awal deret (periode belum penuh). Selalu
> cek panjang deret bila perlu, mis. `if len(r) < 2: return None`.

---

## 4. Contoh

### EMA Crossover
```python
PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 26, "min": 2},
]

def on_bar(ctx):
    fast = ctx.ema(ctx.close, ctx.params["fast"])
    slow = ctx.ema(ctx.close, ctx.params["slow"])
    if ctx.crossover(fast, slow):
        return "BUY"
    if ctx.crossunder(fast, slow):
        return "SELL"
    return None
```

> Folder skrip strategi bawaan saat ini dikosongkan untuk persiapan strategi baru. Anda dapat membuat dan menyimpan skrip strategi kustom sendiri di tab **Programmer Studio**.

---

## 5. Batasan Sandbox (Keamanan)

Demi keamanan, skrip berjalan dalam sandbox terbatas. Hal berikut **diblokir**:

- `import` / `from ... import ...`
- `eval`, `exec`, `compile`, `__import__`, `open`, `input`
- `globals`, `locals`, `vars`, `getattr`, `setattr`, `delattr`, `type`
- Akses atribut/nama dunder (mis. `obj.__class__`, `__globals__`)
- Akses file, jaringan, atau sistem operasi

Perlindungan tambahan:

- **Fail-safe:** error sintaks/runtime pada skrip **tidak** membuat bot crash —
  ditangkap, dicatat di log, dan diperlakukan sebagai "tanpa sinyal" (`None`).
- **Anti loop tak terbatas:** eksekusi `on_bar` dibatasi jumlah langkah; skrip yang
  terjebak loop (mis. `while True`) akan dihentikan otomatis dan dianggap tanpa sinyal.

Builtins yang **diizinkan**: `abs, min, max, round, len, range, sum, float, int,
bool, str, enumerate, sorted, zip, map, filter, all, any`.

---

## 6. Tips

- Kembalikan `None` sesering mungkin; hanya kembalikan `"BUY"`/`"SELL"` saat syarat
  entry benar-benar terpenuhi.
- Gunakan `ctx.position` untuk menghindari menumpuk posisi:
  ```python
  if ctx.position and ctx.position.get("volume", 0) > 0:
      return None
  ```
- Cek panjang deret indikator sebelum mengindeks `[-2]`/`[-1]`.
- Manfaatkan `ctx.log(...)` untuk men-debug logika saat menjalankan di demo.
