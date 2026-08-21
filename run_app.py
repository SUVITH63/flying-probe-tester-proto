#!/usr/bin/env python3
"""
FPTester Standalone Cross-Platform Application Launcher
Runs natively on Windows, macOS, and Linux without requiring pip install or external dependencies.
"""
import os
import sys
import time
import socket
import threading
import webbrowser
from pcb_api_server import run_server

def open_browser(url, delay=0.5):
    time.sleep(delay)
    # Wait until the HTTP server is listening on port 8000 before launching browser
    for _ in range(50):
        try:
            s = socket.create_connection(("127.0.0.1", 8000), timeout=0.3)
            s.close()
            break
        except Exception:
            time.sleep(0.2)
    try:
        webbrowser.open(url)
    except Exception:
        print(f"[!] Note: Please open {url} manually in your web browser.")

def main():
    port = 8000
    print("=" * 65)
    print("   FPTester — Automated Flying Probe PCB Tester Web App")
    print("=" * 65)
    print(f"[*] Starting FPTester Web App Server on http://localhost:{port}...")
    print("[*] Compatible with Windows, macOS, and Linux.")
    print("[*] Press Ctrl+C in this terminal window to stop the app.\n")

    # Start browser opener in background thread — waits for server socket to be ready
    b_thread = threading.Thread(target=open_browser, args=(f"http://localhost:{port}", 0.5), daemon=True)
    b_thread.start()

    # Run HTTP Server on main thread
    run_server(port)

if __name__ == "__main__":
    main()
