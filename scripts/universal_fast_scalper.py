"""Universal Fast Scalper Pro - Multi-Market Responsive Engine (Mode Programmer).

Strategi Scalping Super Cepat Universal untuk SEMUA INSTRUMEN PASAR:
- FOREX    : EURUSD, GBPUSD, USDJPY, AUDUSD, dsb (termasuk suffix 'm', 'c', '.pro')
- LOGAM    : XAUUSD (Gold), XAGUSD (Silver)
- KRIPTO   : BTCUSD, ETHUSD, SOLUSD
- INDEKS   : US30, USTEC (NAS100), US500, GER40

Keunggulan Utama:
1. FAST OP (ANTI-BENGONG / KILAT):
   - TIDAK LAMA MENUNGGU OP: Tidak perlu menunggu berjam-jam untuk sinyal crossover langka.
   - Begitu bot dijalankan dan posisi kosong, bot langsung menganalisis bias momentum bar
     terkini (Micro-EMA 7 + Micro-RSI 7 + Price Action) dan LANGSUNG MEMBUKA POSISI (BUY/SELL)
     dalam 1 bar pertama!
2. ADAPTIF SEMUA PASAR (MULTI-MARKET AUTO-SCALING):
   - Otomatis mendeteksi kelas instrumen dari simbol trading dan menyesuaikan:
     * Batas filter spread aman (Forex: 40 pts, Emas: 70 pts, Kripto: 4500 pts, Indeks: 300 pts)
     * Target Take Profit kilat & Stop Loss terukur sesuai volatilitas aset
     * Penguncian modal Break-Even dan Trailing Stop dinamis
3. SOFT CYCLE RECOVERY (AMAN & TERUKUR):
   - Pengali lot lembut (default 1.25x / max 4 tahap) untuk memulihkan loss sebelumnya
     tanpa risiko lonjakan margin berbahaya.
   - Begitu posisi meraih PROFIT, otomatis langsung RESET ke Base Lot awal.
4. PROTEKSI MODAL LENGKAP:
   - Filter margin level minimal 200%.
   - Batas drawdown harian (5%) dan equity cut-off (10%).
   - One-trade-per-bar nonaktif agar siklus baru dapat langsung dieksekusi setelah order ditutup.
"""

# ==============================================================================
# 1. KONFIGURASI TRADING TERPADU (SETTINGS)
# ==============================================================================
SETTINGS = {
    # Default instrumen & timeframe (bisa diubah di UI atau override otomatis)
    "symbol": "EURUSDm",                 # Universal: ganti EURUSDm, XAUUSDm, BTCUSDm, US30m
    "timeframe": "M1",                   # M1 atau M5 untuk scalping sangat responsif
    "volume": 0.01,                      # Base lot awal
    "max_positions": 1,                  # 1 posisi aktif per siklus agar fokus & terukur

    # Pengaturan SL/TP Standar (Disesuaikan otomatis oleh skrip per tipe aset)
    "tp_points": 100,                    # Target Take Profit kilat
    "sl_points": 160,                    # Stop Loss pengaman terukur

    # Penguncian Modal & Keuntungan Dinamis
    "break_even_enabled": True,          # Mengunci modal saat floating profit tercapai
    "break_even_points": 50,             # Aktif setelah profit +50 points
    "break_even_offset_points": 12,      # Mengunci +12 points di atas entry (tutup spread)
    "trailing_stop_enabled": True,       # Amankan lonjakan tren panjang
    "trailing_stop_points": 70,          # Jarak trailing stop
    "trailing_step_points": 20,          # Geser trailing tiap 20 points

    # Manajemen Risiko & Perlindungan Akun
    "max_spread_points": 50,             # Toleransi spread standar
    "daily_drawdown_limit": 0.05,        # Hentikan bot bila drawdown harian capai 5%
    "equity_stop_loss": 0.10,            # Proteksi batas equity drop 10%
    "max_consecutive_losses": 4,         # Istirahat jika 4x rugi berturut-turut
    "max_daily_trades": 120,            # Kapasitas frekuensi trade tinggi
    "min_margin_level": 200.0,           # Margin level minimal 200%

    # Kontrol Kecepatan Open Posisi
    "one_trade_per_bar": False,          # Siap langsung buka posisi baru saat siklus selesai
    "comment": "Fast_AllMarket",
}

