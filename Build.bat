@echo off
REM ================================================================
REM   Build.bat - Raptech MT5 Bot (PySide6 + QML -> EXE)
REM   Double-click file ini untuk build EXE setelah ada perubahan.
REM   Output: dist\RaptechMT5Bot\RaptechMT5Bot.exe
REM ================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ==^> [1/4] Membersihkan build lama...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"

echo.
echo ==^> [2/4] Membuat ikon aplikasi...
python tools\make_icon.py
if errorlevel 1 goto :error

echo.
echo ==^> [3/4] Menjalankan PyInstaller...
pyinstaller raptech_bot.spec --noconfirm
if errorlevel 1 goto :error

echo.
echo ==^> [4/4] Memeriksa hasil build...
if exist "dist\XAVIQTradingEngine\XAVIQTradingEngine.exe" (
    echo.
    echo ================================================================
    echo   BERHASIL. EXE ada di:
    echo   dist\XAVIQTradingEngine\XAVIQTradingEngine.exe
    echo ================================================================
    echo.
    echo Catatan: salin file .env berisi kredensial MT5 ke folder yang
    echo sama dengan EXE, atau bot tidak bisa login.
    echo.
    goto :done
)
if exist "dist\RaptechMT5Bot\RaptechMT5Bot.exe" (
    echo.
    echo ================================================================
    echo   BERHASIL. EXE ada di:
    echo   dist\RaptechMT5Bot\RaptechMT5Bot.exe
    echo ================================================================
    echo.
    echo Catatan: salin file .env berisi kredensial MT5 ke folder yang
    echo sama dengan EXE, atau bot tidak bisa login.
    echo.
    goto :done
) else (
    goto :error
)

:error
echo.
echo ================================================================
echo   GAGAL: EXE tidak ditemukan / ada error saat build.
echo   Periksa pesan error di atas.
echo ================================================================
echo.
pause
exit /b 1

:done
pause
exit /b 0
