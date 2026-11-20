"""Fast Forex Scalper Pro - High-Frequency Micro Momentum (Mode Programmer).

Strategi Scalping Kilat Khusus Pasangan Mata Uang FOREX (EURUSD, GBPUSD, USDJPY, AUDUSD, dsb).

Karakteristik & Keunggulan:
1. Fast Trigger (Eksekusi Instan Anti-Bengong):
   - M1 / M5 Micro-Momentum: Menggunakan Micro-EMA (7) dan RSI (7).
   - Saat bot aktif dan posisi kosong, bot langsung membuka posisi (BUY/SELL)
     mengikuti bias momentum candle tanpa menunggu crossover lama.
2. Target Scalping Pips Cepat:
   - TP Cepat: 80 points (8 pips) untuk take profit kilat.
   - SL Terukur: 140 points (14 pips) dengan Break-Even otomatis di +40 points (+10 offset).
   - Trailing Stop dinamis 60 points untuk mengamankan cuan saat tren melaju.
3. Soft Multiplier Recovery:
   - Pengali lembut 1.25x saat terjadi loss beruntun (maksimal 4 tahap).
   - Reset ke Base Lot seketika saat siklus profit tercapai.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING (SETTINGS)
# ==============================================================================
SETTINGS = {
    "symbol": "EURUSDm",                 # Pasangan Forex standar
    "timeframe": "M1",                   # Timeframe M1 responsif
    "volume": 0.01,                      # Base lot awal
    "max_positions": 1,                  # 1 posisi aktif per siklus

    # SL/TP Forex Points (10 points = 1 pip)
    "tp_points": 80,                     # TP kilat 8 pips
    "sl_points": 140,                    # SL 14 pips

    # Break-Even & Trailing Stop
    "break_even_enabled": True,
    "break_even_points": 40,             # Kunci modal saat +4 pips
    "break_even_offset_points": 10,      # Kunci 1 pip di atas entry
    "trailing_stop_enabled": True,
    "trailing_stop_points": 60,
    "trailing_step_points": 15,

    # Proteksi Akun
    "max_spread_points": 35,             # Toleransi spread forex
    "daily_drawdown_limit": 0.05,
    "equity_stop_loss": 0.10,
    "max_consecutive_losses": 4,
    "max_daily_trades": 120,
    "min_margin_level": 200.0,
    "one_trade_per_bar": False,
    "comment": "Forex_FastScalp",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 2.0},
    {"key": "tp_points", "label": "Take Profit (pts)", "type": "int", "default": 80, "min": 30, "max": 300},
    {"key": "sl_points", "label": "Stop Loss (pts)", "type": "int", "default": 140, "min": 50, "max": 500},
    {"key": "recovery_multiplier", "label": "Pengali Soft Recovery", "type": "float", "default": 1.25, "min": 1.1, "max": 2.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 4, "min": 1, "max": 6},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.05, "min": 0.02, "max": 1.0},
    {"key": "fast_ema_period", "label": "Periode Micro EMA", "type": "int", "default": 7, "min": 3, "max": 20},
    {"key": "rsi_period", "label": "Periode Micro RSI", "type": "int", "default": 7, "min": 3, "max": 20},
    {"key": "max_spread", "label": "Maksimal Spread (pts)", "type": "int", "default": 35, "min": 10, "max": 100},
]

# ==============================================================================
# 3. PENYIMPAN STATUS SIKLUS PERSISTEN
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
}


def on_bar(ctx):
    """Logika scalping kilat untuk Forex."""
    # 1. Filter Spread & Margin
    max_sp = int(ctx.params.get("max_spread", 35))
    if max_sp > 0 and ctx.spread and ctx.spread > max_sp:
        ctx.log(f"Spread Forex ({ctx.spread} pts) melebihi batas {max_sp} pts. Menunggu stabil.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 200.0:
        ctx.log(f"Margin level ({ctx.margin_level:.1f}%) di bawah batas aman. Menahan order.")
        return None

    # 2. Sinkronisasi Siklus & Evaluasi PnL
    curr_balance = float(ctx.balance)
    if STATE["last_balance"] is None and curr_balance > 0:
        STATE["last_balance"] = curr_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 4))
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = curr_balance - STATE["last_balance"]
            if pnl > 0.001:
                ctx.log(f"Siklus Forex PROFIT (+${pnl:.2f})! Reset tahap soft recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = curr_balance
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = curr_balance
                if STATE["recovery_step"] > max_steps:
                    ctx.log(f"Batas recovery ({max_steps}) tercapai. Reset ke Base Lot.")
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(f"Siklus Forex LOSS (-${abs(pnl):.2f}). Soft Recovery Tahap {STATE['recovery_step']}/{max_steps}.")
    else:
        return None

    # 3. Hitung Lot Lembut
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

    tp_pts = int(ctx.params.get("tp_points", 80))
    sl_pts = int(ctx.params.get("sl_points", 140))

    # Pastikan TP/SL di atas spread aktif
    curr_sp = int(ctx.spread) if ctx.spread and ctx.spread > 0 else 0
    if curr_sp > 0:
        tp_pts = max(tp_pts, int(curr_sp * 1.5) + 10)
        sl_pts = max(sl_pts, int(curr_sp * 2.0) + 20)

    # 4. Fast Trigger Momentum Bias
    ema_p = int(ctx.params.get("fast_ema_period", 7))
    rsi_p = int(ctx.params.get("rsi_period", 7))

    direction = "BUY"

    if len(ctx.close) >= max(ema_p, rsi_p, 4):
        ema_arr = ctx.ema(ctx.close, ema_p)
        rsi_arr = ctx.rsi(ctx.close, rsi_p)

        c_last = ctx.close[-1]
        ema_last = ema_arr[-1] if (ema_arr and ema_arr[-1] is not None) else c_last
        rsi_last = rsi_arr[-1] if (rsi_arr and rsi_arr[-1] is not None) else 50.0

        if c_last >= ema_last and rsi_last >= 45:
            direction = "BUY"
        elif c_last < ema_last and rsi_last <= 55:
            direction = "SELL"
        elif rsi_last < 35:
            direction = "BUY"
        elif rsi_last > 65:
            direction = "SELL"
        else:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"
    else:
        if len(ctx.close) > 0 and len(ctx.open) > 0:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"

    # 5. Eksekusi Order Instan
    STATE["has_traded"] = True
    STATE["last_type"] = direction
    order_comment = f"FX_Fast_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(f"⚡ FOREX FAST BUY -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), TP={tp_pts}pts, SL={sl_pts}pts")
        return ctx.buy(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
    else:
        ctx.log(f"⚡ FOREX FAST SELL -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), TP={tp_pts}pts, SL={sl_pts}pts")
        return ctx.sell(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
