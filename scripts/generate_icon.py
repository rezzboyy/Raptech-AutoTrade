from __future__ import annotations

"""
Raptech Autotrade CLI — Icon & Logo Generator.
Creates a high-resolution, multi-size Windows icon (.ico) and PNG logo featuring
a modern fintech / algorithmic trading stylized "R" glyph with cyber cyan and emerald accents.
Supported icon sizes: 256x256, 128x128, 64x64, 48x48, 32x32, 24x24, 16x16.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

ICO_PATH = ASSETS_DIR / "icon.ico"
PNG_PATH = ASSETS_DIR / "icon.png"
LOGO_PATH = ASSETS_DIR / "logo_r.png"


def create_raptech_r_icon() -> None:
    # Render at 1024x1024 supersampling for razor-sharp antialiasing
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Base Dark Squircle Background
    margin = 48
    radius = 210
    bg_box = [margin, margin, size - margin, size - margin]

    # Outer subtle glow
    glow_box = [margin - 12, margin - 12, size - margin + 12, size - margin + 12]
    draw.rounded_rectangle(glow_box, radius=radius + 8, fill=(0, 229, 255, 30))

    # Outer border cyan accent
    draw.rounded_rectangle(bg_box, radius=radius, fill=(10, 15, 26, 255), outline=(0, 229, 255, 200), width=18)

    # Subtle inner border for depth
    inner_box = [margin + 20, margin + 20, size - margin - 20, size - margin - 20]
    draw.rounded_rectangle(inner_box, radius=radius - 12, fill=(13, 20, 36, 255), outline=(30, 45, 75, 180), width=6)

    # 2. Subtle Bullish Trend Bars in Background (Watermark style)
    bar_color = (0, 230, 118, 22)
    draw.rectangle([700, 560, 750, 780], fill=bar_color)
    draw.line([725, 520, 725, 820], fill=bar_color, width=6)

    draw.rectangle([780, 440, 830, 780], fill=bar_color)
    draw.line([805, 400, 805, 820], fill=bar_color, width=6)

    draw.rectangle([860, 320, 910, 780], fill=bar_color)
    draw.line([885, 280, 885, 820], fill=bar_color, width=6)

    # 3. Geometric Modern "R" Glyph
    # Gradient simulation from Bright Cyan (top) to Neon Emerald (bottom)
    # Primary coordinates for "R":
    stem_left = 260
    stem_width = 120
    stem_right = stem_left + stem_width
    top_y = 260
    bottom_y = 764
    mid_y = 512

    # A. Left Vertical Stem (with gradient bands)
    stem_steps = 100
    for i in range(stem_steps):
        y_curr = top_y + (bottom_y - top_y) * (i / stem_steps)
        y_next = top_y + (bottom_y - top_y) * ((i + 1) / stem_steps) + 1
        # Interpolate Cyan (0, 229, 255) to Emerald (0, 230, 118)
        ratio = i / stem_steps
        r_col = 0
        g_col = int(229 + (230 - 229) * ratio)
        b_col = int(255 + (118 - 255) * ratio)
        draw.rectangle([stem_left, y_curr, stem_right, y_next], fill=(r_col, g_col, b_col, 255))

    # Rounded top and bottom caps for stem
    cap_r = stem_width // 2
    draw.ellipse([stem_left, top_y - cap_r, stem_right, top_y + cap_r], fill=(0, 229, 255, 255))
    draw.ellipse([stem_left, bottom_y - cap_r, stem_right, bottom_y + cap_r], fill=(0, 230, 118, 255))

    # B. Upper Loop of "R"
    # Outer arc
    outer_loop_r = 170
    outer_loop_box = [stem_right - 60, top_y, stem_right + outer_loop_r * 2 - 60, mid_y]
    draw.pieslice(outer_loop_box, start=270, end=90, fill=(0, 229, 255, 255))

    # Upper horizontal bar connecting stem to loop
    draw.rectangle([stem_right - 10, top_y, stem_right + outer_loop_r - 20, top_y + stem_width], fill=(0, 229, 255, 255))

    # Middle horizontal bar connecting stem to bottom of loop
    draw.rectangle([stem_right - 10, mid_y - stem_width, stem_right + outer_loop_r - 20, mid_y], fill=(0, 230, 180, 255))

    # Hollow out the inner loop (inner dark cutout)
    inner_margin = stem_width
    inner_loop_box = [
        stem_right,
        top_y + inner_margin,
        stem_right + (outer_loop_r * 2 - 60) - inner_margin * 2 + 10,
        mid_y - inner_margin,
    ]
    draw.pieslice(inner_loop_box, start=270, end=90, fill=(13, 20, 36, 255))
    draw.rectangle([stem_right, top_y + inner_margin, stem_right + 30, mid_y - inner_margin], fill=(13, 20, 36, 255))

    # C. Dynamic Diagonal Right Leg of "R" (Bulbous / energetic stroke)
    leg_poly = [
        (stem_right - 20, mid_y - 20),
        (stem_right + 80, mid_y - 20),
        (stem_right + 270, bottom_y),
        (stem_right + 150, bottom_y),
    ]
    # Draw gradient for leg
    draw.polygon(leg_poly, fill=(0, 230, 118, 255))

    # Sharp tech arrow tip / chamfer on diagonal leg
    draw.polygon([
        (stem_right + 270, bottom_y),
        (stem_right + 310, bottom_y - 40),
        (stem_right + 270, bottom_y - 80),
    ], fill=(0, 255, 180, 255))

    # 4. Glowing Accent Dots (High-Tech Matrix)
    accent_color = (0, 229, 255, 220)
    draw.ellipse([stem_left - 80, top_y + 40, stem_left - 60, top_y + 60], fill=accent_color)
    draw.ellipse([stem_left - 80, mid_y, stem_left - 60, mid_y + 20], fill=(0, 230, 160, 220))
    draw.ellipse([stem_left - 80, bottom_y - 40, stem_left - 60, bottom_y - 20], fill=(0, 230, 118, 220))

    # Save high-res master PNG
    img.save(PNG_PATH, format="PNG")
    img.save(LOGO_PATH, format="PNG")
    print(f"[OK] High-res master logo disimpan: {PNG_PATH}")

    # Generate multi-resolution Windows ICO
    # Resolutions: 256, 128, 64, 48, 32, 24, 16
    icon_sizes = [
        (256, 256),
        (128, 128),
        (64, 64),
        (48, 48),
        (32, 32),
        (24, 24),
        (16, 16),
    ]

    # Pillow supports saving .ico with sizes parameter
    img.save(
        ICO_PATH,
        format="ICO",
        sizes=icon_sizes,
    )
    print(f"[OK] Multi-resolution Windows Icon disimpan: {ICO_PATH}")
    print(f"     Ukuran terpasang: {', '.join([f'{w}x{h}' for w, h in icon_sizes])}")


if __name__ == "__main__":
    create_raptech_r_icon()
