@echo off
REM ============================================================
REM  Install_Prerequisites.bat - Penginstal Dependensi XAVIQ
REM  Jalankan file ini bila ingin menyiapkan runtime Python di laptop baru
REM ============================================================
setlocal
title XAVIQ Trading Engine - Setup Prasyarat

echo ============================================================
echo   XAVIQ Trading Engine - Pemeriksaan & Setup Prasyarat
echo ============================================================
echo.

set "PY_CMD="

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [PERINGATAN] Python belum terdeteksi di PATH sistem ini.
    echo.
    echo Ingin mencoba memasang Python 3.12 otomatis via Windows Package Manager (winget)?
    choice /M "Pasang Python 3.12 sekarang"
    if errorlevel 2 goto MANUAL_INSTALL
    if errorlevel 1 (
        echo.
        echo Menjalankan: winget install Python.Python.3.12 --scope currentuser
        winget install Python.Python.3.12 --scope currentuser
        echo.
        echo Silakan tutup jendela command prompt ini dan buka kembali
        echo agar PATH sistem diperbarui oleh Windows.
        pause
        exit /b 0
    )
)

:MANUAL_INSTALL
if "%PY_CMD%"=="" (
    echo.
    echo Unduh dan instal Python secara manual dari:
    echo https://www.python.org/downloads/
    echo PENTING: Centang kotak "Add Python to PATH" saat menginstal!
    echo.
    pause
    exit /b 1
)

echo [OK] Menggunakan interpreter: %PY_CMD%
%PY_CMD% --version
echo.
echo Menginstal paket trading MT5 dan pustaka analisis data...
echo.

%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install MetaTrader5 pandas numpy requests python-dotenv

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo  [SUKSES] Seluruh paket dan dependensi berhasil dipasang!
    echo  XAVIQ Trading Engine siap dijalankan di laptop ini.
    echo ============================================================
) else (
    echo.
    echo [PERINGATAN] Terjadi kendala saat instalasi pip.
    echo Pastikan laptop terhubung ke internet dan coba kembali.
)

echo.
pause
endlocal
