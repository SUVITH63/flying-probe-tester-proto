@echo off
title FPTester - Automated Flying Probe PCB Tester
color 0A
echo.
echo  =========================================================
echo     FPTester - Automated Flying Probe PCB Tester
echo  =========================================================
echo.

cd /d "%~dp0"

REM ── Option 1: Standalone .exe already present ────────────────────────────────
if exist "FPTester-Windows.exe" (
    echo  [*] Found FPTester-Windows.exe — launching app...
    echo  [*] Your browser will open at http://localhost:8000
    echo.
    echo  [!] Keep this window open while using the app.
    echo  [!] Close this window to stop the server.
    echo.
    "FPTester-Windows.exe"
    goto end
)

REM ── Option 2: Python (py) is installed ──────────────────────────────────────
where py >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester server — browser will open automatically...
    echo  [!] Keep this window open while using the app.
    echo  [!] Press Ctrl+C to stop the server.
    echo.
    py run_app.py
    goto end
)

REM ── Option 3: Python is installed ───────────────────────────────────────────
where python >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester server — browser will open automatically...
    echo  [!] Keep this window open while using the app.
    echo  [!] Press Ctrl+C to stop the server.
    echo.
    python run_app.py
    goto end
)

REM ── Option 4: python3 is installed ──────────────────────────────────────────
where python3 >nul 2>nul
if %errorlevel%==0 (
    echo  [*] Starting FPTester server — browser will open automatically...
    echo  [!] Keep this window open while using the app.
    echo  [!] Press Ctrl+C to stop the server.
    echo.
    python3 run_app.py
    goto end
)

REM ── Option 5: Nothing found — download .exe from GitHub ─────────────────────
echo  [!] Python not found on this PC.
echo  [*] Downloading FPTester standalone app from GitHub (one-time only)...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/SUVITH63/Flying-probe-tester/releases/download/v1.1.0/FPTester-Windows.exe' -OutFile 'FPTester-Windows.exe'; Write-Host '  Download complete!'"

if exist "FPTester-Windows.exe" (
    echo.
    echo  [*] Download successful! Launching FPTester...
    echo  [*] Your browser will open at http://localhost:8000
    echo.
    echo  [!] Keep this window open while using the app.
    echo  [!] Close this window to stop the server.
    echo.
    "FPTester-Windows.exe"
    goto end
)

REM ── All options failed ───────────────────────────────────────────────────────
echo.
echo  =========================================================
echo   [ERROR] Could not start FPTester automatically.
echo  =========================================================
echo.
echo   Option A — Download and run the .exe directly:
echo     https://github.com/SUVITH63/Flying-probe-tester/releases/tag/v1.1.0
echo.
echo   Option B — Install Python then re-run this file:
echo     https://www.python.org/downloads/
echo.

:end
pause
