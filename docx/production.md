# Production & Deployment Guide — Raptech Autotrade CLI

> 📌 **Navigasi Dokumentasi**:  
> [📋 Task & Roadmap](task.md) • [📐 System Design](design.md) • [🛡️ Engineering Rules](rules.md) • [🚀 Production Guide](production.md) • [🤖 Agents Playbook](agents.md)

Panduan build, packaging (*freezing*), deploy, dan operasional produksi bot **Raptech Autotrade CLI** (TUI & Headless Edition). Dokumen ini mengacu pada tahapan rilis di [task.md §Phase 9](task.md#phase-9-slim-production-packaging-pyinstaller) dan batasan integritas [rules.md](rules.md).

---

## 1. Spesifikasi Produksi & Target Kinerja

| Parameter | Spesifikasi Target | Keterangan |
|---|---|---|
| **Platform Utama** | Windows 10 / 11 / Windows Server 2019/2022 x64 | Single-file executable (`RaptechAutoTradeCLI.exe`). |
| **Platform Sekunder** | Linux x64 (Ubuntu / Debian VPS) | Eksekusi Python murni via MCP Backend Gateway. |
| **Target Ukuran Executable** | **~28 MB – 38 MB** | Sangat ramping dibanding versi GUI desktop (~150 MB+). |
| **Konsumsi Memori (RAM)** | **~25 MB – 40 MB** | Ringan, stabil berjalan berbulan-bulan di VPS mini (1 GB RAM). |
| **Startup Latency** | **< 0.8 detik** | Booting instan tanpa beban runtime GUI atau GPU OpenGL. |
| **Konektivitas MT5** | IPC Native MT5 & Remote MCP JSON-RPC | Latensi order lokal < 5 ms. |

---

## 2. Prasyarat Lingkungan Build

1. **Python 3.10+ (64-bit)** terinstal dan terdaftar di `PATH`.
2. **Terminal MetaTrader 5** (build 4000+) terpasang di sistem jika menggunakan mode Native MT5.
3. Dependensi terinstal:
   ```cmd
   pip install rich textual typer MetaTrader5 aiohttp requests pyinstaller pytest
   ```

---

## 3. Konfigurasi PyInstaller (Slim Spec)

Untuk menjaga biner executable tetap ramping dan tidak membengkak oleh modul desktop yang tidak terpakai, konfigurasi PyInstaller `RaptechAutoTradeCLI.spec` wajib mengecualikan (*exclude*) modul-modul berikut:

### 3.1 Daftar Modul yang Wajib Dikecualikan (`excludes`):
- `PySide6`, `PySide2`, `PyQt5`, `PyQt6`, `shiboken6`
- `tkinter`, `turtle`, `test`
- `matplotlib`, `numpy`, `scipy`, `pandas` (gunakan kalkulasi native math/statistics)
- `PIL.ImageQt`, `OpenGL`

### 3.2 Daftar Modul yang Wajib Dimasukkan (`hiddenimports`):
- `rich`
- `textual`
- `typer`
- `MetaTrader5`
- `aiohttp`
- `requests`

### 3.3 Data Files yang Disertakan (`datas`):
- `strategies/` -> Folder strategi bawaan
- `data/settings.json.example` -> Template konfigurasi awal

---

## 4. Pipeline Build Otomatis (`scripts/build.py`)

Eksekusi build mandiri dilakukan dengan menjalankan skrip pembungkus:

```cmd
python scripts/build.py
```

Skrip ini secara otomatis:
1. Memvalidasi bahwa seluruh unit test lolos (`pytest tests/`).
2. Menghapus folder `build/` dan file `.spec` temporer lama.
3. Menjalankan PyInstaller dengan optimasi bytecode `-O2`.
4. Memindahkan biner terkompilasi ke folder `release/RaptechAutoTradeCLI.exe`.
5. Melakukan verifikasi hash SHA-256 dan smoke test boot off-screen.

---

## 5. Panduan Operasional di Server / VPS

### 5.1 Mode Terminal Interaktif di Windows VPS (RDP)
Jalankan langsung melalui PowerShell atau Windows Terminal:
```powershell
.\release\RaptechAutoTradeCLI.exe --profile Exness-Real-01
```
Gunakan hotkey keyboard untuk operasional cepat:
- `[S]`: Start / Stop Auto Trading
- `[C]`: Emergency Close All Open Positions
- `[M]`: Buka Order Manual
- `[P]`: Ganti Akun / Profil
- `[Q]`: Keluar Rapi (Graceful Exit)

### 5.2 Mode Background Daemon (Headless)
Jika bot ingin dijalankan di latar belakang tanpa jendela antarmuka:
```powershell
.\release\RaptechAutoTradeCLI.exe --headless --profile Exness-Real-01
```

### 5.3 Menjalankan Sebagai Windows Service (NSSM)
Agar bot otomatis berjalan saat VPS menyala tanpa perlu login user RDP:
1. Unduh **NSSM** (Non-Sucking Service Manager).
2. Daftarkan service baru:
   ```cmd
   nssm install RaptechAutotrade "C:\RaptechAutoTradeCLI\release\RaptechAutoTradeCLI.exe" "--headless --profile Exness-Real-01"
   nssm set RaptechAutotrade AppDirectory "C:\RaptechAutoTradeCLI"
   nssm set RaptechAutotrade AppStdout "C:\RaptechAutoTradeCLI\logs\service.log"
   nssm set RaptechAutotrade AppStderr "C:\RaptechAutoTradeCLI\logs\service_error.log"
   nssm start RaptechAutotrade
   ```

---

## 6. Pemeliharaan & Troubleshooting

1. **Terminal MT5 Tidak Terhubung (`IPC Connection Failed`)**:
   - Pastikan opsi *Allow algorithmic trading* / *AutoTrading* di MT5 sudah aktif.
   - Pastikan path `terminal64.exe` sudah benar pada profil akun.
   - Pastikan akun broker tidak dalam status *read-only* (investor password).
2. **Kestabilan Memori (Zero Memory Leak)**:
   - Bot dilengkapi coroutine `Watchdog` yang melakukan garbage collection periodik setiap 4 jam untuk menjaga konsumsi RAM tetap di bawah 40 MB.
3. **Backup Data Otomatis**:
   - Lakukan backup konfigurasi dan riwayat transaksi secara teratur:
     ```bash
     python main.py backup
     ```
   - Arsip disimpan dalam format ZIP terkompresi di folder `backups/raptech_backup_*.zip`.
