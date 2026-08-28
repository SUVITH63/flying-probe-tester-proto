@echo off
title FPTester Flying Probe PCB Tester
color 0A
echo.
echo  =========================================================
echo     FPTester - Automated Flying Probe PCB Tester
echo  =========================================================
echo.

cd /d "%~dp0"

REM Try system Python
where py >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester with Python...
    py run_app.py
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester with Python...
    python run_app.py
    goto end
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester with Python...
    python3 run_app.py
    goto end
)

REM Try bundled exe
if exist "FPTester-Windows.exe" (
    echo  [*] Starting FPTester standalone app...
    start "" "FPTester-Windows.exe"
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

echo.
echo  [ERROR] Python not found. Please run FPTester-Launcher.bat instead,
echo  which will automatically download everything needed.
echo.
pause

:end
pause
