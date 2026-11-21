@echo off
REM ============================================================
REM  Run_XTradingEngine.bat - Jalankan X Trading Engine Standalone EXE
REM ============================================================
setlocal
cd /d "%~dp0"

set "APP_EXE=%~dp0dist\XTradingEngine\XTradingEngine.exe"
if not exist "%APP_EXE%" set "APP_EXE=%~dp0dist\XAVIQTradingEngine\XAVIQTradingEngine.exe"

if not exist "%APP_EXE%" (
    echo [INFO] Build standalone belum ditemukan di dist\XTradingEngine.
    echo Menjalankan deployment terlebih dahulu...
    call "%~dp0deploy_cpp.bat"
    set "APP_EXE=%~dp0dist\XTradingEngine\XTradingEngine.exe"
)

if exist "%APP_EXE%" (
    echo Menjalankan X Trading Engine...
    start "" "%APP_EXE%"
) else (
    echo [ERROR] Gagal menemukan %APP_EXE%
    pause
)

endlocal
