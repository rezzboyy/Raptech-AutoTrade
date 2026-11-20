"""Fast Gold Scalper Pro - Ultra Responsive (Anti-Bengong).

Strategi Scalping Emas Super Cepat & Adaptif (XAUUSDm / XAUUSD).
Dioptimalkan khusus untuk spread dinamis emas (2-digit & 3-digit broker).

Karakteristik & Keunggulan:
1. Fast Trigger (Anti-Bengong):
   - M1 Micro-Momentum: Menggunakan Micro-EMA (7) dan RSI (7).
   - Langsung mendeteksi bias momentum emas dan segera open posisi tanpa tertahan berjam-jam.
2. Auto-Adaptive Spread & Point Scaling:
   - Broker 3-Digit (Exness XAUUSDm, point=0.001): Auto-scale 10x sehingga toleransi spread 650 pts ($0.65).
   - Broker 2-Digit (Standard XAUUSD, point=0.01): Auto-scale 1x sehingga toleransi spread 65 pts ($0.65).
   - Menghilangkan bug "spread melebihi batas" yang membuat bot macet/bengong pada broker ECN/Exness.
3. Scalping Presisi XAU:
   - Target Take Profit terukur: $1.50 pergerakan emas (1500 pts di 3-digit / 150 pts di 2-digit).
   - Stop Loss terukur: $2.50 pergerakan emas (2500 pts di 3-digit / 250 pts di 2-digit).
   - Break-Even otomatis mengunci modal di +$0.80 (+150 pts offset spread).
   - Trailing Stop dinamis 1000 pts ($1.00) untuk mengamankan lonjakan tren.
4. Soft Multiplier Recovery:
   - Pengali lot terukur & lembut (default 1.30x / max 4 tahap).
   - Reset seketika ke Base Lot saat profit diraih.
5. Pilar Proteksi Risiko:
   - Filter margin level minimal 150%.
   - Batas drawdown harian 5% & equity stop loss 10%.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS)
# ==============================================================================
SETTINGS = {
    "symbol": "XAUUSDm",
    "timeframe": "M1",
    "volume": 0.01,
    "max_positions": 1,

    # Points XAU (Skala 3-digit Exness: 1000 pts = $1.00 gerakan emas)
    "tp_points": 1500,                   # TP cepat $1.50
    "sl_points": 2500,                   # SL $2.50

    "break_even_enabled": True,
    "break_even_points": 800,            # Kunci modal saat +$0.80
    "break_even_offset_points": 150,     # Kunci 150 points di atas entry
    "trailing_stop_enabled": True,
    "trailing_stop_points": 1000,
    "trailing_step_points": 250,

    "max_spread_points": 650,            # Toleransi spread aman emas (hingga $0.65)
    "daily_drawdown_limit": 0.05,
    "equity_stop_loss": 0.10,
    "max_consecutive_losses": 4,
    "max_daily_trades": 150,
    "min_margin_level": 150.0,
    "one_trade_per_bar": False,          # Buka posisi berikutnya segera saat posisi selesai
    "comment": "Gold_FastScalp",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 1.0},
    {"key": "tp_usd", "label": "Target TP ($)", "type": "float", "default": 1.50, "min": 0.50, "max": 10.0},
    {"key": "sl_usd", "label": "Batas SL ($)", "type": "float", "default": 2.50, "min": 1.0, "max": 15.0},
    {"key": "recovery_multiplier", "label": "Pengali Soft Recovery", "type": "float", "default": 1.30, "min": 1.1, "max": 2.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 4, "min": 1, "max": 6},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.05, "min": 0.02, "max": 1.0},
    {"key": "fast_ema_period", "label": "Periode Micro EMA", "type": "int", "default": 7, "min": 3, "max": 30},
    {"key": "rsi_period", "label": "Periode Micro RSI", "type": "int", "default": 7, "min": 3, "max": 21},
    {"key": "max_spread_usd", "label": "Maksimal Spread ($)", "type": "float", "default": 0.65, "min": 0.20, "max": 2.0},
]

# ==============================================================================
# 3. PENYIMPAN STATUS PERSISTEN
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
}


def on_bar(ctx):
    """Logika scalping cepat XAU ultra-responsif dengan adaptasi spread broker otomatis."""
    # Auto-deteksi skala point (3 digit Exness point=0.001 -> scale 10, 2 digit standar point=0.01 -> scale 1)
    pt_scale = 10 if (ctx.point and ctx.point < 0.005) else 1

    max_sp_usd = float(ctx.params.get("max_spread_usd", 0.65))
    max_sp_pts = int(max_sp_usd * 100 * pt_scale)

    curr_sp = int(ctx.spread) if ctx.spread and ctx.spread > 0 else 0
    if max_sp_pts > 0 and curr_sp > max_sp_pts:
        ctx.log(f"Spread Emas ({curr_sp} pts) melebihi batas {max_sp_pts} pts (${max_sp_usd:.2f}). Menunggu spread normal.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 150.0:
        ctx.log(f"Margin level tipis ({ctx.margin_level:.1f}%). Menahan order baru demi keamanan modal.")
        return None

    curr_balance = float(ctx.balance)
    if STATE["last_balance"] is None and curr_balance > 0:
        STATE["last_balance"] = curr_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 4))
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = curr_balance - STATE["last_balance"]
            if pnl > 0.001:
                ctx.log(f"Siklus Emas PROFIT (+${pnl:.2f})! Reset tahap recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = curr_balance
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = curr_balance
                if STATE["recovery_step"] > max_steps:
                    ctx.log(f"Batas soft recovery ({max_steps}) tercapai. Reset ke Base Lot.")
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(f"Siklus Emas LOSS (-${abs(pnl):.2f}). Soft Recovery Tahap {STATE['recovery_step']}/{max_steps}.")
    else:
        return None

    base_lot = float(ctx.params.get("base_lot", 0.01))
    rec_mult = float(ctx.params.get("recovery_multiplier", 1.30))
    max_lot = float(ctx.params.get("max_lot_cap", 0.05))

    step = STATE["recovery_step"]
    raw_lot = base_lot * (rec_mult ** step)
    if base_lot <= 0.02 and step > 0:
        soft_lot = base_lot + (step * 0.007)
        calc_lot = round(max(raw_lot, soft_lot), 2)
    else:
        calc_lot = round(raw_lot, 2)

    exec_lot = min(calc_lot, max_lot)
    if exec_lot < 0.01:
        exec_lot = 0.01

    tp_usd = float(ctx.params.get("tp_usd", 1.50))
    sl_usd = float(ctx.params.get("sl_usd", 2.50))
    tp_pts = int(tp_usd * 100 * pt_scale)
    sl_pts = int(sl_usd * 100 * pt_scale)

    if curr_sp > 0:
        tp_pts = max(tp_pts, int(curr_sp * 1.5) + (10 * pt_scale))
        sl_pts = max(sl_pts, int(curr_sp * 2.0) + (15 * pt_scale))

    fast_ema_p = int(ctx.params.get("fast_ema_period", 7))
    rsi_p = int(ctx.params.get("rsi_period", 7))

    direction = "BUY"

    if len(ctx.close) >= max(fast_ema_p, rsi_p, 5):
        ema_vals = ctx.ema(ctx.close, fast_ema_p)
        rsi_vals = ctx.rsi(ctx.close, rsi_p)

        close_curr = ctx.close[-1]
        ema_curr = ema_vals[-1] if (ema_vals and ema_vals[-1] is not None) else close_curr
        rsi_curr = rsi_vals[-1] if (rsi_vals and rsi_vals[-1] is not None) else 50.0

        if close_curr > ema_curr and rsi_curr >= 45:
            direction = "BUY"
        elif close_curr < ema_curr and rsi_curr <= 55:
            direction = "SELL"
        elif rsi_curr < 35:
            direction = "BUY"
        elif rsi_curr > 65:
            direction = "SELL"
        elif close_curr >= ema_curr:
            direction = "BUY"
        else:
            direction = "SELL"
    else:
        if len(ctx.close) > 0 and len(ctx.open) > 0:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"

    STATE["has_traded"] = True
    STATE["last_type"] = direction
    order_comment = f"Gold_Fast_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(f"⚡ GOLD SCALP [BUY] -> Lot={exec_lot:.2f} (Tahap {step}/{max_steps}), TP={tp_pts}pts, SL={sl_pts}pts (Spread={curr_sp}pts)")
        return ctx.buy(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
    else:
        ctx.log(f"⚡ GOLD SCALP [SELL] -> Lot={exec_lot:.2f} (Tahap {step}/{max_steps}), TP={tp_pts}pts, SL={sl_pts}pts (Spread={curr_sp}pts)")
        return ctx.sell(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
