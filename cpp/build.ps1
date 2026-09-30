# Build XAVIQ Trading Engine (C++/Qt6).
# PENTING: jalankan lewat junction tanpa spasi (C:\XaviqCpp), BUKAN dari
# folder "Bot Trading" (spasi memecah qmlimportscanner Qt).
#
# Setup junction sekali (Command Prompt / PowerShell as admin bila perlu):
#   cmd /c mklink /J C:\XaviqCpp "C:\Users\Administrator\Desktop\Bot Trading\cpp"
#
# Build:
#   powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\build.ps1
$ErrorActionPreference = "Stop"
$root = "C:\XaviqCpp"   # gunakan junction (path tanpa spasi)

$env:PATH = "C:\Qt\6.8.1\mingw_64\bin;C:\Qt\Tools\mingw1310_64\bin;C:\Qt\Tools\CMake_64\bin;C:\Qt\Tools\Ninja;$env:PATH"
$env:CMAKE_PREFIX_PATH = "C:\Qt\6.8.1\mingw_64"

Write-Host "==> Configure (Ninja + MinGW)..." -ForegroundColor Cyan
cmake -S $root -B "$root\build" -G Ninja -DCMAKE_BUILD_TYPE=Release `
    -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_COMPILER=gcc
if ($LASTEXITCODE -ne 0) { Write-Host "Configure GAGAL" -ForegroundColor Red; exit 1 }

Write-Host "==> Build..." -ForegroundColor Cyan
cmake --build "$root\build"
if ($LASTEXITCODE -ne 0) { Write-Host "Build GAGAL" -ForegroundColor Red; exit 1 }

Write-Host "`n==> BERHASIL. EXE: $root\build\xaviq.exe" -ForegroundColor Green
