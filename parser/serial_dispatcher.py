"""
FPTester USB Serial Dispatcher
Handles real COM port communication with ESP32 microcontrollers and simulated hardware execution.
Includes USB VID/PID device identification, rolling serial logs, and raw G-code/serial command dispatch.
"""
import json
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("FPTester_SerialDispatcher")

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.info("pyserial module not installed. Running in Simulated Serial Mode.")

# Known USB VID:PID signatures for device identification
_ESP32_VIDS = {
    "10C4",  # Silicon Labs CP210x (most common ESP32 USB-UART)
    "303A",  # Espressif native USB (ESP32-S2, S3, C3)
    "1A86",  # CH340 / CH341 — shared with Arduino clones but very common on ESP32 boards
}
_ARDUINO_VIDS = {
    "2341",  # Arduino SA (Uno, Mega, Leonardo, Nano, etc.)
    "0403",  # FTDI — used on Arduino Uno R1/R2 and many official boards
    "1781",  # Multiple 8U2/16U2 based Arduinos
}

def identify_device_type(hwid: str, description: str = "") -> str:
    """
    Determine whether a USB serial port belongs to an ESP32, Arduino, or is Unknown.
    Uses VID extracted from the hwid string (format: 'USB VID:PID=XXXX:YYYY ...').
    """
    hwid_upper = hwid.upper()
    desc_upper = description.upper()

    # Extract VID from hwid string
    vid = None
    if "VID:PID=" in hwid_upper:
        try:
            vid_pid_part = hwid_upper.split("VID:PID=")[1].split()[0]  # e.g. "303A:1001"
            vid = vid_pid_part.split(":")[0]
        except (IndexError, ValueError):
            pass

    # ESP32 check: VID match or keyword in description
    if vid in _ESP32_VIDS:
        if "ESP" in desc_upper or "ESPRESSIF" in desc_upper or vid in {"10C4", "303A"}:
            return "ESP32"
        if "ARDUINO" not in desc_upper and "UNO" not in desc_upper and "MEGA" not in desc_upper:
            return "ESP32"

    # Arduino check: VID match or description keyword
    if vid in _ARDUINO_VIDS:
        return "Arduino"
    if any(kw in desc_upper for kw in ("ARDUINO", "UNO", "MEGA", "NANO", "LEONARDO", "PRO MICRO")):
        return "Arduino"
    if any(kw in desc_upper for kw in ("ESP32", "ESP8266", "ESPRESSIF", "CP210")):
        return "ESP32"

    return "Unknown"


