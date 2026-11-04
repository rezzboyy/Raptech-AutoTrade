@echo off
REM ============================================================
REM  Raptech Autotrade CLI — Build Standalone Executable (PyInstaller)
REM ============================================================
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

python scripts\build.py
echo.
pause
