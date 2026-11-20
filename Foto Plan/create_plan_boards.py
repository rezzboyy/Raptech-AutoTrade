import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = r"c:\Users\Administrator\Desktop\My Produk\Auto Trade\Bot Trading"
FOTO_PLAN_DIR = os.path.join(BASE_DIR, "Foto Plan")
os.makedirs(FOTO_PLAN_DIR, exist_ok=True)

USER_REF_IMAGE = r"C:/Users/Administrator/.gemini/antigravity-cli/brain/a750671a-b684-4fc0-8d57-31b98f8906b3/.user_uploaded/uploaded_media_1795154023158.jpg"

def get_font(size, bold=False, mono=False):
    if mono:
        paths = [
            r"C:\Windows\Fonts\consolab.ttf" if bold else r"C:\Windows\Fonts\consola.ttf",
            r"C:\Windows\Fonts\courbd.ttf" if bold else r"C:\Windows\Fonts\cour.ttf"
        ]
    else:
        paths = [
            r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"
        ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_header(draw, w, h=52):
    # Header bar
    draw.rectangle([(0, 0), (w, h)], fill="#141822")
    draw.line([(0, h), (w, h)], fill="#252D3D", width=1)
    
    # Logo / App title
    draw.rounded_rectangle([(14, 11), (44, 41)], radius=6, fill="#0288D1")
    draw.text((29, 26), "X", font=get_font(20, True), fill="#FFFFFF", anchor="mm")
    
    draw.text((54, 26), "XAVIQ", font=get_font(18, True), fill="#FFFFFF", anchor="lm")
    draw.text((120, 26), "Trading Engine", font=get_font(15, False), fill="#90A4AE", anchor="lm")
    
    # Version badge
    draw.rounded_rectangle([(245, 16), (300, 36)], radius=4, fill="#1E2638", outline="#323F58", width=1)
    draw.text((272, 26), "v1.0.0", font=get_font(11, True), fill="#64B5F6", anchor="mm")
    
    # Center connection status
    draw.ellipse([(w // 2 - 140, 22), (w // 2 - 130, 32)], fill="#00E676")
    status_text = "MT5 CONNECTED  •  Exness-Real  •  #20307485  •  Ping: 4ms"
    draw.text((w // 2 - 120, 26), status_text, font=get_font(13, True), fill="#E0E0E0", anchor="lm")
    
    # Right buttons
    btn_w = 90
    draw.rounded_rectangle([(w - 320, 12), (w - 225, 40)], radius=4, fill="#1E2638", outline="#2F3C54", width=1)
    draw.text((w - 272, 26), "Dark Mode", font=get_font(12, False), fill="#CFD8DC", anchor="mm")
    
    draw.rounded_rectangle([(w - 215, 12), (w - 110, 40)], radius=4, fill="#1E2638", outline="#2F3C54", width=1)
    draw.text((w - 162, 26), "Cek Update", font=get_font(12, False), fill="#CFD8DC", anchor="mm")
    
    draw.rounded_rectangle([(w - 100, 12), (w - 15, 40)], radius=4, fill="#261E28", outline="#6A2732", width=1)
    draw.text((w - 57, 26), "Logout", font=get_font(12, True), fill="#FF5252", anchor="mm")

def draw_left_sidebar(draw, x0, y0, w, h):
    draw.rectangle([(x0, y0), (x0 + w, y0 + h)], fill="#0E121A")
    draw.line([(x0 + w, y0), (x0 + w, y0 + h)], fill="#232B3B", width=1)
    
    pad = 12
    cx = x0 + pad
    cw = w - 2 * pad
    cy = y0 + pad
    
    # 1. Section Controls Header
    draw.text((cx, cy + 6), "Controls", font=get_font(17, True), fill="#E2E8F0", anchor="lm")
    cy += 30
    
    # Symbol & Uptime Row
    draw.text((cx, cy + 12), "Symbol:", font=get_font(12, False), fill="#94A3B8", anchor="lm")
    # Symbol dropdown
    draw.rounded_rectangle([(cx + 56, cy), (cx + 200, cy + 28)], radius=4, fill="#1A2232", outline="#2E3C54", width=1)
    draw.text((cx + 66, cy + 14), "XAUUSDm", font=get_font(12, True), fill="#FFFFFF", anchor="lm")
    draw.text((cx + 185, cy + 14), "▼", font=get_font(9, False), fill="#94A3B8", anchor="lm")
    
    # Refresh button
    draw.rounded_rectangle([(cx + 206, cy), (cx + 265, cy + 28)], radius=4, fill="#1E293B", outline="#334155", width=1)
    draw.text((cx + 235, cy + 14), "Refresh", font=get_font(11, False), fill="#CBD5E1", anchor="mm")
    
    # Uptime on right
    draw.text((cx + cw - 2, cy + 14), "16:23:09", font=get_font(14, True, True), fill="#00E676", anchor="rm")
    cy += 36
    
    # START and STOP Big Buttons
    btn_w = (cw - 8) // 2
    # START button (Cyan/Blue)
    draw.rounded_rectangle([(cx, cy), (cx + btn_w, cy + 38)], radius=5, fill="#0288D1")
    draw.text((cx + btn_w // 2, cy + 19), "START", font=get_font(15, True), fill="#FFFFFF", anchor="mm")
    
    # STOP button (Red)
    draw.rounded_rectangle([(cx + btn_w + 8, cy), (cx + cw, cy + 38)], radius=5, fill="#D32F2F")
    draw.text((cx + btn_w + 8 + btn_w // 2, cy + 19), "STOP", font=get_font(15, True), fill="#FFFFFF", anchor="mm")
    cy += 46
    
    # Lot input + BUY + SELL Row
    draw.text((cx, cy + 14), "Lot:", font=get_font(12, False), fill="#94A3B8", anchor="lm")
    draw.rounded_rectangle([(cx + 32, cy), (cx + 105, cy + 32)], radius=4, fill="#1A2232", outline="#2E3C54", width=1)
    draw.text((cx + 68, cy + 16), "0.01", font=get_font(13, True, True), fill="#FFFFFF", anchor="mm")
    
    # BUY button (Green)
    order_btn_w = (cw - 115) // 2
    draw.rounded_rectangle([(cx + 113, cy), (cx + 113 + order_btn_w, cy + 32)], radius=4, fill="#2E7D32")
    draw.text((cx + 113 + order_btn_w // 2, cy + 16), "BUY", font=get_font(14, True), fill="#FFFFFF", anchor="mm")
    
    # SELL button (Red)
    draw.rounded_rectangle([(cx + 113 + order_btn_w + 6, cy), (cx + cw, cy + 32)], radius=4, fill="#C62828")
    draw.text((cx + 113 + order_btn_w + 6 + order_btn_w // 2, cy + 16), "SELL", font=get_font(14, True), fill="#FFFFFF", anchor="mm")
    cy += 40
    
    # HEDGE BUY+SELL (Purple full width)
    draw.rounded_rectangle([(cx, cy), (cx + cw, cy + 34)], radius=5, fill="#7B1FA2")
    draw.text((cx + cw // 2, cy + 17), "HEDGE BUY+SELL", font=get_font(13, True), fill="#FFFFFF", anchor="mm")
    cy += 42
    
    # Max OP + CLOSE ALL RESET
    draw.text((cx, cy + 14), "Max OP:", font=get_font(12, False), fill="#94A3B8", anchor="lm")
    draw.rounded_rectangle([(cx + 56, cy), (cx + 120, cy + 32)], radius=4, fill="#1A2232", outline="#2E3C54", width=1)
    draw.text((cx + 82, cy + 16), "6", font=get_font(13, True), fill="#FFFFFF", anchor="mm")
    draw.text((cx + 108, cy + 16), "▲▼", font=get_font(8, False), fill="#64748B", anchor="mm")
    
    # CLOSE ALL RESET (Amber/Orange)
    draw.rounded_rectangle([(cx + 128, cy), (cx + cw, cy + 32)], radius=4, fill="#E65100")
    draw.text((cx + 128 + (cw - 128) // 2, cy + 16), "CLOSE ALL RESET", font=get_font(12, True), fill="#FFFFFF", anchor="mm")
    cy += 48
    
    draw.line([(cx, cy), (cx + cw, cy)], fill="#1E2736", width=1)
    cy += 12
    
    # 2. Section: Market Risk
    draw.text((cx, cy + 6), "Market Risk", font=get_font(13, True), fill="#38BDF8", anchor="lm")
    cy += 20
    
    draw.rounded_rectangle([(cx, cy), (cx + cw, cy + 60)], radius=6, fill="#131824", outline="#1F283B", width=1)
    # Bid / Ask
    draw.text((cx + 12, cy + 18), "Bid:", font=get_font(12, False), fill="#94A3B8", anchor="lm")
    draw.text((cx + 42, cy + 18), "2650.87", font=get_font(13, True, True), fill="#38BDF8", anchor="lm")
    
    draw.text((cx + 130, cy + 18), "Ask:", font=get_font(12, False), fill="#94A3B8", anchor="lm")
    draw.text((cx + 162, cy + 18), "2651.18", font=get_font(13, True, True), fill="#F87171", anchor="lm")
    
    # Spread / Target
    draw.text((cx + 12, cy + 42), "Spread:", font=get_font(11, False), fill="#94A3B8", anchor="lm")
    draw.text((cx + 58, cy + 42), "31 pts", font=get_font(11, True), fill="#F1F5F9", anchor="lm")
    
    draw.text((cx + 130, cy + 42), "Target:", font=get_font(11, False), fill="#94A3B8", anchor="lm")
    draw.text((cx + 172, cy + 42), "SL 20.0% / TP 3.0%", font=get_font(11, True), fill="#34D399", anchor="lm")
    cy += 72
    
    # 3. Section: Account
    draw.text((cx, cy + 6), "Account", font=get_font(13, True), fill="#38BDF8", anchor="lm")
    cy += 20
    
    draw.rounded_rectangle([(cx, cy), (cx + cw, cy + 125)], radius=6, fill="#131824", outline="#1F283B", width=1)
    acc_rows = [
        ("Balance:", "$204.84", "#FFFFFF"),
        ("Equity:", "$205.64", "#FFFFFF"),
        ("Open PnL:", "$+0.80 (+0.39%)", "#00E676"),
        ("Daily PnL:", "$+97.85 (+47.7%)", "#00E676"),
        ("Win Rate:", "86.4% (19W / 3L)", "#38BDF8"),
    ]
    for idx, (k, v, col) in enumerate(acc_rows):
        ry = cy + 14 + idx * 22
        draw.text((cx + 12, ry), k, font=get_font(12, False), fill="#94A3B8", anchor="lm")
        draw.text((cx + cw - 12, ry), v, font=get_font(12, True, True), fill=col, anchor="rm")
    cy += 137
    
    # 4. Section: Momentum Scanner (M5/M15/M30)
    draw.text((cx, cy + 6), "Momentum Scanner (M5/M15/M30)", font=get_font(13, True), fill="#38BDF8", anchor="lm")
    cy += 20
    
    draw.rounded_rectangle([(cx, cy), (cx + cw, cy + 135)], radius=6, fill="#131824", outline="#1F283B", width=1)
    scanner_rows = [
        ("Signal:", "EMA Pullback SELL", "#FBBF24"),
        ("Source:", "TF: M5", "#FFFFFF"),
        ("Trend:", "M15: Bearish ▼", "#F87171"),
        ("Trend30:", "M30: Bearish ▼", "#F87171"),
        ("M5 ATR:", "ATR: 13.74 (Active)", "#38BDF8"),
    ]
    for idx, (k, v, col) in enumerate(scanner_rows):
        ry = cy + 14 + idx * 23
        draw.text((cx + 12, ry), k, font=get_font(12, False), fill="#94A3B8", anchor="lm")
        draw.text((cx + 90, ry), v, font=get_font(12, True), fill=col, anchor="lm")
    cy += 147
    
    # 5. Bottom Status
    draw.text((cx, cy + 8), "Momentum Status: Engine Active & Monitoring Ticks", font=get_font(11, False), fill="#64748B", anchor="lm")

def draw_right_panel(draw, x0, y0, w, h):
    draw.rectangle([(x0, y0), (x0 + w, y0 + h)], fill="#0B0E14")
    
    # Top Tab Bar
    tab_h = 42
    draw.rectangle([(x0, y0), (x0 + w, y0 + tab_h)], fill="#121620")
    draw.line([(x0, y0 + tab_h), (x0 + w, y0 + tab_h)], fill="#232B3B", width=1)
    
    tabs = [
        ("Open Trades (3)", False),
        ("Trade History", True), # Active
        ("Candlestick Chart", False),
        ("Equity Curve", False),
        ("Strategy Config", False),
        ("Programmer Studio", False),
        ("Expert Log", False),
    ]
    
    cur_tx = x0 + 12
    for t_title, is_active in tabs:
        tw = int(get_font(12, is_active).getlength(t_title)) + 28
        if is_active:
            # Active tab style (blue highlight)
            draw.rectangle([(cur_tx, y0 + 6), (cur_tx + tw, y0 + tab_h)], fill="#1E293B")
            draw.line([(cur_tx, y0 + tab_h - 2), (cur_tx + tw, y0 + tab_h - 2)], fill="#38BDF8", width=3)
            draw.text((cur_tx + tw // 2, y0 + 22), t_title, font=get_font(12, True), fill="#FFFFFF", anchor="mm")
        else:
            draw.text((cur_tx + tw // 2, y0 + 22), t_title, font=get_font(12, False), fill="#94A3B8", anchor="mm")
        cur_tx += tw + 4
        
    # Table Header
    tbl_top = y0 + tab_h + 8
    tbl_h = 32
    draw.rectangle([(x0 + 12, tbl_top), (x0 + w - 12, tbl_top + tbl_h)], fill="#151A24")
    draw.line([(x0 + 12, tbl_top + tbl_h), (x0 + w - 12, tbl_top + tbl_h)], fill="#252E3E", width=1)
    
    cols = [
        ("Time", 120),
        ("Ticket", 140),
        ("Symbol", 90),
        ("Source", 80),
        ("Reason / Strategy", 250),
        ("Lot", 70),
        ("Open Price", 120),
        ("Close Price", 120),
        ("Profit / PnL", 120),
    ]
    
    cur_x = x0 + 24
    for c_title, cw in cols:
        draw.text((cur_x, tbl_top + 16), c_title, font=get_font(11, True), fill="#94A3B8", anchor="lm")
        cur_x += cw
        
    # Table Rows matching the user's reference image
    rows = [
        ("20/11 12:01", "20307485738", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2655.80", "2649.82", "+$5.98", False),
        ("20/11 10:22", "20307296688", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2658.20", "2651.88", "+$6.32", False),
        ("20/11 10:16", "20307287822", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2654.10", "2648.21", "+$5.89", False),
        ("20/11 10:05", "20307239658", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2652.40", "2653.87", "-$1.47", False),
        ("20/11 10:00", "20307250196", "XAUUSDm", "Step", "-50% SL #20307239658", "0.02", "2661.10", "2655.96", "+$5.14", False),
        ("20/11 09:45", "20307221622", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2655.40", "2650.13", "+$5.27", False),
        ("20/11 09:42", "20307215298", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2652.65", "2658.05", "-$5.40", False),
        ("20/11 09:35", "20307204282", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2654.90", "2649.91", "+$4.99", False),
        ("20/11 09:28", "20307199931", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2658.56", "2654.36", "+$4.20", True), # Highlighted Blue
        ("20/11 06:19", "20307063055", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2659.92", "2655.26", "+$4.66", False),
        ("20/11 05:57", "20307052134", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2664.79", "2660.41", "+$4.38", False),
        ("20/11 05:44", "20307043377", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2668.00", "2663.57", "+$4.43", False),
        ("20/11 05:31", "20307040801", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2669.73", "2664.94", "+$4.79", False),
        ("20/11 05:01", "20307021982", "XAUUSDm", "M15", "Momentum Break SELL", "0.01", "2666.41", "2662.62", "+$3.79", False),
        ("20/11 04:49", "20307008214", "XAUUSDm", "M5", "Momentum Break SELL", "0.01", "2674.46", "2670.67", "+$3.79", False),
        ("20/11 04:48", "20306996327", "XAUUSDm", "M15", "EMA Pullback SELL", "0.01", "2675.10", "2671.19", "+$3.91", False),
        ("20/11 04:47", "20306989190", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2675.86", "2672.22", "+$3.64", False),
        ("20/11 04:47", "20306949761", "XAUUSDm", "M15", "EMA Pullback SELL", "0.01", "2676.11", "2672.60", "+$3.51", False),
        ("20/11 04:05", "20306975102", "XAUUSDm", "M5", "EMA Pullback SELL", "0.01", "2678.94", "2675.15", "+$3.79", False),
    ]
    
    row_h = 32
    cur_ry = tbl_top + tbl_h
    for time_s, tkt, sym, src, rsn, lot, op_p, cl_p, pnl, is_hl in rows:
        if is_hl:
            # Highlighted Row (Blue as in reference)
            draw.rectangle([(x0 + 12, cur_ry), (x0 + w - 12, cur_ry + row_h)], fill="#0284C7")
            text_color = "#FFFFFF"
            pnl_color = "#E0F2FE"
        else:
            bg_r = "#0E121A" if ((cur_ry - tbl_top) // row_h) % 2 == 0 else "#0B0E14"
            draw.rectangle([(x0 + 12, cur_ry), (x0 + w - 12, cur_ry + row_h)], fill=bg_r)
            text_color = "#CBD5E1"
            pnl_color = "#34D399" if pnl.startswith("+") else "#F87171"
            
        cur_cx = x0 + 24
        vals = [time_s, tkt, sym, src, rsn, lot, op_p, cl_p, pnl]
        for v_idx, val in enumerate(vals):
            cw = cols[v_idx][1]
            c_val = pnl_color if v_idx == 8 else text_color
            bold_val = is_hl or v_idx == 8
            mono_val = v_idx in [0, 1, 5, 6, 7, 8]
            draw.text((cur_cx, cur_ry + 16), val, font=get_font(11, bold_val, mono_val), fill=c_val, anchor="lm")
            cur_cx += cw
            
        cur_ry += row_h
        
    # Table Summary Footer Bar
    draw.rounded_rectangle([(x0 + 12, cur_ry + 8), (x0 + w - 12, cur_ry + 44)], radius=4, fill="#131824", outline="#252E3E", width=1)
    draw.text((x0 + 24, cur_ry + 26), "Total Closed Trades: 19  •  Wins: 17 (89.5%)  •  Losses: 2 (10.5%)  •  Total Volume: 0.20 Lots", font=get_font(12, False), fill="#94A3B8", anchor="lm")
    draw.text((x0 + w - 24, cur_ry + 26), "Net Realized Profit:  +$68.96 USD", font=get_font(13, True, True), fill="#00E676", anchor="rm")

def build_board_1():
    # Board 1: Design Plan Mockup Layout Baru (Full HD 1920 x 1080)
    w, h = 1920, 1080
    board = Image.new("RGB", (w, h), "#080B10")
    draw = ImageDraw.Draw(board)
    
    # 1. Header
    draw_header(draw, w, 52)
    
    # 2. Left Sidebar (380px)
    draw_left_sidebar(draw, 0, 52, 380, h - 52)
    
    # 3. Right Main Panel (w - 380 = 1540px)
    draw_right_panel(draw, 380, 52, w - 380, h - 52)
    
    out_path = os.path.join(FOTO_PLAN_DIR, "01_Design_Plan_Mockup_Layout_Baru.png")
    board.save(out_path, quality=95)
    print("Saved Board 1 to:", out_path)

def build_board_2():
    # Board 2: Diagram Pengukuran Presisi Geometri Layout (Wireframe / Blueprint with Measurement Annotations)
    w, h = 2560, 1440
    board = Image.new("RGB", (w, h), "#090D16")
    draw = ImageDraw.Draw(board)
    
    # Header
    draw.rectangle([(0, 0), (w, 130)], fill="#0F172A")
    draw.line([(0, 130), (w, 130)], fill="#38BDF8", width=3)
    draw.text((60, 36), "DIAGRAM PENGUKURAN PRESISI & CETAK BIRU GEOMETRI LAYOUT DESKTOP XAVIQ", font=get_font(32, True), fill="#FFFFFF")
    draw.text((60, 84), "Spesifikasi Ergonomi Desktop: Tata Letak Kontrol Samping (Controls), Tab Bar Lintas Fitur, Tabel Riwayat Transaksi & Palet Desain Token", font=get_font(18), fill="#93C5FD")
    
    # Draw scaled layout preview with dimension lines
    preview_x = 80
    preview_y = 180
    preview_w = 1600
    preview_h = 900
    
    # Outer frame of the application window
    draw.rounded_rectangle([(preview_x, preview_y), (preview_x + preview_w, preview_y + preview_h)], radius=10, fill="#0B0E14", outline="#38BDF8", width=2)
    
    # Dimension Callouts:
    # 1. Header (Height 52px)
    hdr_h = int(preview_h * (52 / 1080.0))
    draw.rectangle([(preview_x, preview_y), (preview_x + preview_w, preview_y + hdr_h)], fill="#1E293B")
    draw.text((preview_x + 20, preview_y + hdr_h // 2), "HEADER BAR: Logo • Status MT5 Real-time • Dark/Light • OTA Update • Logout", font=get_font(13, True), fill="#94A3B8", anchor="lm")
    
    # Header dimension line on the right
    draw.line([(preview_x + preview_w + 20, preview_y), (preview_x + preview_w + 20, preview_y + hdr_h)], fill="#F59E0B", width=2)
    draw.line([(preview_x + preview_w + 15, preview_y), (preview_x + preview_w + 25, preview_y)], fill="#F59E0B", width=2)
    draw.line([(preview_x + preview_w + 15, preview_y + hdr_h), (preview_x + preview_w + 25, preview_y + hdr_h)], fill="#F59E0B", width=2)
    draw.text((preview_x + preview_w + 35, preview_y + hdr_h // 2), "H: 52 px (48-56dp)", font=get_font(13, True), fill="#F59E0B", anchor="lm")
    
    # 2. Left Sidebar (Width 380px)
    side_w = int(preview_w * (380 / 1920.0)) # ~316px
    content_y = preview_y + hdr_h
    content_h = preview_h - hdr_h
    draw.rectangle([(preview_x, content_y), (preview_x + side_w, content_y + content_h)], fill="#0F172A", outline="#1E293B", width=1)
    
    # Dimension line above Left Sidebar
    draw.line([(preview_x, preview_y - 20), (preview_x + side_w, preview_y - 20)], fill="#38BDF8", width=2)
    draw.line([(preview_x, preview_y - 25), (preview_x, preview_y - 15)], fill="#38BDF8", width=2)
    draw.line([(preview_x + side_w, preview_y - 25), (preview_x + side_w, preview_y - 15)], fill="#38BDF8", width=2)
    draw.text((preview_x + side_w // 2, preview_y - 35), "WIDTH: 380 px (Rasio 20%)", font=get_font(13, True), fill="#38BDF8", anchor="mm")
    
    # Internal left sidebar section wireframes
    side_sections = [
        ("Controls: Symbol + Uptime", 40, "#1E293B"),
        ("Big Action: START | STOP", 46, "#0288D1"),
        ("Manual Trade: Lot | BUY | SELL", 40, "#2E7D32"),
        ("HEDGE BUY+SELL", 38, "#7B1FA2"),
        ("Max OP | CLOSE ALL RESET", 38, "#E65100"),
        ("Market Risk: Bid / Ask / Spread / SL / TP", 80, "#1E293B"),
        ("Account: Balance / Equity / PnL / WinRate", 130, "#1E293B"),
        ("Momentum Scanner: Signal / Trend / ATR", 140, "#1E293B"),
        ("Momentum Status Bar", 30, "#0F172A"),
    ]
    
    cur_sy = content_y + 10
    for s_name, s_h_orig, s_col in side_sections:
        s_h = int(content_h * (s_h_orig / 1028.0))
        draw.rounded_rectangle([(preview_x + 10, cur_sy), (preview_x + side_w - 10, cur_sy + s_h)], radius=4, fill="#131B2E", outline=s_col, width=1)
        draw.text((preview_x + 20, cur_sy + s_h // 2), s_name, font=get_font(10, True), fill="#E2E8F0", anchor="lm")
        cur_sy += s_h + 6
        
    # 3. Right Main Area (Width 1540px)
    main_x = preview_x + side_w
    main_w = preview_w - side_w
    
    # Dimension line above Right Panel
    draw.line([(main_x, preview_y - 20), (main_x + main_w, preview_y - 20)], fill="#34D399", width=2)
    draw.line([(main_x, preview_y - 25), (main_x, preview_y - 15)], fill="#34D399", width=2)
    draw.line([(main_x + main_w, preview_y - 25), (main_x + main_w, preview_y - 15)], fill="#34D399", width=2)
    draw.text((main_x + main_w // 2, preview_y - 35), "MAIN WORKSPACE WIDTH: 1540 px (Rasio 80%)", font=get_font(13, True), fill="#34D399", anchor="mm")
    
    # Tab Bar
    tab_bar_h = int(content_h * (42 / 1028.0))
    draw.rectangle([(main_x, content_y), (main_x + main_w, content_y + tab_bar_h)], fill="#1E293B")
    draw.text((main_x + 16, content_y + tab_bar_h // 2), "MULTI-TAB BAR: [Open Trades] • [Trade History (Active)] • [Candlestick Chart] • [Equity Curve] • [Strategy Config] • [Programmer] • [Expert Log]", font=get_font(12, True), fill="#F8FAFC", anchor="lm")
    
    # Table Header
    tbl_hdr_h = int(content_h * (32 / 1028.0))
    draw.rectangle([(main_x + 10, content_y + tab_bar_h + 8), (main_x + main_w - 10, content_y + tab_bar_h + 8 + tbl_hdr_h)], fill="#1E293B", outline="#334155", width=1)
    draw.text((main_x + 24, content_y + tab_bar_h + 8 + tbl_hdr_h // 2), "TABLE HEADER: Time | Ticket | Symbol | Source | Reason / Strategy | Lot | Open Price | Close Price | Profit/PnL", font=get_font(11, True), fill="#94A3B8", anchor="lm")
    
    # Table Rows Mockup
    row_block_y = content_y + tab_bar_h + 8 + tbl_hdr_h
    row_block_h = int(content_h * (650 / 1028.0))
    draw.rounded_rectangle([(main_x + 10, row_block_y), (main_x + main_w - 10, row_block_y + row_block_h)], radius=4, fill="#0B0E14", outline="#1E293B", width=1)
    
    # Draw sample row lines
    for i in range(16):
        ry = row_block_y + i * (row_block_h // 16)
        if i == 7:
            draw.rectangle([(main_x + 10, ry), (main_x + main_w - 10, ry + (row_block_h // 16))], fill="#0284C7")
            draw.text((main_x + 24, ry + 12), "► BARIS TERPILIH (ACTIVE ROW HIGHLIGHT: #0284C7) — 20/11 09:28 • XAUUSDm • Momentum Break SELL • +$4.20", font=get_font(11, True), fill="#FFFFFF", anchor="lm")
        else:
            draw.line([(main_x + 10, ry), (main_x + main_w - 10, ry)], fill="#151C2A", width=1)
            draw.text((main_x + 24, ry + 12), f"Row #{i+1:02d}: Time • Ticket #2030748... • XAUUSDm • Strategy Execution • 0.01 Lot • PnL Green/Red", font=get_font(10, False), fill="#64748B", anchor="lm")
            
    # Table Footer
    ftr_y = row_block_y + row_block_h + 10
    ftr_h = int(content_h * (40 / 1028.0))
    draw.rounded_rectangle([(main_x + 10, ftr_y), (main_x + main_w - 10, ftr_y + ftr_h)], radius=4, fill="#131B2E", outline="#1E293B", width=1)
    draw.text((main_x + 24, ftr_y + ftr_h // 2), "SUMMARY FOOTER: Total Closed Trades: 19 • Win Rate: 89.5% • Total Volume: 0.20 Lots • Net Profit: +$68.96", font=get_font(11, True), fill="#34D399", anchor="lm")
    
    # 4. Right side Specification Cards (Width 680px)
    card_x = preview_x + preview_w + 100
    card_y = 180
    card_w = w - card_x - 60
    
    # Specifications Box 1: Design Tokens
    draw.rounded_rectangle([(card_x, card_y), (card_x + card_w, card_y + 430)], radius=12, fill="#0F172A", outline="#38BDF8", width=2)
    draw.text((card_x + 24, card_y + 26), "🎨 DESIGN TOKENS & PALET WARNA RESMI", font=get_font(18, True), fill="#38BDF8")
    
    tokens = [
        ("Background Utama", "#0B0E14", "Deep Black Canvas"),
        ("Card / Sidebar Surface", "#0E121A", "Kontrol & Card Surface"),
        ("Border / Divider", "#232B3B", "Pemisah Halus Subpixel"),
        ("Tombol START (Auto)", "#0288D1", "Cyan Action Primer"),
        ("Tombol STOP (Auto)", "#D32F2F", "Crimson Stop Primer"),
        ("Tombol BUY (Manual)", "#2E7D32", "Emerald Buy Order"),
        ("Tombol SELL (Manual)", "#C62828", "Scarlet Sell Order"),
        ("Tombol HEDGE", "#7B1FA2", "Violet Hedge Double Lock"),
        ("Tombol CLOSE ALL RESET", "#E65100", "Vibrant Amber Liquidation"),
        ("Profit Text (+)", "#00E676", "Neon Emerald Green"),
        ("Loss Text (-)", "#FF5252", "Vivid Coral Red"),
    ]
    for idx, (tname, tcol, tdesc) in enumerate(tokens):
        ty = card_y + 60 + idx * 33
        # Swatch
        draw.rounded_rectangle([(card_x + 24, ty), (card_x + 50, ty + 20)], radius=4, fill=tcol, outline="#FFFFFF", width=1)
        draw.text((card_x + 62, ty + 10), tcol, font=get_font(12, True, True), fill="#E2E8F0", anchor="lm")
        draw.text((card_x + 150, ty + 10), tname, font=get_font(12, True), fill="#FFFFFF", anchor="lm")
        draw.text((card_x + 380, ty + 10), tdesc, font=get_font(11, False), fill="#94A3B8", anchor="lm")
        
    # Specifications Box 2: Feature Mapping Matrix
    draw.rounded_rectangle([(card_x, card_y + 460), (card_x + card_w, card_y + 900)], radius=12, fill="#0F172A", outline="#34D399", width=2)
    draw.text((card_x + 24, card_y + 486), "⚡ PEMETAAN SELURUH FITUR XAVIQ KE LAYOUT BARU", font=get_font(18, True), fill="#34D399")
    
    feat_map = [
        ("Koneksi & Auth MT5", "Header Bar + Status Pill + Modal Login/Logout cepat."),
        ("Auto Trading Engine", "START & STOP besar di panel kiri (Status Uptime aktif)."),
        ("Manual Trading", "Lot input + BUY + SELL berdampingan untuk eksekusi instan."),
        ("Quick Hedge Order", "Tombol HEDGE BUY+SELL 1-klik untuk kuncian posisi ganda."),
        ("Emergency Liquidation", "CLOSE ALL RESET untuk cut loss/TP semua posisi & reset state."),
        ("Market Risk Telemetry", "Bid, Ask, Spread, Target SL/TP virtual live per simbol."),
        ("Account Health Stats", "Balance, Equity, Open PnL, Daily PnL, Win Rate real-time."),
        ("Momentum Scanner", "Signal, Source TF, Trend M15/M30, ATR volatility scanner."),
        ("Open Positions & History", "Tab 'Open Trades' & 'Trade History' dengan tabel modern."),
        ("Candle & Equity Chart", "Tab 'Candlestick Chart' & 'Equity Curve' full-size responsif."),
        ("Programmer & Scripting", "Tab 'Programmer Studio' & 'Expert Log' untuk skrip custom."),
    ]
    for idx, (f_name, f_desc) in enumerate(feat_map):
        fy = card_y + 520 + idx * 34
        draw.text((card_x + 24, fy + 10), f"• {f_name}:", font=get_font(12, True), fill="#F8FAFC", anchor="lm")
        draw.text((card_x + 210, fy + 10), f_desc, font=get_font(11, False), fill="#94A3B8", anchor="lm")
        
    # Footer Banner
    draw.rectangle([(0, h - 60), (w, h)], fill="#0F172A")
    draw.text((w // 2, h - 30), "XAVIQ Trading Engine Architecture Plan • 100% Fitur Terintegrasi • Layout Ergonomis Standar Pro Trading Desk", font=get_font(14, True), fill="#94A3B8", anchor="mm")
    
    out_path = os.path.join(FOTO_PLAN_DIR, "02_Diagram_Pengukuran_Presisi_Geometri_Layout.png")
    board.save(out_path, quality=95)
    print("Saved Board 2 to:", out_path)

def build_board_3():
    # Board 3: Komparasi Side-By-Side Desain Referensi vs Desain Baru
    w, h = 2600, 1400
    board = Image.new("RGB", (w, h), "#080B10")
    draw = ImageDraw.Draw(board)
    
    # Header
    draw.rectangle([(0, 0), (w, 140)], fill="#0F172A")
    draw.line([(0, 140), (w, 140)], fill="#38BDF8", width=3)
    draw.text((60, 36), "BOARD 3: KOMPARASI SIDE-BY-SIDE DESAIN REFERENSI VS RANCANGAN DESAIN BARU", font=get_font(34, True), fill="#FFFFFF")
    draw.text((60, 88), "Validasi Paritas Visual: Memastikan Desain Baru Mengadopsi Penuh Ergonomi Referensi Sekaligus Mengintegrasikan Seluruh Fitur C++ XAVIQ", font=get_font(19), fill="#93C5FD")
    
    panel_w = 1200
    panel_h = 1180
    start_y = 180
    
    # Panel 1: Desain Referensi Pengguna
    p1_x = 70
    draw.rounded_rectangle([(p1_x, start_y), (p1_x + panel_w, start_y + panel_h)], radius=16, fill="#0F172A", outline="#F59E0B", width=2)
    draw.rectangle([(p1_x, start_y), (p1_x + panel_w, start_y + 70)], fill="#1E293B")
    draw.text((p1_x + 24, start_y + 22), "1. DESAIN REFERENSI PILIHAN PENGGUNA", font=get_font(18, True), fill="#FBBF24")
    draw.text((p1_x + 24, start_y + 46), "Screenshot Asli Target: Kontrol Samping Padat + Tabel Trade History Lebar", font=get_font(12), fill="#94A3B8")
    
    # Load and place user ref image
    if os.path.exists(USER_REF_IMAGE):
        ref_im = Image.open(USER_REF_IMAGE).convert("RGB")
        target_ref_w = panel_w - 40
        target_ref_h = int(target_ref_w * (ref_im.height / float(ref_im.width)))
        if target_ref_h > panel_h - 180:
            target_ref_h = panel_h - 180
            target_ref_w = int(target_ref_h * (ref_im.width / float(ref_im.height)))
        scaled_ref = ref_im.resize((target_ref_w, target_ref_h), Image.Resampling.LANCZOS)
        board.paste(scaled_ref, (p1_x + (panel_w - target_ref_w) // 2, start_y + 90))
        
    # Analysis note under Panel 1
    note1_y = start_y + panel_h - 80
    draw.rounded_rectangle([(p1_x + 20, note1_y), (p1_x + panel_w - 20, start_y + panel_h - 16)], radius=8, fill="#1A1810", outline="#F59E0B", width=1)
    draw.text((p1_x + 36, note1_y + 16), "✔ Karakteristik: Panel Kiri (Controls, Risk, Account, Scanner) + Panel Kanan (Tabs Open/History/Log & Full Data Grid).", font=get_font(12, True), fill="#FDE68A")
    draw.text((p1_x + 36, note1_y + 36), "✔ Skema Warna: Dark Gunmetal (#0B0E14) dengan aksen tombol fungsional (Cyan, Red, Green, Purple, Amber).", font=get_font(11, False), fill="#D1D5DB")
    
    # Panel 2: Desain Baru XAVIQ Trading Engine
    p2_x = p1_x + panel_w + 60
    draw.rounded_rectangle([(p2_x, start_y), (p2_x + panel_w, start_y + panel_h)], radius=16, fill="#0F172A", outline="#34D399", width=2)
    draw.rectangle([(p2_x, start_y), (p2_x + panel_w, start_y + 70)], fill="#1E293B")
    draw.text((p2_x + 24, start_y + 22), "2. RANCANGAN DESAIN BARU XAVIQ TRADING ENGINE", font=get_font(18, True), fill="#34D399")
    draw.text((p2_x + 24, start_y + 46), "Adaptasi Presisi 100%: Menampung Seluruh Fitur C++ & MT5 dengan Finishing Modern & Rapi", font=get_font(12), fill="#94A3B8")
    
    # Load Board 1 mockup
    b1_path = os.path.join(FOTO_PLAN_DIR, "01_Design_Plan_Mockup_Layout_Baru.png")
    if os.path.exists(b1_path):
        b1_im = Image.open(b1_path).convert("RGB")
        target_b1_w = panel_w - 40
        target_b1_h = int(target_b1_w * (b1_im.height / float(b1_im.width)))
        if target_b1_h > panel_h - 180:
            target_b1_h = panel_h - 180
            target_b1_w = int(target_b1_h * (b1_im.width / float(b1_im.height)))
        scaled_b1 = b1_im.resize((target_b1_w, target_b1_h), Image.Resampling.LANCZOS)
        board.paste(scaled_b1, (p2_x + (panel_w - target_b1_w) // 2, start_y + 90))
        
    # Analysis note under Panel 2
    note2_y = start_y + panel_h - 80
    draw.rounded_rectangle([(p2_x + 20, note2_y), (p2_x + panel_w - 20, start_y + panel_h - 16)], radius=8, fill="#0B1C1A", outline="#34D399", width=1)
    draw.text((p2_x + 36, note2_y + 16), "✔ Peningkatan: 100% Fitur XAVIQ (Candle Chart, Equity Curve, Programmer, Strategy Config) terintegrasi via Multi-Tab Bar.", font=get_font(12, True), fill="#A7F3D0")
    draw.text((p2_x + 36, note2_y + 36), "✔ Ergonomi Pro Desk: Quick Hedge, Close All Reset, Telemetri Risiko, Uptime Timer, dan PnL Real-time selalu siap diakses.", font=get_font(11, False), fill="#D1D5DB")
    
    out_path = os.path.join(FOTO_PLAN_DIR, "03_Komparasi_Side_By_Side_Desain_Lama_vs_Baru.png")
    board.save(out_path, quality=95)
    print("Saved Board 3 to:", out_path)

if __name__ == "__main__":
    build_board_1()
    build_board_2()
    build_board_3()
    print("All Foto Plan boards created successfully!")
