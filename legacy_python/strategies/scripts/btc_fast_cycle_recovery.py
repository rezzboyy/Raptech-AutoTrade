"""Strategi BTC Fast Scalper & Adaptive Recovery (Khusus Bitcoin BTCUSDm 24/7).

Karakteristik & Optimasi Khusus Bitcoin (BTCUSDm):
1. Native Scale BTC: Skala TP, SL, Trailing, dan Break-Even disesuaikan khusus
   karakteristik pergerakan Bitcoin (harga ~$84k+, 2 desimal, 1 pt = $0.01).
   TP default 3,000 pts ($30) dan SL default 4,500 pts ($45) untuk memastikan
   eksekusi mulus tanpa pernah melanggar stops-level broker (Error #10016).
2. Instant Fast Entry: Eksekusi LANGSUNG pada bar/tick pertama tanpa delay.
3. Fast Turnover Cycle: Mengunci profit secara cepat, dan langsung siap membuka
   siklus order baru begitu posisi sebelumnya ditutup (one_trade_per_bar: False).
4. Adaptive Direction:
   - Mode 1 (Default): Mengikuti momentum tren EMA Bitcoin (Close >= EMA -> BUY, Close < EMA -> SELL).
   - Mode 0: Selalu BUY.
   - Mode 2: Reversal on Loss (jika trade sebelumnya BUY dan loss, recovery beralih ke SELL, dan sebaliknya).
5. Smart Loss Recovery:
   - Jika profit: Reset tahap recovery ke Base Lot.
   - Jika loss: Naikkan tahap recovery secara terukur (Base Lot * Multiplier^Step).
6. Triple Risk Shield:
   - Batas maksimal tahap recovery (Max Steps, default: 3).
   - Batas maksimal lot (Max Lot Cap, default: 0.16).
   - Proteksi spread khusus Crypto BTC (Max Spread: 3,500 pts).
7. 24/7 Weekend Ready: Dirancang siap running non-stop sepanjang hari, termasuk akhir pekan
   di pasar Crypto Exness.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS KHUSUS BTC)
# ==============================================================================
SETTINGS = {
    # Instrumen & Timeframe
    "symbol": "BTCUSDm",                 # Khusus Bitcoin Exness (Crypto 24/7)
    "timeframe": "M1",                   # Timeframe M1 untuk eksekusi siklus cepat
    "volume": 0.01,                      # Base lot awal
    "max_positions": 1,                  # 1 posisi aktif per siklus

    # Target Cuan & Stop Loss Skala Bitcoin (1 pt = $0.01)
    "tp_points": 3000,                   # Take Profit $30 (3000 points)
    "sl_points": 4500,                   # Stop Loss $45 (4500 points)

    # Proteksi Profit Dinamis (Kunci Modal)
    "break_even_enabled": True,          # Kunci modal saat floating profit
    "break_even_points": 1800,           # Aktif di profit +$18 (1800 pts)
    "break_even_offset_points": 400,     # Kunci profit +$4 di atas harga entry
    "trailing_stop_enabled": True,       # Amankan cuan saat rally berlanjut
    "trailing_stop_points": 2500,        # Jarak trailing $25 (2500 pts)
    "trailing_step_points": 500,         # Step geser trailing $5 (500 pts)

    # Gerbang Proteksi Risiko Akun
    "max_spread_points": 3500,           # Toleransi spread BTC (3500 pts = $35)
    "daily_drawdown_limit": 0.05,        # Batas maksimal drawdown harian 5%
    "equity_stop_loss": 0.10,            # Cut off proteksi jika equity drop 10%
    "max_consecutive_losses": 4,         # Istirahat jika 4 loss beruntun
    "max_daily_trades": 100,             # Kuota trade harian
    "min_margin_level": 150.0,           # Margin level minimal 150%

    # Kontrol Siklus Kontinu
    "one_trade_per_bar": False,          # Buka order baru segera setelah posisi selesai
    "comment": "BTC_FastRecovery",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 1.0},
    {"key": "tp_points", "label": "Take Profit BTC (pts, 3000 = $30)", "type": "int", "default": 3000, "min": 2000, "max": 20000},
    {"key": "sl_points", "label": "Stop Loss BTC (pts, 4500 = $45)", "type": "int", "default": 4500, "min": 2500, "max": 30000},
    {"key": "recovery_multiplier", "label": "Pengali Lot Recovery", "type": "float", "default": 2.0, "min": 1.2, "max": 3.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 3, "min": 1, "max": 5},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.16, "min": 0.02, "max": 5.0},
    {"key": "direction_mode", "label": "Mode Arah (1=Tren EMA, 0=Selalu BUY, 2=Balik saat Loss)", "type": "int", "default": 1, "min": 0, "max": 2},
    {"key": "ema_trend_period", "label": "Periode EMA Momentum BTC", "type": "int", "default": 20, "min": 5, "max": 100},
    {"key": "max_spread", "label": "Maksimal Spread BTC (pts)", "type": "int", "default": 3500, "min": 500, "max": 10000},
]

# ==============================================================================
# 3. STATUS SIKLUS PERSISTEN (MEMORY STATE)
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
    "last_result": "NONE",
}


def on_bar(ctx):
    """Logika eksekusi instan dan siklus recovery cepat khusus BTCUSDm."""
    # --------------------------------------------------------------------------
    # 1. VALIDASI FILTER & PROTEKSI KEAMANAN
    # --------------------------------------------------------------------------
    # Rekomendasi simbol khusus BTC
    if ctx.symbol and "BTC" not in ctx.symbol.upper():
        ctx.log(f"⚠️ Perhatian: Skrip ini dioptimasi khusus BTCUSDm (simbol aktif: {ctx.symbol}).")

    max_sp = int(ctx.params.get("max_spread", 3500))
    if max_sp > 0 and ctx.spread and ctx.spread > max_sp:
        ctx.log(f"Spread BTC ({ctx.spread} pts) melebihi batas {max_sp} pts. Menunggu spread normal.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 150.0:
        ctx.log(f"Margin level tipis ({ctx.margin_level:.1f}%). Eksekusi ditahan demi proteksi.")
        return None

    # --------------------------------------------------------------------------
    # 2. EVALUASI HASIL SIKLUS SEBELUMNYA (WIN / LOSS TRACKER)
    # --------------------------------------------------------------------------
    current_balance = float(ctx.balance)
    if STATE["last_balance"] is None and current_balance > 0:
        STATE["last_balance"] = current_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 3))

    # Cek apakah ada posisi aktif yang sedang terbuka
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        # Jika baru saja ada posisi yang tertutup, evaluasi pergerakan saldo akun
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = current_balance - STATE["last_balance"]

            # Profit -> Reset ke Base Lot
            if pnl > 0.001:
                ctx.log(f"🎯 [BTC Script] Siklus PROFIT (+${pnl:.2f})! Reset tahap recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = current_balance
                STATE["last_result"] = "WIN"

            # Loss -> Naikkan Tahap Recovery
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = current_balance
                STATE["last_result"] = "LOSS"

                if STATE["recovery_step"] > max_steps:
                    ctx.log(
                        f"🛡️ [BTC Script] Batas maksimal recovery ({max_steps} tahap) tercapai. "
                        f"Reset ke Base Lot demi disiplin modal dan keamanan akun."
                    )
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(
                        f"⚡ [BTC Script] Siklus LOSS (-${abs(pnl):.2f}). "
                        f"Mengaktifkan Fast Recovery Tahap {STATE['recovery_step']}/{max_steps}!"
                    )
    else:
        # Sedang ada posisi BTC aktif yang berjalan: tunggu hingga tertutup
        return None

    # --------------------------------------------------------------------------
    # 3. PERHITUNGAN LOT RECOVERY & JARAK SL/TP AMAN (BEBAS ERROR #10016)
    # --------------------------------------------------------------------------
    base_lot = float(ctx.params.get("base_lot", 0.01))
    rec_mult = float(ctx.params.get("recovery_multiplier", 2.0))
    max_lot = float(ctx.params.get("max_lot_cap", 0.16))

    step = STATE["recovery_step"]
    calc_lot = round(base_lot * (rec_mult ** step), 2)
    exec_lot = min(calc_lot, max_lot)
    if exec_lot < 0.01:
        exec_lot = 0.01

    tp_pts = int(ctx.params.get("tp_points", 3000))
    sl_pts = int(ctx.params.get("sl_points", 4500))

    # Proteksi anti-Error #10016: Pastikan jarak SL dan TP selalu aman terhadap spread live BTC
    curr_sp = int(ctx.spread) if ctx.spread and ctx.spread > 0 else 1000
    tp_pts = max(tp_pts, int(curr_sp * 2.0), 2500)
    sl_pts = max(sl_pts, int(curr_sp * 3.0), 4000)

    # --------------------------------------------------------------------------
    # 4. PENENTUAN ARAH ORDER (INSTANT & ADAPTIF)
    # --------------------------------------------------------------------------
    direction_mode = int(ctx.params.get("direction_mode", 1))
    direction = "BUY"  # Default cepat

    if direction_mode == 0:
        # Mode 0: Selalu BUY
        direction = "BUY"
    elif direction_mode == 2:
        # Mode 2: Balik Arah saat Kalah (Reversal on Loss)
        if STATE["last_result"] == "LOSS" and STATE["last_type"]:
            direction = "SELL" if STATE["last_type"] == "BUY" else "BUY"
        else:
            # Jika profit atau baru mulai, ikuti tren EMA
            ema_p = int(ctx.params.get("ema_trend_period", 20))
            if len(ctx.close) >= ema_p:
                ema_vals = ctx.ema(ctx.close, ema_p)
                if ema_vals and ema_vals[-1] is not None:
                    direction = "BUY" if ctx.close[-1] >= ema_vals[-1] else "SELL"
    else:
        # Mode 1 (Default): Adaptif Tren EMA Bitcoin
        ema_p = int(ctx.params.get("ema_trend_period", 20))
        if len(ctx.close) >= ema_p:
            ema_vals = ctx.ema(ctx.close, ema_p)
            if ema_vals and ema_vals[-1] is not None:
                direction = "BUY" if ctx.close[-1] >= ema_vals[-1] else "SELL"

    # --------------------------------------------------------------------------
    # 5. EKSEKUSI ORDER INSTAN
    # --------------------------------------------------------------------------
    STATE["has_traded"] = True
    STATE["last_type"] = direction

    order_comment = f"BTCRec_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(
            f"⚡ [BTC] INSTANT OPEN [BUY] -> Lot={exec_lot:.2f} (Step {step}), "
            f"TP={tp_pts}pts, SL={sl_pts}pts | Simbol: {ctx.symbol}"
        )
        return ctx.buy(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
    else:
        ctx.log(
            f"⚡ [BTC] INSTANT OPEN [SELL] -> Lot={exec_lot:.2f} (Step {step}), "
            f"TP={tp_pts}pts, SL={sl_pts}pts | Simbol: {ctx.symbol}"
        )
        return ctx.sell(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