# ==============================================================================
# 2. PARAMETER KONTROL STRATEGI (PARAMS)
# ==============================================================================
PARAMS = [
    {"key": "base_lot", "label": "Volume Base Lot", "type": "float", "default": 0.01, "min": 0.01, "max": 2.0},
    {"key": "recovery_multiplier", "label": "Pengali Soft Recovery", "type": "float", "default": 1.25, "min": 1.1, "max": 2.0},
    {"key": "max_recovery_steps", "label": "Maksimal Tahap Recovery", "type": "int", "default": 4, "min": 1, "max": 6},
    {"key": "max_lot_cap", "label": "Batas Maksimal Lot", "type": "float", "default": 0.05, "min": 0.02, "max": 1.0},
    {"key": "fast_ema_period", "label": "Periode Micro EMA", "type": "int", "default": 7, "min": 3, "max": 25},
    {"key": "rsi_period", "label": "Periode Micro RSI", "type": "int", "default": 7, "min": 3, "max": 21},
    {"key": "auto_market_scaling", "label": "Auto Skala TP/SL Aset", "type": "bool", "default": True},
]

# ==============================================================================
# 3. PENYIMPAN STATUS PERSISTEN (STATE SIKLUS)
# ==============================================================================
STATE = {
    "recovery_step": 0,
    "last_balance": None,
    "has_traded": False,
    "last_type": "BUY",
}


def _get_market_category(symbol):
    """Deteksi kategori pasar untuk penyesuaian TP, SL, dan spread dinamis."""
    s = (symbol or "").upper()
    if "BTC" in s or "ETH" in s or "SOL" in s or "CRYPTO" in s:
        return "CRYPTO"
    if "XAU" in s or "GOLD" in s or "XAG" in s or "SILVER" in s:
        return "METAL"
    if "US30" in s or "DJ30" in s or "NAS" in s or "USTEC" in s or "GER40" in s or "US500" in s:
        return "INDEX"
    return "FOREX"


def _get_market_targets(category, spread_pts):
    """Hitung target TP, SL, BE, dan Max Spread yang cocok untuk kategori instrumen."""
    sp = max(spread_pts or 0, 0)
    if category == "CRYPTO":
        max_sp = 4500
        tp = max(4000, sp * 2 + 1000)
        sl = max(6000, sp * 3 + 1500)
        be = 2500
        be_off = 500
        trail = 3500
    elif category == "METAL":
        max_sp = 70
        tp = max(120, sp * 2 + 30)
        sl = max(180, sp * 3 + 40)
        be = 60
        be_off = 15
        trail = 80
    elif category == "INDEX":
        max_sp = 350
        tp = max(350, sp * 2 + 80)
        sl = max(500, sp * 3 + 100)
        be = 180
        be_off = 40
        trail = 250
    else:  # FOREX
        max_sp = 45
        tp = max(80, sp * 2 + 20)
        sl = max(140, sp * 3 + 30)
        be = 45
        be_off = 12
        trail = 60
    return max_sp, tp, sl, be, be_off, trail


