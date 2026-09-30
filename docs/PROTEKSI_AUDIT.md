# Audit & Rencana Fitur Proteksi

Status fitur proteksi/keamanan yang diminta, dan rencana pengerjaan bertahap.
Legenda: ✅ sudah ada · ⚠️ sebagian · ❌ belum ada

## 1. Proteksi Eksekusi Posisi
| Fitur | Status | Catatan |
|---|---|---|
| Hard Stop Loss & Dynamic Take Profit | ✅ | Mode **points** & **percent** (`sl_tp_mode`, `sl_percent`/`tp_percent`), override per-strategi. |
| Trailing Stop / Trailing Profit | ✅ | `apply_trailing_stop` (broker) + versi virtual saat mode hidden. |
| Virtual / Hidden Stop Loss | ✅ | `virtual_sltp_enabled` — SL/TP tidak dikirim ke broker; dipantau bot tiap detik + trailing/BE virtual. |

## 2. Money Management
| Fitur | Status | Catatan |
|---|---|---|
| Dynamic Lot Sizing (% risiko) | ✅ | `calc_lot_from_spec` pakai `risk_per_trade` × balance. |
| Max Open Positions | ✅ | `max_open_positions`. |
| Max Exposure Limit (total lot) | ✅ | `max_exposure_lots` — tolak entry bila total lot melebihi batas. |
| Max Equity Protection / Cut Loss Account (tutup semua + stop) | ✅ | `equity_stop_loss` — tutup SEMUA posisi + stop auto-trading saat DD ekuitas ≥ ambang. |

## 3. Filter Kondisi Pasar
| Fitur | Status | Catatan |
|---|---|---|
| Spread & Volatility Filter | ✅ | `max_spread_points` — tolak entry bila spread melebihi batas. |
| Indikator Filter Tren/Konfirmasi | ⚠️ | Strategi sudah pakai indikator; filter tren terpisah belum. |
| News Filter (high-impact) | ❌ | Butuh kalender ekonomi (sumber eksternal); tidak tersedia andal via MCP. Ditunda. |

## 4. Fitur Pengaman Ekstra
| Fitur | Status | Catatan |
|---|---|---|
| Max Drawdown Daily Limit | ✅ | `daily_drawdown_limit` + `check_daily_drawdown`. |
| Safety Guard (pause setelah loss beruntun) | ✅ | `max_consecutive_losses` — jeda entry setelah N loss beruntun. |
| Backtest Support | ❌ | MCP punya `tester_*` tapi belum diintegrasikan (fitur besar terpisah). |
| Demo/Forward test | ✅ | Bot jalan di akun demo; badge Demo/Real ada. |

---

## Rencana Bertahap (tiap tahap diakhiri test/audit)

- **Tahap 1 — Konfigurasi + gerbang entry:** ✅ SELESAI. Spread filter & max exposure +
  field config + UI + test (83 lolos).
- **Tahap 2 — Proteksi ekuitas:** ✅ SELESAI. Equity cut-loss (tutup semua + stop) +
  safety guard (loss beruntun) + UI + test.
- **Tahap 3 — SL/TP persen + Virtual/Hidden SL/TP:** ✅ SELESAI. Mode points/percent,
  virtual SL/TP (dipantau tiap detik) + trailing/BE virtual + UI + test (92 lolos).
- **Tahap 4 — UI + rebuild EXE:** UI semua proteksi ✅ selesai; **rebuild EXE** menyusul
  (jalankan `Build.bat` atau minta rebuild).
- **Ditunda (butuh usaha/sumber eksternal):** News filter (kalender ekonomi),
  Backtesting penuh (integrasi `tester_*` MCP) — masing-masing jadi proyek sendiri.

Setiap gerbang mengikuti prinsip **fail-safe**: bila kondisi proteksi terpicu, order
tidak dikirim / posisi ditutup, dengan log yang jelas.
