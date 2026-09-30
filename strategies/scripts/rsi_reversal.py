"""Contoh skrip strategi: RSI Reversal.

BUY saat RSI keluar dari area oversold; SELL saat keluar dari area overbought.
"""

PARAMS = [
    {"key": "period", "label": "Periode RSI", "type": "int", "default": 14, "min": 2},
    {"key": "oversold", "label": "Oversold", "type": "float", "default": 30.0},
    {"key": "overbought", "label": "Overbought", "type": "float", "default": 70.0},
]


def on_bar(ctx):
    r = ctx.rsi(ctx.close, ctx.params["period"])
    if len(r) < 2:
        return None

    prev, now = r[-2], r[-1]
    os_level = ctx.params["oversold"]
    ob_level = ctx.params["overbought"]

    # Naik menembus keluar dari oversold -> sinyal beli.
    if prev < os_level <= now:
        return "BUY"
    # Turun menembus keluar dari overbought -> sinyal jual.
    if prev > ob_level >= now:
        return "SELL"
    return None
