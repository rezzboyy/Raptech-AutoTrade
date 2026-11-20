"""Brutal Cent Scalper - High-Frequency Instant OP & Adaptive Martingale Recovery.

Dirancang khusus untuk pengetesan agresif bot trading di Akun Cent / Standar:
1. INSTANT OP SAAT START (ANTI-BENGONG / KILAT):
   - Langsung membuka posisi (BUY/SELL) pada bar/tick pertama saat bot dijalankan.
   - Tidak perlu menunggu sinyal crossover berjam-jam: membaca arah micro momentum /
     candle terkini dan LANGSUNG MASUK PASAR seketika!
2. BRUTAL HIGH-FREQUENCY TURNOVER:
   - Target Take Profit kilat (Scalping 50-80 points) agar siklus cepat profit dan tertutup.
   - One-Trade-Per-Bar dinonaktifkan: begitu posisi selesai (TP/SL), bot langsung siap
     membuka posisi baru tanpa jeda bar.
3. ADAPTIVE MARTINGALE & CYCLE RECOVERY (RECOVERY PASTI JALAN):
   - Melacak PnL saldo secara real-time antar-siklus order.
   - Jika posisi terkena SL (Loss): otomatis melipatgandakan lot secara terukur
     (default pengali 1.75x - 2.0x) untuk memulihkan loss pada siklus berikutnya.
   - Begitu siklus meraih PROFIT: seketika RESET ke Base Lot awal (0.01) dan Step 0!
   - Dilengkapi 3 Mode Arah Recovery: Auto Momentum, Flip Balik Arah, atau Tetap Searah.
4. PERLINDUNGAN KEAMANAN & MULTI-MARKET AUTO-SCALING:
   - Otomatis menyesuaikan spread, TP, dan SL untuk Forex (EURUSDc/m), Gold (XAUUSDc/m),
     Crypto (BTCUSDm), dan Indeks.
   - Dilengkapi Max Recovery Steps (default 5 tahap) dan Max Lot Cap agar akun cent tetap
     aman dari lonjakan margin tak terkendali.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS)
# ==============================================================================
SETTINGS = {
    # Default instrumen & timeframe (cocok untuk akun Cent: EURUSDc, EURUSDm, XAUUSDc, dsb)
    "symbol": "EURUSDm",
    "timeframe": "M1",                   # M1 untuk eksekusi kilat dan tes agresif
    "volume": 0.01,                      # Base lot awal (0.01 cent = super aman)
    "max_positions": 1,                  # 1 posisi aktif per siklus agar terukur

    # Target Scalping Kilat (Quick TP)
    "tp_points": 50,                     # TP kilat 50 points (5 pips di forex)
    "sl_points": 100,                    # SL terukur 100 points (10 pips)

    # Penguncian Modal & Keuntungan Dinamis
    "break_even_enabled": True,          # Mengunci modal saat floating profit
    "break_even_points": 30,             # Aktif setelah profit +30 points
    "break_even_offset_points": 8,       # Kunci +8 points di atas entry
    "trailing_stop_enabled": True,       # Amankan lonjakan tren panjang
    "trailing_stop_points": 45,          # Jarak trailing stop
    "trailing_step_points": 15,          # Geser tiap 15 points

    # Manajemen Risiko & Batas Akun
    "max_spread_points": 50,             # Batas spread aman Forex
    "daily_drawdown_limit": 0.10,        # Batas drawdown harian 10%
    "equity_stop_loss": 0.20,            # Proteksi cut-off ekuitas 20%
    "max_consecutive_losses": 6,         # Cooldown jika 6x loss berturut-turut
    "max_daily_trades": 300,             # Kapasitas frekuensi tinggi untuk pengujian brutal
    "min_margin_level": 150.0,           # Margin level minimal 150%

    # Kontrol Kecepatan Open Posisi Instan
    "one_trade_per_bar": False,          # Bebas buka posisi baru begitu siklus selesai
    "comment": "BrutalCent",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 5.0},
    {"key": "recovery_multiplier", "label": "Pengali Lot Recovery (Martingale)", "type": "float", "default": 1.75, "min": 1.2, "max": 3.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 5, "min": 1, "max": 8},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.64, "min": 0.02, "max": 10.0},
    {"key": "recovery_direction_mode", "label": "Mode Arah Recovery (0=Auto Momentum, 1=Flip Balik Arah, 2=Tetap Searah)", "type": "int", "default": 0, "min": 0, "max": 2},
    {"key": "initial_bias", "label": "Bias Arah Awal (0=Auto Micro Candle, 1=Selalu BUY, 2=Selalu SELL)", "type": "int", "default": 0, "min": 0, "max": 2},
    {"key": "tp_points", "label": "Take Profit (pts)", "type": "int", "default": 50, "min": 20, "max": 1000},
    {"key": "sl_points", "label": "Stop Loss (pts)", "type": "int", "default": 100, "min": 30, "max": 1500},
    {"key": "auto_market_scaling", "label": "Auto Adaptasi Pasar (Forex/Gold/Crypto)", "type": "bool", "default": True},
    {"key": "max_spread", "label": "Maksimal Spread (pts)", "type": "int", "default": 50, "min": 5, "max": 10000},
]

# ==============================================================================
# 3. PENYIMPAN STATUS PERSISTEN (STATE SIKLUS & RECOVERY)
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
    "consecutive_losses": 0,
    "consecutive_wins": 0,
}


def _get_market_category(symbol):
    """Deteksi kategori pasar secara cerdas dari nama simbol."""
    s = (symbol or "").upper()
    if "BTC" in s or "ETH" in s or "SOL" in s or "CRYPTO" in s:
        return "CRYPTO"
    if "XAU" in s or "GOLD" in s or "XAG" in s or "SILVER" in s:
        return "METAL"
    if "US30" in s or "DJ30" in s or "NAS" in s or "USTEC" in s or "GER40" in s or "US500" in s:
        return "INDEX"
    return "FOREX"


def _get_market_targets(category, spread_pts, default_tp, default_sl, default_max_sp):
    """Hitung target TP, SL, BE, Trailing, dan Max Spread adaptif per kelas pasar."""
    sp = max(spread_pts or 0, 0)
    if category == "CRYPTO":
        max_sp = max(default_max_sp, 4500)
        tp = max(3000, sp * 2 + 500)
        sl = max(5000, sp * 3 + 1000)
        be = 1800
        be_off = 400
        trail = 2500
    elif category == "METAL":
        max_sp = max(default_max_sp, 75)
        tp = max(100, sp * 2 + 20)
        sl = max(180, sp * 3 + 30)
        be = 50
        be_off = 15
        trail = 70
    elif category == "INDEX":
        max_sp = max(default_max_sp, 350)
        tp = max(250, sp * 2 + 50)
        sl = max(400, sp * 3 + 80)
        be = 150
        be_off = 30
        trail = 200
    else:  # FOREX (termasuk Cent EURUSDc, GBPUSDc, dsb)
        max_sp = max(default_max_sp, 50)
        tp = max(default_tp, sp * 2 + 10)
        sl = max(default_sl, sp * 3 + 20)
        be = 30
        be_off = 8
        trail = 45
    return max_sp, tp, sl, be, be_off, trail


def _detect_momentum(ctx):
    """Deteksi arah pasar seketika: Micro EMA / RSI atau warna candle terakhir."""
    if len(ctx.close) >= 2 and len(ctx.open) >= 2:
        c_last = ctx.close[-1]
        o_last = ctx.open[-1]

        # Jika ada candle cukup untuk Micro EMA 5
        if len(ctx.close) >= 5:
            ema5 = ctx.ema(ctx.close, 5)
            ema_val = ema5[-1] if (ema5 and ema5[-1] is not None) else c_last
            if c_last > ema_val:
                return "BUY"
            if c_last < ema_val:
                return "SELL"

        # Cek arah candle terkini
        if c_last >= o_last:
            return "BUY"
        return "SELL"

    # Fallback aman bila data candle sangat minimal
    return "BUY"


def on_bar(ctx):
    """Logika eksekusi instan dan Martingale recovery untuk pengetesan agresif."""
    sym = ctx.symbol or "EURUSDm"
    market_cat = _get_market_category(sym)

    curr_spread = int(ctx.spread) if ctx.spread is not None else 0
    param_tp = int(ctx.params.get("tp_points", 50))
    param_sl = int(ctx.params.get("sl_points", 100))
    param_max_sp = int(ctx.params.get("max_spread", 50))
    use_auto_scaling = bool(ctx.params.get("auto_market_scaling", True))

    if use_auto_scaling:
        max_sp, auto_tp, auto_sl, auto_be, auto_be_off, auto_trail = _get_market_targets(
            market_cat, curr_spread, param_tp, param_sl, param_max_sp
        )
    else:
        max_sp = param_max_sp
        auto_tp = param_tp
        auto_sl = param_sl

    # --------------------------------------------------------------------------
    # 1. FILTER PROTEKSI SPREAD & MARGIN LEVEL
    # --------------------------------------------------------------------------
    if max_sp > 0 and curr_spread > max_sp:
        ctx.log(f"[{market_cat}] Spread ({curr_spread} pts) > batas ({max_sp} pts). Menunggu spread normal.")
        return None

    min_ml = float(ctx.settings.get("min_margin_level", 150.0))
    if ctx.margin_level and 0 < ctx.margin_level < min_ml:
        ctx.log(f"Margin level kritis ({ctx.margin_level:.1f}% < {min_ml:.1f}%). Menahan entry.")
        return None

    # --------------------------------------------------------------------------
    # 2. SINKRONISASI SIKLUS & RECOVERY ENGINE (EVALUASI PNL)
    # --------------------------------------------------------------------------
    curr_balance = float(ctx.balance)
    if STATE["last_balance"] is None and curr_balance > 0:
        STATE["last_balance"] = curr_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 5))
    base_lot = float(ctx.params.get("base_lot", 0.01))
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        # Jika baru saja ada posisi yang tertutup, evaluasi PnL perubahan saldo
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = curr_balance - STATE["last_balance"]

            # KASUS A: POSISI PROFIT (SIKLUS WIN) -> RESET RECOVERY KE BASE LOT!
            if pnl > 0.001:
                ctx.log(
                    f"🔥 [BRUTAL CENT WIN] Siklus PROFIT (+${pnl:.2f})! "
                    f"Reset recovery ke Step 0 (Base Lot {base_lot:.2f})."
                )
                STATE["recovery_step"] = 0
                STATE["consecutive_wins"] += 1
                STATE["consecutive_losses"] = 0
                STATE["last_balance"] = curr_balance

            # KASUS B: POSISI LOSS (SIKLUS KALAH) -> NAIKKAN TAHAP RECOVERY!
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["consecutive_losses"] += 1
                STATE["consecutive_wins"] = 0
                STATE["last_balance"] = curr_balance

                if STATE["recovery_step"] > max_steps:
                    ctx.log(
                        f"🛡️ [BRUTAL CENT CAP] Batas tahap recovery ({max_steps}) tercapai. "
                        f"Reset ke Base Lot ({base_lot:.2f}) demi proteksi modal."
                    )
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(
                        f"⚡ [BRUTAL CENT LOSS] Siklus LOSS (-${abs(pnl):.2f}). "
                        f"Mengaktifkan Recovery Tahap {STATE['recovery_step']}/{max_steps}!"
                    )
    else:
        # Sedang ada posisi aktif terbuka: biarkan TP / SL / Trailing Stop bekerja
        return None

    # --------------------------------------------------------------------------
    # 3. KALKULASI SIZING LOT MARTINGALE / RECOVERY
    # --------------------------------------------------------------------------
    rec_mult = float(ctx.params.get("recovery_multiplier", 1.75))
    max_lot = float(ctx.params.get("max_lot_cap", 0.64))
    step = STATE["recovery_step"]

    # Hitung lot bertingkat
    raw_lot = base_lot * (rec_mult ** step)

    # Proteksi pembulatan: pastikan setiap step recovery selalu naik minimal 0.01
    if step > 0 and raw_lot <= base_lot:
        calc_lot = round(base_lot + (step * 0.01), 2)
    else:
        calc_lot = round(raw_lot, 2)
        if step > 0:
            prev_raw = base_lot * (rec_mult ** (step - 1))
            if calc_lot <= round(prev_raw, 2):
                calc_lot = round(round(prev_raw, 2) + 0.01, 2)

    exec_lot = min(calc_lot, max_lot)
    if exec_lot < 0.01:
        exec_lot = 0.01

    # --------------------------------------------------------------------------
    # 4. PENENTUAN ARAH EKSEKUSI (INSTANT OP - LANGSUNG MASUK TANPA TUNDA)
    # --------------------------------------------------------------------------
    bias_mode = int(ctx.params.get("initial_bias", 0))
    rec_dir_mode = int(ctx.params.get("recovery_direction_mode", 0))

    if step > 0:
        # Mode Recovery: tentukan arah berdasarkan strategi recovery
        if rec_dir_mode == 1:
            # Flip Reversal: jika tadi BUY loss -> sekarang SELL
            direction = "SELL" if STATE["last_type"] == "BUY" else "BUY"
        elif rec_dir_mode == 2:
            # Same Direction: tetap buka arah yang sama
            direction = STATE["last_type"]
        else:
            # Auto Momentum (default): ikuti momentum bar terbaru saat ini
            direction = _detect_momentum(ctx)
    else:
        # Step 0 (Normal Entry):
        if bias_mode == 1:
            direction = "BUY"
        elif bias_mode == 2:
            direction = "SELL"
        else:
            direction = _detect_momentum(ctx)

    # --------------------------------------------------------------------------
    # 5. EKSEKUSI ORDER INSTAN
    # --------------------------------------------------------------------------
    STATE["has_traded"] = True
    STATE["last_type"] = direction
    STATE["last_balance"] = curr_balance

    order_comment = f"Brutal_{direction[0]}_S{step}"

    if direction == "BUY":
        ctx.log(
            f"🚀 [BRUTAL OP] BUY -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), "
            f"TP={auto_tp}pts, SL={auto_sl}pts | Simbol: {sym}"
        )
        return ctx.buy(volume=exec_lot, sl_points=auto_sl, tp_points=auto_tp, comment=order_comment)
    else:
        ctx.log(
            f"🚀 [BRUTAL OP] SELL -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), "
            f"TP={auto_tp}pts, SL={auto_sl}pts | Simbol: {sym}"
        )
        return ctx.sell(volume=exec_lot, sl_points=auto_sl, tp_points=auto_tp, comment=order_comment)
