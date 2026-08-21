"""
FPTester Fully-Bundled Windows Standalone Builder
Bundles Python 3.11 Embeddable Runtime directly into:
 1. FPTester-Windows-1Click.zip (Zero-dependency portable zip)
 2. FPTester-Windows.bat (Self-extracting single batch file)
"""
import os
import sys
import zipfile
import base64
import io
import shutil

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

def build_zip_package():
    print("=== 1. Building Fully Bundled FPTester-Windows-1Click.zip ===")
    os.makedirs(DIST_DIR, exist_ok=True)
    zip_path = os.path.join(DIST_DIR, "FPTester-Windows-1Click.zip")

    added = set()
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add app source files
        for rel in APP_FILES:
            full = os.path.join(SRC_DIR, rel)
            if os.path.exists(full) and rel not in added:
                zf.write(full, rel)
                added.add(rel)

        # Add bundled python embeddable environment
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

    size_mb = round(os.path.getsize(zip_path) / (1024 * 1024), 2)
    print(f"✅ Built: {zip_path} ({size_mb} MB)")

def build_sfx_bat():
    print("=== 2. Building Self-Extracting FPTester-Windows.bat ===")
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
        "",
        "echo [*] Initializing FPTester files and Python runtime in %FPTDIR% ...",
        "if not exist \"%FPTDIR%\" mkdir \"%FPTDIR%\"",
        "if exist \"%B64FILE%\" del /f /q \"%B64FILE%\"",
        "echo -----BEGIN CERTIFICATE----- >> \"%B64FILE%\"",
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
        "",
        "cd /d \"%FPTDIR%\"",
        "",
        "REM 1. Try bundled Python Embeddable runtime first",
        "if exist \"%FPTDIR%\\py_embed_win\\python.exe\" (",
        "    echo [*] Starting FPTester server with bundled Python runtime...",
        "    \"%FPTDIR%\\py_embed_win\\python.exe\" run_app.py",
        "    if %errorlevel% neq 0 (",
        "        echo [ERROR] Server exited with code %errorlevel%.",
        "        pause",
        "    )",
        "    goto end",
        ")",
        "",
        "REM 2. Fallback to System Python",
        "where py >nul 2>nul",
        "if %errorlevel%==0 (",
        "    echo [*] Starting FPTester server with system py...",
        "    py run_app.py",
        "    goto end",
        ")",
        "where python >nul 2>nul",
        "if %errorlevel%==0 (",
        "    echo [*] Starting FPTester server with system python...",
        "    python run_app.py",
        "    goto end",
        ")",
        "",
        "echo [ERROR] Could not start Python server.",
        "pause",
        "",
        ":end",
        "pause",
    ]

    bat_path = os.path.join(DIST_DIR, "FPTester-Windows.bat")
    with open(bat_path, "w", encoding="ascii", errors="ignore") as f:
        f.write("\r\n".join(bat_lines))

    size_mb = round(os.path.getsize(bat_path) / (1024 * 1024), 2)
    print(f"✅ Built: {bat_path} ({size_mb} MB)")

if __name__ == "__main__":
    build_zip_package()
    build_sfx_bat()
