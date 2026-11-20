"""Contoh gaya cBot: skrip mengontrol volume & SL/TP sendiri.

Semua eksekusi (lot, stop loss, take profit) ditentukan di dalam skrip lewat
ctx.buy()/ctx.sell() — mirip ExecuteMarketOrder di cBot cTrader.
"""

PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 10, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 30, "min": 2},
    {"key": "lot", "label": "Volume (lot)", "type": "float", "default": 0.1, "min": 0.01},
    {"key": "sl_pts", "label": "Stop Loss (pts)", "type": "int", "default": 250, "min": 10},
    {"key": "tp_pts", "label": "Take Profit (pts)", "type": "int", "default": 500, "min": 10},
]


def on_bar(ctx):
    # Jangan menambah posisi bila sudah ada posisi terbuka di simbol ini.
    if ctx.position and ctx.position.get("volume", 0) > 0:
        return None

    fast = ctx.ema(ctx.close, ctx.params["fast"])
    slow = ctx.ema(ctx.close, ctx.params["slow"])
    lot = ctx.params["lot"]
    sl = ctx.params["sl_pts"]
    tp = ctx.params["tp_pts"]

    if ctx.crossover(fast, slow):
        ctx.log("EMA cross UP -> BUY (script-controlled)")
        return ctx.buy(volume=lot, sl_points=sl, tp_points=tp)
    if ctx.crossunder(fast, slow):
        ctx.log("EMA cross DOWN -> SELL (script-controlled)")
        return ctx.sell(volume=lot, sl_points=sl, tp_points=tp)
    return None
