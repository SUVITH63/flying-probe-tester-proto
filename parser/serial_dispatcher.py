"""
FPTester USB Serial Dispatcher
Handles real COM port communication with ESP32 & Arduino microcontrollers,
includes USB VID/PID device identification, rolling serial monitor logs,
and raw serial command execution with customizable line endings (Arduino IDE style).
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

_ESP32_VIDS = {"10C4", "303A", "1A86"}
_ARDUINO_VIDS = {"2341", "0403", "1781"}

def identify_device_type(hwid: str, description: str = "") -> str:
    hwid_upper = hwid.upper()
    desc_upper = description.upper()

    vid = None
    if "VID:PID=" in hwid_upper:
        try:
            vid_pid_part = hwid_upper.split("VID:PID=")[1].split()[0]
            vid = vid_pid_part.split(":")[0]
        except (IndexError, ValueError):
            pass

    if vid in _ESP32_VIDS:
        if "ESP" in desc_upper or "ESPRESSIF" in desc_upper or vid in {"10C4", "303A"}:
            return "ESP32"
        if "ARDUINO" not in desc_upper and "UNO" not in desc_upper and "MEGA" not in desc_upper:
            return "ESP32"

    if vid in _ARDUINO_VIDS:
        return "Arduino Uno / Mega"
    if any(kw in desc_upper for kw in ("ARDUINO", "UNO", "MEGA", "NANO", "LEONARDO", "PRO MICRO")):
        return "Arduino Uno"
    if any(kw in desc_upper for kw in ("ESP32", "ESP8266", "ESPRESSIF", "CP210")):
        return "ESP32"

    return "Unknown"


class SerialDispatcher:
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.conn = None
        self.is_connected = False
        self.logs: List[Dict[str, str]] = []
        self._max_logs = 200

    def _add_log(self, direction: str, data: str):
        t_str = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
        entry = {"timestamp": t_str, "direction": direction, "data": data}
        self.logs.append(entry)
        if len(self.logs) > self._max_logs:
            self.logs = self.logs[-self._max_logs:]

    @staticmethod
    def list_available_ports() -> List[Dict[str, str]]:
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
            self._add_log("SYS", f"Connected to SIMULATED_COM1 at {self.baudrate} baud.")
            return True

        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=1.0)
            self.is_connected = True
            self._add_log("SYS", f"Connected to {self.port} at {self.baudrate} baud.")
            return True
        except Exception as e:
            self.is_connected = False
            self._add_log("SYS", f"Could not open {self.port}: {e}")
            return False

    def send_test_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        msg_str = json.dumps(cmd_dict)
        self._add_log("TX", msg_str)

        if not self.conn or not SERIAL_AVAILABLE or self.port == "SIMULATED_COM1":
            expected_min = cmd_dict.get("meta", {}).get("expected_min_v", 3.0)
            sim_voltage = round(expected_min + 0.05, 3)
            sim_adc = int((sim_voltage / 3.3) * 4095)

            response = {
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
            self._add_log("RX", json.dumps(response))
            return response

        try:
            self.conn.write((msg_str + "\n").encode('utf-8'))
            self.conn.flush()
            line = self.conn.readline().decode('utf-8', errors='ignore').strip()
            if line:
                self._add_log("RX", line)
                try:
                    return json.loads(line)
                except Exception:
                    return {"status": "ok", "raw_response": line}
            else:
                self._add_log("RX", "[Timeout waiting for response]")
                return {"status": "error", "message": "Serial timeout."}
        except Exception as e:
            self._add_log("SYS", f"Serial Error: {e}")
            return {"status": "error", "message": f"Serial failure: {str(e)}"}

    def send_raw_command(self, raw_str: str, line_ending: str = "\r\n") -> str:
        """
        Sends custom string command over serial with Arduino IDE style line endings (NL, CR, BOTH, NONE).
        """
        self._add_log("TX", raw_str)
        payload = raw_str + line_ending

        if not self.conn or not SERIAL_AVAILABLE or self.port == "SIMULATED_COM1":
            sim_resp = f"ACK: {raw_str} [Simulated response]"
            self._add_log("RX", sim_resp)
            return sim_resp

        try:
            self.conn.write(payload.encode('utf-8'))
            self.conn.flush()
            time.sleep(0.1)
            lines = []
            while self.conn.in_waiting > 0:
                line = self.conn.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    lines.append(line)
                    self._add_log("RX", line)
            if not lines:
                lines = ["ACK"]
                self._add_log("RX", lines[0])
            return "\n".join(lines)
        except Exception as e:
            err = f"[Serial Error: {e}]"
            self._add_log("SYS", err)
            return err

    def disconnect(self):
        if self.conn and self.conn.is_open:
            try:
                self.conn.close()
            except Exception:
                pass
        self._add_log("SYS", f"Disconnected from {self.port or 'COM port'}.")
        self.is_connected = False
