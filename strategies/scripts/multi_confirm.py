"""Contoh skrip strategi: Multi-Konfirmasi (Tren + Momentum + MACD).

Hanya entry bila SEMUA syarat searah:
  - BUY : harga di atas EMA tren, RSI di atas ambang, MACD histogram positif & naik.
  - SELL: kebalikannya.
Menghindari menambah posisi bila sudah ada posisi terbuka di simbol ini.
"""

PARAMS = [
    {"key": "trend", "label": "EMA Tren", "type": "int", "default": 100, "min": 5},
    {"key": "rsi_period", "label": "Periode RSI", "type": "int", "default": 14, "min": 2},
    {"key": "rsi_level", "label": "Ambang RSI", "type": "float", "default": 50.0},
]


def on_bar(ctx):
    # Jangan menumpuk posisi.
    if ctx.position and ctx.position.get("volume", 0) > 0:
        return None

    ema_trend = ctx.ema(ctx.close, ctx.params["trend"])
    rsi = ctx.rsi(ctx.close, ctx.params["rsi_period"])
    macd, signal, hist = ctx.macd(ctx.close, 12, 26, 9)
    if len(hist) < 2 or len(ema_trend) < 1:
        return None

    price = ctx.close[-1]
    lvl = ctx.params["rsi_level"]
    hist_rising = hist[-1] > hist[-2]

    up = price > ema_trend[-1] and rsi[-1] > lvl and hist[-1] > 0 and hist_rising
    down = price < ema_trend[-1] and rsi[-1] < lvl and hist[-1] < 0 and not hist_rising

    if up:
        ctx.log("Semua konfirmasi bullish -> BUY")
        return "BUY"
    if down:
        ctx.log("Semua konfirmasi bearish -> SELL")
        return "SELL"
    return None
