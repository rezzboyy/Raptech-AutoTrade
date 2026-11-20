"""Contoh skrip strategi: Bollinger Bands Breakout.

BUY saat harga menembus ke ATAS upper band; SELL saat menembus ke BAWAH lower band.
(Strategi trend-following; untuk mean-reversion, balik logikanya.)
"""

PARAMS = [
    {"key": "period", "label": "Periode", "type": "int", "default": 20, "min": 2},
    {"key": "mult", "label": "Deviasi (x)", "type": "float", "default": 2.0, "min": 0.1},
]


def on_bar(ctx):
    upper, mid, lower = ctx.bbands(ctx.close, ctx.params["period"], ctx.params["mult"])
    if len(upper) < 2:
        return None

    price = ctx.close[-1]
    prev = ctx.close[-2]

    # Breakout naik: bar sebelumnya di dalam band, sekarang menembus upper.
    if prev <= upper[-2] and price > upper[-1]:
        return "BUY"
    # Breakout turun: menembus lower band.
    if prev >= lower[-2] and price < lower[-1]:
        return "SELL"
    return None
