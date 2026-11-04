from __future__ import annotations

"""
Raptech Autotrade CLI — Automated Market Recommendation Engine.
Performs real-time multi-timeframe algorithmic market scanning:
volatility (dynamic ATR), trend direction (EMA slope & Price Action),
spread safety verification, and strategy matching.
"""

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Dict, List, Optional

from backend.base import Candle, Tick, TradingBackend
from core.logger import get_logger

logger = get_logger("market_analyzer")


@dataclass
class MarketRecommendation:
    """Standardized market intelligence and trading recommendation report."""
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    spread_pts: int = 0
    high_24h: float = 0.0
    low_24h: float = 0.0
    change_pct: float = 0.0
    condition: str = "Normal"
    volatility: str = "Sedang"
    strategy_recommended: str = "Price Action Hybrid Scalper (M1)"
    readiness_score: str = "[★★★★☆] SIAP TRADING"
    action_hint: str = "Kondisi pasar seimbang untuk scalping presisi."
    updated_at: Optional[datetime] = None


class MarketAnalyzer:
    """Algorithmic multi-instrument scanner and recommendation system."""

    def __init__(self, backend: Optional[TradingBackend] = None) -> None:
        self.backend = backend
        self._cache: Dict[str, MarketRecommendation] = {}
        self._last_scan_time: float = 0.0

    @staticmethod
    def _calculate_ema(prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average (EMA) for given prices."""
        if not prices:
            return 0.0
        if len(prices) < period:
            return sum(prices) / len(prices)
        k = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = (p * k) + (ema * (1.0 - k))
        return ema

    @staticmethod
    def _calculate_atr(candles: List[Candle], period: int = 14) -> float:
        """Calculate Average True Range (ATR) over historical candles."""
        if len(candles) < 2:
            return 0.0
        tr_list = []
        for i in range(1, len(candles)):
            prev = candles[i - 1]
            curr = candles[i]
            hl = curr.high - curr.low
            hc = abs(curr.high - prev.close)
            lc = abs(curr.low - prev.close)
            tr = max(hl, hc, lc)
            tr_list.append(tr)
        
        if not tr_list:
            return 0.0
        eff_period = min(len(tr_list), period)
        return sum(tr_list[-eff_period:]) / eff_period

    def analyze_symbol(
        self,
        symbol: str,
        backend: Optional[TradingBackend] = None,
        timeframe: str = "M1",
    ) -> MarketRecommendation:
        """Perform algorithmic analysis for a specific symbol."""
        active_backend = backend or self.backend
        rec = MarketRecommendation(symbol=symbol, updated_at=datetime.now())

        tick: Optional[Tick] = None
        candles: List[Candle] = []

        if active_backend:
            try:
                tick = active_backend.get_tick(symbol)
            except Exception as e:
                logger.debug(f"Gagal mengambil tick {symbol}: {e}")

            try:
                candles = active_backend.get_candles(symbol, timeframe, count=40)
            except Exception as e:
                logger.debug(f"Gagal mengambil candle {symbol}: {e}")

        # Fallback or synthetic tick if backend returned none
        if tick:
            rec.bid = tick.bid
            rec.ask = tick.ask
        elif candles:
            rec.bid = candles[-1].close
            rec.ask = candles[-1].close

        # Compute digits and spread
        sym_lower = symbol.lower()
        if "xau" in sym_lower or "jpy" in sym_lower:
            digits = 3
        elif "btc" in sym_lower:
            digits = 2
        else:
            digits = 5
        point_scale = 10 ** -digits

        if rec.ask > 0 and rec.bid > 0:
            raw_spread = rec.ask - rec.bid
            rec.spread_pts = max(1, int(round(raw_spread / point_scale)))
        else:
            rec.spread_pts = 20

        # Process candles
        if candles and len(candles) >= 5:
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            closes = [c.close for c in candles]

            rec.high_24h = max(highs)
            rec.low_24h = min(lows)

            first_open = candles[0].open
            last_close = candles[-1].close
            if first_open > 0:
                rec.change_pct = ((last_close - first_open) / first_open) * 100.0

            # Technical indicators
            atr = self._calculate_atr(candles, period=14)
            ema9 = self._calculate_ema(closes, period=9)
            ema21 = self._calculate_ema(closes, period=21)

            # Volatility rating based on relative ATR
            cur_price = max(0.0001, last_close)
            rel_atr = (atr / cur_price) * 100.0

            if "btc" in sym_lower:
                vol_rating = "Ekstrem" if rel_atr > 0.4 else ("Tinggi" if rel_atr > 0.15 else "Sedang")
            elif "xau" in sym_lower or "xag" in sym_lower:
                vol_rating = "Tinggi" if rel_atr > 0.12 else ("Sedang" if rel_atr > 0.05 else "Rendah")
            else:
                vol_rating = "Tinggi" if rel_atr > 0.08 else ("Sedang" if rel_atr > 0.03 else "Rendah")
            rec.volatility = vol_rating

            # Spread safety check
            spread_ratio = (rec.ask - rec.bid) / max(0.00001, atr)
            if spread_ratio > 0.8:
                rec.condition = "Spread Melebar"
                rec.strategy_recommended = "Wait & See (Spread Tinggi)"
                rec.readiness_score = "[★★☆☆☆] WASPADA SPREAD"
                rec.action_hint = "Spread broker sedang melebar melebihi rasio ideal scalping."
                self._cache[symbol] = rec
                return rec

            # Trend & Price Action analysis
            recent_candles = candles[-5:]
            bullish_count = sum(1 for c in recent_candles if c.close > c.open)
            bearish_count = sum(1 for c in recent_candles if c.close < c.open)

            # Trend slope
            if ema9 > ema21 and last_close > ema9:
                trend = "BULLISH"
            elif ema9 < ema21 and last_close < ema9:
                trend = "BEARISH"
            else:
                trend = "SIDEWAYS"

            if trend == "BULLISH":
                if bullish_count >= 3 and rec.change_pct > 0:
                    rec.condition = "Strong Bullish M1"
                    rec.strategy_recommended = "Price Action Breakout (M1)"
                    rec.readiness_score = "[★★★★★] SIAP TRADING"
                    rec.action_hint = "Momentum naik kuat terkonfirmasi. Sangat ideal untuk entry breakout."
                else:
                    rec.condition = "Bullish Expansion"
                    rec.strategy_recommended = "Price Action Hybrid Scalper (M1)"
                    rec.readiness_score = "[★★★★☆] SIAP TRADING"
                    rec.action_hint = "Tren bullish teratur dengan pergerakan stabil."
            elif trend == "BEARISH":
                if bearish_count >= 3 and rec.change_pct < 0:
                    rec.condition = "Strong Bearish M1"
                    rec.strategy_recommended = "Price Action Breakout (M1)"
                    rec.readiness_score = "[★★★★★] SIAP TRADING"
                    rec.action_hint = "Tekanan jual dominan. Optimal untuk mengikuti breakout ke bawah."
                else:
                    rec.condition = "Bearish Expansion"
                    rec.strategy_recommended = "Price Action Hybrid Scalper (M1)"
                    rec.readiness_score = "[★★★★☆] SIAP TRADING"
                    rec.action_hint = "Tren menurun stabil, pas untuk pola hybrid scalper."
            else:
                # Sideways / Range-bound
                # Check for pin-bar rejection opportunities
                wicks_present = False
                for c in recent_candles:
                    rng = c.high - c.low
                    if rng > 0:
                        upper_wick = c.high - max(c.open, c.close)
                        lower_wick = min(c.open, c.close) - c.low
                        if (upper_wick / rng > 0.45) or (lower_wick / rng > 0.45):
                            wicks_present = True
                            break

                if wicks_present:
                    rec.condition = "Range-Bound / Rejection"
                    rec.strategy_recommended = "Pin Bar Rejection (M1)"
                    rec.readiness_score = "[★★★★☆] SIAP TRADING"
                    rec.action_hint = "Pasar berada di batas support/resistance dengan sinyal rejection ekor candle."
                else:
                    rec.condition = "Konsolidasi Pasif"
                    rec.strategy_recommended = "Price Action Hybrid Scalper (M1)"
                    rec.readiness_score = "[★★★☆☆] WAIT & SEE"
                    rec.action_hint = "Pergerakan harga mendatar. Gunakan lot minimum atau tunggu breakout."
        else:
            # Baseline estimation if no historical candles available
            rec.high_24h = rec.bid * 1.004 if rec.bid > 0 else 0.0
            rec.low_24h = rec.bid * 0.996 if rec.bid > 0 else 0.0
            rec.change_pct = 0.0
            rec.volatility = "Sedang"
            rec.condition = "Monitoring Aktif"
            rec.strategy_recommended = "Price Action Hybrid Scalper (M1)"
            rec.readiness_score = "[★★★★☆] SIAP TRADING"
            rec.action_hint = "Menunggu tick/bar baru dari terminal broker."

        self._cache[symbol] = rec
        return rec

    def scan_all(
        self,
        symbols: List[str],
        backend: Optional[TradingBackend] = None,
        timeframe: str = "M1",
    ) -> List[MarketRecommendation]:
        """Scan multiple instruments and return prioritized recommendations."""
        results = []
        for sym in symbols:
            try:
                rec = self.analyze_symbol(sym, backend=backend, timeframe=timeframe)
                results.append(rec)
            except Exception as e:
                logger.error(f"Error memindai instrumen {sym}: {e}")
                # Safe fallback item
                results.append(MarketRecommendation(symbol=sym))
        return results
