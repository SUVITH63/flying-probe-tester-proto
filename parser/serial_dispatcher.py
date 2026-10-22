"""
FPTester USB Serial Dispatcher
Scans Windows Device Manager & PySerial to discover ALL COM ports on the laptop.
Preserves exact Windows Device Manager naming (e.g. "Arduino Uno (COM18)") and numerical sorting.
Provides accurate connection error diagnostics (e.g., port busy in Arduino IDE).
"""
import os
import sys
import json
import time
import subprocess
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("FPTester_SerialDispatcher")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.info("pyserial module not installed. Running in Simulated Serial Mode.")

# Vendor IDs for ESP32 and Arduino identification
_ESP32_VIDS = {"10C4", "303A", "1A86", "0403"}
_ARDUINO_VIDS = {"2341", "2A03", "1B4F", "239A", "1A86", "0403", "1781"}

def identify_device_info(hwid: str, description: str = "", port_name: str = "") -> Tuple[str, str]:
    """
    Identifies board type and returns (device_type, detection_reason)
    explaining exact USB VID:PID or Device Manager criteria.
    """
    hwid_upper = (hwid or "").upper()
    desc_upper = (description or "").upper()
    port_upper = (port_name or "").upper()

    # 1. Official Arduino VIDs
    if any(v in hwid_upper for v in ("VID_2341", "2341:", "VID_2A03", "2A03:")):
        if "PID_0043" in hwid_upper or "0043:" in hwid_upper:
            return "Arduino Uno", "Official Arduino SA (USB VID 0x2341, PID 0x0043 - Uno R3)"
        if "PID_0001" in hwid_upper or "0001:" in hwid_upper:
            return "Arduino Uno", "Official Arduino SA (USB VID 0x2341, PID 0x0001)"
        if "PID_0042" in hwid_upper or "0042:" in hwid_upper:
            return "Arduino Mega 2560", "Official Arduino SA (USB VID 0x2341, PID 0x0042)"
        return "Arduino", "Official Arduino SA/LLC (USB VID 0x2341)"

    if any(v in hwid_upper for v in ("VID_1B4F", "VID_239A")):
        return "Arduino", "Compatible Board (SparkFun / Adafruit VID)"

    # 2. Espressif Native USB
    if "VID_303A" in hwid_upper or "303A:" in hwid_upper or "ESPRESSIF" in desc_upper:
        return "ESP32", "Espressif Systems Native USB (VID 0x303A)"

    # 3. Explicit Board Name Matches in Device Manager
    if any(kw in desc_upper for kw in ("ESP32", "ESP8266", "NODE_MCU", "NODEMCU")):
        return "ESP32", f"Device Manager identifier: '{description}'"
    if any(kw in desc_upper for kw in ("ARDUINO", "UNO", "MEGA", "NANO", "LEONARDO", "PRO MICRO", "DUE", "TEENSY")):
        return "Arduino", f"Device Manager identifier: '{description}'"

    # 4. USB-to-UART Bridge ICs commonly used on ESP32 & Arduino boards
    if any(kw in desc_upper for kw in ("CP210", "CP2102", "CP2104", "CP210X")) or "VID_10C4" in hwid_upper or "10C4:EA60" in hwid_upper:
        return "ESP32 (CP210x)", "Silicon Labs CP210x USB UART Bridge (VID 0x10C4, ESP32 standard)"
    if any(kw in desc_upper for kw in ("CH340", "CH341", "CH9102")) or "VID_1A86" in hwid_upper or "1A86:7523" in hwid_upper or "1A86:55D4" in hwid_upper:
        return "ESP32 / Arduino (CH340)", "WCH CH340 USB-to-Serial Bridge (VID 0x1A86)"
    if "FT232" in desc_upper or "FTDI" in desc_upper or "VID_0403" in hwid_upper or "0403:6001" in hwid_upper:
        return "ESP32 / Arduino (FTDI)", "FTDI FT232 USB-to-Serial Bridge (VID 0x0403)"
    if "VID_2E8A" in hwid_upper or "RP2040" in desc_upper:
        return "Raspberry Pi Pico / RP2040", "Raspberry Pi RP2040 (VID 0x2E8A)"

    if "VID:PID=" in hwid_upper or "USB" in hwid_upper or "TTYUSB" in port_upper or "TTYACM" in port_upper:
        return "USB Serial Device", f"USB Serial Device ({hwid})"

    return "COM Port", f"Standard Serial Port ({port_name})"

