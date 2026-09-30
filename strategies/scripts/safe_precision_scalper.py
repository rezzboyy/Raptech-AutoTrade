"""Strategi Scalping Presisi & Aman (Safe Precision Scalper Pro).

Dirancang khusus untuk Mode Programmer di XAVIQ Trading Engine.
Menggabungkan 3 lapis konfirmasi teknikal (Trend, Momentum, Pullback)
dan 5 pilar proteksi risiko terpadu untuk eksekusi scalping yang aman,
presisi, dan tahan banting di akun Exness / broker MT5 lainnya.

Pilar Konfirmasi Teknikal:
1. Macro Trend Filter : EMA 200 (Hanya BUY di atas EMA 200, hanya SELL di bawah EMA 200).
2. Micro Momentum     : EMA 8 vs EMA 21 (Memastikan momentum searah tren).
3. Pullback Trigger   : Stochastic Oscillator (%K/%D) memantul dari area jenuh (oversold/overbought).
4. Healthy Zone       : RSI 14 menyaring overextension agar tidak entry di pucuk/lembah ekstrim.
5. Volatility Shield  : ATR 14 menyaring pasar flat/sideways mati dan mengatur SL/TP dinamis.

Pilar Proteksi Risiko & Keamanan:
- Spread Protection   : Batalkan entry jika spread > toleransi maksimum (mencegah slippage & biaya bengkak).
- Anti-Rollover Guard : Hindari trading saat jam rollover malam (23:00 - 01:00 server) saat spread melebar.
- Weekend Gap Guard   : Hindari open posisi menjelang pasar tutup di akhir pekan (Jumat malam s/d Minggu).
- Capital & Margin    : Perlindungan margin level akun (hanya trade jika margin sehat).
- Strict Single-Order : Menghindari overtrading dan martil (maks 1 posisi per simbol).
- Emergency Invalidation Exit : Cut loss lebih dini jika momentum harga mendadak berbalik drastis.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS)
# Nilai di bawah otomatis tersinkronisasi ke kontrol bot saat skrip dimuat.
# ==============================================================================
SETTINGS = {
    # Instrumen & Timeframe
    "symbol": "EURUSDm",                 # Simbol standar Exness (suffix 'm')
    "timeframe": "M5",                   # Timeframe M5 ideal untuk scalping minim noise
    "volume": 0.01,                      # Lot aman untuk akun uji coba / scalping terukur
    "max_positions": 1,                  # Disiplin 1 posisi aktif saja per simbol

    # Stop Loss & Target Profit (Points)
    "sl_points": 120,                    # 12 pips Stop Loss
    "tp_points": 180,                    # 18 pips Take Profit (Risk:Reward ~ 1:1.5)
    "risk_reward_ratio": 1.5,

    # Proteksi Break-Even & Trailing Stop
    "break_even_enabled": True,          # Kunci profit modal saat posisi sudah floating positif
    "break_even_points": 60,             # Aktif setelah profit +60 points (6 pips)
    "break_even_offset_points": 10,      # Kunci 10 points di atas entry (menutup komisi/spread)
    "trailing_stop_enabled": True,       # Amankan cuan saat tren berlanjut panjang
    "trailing_stop_points": 80,          # Jarak trailing 80 points
    "trailing_step_points": 20,          # Geser tiap lompatan 20 points

    # Proteksi Akun Global
    "max_spread_points": 25,             # Toleransi maksimal spread (2.5 pips)
    "daily_drawdown_limit": 0.03,        # Hentikan bot jika drawdown harian mencapai 3%
    "equity_stop_loss": 0.05,            # Hentikan bot jika equity turun 5%
    "max_consecutive_losses": 3,         # Istirahat setelah 3x rugi beruntun
    "max_daily_trades": 15,              # Batasi maksimal 15 trade per hari
    "min_margin_level": 300.0,           # Margin level minimal 300%

    # Filter Waktu & Sesi (UTC)
    "trade_start_time": "07:00",         # Mulai sesi London yang likuid
    "trade_end_time": "20:00",           # Berakhir sebelum sesi New York tutup
    "close_friday_hour": 20,             # Tutup posisi Jumat jam 20 UTC (hindari weekend hold)
    "active_days": [0, 1, 2, 3, 4],      # Senin s/d Jumat saja

    # Anti-Spam Bar & Eksekusi
    "one_trade_per_bar": True,           # Maksimal 1 entry per bar candle
    "cooldown_bars": 2,                  # Beri jeda 2 bar setelah posisi tertutup
    "close_on_reversal": True,           # Tutup posisi lama jika sinyal berbalik tajam
    "comment": "SafeScalperPro",
}

# ==============================================================================
# 2. PARAMETER INDIKATOR (PARAMS)
# Muncul sebagai kontrol input di panel Parameter Mode Programmer.
# ==============================================================================
PARAMS = [
    {"key": "ema_trend", "label": "Trend Baseline (EMA)", "type": "int", "default": 200, "min": 50, "max": 500},
    {"key": "ema_fast", "label": "Fast Momentum (EMA)", "type": "int", "default": 8, "min": 3, "max": 30},
    {"key": "ema_slow", "label": "Slow Momentum (EMA)", "type": "int", "default": 21, "min": 10, "max": 60},
    {"key": "stoch_k", "label": "Stoch %K Period", "type": "int", "default": 14, "min": 5, "max": 40},
    {"key": "stoch_d", "label": "Stoch %D Period", "type": "int", "default": 3, "min": 2, "max": 15},
    {"key": "stoch_oversold", "label": "Stoch Oversold (BUY)", "type": "int", "default": 30, "min": 10, "max": 45},
    {"key": "stoch_overbought", "label": "Stoch Overbought (SELL)", "type": "int", "default": 70, "min": 55, "max": 90},
    {"key": "rsi_period", "label": "RSI Period", "type": "int", "default": 14, "min": 5, "max": 30},
    {"key": "rsi_max_buy", "label": "RSI Max Ceiling (BUY)", "type": "int", "default": 65, "min": 50, "max": 80},
    {"key": "rsi_min_sell", "label": "RSI Min Floor (SELL)", "type": "int", "default": 35, "min": 20, "max": 50},
    {"key": "atr_period", "label": "ATR Period", "type": "int", "default": 14, "min": 5, "max": 30},
    {"key": "min_atr_points", "label": "Min Volatilitas ATR (pts)", "type": "int", "default": 35, "min": 0, "max": 150},
    {"key": "use_dynamic_atr_sltp", "label": "Gunakan SL/TP Dinamis ATR (1/0)", "type": "int", "default": 1, "min": 0, "max": 1},
    {"key": "atr_sl_mult", "label": "ATR Multiplier SL", "type": "float", "default": 1.5, "min": 0.5, "max": 4.0},
    {"key": "atr_tp_mult", "label": "ATR Multiplier TP", "type": "float", "default": 2.2, "min": 0.8, "max": 6.0},
    {"key": "max_spread", "label": "Max Spread Tolerance (pts)", "type": "int", "default": 25, "min": 5, "max": 100},
]


def on_bar(ctx):
    """Logika evaluasi per penutupan bar candle."""
    # --------------------------------------------------------------------------
    # PROTEKSI 1: Filter Hari & Jam Trading Aman
    # --------------------------------------------------------------------------
    # Jangan trading di akhir pekan (5=Sabtu, 6=Minggu)
    if ctx.weekday >= 5:
        return None

    # Jumat malam mendekati penutupan pasar: hindari hold posisi di akhir pekan
    if ctx.weekday == 4 and ctx.hour >= 20:
        return None

    # Jam Rollover Midnight broker (23:00 - 00:59): spread biasanya melebar liar
    if ctx.hour in (23, 0):
        return None

    # --------------------------------------------------------------------------
    # PROTEKSI 2: Filter Spread Live Broker
    # --------------------------------------------------------------------------
    max_sp = ctx.params.get("max_spread", 25)
    if max_sp and ctx.spread and ctx.spread > max_sp:
        # Spread terlalu lebar, bahaya untuk scalping
        return None

    # --------------------------------------------------------------------------
    # PROTEKSI 3: Ketahanan Margin Akun
    # --------------------------------------------------------------------------
    if ctx.margin_level and 0 < ctx.margin_level < 300.0:
        ctx.log(f"Margin level tipis ({ctx.margin_level:.1f}%). Eksekusi ditahan.")
        return None

    # --------------------------------------------------------------------------
    # HITUNG INDIKATOR TEKNIKAL
    # --------------------------------------------------------------------------
    ema_trend_p = int(ctx.params.get("ema_trend", 200))
    ema_fast_p = int(ctx.params.get("ema_fast", 8))
    ema_slow_p = int(ctx.params.get("ema_slow", 21))

    # Pastikan data candle historis mencukupi
    min_required_bars = ema_trend_p + 10
    if len(ctx.close) < min_required_bars:
        return None

    trend = ctx.ema(ctx.close, ema_trend_p)
    fast = ctx.ema(ctx.close, ema_fast_p)
    slow = ctx.ema(ctx.close, ema_slow_p)

    rsi_p = int(ctx.params.get("rsi_period", 14))
    rsi_vals = ctx.rsi(ctx.close, rsi_p)

    stoch_k_p = int(ctx.params.get("stoch_k", 14))
    stoch_d_p = int(ctx.params.get("stoch_d", 3))
    k_vals, d_vals = ctx.stochastic(stoch_k_p, stoch_d_p, 3)

    atr_p = int(ctx.params.get("atr_period", 14))
    atr_vals = ctx.atr(atr_p)

    # Validasi kesiapan nilai indikator pada bar terakhir
    if (
        not trend or trend[-1] is None
        or not fast or fast[-1] is None
        or not slow or slow[-1] is None
        or not rsi_vals or rsi_vals[-1] is None
        or not k_vals or k_vals[-1] is None or len(k_vals) < 2
        or not d_vals or d_vals[-1] is None or len(d_vals) < 2
        or not atr_vals or atr_vals[-1] is None
    ):
        return None

    # --------------------------------------------------------------------------
    # PROTEKSI 4: Manajemen Posisi Terbuka & Emergency Invalidation Exit
    # --------------------------------------------------------------------------
    if ctx.position and ctx.position.get("volume", 0) > 0:
        pos_type = ctx.position.get("type")

        # Invalidation Exit untuk BUY:
        # Jika momentum cepat memotong ke bawah slow EMA dan harga menembus di bawah slow EMA,
        # momentum naik telah patah. Tutup dini untuk menghemat modal sebelum terkena full SL.
        if pos_type == "BUY":
            if ctx.crossunder(fast, slow) and ctx.close[-1] < slow[-1]:
                ctx.log("Momentum BUY berbalik patah. Emergency Exit dieksekusi.")
                return ctx.close_position(ctx.position)

        # Invalidation Exit untuk SELL:
        elif pos_type == "SELL":
            if ctx.crossover(fast, slow) and ctx.close[-1] > slow[-1]:
                ctx.log("Momentum SELL berbalik patah. Emergency Exit dieksekusi.")
                return ctx.close_position(ctx.position)

        # Disiplin: jangan buka posisi baru saat masih ada posisi aktif
        return None

    # --------------------------------------------------------------------------
    # PROTEKSI 5: Filter Volatilitas Pasar (Anti-Sideways Mati)
    # --------------------------------------------------------------------------
    point = ctx.point if ctx.point and ctx.point > 0 else 0.00001
    atr_val = atr_vals[-1]
    atr_points = round(atr_val / point) if point > 0 else 0

    min_atr = int(ctx.params.get("min_atr_points", 35))
    if min_atr > 0 and atr_points < min_atr:
        # Pasar terlalu flat/mati, rasio risk-reward scalping tidak menguntungkan
        return None

    # --------------------------------------------------------------------------
    # EVALUASI SINYAL ENTRY PRESISI TINGGI
    # --------------------------------------------------------------------------
    close_curr = ctx.close[-1]
    open_curr = ctx.open[-1]
    trend_val = trend[-1]
    fast_val = fast[-1]
    slow_val = slow[-1]
    rsi_val = rsi_vals[-1]
    k_curr = k_vals[-1]
    k_prev = k_vals[-2]

    stoch_os = int(ctx.params.get("stoch_oversold", 30))
    stoch_ob = int(ctx.params.get("stoch_overbought", 70))
    rsi_max_b = int(ctx.params.get("rsi_max_buy", 65))
    rsi_min_s = int(ctx.params.get("rsi_min_sell", 35))

    # Konfigurasi SL / TP Dinamis Berbasis ATR
    use_atr = int(ctx.params.get("use_dynamic_atr_sltp", 1)) == 1
    atr_sl_mult = float(ctx.params.get("atr_sl_mult", 1.5))
    atr_tp_mult = float(ctx.params.get("atr_tp_mult", 2.2))

    if use_atr and atr_points > 0:
        sl_calc = max(80, int(atr_points * atr_sl_mult))
        tp_calc = max(120, int(atr_points * atr_tp_mult))
    else:
        sl_calc = int(ctx.settings.get("sl_points", 120))
        tp_calc = int(ctx.settings.get("tp_points", 180))

    # --- SETUP 1: BULLISH SCALPING (BUY) ---
    # Syarat:
    # 1. Macro Trend: Harga di atas EMA 200
    # 2. Micro Momentum: EMA 8 di atas EMA 21
    # 3. Pullback Confirmation: Stochastic %K cross UP melintasi %D dari area oversold (k <= 30)
    # 4. Healthy Zone: RSI antara 35 s/d 65 (belum overbought)
    # 5. Price Action: Candle penutup berupa candle hijau / bullish
    stoch_cross_up = ctx.crossover(k_vals, d_vals)
    was_oversold = (k_curr <= stoch_os) or (k_prev <= stoch_os)
    is_bullish_candle = close_curr >= open_curr

    if (
        close_curr > trend_val
        and fast_val > slow_val
        and stoch_cross_up
        and was_oversold
        and 35.0 <= rsi_val <= rsi_max_b
        and is_bullish_candle
    ):
        ctx.log(
            f"Bullish Scalp Trigger [BUY] -> EMA200={trend_val:.5f}, "
            f"RSI={rsi_val:.1f}, StochK={k_curr:.1f}, ATR_pts={atr_points}, SL={sl_calc}pts, TP={tp_calc}pts"
        )
        return ctx.buy(sl_points=sl_calc, tp_points=tp_calc, comment="SafeScalp_BUY")

    # --- SETUP 2: BEARISH SCALPING (SELL) ---
    # Syarat:
    # 1. Macro Trend: Harga di bawah EMA 200
    # 2. Micro Momentum: EMA 8 di bawah EMA 21
    # 3. Pullback Confirmation: Stochastic %K cross DOWN melintasi %D dari area overbought (k >= 70)
    # 4. Healthy Zone: RSI antara 35 s/d 65 (belum oversold)
    # 5. Price Action: Candle penutup berupa candle merah / bearish
    stoch_cross_down = ctx.crossunder(k_vals, d_vals)
    was_overbought = (k_curr >= stoch_ob) or (k_prev >= stoch_ob)
    is_bearish_candle = close_curr <= open_curr

    if (
        close_curr < trend_val
        and fast_val < slow_val
        and stoch_cross_down
        and was_overbought
        and rsi_min_s <= rsi_val <= 65.0
        and is_bearish_candle
    ):
        ctx.log(
            f"Bearish Scalp Trigger [SELL] -> EMA200={trend_val:.5f}, "
            f"RSI={rsi_val:.1f}, StochK={k_curr:.1f}, ATR_pts={atr_points}, SL={sl_calc}pts, TP={tp_calc}pts"
        )
        return ctx.sell(sl_points=sl_calc, tp_points=tp_calc, comment="SafeScalp_SELL")

    return None
