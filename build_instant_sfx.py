"""
FPTester Instant Binary-Tail Windows SFX Builder (v1.2.0 - Forced Embedded Python Extraction)
Appends raw ZIP payload (with Python 3.11 Embeddable Runtime) after __ZIP_START__ marker.
Checks for %FPTDIR%\\py_embed_win\\python.exe so extraction is NEVER skipped on systems with stale temp files.
"""
import os
import sys
import zipfile
import io

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
EMBED_DIR = os.path.join(SRC_DIR, "py_embed_win")
DIST_DIR = os.path.join(SRC_DIR, "dist")

APP_FILES = [
    "run_app.py",
    "pcb_api_server.py",
    "download_model.py",
    "main_parser.py",
    "start_windows.bat",
    "FPTester-Launcher.bat",
    "frontend/index.html",
    "parser/__init__.py",
    "parser/ai_planner.py",
    "parser/gerber_parser.py",
    "parser/kicad_parser.py",
    "parser/models.py",
    "parser/serial_dispatcher.py",
    "parser/test_plan_gen.py",
    "parser/workspace.py",
    "llm/__init__.py",
]

def build_instant_sfx():
    print("Building Instant Binary-Tail FPTester-Windows.bat (v1.2.0)...")
    os.makedirs(DIST_DIR, exist_ok=True)

    buf = io.BytesIO()
    added = set()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel in APP_FILES:
            full = os.path.join(SRC_DIR, rel)
            if os.path.exists(full) and rel not in added:
                zf.write(full, rel)
                added.add(rel)

        if os.path.exists(EMBED_DIR):
            for root, dirs, files in os.walk(EMBED_DIR):
                for f in files:
                    if f.startswith("._") or "__pycache__" in root:
                        continue
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, SRC_DIR)
                    if rel_path not in added:
                        zf.write(full_path, rel_path)
                        added.add(rel_path)

    zip_bytes = buf.getvalue()
    marker = b"\r\n__ZIP_START__\r\n"

    ps_extract_script = (
        "$bat = $env:BAT_PATH; "
        "$dest = $env:FPTDIR; "
        "$bytes = [System.IO.File]::ReadAllBytes($bat); "
        "$marker = [System.Text.Encoding]::ASCII.GetBytes(\"`r`n__ZIP_START__`r`n\"); "
        "$idx = -1; "
        "for ($i = 0; $i -le $bytes.Length - $marker.Length; $i++) { "
        "    $match = $true; "
        "    for ($j = 0; $j -lt $marker.Length; $j++) { "
        "        if ($bytes[$i + $j] -ne $marker[$j]) { $match = $false; break } "
        "    } "
        "    if ($match) { $idx = $i + $marker.Length; break } "
        "} "
        "if ($idx -gt 0) { "
        "    $zipBytes = new-object byte[] ($bytes.Length - $idx); "
        "    [System.Buffer]::BlockCopy($bytes, $idx, $zipBytes, 0, $zipBytes.Length); "
        "    $tmpZip = [System.IO.Path]::Combine($env:TEMP, 'fpt_instant.zip'); "
        "    [System.IO.File]::WriteAllBytes($tmpZip, $zipBytes); "
        "    Expand-Archive -Path $tmpZip -DestinationPath $dest -Force; "
        "    Remove-Item $tmpZip -ErrorAction SilentlyContinue; "
        "}"
    )

    bat_header = f"""@echo off
title FPTester - Flying Probe PCB Tester
echo =========================================================
echo    FPTester - Automated Flying Probe PCB Tester
echo =========================================================
echo.

set FPTDIR=%TEMP%\\FPTester
set BAT_PATH=%~f0

REM Force extraction if bundled python runtime is not present
if not exist "%FPTDIR%\\py_embed_win\\python.exe" (
    echo [*] Extracting FPTester and bundled Python 3.11 runtime to %FPTDIR% ...
    if not exist "%FPTDIR%" mkdir "%FPTDIR%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_extract_script}"
    echo [*] Extraction complete!
    echo.
)

cd /d "%FPTDIR%"

REM 1. Always use bundled Python 3.11 embeddable runtime
if exist "%FPTDIR%\\py_embed_win\\python.exe" (
    echo [*] Starting FPTester server with bundled Python runtime...
    "%FPTDIR%\\py_embed_win\\python.exe" run_app.py
    if %errorlevel% neq 0 (
        echo [ERROR] Server exited with code %errorlevel%.
        pause
    )
    goto end
)

echo [ERROR] Could not find bundled Python runtime in %FPTDIR%\\py_embed_win.
pause

:end
pause
exit /b
"""

    bat_bytes = bat_header.encode("ascii") + marker + zip_bytes

    out_bat = os.path.join(DIST_DIR, "FPTester-Windows.bat")
    with open(out_bat, "wb") as f:
        f.write(bat_bytes)

    size_mb = round(len(bat_bytes) / (1024 * 1024), 2)
    print(f"✅ Built Instant SFX: {out_bat} ({size_mb} MB)")

if __name__ == "__main__":
    build_instant_sfx()
