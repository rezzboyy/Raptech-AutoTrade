@echo off
REM ============================================================
REM  run_cpp_tests.bat - Jalankan Test Suite C++ (QtTest/ctest)
REM ============================================================
setlocal

set "JUNC=C:\XaviqCpp"
if exist "%JUNC%" rmdir "%JUNC%" >nul 2>&1
mklink /J "%JUNC%" "%~dp0cpp" >nul 2>&1

powershell -ExecutionPolicy Bypass -File "%JUNC%\runtests.ps1"
echo.
pause
endlocal
