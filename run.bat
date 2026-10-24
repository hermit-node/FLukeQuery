@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -m volthttp
) else (
    python -m volthttp
)
if errorlevel 1 pause
