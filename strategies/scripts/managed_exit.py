"""Contoh lanjutan: kelola posisi sendiri (buka, tutup, modifikasi) + filter.

Menunjukkan fitur baru:
  - ctx.bid / ctx.ask / ctx.spread  -> filter spread & harga live
  - ctx.hour / ctx.weekday          -> filter sesi (hindari akhir pekan/jam sepi)
  - ctx.close(pos) / ctx.modify(pos)-> tutup & geser SL dari dalam skrip
  - kembalikan LIST perintah untuk beberapa aksi sekaligus
"""

PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 26, "min": 2},
    {"key": "lot", "label": "Volume (lot)", "type": "float", "default": 0.1, "min": 0.01},
    {"key": "max_spread", "label": "Max Spread (pts)", "type": "int", "default": 30, "min": 0},
]


def on_bar(ctx):
    # Filter sesi: jangan trading di akhir pekan (5=Sabtu, 6=Minggu).
    if ctx.weekday >= 5:
        return None
    # Filter spread: tolak bila spread melebar (kondisi pasar buruk).
    max_spread = ctx.params["max_spread"]
    if max_spread and ctx.spread and ctx.spread > max_spread:
        return None

    fast = ctx.ema(ctx.close, ctx.params["fast"])
    slow = ctx.ema(ctx.close, ctx.params["slow"])
    lot = ctx.params["lot"]

    up = ctx.crossover(fast, slow)
    down = ctx.crossunder(fast, slow)

    # Jika sudah ada posisi: keluar saat sinyal berbalik arah.
    if ctx.position:
        ptype = ctx.position.get("type")
        if (ptype == "BUY" and down) or (ptype == "SELL" and up):
            return ctx.close_position(ctx.position)
        return None

    # Belum ada posisi: buka sesuai sinyal, SL/TP dikontrol skrip.
    if up:
        return ctx.buy(volume=lot, sl_points=300, tp_points=600)
    if down:
        return ctx.sell(volume=lot, sl_points=300, tp_points=600)
    return None
