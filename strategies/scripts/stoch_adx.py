"""Contoh: Stochastic + ADX (filter tren + momentum).

Masuk hanya saat tren cukup kuat (ADX di atas ambang) DAN searah dengan
Stochastic keluar dari area jenuh. SL/TP dikontrol dari skrip.
"""

PARAMS = [
    {"key": "adx_min", "label": "ADX Minimum", "type": "float", "default": 20.0, "min": 0},
    {"key": "k", "label": "Stoch %K", "type": "int", "default": 14, "min": 1},
    {"key": "lot", "label": "Volume (lot)", "type": "float", "default": 0.1, "min": 0.01},
]


def on_bar(ctx):
    if ctx.position and ctx.position.get("volume", 0) > 0:
        return None

    k, d = ctx.stochastic(ctx.params["k"], 3, 3)
    a, plus_di, minus_di = ctx.adx(14)
    if k[-1] is None or a[-1] is None:
        return None

    lot = ctx.params["lot"]
    strong_trend = a[-1] >= ctx.params["adx_min"]

    # Tren naik kuat + Stochastic bangkit dari oversold -> BUY.
    if strong_trend and plus_di[-1] > minus_di[-1] and k[-1] > 20 and k[-2] is not None and k[-2] <= 20:
        return ctx.buy(volume=lot, sl_points=300, tp_points=600)
    # Tren turun kuat + Stochastic jatuh dari overbought -> SELL.
    if strong_trend and minus_di[-1] > plus_di[-1] and k[-1] < 80 and k[-2] is not None and k[-2] >= 80:
        return ctx.sell(volume=lot, sl_points=300, tp_points=600)
    return None
