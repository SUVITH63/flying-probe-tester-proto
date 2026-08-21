@echo off
title FPTester — Automated Flying Probe PCB Tester
echo =========================================================
echo    FPTester — Automated Flying Probe PCB Tester
echo =========================================================
echo.

cd /d "%~dp0"

REM ── Check if user ran directly inside an un-extracted ZIP file ─────────────
if not exist "run_app.py" (
    echo.
    echo ====================================================================
    echo  [!] IMPORTANT: YOU MUST EXTRACT THE ZIP FILE FIRST!
    echo ====================================================================
    echo.
    echo  You clicked FPTester-Launcher.bat directly inside the ZIP folder.
    echo  Windows cannot start the Python server from inside a compressed ZIP.
    echo.
    echo  HOW TO FIX THIS (2 Easy Steps):
    echo   1. Right-click "FPTester-Windows-1Click.zip"
    echo   2. Select "Extract All..." -> Click "Extract"
    echo   3. Open the new extracted folder and run FPTester-Launcher.bat!
    echo.
    echo ====================================================================
    echo.
    pause
    exit /b
)

REM ── Check System Python & Launch Server ───────────────────────────────────
where py >nul 2>nul
if %errorlevel%==0 (
    echo [*] Starting FPTester server with py...
    py run_app.py
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] FPTester server exited with error code %errorlevel%.
        pause
    )
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    echo [*] Starting FPTester server with python...
    python run_app.py
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] FPTester server exited with error code %errorlevel%.
        pause
    )
    goto end
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    echo [*] Starting FPTester server with python3...
    python3 run_app.py
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] FPTester server exited with error code %errorlevel%.
        pause
    )
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
    "%PORTABLE_PY%\python.exe" run_app.py
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] FPTester server exited with error code %errorlevel%.
        pause
    )
    goto end
)

echo.
echo [ERROR] Automatic Portable Python setup failed. Please check internet connection.
pause

:end
