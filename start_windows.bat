@echo off
title FPTester Flying Probe PCB Tester Web App
echo =========================================================
echo    FPTester - Automated Flying Probe PCB Tester Web App
echo =========================================================
echo.

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -c "import sys" >nul 2>nul
    if %errorlevel%==0 (
        if not exist "llm\models\fptester-circuit-llm.gguf" (
            echo [*] Downloading local GGUF LLM Model for offline AI reasoning...
            py download_model.py
        )
        echo [*] Launching FPTester server with py...
        py run_app.py
        if %errorlevel% neq 0 (
            echo.
            echo [ERROR] Server exited with code %errorlevel%.
            pause
        )
        goto end
    )
)

where python >nul 2>nul
if %errorlevel%==0 (
    python -c "import sys" >nul 2>nul
    if %errorlevel%==0 (
        if not exist "llm\models\fptester-circuit-llm.gguf" (
            echo [*] Downloading local GGUF LLM Model for offline AI reasoning...
            python download_model.py
        )
        echo [*] Launching FPTester server with python...
        python run_app.py
        if %errorlevel% neq 0 (
            echo.
            echo [ERROR] Server exited with code %errorlevel%.
            pause
        )
        goto end
    )
)

where python3 >nul 2>nul
if %errorlevel%==0 (
    python3 -c "import sys" >nul 2>nul
    if %errorlevel%==0 (
        if not exist "llm\models\fptester-circuit-llm.gguf" (
            echo [*] Downloading local GGUF LLM Model for offline AI reasoning...
            python3 download_model.py
        )
        echo [*] Launching FPTester server with python3...
        python3 run_app.py
        if %errorlevel% neq 0 (
            echo.
            echo [ERROR] Server exited with code %errorlevel%.
            pause
        )
        goto end
    )
)

echo [!] System Python command was not detected or active.
echo [!] Launching FPTester-Launcher.bat ...
if exist FPTester-Launcher.bat (
    call FPTester-Launcher.bat
    goto end
)

echo.
echo [ERROR] Could not start Python server automatically.
echo Please run FPTester-Launcher.bat!
echo.
pause

:end
pause
