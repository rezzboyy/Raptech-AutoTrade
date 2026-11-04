@echo off
REM ============================================================
REM  Raptech Autotrade CLI — Jalankan Headless Daemon (Background)
REM ============================================================
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

python main.py --headless
if errorlevel 1 pause
