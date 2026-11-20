"""Strategi Fast Cycle & Adaptive Market Recovery (Mode Programmer - Instant Trigger).

Karakteristik Strategi:
1. Instant Fast Entry: LANGSUNG membuka posisi pada bar pertama tanpa menunggu lama.
2. Fast Turnover Cycle: Menggunakan target Take Profit (TP) scalping cepat untuk mengunci profit.
3. Adaptive Direction: Menyesuaikan arah pasar (bila tren bullish buka BUY, jika tren bearish
   saat recovery buka SELL untuk mengikuti arah momentum pasar).
4. Smart Loss Recovery: Jika posisi sebelumnya terkena Stop Loss, strategi otomatis menaikkan
   tahap recovery secara terukur untuk memulihkan kerugian di siklus berikutnya.
5. 24/7 Ready (Tanpa Blokir Waktu): Bebas batasan jam/hari agar bisa langsung ditest kapan saja
   (termasuk untuk simbol Crypto BTCUSDm di akhir pekan).
6. Strict Risk Shield: Dilengkapi batas maksimal tahap recovery (Max Steps) dan batas maksimal lot (Max Lot)
   agar akun tetap aman dari drawdown liar.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS)
# ==============================================================================
SETTINGS = {
    # Instrumen & Timeframe
    "symbol": "BTCUSDm",                 # Default Crypto 24/7 (ganti ke EURUSDm saat market forex buka)
    "timeframe": "M1",                   # Timeframe M1 untuk eksekusi siklus super cepat
    "volume": 0.01,                      # Base lot awal
    "max_positions": 1,                  # Disiplin 1 posisi saja per siklus

    # Target Cuan & Stop Loss Cepat
    "tp_points": 100,                    # Target Take Profit cepat (10 pips)
    "sl_points": 150,                    # Stop Loss terukur (15 pips)

    # Proteksi Profit Kunci Modal
    "break_even_enabled": True,          # Geser SL ke entry saat floating profit
    "break_even_points": 60,             # Aktif di +60 points
    "break_even_offset_points": 10,      # Kunci 10 points di atas harga masuk
    "trailing_stop_enabled": True,       # Amankan profit saat pergerakan berlanjut kencang
    "trailing_stop_points": 80,          # Jarak trailing 80 points
    "trailing_step_points": 20,          # Step pergerakan trailing

    # Proteksi Keamanan Risiko Akun
    "max_spread_points": 2500,           # Toleransi spread ramah Crypto BTC & Forex agar tidak terblokir gerbang risiko
    "daily_drawdown_limit": 0.05,        # Batas maksimal drawdown harian 5%
    "equity_stop_loss": 0.10,            # Cut off proteksi jika equity drop 10%
    "max_consecutive_losses": 4,         # Istirahat jika 4 loss beruntun
    "max_daily_trades": 50,              # Maksimal 50 trade per hari
    "min_margin_level": 150.0,           # Margin level minimal 150%

    # Kontrol Eksekusi Instan
    "one_trade_per_bar": False,          # Siklus kilat: langsung buka order baru setelah posisi tertutup
    "comment": "FastCycleRecovery",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 1.0},
    {"key": "tp_points", "label": "Take Profit (pts)", "type": "int", "default": 100, "min": 20, "max": 500},
    {"key": "sl_points", "label": "Stop Loss (pts)", "type": "int", "default": 150, "min": 30, "max": 600},
    {"key": "recovery_multiplier", "label": "Pengali Lot Recovery", "type": "float", "default": 2.0, "min": 1.2, "max": 3.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 3, "min": 1, "max": 5},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.16, "min": 0.02, "max": 5.0},
    {"key": "adaptive_direction", "label": "Arah Adaptif Tren Pasar (1=Ya, 0=Selalu BUY)", "type": "int", "default": 1, "min": 0, "max": 1},
    {"key": "ema_trend_period", "label": "Periode EMA Arah Pasar", "type": "int", "default": 20, "min": 5, "max": 100},
    {"key": "max_spread", "label": "Maksimal Spread (pts)", "type": "int", "default": 2500, "min": 5, "max": 10000},
]

# ==============================================================================
# 3. PENYIMPAN STATUS SIKLUS & RECOVERY (PERSISTEN ANTAR-BAR)
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
}


def on_bar(ctx):
    """Logika eksekusi instan dan recovery adaptif per bar."""
    # --------------------------------------------------------------------------
    # FILTER 1: Toleransi Spread & Margin Dasar
    # --------------------------------------------------------------------------
    # Deteksi aset bernilai tinggi / Crypto (seperti BTCUSDm dengan harga > 1000)
    is_high_value = bool(ctx.close and ctx.close[-1] > 1000)

    max_sp = int(ctx.params.get("max_spread", 100))
    if is_high_value:
        max_sp = max(max_sp, 3500)

    if max_sp > 0 and ctx.spread and ctx.spread > max_sp:
        ctx.log(f"Spread saat ini ({ctx.spread} pts) melebihi batas {max_sp} pts. Menunggu spread stabil.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 150.0:
        ctx.log(f"Margin level tipis ({ctx.margin_level:.1f}%). Eksekusi ditahan demi keamanan.")
        return None

    # --------------------------------------------------------------------------
    # SINKRONISASI HASIL SIKLUS SEBELUMNYA (WIN / LOSS TRACKER)
    # --------------------------------------------------------------------------
    current_balance = float(ctx.balance)
    if STATE["last_balance"] is None and current_balance > 0:
        STATE["last_balance"] = current_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 3))

    # Cek apakah saat ini ada posisi aktif
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        # Jika baru saja ada posisi yang tertutup, evaluasi PnL perubahan saldo
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = current_balance - STATE["last_balance"]

            # Jika saldo bertambah -> Siklus Menang (Profit)
            if pnl > 0.001:
                ctx.log(f"Siklus SEBELUMNYA PROFIT (+${pnl:.2f})! Reset tahap recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = current_balance

            # Jika saldo berkurang -> Siklus Kalah (Loss) -> Naikkan Tahap Recovery
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = current_balance

                if STATE["recovery_step"] > max_steps:
                    ctx.log(
                        f"Batas maksimal recovery ({max_steps} tahap) tercapai. "
                        f"Mereset ke Base Lot demi disiplin dan proteksi modal."
                    )
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(
                        f"Siklus SEBELUMNYA LOSS (-${abs(pnl):.2f}). "
                        f"Mengaktifkan Fast Recovery Tahap {STATE['recovery_step']}/{max_steps}!"
                    )
    else:
        # Sedang ada posisi aktif berjalan: disiplin tunggu siklus ini selesai
        return None

    # --------------------------------------------------------------------------
    # HITUNG SIZING LOT RECOVERY CEPAT
    # --------------------------------------------------------------------------
    base_lot = float(ctx.params.get("base_lot", 0.01))
    rec_mult = float(ctx.params.get("recovery_multiplier", 2.0))
    max_lot = float(ctx.params.get("max_lot_cap", 0.16))

    step = STATE["recovery_step"]
    # Perhitungan lot: base_lot * (multiplier ^ step)
    calc_lot = round(base_lot * (rec_mult ** step), 2)
    exec_lot = min(calc_lot, max_lot)
    if exec_lot < 0.01:
        exec_lot = 0.01

    tp_pts = int(ctx.params.get("tp_points", 100))
    sl_pts = int(ctx.params.get("sl_points", 150))

    curr_sp = int(ctx.spread) if ctx.spread and ctx.spread > 0 else 0
    if is_high_value:
        # Aset bernilai tinggi (Crypto BTC/ETH): adaptasi jarak poin agar aman dari spread ribuan poin
        sl_pts = max(sl_pts, int(curr_sp * 2.5), 3000)
        tp_pts = max(tp_pts, int(curr_sp * 1.8), 2000)
    elif curr_sp > 0:
        # Aset Forex / reguler: pastikan minimal di atas 1.5x spread saat ini
        sl_pts = max(sl_pts, int(curr_sp * 1.5) + 10)
        tp_pts = max(tp_pts, int(curr_sp * 1.2) + 10)

    # --------------------------------------------------------------------------
    # PENENTUAN ARAH EKSEKUSI (INSTANT & ADAPTIF MENGIKUTI ARAH PASAR)
    # --------------------------------------------------------------------------
    use_adaptive = int(ctx.params.get("adaptive_direction", 1)) == 1
    direction = "BUY"  # Default cepat: BUY langsung

    if use_adaptive:
        ema_p = int(ctx.params.get("ema_trend_period", 20))
        # Jika data candle historis cukup untuk menghitung EMA
        if len(ctx.close) >= ema_p:
            ema_vals = ctx.ema(ctx.close, ema_p)
            if ema_vals and ema_vals[-1] is not None:
                ema_curr = ema_vals[-1]
                close_curr = ctx.close[-1]

                # Jika harga di atas EMA -> Tren bullish (BUY)
                # Jika harga di bawah EMA -> Tren bearish (SELL)
                if close_curr >= ema_curr:
                    direction = "BUY"
                else:
                    direction = "SELL"

    # --------------------------------------------------------------------------
    # EKSEKUSI ORDER INSTAN (LANGSUNG BUKA POSISI)
    # --------------------------------------------------------------------------
    STATE["has_traded"] = True
    STATE["last_type"] = direction

    order_comment = f"FastRec_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(
            f"⚡ INSTANT OPEN [BUY] -> Lot={exec_lot:.2f} (Step {step}), "
            f"TP={tp_pts}pts, SL={sl_pts}pts | Simbol: {ctx.symbol}"
        )
        return ctx.buy(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
    else:
        ctx.log(
            f"⚡ INSTANT OPEN [SELL] -> Lot={exec_lot:.2f} (Step {step}), "
            f"TP={tp_pts}pts, SL={sl_pts}pts | Simbol: {ctx.symbol}"
        )
        return ctx.sell(volume=exec_lot, sl_points=sl_pts, tp_points=tp_pts, comment=order_comment)