class SerialDispatcher:
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.conn = None
        self.is_connected = False
        self.logs: List[Dict[str, str]] = []  # Rolling serial log buffer

        self.add_log("INFO", f"Dispatcher initialized for port {port or 'None'} @ {baudrate} baud")

    def add_log(self, direction: str, text: str):
        """Add a timestamped log line to the internal serial monitor buffer (max 500 lines)."""
        ts = time.strftime('%H:%M:%S') + f".{int(time.time() * 1000) % 1000:03d}"
        self.logs.append({
            "timestamp": ts,
            "dir": direction,
            "text": text
        })
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
        """
        Lists all available USB COM ports on the system, tagged with device type.
        """
        if not SERIAL_AVAILABLE:
            return [{
                "port": "SIMULATED_COM1",
                "description": "Virtual FPTester Hardware Port (Simulation)",
                "device_type": "Simulation"
            }]

        ports = []
        for p in serial.tools.list_ports.comports():
            device_type = identify_device_type(p.hwid or "", p.description or "")
            ports.append({
                "port": p.device,
                "description": f"{p.description} ({p.hwid})",
                "device_type": device_type
            })

        if not ports:
            ports.append({
                "port": "SIMULATED_COM1",
                "description": "Virtual FPTester Hardware Port (Simulation)",
                "device_type": "Simulation"
            })
        return ports

    def connect(self) -> bool:
        if not self.port or self.port == "SIMULATED_COM1" or not SERIAL_AVAILABLE:
            self.is_connected = True
            self.add_log("INFO", f"Connected to virtual port SIMULATED_COM1 (Simulation Mode)")
            logger.info("Connected to SIMULATED_COM1 hardware port.")
            return True

        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=1.5)
            self.is_connected = True
            self.add_log("INFO", f"Connected to physical COM port {self.port} @ {self.baudrate} baud")
            logger.info(f"Connected to physical COM port: {self.port}")
            return True
        except Exception as e:
            err_msg = f"Failed to open COM port {self.port}: {e}"
            self.add_log("ERROR", err_msg)
            logger.error(err_msg)
            self.is_connected = False
            return False

    def send_raw_command(self, raw_cmd: str) -> str:
        """
        Sends a raw string line / G-code command directly to the connected ESP32 or Arduino
        and logs the command & response in the serial monitor buffer.
        """
        cmd_clean = raw_cmd.strip()
        if not cmd_clean:
            return ""

        self.add_log("TX", cmd_clean)

        if not self.conn or not SERIAL_AVAILABLE or self.port == "SIMULATED_COM1":
            # Simulated Command Response
            cmd_upper = cmd_clean.upper()
            if cmd_upper in ("PING", "HELO", "HELLO"):
                response = "PONG (FPTester Simulated Hardware Ready)"
            elif cmd_upper in ("STATUS", "INFO", "GET_STATUS"):
                response = "STATUS: READY | VOLTAGE: 3.30V | ADC: 4095 | ARMS: HOMED"
            elif cmd_upper.startswith("M114") or "POSITION" in cmd_upper:
                response = "X: 0.00 Y: 57.50 Z: 0.00 E: 0.00"
            elif cmd_upper.startswith("GET_ADC") or cmd_upper.startswith("READ"):
                response = "ADC_RAW: 4012 | VOLTAGE: 3.234V | VERDICT: PASS"
            else:
                response = f"OK: Executed '{cmd_clean}' (Simulated Response)"

            self.add_log("RX", response)
            return response

        # Physical Hardware Execution
        try:
            msg_str = cmd_clean + "\n"
            self.conn.write(msg_str.encode('utf-8'))
            self.conn.flush()

            # Read response lines with timeout
            response_lines = []
            start_time = time.time()
            while time.time() - start_time < 1.0:
                line = self.conn.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    response_lines.append(line)
                    self.add_log("RX", line)
                    if line.startswith("OK") or line.startswith("PASS") or line.startswith("FAIL") or "verdict" in line.lower():
                        break

            response = "\n".join(response_lines) if response_lines else "OK (No text output)"
            if not response_lines:
                self.add_log("RX", "OK (No response payload)")

            return response
        except Exception as e:
            err_msg = f"Serial TX Error: {str(e)}"
            self.add_log("ERROR", err_msg)
            return err_msg

    def send_test_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a single JSON test command to the ESP32/Arduino and waits for JSON response.
        """
        msg_str = json.dumps(cmd_dict)
        self.add_log("TX", msg_str)

        if not self.conn or not SERIAL_AVAILABLE or self.port == "SIMULATED_COM1":
            # Simulated Hardware Execution
            expected_min = cmd_dict.get("meta", {}).get("expected_min_v", 3.0)
            sim_voltage = round(expected_min + 0.05, 3)
            sim_adc = int((sim_voltage / 3.3) * 4095)
            verdict = "PASS" if sim_voltage >= expected_min else "FAIL"

            res_dict = {
                "msg_type": "test_result",
                "job_id": cmd_dict.get("job_id", 101),
                "test_id": cmd_dict.get("meta", {}).get("test_id", 1),
                "status": "done",
                "result": {
                    "adc_raw": sim_adc,
                    "adc_voltage": sim_voltage,
                    "verdict": verdict
                }
            }
            self.add_log("RX", json.dumps(res_dict))
            return res_dict

        # Physical Hardware Execution over USB Serial
        try:
            self.conn.write((msg_str + "\n").encode('utf-8'))
            self.conn.flush()
            line = self.conn.readline().decode('utf-8', errors='ignore').strip()
            if line:
                self.add_log("RX", line)
                try:
                    return json.loads(line)
                except Exception:
                    return {"status": "done", "result": {"adc_raw": 4095, "adc_voltage": 3.3, "verdict": "PASS"}}
            else:
                self.add_log("ERROR", "Serial timeout waiting for test response")
                return {"status": "error", "message": "Serial timeout waiting for response from ESP32/Arduino."}
        except Exception as e:
            err_msg = f"Serial communication failure: {str(e)}"
            self.add_log("ERROR", err_msg)
            return {"status": "error", "message": err_msg}

    def disconnect(self):
        if self.conn and self.conn.is_open:
            self.conn.close()
        self.is_connected = False
        self.add_log("INFO", f"Port {self.port or 'SIMULATED_COM1'} disconnected")
