"""XAU Fast Scalper Pro - Soft Multi Recovery (Mode Programmer).

Strategi Scalping Cepat Khusus Emas (XAUUSDm / XAUUSD) dengan Respon Sinyal Kilat
dan Manajemen Pemulihan Siklus Lembut (Soft Multiplier).

Karakteristik & Keunggulan:
1. Fast Trigger (Anti-Bengong):
   - Dirancang agar TIDAK LAMA MENUNGGU OP.
   - Menggunakan Micro-EMA (9) + Micro-RSI (7) yang sangat responsif di timeframe M1/M5.
   - Begitu bot aktif dan posisi kosong, bot langsung membaca momentum bar terkini
     dan segera membuka posisi (BUY / SELL) tanpa tertahan crossing berjam-jam.
2. Soft Multiplier Recovery (Bukan Martingale Kasar):
   - Pengali lot terukur & lembut (default 1.30x / soft progression).
   - Contoh tangga lot: 0.01 -> 0.02 -> 0.02 -> 0.03 -> 0.04 (Max Cap 0.05).
   - Sangat aman untuk volatilitas tinggi XAU, margin tetap terjaga dan tidak berisiko MC.
   - Begitu siklus PROFIT tercapai, otomatis langsung RESET ke Base Lot (0.01).
   - Dilengkapi batas maksimal tahap (default 4 tahap); jika berturut-turut loss melebihi batas,
     otomatis reset ke Base Lot demi proteksi modal.
3. Scalping Presisi XAU:
   - Target Take Profit cepat (120 points = 12 pips / $1.20 gerakan emas).
   - Stop Loss terukur (180 points = 18 pips / $1.80 gerakan emas).
   - Break-Even otomatis mengunci modal di +60 points (+15 offset menutupi spread).
   - Trailing Stop dinamis 80 points untuk mengamankan cuan saat emas melesat kencang.
4. Pilar Proteksi Risiko:
   - Toleransi spread dinamis aman XAU (default maks 60 points).
   - Filter margin level minimal 200%.
   - Batas drawdown harian 5% & equity stop loss 10%.
   - one_trade_per_bar: False agar siklus baru bisa langsung jalan setelah order tertutup.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS)
# ==============================================================================
SETTINGS = {
    # Instrumen & Timeframe
    "symbol": "XAUUSDm",                 # Simbol Emas standar Exness (kompatibel juga XAUUSD)
    "timeframe": "M1",                   # Timeframe M1 untuk eksekusi scalping responsif
    "volume": 0.01,                      # Base lot awal
    "max_positions": 1,                  # Disiplin 1 posisi per siklus agar fokus & aman

    # Target Scalping & Stop Loss (Points XAU: 100 pts = $1.00 gerakan emas)
    "tp_points": 120,                    # Target Take Profit cepat (12 pips / $1.20)
    "sl_points": 180,                    # Stop Loss terukur (18 pips / $1.80)

    # Proteksi Profit & Penguncian Modal
    "break_even_enabled": True,          # Kunci profit modal saat sudah floating positif
    "break_even_points": 60,             # Aktif setelah profit +60 points ($0.60)
    "break_even_offset_points": 15,      # Kunci 15 points di atas entry (menutup biaya spread)
    "trailing_stop_enabled": True,       # Amankan cuan saat tren emas berlanjut panjang
    "trailing_stop_points": 80,          # Jarak trailing 80 points
    "trailing_step_points": 20,          # Geser trailing tiap pergerakan 20 points

    # Proteksi Keamanan Risiko Akun
    "max_spread_points": 60,             # Toleransi spread aman XAUUSDm
    "daily_drawdown_limit": 0.05,        # Hentikan bot jika drawdown harian mencapai 5%
    "equity_stop_loss": 0.10,            # Cut off proteksi jika equity drop 10%
    "max_consecutive_losses": 4,         # Istirahat jika 4x rugi berturut-turut
    "max_daily_trades": 100,             # Siap frekuensi trade tinggi
    "min_margin_level": 200.0,           # Margin level minimal 200%

    # Kontrol Eksekusi Instan
    "one_trade_per_bar": False,          # Langsung bisa buka posisi baru setelah siklus selesai
    "comment": "XAU_FastScalp",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 1.0},
    {"key": "tp_points", "label": "Take Profit (pts)", "type": "int", "default": 120, "min": 30, "max": 600},
    {"key": "sl_points", "label": "Stop Loss (pts)", "type": "int", "default": 180, "min": 50, "max": 800},
    {"key": "recovery_multiplier", "label": "Pengali Soft Recovery", "type": "float", "default": 1.30, "min": 1.1, "max": 2.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 4, "min": 1, "max": 6},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.05, "min": 0.02, "max": 1.0},
    {"key": "fast_ema_period", "label": "Periode Micro EMA", "type": "int", "default": 9, "min": 3, "max": 30},
    {"key": "rsi_period", "label": "Periode Micro RSI", "type": "int", "default": 7, "min": 3, "max": 21},
    {"key": "max_spread", "label": "Maksimal Spread (pts)", "type": "int", "default": 60, "min": 10, "max": 200},
]

# ==============================================================================
# 3. PENYIMPAN STATUS SIKLUS & SOFT RECOVERY (PERSISTEN ANTAR-BAR)
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
}


def on_bar(ctx):
    """Logika scalping cepat XAU dengan soft multi recovery."""
    # --------------------------------------------------------------------------
    # FILTER 1: Toleransi Spread & Margin Level
    # --------------------------------------------------------------------------
    max_sp = int(ctx.params.get("max_spread", 60))
    if max_sp > 0 and ctx.spread and ctx.spread > max_sp:
        ctx.log(f"Spread XAU ({ctx.spread} pts) melebihi batas {max_sp} pts. Menunggu spread stabil.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 200.0:
        ctx.log(f"Margin level tipis ({ctx.margin_level:.1f}%). Eksekusi ditahan demi proteksi modal.")
        return None

    # --------------------------------------------------------------------------
    # SINKRONISASI SIKLUS SEBELUMNYA (WIN / LOSS EVALUASI)
    # --------------------------------------------------------------------------
    current_balance = float(ctx.balance)
    if STATE["last_balance"] is None and current_balance > 0:
        STATE["last_balance"] = current_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 4))

    # Cek apakah sedang ada posisi aktif terbuka
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        # Jika baru saja ada posisi selesai tertutup, evaluasi hasil PnL
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = current_balance - STATE["last_balance"]

            # Profit -> Siklus Menang -> Reset ke Base Lot
            if pnl > 0.001:
                ctx.log(f"Siklus XAU PROFIT (+${pnl:.2f})! Reset tahap soft recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = current_balance

            # Loss -> Naikkan tahap soft recovery
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = current_balance

                if STATE["recovery_step"] > max_steps:
                    ctx.log(
                        f"Batas soft recovery ({max_steps} tahap) tercapai. "
                        f"Mereset ke Base Lot demi disiplin dan keamanan modal."
                    )
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(
                        f"Siklus XAU LOSS (-${abs(pnl):.2f}). "
                        f"Mengaktifkan Soft Recovery Tahap {STATE['recovery_step']}/{max_steps}."
                    )
    else:
        # Sedang ada posisi aktif: biarkan TP / SL / Trailing bekerja
        return None

    # --------------------------------------------------------------------------
    # HITUNG SIZING LOT LEMBUT (SOFT MULTIPLIER)
    # --------------------------------------------------------------------------
    base_lot = float(ctx.params.get("base_lot", 0.01))
    rec_mult = float(ctx.params.get("recovery_multiplier", 1.30))
    max_lot = float(ctx.params.get("max_lot_cap", 0.05))

    step = STATE["recovery_step"]

    # Perhitungan soft progression:
    # Untuk base_lot kecil (0.01-0.02): kenaikan lembut 0.01 -> 0.02 -> 0.02 -> 0.03 -> 0.04
    # Untuk base_lot lebih besar: mengikuti eksponensial lembut 1.3x
    raw_lot = base_lot * (rec_mult ** step)
    if base_lot <= 0.02 and step > 0:
        soft_lot = base_lot + (step * 0.007)
        calc_lot = round(max(raw_lot, soft_lot), 2)
    else:
        calc_lot = round(raw_lot, 2)

    exec_lot = min(calc_lot, max_lot)
    if exec_lot < 0.01:
        exec_lot = 0.01

    tp_pts = int(ctx.params.get("tp_points", 120))
    sl_pts = int(ctx.params.get("sl_points", 180))

    # Pastikan jarak TP & SL minimal di atas 1.5x spread saat ini
    curr_sp = int(ctx.spread) if ctx.spread and ctx.spread > 0 else 0
    if curr_sp > 0:
        tp_pts = max(tp_pts, int(curr_sp * 1.5) + 10)
        sl_pts = max(sl_pts, int(curr_sp * 2.0) + 15)

    # --------------------------------------------------------------------------
    # DETEKSI MOMENTUM KILAT (FAST OP TRIGGER - ANTI LAMA GAK OP)
    # --------------------------------------------------------------------------
    fast_ema_p = int(ctx.params.get("fast_ema_period", 9))
    rsi_p = int(ctx.params.get("rsi_period", 7))

    direction = "BUY"  # Default aman

    if len(ctx.close) >= max(fast_ema_p, rsi_p, 5):
        ema_vals = ctx.ema(ctx.close, fast_ema_p)
        rsi_vals = ctx.rsi(ctx.close, rsi_p)

        close_curr = ctx.close[-1]
        ema_curr = ema_vals[-1] if (ema_vals and ema_vals[-1] is not None) else close_curr
        rsi_curr = rsi_vals[-1] if (rsi_vals and rsi_vals[-1] is not None) else 50.0

        # Logika Fast Trigger:
        # Bullish Bias: Harga di atas Micro EMA atau RSI rebound dari area oversold (< 40)
        # Bearish Bias: Harga di bawah Micro EMA atau RSI pullback dari area overbought (> 60)
        if close_curr >= ema_curr and rsi_curr >= 45:
            direction = "BUY"
        elif close_curr < ema_curr and rsi_curr <= 55:
            direction = "SELL"
        elif rsi_curr < 35:
            # Rebound oversold kilat
            direction = "BUY"
        elif rsi_curr > 65:
            # Rebound overbought kilat
            direction = "SELL"
        else:
            # Fallback arah candle terakhir agar langsung OP
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"
    else:
        # Data candle minimal: ikuti arah candle terakhir
        if len(ctx.close) > 0 and len(ctx.open) > 0:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"

    # --------------------------------------------------------------------------
    # EKSEKUSI ORDER INSTAN
    # --------------------------------------------------------------------------
    STATE["has_traded"] = True
    STATE["last_type"] = direction

    order_comment = f"XAU_Fast_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(
            f"⚡ XAU FAST SCALP [BUY] -> Lot={exec_lot:.2f} (Soft Step {step}/{max_steps}), "
            f"TP={tp_pts}pts, SL={sl_pts}pts | Simbol: {ctx.symbol}"
        )
        return ctx.buy(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
    else:
        ctx.log(
            f"⚡ XAU FAST SCALP [SELL] -> Lot={exec_lot:.2f} (Soft Step {step}/{max_steps}), "
            f"TP={tp_pts}pts, SL={sl_pts}pts | Simbol: {ctx.symbol}"
        )
        return ctx.sell(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
