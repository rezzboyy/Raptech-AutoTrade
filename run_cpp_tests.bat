@echo off
REM ============================================================
REM  run_cpp_tests.bat - Jalankan 7 Test Suite C++ (QtTest/ctest)
REM ============================================================
setlocal

set "JUNC=C:\XaviqCpp"
if not exist "%JUNC%" (
    mklink /J "%JUNC%" "%~dp0cpp" >nul
)

powershell -ExecutionPolicy Bypass -File "%JUNC%\runtests.ps1"
echo.
pause
endlocal
