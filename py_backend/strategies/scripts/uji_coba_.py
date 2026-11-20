"""Strategi kustom saya (Mode Programmer Full Settings).

Anda dapat mengatur SEMUA konfigurasi trading langsung dari skrip ini
tanpa harus mengisi kolom form satu per satu di UI!
"""

# Pengaturan trading lengkap (opsional, otomatis diselaraskan ke bot)
SETTINGS = {
    "symbol": "EURUSDm",          # Simbol aktif (mis. EURUSDm untuk Exness)
    "timeframe": "M5",            # M1, M5, M15, M30, H1, H4, D1
    "volume": 0.01,               # Ukuran lot per order (atau 'lot')
    "sl_points": 300,             # Stop Loss dalam points
    "tp_points": 600,             # Take Profit dalam points
    "max_positions": 1,           # Maksimal posisi terbuka bersamaan
    "trailing_stop_points": 200,  # Trailing stop points (0 = nonaktif)
    "trailing_step_points": 50,
    "break_even_points": 150,     # Break-even stop points (0 = nonaktif)
    "break_even_offset_points": 10,
    "max_spread_points": 35,      # Batas maksimal spread points (0 = nonaktif)
}

# Parameter strategi (bisa berupa list skema di bawah, atau dict sederhana {"fast": 12, "slow": 26})
PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 26, "min": 2},
]


def on_bar(ctx):
    # Akses parameter via ctx.params.fast atau ctx.params["fast"]
    fast = ctx.ema(ctx.close, ctx.params.fast)
    slow = ctx.ema(ctx.close, ctx.params.slow)

    # ctx.buy() & ctx.sell() otomatis memakai volume, sl, dan tp dari SETTINGS
    if ctx.crossover(fast, slow):
        return ctx.buy()
    if ctx.crossunder(fast, slow):
        return ctx.sell()

    return None
