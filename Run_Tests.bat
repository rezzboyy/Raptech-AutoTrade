@echo off
REM ============================================================
REM  Raptech Autotrade CLI — Jalankan Test Suite Pytest
REM ============================================================
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

python -m pytest tests/
echo.
pause