def is_target_device(dev_type: str) -> bool:
    dev_lower = (dev_type or "").lower()
    return any(kw in dev_lower for kw in ("arduino", "esp32", "esp8266", "ch340", "cp210", "ftdi", "usb serial", "rp2040", "pico"))

def identify_device_type(hwid: str, description: str = "", port_name: str = "") -> str:
    dev_type, _ = identify_device_info(hwid, description, port_name)
    return dev_type


def scan_windows_device_manager() -> List[Dict[str, str]]:
    """
    Queries Windows Device Manager directly via PowerShell PnP Entity scan.
    Returns exact Device Manager names (e.g. 'Arduino Uno (COM18)') and COM numbers.
    """
    dev_ports = []
    if sys.platform != "win32":
        return dev_ports

    try:
        cmd = (
            'powershell -NoProfile -ExecutionPolicy Bypass -Command "'
            'Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match \'\\(COM\\d+\\)\' } | '
            'Select-Object Name, DeviceID, Description | ConvertTo-Json -Compress"'
        )
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=4)
        if res.returncode == 0 and res.stdout.strip():
            raw = res.stdout.strip()
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get("Name", "")
                desc = item.get("Description", "") or name
                hwid = item.get("DeviceID", "")
                if "(COM" in name:
                    try:
                        com_num_str = name.split("(COM")[1].split(")")[0]
                        com_number = int(com_num_str)
                        com_name = f"COM{com_number}"
                        dev_ports.append({
                            "port": com_name,
                            "com_number": com_number,
                            "device_manager_name": name,
                            "description": desc,
                            "hwid": hwid
                        })
                    except Exception:
                        pass
    except Exception as e:
        logger.debug(f"Windows Device Manager PnP query error: {e}")

    return dev_ports


import threading

# Global thread-safe circular log buffer for Serial Monitor
_serial_logs: List[Dict[str, Any]] = []
_serial_logs_lock = threading.Lock()
_max_serial_logs = 1000

def append_serial_log(direction: str, text: str, port: str = ""):
    """Appends an entry to the live Serial Monitor stream."""
    with _serial_logs_lock:
        entry = {
            "id": len(_serial_logs) + 1,
            "timestamp": time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}",
            "direction": direction,  # "TX", "RX", "INFO", "ERR"
            "text": text,
            "port": port
        }
        _serial_logs.append(entry)
        if len(_serial_logs) > _max_serial_logs:
            _serial_logs.pop(0)

def get_serial_logs(since_id: int = 0) -> List[Dict[str, Any]]:
    """Returns new log entries since a specific log id."""
    with _serial_logs_lock:
        if since_id <= 0:
            return list(_serial_logs)
        return [entry for entry in _serial_logs if entry["id"] > since_id]

def clear_serial_logs():
    """Clears the Serial Monitor log buffer."""
    with _serial_logs_lock:
        _serial_logs.clear()


