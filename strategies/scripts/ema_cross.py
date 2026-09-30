"""Contoh skrip strategi: EMA Crossover.

BUY saat EMA cepat memotong ke ATAS EMA lambat; SELL saat memotong ke BAWAH.
"""

PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 26, "min": 2},
]


def on_bar(ctx):
    fast = ctx.ema(ctx.close, ctx.params["fast"])
    slow = ctx.ema(ctx.close, ctx.params["slow"])

    if ctx.crossover(fast, slow):
        ctx.log("EMA cross UP -> BUY")
        return "BUY"
    if ctx.crossunder(fast, slow):
        ctx.log("EMA cross DOWN -> SELL")
        return "SELL"
    return None
