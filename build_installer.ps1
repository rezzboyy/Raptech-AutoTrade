# =====================================================================
# X Trading Engine - Inno Setup Installer Builder (PowerShell Engine)
# =====================================================================
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   X Trading Engine - Inno Setup Installer Builder        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$candidates = @(
    "C:\Users\Administrator\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$isccPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $isccPath) {
    Write-Host "[ERROR] Inno Setup Compiler (ISCC.exe) tidak ditemukan di sistem!" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/2] Memeriksa paket distribusi mandiri..." -ForegroundColor Yellow
$exePath = Join-Path $scriptDir "dist\XAVIQTradingEngine\XAVIQTradingEngine.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "      Folder dist belum lengkap, menjalankan deploy_cpp.bat..." -ForegroundColor Gray
    & cmd /c deploy_cpp.bat
}

Write-Host "`n[2/2] Mengompilasi installer Windows via Inno Setup 6..." -ForegroundColor Yellow
Write-Host "      Compiler: $isccPath" -ForegroundColor Gray
$issFile = Join-Path $scriptDir "installer.iss"

& "$isccPath" "$issFile"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Kompilasi Inno Setup gagal!" -ForegroundColor Red
    exit 1
}

$issContent = Get-Content $issFile -Raw
$appVer = "3.2.0"
if ($issContent -match '#define\s+MyAppVersion\s+"([^"]+)"') {
    $appVer = $matches[1]
}

$setupExe = Join-Path $scriptDir "dist\XTradingEngine_Setup_v$appVer.exe"
if (Test-Path $setupExe) {
    $sizeMb = [math]::Round((Get-Item $setupExe).Length / 1MB, 2)
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "  INSTALLER WINDOWS RESMI BERHASIL DIBUAT!                " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  Lokasi Berkas : $setupExe" -ForegroundColor Cyan
    Write-Host "  Ukuran Berkas : $sizeMb MB (Kompresi LZMA2 Ultra)" -ForegroundColor Cyan
    Write-Host "  Setup Wizard  : Modern GUI Installer (Desktop Shortcut + Start Menu)" -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Green
}
