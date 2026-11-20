"""Generate ikon aplikasi untuk SEMUA kebutuhan bot dari satu sumber.

Sumber ikon (prioritas atas ke bawah):
    1. iconnew.png     (root project)        <- file ikon kustom TERBARU pengguna
    2. iconbaru.png    (root project)
    3. icon.ico        (root project)
    4. icon.png        (root project)
    4. tools/source_icon.png / .ico
    5. ui/assets/source_icon.png
    6. fallback: logo gambar sederhana (gradasi hijau + garis tren)

Output:
    - ui/assets/icon.ico      : ICO multi-ukuran (16, 20, 24, 32, 40, 48, 64, 96, 128, 256) untuk Windows
    - ui/assets/icon.png      : PNG 256x256 untuk Splash & komponen UI umum
    - ui/assets/icon-{s}.png  : PNG terpisah untuk tiap resolusi (16, 20, 24, 32, 40, 48, 64, 96, 128, 256, 512)
    - tools/source_icon.png   : Master arsip resolusi penuh

Jalankan: python tools/make_icon.py
"""

import os
import shutil

from PIL import Image, ImageDraw

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT_DIR, "ui", "assets")
OUT_ICO = os.path.join(OUT_DIR, "icon.ico")
OUT_PNG = os.path.join(OUT_DIR, "icon.png")

# Ukuran ICO yang dibutuhkan ekosistem Windows (taskbar, desktop, tray, Explorer, alt-tab, high-DPI).
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

# Ukuran PNG terpisah untuk berbagai keperluan UI & display.
PNG_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256, 512]

# Kandidat berkas sumber (ikon kustom pengguna).
SOURCE_CANDIDATES = [
    os.path.join(ROOT_DIR, "iconnew.png"),
    os.path.join(ROOT_DIR, "iconbaru.png"),
    os.path.join(ROOT_DIR, "icon.ico"),
    os.path.join(ROOT_DIR, "icon.png"),
    os.path.join(ROOT_DIR, "tools", "source_icon.png"),
    os.path.join(ROOT_DIR, "tools", "source_icon.ico"),
    os.path.join(OUT_DIR, "source_icon.png"),
]

# Warna fallback (bila tidak ada sumber kustom).
BG_TOP = (34, 197, 94)
BG_BOTTOM = (16, 122, 60)
FG = (255, 255, 255)


def _load_source() -> tuple[Image.Image | None, str | None]:
    """Muat ikon sumber kustom bila ada; ambil frame terbesar & jadikan RGBA persegi."""
    out_abs = os.path.abspath(OUT_ICO)
    for cand in SOURCE_CANDIDATES:
        if not os.path.exists(cand):
            continue
        if os.path.abspath(cand) == out_abs:
            continue  # jangan pakai output sebagai sumber
        try:
            img = Image.open(cand)
            # Untuk .ico multi-frame, pilih frame terbesar.
            if getattr(img, "n_frames", 1) and cand.lower().endswith(".ico"):
                largest, best = img, 0
                try:
                    for i in range(getattr(img, "n_frames", 1)):
                        img.seek(i)
                        area = img.size[0] * img.size[1]
                        if area > best:
                            best = area
                            largest = img.copy()
                except EOFError:
                    pass
                img = largest
            img = img.convert("RGBA")
            print(f"Sumber ikon: {cand} ({img.size[0]}x{img.size[1]})")
            return _squarify(img), cand
        except Exception as exc:  # noqa: BLE001
            print(f"Gagal memuat sumber {cand}: {exc}")
    return None, None


