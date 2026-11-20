# Deploy XAVIQ Trading Engine ke folder rilis mandiri (windeployqt).
#   powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\deploy.ps1
# Hasil:
#   1. C:\XaviqCppDist\XAVIQTradingEngine\
#   2. C:\Users\Administrator\Desktop\Auto Trade\Bot Trading\dist\XAVIQTradingEngine\
$ErrorActionPreference = "Stop"
$root = "C:\XaviqCpp"
if (Test-Path "C:\Users\Administrator\Desktop\My Produk\Auto Trade\Bot Trading") {
    $workspace = "C:\Users\Administrator\Desktop\My Produk\Auto Trade\Bot Trading"
} elseif (Test-Path "C:\Users\Administrator\Desktop\Auto Trade\Bot Trading") {
    $workspace = "C:\Users\Administrator\Desktop\Auto Trade\Bot Trading"
} elseif (Test-Path "C:\Users\Administrator\Desktop\Bot Trading") {
    $workspace = "C:\Users\Administrator\Desktop\Bot Trading"
} else {
    $workspace = Split-Path (Get-Item $root).Target -Parent
}
$qtBin = "C:\Qt\6.8.1\mingw_64\bin"
$env:PATH = "$qtBin;C:\Qt\Tools\mingw1310_64\bin;$env:PATH"

$dist = "C:\XaviqCppDist\XAVIQTradingEngine"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Path $dist | Out-Null

Copy-Item "$root\build\xaviq.exe" "$dist\XAVIQTradingEngine.exe"
Copy-Item -Recurse -Force "$workspace\scripts" "$dist\scripts" -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force "$workspace\py_backend" "$dist\py_backend"

# Salin runtime standalone py_bridge (jika sudah dikompilasi atau buat jika belum)
$pyBridgeSrc = "$workspace\build_test_bridge\py_bridge"
if (-not (Test-Path "$pyBridgeSrc\py_bridge.exe")) {
    Write-Host "==> Menyiapkan standalone py_bridge via PyInstaller..." -ForegroundColor Cyan
    & pyinstaller "$workspace\py_bridge.spec" --distpath "$workspace\build_test_bridge" --workpath "$workspace\build_test_bridge\work" --noconfirm
}
if (Test-Path "$pyBridgeSrc\py_bridge.exe") {
    Write-Host "==> Menyertakan embedded runtime py_bridge..." -ForegroundColor Cyan
    Copy-Item -Recurse -Force $pyBridgeSrc "$dist\py_bridge"
}

# Salin file bantuan & skrip instalasi
if (Test-Path "$workspace\Install_Prerequisites.bat") {
    Copy-Item "$workspace\Install_Prerequisites.bat" "$dist\Install_Prerequisites.bat" -Force
}
if (Test-Path "$workspace\Run_XAVIQ.bat") {
    Copy-Item "$workspace\Run_XAVIQ.bat" "$dist\Run_XAVIQ.bat" -Force
}

# Salin config & credentials default
if (Test-Path "$workspace\mcp_secret.json") {
    Copy-Item "$workspace\mcp_secret.json" "$dist\mcp_secret.json" -Force
}
if (Test-Path "$workspace\config.json") {
    Copy-Item "$workspace\config.json" "$dist\config.json" -Force
}

Write-Host "==> windeployqt..." -ForegroundColor Cyan
& "$qtBin\windeployqt.exe" --release --compiler-runtime `
    --qmldir "$root\qml" "$dist\XAVIQTradingEngine.exe"
if ($LASTEXITCODE -ne 0) { Write-Host "windeployqt GAGAL" -ForegroundColor Red; exit 1 }

# Plugin offscreen (untuk uji headless / server tanpa layar).
Copy-Item "C:\Qt\6.8.1\mingw_64\plugins\platforms\qoffscreen.dll" "$dist\platforms\" -Force -ErrorAction SilentlyContinue

# Sinkronkan juga ke direktori lokal Bot Trading\dist\XAVIQTradingEngine
$localDist = "$workspace\dist\XAVIQTradingEngine"
Write-Host "==> Menyalin rilis ke folder lokal: $localDist..." -ForegroundColor Cyan
if (Test-Path $localDist) { Remove-Item -Recurse -Force $localDist }
$localDistParent = Split-Path $localDist -Parent
if (-not (Test-Path $localDistParent)) { New-Item -ItemType Directory -Path $localDistParent | Out-Null }
Copy-Item -Recurse -Force $dist $localDist

# Buat arsip ZIP portabel untuk distribusi mudah ke laptop lain
$zipPath = "$workspace\dist\XAVIQTradingEngine.zip"
$desktopZip = "C:\Users\Administrator\Desktop\XAVIQTradingEngine.zip"
Write-Host "==> Mengompresi paket ZIP distribusi mandiri..." -ForegroundColor Cyan
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
if (Get-Command tar -ErrorAction SilentlyContinue) {
    & tar -a -cf "$zipPath" -C "$localDist" .
} else {
    Compress-Archive -Path "$localDist\*" -DestinationPath $zipPath -CompressionLevel Optimal
}
if (Test-Path "C:\Users\Administrator\Desktop") {
    Copy-Item $zipPath $desktopZip -Force -ErrorAction SilentlyContinue
}

$sizeMB = [math]::Round(((Get-ChildItem -Recurse $localDist | Measure-Object Length -Sum).Sum / 1MB), 1)
$zipSizeMB = [math]::Round(((Get-Item $zipPath).Length / 1MB), 1)
Write-Host "`n==> Rilis mandiri siap di folder ini: $localDist  (total ${sizeMB} MB)" -ForegroundColor Green
Write-Host "    Paket ZIP Mandiri (Portabel): $zipPath (${zipSizeMB} MB)" -ForegroundColor Green
Write-Host "    EXE Utama: $localDist\XAVIQTradingEngine.exe" -ForegroundColor Green
