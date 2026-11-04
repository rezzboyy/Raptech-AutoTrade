@echo off
REM ============================================================
REM  Raptech Autotrade CLI — Jalankan Terminal UI Interaktif
REM ============================================================
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

python main.py
if errorlevel 1 pause
