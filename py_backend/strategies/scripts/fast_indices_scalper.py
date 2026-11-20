"""Fast Indices Scalper Pro - Index Momentum Bursts (Mode Programmer).

Strategi Scalping Kilat Khusus Pasar Indeks (US30m / Dow Jones, USTECm / Nasdaq, US500m, GER40m).

Karakteristik & Keunggulan:
1. Fast Trigger (Anti-Bengong):
   - M1 / M5 Micro-Momentum: Menggunakan Micro-EMA (7) dan RSI (7).
   - Langsung mendeteksi ledakan momentum indeks dan mengeksekusi order seketika.
2. Scalping Dinamis Indeks:
   - Target Take Profit cepat: 350 points.
   - Stop Loss pengaman: 500 points.
   - Break-Even otomatis di +180 points (+40 offset points) demi mengunci titik impas.
   - Trailing Stop dinamis 250 points untuk menangkap reli indeks cepat.
3. Soft Multiplier Recovery:
   - Pengali lot lembut 1.25x (maksimal 4 tahap) untuk memulihkan loss.
   - Reset seketika ke Base Lot saat profit tercapai.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING (SETTINGS)
# ==============================================================================
SETTINGS = {
    "symbol": "US30m",
    "timeframe": "M1",
    "volume": 0.01,
    "max_positions": 1,

    "tp_points": 350,                    # TP cepat 350 points
    "sl_points": 500,                    # SL terukur 500 points

    "break_even_enabled": True,
    "break_even_points": 180,            # Kunci modal saat +180 points
    "break_even_offset_points": 40,      # Kunci 40 points di atas entry
    "trailing_stop_enabled": True,
    "trailing_stop_points": 250,
    "trailing_step_points": 50,

    "max_spread_points": 350,
    "daily_drawdown_limit": 0.05,
    "equity_stop_loss": 0.10,
    "max_consecutive_losses": 4,
    "max_daily_trades": 120,
    "min_margin_level": 200.0,
    "one_trade_per_bar": False,
    "comment": "Indices_FastScalp",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 1.0},
    {"key": "tp_points", "label": "Take Profit (pts)", "type": "int", "default": 350, "min": 100, "max": 1500},
    {"key": "sl_points", "label": "Stop Loss (pts)", "type": "int", "default": 500, "min": 150, "max": 2500},
    {"key": "recovery_multiplier", "label": "Pengali Soft Recovery", "type": "float", "default": 1.25, "min": 1.1, "max": 2.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 4, "min": 1, "max": 6},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.05, "min": 0.02, "max": 1.0},
    {"key": "fast_ema_period", "label": "Periode Micro EMA", "type": "int", "default": 7, "min": 3, "max": 25},
    {"key": "rsi_period", "label": "Periode Micro RSI", "type": "int", "default": 7, "min": 3, "max": 21},
    {"key": "max_spread", "label": "Maksimal Spread (pts)", "type": "int", "default": 350, "min": 50, "max": 1000},
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
    """Logika scalping cepat Indeks dengan soft multi recovery."""
    max_sp = int(ctx.params.get("max_spread", 350))
    if max_sp > 0 and ctx.spread and ctx.spread > max_sp:
        ctx.log(f"Spread Indeks ({ctx.spread} pts) melebihi batas {max_sp} pts. Menunggu stabil.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 200.0:
        ctx.log(f"Margin level tipis ({ctx.margin_level:.1f}%). Menahan order demi modal.")
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
                ctx.log(f"Siklus Indeks PROFIT (+${pnl:.2f})! Reset tahap soft recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = curr_balance
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = curr_balance
                if STATE["recovery_step"] > max_steps:
                    ctx.log(f"Batas soft recovery ({max_steps}) tercapai. Reset ke Base Lot.")
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(f"Siklus Indeks LOSS (-${abs(pnl):.2f}). Soft Recovery Tahap {STATE['recovery_step']}/{max_steps}.")
    else:
        return None

    base_lot = float(ctx.params.get("base_lot", 0.01))
    rec_mult = float(ctx.params.get("recovery_multiplier", 1.25))
    max_lot = float(ctx.params.get("max_lot_cap", 0.05))

    step = STATE["recovery_step"]
    raw_lot = base_lot * (rec_mult ** step)
    if base_lot <= 0.02 and step > 0:
        soft_lot = base_lot + (step * 0.006)
        calc_lot = round(max(raw_lot, soft_lot), 2)
    else:
        calc_lot = round(raw_lot, 2)

    exec_lot = min(calc_lot, max_lot)
    if exec_lot < 0.01:
        exec_lot = 0.01

    tp_pts = int(ctx.params.get("tp_points", 350))
    sl_pts = int(ctx.params.get("sl_points", 500))

    curr_sp = int(ctx.spread) if ctx.spread and ctx.spread > 0 else 0
    if curr_sp > 0:
        tp_pts = max(tp_pts, int(curr_sp * 1.5) + 50)
        sl_pts = max(sl_pts, int(curr_sp * 2.5) + 100)

    fast_ema_p = int(ctx.params.get("fast_ema_period", 7))
    rsi_p = int(ctx.params.get("rsi_period", 7))

    direction = "BUY"

    if len(ctx.close) >= max(fast_ema_p, rsi_p, 4):
        ema_vals = ctx.ema(ctx.close, fast_ema_p)
        rsi_vals = ctx.rsi(ctx.close, rsi_p)

        close_curr = ctx.close[-1]
        ema_curr = ema_vals[-1] if (ema_vals and ema_vals[-1] is not None) else close_curr
        rsi_curr = rsi_vals[-1] if (rsi_vals and rsi_vals[-1] is not None) else 50.0

        if close_curr >= ema_curr and rsi_curr >= 45:
            direction = "BUY"
        elif close_curr < ema_curr and rsi_curr <= 55:
            direction = "SELL"
        elif rsi_curr < 35:
            direction = "BUY"
        elif rsi_curr > 65:
            direction = "SELL"
        else:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"
    else:
        if len(ctx.close) > 0 and len(ctx.open) > 0:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"

    STATE["has_traded"] = True
    STATE["last_type"] = direction
    order_comment = f"IDX_Fast_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(f"⚡ INDICES FAST SCALP [BUY] -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), TP={tp_pts}pts, SL={sl_pts}pts")
        return ctx.buy(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
    else:
        ctx.log(f"⚡ INDICES FAST SCALP [SELL] -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), TP={tp_pts}pts, SL={sl_pts}pts")
        return ctx.sell(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
