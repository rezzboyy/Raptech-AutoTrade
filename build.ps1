# Build script XAVIQ Trading Engine -> EXE (PowerShell)
# Jalankan: .\build.ps1
#
# Prasyarat: pip install -r requirements.txt  (termasuk pyinstaller, pillow)

$ErrorActionPreference = "Stop"

Write-Host "==> Membersihkan build lama..." -ForegroundColor Cyan
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist")  { Remove-Item -Recurse -Force "dist" }

Write-Host "==> Membuat ikon aplikasi..." -ForegroundColor Cyan
python tools\make_icon.py

Write-Host "==> Menjalankan PyInstaller..." -ForegroundColor Cyan
pyinstaller raptech_bot.spec --noconfirm

if (Test-Path "dist\XAVIQTradingEngine\XAVIQTradingEngine.exe") {
    if (-not (Test-Path "dist\XAVIQTradingEngine\strategies\scripts")) {
        New-Item -ItemType Directory -Force -Path "dist\XAVIQTradingEngine\strategies\scripts" | Out-Null
    }
    Copy-Item -Path "strategies\scripts\*" -Destination "dist\XAVIQTradingEngine\strategies\scripts\" -Recurse -Force
    Write-Host "`n==> BERHASIL. EXE ada di:" -ForegroundColor Green
    Write-Host "    dist\XAVIQTradingEngine\XAVIQTradingEngine.exe" -ForegroundColor Green
    Write-Host "`nCatatan: Salin file .env berisi kredensial ke folder yang sama"
    Write-Host "dengan EXE, atau bot tidak bisa login ke MT5." -ForegroundColor Yellow
} elseif (Test-Path "dist\RaptechMT5Bot\RaptechMT5Bot.exe") {
    Write-Host "`n==> BERHASIL. EXE ada di:" -ForegroundColor Green
    Write-Host "    dist\RaptechMT5Bot\RaptechMT5Bot.exe" -ForegroundColor Green
} else {
    Write-Host "`n==> GAGAL: EXE tidak ditemukan. Periksa output di atas." -ForegroundColor Red
    exit 1
}
