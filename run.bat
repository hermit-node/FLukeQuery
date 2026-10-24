@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -m core
) else (
    python -m core
)
if errorlevel 1 (
    echo.
    echo FLukeQuery could not start. Run install.bat to install PySide6 and HTTPX.
    pause
)
