# Skrip Strategi Kustom (Programmer Mode)

Folder ini berisi **skrip strategi contoh** untuk fitur *Strategy Programmer Mode*
(lihat `tasknext.md`). Skrip dijalankan bot dalam sandbox aman.

## Kontrak skrip
- Deklarasikan `PARAMS` (opsional) — daftar parameter yang muncul di UI.
- Implementasikan `on_bar(ctx)` yang mengembalikan `"BUY"`, `"SELL"`, atau `None`.
- TIDAK boleh `import`, akses file/OS, `eval`/`exec` (diblokir sandbox).

## Objek `ctx`
- Deret harga (lama → baru): `ctx.open`, `ctx.high`, `ctx.low`, `ctx.close`, `ctx.volume`
- Parameter: `ctx.params["key"]`
- Info posisi simbol ini: `ctx.position` (dict `{type, volume, price_open, sl, tp, profit}` atau `None`), `ctx.positions` (list semua posisi simbol ini)
- Info akun: `ctx.balance`, `ctx.equity`, `ctx.symbol`
- Harga live: `ctx.bid`, `ctx.ask`, `ctx.spread` (points), `ctx.point`, `ctx.digits`
- Waktu/sesi: `ctx.time`, `ctx.now`, `ctx.hour`, `ctx.minute`, `ctx.weekday` (0=Senin..6=Minggu)
- Perintah order (gaya cBot): `ctx.buy(...)` / `ctx.sell(...)` dengan `volume`, `risk`, `sl_points`, `tp_points`, `sl`, `tp`, `comment`
- Kelola posisi: `ctx.close_position(pos)`, `ctx.close_all()`, `ctx.modify(pos, sl=..., tp=...)`
- Bisa kembalikan satu perintah atau **list** perintah (beberapa aksi sekaligus)
- Log: `ctx.log("pesan")`
- Indikator (mengembalikan list selaras `close`):
  `ctx.sma(src, n)`, `ctx.ema(src, n)`, `ctx.rsi(src, n)`, `ctx.atr(n)`,
  `ctx.stdev(src, n)`, `ctx.highest(src, n)`, `ctx.lowest(src, n)`,
  `ctx.bbands(src, n, mult) -> (upper, mid, lower)`,
  `ctx.macd(src, fast, slow, signal) -> (macd, signal, hist)`,
  `ctx.wma(src, n)`, `ctx.stochastic(k, d, smooth) -> (%K, %D)`,
  `ctx.adx(n) -> (ADX, +DI, -DI)`, `ctx.cci(n)`, `ctx.vwap(n)`,
  `ctx.williams_r(n)`, `ctx.obv()`, `ctx.mfi(n)`, `ctx.donchian(n) -> (upper, mid, lower)`,
  `ctx.parabolic_sar(step, max_step)`, `ctx.supertrend(n, mult) -> (garis, arah)`,
  `ctx.ichimoku(...) -> (tenkan, kijun, senkou_a, senkou_b, chikou)`, `ctx.pivot_points() -> dict`
- Sinyal silang: `ctx.crossover(a, b)`, `ctx.crossunder(a, b)` (bool, pada bar terakhir)

> Catatan: nama/daftar API bisa disesuaikan saat implementasi Tahap 1.

## Koleksi Skrip Strategi Tersedia
- `btc_fast_cycle_recovery.py` — **BTC Fast Scalper & Adaptive Recovery** (Khusus Bitcoin BTCUSDm 24/7, skala poin aman bebas Error #10016, instant entry, adaptif EMA / reversal loss recovery).
- `fast_cycle_recovery.py` — **Fast Cycle & Adaptive Recovery** (Eksekusi cepat BUY/SELL, siklus kontinu, recovery cepat adaptif tren pasar + batas pengaman lot & steps).
- `safe_precision_scalper.py` — **Safe Precision Scalper Pro** (3 konfirmasi: EMA 200, EMA 8/21, Stoch Pullback + 5 proteksi risiko & ATR SL/TP).
- `full_settings_example.py` — Contoh lengkap Mode Programmer dengan konfigurasi trading terpusat (`SETTINGS`).
- `cbot_style.py` — Eksekusi gaya cBot dengan volume dan SL/TP langsung di skrip.
- `managed_exit.py` — Manajemen posisi manual (tutup sinyal balik & filter spread).
- `ema_cross.py` — Golden cross & Death cross EMA klasik.
- `rsi_reversal.py` — Reversal oversold/overbought RSI.
- `bollinger_breakout.py` — Breakout pita Bollinger Bands.
- `stoch_adx.py` — Filter tren kuat ADX + trigger Stochastic.
- `supertrend_ichimoku.py` — Kombinasi Supertrend & Ichimoku Kinko Hyo.
- `multi_confirm.py` — Multi-indikator konfirmasi 3 lapis.

