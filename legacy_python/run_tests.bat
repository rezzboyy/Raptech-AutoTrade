@echo off
REM Jalankan 264 unit test Python (legacy)
setlocal
cd /d "%~dp0"
python -m pytest -q
pause
endlocal
