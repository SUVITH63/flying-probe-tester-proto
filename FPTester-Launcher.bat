@echo off
title FPTester — Flying Probe PCB Tester
echo =========================================================
echo    FPTester — Automated Flying Probe PCB Tester Web App
echo =========================================================
echo.
echo [*] Starting FPTester server...
echo [*] Browser will open automatically at http://localhost:8000
echo [*] Press Ctrl+C to stop the server.
echo.

REM ── Option 1: Pre-built dist\FPTester\FPTester.exe ─────────────────────────
if exist "dist\FPTester\FPTester.exe" (
    echo [*] Found dist\FPTester\FPTester.exe — launching...
    start "" "dist\FPTester\FPTester.exe"
    timeout /t 2 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

REM ── Option 2: FPTester.exe in current directory ─────────────────────────────
if exist "FPTester.exe" (
    echo [*] Found FPTester.exe — launching...
    start "" "FPTester.exe"
    timeout /t 2 /nobreak >nul
    start "" "http://localhost:8000"
    goto end
)

REM ── Option 3: Python via 'py' launcher (Windows Store / official installer) ──
where py >nul 2>nul
if %errorlevel%==0 (
    echo [*] Found Python (py launcher) — starting server...
    start /B py run_app.py
    timeout /t 2 /nobreak >nul
    start "" "http://localhost:8000"
    echo.
    echo [*] Server running. Close this window to stop.
    py run_app.py
    goto end
)

REM ── Option 4: python command ─────────────────────────────────────────────────
where python >nul 2>nul
if %errorlevel%==0 (
    echo [*] Found Python — starting server...
    start /B python run_app.py
    timeout /t 2 /nobreak >nul
    start "" "http://localhost:8000"
    echo.
    echo [*] Server running. Close this window to stop.
    python run_app.py
    goto end
)

REM ── Option 5: python3 command ────────────────────────────────────────────────
where python3 >nul 2>nul
if %errorlevel%==0 (
    echo [*] Found Python3 — starting server...
    start /B python3 run_app.py
    timeout /t 2 /nobreak >nul
    start "" "http://localhost:8000"
    echo.
    echo [*] Server running. Close this window to stop.
    python3 run_app.py
    goto end
)

REM ── No Python or EXE found ───────────────────────────────────────────────────
echo.
echo [ERROR] Could not find FPTester.exe or a Python installation.
echo.
echo Please install Python from https://www.python.org/downloads/
echo Then re-run this launcher.
echo.
pause

:end
