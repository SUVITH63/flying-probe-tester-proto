"""
FPTester Instant SFX Builder (Bulletproof ZIP Signature Search)
Appends raw ZIP payload after marker: REM __FPT_PAYLOAD_OFFSET_MARKER_999__
PowerShell finds 'FPT_PAYLOAD_OFFSET_MARKER_999' and locates ZIP header PK (0x50 0x4B 0x03 0x04).
Zero backticks, zero quote escape issues, 100% robust on all Windows PowerShell versions.
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
    print("Building Bulletproof SFX FPTester-Windows.bat ...")
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
    marker_str = "REM __FPT_PAYLOAD_OFFSET_MARKER_999__"
    marker_bytes = f"\r\n{marker_str}\r\n".encode("ascii")

    # Clean PowerShell extraction script — no backticks, no complex escapes
    ps_extract_script = (
        "$b = [System.IO.File]::ReadAllBytes($env:BAT_PATH); "
        "$mk = [System.Text.Encoding]::ASCII.GetBytes('FPT_PAYLOAD_OFFSET_MARKER_999'); "
        "$start = -1; "
        "for ($i = 0; $i -le $b.Length - $mk.Length; $i++) { "
        "    $m = $true; "
        "    for ($j = 0; $j -lt $mk.Length; $j++) { if ($b[$i + $j] -ne $mk[$j]) { $m = $false; break } } "
        "    if ($m) { $start = $i; break } "
        "} "
        "if ($start -gt 0) { "
        "    $zipStart = -1; "
        "    for ($i = $start; $i -le $b.Length - 4; $i++) { "
        "        if ($b[$i] -eq 0x50 -and $b[$i+1] -eq 0x4B -and $b[$i+2] -eq 0x03 -and $b[$i+3] -eq 0x04) { $zipStart = $i; break } "
        "    } "
        "    if ($zipStart -gt 0) { "
        "        $z = new-object byte[] ($b.Length - $zipStart); "
        "        [System.Buffer]::BlockCopy($b, $zipStart, $z, 0, $z.Length); "
        "        $tmp = [System.IO.Path]::Combine($env:TEMP, 'fpt_instant.zip'); "
        "        [System.IO.File]::WriteAllBytes($tmp, $z); "
        "        Expand-Archive -Path $tmp -DestinationPath $env:FPTDIR -Force; "
        "        Remove-Item $tmp -ErrorAction SilentlyContinue; "
        "    } "
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

if not exist "%FPTDIR%\\py_embed_win\\python.exe" (
    echo [*] Extracting FPTester and bundled Python 3.11 runtime to %FPTDIR% ...
    if not exist "%FPTDIR%" mkdir "%FPTDIR%"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "{ps_extract_script}"
    echo [*] Extraction complete!
    echo.
)

cd /d "%FPTDIR%"

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

    bat_bytes = bat_header.encode("ascii") + marker_bytes + zip_bytes

    out_bat = os.path.join(DIST_DIR, "FPTester-Windows.bat")
    with open(out_bat, "wb") as f:
        f.write(bat_bytes)

    size_mb = round(len(bat_bytes) / (1024 * 1024), 2)
    print(f"✅ Built Bulletproof SFX: {out_bat} ({size_mb} MB)")

if __name__ == "__main__":
    build_instant_sfx()
