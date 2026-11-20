@echo off
REM ============================================================
REM  Run_XAVIQ.bat - Jalankan XAVIQ Trading Engine Standalone EXE
REM ============================================================
setlocal
cd /d "%~dp0"

set "APP_EXE=%~dp0dist\XAVIQTradingEngine\XAVIQTradingEngine.exe"

if not exist "%APP_EXE%" (
    echo [INFO] Build standalone belum ditemukan di dist\XAVIQTradingEngine.
    echo Menjalankan deployment terlebih dahulu...
    call "%~dp0deploy_cpp.bat"
)

if exist "%APP_EXE%" (
    echo Menjalankan XAVIQ Trading Engine...
    start "" "%APP_EXE%"
) else (
    echo [ERROR] Gagal menemukan %APP_EXE%
    pause
)

endlocal