def _squarify(img: Image.Image, pad_ratio: float = 0.03) -> Image.Image:
    """Potong margin transparan, lalu jadikan persegi dgn padding tipis.

    Tujuannya agar logo mengisi hampir penuh kanvas sehingga tetap jelas/besar
    saat ditampilkan kecil (title bar/taskbar 16-32px). `pad_ratio` = margin kosong
    di tiap sisi (fraksi dari sisi konten).
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    # 1) Buang border transparan/semi-transparan (ambang alpha agar crop ketat).
    alpha = img.split()[3]
    mask = alpha.point(lambda a: 255 if a > 40 else 0)
    bbox = mask.getbbox() or alpha.getbbox()
    if bbox:
        img = img.crop(bbox)
    # 2) Persegi + padding tipis (logo mengisi hampir penuh kanvas).
    w, h = img.size
    content = max(w, h)
    pad = int(content * pad_ratio)
    side = content + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
    return canvas


def _fallback_logo(size: int = 512) -> Image.Image:
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        gd.line([(0, y), (size, y)], fill=(r, g, b, 255))
    radius = int(size * 0.24)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(icon)
    s = size / 48.0
    pts = [(10 * s, 31 * s), (19 * s, 22 * s), (25 * s, 27 * s), (38 * s, 13 * s)]
    draw.line(pts, fill=FG, width=max(2, int(3 * s)), joint="curve")
    rr = max(2, int(3.2 * s))
    ex, ey = pts[-1]
    draw.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=FG)
    return icon


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    base, src_path = _load_source()
    if base is None:
        print("Tidak ada ikon sumber kustom, memakai logo bawaan.")
        base = _fallback_logo(512)

    # Simpan master arsip di tools/source_icon.png agar sumber selalu terjaga
    tools_source = os.path.join(ROOT_DIR, "tools", "source_icon.png")
    if src_path is None or os.path.abspath(src_path) != os.path.abspath(tools_source):
        try:
            base.save(tools_source, format="PNG")
            print(f"Master ikon diarsipkan: {tools_source}")
        except Exception as exc:  # noqa: BLE001
            print(f"Catatan: Gagal mengarsipkan master: {exc}")

    # Generate setiap ukuran ICO secara presisi langsung dari base beresolusi tinggi (LANCZOS)
    sorted_ico_sizes = sorted(set(ICO_SIZES))
    ico_frames = [base.resize((s, s), Image.Resampling.LANCZOS) for s in sorted_ico_sizes]
    # Pillow save ICO membutuhkan master frame (256x256) sebagai pemanggil dan frame lainnya di append_images
    master_ico = [f for f in ico_frames if f.size == (256, 256)][0]
    other_ico = [f for f in ico_frames if f.size != (256, 256)]
    master_ico.save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in sorted_ico_sizes],
        append_images=other_ico,
    )
    print(f"ICO dibuat: {OUT_ICO}  (ukuran: {', '.join(str(s) for s in sorted_ico_sizes)})")

    # PNG standar (256x256) untuk Splash & umum
    png_256 = base.resize((256, 256), Image.Resampling.LANCZOS)
    png_256.save(OUT_PNG, format="PNG")
    print(f"PNG dibuat : {OUT_PNG}  (256x256)")

    # PNG per ukuran spesifik
    for s in PNG_SIZES:
        png_path = os.path.join(OUT_DIR, f"icon-{s}.png")
        resized = base.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(png_path, format="PNG")

    print(f"PNG multi-ukuran dibuat di {OUT_DIR} (ukuran: {', '.join(str(s) for s in PNG_SIZES)})")

    # Sinkronisasi ke dist bila build EXE sudah ada
    for dist_name in ["XAVIQTradingEngine", "RaptechMT5Bot"]:
        dist_assets = os.path.join(ROOT_DIR, "dist", dist_name, "_internal", "ui", "assets")
        if os.path.isdir(dist_assets):
            try:
                shutil.copy2(OUT_ICO, os.path.join(dist_assets, "icon.ico"))
                shutil.copy2(OUT_PNG, os.path.join(dist_assets, "icon.png"))
                print(f"Distributable assets disinkronkan ke: {dist_assets}")
            except Exception as exc:  # noqa: BLE001
                print(f"Catatan: Gagal sinkronisasi dist ({dist_name}): {exc}")


if __name__ == "__main__":
    main()
