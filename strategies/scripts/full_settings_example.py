"""Strategi Contoh: Mode Programmer Full Settings.

Semua konfigurasi (simbol, timeframe, lot, SL, TP, trailing stop, break-even,
sesi waktu, rasio RR, filter margin, dan anti-spam bar) diatur langsung dari skrip ini!
Tidak perlu lagi menginput form/kolom satu per satu di UI.
"""

# 1. Konfigurasi trading terpusat
SETTINGS = {
    # Pasar & Simbol
    "symbol": "EURUSDm",          # Simbol Exness (suffix 'm')
    "timeframe": "M5",            # Timeframe: M1, M5, M15, M30, H1, H4, D1
    "volume": 0.01,               # Ukuran lot per trade
    "max_positions": 1,           # Maksimal posisi terbuka bersamaan

    # Stop Loss & Take Profit
    "sl_points": 250,             # Stop Loss (jarak points)
    "risk_reward_ratio": 2.0,     # TP otomatis 2x SL (500 pts)
    "trailing_stop_points": 150,  # Trailing stop aktif di 150 pts
    "trailing_step_points": 30,   # Step pergerakan trailing
    "break_even_points": 120,     # Break-even aktif saat profit 120 pts
    "break_even_offset_points": 15,# Kunci profit 15 pts di atas entry

    # Waktu & Sesi Trading
    "trade_start_time": "07:00",  # Jam buka trading (UTC)
    "trade_end_time": "21:00",    # Jam tutup trading (UTC)
    "close_friday_hour": 20,      # Tutup posisi hari Jumat jam 20 UTC
    "active_days": [0, 1, 2, 3, 4], # Senin s/d Jumat

    # Kontrol Entry & Anti-Spam Bar
    "close_on_reversal": True,    # Tutup posisi berlawanan saat sinyal baru
    "one_trade_per_bar": True,    # Maksimal 1 trade per bar candle
    "cooldown_bars": 2,           # Jeda minimal 2 bar antar trade
    "min_margin_level": 200.0,    # Minimal margin level 200%
    "max_holding_bars": 24,       # Auto exit jika posisi terbuka > 24 bar
    "max_spread_points": 35,      # Toleransi spread maks 35 pts
    "comment": "XAVIQ Full Settings",
}

# 2. Parameter strategi (bisa berupa dictionary langsung!)
PARAMS = {
    "ema_fast": 9,
    "ema_slow": 21,
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
}


def on_bar(ctx):
    """Logika strategi per bar penutupan."""
    # Bisa cek metrik live akun langsung dari ctx
    if ctx.margin_level > 0 and ctx.margin_level < 250:
        ctx.log(f"Margin level tipis: {ctx.margin_level:.1f}%, floating PnL: {ctx.floating_profit:.2f}")

    # Akses parameter via dot-notation (ctx.params.ema_fast) atau dict
    fast = ctx.ema(ctx.close, ctx.params.ema_fast)
    slow = ctx.ema(ctx.close, ctx.params.ema_slow)
    rsi_vals = ctx.rsi(ctx.close, ctx.params.rsi_period)

    # Indikator belum siap (bar awal)
    if len(fast) < 2 or len(slow) < 2 or not rsi_vals or rsi_vals[-1] is None:
        return None

    current_rsi = rsi_vals[-1]

    # Sinyal BUY: Golden cross EMA & RSI belum overbought
    if ctx.crossover(fast, slow) and current_rsi < ctx.params.rsi_overbought:
        ctx.log(f"Golden cross terdeteksi, RSI={current_rsi:.1f}. Membuka BUY.")
        # ctx.buy() otomatis memakai volume, sl_points, tp_points dari SETTINGS!
        return ctx.buy()

    # Sinyal SELL: Death cross EMA & RSI belum oversold
    if ctx.crossunder(fast, slow) and current_rsi > ctx.params.rsi_oversold:
        ctx.log(f"Death cross terdeteksi, RSI={current_rsi:.1f}. Membuka SELL.")
        return ctx.sell()

    return None
