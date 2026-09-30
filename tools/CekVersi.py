"""Cek kecocokan versi antara terminal MT5 dan paket Python MetaTrader5.

Jalankan lewat: dobel-klik CekVersi.bat  (atau: python CekVersi.py)

Skrip ini TIDAK butuh koneksi ke MT5. Dia hanya:
  1. Membaca build terminal MT5 dari file log terminal.
  2. Membaca versi paket Python MetaTrader5 yang terpasang.
  3. Membandingkan keduanya dan memberi kesimpulan sederhana.
"""

import glob
import os
import re


def build_terminal_dari_log() -> int | None:
    """Ambil nomor build terminal terakhir dari file log MT5."""
    base = os.path.join(os.getenv("APPDATA", ""), "MetaQuotes", "Terminal")
    logs = glob.glob(os.path.join(base, "*", "logs", "*.log"))
    if not logs:
        return None
    logs.sort(key=os.path.getmtime, reverse=True)
    for log_path in logs[:5]:  # cek beberapa log terbaru
        try:
            with open(log_path, "r", encoding="utf-16", errors="ignore") as f:
                isi = f.read()
        except OSError:
            continue
        # Khusus baris "MetaTrader 5 ... build NNNN" (hindari "Windows ... build").
        cocok = re.findall(r"MetaTrader\s*5[^\n]*?build (\d+)", isi)
        if cocok:
            return int(cocok[-1])  # build terakhir yang tercatat
    return None


def versi_paket() -> str | None:
    try:
        import MetaTrader5 as mt5
        return getattr(mt5, "__version__", None)
    except Exception:
        return None


def build_dari_versi_paket(ver: str) -> int | None:
    """Versi paket '5.0.6180' -> build 6180."""
    if not ver:
        return None
    bagian = ver.split(".")
    try:
        return int(bagian[-1])
    except (ValueError, IndexError):
        return None


def main() -> None:
    print("=" * 55)
    print("  CEK KECOCOKAN VERSI MT5")
    print("=" * 55)

    build_term = build_terminal_dari_log()
    ver_pkg = versi_paket()
    build_pkg = build_dari_versi_paket(ver_pkg)

    if build_term is None:
        print("[?] Build terminal tidak terbaca dari log.")
        print("    Pastikan MT5 pernah dibuka di komputer ini.")
    else:
        print(f"[i] Build terminal MT5  : {build_term}")

    if ver_pkg is None:
        print("[!] Paket Python MetaTrader5 BELUM terpasang.")
        print("    Jalankan: pip install MetaTrader5")
        _tahan()
        return
    print(f"[i] Paket Python MT5     : {ver_pkg} (build {build_pkg})")
    print("-" * 55)

    if build_term is None or build_pkg is None:
        print("Tidak bisa membandingkan otomatis. Cek manual saja.")
    elif build_pkg >= build_term:
        print(">> VERSI SUDAH COCOK. Bot siap connect!")
        print("   Buka MT5 (login), lalu jalankan bot dan tekan Login_Connect.")
    else:
        selisih = build_term - build_pkg
        print(f">> MASIH BEDA VERSI (terminal {selisih} build lebih baru).")
        print("   Koneksi kemungkinan masih GAGAL (IPC timeout).")
        print("   Coba upgrade paket: pip install --upgrade MetaTrader5")
        print("   Kalau belum ada versi baru, tunggu beberapa hari lalu cek lagi.")

    _tahan()


def _tahan() -> None:
    print("=" * 55)
    try:
        input("Tekan Enter untuk menutup...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
