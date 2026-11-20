@echo off
REM ============================================================
REM  run_cpp_dev.bat - Build & Jalankan XAVIQ Trading Engine (C++)
REM  Langsung dari root folder. Dobel-klik untuk menjalankan.
REM ============================================================
setlocal EnableDelayedExpansion

set "QTROOT=C:\Qt\6.8.1\mingw_64"
set "JUNC=C:\XaviqCpp"

set "PATH=%QTROOT%\bin;C:\Qt\Tools\mingw1310_64\bin;C:\Qt\Tools\CMake_64\bin;C:\Qt\Tools\Ninja;%PATH%"
set "QML2_IMPORT_PATH=%QTROOT%\qml"
set "QML_IMPORT_PATH=%QTROOT%\qml"

if exist "%JUNC%" rmdir "%JUNC%" >nul 2>&1
echo ==^> Menghubungkan junction %JUNC% -^> "%~dp0cpp"
mklink /J "%JUNC%" "%~dp0cpp" >nul
if errorlevel 1 (
    echo [GAGAL] Tidak bisa membuat junction. Jalankan sekali sebagai Administrator:
    echo         mklink /J %JUNC% "%~dp0cpp"
    pause
    exit /b 1
)

echo.
echo ==^> Membangun XAVIQ C++ (Release)...
powershell -ExecutionPolicy Bypass -File "%JUNC%\build.ps1"
if errorlevel 1 (
    echo.
    echo [BUILD GAGAL] Periksa pesan error di atas.
    pause
    exit /b 1
)

echo.
echo ==^> Menjalankan XAVIQ Trading Engine (C++ GUI)...
echo     Tutup jendela aplikasi untuk kembali ke terminal ini.
echo.
"%JUNC%\build\xaviq.exe"

echo.
echo ==^> Aplikasi ditutup.
pause
endlocal
