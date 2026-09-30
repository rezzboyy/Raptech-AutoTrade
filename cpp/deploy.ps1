# Deploy XAVIQ Trading Engine ke folder rilis mandiri (windeployqt).
#   powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\deploy.ps1
# Hasil: C:\XaviqCppDist\XAVIQTradingEngine\  (EXE + semua DLL Qt + plugin QML)
$ErrorActionPreference = "Stop"
$root = "C:\XaviqCpp"
$qtBin = "C:\Qt\6.8.1\mingw_64\bin"
$env:PATH = "$qtBin;C:\Qt\Tools\mingw1310_64\bin;$env:PATH"

$dist = "C:\XaviqCppDist\XAVIQTradingEngine"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Path $dist | Out-Null

Copy-Item "$root\build\xaviq.exe" "$dist\XAVIQTradingEngine.exe"

Write-Host "==> windeployqt..." -ForegroundColor Cyan
& "$qtBin\windeployqt.exe" --release --compiler-runtime `
    --qmldir "$root\qml" "$dist\XAVIQTradingEngine.exe"
if ($LASTEXITCODE -ne 0) { Write-Host "windeployqt GAGAL" -ForegroundColor Red; exit 1 }

# Plugin offscreen (untuk uji headless / server tanpa layar).
Copy-Item "C:\Qt\6.8.1\mingw_64\plugins\platforms\qoffscreen.dll" "$dist\platforms\" -Force -ErrorAction SilentlyContinue

$sizeMB = [math]::Round(((Get-ChildItem -Recurse $dist | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host "`n==> Rilis siap: $dist  (total ${sizeMB} MB)" -ForegroundColor Green
