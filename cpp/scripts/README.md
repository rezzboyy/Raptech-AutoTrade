# Skrip Mode Programmer (JavaScript / QJSEngine)

Versi C++ memakai **JavaScript** (QJSEngine) sebagai bahasa skrip Mode Programmer,
menggantikan Python di versi lama. Kontraknya setara.

## Kontrak skrip
- Definisikan `SETTINGS` (opsional): objek pengaturan trading (symbol, timeframe,
  volume/lot, sl_points, tp_points, max_positions, dst). Diselaraskan otomatis.
- Definisikan `PARAMS` (opsional): objek parameter strategi, diakses via `ctx.params`.
- Definisikan `function on_bar(ctx)` — dipanggil tiap bar.

`on_bar` boleh mengembalikan:
- `"BUY"` / `"SELL"` / `null`, atau
- perintah dari `ctx.*` (objek), atau
- array beberapa perintah (dieksekusi berurutan).

## API `ctx`
- Harga: `ctx.open/high/low/close/volume` (array, lama→baru)
- Live: `ctx.bid/ask/spread/point/digits/symbol`
- Akun/posisi: `ctx.balance/equity/margin/freeMargin/marginLevel`,
  `ctx.position` (posisi aktif atau null), `ctx.positions`
- Waktu: `ctx.hour/minute/weekday` (0=Senin..6=Minggu)
- `ctx.params`, `ctx.log(msg)`
- Indikator: `sma, ema, wma, rsi, stdev, highest, lowest, atr, bbands, macd,
  stochastic, adx, cci, vwap, williams_r, obv, mfi, donchian, parabolic_sar,
  supertrend, ichimoku, pivot_points, crossover, crossunder`
- Order: `ctx.buy(opts)`, `ctx.sell(opts)`, `ctx.close_position(opts)`,
  `ctx.close_all()`, `ctx.modify(opts)`
  - `opts` objek: `{volume, sl_points, tp_points, sl, tp, risk, comment, ticket}`
  - Tanpa argumen -> membaca nilai dari `SETTINGS`.

## Sandbox
- QJSEngine tidak punya akses file/OS/jaringan (hanya `ctx` + JS standar).
- Watchdog anti loop tak terbatas: eksekusi diinterupsi bila melewati batas waktu.
- Error skrip TIDAK meng-crash bot (fail-safe → dianggap tanpa sinyal).

## Contoh
- `ema_cross.js` — crossover EMA.
- `cbot_style.js` — kontrol posisi penuh gaya cBot.
- `managed_exit.js` — entry RSI + exit terkelola.
