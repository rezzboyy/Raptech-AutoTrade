@echo off
REM ============================================================
REM  rundev.bat - Build + jalankan XAVIQ (C++) mode DEV untuk
REM  DITEST dulu sebelum bikin EXE rilis (deploy.ps1).
REM  Cukup dobel-klik file ini.
REM ============================================================
setlocal EnableDelayedExpansion

set "QTROOT=C:\Qt\6.8.1\mingw_64"
set "JUNC=C:\XaviqCpp"

REM --- PATH toolchain Qt/MinGW/CMake/Ninja ---
set "PATH=%QTROOT%\bin;C:\Qt\Tools\mingw1310_64\bin;C:\Qt\Tools\CMake_64\bin;C:\Qt\Tools\Ninja;%PATH%"
set "QML2_IMPORT_PATH=%QTROOT%\qml"
set "QML_IMPORT_PATH=%QTROOT%\qml"

REM --- Pastikan junction tanpa spasi ada (qmlimportscanner gagal bila path ber-spasi) ---
if not exist "%JUNC%" (
    echo ==^> Membuat junction %JUNC% -^> "%~dp0"
    mklink /J "%JUNC%" "%~dp0." >nul
    if errorlevel 1 (
        echo [GAGAL] Tidak bisa membuat junction. Jalankan sekali sebagai Administrator:
        echo         mklink /J %JUNC% "%~dp0."
        pause
        exit /b 1
    )
)

echo.
echo ==^> Build (dev)...
powershell -ExecutionPolicy Bypass -File "%JUNC%\build.ps1"
if errorlevel 1 (
    echo.
    echo [BUILD GAGAL] Perbaiki error di atas lalu jalankan lagi.
    pause
    exit /b 1
)

echo.
echo ==^> Menjalankan XAVIQ Trading Engine (mode DEV / GUI)...
echo     Tutup jendela aplikasi untuk kembali ke sini.
echo.
"%JUNC%\build\xaviq.exe"

echo.
echo ==^> Aplikasi ditutup. Jika semua sudah OK, buat EXE rilis dengan:
echo     powershell -ExecutionPolicy Bypass -File %JUNC%\deploy.ps1
echo.
pause
endlocal