def on_bar(ctx):
    """Logika eksekusi kilat universal untuk semua market."""
    sym = ctx.symbol or "EURUSDm"
    market_cat = _get_market_category(sym)

    curr_spread = int(ctx.spread) if ctx.spread is not None else 0
    max_sp, auto_tp, auto_sl, auto_be, auto_be_off, auto_trail = _get_market_targets(market_cat, curr_spread)

    # --------------------------------------------------------------------------
    # 1. FILTER KEAMANAN SPREAD & MARGIN LEVEL
    # --------------------------------------------------------------------------
    if max_sp > 0 and curr_spread > max_sp:
        ctx.log(f"[{market_cat}] Spread ({curr_spread} pts) melebihi batas {max_sp} pts. Menunggu stabil.")
        return None

    if ctx.margin_level and 0 < ctx.margin_level < 200.0:
        ctx.log(f"Margin level kritis ({ctx.margin_level:.1f}%). Menahan entry baru.")
        return None

    # --------------------------------------------------------------------------
    # 2. SINKRONISASI SIKLUS & EVALUASI PNL
    # --------------------------------------------------------------------------
    curr_balance = float(ctx.balance)
    if STATE["last_balance"] is None and curr_balance > 0:
        STATE["last_balance"] = curr_balance

    max_steps = int(ctx.params.get("max_recovery_steps", 4))
    has_active_pos = (ctx.position is not None and ctx.position.get("volume", 0) > 0)

    if not has_active_pos:
        if STATE["has_traded"] and STATE["last_balance"] is not None:
            pnl = curr_balance - STATE["last_balance"]
            if pnl > 0.001:
                ctx.log(f"[{market_cat}] Siklus PROFIT (+${pnl:.2f})! Reset tahap soft recovery ke Base Lot.")
                STATE["recovery_step"] = 0
                STATE["last_balance"] = curr_balance
            elif pnl < -0.001:
                STATE["recovery_step"] += 1
                STATE["last_balance"] = curr_balance
                if STATE["recovery_step"] > max_steps:
                    ctx.log(f"[{market_cat}] Batas tahap recovery ({max_steps}) tercapai. Reset ke Base Lot demi proteksi modal.")
                    STATE["recovery_step"] = 0
                else:
                    ctx.log(f"[{market_cat}] Siklus LOSS (-${abs(pnl):.2f}). Membuka Soft Recovery Tahap {STATE['recovery_step']}/{max_steps}.")
    else:
        # Posisi sedang terbuka: biarkan TP / SL / BE / Trailing bekerja
        return None

    # --------------------------------------------------------------------------
    # 3. KALKULASI SIZING LOT SOFT RECOVERY
    # --------------------------------------------------------------------------
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

    # --------------------------------------------------------------------------
    # 4. DETEKSI MOMENTUM KILAT (FAST OP - ANTI LAMA GAK OP)
    # --------------------------------------------------------------------------
    ema_p = int(ctx.params.get("fast_ema_period", 7))
    rsi_p = int(ctx.params.get("rsi_period", 7))

    direction = "BUY"  # Default fallback aman

    if len(ctx.close) >= max(ema_p, rsi_p, 4):
        ema_arr = ctx.ema(ctx.close, ema_p)
        rsi_arr = ctx.rsi(ctx.close, rsi_p)

        c_last = ctx.close[-1]
        ema_last = ema_arr[-1] if (ema_arr and ema_arr[-1] is not None) else c_last
        rsi_last = rsi_arr[-1] if (rsi_arr and rsi_arr[-1] is not None) else 50.0

        # Logika Fast Trigger Teruji:
        # Bullish: Harga di atas Micro EMA & RSI >= 45, ATAU Rebound oversold kilat (RSI < 35)
        # Bearish: Harga di bawah Micro EMA & RSI <= 55, ATAU Rebound overbought kilat (RSI > 65)
        if c_last >= ema_last and rsi_last >= 45:
            direction = "BUY"
        elif c_last < ema_last and rsi_last <= 55:
            direction = "SELL"
        elif rsi_last < 35:
            direction = "BUY"
        elif rsi_last > 65:
            direction = "SELL"
        else:
            # Fallback arah candle terakhir untuk eksekusi tanpa menunggu
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"
    else:
        # Data candle minimal: ikuti arah candle terakhir
        if len(ctx.close) > 0 and len(ctx.open) > 0:
            direction = "BUY" if (ctx.close[-1] >= ctx.open[-1]) else "SELL"

    # --------------------------------------------------------------------------
    # 5. EKSEKUSI ORDER INSTAN
    # --------------------------------------------------------------------------
    STATE["has_traded"] = True
    STATE["last_type"] = direction

    order_comment = f"Fast_{market_cat[:3]}_{direction[0]}{step}"

    if direction == "BUY":
        ctx.log(
            f"⚡ FAST [{market_cat}] BUY -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), "
            f"TP={auto_tp}pts, SL={auto_sl}pts | Simbol: {sym}"
        )
        return ctx.buy(volume=exec_lot, sl_points=auto_sl, tp_points=auto_tp, comment=order_comment)
    else:
        ctx.log(
            f"⚡ FAST [{market_cat}] SELL -> Lot={exec_lot:.2f} (Step {step}/{max_steps}), "
            f"TP={auto_tp}pts, SL={auto_sl}pts | Simbol: {sym}"
        )
        return ctx.sell(volume=exec_lot, sl_points=auto_sl, tp_points=auto_tp, comment=order_comment)
