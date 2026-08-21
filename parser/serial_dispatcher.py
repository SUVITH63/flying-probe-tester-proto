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

def identify_device_type(hwid: str, description: str = "", port_name: str = "") -> str:
    """
    Identifies whether a serial port belongs to an ESP32, Arduino, or USB Serial board.
    """
    hwid_upper = (hwid or "").upper()
    desc_upper = (description or "").upper()
    port_upper = (port_name or "").upper()

    if any(kw in desc_upper for kw in ("ARDUINO", "UNO", "MEGA", "NANO", "LEONARDO", "PRO MICRO")):
        return "Arduino"
    if any(kw in desc_upper for kw in ("ESP32", "ESP8266", "ESPRESSIF")):
        return "ESP32"
    if any(kw in desc_upper for kw in ("CP210", "CP2102", "CP210X")):
        return "ESP32 (CP210x)"
    if any(kw in desc_upper for kw in ("CH340", "CH341", "CH9102")):
        return "ESP32 / Arduino (CH340)"
    if "FT232" in desc_upper or "FTDI" in desc_upper:
        return "ESP32 / Arduino (FTDI)"
    if "VID:PID=" in hwid_upper or "USB" in hwid_upper or "TTYUSB" in port_upper or "TTYACM" in port_upper:
        return "USB Serial Device"

    return "COM Port"


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


class SerialDispatcher:
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.conn = None
        self.is_connected = False

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
                    dev_type = identify_device_type(hwid, desc, port_name)
                    com_num = int(port_name[3:]) if port_name.startswith("COM") and port_name[3:].isdigit() else 999
                    found_map[port_name] = {
                        "port": port_name,
                        "com_number": com_num,
                        "device_manager_name": desc if "(" in desc else f"{desc} ({port_name})",
                        "description": desc,
                        "device_type": dev_type,
                        "hwid": hwid,
                        "is_target_hardware": dev_type in ("ESP32", "Arduino", "ESP32 (CP210x)", "ESP32 / Arduino (CH340)", "ESP32 / Arduino (FTDI)", "USB Serial Device")
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
            dev_type = identify_device_type(hwid, dm_name, port_name)

            found_map[port_name] = {
                "port": port_name,
                "com_number": com_num,
                "device_manager_name": dm_name,
                "description": desc,
                "device_type": dev_type,
                "hwid": hwid,
                "is_target_hardware": True
            }

        # Sort strictly by numerical COM number (COM1, COM2, COM3 ... COM18)
        def port_sort_key(item):
            return item.get("com_number", 999)

        sorted_ports = sorted(list(found_map.values()), key=port_sort_key)
        return sorted_ports

    def connect(self) -> Tuple[bool, str]:
        if not self.port or self.port == "SIMULATED_COM1":
            self.is_connected = False
            return False, "No physical COM port specified."

        if not SERIAL_AVAILABLE:
            self.is_connected = False
            return False, "pyserial module is not installed."

        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=2.0)
            self.is_connected = True
            logger.info(f"Successfully opened physical COM port: {self.port} at {self.baudrate} baud")
            return True, f"Successfully connected to {self.port}"
        except Exception as e:
            err_str = str(e)
            if "Access is denied" in err_str or "PermissionError" in err_str or "Permission" in err_str:
                msg = f"Port {self.port} is currently in use by another program (e.g. Arduino IDE or Serial Monitor). Please close Arduino IDE and try again."
            else:
                msg = f"Could not open {self.port}: {err_str}"
            logger.error(f"Failed to open COM port {self.port}: {err_str}")
            self.is_connected = False
            return False, msg

    def send_test_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a single JSON test command to the hardware on the connected COM port.
        """
        msg_str = json.dumps(cmd_dict) + "\n"

        if not self.conn or not SERIAL_AVAILABLE or not self.is_connected:
            return {"status": "error", "message": f"Port {self.port} is not open."}

        try:
            self.conn.write(msg_str.encode('utf-8'))
            self.conn.flush()
            line = self.conn.readline().decode('utf-8').strip()
            if line:
                return json.loads(line)
            else:
                return {"status": "error", "message": f"Timeout waiting for response from {self.port}."}
        except Exception as e:
            return {"status": "error", "message": f"Serial communication error on {self.port}: {str(e)}"}

    def disconnect(self):
        if self.conn and self.conn.is_open:
            try:
                self.conn.close()
            except Exception:
                pass
        self.is_connected = False
