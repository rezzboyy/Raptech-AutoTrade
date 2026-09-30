"""Engine bot: operasi MT5 tingkat tinggi melalui lapisan backend.

Backend dipilih dari konfigurasi (`settings.backend`):
    - "native": library MetaTrader5 (perilaku lama).
    - "mcp"   : server MCP bawaan terminal (kebal masalah versi library).

Kelas ini TIDAK menjalankan loop sendiri. Loop dikendalikan oleh worker di
controller (satu thread) agar semua panggilan MT5/MCP terjadi di thread yang sama.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from config.settings import settings
from src.logger import get_logger
from src import strategy_loader
from src import trade_rules
from strategies.base import SIGNAL_BUY, SIGNAL_SELL

logger = get_logger("mt5bot")


def make_backend():
    """Buat backend sesuai konfigurasi. Default 'native'."""
    if str(getattr(settings, "backend", "native")).lower() == "mcp":
        from src.backends.mcp_backend import McpBackend
        logger.info("Menggunakan backend MCP (%s).", settings.mcp_endpoint)
        return McpBackend(settings.mcp_endpoint, settings.mcp_api_key)
    from src.backends.native_backend import NativeBackend
    logger.info("Menggunakan backend native (library MetaTrader5).")
    return NativeBackend()


class BotEngine:
    """Membungkus operasi tingkat tinggi untuk dipakai worker thread."""

    def __init__(self, backend=None):
        self.backend = backend if backend is not None else make_backend()
        self.strategy = self._build_strategy()
        # Level SL/TP virtual per ticket: {ticket: {symbol,type,sl,tp}}.
        self._virtual = {}
        # Callback jurnal aksi skrip (diisi worker; aman antar-thread via sinyal Qt).
        self.on_journal = None
        # Pelacakan bar & step trading per simbol (one_trade_per_bar & cooldown)
        self._last_trade_bar = {}
        self._last_trade_step = {}
        self._trade_steps = 0

    def _journal(self, action: str, symbol: str, detail: str, ok: bool = True) -> None:
        """Catat aksi eksekusi ke jurnal (bila callback tersedia). Fail-safe."""
        cb = self.on_journal
        if not cb:
            return
        try:
            cb({"action": action, "symbol": symbol, "detail": detail, "ok": bool(ok)})
        except Exception:  # noqa: BLE001
            pass

    def _build_strategy(self):
        try:
            if settings.strategy_name == "custom_script":
                from strategies.script_runtime import ScriptStrategy
                return ScriptStrategy(settings.script_source, settings.strategy_params)
            return strategy_loader.create(settings.strategy_name, settings.strategy_params)
        except Exception as exc:  # noqa: BLE001
            logger.error("Gagal membuat strategi '%s' (%s), fallback ke ma_cross.",
                         settings.strategy_name, exc)
            return strategy_loader.create("ma_cross", {})

    def rebuild_strategy(self) -> None:
        self.strategy = self._build_strategy()
        logger.info("Strategi diperbarui: %s %s", self.strategy.display_name, self.strategy.params)

    def rebuild_backend(self) -> None:
        """Bangun ulang backend sesuai settings.backend terkini (dipanggil sebelum connect)."""
        self.backend = make_backend()

    # ----- Siklus koneksi -----

    def connect(self) -> bool:
        if not self.backend.connect():
            return False
        valid = []
        adapted = False
        for sym in settings.symbols_list:
            resolved = None
            if hasattr(self.backend, "resolve_symbol"):
                try:
                    resolved = self.backend.resolve_symbol(sym)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("resolve_symbol gagal untuk %s: %s", sym, exc)
            target = resolved or sym
            if self.backend.ensure_symbol(target):
                valid.append(target)
                if target != sym:
                    adapted = True
                    logger.info(
                        "Simbol '%s' disesuaikan otomatis untuk akun ini menjadi '%s' (tipe akun Exness/broker).",
                        sym, target,
                    )
            elif self.backend.ensure_symbol(sym):
                valid.append(sym)
        if valid and (adapted or valid[0] != settings.symbol):
            settings.symbol = valid[0]
            logger.info("Pengaturan simbol aktif diselaraskan ke '%s'.", valid[0])
        if not valid:
            # Jangan gagal-total: tetap terhubung agar daftar simbol termuat &
            # pengguna bisa memilih simbol yang benar (mis. suffix Exness 'EURUSDm').
            logger.warning(
                "Simbol '%s' tidak ditemukan di broker ini. Bot tetap terhubung — "
                "pilih simbol yang benar dari dropdown chart / tab Manual "
                "(broker Exness sering memakai suffix, mis. 'EURUSDm').",
                ", ".join(settings.symbols_list),
            )
        self.rebuild_strategy()
        return True

    def disconnect(self) -> None:
        self.backend.disconnect()

    # ----- Monitoring -----

    def poll_account(self) -> dict:
        acc = self.backend.account_info()
        if not acc:
            return {}
        return {
            "balance": acc.get("balance", 0.0),
            "equity": acc.get("equity", 0.0),
            "margin": acc.get("margin", 0.0),
            "free_margin": acc.get("free_margin", 0.0),
            "profit": acc.get("profit", 0.0),
            "currency": acc.get("currency", ""),
            "account_type": acc.get("account_type", "?"),
            "server": acc.get("server", ""),
            "server_connected": acc.get("server_connected", False),
            "trade_allowed": acc.get("trade_allowed", False),
        }

    def poll_positions(self) -> list:
        return self.backend.positions()

    def close_ticket(self, ticket: int) -> bool:
        # Cari simbol posisi dari daftar posisi terbuka.
        symbol = None
        for p in self.backend.positions():
            if int(p.get("ticket", 0)) == int(ticket):
                symbol = p.get("symbol")
                break
        if symbol is None:
            logger.warning("Posisi %s tidak ditemukan untuk ditutup.", ticket)
            return False
        return self.backend.close_position(int(ticket), symbol).get("ok", False)

    # ----- Chart -----

    def poll_candles(self, symbol: str, count: int = 120) -> list:
        df = self.backend.get_rates(symbol, settings.timeframe_str, count)
        return self._df_to_candles(df)

    def poll_chart(self, symbol: str, count: int = 150) -> dict:
        payload = {"candles": [], "overlays": [], "positions": [], "trades": []}
        if not symbol:
            return payload
        if hasattr(self.backend, "resolve_symbol"):
            symbol = self.backend.resolve_symbol(symbol) or symbol
        self.backend.ensure_symbol(symbol)
        df = self.backend.get_rates(symbol, settings.timeframe_str, count)
        if df is None or df.empty:
            return payload

        payload["candles"] = self._df_to_candles(df)

        # Overlay indikator dari strategi aktif.
        try:
            payload["overlays"] = self.strategy.compute_overlays(df) or []
        except Exception as exc:  # noqa: BLE001
            logger.debug("Gagal hitung overlay chart: %s", exc)

        # Garis posisi terbuka untuk simbol ini.
        try:
            payload["positions"] = [
                {"type": p["type"], "open": p["price_open"], "sl": p["sl"], "tp": p["tp"]}
                for p in self.backend.positions(symbol)
            ]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Gagal ambil posisi chart: %s", exc)

        return payload

    @staticmethod
    def _df_to_candles(df) -> list:
        if df is None or getattr(df, "empty", True):
            return []
        out = []
        for ts, row in df.iterrows():
            try:
                epoch = int(ts.timestamp())
            except (AttributeError, ValueError):
                epoch = 0
            out.append({
                "t": epoch,
                "o": round(float(row["open"]), 5),
                "h": round(float(row["high"]), 5),
                "l": round(float(row["low"]), 5),
                "c": round(float(row["close"]), 5),
            })
        return out

    def list_symbols(self, limit: int = 60) -> list:
        return self.backend.list_symbols(limit)

    # ----- Statistik & kurva ekuitas -----

    def _closed_deals(self, days: int = 90) -> list:
        now = datetime.now(timezone.utc)
        deals = self.backend.history_deals(now - timedelta(days=days), now + timedelta(days=1))
        if settings.magic_number > 0:
            matched = [d for d in deals if int(d.get("magic", 0)) == settings.magic_number]
            if matched:
                return matched
        return deals

    def poll_stats(self) -> dict:
        default = {
            "total_trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
            "win_rate": 0.0, "profit_factor": 0.0, "gross_profit": 0.0,
            "gross_loss": 0.0, "net_profit": 0.0, "avg_profit": 0.0,
            "avg_loss": 0.0, "max_profit": 0.0, "max_loss": 0.0,
        }
        try:
            deals = self._closed_deals(90)
            total = len(deals)
            if total == 0:
                return default
            wins = [d for d in deals if d["net_profit"] > 0]
            losses = [d for d in deals if d["net_profit"] < 0]
            gross_profit = sum(d["net_profit"] for d in wins)
            gross_loss = abs(sum(d["net_profit"] for d in losses))
            net = sum(d["net_profit"] for d in deals)
            return {
                "total_trades": total,
                "wins": len(wins),
                "losses": len(losses),
                "breakeven": total - len(wins) - len(losses),
                "win_rate": round(len(wins) / total * 100.0, 1),
                "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 0.0),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "net_profit": round(net, 2),
                "avg_profit": round(gross_profit / len(wins), 2) if wins else 0.0,
                "avg_loss": round(gross_loss / len(losses), 2) if losses else 0.0,
                "max_profit": round(max((d["net_profit"] for d in deals), default=0.0), 2),
                "max_loss": round(min((d["net_profit"] for d in deals), default=0.0), 2),
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("Error hitung statistik: %s", exc)
            return default

    def poll_equity_curve(self, current_balance: float = 0.0, current_equity: float = 0.0) -> list:
        curve = []
        try:
            deals = sorted(self._closed_deals(90), key=lambda d: d.get("time", 0))
            if deals:
                total_p = sum(d["net_profit"] for d in deals)
                run_bal = (current_balance - total_p) if current_balance > 0 else 0.0
                for d in deals:
                    run_bal += d["net_profit"]
                    curve.append({"t": int(d.get("time", 0)), "balance": round(run_bal, 2), "equity": round(run_bal, 2)})
            if current_balance > 0:
                import time as _t
                curve.append({
                    "t": int(_t.time()),
                    "balance": round(current_balance, 2),
                    "equity": round(current_equity if current_equity > 0 else current_balance, 2),
                })
        except Exception as exc:  # noqa: BLE001
            logger.debug("Error kurva ekuitas: %s", exc)
        return curve[-120:]

    # ----- Trading -----

    def manage_open_positions(self) -> None:
        # Cek umur holding posisi (max_holding_bars) dari skrip
        strat_cfg = getattr(self.strategy, "script_settings", {}) or {}
        mhb = strat_cfg.get("max_holding_bars", 0)
        if mhb and mhb > 0:
            import time as _t
            tf_seconds = {
                "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
                "H1": 3600, "H4": 14400, "D1": 86400,
            }.get(settings.timeframe_str.upper(), 300)
            now_sec = _t.time()
            for p in self.backend.positions():
                pos_time = float(p.get("time", 0))
                if pos_time > 0 and (now_sec - pos_time) >= (mhb * tf_seconds):
                    ticket = p.get("ticket")
                    if ticket:
                        logger.info("Posisi %s ditutup otomatis karena melewati batas max_holding_bars=%d.", ticket, mhb)
                        self.backend.close_position(int(ticket), p["symbol"])
                        self._journal("CLOSE", p["symbol"], f"tutup posisi ticket {ticket} (max holding {mhb} bars)", True)

        # Saat mode virtual aktif, trailing/break-even dikelola pada level virtual
        # (lihat check_virtual_exits), bukan dikirim ke broker.
        if getattr(settings, "virtual_sltp_enabled", False):
            return
        if not settings.break_even_enabled and not settings.trailing_stop_enabled:
            return
        for p in self.backend.positions():
            if settings.magic_number > 0 and p.get("magic", 0) != settings.magic_number:
                continue
            spec = self.backend.symbol_spec(p["symbol"])
            if not spec:
                continue
            if settings.break_even_enabled:
                trade_rules.apply_break_even(
                    self.backend, p, spec,
                    settings.break_even_trigger_points, settings.break_even_offset_points,
                )
            if settings.trailing_stop_enabled:
                trade_rules.apply_trailing_stop(
                    self.backend, p, spec,
                    settings.trailing_stop_points, settings.trailing_step_points,
                )

    def _compute_sl_tp(self, symbol: str, signal: str, entry_price: float, overrides: dict = None):
        spec = self.backend.symbol_spec(symbol)
        if not spec or spec.get("point", 0) <= 0:
            return 0.0, 0.0
        point = spec["point"]
        digits = spec["digits"]

        # Mode persen: SL/TP sebagai persentase dari harga entry.
        # (Diabaikan bila skrip memberi sl_points/tp_points eksplisit.)
        _ov = overrides or {}
        if getattr(settings, "sl_tp_mode", "points") == "percent" \
                and "sl_points" not in _ov and "tp_points" not in _ov:
            slp = float(settings.sl_percent) / 100.0
            tpp = float(settings.tp_percent) / 100.0
            if signal == SIGNAL_BUY:
                return round(entry_price * (1 - slp), digits), round(entry_price * (1 + tpp), digits)
            return round(entry_price * (1 + slp), digits), round(entry_price * (1 - tpp), digits)

        overrides = overrides or {}
        strat_script_cfg = getattr(self.strategy, "script_settings", {}) or {}

        # 1. Hitung SL points (prioritas: intent -> atr_sl_mult -> strategy.params -> settings)
        atr_sl_mult = strat_script_cfg.get("atr_sl_mult")
        if atr_sl_mult and "sl_points" not in overrides and "sl" not in overrides:
            rates = self.backend.get_rates(symbol, settings.timeframe_str, count=25)
            if rates is not None and not rates.empty and len(rates) >= 15:
                from strategies.script_runtime import atr
                atr_vals = atr(rates["high"], rates["low"], rates["close"], 14)
                if atr_vals and atr_vals[-1] is not None and point > 0:
                    sl_pts = int(round(atr_vals[-1] * float(atr_sl_mult) / point))
                else:
                    sl_pts = settings.sl_points
            else:
                sl_pts = settings.sl_points
        else:
            sl_pts = overrides.get(
                "sl_points",
                self.strategy.params.get("sl_points",
                strat_script_cfg.get("sl_points", settings.sl_points)),
            )

        # 2. Hitung TP points (prioritas: intent -> atr_tp_mult -> risk_reward_ratio -> strategy.params -> settings)
        atr_tp_mult = strat_script_cfg.get("atr_tp_mult")
        if atr_tp_mult and "tp_points" not in overrides and "tp" not in overrides:
            rates = self.backend.get_rates(symbol, settings.timeframe_str, count=25)
            if rates is not None and not rates.empty and len(rates) >= 15:
                from strategies.script_runtime import atr
                atr_vals = atr(rates["high"], rates["low"], rates["close"], 14)
                if atr_vals and atr_vals[-1] is not None and point > 0:
                    tp_pts = int(round(atr_vals[-1] * float(atr_tp_mult) / point))
                else:
                    tp_pts = settings.tp_points
            else:
                tp_pts = settings.tp_points
        elif "risk_reward_ratio" in strat_script_cfg and "tp_points" not in overrides and "tp_points" not in self.strategy.params and "tp_points" not in strat_script_cfg:
            try:
                rr = float(strat_script_cfg["risk_reward_ratio"])
                tp_pts = int(round(int(sl_pts) * rr))
            except Exception:
                tp_pts = settings.tp_points
        else:
            tp_pts = overrides.get(
                "tp_points",
                self.strategy.params.get("tp_points",
                strat_script_cfg.get("tp_points", settings.tp_points)),
            )

        try:
            sl_pts, tp_pts = int(sl_pts), int(tp_pts)
        except (TypeError, ValueError):
            sl_pts, tp_pts = settings.sl_points, settings.tp_points

        # Proteksi batas minimal broker (trade_stops_level & spread) untuk mencegah error #10016 (Invalid stops)
        stop_level = int(spec.get("stop_level") or 0)
        curr_spread = 0
        try:
            sp = self.backend.spread_points(symbol)
            if sp is not None and sp > 0:
                curr_spread = int(round(sp))
        except Exception:
            pass

        min_stop_pts = max(stop_level, int(curr_spread * 1.5), int(curr_spread) + 50, 20)
        if sl_pts > 0 and sl_pts < min_stop_pts:
            logger.info("Jarak SL (%d pts) di bawah batas aman (%d pts, stop_lvl=%d, spread=%d). Disesuaikan otomatis.",
                        sl_pts, min_stop_pts, stop_level, curr_spread)
            sl_pts = min_stop_pts

        if tp_pts > 0 and tp_pts < min_stop_pts:
            logger.info("Jarak TP (%d pts) di bawah batas aman (%d pts, stop_lvl=%d, spread=%d). Disesuaikan otomatis.",
                        tp_pts, min_stop_pts, stop_level, curr_spread)
            tp_pts = min_stop_pts

        if signal == SIGNAL_BUY:
            return round(entry_price - sl_pts * point, digits), round(entry_price + tp_pts * point, digits)
        return round(entry_price + sl_pts * point, digits), round(entry_price - tp_pts * point, digits)

    def _handle_signal(self, symbol: str, signal: str, overrides: dict = None) -> bool:
        overrides = overrides or {}
        strat_script_cfg = getattr(self.strategy, "script_settings", {}) or {}
        tick = self.backend.get_tick(symbol)
        if not tick:
            logger.warning(
                "[MARKET TUTUP/DATA KOSONG] Harga live/tick untuk %s tidak tersedia. "
                "Pasar Forex tutup di akhir pekan. Gunakan aset Crypto (BTCUSDm) untuk trading 24/7. Order %s dibatalkan.",
                symbol, signal,
            )
            return False
        entry = tick["ask"] if signal == SIGNAL_BUY else tick["bid"]

        # SL/TP: skrip boleh memberi HARGA absolut (sl/tp) atau points (via _compute_sl_tp).
        if "sl" in overrides or "tp" in overrides:
            comp_sl, comp_tp = self._compute_sl_tp(symbol, signal, entry, overrides)
            sl = float(overrides.get("sl", comp_sl))
            tp = float(overrides.get("tp", comp_tp))
        else:
            sl, tp = self._compute_sl_tp(symbol, signal, entry, overrides)

        spec = self.backend.symbol_spec(symbol)
        acc = self.backend.account_info() or {}

        # Validasi keamanan tambahan untuk SL/TP harga absolut (cegah #10016 Invalid stops)
        if spec and spec.get("point"):
            _pt = float(spec["point"])
            _dg = int(spec.get("digits", 5))
            _stop_lvl = int(spec.get("stop_level") or 0)
            _sp = 0
            try:
                _sp_raw = self.backend.spread_points(symbol)
                if _sp_raw is not None and _sp_raw > 0:
                    _sp = int(round(_sp_raw))
            except Exception:
                pass
            _min_dist = max(_stop_lvl, int(_sp * 1.5), int(_sp) + 50, 20) * _pt
            if signal == SIGNAL_BUY:
                if sl > 0 and (entry - sl) < _min_dist:
                    sl = round(entry - _min_dist, _dg)
                if tp > 0 and (tp - entry) < _min_dist:
                    tp = round(entry + _min_dist, _dg)
            else:
                if sl > 0 and (sl - entry) < _min_dist:
                    sl = round(entry + _min_dist, _dg)
                if tp > 0 and (entry - tp) < _min_dist:
                    tp = round(entry - _min_dist, _dg)

        # Volume: skrip boleh memaksa volume tetap; jika tidak, cek script_settings; jika tidak, hitung dari risk
        if overrides.get("volume") is not None:
            lot = float(overrides["volume"])
        elif strat_script_cfg.get("volume") is not None:
            lot = float(strat_script_cfg["volume"])
        elif strat_script_cfg.get("lot") is not None:
            lot = float(strat_script_cfg["lot"])
        else:
            risk_frac = float(
                overrides.get("risk",
                strat_script_cfg.get("risk",
                strat_script_cfg.get("risk_per_trade", settings.risk_per_trade)))
            )
            lot = trade_rules.calc_lot_from_spec(
                spec, float(acc.get("balance", 0.0)), risk_frac, sl, entry
            )
        if lot <= 0:
            logger.warning("Ukuran lot untuk %s tidak valid (spec/harga belum lengkap), order dibatalkan.", symbol)
            return False

        side = trade_rules.map_signal_to_side(signal)
        cmt = str(overrides.get("comment") or strat_script_cfg.get("comment") or "mt5bot")
        if getattr(settings, "virtual_sltp_enabled", False):
            # Kirim TANPA SL/TP ke broker (tersembunyi); pantau sendiri.
            res = trade_rules.open_order_if_allowed(self.backend, settings, symbol, side, lot, sl=0.0, tp=0.0, comment=cmt)
            if res.get("ok") and res.get("ticket"):
                self._virtual[int(res["ticket"])] = {
                    "symbol": symbol,
                    "type": "BUY" if signal == SIGNAL_BUY else "SELL",
                    "sl": sl, "tp": tp,
                }
                logger.info("Virtual SL/TP diset untuk posisi %s: SL=%.5f TP=%.5f", res["ticket"], sl, tp)
                return True
            return False
        else:
            res = trade_rules.open_order_if_allowed(self.backend, settings, symbol, side, lot, sl=sl, tp=tp, comment=cmt)
            return bool(res.get("ok"))

    def check_virtual_exits(self) -> None:
        """Pantau posisi dengan SL/TP virtual: geser SL (trailing/BE) & tutup bila tercapai.

        Dipanggil tiap detik oleh worker agar proteksi tetap aktif walau auto-trading off.
        """
        if not self._virtual:
            return
        try:
            positions = {int(p["ticket"]): p for p in self.backend.positions()}
        except Exception:  # noqa: BLE001
            return
        for ticket in list(self._virtual):
            if ticket not in positions:
                self._virtual.pop(ticket, None)  # sudah tertutup di luar bot
                continue
            v = self._virtual[ticket]
            spec = self.backend.symbol_spec(v["symbol"])
            tick = self.backend.get_tick(v["symbol"])
            if not spec or not tick:
                continue
            self._update_virtual_sl(positions[ticket], v, spec, tick)
            hit = trade_rules.virtual_exit_hit(v["type"], v.get("sl", 0.0), v.get("tp", 0.0),
                                               tick["bid"], tick["ask"])
            if hit:
                logger.info("Virtual %s tercapai posisi %s (%s) @ bid=%.5f/ask=%.5f -> tutup.",
                            hit, ticket, v["symbol"], tick["bid"], tick["ask"])
                if self.backend.close_position(ticket, v["symbol"]).get("ok"):
                    self._virtual.pop(ticket, None)

    def _update_virtual_sl(self, pos: dict, v: dict, spec: dict, tick: dict) -> None:
        """Geser SL virtual mengikuti break-even & trailing (tanpa kirim ke broker)."""
        point = spec.get("point", 0.0)
        digits = spec.get("digits", 5)
        if point <= 0:
            return
        entry = pos["price_open"]
        cur_sl = v.get("sl", 0.0) or 0.0

        if pos["type"] == "BUY":
            price = tick["bid"]
            if settings.break_even_enabled and settings.break_even_trigger_points > 0:
                if (price - entry) / point >= settings.break_even_trigger_points:
                    be = round(entry + settings.break_even_offset_points * point, digits)
                    if cur_sl == 0 or cur_sl < be:
                        v["sl"] = be; cur_sl = be
            if settings.trailing_stop_enabled and settings.trailing_stop_points > 0:
                ideal = round(price - settings.trailing_stop_points * point, digits)
                if ideal > entry and (cur_sl == 0 or (ideal - cur_sl) >= settings.trailing_step_points * point):
                    v["sl"] = ideal
        else:  # SELL
            price = tick["ask"]
            if settings.break_even_enabled and settings.break_even_trigger_points > 0:
                if (entry - price) / point >= settings.break_even_trigger_points:
                    be = round(entry - settings.break_even_offset_points * point, digits)
                    if cur_sl == 0 or cur_sl > be:
                        v["sl"] = be; cur_sl = be
            if settings.trailing_stop_enabled and settings.trailing_stop_points > 0:
                ideal = round(price + settings.trailing_stop_points * point, digits)
                if ideal < entry and (cur_sl == 0 or (cur_sl - ideal) >= settings.trailing_step_points * point):
                    v["sl"] = ideal

    # ----- Operasi order manual (dari UI) -----

    def poll_orders(self) -> list:
        """Daftar pending order (untuk UI)."""
        try:
            return self.backend.pending_orders()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Gagal ambil pending orders: %s", exc)
            return []

    def manual_market_order(self, symbol: str, side: str, volume: float,
                            sl: float = 0.0, tp: float = 0.0) -> dict:
        """Kirim market order manual dari UI (tetap lewat fail-safe backend)."""
        if hasattr(self.backend, "resolve_symbol"):
            symbol = self.backend.resolve_symbol(symbol) or symbol

        # Validasi keamanan jarak SL/TP manual (cegah #10016 Invalid stops)
        if (sl > 0 or tp > 0):
            spec = self.backend.symbol_spec(symbol)
            tick = self.backend.get_tick(symbol)
            if spec and tick and spec.get("point"):
                _pt = float(spec["point"])
                _dg = int(spec.get("digits", 5))
                _stop_lvl = int(spec.get("stop_level") or 0)
                _sp = 0
                try:
                    _sp_raw = self.backend.spread_points(symbol)
                    if _sp_raw is not None and _sp_raw > 0:
                        _sp = int(round(_sp_raw))
                except Exception:
                    pass
                _min_dist = max(_stop_lvl, int(_sp * 1.5), int(_sp) + 50, 20) * _pt
                is_buy = str(side).upper() in ("BUY", "0")
                entry = float(tick.get("ask", 0.0)) if is_buy else float(tick.get("bid", 0.0))
                if entry > 0:
                    if is_buy:
                        if sl > 0 and (entry - sl) < _min_dist:
                            sl = round(entry - _min_dist, _dg)
                        if tp > 0 and (tp - entry) < _min_dist:
                            tp = round(entry + _min_dist, _dg)
                    else:
                        if sl > 0 and (sl - entry) < _min_dist:
                            sl = round(entry + _min_dist, _dg)
                        if tp > 0 and (entry - tp) < _min_dist:
                            tp = round(entry - _min_dist, _dg)

        res = self.backend.send_market_order(
            symbol, side, volume, sl=sl, tp=tp,
            magic=settings.magic_number, comment="manual",
        )
        logger.info("Order manual %s %s %.2f -> %s", side, symbol, volume,
                    "OK" if res.get("ok") else res.get("message"))
        return res

    def place_pending_order(self, symbol: str, order_type: str, volume: float,
                            price: float, sl: float = 0.0, tp: float = 0.0) -> dict:
        if hasattr(self.backend, "resolve_symbol"):
            symbol = self.backend.resolve_symbol(symbol) or symbol
        res = self.backend.send_pending_order(
            symbol, order_type, volume, price, sl=sl, tp=tp,
            magic=settings.magic_number, comment="manual",
        )
        logger.info("Pending %s %s @ %.5f -> %s", order_type, symbol, price,
                    "OK" if res.get("ok") else res.get("message"))
        return res

    def delete_pending(self, ticket: int) -> bool:
        return self.backend.delete_pending_order(int(ticket)).get("ok", False)

    def close_all(self, symbol: str = "") -> int:
        """Tutup semua posisi (opsional filter simbol + magic). Kembalikan jumlah tertutup."""
        closed = 0
        for p in self.backend.positions(symbol or None):
            if settings.magic_number > 0 and p.get("magic", 0) != settings.magic_number:
                continue
            if self.backend.close_position(int(p["ticket"]), p["symbol"]).get("ok"):
                closed += 1
        logger.info("Tutup semua: %d posisi ditutup.", closed)
        return closed

    def process_trading_step(self) -> bool:
        if not hasattr(self, "_trade_steps"):
            self._trade_steps = 0
        if not hasattr(self, "_last_trade_bar"):
            self._last_trade_bar = {}
        if not hasattr(self, "_last_trade_step"):
            self._last_trade_step = {}
        self._trade_steps += 1

        # 1) Manajemen posisi terbuka (termasuk max_holding_bars).
        self.manage_open_positions()

        now_utc = datetime.now(timezone.utc)
        strat_cfg = getattr(self.strategy, "script_settings", {}) or {}

        # 1c) Filter penutupan Jumat (close_friday_hour)
        cfh = strat_cfg.get("close_friday_hour")
        if cfh is not None and now_utc.weekday() == 4 and now_utc.hour >= cfh:
            if self.backend.positions():
                logger.info("[FILTER JUMAT] Menutup semua posisi menjelang weekend (close_friday_hour=%d).", cfh)
                self.close_all()
            return True

        # 1d) Filter hari aktif (active_days)
        act_days = strat_cfg.get("active_days")
        if act_days is not None and now_utc.weekday() not in act_days:
            return True

        # 1e) Filter jam trading (trade_start_time & trade_end_time)
        t_start = strat_cfg.get("trade_start_time")
        t_end = strat_cfg.get("trade_end_time")
        if t_start or t_end:
            cur_hm = now_utc.strftime("%H:%M")
            if t_start and cur_hm < t_start:
                return True
            if t_end and cur_hm > t_end:
                return True

        # 1b) Equity cut-loss: tutup semua posisi + stop bila drawdown ekuitas
        #     dari balance melewati ambang.
        esl = getattr(settings, "equity_stop_loss", 0.0)
        if esl and esl > 0:
            acc = self.backend.account_info() or {}
            bal = float(acc.get("balance", 0.0))
            eq = float(acc.get("equity", 0.0))
            if bal > 0 and eq > 0:
                dd = (bal - eq) / bal
                if dd >= esl:
                    logger.warning(
                        "[EQUITY CUT-LOSS] Drawdown ekuitas %.2f%% >= %.2f%%. "
                        "Menutup SEMUA posisi & menghentikan auto trading.",
                        dd * 100, esl * 100,
                    )
                    self.close_all()
                    return False

        # 2) Proteksi drawdown harian.
        if settings.daily_drawdown_limit > 0:
            breached, dd = trade_rules.daily_drawdown_breached(
                self.backend, settings.daily_drawdown_limit, settings.magic_number
            )
            if breached:
                logger.warning("[PROTEKSI] Drawdown harian %.2f%% terlampaui. Auto trading nonaktif.", dd * 100)
                return False

        # 3) Batas trade harian.
        if settings.max_daily_trades > 0:
            if trade_rules.daily_trade_count(self.backend, settings.magic_number) >= settings.max_daily_trades:
                return True

        # 4) Evaluasi strategi per simbol.
        for sym in settings.symbols_list:
            df = self.backend.get_rates(sym, settings.timeframe_str, count=200)
            if df is None or df.empty:
                continue
            cur_bar_time = str(df.index[-1]) if len(df.index) > 0 else ""
            # Beri konteks runtime ke strategi skrip (posisi, akun, tick/harga) agar
            # skrip bisa cek ctx.position, harga live, dan sizing berbasis saldo.
            binder = getattr(self.strategy, "bind_runtime", None)
            if callable(binder):
                try:
                    binder(symbol=sym, positions=self.backend.positions(sym),
                           account=self.backend.account_info() or {},
                           tick=self.backend.get_tick(sym),
                           spec=self.backend.symbol_spec(sym))
                except Exception:  # noqa: BLE001
                    try:
                        binder(symbol=sym)
                    except Exception:  # noqa: BLE001
                        pass
            result = self.strategy.generate_signal(df)
            for cmd in self._normalize_commands(result):
                cmd["_bar_time"] = cur_bar_time
                self._execute_command(sym, cmd)
        return True

    @staticmethod
    def _normalize_commands(result) -> list:
        """Seragamkan hasil strategi ke daftar perintah dict."""
        if result is None:
            return []
        if isinstance(result, str):
            return [{"action": result}] if result in (SIGNAL_BUY, SIGNAL_SELL) else []
        if isinstance(result, dict):
            return [result] if result.get("action") else []
        if isinstance(result, (list, tuple)):
            return [c for c in result if isinstance(c, dict) and c.get("action")]
        return []

    def _execute_command(self, symbol: str, cmd: dict) -> None:
        """Eksekusi satu perintah strategi. OPEN dibatasi gerbang posisi;
        CLOSE/MODIFY selalu dijalankan (fail-safe per perintah)."""
        action = cmd.get("action")
        strat_cfg = getattr(self.strategy, "script_settings", {}) or {}
        try:
            if action in (SIGNAL_BUY, SIGNAL_SELL):
                # 1. Close on reversal bila ada posisi arah berlawanan
                if strat_cfg.get("close_on_reversal", True):
                    opp_side = "SELL" if action == SIGNAL_BUY else "BUY"
                    for p in self.backend.positions(symbol):
                        if settings.magic_number > 0 and p.get("magic", 0) != settings.magic_number:
                            continue
                        p_type = str(p.get("type", "")).upper()
                        if (opp_side == "SELL" and ("SELL" in p_type or p_type == "1")) or \
                           (opp_side == "BUY" and ("BUY" in p_type or p_type == "0")):
                            t_num = p.get("ticket")
                            if t_num:
                                self.backend.close_position(int(t_num), symbol)
                                self._virtual.pop(int(t_num), None)
                                self._journal("REVERSAL", symbol, f"tutup posisi ticket {t_num} ({opp_side}) sebelum balik arah", True)

                # 2. Min margin level filter
                min_ml = float(strat_cfg.get("min_margin_level", 0.0))
                if min_ml > 0:
                    acc = self.backend.account_info() or {}
                    m = float(acc.get("margin", 0.0))
                    eq = float(acc.get("equity", 0.0))
                    lvl = float(acc.get("margin_level", (eq / m * 100) if m > 0 else 99999))
                    if lvl < min_ml:
                        self._journal(action, symbol, f"dilewati (margin level {lvl:.1f}% < batas {min_ml:.1f}%)", False)
                        return

                # 3. One trade per bar filter
                if strat_cfg.get("one_trade_per_bar", True):
                    bar_time = cmd.get("_bar_time", "")
                    if bar_time and self._last_trade_bar.get(symbol) == bar_time:
                        self._journal(action, symbol, "dilewati (one_trade_per_bar: sudah trade di bar ini)", False)
                        return

                # 4. Cooldown bars filter
                cd_bars = int(strat_cfg.get("cooldown_bars", 0))
                if cd_bars > 0:
                    last_step = self._last_trade_step.get(symbol, 0)
                    if (self._trade_steps - last_step) < cd_bars:
                        self._journal(action, symbol, f"dilewati (cooldown {cd_bars} bar)", False)
                        return

                if trade_rules.can_open_new_position(
                        self.backend, symbol, settings.magic_number, settings.max_open_positions):
                    sent = self._handle_signal(symbol, action, cmd)
                    if sent:
                        vol = cmd.get("volume", "auto")
                        self._journal(action, symbol,
                                      f"buka {action} vol={vol} sl_pts={cmd.get('sl_points','-')} "
                                      f"tp_pts={cmd.get('tp_points','-')}", True)
                        # Catat bar & step sukses
                        if cmd.get("_bar_time"):
                            self._last_trade_bar[symbol] = cmd["_bar_time"]
                        self._last_trade_step[symbol] = self._trade_steps
                else:
                    self._journal(action, symbol, "dilewati (batas Maks Posisi tercapai)", False)
            elif action == "CLOSE":
                ticket = cmd.get("ticket")
                if ticket:
                    ok = self.backend.close_position(int(ticket), symbol).get("ok", False)
                    self._virtual.pop(int(ticket), None)
                    self._journal("CLOSE", symbol, f"tutup posisi ticket {ticket}", ok)
            elif action == "CLOSE_ALL":
                n = self.close_all(symbol)
                self._journal("CLOSE_ALL", symbol, f"tutup semua ({n} posisi)", True)
            elif action == "MODIFY":
                ticket = cmd.get("ticket")
                if ticket:
                    ok = self.backend.modify_sl_tp(int(ticket), symbol, cmd.get("sl"), cmd.get("tp"))
                    v = self._virtual.get(int(ticket))
                    if v:  # jaga konsistensi SL/TP virtual bila dipakai
                        if cmd.get("sl") is not None:
                            v["sl"] = float(cmd["sl"])
                        if cmd.get("tp") is not None:
                            v["tp"] = float(cmd["tp"])
                    self._journal("MODIFY", symbol,
                                  f"ubah SL/TP ticket {ticket} sl={cmd.get('sl','-')} tp={cmd.get('tp','-')}", ok)
        except Exception as exc:  # noqa: BLE001 - fail-safe per perintah
            logger.error("Perintah strategi '%s' gagal utk %s: %s", action, symbol, exc)
            self._journal(action or "?", symbol, f"error: {exc}", False)
