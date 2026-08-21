@echo off
title FPTester — Automated Flying Probe PCB Tester
echo =========================================================
echo    FPTester — Automated Flying Probe PCB Tester
echo =========================================================
echo.

set TARGET_DIR=%~dp0
if "%TARGET_DIR:~-1%"=="\" set TARGET_DIR=%TARGET_DIR:~0,-1%
if not exist "%TARGET_DIR%\run_app.py" set TARGET_DIR=%TEMP%\FPTester

REM ── Check System Python ──────────────────────────────────────────────────
where py >nul 2>nul
if %errorlevel%==0 (
    echo [*] Found system Python. Starting FPTester server...
    start "" "http://localhost:8000"
    py "%TARGET_DIR%\run_app.py"
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    echo [*] Found system Python. Starting FPTester server...
    start "" "http://localhost:8000"
    python "%TARGET_DIR%\run_app.py"
    goto end
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    echo [*] Found system Python3. Starting FPTester server...
    start "" "http://localhost:8000"
    python3 "%TARGET_DIR%\run_app.py"
    goto end
)

REM ── No Python Found: Auto-Download Portable Python Runtime ───────────────
echo [*] Python not detected on your system.
echo [*] Automatically downloading Portable Python Runtime (10MB, no install required)...
echo.

set PORTABLE_PY=%TEMP%\FPTester_Python

if not exist "%PORTABLE_PY%\python.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "
        $ProgressPreference = 'SilentlyContinue';
        $url = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';
        $zip = '$env:TEMP\python_embed.zip';
        Write-Host '[*] Fetching Portable Python package from python.org...';
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;
        Invoke-WebRequest -Uri $url -OutFile $zip;
        Write-Host '[*] Extracting portable runtime...';
        Expand-Archive -Path $zip -DestinationPath '$env:TEMP\FPTester_Python' -Force;
        Remove-Item $zip;
        $pth = '$env:TEMP\FPTester_Python\python311._pth';
        if (Test-Path $pth) {
            (Get-Content $pth) -replace '#import site', 'import site' | Set-Content $pth;
        }
        Write-Host '[*] Portable Python setup complete!';
    "
)

if exist "%PORTABLE_PY%\python.exe" (
    echo [*] Starting FPTester server with Portable Python...
    start "" "http://localhost:8000"
    "%PORTABLE_PY%\python.exe" "%TARGET_DIR%\run_app.py"
    goto end
)

echo.
echo [ERROR] Automatic Portable Python setup failed. Please check internet connection.
pause

:end
