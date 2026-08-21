# FPTester

> **Automated Flying Probe PCB Evaluation & Kinematics Engine**

![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-orange?style=flat-square)
![Release](https://img.shields.io/badge/Release-v1.2.0-brightgreen?style=flat-square)

**FPTester** is an automated dual-arm flying probe PCB evaluation application. It parses KiCad (`.kicad_pcb`) and Gerber (`.gbr`) design files, generates AI-powered hardware-ready test plan sequences, and provides a 2D dual 5-bar linkage kinematics visualizer. Now with **automatic ESP32 & Arduino hardware detection and connection**.

---

## 💾 1-Click Standalone Direct Downloads (No Unzipping Required!)

Click below to download the single-file executable for your OS. **No unzipping or manual extraction needed — just click and launch!**

<div align="center">

| Operating System | Single-File 1-Click Download | How to Run |
| :---: | :---: | :---: |
| 🍎 **macOS** | [⬇ **Download FPTester-macOS**](https://github.com/SUVITH63/flying-probe-tester-proto/releases/download/v1.2.0/FPTester-macOS) | Single click / executable |
| 🪟 **Windows** | [⬇ **Download FPTester-Windows.bat**](https://github.com/SUVITH63/flying-probe-tester-proto/releases/download/v1.2.0/FPTester-Windows.bat) | Direct 1-Click `.bat` |

</div>

> 🍎 **macOS Gatekeeper Tip**: If macOS blocks execution on first click, right-click `FPTester-macOS` → select **Open** → click **Open Anyway**. Or run `chmod +x FPTester-macOS`.

> 🪟 **Windows Tip**: If SmartScreen appears, click **More info** → **Run anyway**.

---

## 🔌 What's New in v1.2.0 — Hardware Auto-Connect

Plug in your **ESP32 or Arduino** and the app connects **automatically** — no configuration needed.

| Feature | Description |
|---------|-------------|
| 🔴→🟢 **Live Status Pill** | Animated DISCONNECTED → CONNECTING → HARDWARE CONNECTED indicator |
| ⚡ **Auto-Detect** | Detects new USB device within 2 seconds and connects automatically |
| 🔬 **Run on Hardware** | Send full AI test plan to real ESP32/Arduino over USB serial |
| 🔔 **Toast Alerts** | Slide-up notifications for connect/disconnect events |
| 🔁 **Auto-Revert** | Unplug the device → silently falls back to simulation mode |

**Supported Devices:**
- **ESP32** — Silicon Labs CP210x, Espressif native USB, CH340
- **Arduino** — Uno, Mega, Nano, Leonardo, Pro Micro (FTDI / Arduino SA)

---

## ✨ Key Features

- **AI Test Plan Engine**: Local Ollama, Google Gemini, or OpenAI GPT-4o for generating probe sequences
- **Universal PCB Parser**: KiCad `.kicad_pcb` and Gerber `.gbr` file support
- Republic 2D Dual 5-Bar Kinematics Visualizer: Real-time inverse kinematics with drag-and-drop flex handles
- **Hardware & Simulation**: ESP32/Arduino USB serial dispatch + laptop simulation mode
- **Zero External Dependencies**: Native Python HTTP server, no pip installs needed

---

## 🚀 Running from Source

```bash
git clone https://github.com/SUVITH63/flying-probe-tester-proto.git
cd flying-probe-tester-proto

# Launch the application (opens browser automatically)
python3 run_app.py
```

App opens automatically at **http://localhost:8000**

---

## 📦 All Releases

[View all releases →](https://github.com/SUVITH63/flying-probe-tester-proto/releases)
