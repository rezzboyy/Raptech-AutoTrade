@echo off
REM ============================================================
REM  Raptech AutoTrade — Buat ZIP Paket Rilis Customer
REM ============================================================
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

python scripts\package_customer.py
echo.
pause
