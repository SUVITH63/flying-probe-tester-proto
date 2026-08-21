"""
FPTester Windows Self-Extracting Launcher Builder (Auto-Bootstrapping Python & Native Browser Trigger)
Creates a standalone FPTester-Windows.bat that:
 - Decodes embedded ZIP payload via certutil to %TEMP%/FPTester
 - Uses background delayed Windows OS shell command to open default browser at http://localhost:8000
 - Checks for system Python; if missing, auto-downloads Portable Python 3.11 in 3 seconds
 - Requires ZERO user setup, NO manual Python installation, and NO admin rights!
"""
import os
import sys
import zipfile
import base64
import io

SRC_DIR = os.path.dirname(os.path.abspath(__file__))

INCLUDE = [
    "run_app.py",
    "pcb_api_server.py",
    "download_model.py",
    "main_parser.py",
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

def build_sfx_bat():
    print("Building FPTester Windows Self-Extracting .bat (Native OS Browser Trigger)...")

    buf = io.BytesIO()
    added_files = set()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path in INCLUDE:
            abs_path = os.path.join(SRC_DIR, rel_path)
            if os.path.exists(abs_path) and rel_path not in added_files:
                zf.write(abs_path, rel_path)
                added_files.add(rel_path)

        llm_dir = os.path.join(SRC_DIR, "llm")
        if os.path.isdir(llm_dir):
            for root, dirs, files in os.walk(llm_dir):
                for f in files:
                    if f.startswith("._") or "__pycache__" in root:
                        continue
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, SRC_DIR)
                    if rel not in added_files:
                        zf.write(full, rel)
                        added_files.add(rel)

    zip_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    b64_lines = [zip_b64[i:i+64] for i in range(0, len(zip_b64), 64)]

    bat_lines = [
        "@echo off",
        "title FPTester - Flying Probe PCB Tester",
        "echo =========================================================",
        "echo    FPTester - Automated Flying Probe PCB Tester",
        "echo =========================================================",
        "echo.",
        "",
        "set FPTDIR=%TEMP%\\FPTester",
        "set B64FILE=%TEMP%\\fpt_payload.b64",
        "set ZIPFILE=%TEMP%\\fpt_payload.zip",
        "set PORTABLE_PY=%TEMP%\\FPTester_Python",
        "",
        "if not exist \"%FPTDIR%\\run_app.py\" (",
        "    echo [*] First run: extracting FPTester to %FPTDIR% ...",
        "    if not exist \"%FPTDIR%\" mkdir \"%FPTDIR%\"",
        "    if exist \"%B64FILE%\" del /f /q \"%B64FILE%\"",
        "    echo -----BEGIN CERTIFICATE----- >> \"%B64FILE%\"",
    ]

    for line in b64_lines:
        bat_lines.append(f"    echo {line} >> \"%B64FILE%\"")

    bat_lines += [
        "    echo -----END CERTIFICATE----- >> \"%B64FILE%\"",
        "    certutil -decode \"%B64FILE%\" \"%ZIPFILE%\" >nul 2>&1",
        "    powershell -NoProfile -Command \"Expand-Archive -Path '%ZIPFILE%' -DestinationPath '%FPTDIR%' -Force\"",
        "    if exist \"%B64FILE%\" del /f /q \"%B64FILE%\"",
        "    if exist \"%ZIPFILE%\" del /f /q \"%ZIPFILE%\"",
        "    echo [*] Extraction complete.",
        "    echo.",
        ")",
        "",
        "REM ── Trigger background browser opener (waits 2s for server, then opens default browser) ──",
        "start /B cmd /c \"timeout /t 2 >nul & start \"\" http://localhost:8000\"",
        "",
        "REM ── System Python Check ─────────────────────────────────────────────",
        "where py >nul 2>nul",
        "if %errorlevel%==0 (",
        "    echo [*] Starting FPTester server with py...",
        "    py \"%FPTDIR%\\run_app.py\"",
        "    goto end",
        ")",
        "",
        "where python >nul 2>nul",
        "if %errorlevel%==0 (",
        "    echo [*] Starting FPTester server with python...",
        "    python \"%FPTDIR%\\run_app.py\"",
        "    goto end",
        ")",
        "",
        "where python3 >nul 2>nul",
        "if %errorlevel%==0 (",
        "    echo [*] Starting FPTester server with python3...",
        "    python3 \"%FPTDIR%\\run_app.py\"",
        "    goto end",
        ")",
        "",
        "REM ── Auto-Bootstrap Portable Python Environment ────────────────────────",
        "echo [*] Python not detected on system.",
        "echo [*] Auto-setting up Portable Python (10MB, zero install required)...",
        "echo.",
        "",
        "if not exist \"%PORTABLE_PY%\\python.exe\" (",
        "    powershell -NoProfile -ExecutionPolicy Bypass -Command \"",
        "        $ProgressPreference = 'SilentlyContinue';",
        "        $url = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';",
        "        $zip = '$env:TEMP\\python_embed.zip';",
        "        Write-Host '[*] Downloading Portable Python package...';",
        "        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;",
        "        Invoke-WebRequest -Uri $url -OutFile $zip;",
        "        Write-Host '[*] Extracting portable runtime...';",
        "        Expand-Archive -Path $zip -DestinationPath '$env:TEMP\\FPTester_Python' -Force;",
        "        Remove-Item $zip;",
        "        $pth = '$env:TEMP\\FPTester_Python\\python311._pth';",
        "        if (Test-Path $pth) {",
        "            (Get-Content $pth) -replace '#import site', 'import site' | Set-Content $pth;",
        "        }",
        "        Write-Host '[*] Portable Python setup complete!';",
        "    \"",
        ")",
        "",
        "if exist \"%PORTABLE_PY%\\python.exe\" (",
        "    echo [*] Starting FPTester server with Portable Python...",
        "    \"%PORTABLE_PY%\\python.exe\" \"%FPTDIR%\\run_app.py\"",
        "    goto end",
        ")",
        "",
        "echo [ERROR] Portable Python download failed. Please check internet connection.",
        "pause",
        "",
        ":end",
    ]

    out_path = os.path.join(SRC_DIR, "dist", "FPTester-Windows.bat")
    os.makedirs(os.path.join(SRC_DIR, "dist"), exist_ok=True)
    with open(out_path, "w", encoding="ascii", errors="ignore") as f:
        f.write("\r\n".join(bat_lines))

    size_kb = os.path.getsize(out_path) // 1024
    print(f"✅ Built: {out_path} ({size_kb} KB)")

if __name__ == "__main__":
    build_sfx_bat()