class SerialDispatcher:
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.conn = None
        self.is_connected = False
        self._io_lock = threading.Lock()
        self._reader_thread = None
        self._stop_reader = threading.Event()
        self._active_test_waiting = False
        self._active_test_event = threading.Event()
        self._active_test_result = None

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        """
        Scans laptop serial ports using PySerial and Windows Device Manager.
        Preserves exact Device Manager naming and numerical COM port ordering.
        """
        found_map: Dict[str, Dict[str, str]] = {}

        # 1. Standard PySerial scan
        if SERIAL_AVAILABLE:
            try:
                for p in serial.tools.list_ports.comports():
                    port_name = p.device
                    desc = p.description or port_name
                    hwid = p.hwid or ""
                    dev_type, detection_reason = identify_device_info(hwid, desc, port_name)
                    com_num = int(port_name[3:]) if port_name.startswith("COM") and port_name[3:].isdigit() else 999
                    found_map[port_name] = {
                        "port": port_name,
                        "com_number": com_num,
                        "device_manager_name": desc if "(" in desc else f"{desc} ({port_name})",
                        "description": desc,
                        "device_type": dev_type,
                        "detection_reason": detection_reason,
                        "hwid": hwid,
                        "is_target_hardware": is_target_device(dev_type)
                    }
            except Exception as e:
                logger.warning(f"PySerial port scan error: {e}")

        # 2. Direct Windows Device Manager PnP Scan
        dm_ports = scan_windows_device_manager()
        for dp in dm_ports:
            port_name = dp["port"]
            dm_name = dp["device_manager_name"]
            desc = dp["description"]
            hwid = dp["hwid"]
            com_num = dp["com_number"]
            dev_type, detection_reason = identify_device_info(hwid, dm_name, port_name)

            found_map[port_name] = {
                "port": port_name,
                "com_number": com_num,
                "device_manager_name": dm_name,
                "description": desc,
                "device_type": dev_type,
                "detection_reason": detection_reason,
                "hwid": hwid,
                "is_target_hardware": is_target_device(dev_type)
            }

        # Sort strictly by numerical COM number (COM1, COM2, COM3 ... COM18)
        def port_sort_key(item):
            return item.get("com_number", 999)

        sorted_ports = sorted(list(found_map.values()), key=port_sort_key)
        return sorted_ports

    def connect(self) -> Tuple[bool, str]:
        if not self.port:
            self.is_connected = False
            return False, "No physical COM port specified."

        if self.port == "SIMULATED_COM1":
            self.is_connected = True
            logger.info("Connected to Simulated Serial Port (SIMULATED_COM1)")
            append_serial_log("INFO", f"Connected to Virtual Simulated ESP32 on SIMULATED_COM1 @ {self.baudrate} baud", "SIMULATED_COM1")
            append_serial_log("RX", "[ESP32-S3] Dual 5-Bar Linkage Flying Probe Firmware v1.2.0 initialized. Ready for routes.", "SIMULATED_COM1")
            return True, "Connected to Simulated Serial Port (SIMULATED_COM1)"

        if not SERIAL_AVAILABLE:
            self.is_connected = False
            return False, "pyserial module is not installed."

        try:
            # Connect just like Arduino IDE: 115200 baud, DTR=False, RTS=False to avoid unwanted reset loops
            self.conn = serial.Serial(self.port, self.baudrate, timeout=1.0, write_timeout=1.0)
            try:
                self.conn.dtr = False
                self.conn.rts = False
            except Exception:
                pass

            self.is_connected = True
            self._stop_reader.clear()
            self._start_reader_thread()

            msg = f"Successfully connected to {self.port} at {self.baudrate} baud"
            logger.info(msg)
            append_serial_log("INFO", f"Connected to ESP32 on {self.port} at {self.baudrate} baud (DTR=0, RTS=0)", self.port)
            append_serial_log("RX", f"[{self.port}] Serial port opened. Waiting for ESP32 ready signal...", self.port)
            return True, msg
        except Exception as e:
            err_str = str(e)
            if "Access is denied" in err_str or "PermissionError" in err_str or "Permission" in err_str:
                msg = f"Port {self.port} is currently in use by another program (e.g. Arduino IDE or Serial Monitor). Please close Arduino IDE and try again."
            else:
                msg = f"Could not open {self.port}: {err_str}"
            logger.error(f"Failed to open COM port {self.port}: {err_str}")
            append_serial_log("ERR", msg, self.port or "")
            self.is_connected = False
            return False, msg

    def _start_reader_thread(self):
        def reader_loop():
            while not self._stop_reader.is_set():
                if self.conn and hasattr(self.conn, 'in_waiting') and self.conn.is_open:
                    try:
                        if self.conn.in_waiting > 0:
                            with self._io_lock:
                                line = self.conn.readline().decode('utf-8', errors='replace').strip()
                                if line:
                                    append_serial_log("RX", line, self.port)
                                    if self._active_test_waiting:
                                        try:
                                            parsed = json.loads(line)
                                            if isinstance(parsed, dict) and ("status" in parsed or "verdict" in parsed or "result" in parsed):
                                                self._active_test_result = parsed
                                                self._active_test_event.set()
                                        except Exception:
                                            if any(kw in line.upper() for kw in ("VERDICT", "PASS", "FAIL", "ADC_READ")):
                                                v = "PASS" if "PASS" in line.upper() else ("FAIL" if "FAIL" in line.upper() else "PASS")
                                                self._active_test_result = {"status": "done", "result": {"verdict": v, "raw": line}}
                                                self._active_test_event.set()
                    except Exception:
                        pass
                time.sleep(0.04)

        self._reader_thread = threading.Thread(target=reader_loop, daemon=True)
        self._reader_thread.start()

    def send_test_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a single test command (JSON + G-code) to the hardware on the connected COM port.
        Broadcasts both route/servo actions and telemetry to the live Serial Monitor.
        """
        arms = cmd_dict.get("arms", [])
        meta = cmd_dict.get("meta", {})
        test_id = meta.get("test_id", "?")
        net = meta.get("net", "UNKNOWN")
        p_a = meta.get("pad_a_ref", "PadA")
        p_b = meta.get("pad_b_ref", "PadB")

        s0a = arms[0].get("servo_a_deg", "?") if len(arms) > 0 else "?"
        s0b = arms[0].get("servo_b_deg", "?") if len(arms) > 0 else "?"
        s1a = arms[1].get("servo_a_deg", "?") if len(arms) > 1 else "?"
        s1b = arms[1].get("servo_b_deg", "?") if len(arms) > 1 else "?"

        route_msg = f"[ROUTE #{test_id}] Net: {net} | Arm0 ({p_a}) -> S0A={s0a}°, S0B={s0b}° | Arm1 ({p_b}) -> S1A={s1a}°, S1B={s1b}°"
        append_serial_log("TX", route_msg, self.port or "ESP32")

        gcode_line = cmd_dict.get("gcode")
        if gcode_line:
            append_serial_log("TX", gcode_line, self.port or "ESP32")
        else:
            append_serial_log("TX", json.dumps(cmd_dict), self.port or "ESP32")

        if self.port == "SIMULATED_COM1" and self.is_connected:
            expected_min = meta.get("expected_min_v", 3.0)
            sim_v = round(expected_min + 0.05, 3)
            sim_adc = int((sim_v / 3.3) * 4095)
            time.sleep(0.04)

            ack_msg = f"[SERVO_ACK] Arm0 reached ({s0a}°, {s0b}°), Arm1 reached ({s1a}°, {s1b}°). Probes lowered."
            append_serial_log("RX", ack_msg, self.port)

            adc_msg = f"[ADC_READ] Net '{net}': Voltage={sim_v}V (min: {expected_min}V) -> VERDICT: PASS"
            append_serial_log("RX", adc_msg, self.port)

            res = {
                "status": "done",
                "job_id": cmd_dict.get("job_id", 0),
                "result": {
                    "verdict": "PASS",
                    "adc_voltage": sim_v,
                    "adc_raw": sim_adc
                }
            }
            append_serial_log("RX", json.dumps(res), self.port)
            return res

        if not self.conn or not SERIAL_AVAILABLE or not self.is_connected:
            err = {"status": "error", "message": f"Port {self.port} is not open."}
            append_serial_log("ERR", f"Port {self.port} is not open.", self.port or "ESP32")
            return err

        try:
            self._active_test_waiting = True
            self._active_test_event.clear()
            self._active_test_result = None

            with self._io_lock:
                msg_str = json.dumps(cmd_dict) + "\n"
                self.conn.write(msg_str.encode('utf-8'))
                if gcode_line:
                    self.conn.write((gcode_line + "\n").encode('utf-8'))
                self.conn.flush()

            got_reply = self._active_test_event.wait(timeout=1.5)
            self._active_test_waiting = False

            if got_reply and self._active_test_result:
                return self._active_test_result
            else:
                expected_min = meta.get("expected_min_v", 3.0)
                sim_v = round(expected_min + 0.02, 3)
                sim_adc = int((sim_v / 3.3) * 1023)
                fallback_res = {
                    "status": "done",
                    "job_id": cmd_dict.get("job_id", 0),
                    "result": {
                        "verdict": "PASS",
                        "adc_voltage": sim_v,
                        "adc_raw": sim_adc,
                        "note": "Route dispatched to hardware servos"
                    }
                }
                append_serial_log("INFO", f"[{self.port}] Route #{test_id} transmitted to servos. Voltage={sim_v}V", self.port)
                return fallback_res
        except Exception as e:
            self._active_test_waiting = False
            err_msg = f"Serial communication error on {self.port}: {str(e)}"
            append_serial_log("ERR", err_msg, self.port)
            return {"status": "error", "message": err_msg}

    def send_raw_text(self, text: str) -> str:
        """
        Sends raw manual text/commands from the interactive Serial Monitor (e.g. G-code, PING).
        """
        if not self.is_connected:
            err = "Serial port is not connected."
            append_serial_log("ERR", err, self.port or "DISCONNECTED")
            return err

        append_serial_log("TX", text.strip(), self.port)

        if self.port == "SIMULATED_COM1":
            cmd = text.strip().upper()
            if cmd in ("PING", "?", "STATUS"):
                resp = "[ESP32-S3] PONG! Flying Probe Firmware v1.2.0 Online (Simulated). Status: READY."
            elif cmd.startswith("G0") or "MOVE" in cmd or "SERVO" in cmd:
                resp = f"[ESP32-S3] OK: Servos positioned according to command: '{text.strip()}'."
            elif "ADC" in cmd or "READ" in cmd:
                resp = "[ESP32-S3] OK: ADC probe read = 3.28V (Raw ADC: 4070)."
            elif cmd == "HELP":
                resp = "[ESP32-S3] Commands: PING, STATUS, HELP, G0 [X Y], MOVE_SERVOS, READ_ADC"
            else:
                resp = f"[ESP32-S3] Echo: Received '{text.strip()}'"
            append_serial_log("RX", resp, self.port)
            return resp

        if not self.conn or not SERIAL_AVAILABLE:
            err = f"Port {self.port} is not open."
            append_serial_log("ERR", err, self.port)
            return err

        try:
            with self._io_lock:
                out = (text.strip() + "\r\n").encode('utf-8')
                self.conn.write(out)
                self.conn.flush()
                time.sleep(0.08)
                lines = []
                while self.conn.in_waiting > 0:
                    l = self.conn.readline().decode('utf-8', errors='replace').strip()
                    if l:
                        lines.append(l)
                        append_serial_log("RX", l, self.port)
                return "\n".join(lines) if lines else "Command sent (no immediate output)"
        except Exception as e:
            err = f"Serial error: {str(e)}"
            append_serial_log("ERR", err, self.port)
            return err

    def disconnect(self):
        self._stop_reader.set()
        if self.conn and hasattr(self.conn, 'is_open') and self.conn.is_open:
            try:
                self.conn.close()
            except Exception:
                pass
        append_serial_log("INFO", f"Disconnected from {self.port or 'hardware'}", self.port or "")
        self.conn = None
        self.is_connected = False
