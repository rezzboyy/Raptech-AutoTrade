"""Contoh: SuperTrend + Ichimoku (filter tren kuat).

Entry hanya saat SuperTrend & posisi harga terhadap awan Ichimoku searah.
Menutup posisi saat arah SuperTrend berbalik. SL/TP dikontrol dari skrip.
"""

PARAMS = [
    {"key": "st_period", "label": "SuperTrend Periode", "type": "int", "default": 10, "min": 1},
    {"key": "st_mult", "label": "SuperTrend Deviasi", "type": "float", "default": 3.0, "min": 0.1},
    {"key": "lot", "label": "Volume (lot)", "type": "float", "default": 0.1, "min": 0.01},
]


def on_bar(ctx):
    st, direction = ctx.supertrend(ctx.params["st_period"], ctx.params["st_mult"])
    tenkan, kijun, senkou_a, senkou_b, chikou = ctx.ichimoku()
    if direction[-1] is None or senkou_a[-1] is None or senkou_b[-1] is None:
        return None

    price = ctx.close[-1]
    cloud_top = max(senkou_a[-1], senkou_b[-1])
    cloud_bot = min(senkou_a[-1], senkou_b[-1])
    up = direction[-1] == 1 and price > cloud_top
    down = direction[-1] == -1 and price < cloud_bot

    # Kelola posisi: tutup saat arah SuperTrend berbalik.
    if ctx.position:
        ptype = ctx.position.get("type")
        if (ptype == "BUY" and direction[-1] == -1) or (ptype == "SELL" and direction[-1] == 1):
            return ctx.close_position(ctx.position)
        return None

    lot = ctx.params["lot"]
    if up:
        return ctx.buy(volume=lot, sl_points=400, tp_points=800)
    if down:
        return ctx.sell(volume=lot, sl_points=400, tp_points=800)
    return None
