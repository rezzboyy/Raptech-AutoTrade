@echo off
REM ============================================================
REM  deploy_cpp.bat - Paketkan rilis mandiri C++ (windeployqt)
REM  Hasil rilis: C:\XaviqCppDist\XAVIQTradingEngine\
REM ============================================================
setlocal

set "JUNC=C:\XaviqCpp"
if exist "%JUNC%" rmdir "%JUNC%" >nul 2>&1
mklink /J "%JUNC%" "%~dp0cpp" >nul 2>&1

echo ==^> Memaketkan rilis mandiri C++...
powershell -ExecutionPolicy Bypass -File "%JUNC%\deploy.ps1"
if errorlevel 1 (
    echo [DEPLOY GAGAL]
    pause
    exit /b 1
)

echo.
echo ==^> Memverifikasi rilis mandiri (PATH terisolasi)...
powershell -ExecutionPolicy Bypass -File "%JUNC%\verify_dist.ps1"

echo.
pause
endlocal
