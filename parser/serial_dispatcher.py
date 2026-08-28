"""
FPTester USB Serial Dispatcher
Handles real COM port communication with ESP32 microcontrollers and simulated hardware execution.
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
        # Distinguish ESP32 from Arduino CH340 by description keywords
        if "ESP" in desc_upper or "ESPRESSIF" in desc_upper or vid in {"10C4", "303A"}:
            return "ESP32"
        # CH340 could be either; prefer ESP32 label if no Arduino keyword
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
            logger.info("Connected to SIMULATED_COM1 hardware port.")
            return True

        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=2.0)
            self.is_connected = True
            logger.info(f"Connected to physical COM port: {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to COM port {self.port}: {e}")
            self.is_connected = False
            return False

    def send_test_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a single JSON test command to the ESP32/Arduino and waits for JSON response.
        """
        msg_str = json.dumps(cmd_dict) + "\n"

        if not self.conn or not SERIAL_AVAILABLE or self.port == "SIMULATED_COM1":
            # Simulated Hardware Execution (Instant response for fast simulation)
            expected_min = cmd_dict.get("meta", {}).get("expected_min_v", 3.0)
            sim_voltage = round(expected_min + 0.05, 3)
            sim_adc = int((sim_voltage / 3.3) * 4095)

            return {
                "msg_type": "test_result",
                "job_id": cmd_dict.get("job_id", 101),
                "test_id": cmd_dict.get("meta", {}).get("test_id", 1),
                "status": "done",
                "result": {
                    "adc_raw": sim_adc,
                    "adc_voltage": sim_voltage,
                    "verdict": "PASS" if sim_voltage >= expected_min else "FAIL"
                }
            }

        # Physical Hardware Execution over USB Serial
        try:
            self.conn.write(msg_str.encode('utf-8'))
            self.conn.flush()
            line = self.conn.readline().decode('utf-8').strip()
            if line:
                return json.loads(line)
            else:
                return {"status": "error", "message": "Serial timeout waiting for response from ESP32/Arduino."}
        except Exception as e:
            return {"status": "error", "message": f"Serial communication failure: {str(e)}"}

    def disconnect(self):
        if self.conn and self.conn.is_open:
            self.conn.close()
        self.is_connected = False
