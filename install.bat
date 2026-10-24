@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -m pip install -r requirements.txt
) else (
    python -m pip install -r requirements.txt
)
echo.
if errorlevel 1 (
    echo Dependency installation did not complete successfully.
) else (
    echo Dependencies installed. Double-click run.bat to launch.
)
pause
