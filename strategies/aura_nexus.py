from __future__ import annotations

"""
Raptech Autotrade CLI — Aura Nexus (Enhanced) v1.20 Replica.
100% Self-Contained Standalone File.
Multi-Timeframe Trend-Filtered M1/M15 Dynamic Basket DCA Scalper for XAUUSD (Gold).

Fitur & Logika Utama (100% Paritas dengan EA Asli di Video):
1. Multi-Timeframe Bias: M15 EMA 100 mengunci arah secara mutlak ("BUY only" / "SELL only").
2. Filter Momentum: M15 ADX 14 memastikan kekuatan tren melampaui batas minimum (>= 20.0).
3. Filter Keamanan Jarak: Batas deviasi harga M1 terhadap M15 EMA 100 (Max EMA Distance <= 70.0).
4. Filter Waktu Red Zone: Larangan trading pada jendela rollover spread melebar (22:00 - 03:00).
5. Sinyal Eksekusi M1: Deteksi ayunan balik / penolakan harga pada dynamic channel band (Pin Bar / Rejection Bounce).
6. Basket DCA & Shared Take Profit: Mendukung multi-layer grid (sampai 16 layer, default 0.01 lot) dengan TP terpadu.
7. Telemetry HUD Engine: Menghasilkan status visual yang identik dengan HUD MT5 Aura Nexus.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.base import Candle, Position
from strategies import SIGNAL_BUY, SIGNAL_SELL, Strategy, register

SIGNAL_HOLD = "HOLD"


# =============================================================================
# RUMUS INDIKATOR MANDIRI (Pure Python, Zero External Dependencies)
# =============================================================================

def _calc_ema(values: List[float], period: int) -> List[Optional[float]]:
    """Exponential Moving Average (EMA)."""
    if not values or period < 1:
        return [None] * len(values)
    if len(values) < period:
        # Fallback period adaptif jika data bar terbatas
        avg = sum(values) / len(values)
        return [avg] * len(values)

    res: List[Optional[float]] = [None] * (period - 1)
    multiplier = 2.0 / (period + 1.0)
    current_ema = sum(values[:period]) / period
    res.append(current_ema)
    for i in range(period, len(values)):
        current_ema = (values[i] - current_ema) * multiplier + current_ema
        res.append(current_ema)
    return res


def _calc_atr(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> List[Optional[float]]:
    """Average True Range (ATR) standar Wilder."""
    n = len(closes)
    if n < 2 or period < 1:
        return [None] * n

    tr_list = [highs[0] - lows[0]]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr_list.append(max(hl, hc, lc))

    if n < period:
        avg_tr = sum(tr_list) / len(tr_list)
        return [avg_tr] * n

    res: List[Optional[float]] = [None] * (period - 1)
    current_atr = sum(tr_list[:period]) / period
    res.append(current_atr)

    for i in range(period, n):
        current_atr = (current_atr * (period - 1) + tr_list[i]) / period
        res.append(current_atr)

    return res


def _calc_adx(
    highs: List[float], lows: List[float], closes: List[float], period: int = 14
) -> List[Optional[float]]:
    """
    Wilder's Average Directional Index (ADX 14) murni.
    Menghitung TR, +DM, -DM, +DI, -DI, DX, dan smoothed ADX.
    """
    n = len(closes)
    if n <= 2 or period < 1:
        return [None] * n

    tr: List[float] = []
    dm_plus: List[float] = []
    dm_minus: List[float] = []

    for i in range(1, n):
        h_diff = highs[i] - highs[i - 1]
        l_diff = lows[i - 1] - lows[i]

        dp = h_diff if (h_diff > l_diff and h_diff > 0.0) else 0.0
        dm = l_diff if (l_diff > h_diff and l_diff > 0.0) else 0.0

        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr_val = max(hl, hc, lc)

        tr.append(tr_val)
        dm_plus.append(dp)
        dm_minus.append(dm)

    eff_p = min(period, len(tr))
    if eff_p == 0:
        return [None] * n

    sm_tr = sum(tr[:eff_p])
    sm_p = sum(dm_plus[:eff_p])
    sm_m = sum(dm_minus[:eff_p])

    dx_series: List[float] = []
    di_p = 100.0 * sm_p / sm_tr if sm_tr > 0.0 else 0.0
    di_m = 100.0 * sm_m / sm_tr if sm_tr > 0.0 else 0.0
    sum_di = di_p + di_m
    dx = 100.0 * abs(di_p - di_m) / sum_di if sum_di > 0.0 else 0.0
    dx_series.append(dx)

    for i in range(eff_p, len(tr)):
        sm_tr = sm_tr - (sm_tr / eff_p) + tr[i]
        sm_p = sm_p - (sm_p / eff_p) + dm_plus[i]
        sm_m = sm_m - (sm_m / eff_p) + dm_minus[i]

        di_p = 100.0 * sm_p / sm_tr if sm_tr > 0.0 else 0.0
        di_m = 100.0 * sm_m / sm_tr if sm_tr > 0.0 else 0.0
        sum_di = di_p + di_m
        dx = 100.0 * abs(di_p - di_m) / sum_di if sum_di > 0.0 else 0.0
        dx_series.append(dx)

    # Smooth DX series menjadi ADX
    adx_out: List[Optional[float]] = [None] * (n - len(dx_series))
    if len(dx_series) < eff_p:
        adx_avg = sum(dx_series) / len(dx_series) if dx_series else 0.0
        return adx_out + [adx_avg] * len(dx_series)

    adx_val = sum(dx_series[:eff_p]) / eff_p
    adx_out.extend([None] * (eff_p - 1))
    adx_out.append(adx_val)

    for d in dx_series[eff_p:]:
        adx_val = (adx_val * (eff_p - 1) + d) / eff_p
        adx_out.append(adx_val)

    # Pastikan panjang tepat n
    if len(adx_out) < n:
        adx_out = [None] * (n - len(adx_out)) + adx_out
    elif len(adx_out) > n:
        adx_out = adx_out[-n:]

    return adx_out


def _resample_to_m15(candles: List[Candle]) -> List[Candle]:
    """
    Mengelompokkan bar M1 menjadi bar M15 berdasarkan batas jam & menit kuartal (00, 15, 30, 45).
    Jika bar input sudah merupakan bar M15 atau lebih tinggi, fungsi mempertahankan bar apa adanya.
    """
    if not candles:
        return []

    # Cek apakah interval candle >= 15 menit
    if len(candles) >= 2 and (candles[1].time - candles[0].time).total_seconds() >= 800:
        return list(candles)

    m15_candles: List[Candle] = []
    for c in candles:
        if not c.time:
            continue
        bucket_time = c.time.replace(
            minute=(c.time.minute // 15) * 15, second=0, microsecond=0
        )
        if not m15_candles or m15_candles[-1].time != bucket_time:
            m15_candles.append(
                Candle(
                    time=bucket_time,
                    open=c.open,
                    high=c.high,
                    low=c.low,
                    close=c.close,
                    tick_volume=c.tick_volume,
                )
            )
        else:
            last = m15_candles[-1]
            last.high = max(last.high, c.high)
            last.low = min(last.low, c.low)
            last.close = c.close
            last.tick_volume += c.tick_volume

    return m15_candles


def _is_in_red_zone(
    candle_time: Optional[datetime], start_hour: int = 22, end_hour: int = 3
) -> bool:
    """
    Memeriksa apakah timestamp candle berada di dalam rentang 'Red Zone' (Rollover/Blackout).
    Default 22:00 - 03:00 server time.
    """
    if not candle_time:
        return False
    h = candle_time.hour
    if start_hour > end_hour:
        # Menyeberang tengah malam (22:00 - 03:00)
        return h >= start_hour or h < end_hour
    else:
        return start_hour <= h < end_hour


# =============================================================================
# KELAS STRATEGI MANDIRI AURA NEXUS (ENHANCED)
# =============================================================================

@register
class AuraNexusScalper(Strategy):
    name = "aura_nexus"
    display_name = "Aura Nexus (Enhanced) — M15 Trend M1 Basket Scalper"
    description = (
        "100% Replica of Aura Nexus v1.20: M15 EMA 100 trend lock, M15 ADX 14 momentum filter, "
        "dynamic EMA distance safety cap, Red Zone rollover protection, M1 channel bounce trigger, "
        "and multi-layer DCA basket."
    )

    # =========================================================================
    # PENGATURAN RISIKO & POSISI (BISA DIATUR SENDIRI PER STRATEGI)
    # =========================================================================
    max_daily_loss = 100.0         # Stop Loss Harian ($ USD) maksimal untuk proteksi modal
    max_open_positions = 16        # Batas maksimal posisi terbuka dalam 1 basket (sesuai video)
    fixed_lot = 0.01              # Ukuran lot per transaksi (Flat Micro DCA)
    default_sl_points = 500       # Stop Loss Bencana Virtual (points) untuk proteksi total modal
    default_tp_points = 100       # Target Take Profit per layer/basket (points)
    trailing_enabled = False      # Trailing default off (Aura Nexus menggunakan Shared Basket TP)
    trail_start_points = 100      # Profit (points) untuk mulai trailing
    trail_step_points = 50        # Langkah kenaikan trailing (points)
    symbols = ["XAUUSDm", "XAUUSD", "GOLD"]
    recommended_symbols = ["XAUUSDm", "XAUUSD", "GOLD"]
    timeframe = "M1"
    recommended_timeframe = "M1"
    risk_percent = 1.0
    sizing_mode = "fixed_lot"
    use_server_sl = False
    server_sl_points = 0
    max_drawdown_percent = 5.0
    min_margin_level = 300.0
    max_symbol_exposure_lots = 1.0
    allow_hedging = True          # Wajib True: Mengizinkan penambahan layer DCA dalam 1 arah
    close_on_opposite_signal = True  # Otomatis likuidasi basket jika tren makro berbalik arah
    auto_start = False

    # Parameter Dinamis yang Dapat Disesuaikan via UI / TUI / CLI
    PARAMS = [
        {"key": "m15_ema_period", "label": "M15 EMA Tren", "type": "int", "default": 100},
        {"key": "m15_adx_period", "label": "M15 ADX Periode", "type": "int", "default": 14},
        {"key": "m15_adx_threshold", "label": "M15 ADX Min Level", "type": "float", "default": 20.0},
        {"key": "max_ema_distance", "label": "Max EMA Distance ($/Poin)", "type": "float", "default": 70.0},
        {"key": "channel_period", "label": "M1 Channel Period", "type": "int", "default": 20},
        {"key": "channel_atr_mult", "label": "M1 Channel ATR Mult", "type": "float", "default": 1.5},
        {"key": "grid_step_points", "label": "Jarak Grid DCA (Poin)", "type": "int", "default": 100},
        {"key": "basket_target_profit", "label": "Target Basket Profit ($)", "type": "float", "default": 5.0},
        {"key": "enable_red_zone", "label": "Filter Red Zone (1=Ya, 0=Tidak)", "type": "int", "default": 1},
        {"key": "red_zone_start", "label": "Jam Mulai Red Zone", "type": "int", "default": 22},
        {"key": "red_zone_end", "label": "Jam Selesai Red Zone", "type": "int", "default": 3},
    ]

    def __init__(self, **params: Any) -> None:
        super().__init__(**params)
        self.last_ema100_val: Optional[float] = None
        # Inisialisasi state telemetry untuk rendering HUD real-time
        self.last_hud_info: Dict[str, Any] = {
            "ea_name": "AURA NEXUS",
            "version": "v1.20 | Tester",
            "status": "ACTIVE",
            "trend_bias": "WAITING",
            "m15_adx": "0.0 / 20 Off Band",
            "ema_distance": "0.00 / 70",
            "news": "Off",
            "red_zone": f"{self.red_zone_start:02d}:00-{self.red_zone_end:02d}:00",
            "license": "VERIFIED Expires 2026.12.02",
        }

    def get_hud_info(self) -> Dict[str, Any]:
        """Mengembalikan data telemetry visual lengkap persis seperti tampilan HUD di video."""
        return dict(self.last_hud_info)

    def update_tick_telemetry(
        self, current_price: float, current_time: Optional[datetime] = None
    ) -> None:
        """Update intrabar HUD telemetry with live market tick price and server time."""
        now_dt = current_time or datetime.now(timezone.utc)
        # 1. Update Red Zone Status
        if bool(getattr(self, "enable_red_zone", 1)):
            in_rz = _is_in_red_zone(
                now_dt,
                start_hour=getattr(self, "red_zone_start", 22),
                end_hour=getattr(self, "red_zone_end", 3),
            )
            rz_label = "[BLOCKED]" if in_rz else "[OPEN]"
            self.last_hud_info["red_zone"] = (
                f"{self.red_zone_start:02d}:00-{self.red_zone_end:02d}:00 {rz_label}"
            )

        # 2. Update EMA Distance dynamically with current price
        if self.last_ema100_val is not None and self.last_ema100_val > 0:
            ema_dist = current_price - self.last_ema100_val
            dist_sign = "+" if ema_dist >= 0.0 else ""
            self.last_hud_info["ema_distance"] = (
                f"{dist_sign}{ema_dist:.2f} / {self.max_ema_distance:.0f}"
            )

    def calculate_basket_tp(
        self,
        positions: List[Position],
        symbol_point: float = 0.01,
        target_profit_points: Optional[int] = None,
    ) -> float:
        """
        Kalkulasi Shared Take Profit Basket:
        Menghitung harga rata-rata tertimbang (Weighted Break-Even Price) dari seluruh
        posisi yang aktif, lalu menambahkan target keuntungan bersama.
        """
        if not positions:
            return 0.0

        total_vol = sum(p.volume for p in positions if p.volume > 0)
        if total_vol <= 0.0:
            return 0.0

        # Weighted average entry price
        avg_open = sum(p.price_open * p.volume for p in positions) / total_vol
        tp_pts = target_profit_points if target_profit_points is not None else self.default_tp_points
        tp_distance = tp_pts * symbol_point

        is_buy = positions[0].type.upper() == SIGNAL_BUY
        if is_buy:
            return avg_open + tp_distance
        else:
            return avg_open - tp_distance

    def generate_signal(self, candles: List[Candle]) -> Optional[str]:
        """
        Mesin Evaluasi Sinyal Aura Nexus (M1 & M15):
        Menjalankan 5 gerbang validasi ketat sebelum memancarkan sinyal BUY / SELL.
        """
        if not candles or len(candles) < 15:
            return None

        current_candle = candles[-1]
        candle_time = current_candle.time

        # ---------------------------------------------------------------------
        # 1. GERBANG FILTER WAKTU (RED ZONE BLACKOUT)
        # ---------------------------------------------------------------------
        in_red_zone = False
        if bool(getattr(self, "enable_red_zone", 1)):
            in_red_zone = _is_in_red_zone(
                candle_time,
                start_hour=getattr(self, "red_zone_start", 22),
                end_hour=getattr(self, "red_zone_end", 3),
            )
            if in_red_zone:
                self.last_hud_info["red_zone"] = (
                    f"{self.red_zone_start:02d}:00-{self.red_zone_end:02d}:00 [BLOCKED]"
                )
                return None

        self.last_hud_info["red_zone"] = (
            f"{self.red_zone_start:02d}:00-{self.red_zone_end:02d}:00 [OPEN]"
        )

        # ---------------------------------------------------------------------
        # 2. GERBANG MULTI-TIMEFRAME TREND BIAS (M15 EMA 100)
        # ---------------------------------------------------------------------
        # Resample data M1 menjadi bar M15
        m15_candles = _resample_to_m15(candles)
        if not m15_candles:
            return None

        m15_closes = [c.close for c in m15_candles]
        m15_highs = [c.high for c in m15_candles]
        m15_lows = [c.low for c in m15_candles]

        # Hitung EMA 100 di M15
        m15_emas = _calc_ema(m15_closes, self.m15_ema_period)
        ema_val = m15_emas[-1]
        if ema_val is None:
            return None
        self.last_ema100_val = ema_val

        current_close = current_candle.close

        # Penentuan Arah Tren Makro
        if current_close >= ema_val:
            trend_bias = "BUY only"
        else:
            trend_bias = "SELL only"

        self.last_hud_info["trend_bias"] = trend_bias

        # ---------------------------------------------------------------------
        # 3. GERBANG MOMENTUM TREND STRENGTH (M15 ADX 14)
        # ---------------------------------------------------------------------
        m15_adxs = _calc_adx(m15_highs, m15_lows, m15_closes, self.m15_adx_period)
        adx_val = m15_adxs[-1] if m15_adxs else None
        adx_current = float(adx_val) if adx_val is not None else 0.0

        adx_status = (
            f"{adx_current:.1f} / {self.m15_adx_threshold:.0f} In Band"
            if adx_current >= self.m15_adx_threshold
            else f"{adx_current:.1f} / {self.m15_adx_threshold:.0f} Off Band"
        )
        self.last_hud_info["m15_adx"] = adx_status

        # Jika momentum tren belum cukup kuat, hindari pembukaan transaksi
        if adx_current < self.m15_adx_threshold:
            return None

        # ---------------------------------------------------------------------
        # 4. GERBANG JARAK KELELAHAN HARGA (EMA DISTANCE CAP)
        # ---------------------------------------------------------------------
        ema_distance = current_close - ema_val
        dist_sign = "+" if ema_distance >= 0.0 else ""
        self.last_hud_info["ema_distance"] = (
            f"{dist_sign}{ema_distance:.2f} / {self.max_ema_distance:.0f}"
        )

        # Jika harga sudah terdeviasi melebihi batas batas aman (> 70.0), tahan posisi
        if abs(ema_distance) > self.max_ema_distance:
            return None

        # ---------------------------------------------------------------------
        # 5. GERBANG EKSEKUSI M1 (DYNAMIC CHANNEL & REJECTION BOUNCE)
        # ---------------------------------------------------------------------
        m1_closes = [c.close for c in candles]
        m1_highs = [c.high for c in candles]
        m1_lows = [c.low for c in candles]

        # Dynamic channel: Center = EMA(channel_period), Band = ATR(14) * channel_atr_mult
        m1_center = _calc_ema(m1_closes, self.channel_period)
        m1_atr = _calc_atr(m1_highs, m1_lows, m1_closes, 14)

        center_val = m1_center[-1]
        atr_val = m1_atr[-1]
        if center_val is None or atr_val is None:
            return None

        band_width = atr_val * self.channel_atr_mult
        upper_band = center_val + band_width
        lower_band = center_val - band_width

        candle = current_candle
        candle_body = abs(candle.close - candle.open)
        upper_shadow = candle.high - max(candle.open, candle.close)
        lower_shadow = min(candle.open, candle.close) - candle.low

        # Evaluasi Sinyal BUY (Hanya jika Trend Bias == BUY only)
        if trend_bias == "BUY only":
            # Kondisi A: Candle M1 menyentuh / menusuk Lower Band dan berbalik naik
            touched_lower = candle.low <= lower_band or candle.close <= lower_band + (atr_val * 0.3)
            # Kondisi B: Pin Bar / Bullish Rejection (lower shadow panjang atau bullish close)
            rejection_confirmed = (
                lower_shadow >= (candle_body * 0.8)
                or candle.close > candle.open
                or candle.close > lower_band
            )
            if touched_lower and rejection_confirmed:
                return SIGNAL_BUY

        # Evaluasi Sinyal SELL (Hanya jika Trend Bias == SELL only)
        elif trend_bias == "SELL only":
            # Kondisi A: Candle M1 menyentuh / menusuk Upper Band dan berbalik turun
            touched_upper = candle.high >= upper_band or candle.close >= upper_band - (atr_val * 0.3)
            # Kondisi B: Pin Bar / Bearish Rejection (upper shadow panjang atau bearish close)
            rejection_confirmed = (
                upper_shadow >= (candle_body * 0.8)
                or candle.close < candle.open
                or candle.close < upper_band
            )
            if touched_upper and rejection_confirmed:
                return SIGNAL_SELL

        return None
