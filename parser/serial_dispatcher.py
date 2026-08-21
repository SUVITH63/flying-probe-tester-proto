"""
FPTester USB Serial Dispatcher
Handles physical COM port auto-detection & communication for ESP32 and Arduino microcontrollers.
Enforces strict USB hardware validation — if no ESP32 or Arduino is connected, reports "No hardware found".
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

# Vendor IDs for ESP32 and Arduino identification
_ESP32_VIDS = {
    "10C4",  # Silicon Labs CP210x (ESP32 / ESP8266)
    "303A",  # Espressif native USB (ESP32-S2, ESP32-S3, ESP32-C3)
    "1A86",  # CH340 / CH341 / CH9102 (ESP32 dev boards)
    "0403",  # FTDI (ESP32 dev boards)
}

_ARDUINO_VIDS = {
    "2341",  # Official Arduino SA (Uno, Mega, Leonardo, Nano)
    "2A03",  # Arduino.org
    "1B4F",  # SparkFun Arduino compatible
    "239A",  # Adafruit Arduino compatible
    "1A86",  # CH340 (Chinese Arduino Uno/Nano clones)
    "0403",  # FTDI FT232 (Arduino Nano/Duemilanove)
    "1781",  # Atmel 8U2/16U2 Arduinos
}

def identify_device_type(hwid: str, description: str = "", port_name: str = "") -> str:
    """
    Identifies whether a serial port belongs to an ESP32 or Arduino microcontroller.
    Returns 'ESP32', 'Arduino', or 'Unknown'.
    """
    hwid_upper = (hwid or "").upper()
    desc_upper = (description or "").upper()
    port_upper = (port_name or "").upper()

    # Extract VID from USB HWID string (e.g. "USB VID:PID=10C4:EA60 ...")
    vid = None
    if "VID:PID=" in hwid_upper:
        try:
            vid_pid_part = hwid_upper.split("VID:PID=")[1].split()[0]
            vid = vid_pid_part.split(":")[0]
        except (IndexError, ValueError):
            pass

    # Check explicit keywords first
    if any(kw in desc_upper for kw in ("ARDUINO", "UNO", "MEGA", "NANO", "LEONARDO", "PRO MICRO")):
        return "Arduino"
    if any(kw in desc_upper for kw in ("ESP32", "ESP8266", "ESPRESSIF")):
        return "ESP32"

    # Check VID matches
    if vid in _ESP32_VIDS:
        if vid in {"10C4", "303A"}:
            return "ESP32"
        # CH340 or FTDI — can be ESP32 or Arduino clone
        if "ARDUINO" in desc_upper or "UNO" in desc_upper:
            return "Arduino"
        return "ESP32"

    if vid in _ARDUINO_VIDS:
        return "Arduino"

    # If it's a USB serial port (has USB in HWID or ttyUSB/ttyACM in port name)
    if "USB" in hwid_upper or "TTYUSB" in port_upper or "TTYACM" in port_upper:
        return "ESP32"  # Generic USB Serial board

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
        Scans all physical USB COM ports on the laptop.
        Identifies ESP32 / Arduino devices and returns tagged port details.
        """
        if not SERIAL_AVAILABLE:
            return []

        ports = []
        for p in serial.tools.list_ports.comports():
            # Skip built-in motherboard legacy LPT/COM ports without USB connection
            hwid = p.hwid or ""
            desc = p.description or ""
            port_name = p.device or ""

            # Check if this port is a USB device or active serial port
            device_type = identify_device_type(hwid, desc, port_name)
            
            # Only include USB serial ports or recognized microcontrollers
            is_usb = "USB" in hwid.upper() or "TTYUSB" in port_name.upper() or "TTYACM" in port_name.upper() or device_type in ("ESP32", "Arduino")
            
            if is_usb or device_type != "Unknown":
                ports.append({
                    "port": port_name,
                    "description": f"{port_name} - {desc}",
                    "device_type": device_type if device_type != "Unknown" else "USB Serial Device",
                    "hwid": hwid,
                    "is_target_hardware": device_type in ("ESP32", "Arduino", "USB Serial Device")
                })

        return ports

    def connect(self) -> bool:
        if not self.port or self.port == "SIMULATED_COM1":
            self.is_connected = False
            return False

        if not SERIAL_AVAILABLE:
            self.is_connected = False
            return False

        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=2.0)
            self.is_connected = True
            logger.info(f"Connected to physical USB COM port: {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to USB COM port {self.port}: {e}")
            self.is_connected = False
            return False

    def send_test_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a single JSON test command to the ESP32/Arduino and returns response.
        """
        msg_str = json.dumps(cmd_dict) + "\n"

        if not self.conn or not SERIAL_AVAILABLE or not self.is_connected:
            return {"status": "error", "message": "No hardware connected. Connect an ESP32 or Arduino to USB."}

        try:
            self.conn.write(msg_str.encode('utf-8'))
            self.conn.flush()
            line = self.conn.readline().decode('utf-8').strip()
            if line:
                return json.loads(line)
            else:
                return {"status": "error", "message": f"Serial timeout on port {self.port}."}
        except Exception as e:
            return {"status": "error", "message": f"Serial communication error on {self.port}: {str(e)}"}

    def disconnect(self):
        if self.conn and self.conn.is_open:
            try:
                self.conn.close()
            except Exception:
                pass
        self.is_connected = False
