#!/usr/bin/env python3
"""
FPTester Standalone Cross-Platform Application Launcher
Runs natively on Windows, macOS, and Linux without requiring pip install or external dependencies.
"""
import os
import sys

# Ensure current script directory is at the head of sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import socket
import threading
import webbrowser
from pcb_api_server import run_server

def open_browser(port, delay=0.5):
    time.sleep(delay)
    url = f"http://localhost:{port}"
    # Wait until the HTTP server is listening on bound_port before launching browser
    for _ in range(50):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.3)
            s.close()
            break
        except Exception:
            time.sleep(0.2)
    try:
        webbrowser.open(url)
    except Exception:
        print(f"[!] Note: Please open {url} manually in your web browser.")

def main():
    print("=" * 65)
    print("   FPTester — Automated Flying Probe PCB Tester Web App")
    print("=" * 65)

    # Bind HTTP Server to port (8000 or fallback if busy)
    httpd, port = run_server(8000)

    print(f"[*] FPTester Web App Server ONLINE at http://localhost:{port}")
    print("[*] Compatible with Windows, macOS, and Linux.")
    print("[*] Press Ctrl+C in this terminal window to stop the app.\n")

    # Start browser opener in background thread — waits for server socket to be ready
    b_thread = threading.Thread(target=open_browser, args=(port, 0.5), daemon=True)
    b_thread.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] FPTester Server stopped by user.")

if __name__ == "__main__":
    main()
