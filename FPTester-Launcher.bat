@echo off
title FPTester - Automated Flying Probe PCB Tester
color 0A
echo.
echo  =========================================================
echo     FPTester - Automated Flying Probe PCB Tester
echo  =========================================================
echo.

cd /d "%~dp0"

REM ── Step 1: Try to run with the bundled or already-downloaded .exe ──────────
if exist "FPTester-Windows.exe" (
    echo  [*] Launching FPTester.exe...
    start "" "FPTester-Windows.exe"
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

REM ── Step 2: Try system Python (py / python / python3) ───────────────────────
where py >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester server with Python...
    start "" /b py run_app.py
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester server with Python...
    start "" /b python run_app.py
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester server with Python...
    start "" /b python3 run_app.py
    timeout /t 3 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

REM ── Step 3: No Python found — download the standalone .exe from GitHub ───────
echo  [*] Python not found. Downloading FPTester standalone app from GitHub...
echo  [*] This only happens once. Please wait...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference = 'SilentlyContinue';" ^
    "$url = 'https://github.com/SUVITH63/Flying-probe-tester/releases/download/v1.1.0/FPTester-Windows.exe';" ^
    "Write-Host '  Downloading FPTester-Windows.exe...';" ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "Invoke-WebRequest -Uri $url -OutFile 'FPTester-Windows.exe';" ^
    "Write-Host '  Download complete!'"

if exist "FPTester-Windows.exe" (
    echo.
    echo  [*] Download successful! Launching FPTester...
    start "" "FPTester-Windows.exe"
    timeout /t 4 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

REM ── Step 4: Everything failed ────────────────────────────────────────────────
echo.
echo  [ERROR] Could not start FPTester automatically.
echo.
echo  Please try one of these options:
echo   1. Download FPTester-Windows.exe from:
echo      https://github.com/SUVITH63/Flying-probe-tester/releases/tag/v1.1.0
echo      and place it in this folder, then run this .bat again.
echo.
echo   2. Install Python from https://www.python.org and run:
echo      python run_app.py
echo.
pause
exit /b 1

:end
echo.
echo  [*] FPTester is running at http://localhost:8000
echo  [*] Keep this window open while using the app.
echo  [*] Close this window to stop the server.
echo.
pause
