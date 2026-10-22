"""
Integration tests for FPTester FastAPI Server, AI Planner, and Serial Dispatcher
"""
import unittest
import os
import sys

# Ensure host directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from parser.kicad_parser import KiCadPCBParser
from parser.ai_planner import AITestPlanner
from parser.serial_dispatcher import SerialDispatcher
from parser.workspace import WorkspaceValidator

SAMPLE_KICAD_PCB = """(kicad_pcb (version 20211014) (generator pcbnew)
  (net 0 "")
  (net 1 "GND")
  (net 2 "+3V3")
  (net 3 "SDA")

  (footprint "Resistor_SMD:R_0805_2012Metric" (at -2.0 57.5 0.0)
    (property "Reference" "R1")
    (property "Value" "10k")
    (pad "1" smd rect (at -0.5 0.0 0.0) (size 1.0 1.2) (layers "F.Cu") (net 3 "SDA"))
    (pad "2" smd rect (at 0.5 0.0 0.0) (size 1.0 1.2) (layers "F.Cu") (net 2 "+3V3"))
  )

  (footprint "Resistor_SMD:R_0805_2012Metric" (at 2.0 57.5 0.0)
    (property "Reference" "R2")
    (property "Value" "10k")
    (pad "1" smd rect (at -0.5 0.0 0.0) (size 1.0 1.2) (layers "F.Cu") (net 3 "SDA"))
    (pad "2" smd rect (at 0.5 0.0 0.0) (size 1.0 1.2) (layers "F.Cu") (net 2 "+3V3"))
  )
)"""

class TestAPIServerAndAI(unittest.TestCase):
    def test_ai_planner(self):
        parser = KiCadPCBParser()
        board = parser.parse_string(SAMPLE_KICAD_PCB)

        planner = AITestPlanner()
        job = planner.generate_plan(board, job_id=202)

        self.assertEqual(job.job_id, 202)
        self.assertGreater(len(job.test_pairs), 0)

        first_test = job.test_pairs[0]
        self.assertIn(first_test.net_name, ["+3V3", "SDA"])
        self.assertGreaterEqual(first_test.expected_min_v, 1.8)

    def test_serial_dispatcher_simulation(self):
        dispatcher = SerialDispatcher(port="SIMULATED_COM1")
        ok, msg = dispatcher.connect()
        self.assertTrue(ok)

        cmd = {
            "msg_type": "run_test",
            "job_id": 202,
            "test_params": {"tx_high_time_ms": 100},
            "meta": {"test_id": 1, "expected_min_v": 3.0}
        }

        res = dispatcher.send_test_command(cmd)
        self.assertEqual(res["status"], "done")
        self.assertEqual(res["result"]["verdict"], "PASS")
        self.assertGreaterEqual(res["result"]["adc_voltage"], 3.0)

        dispatcher.disconnect()

    def test_serial_ports_listing(self):
        ports = SerialDispatcher.list_available_ports()
        self.assertIsInstance(ports, list)

    def test_5bar_servo_angles_ik(self):
        val = WorkspaceValidator()
        # Arm 0 (Top arm) at center of PCB
        deg_a, deg_b = val.calculate_servo_angles(0, 0.0, 57.5)
        self.assertGreaterEqual(deg_a, 0.0)
        self.assertLessEqual(deg_a, 180.0)
        self.assertGreaterEqual(deg_b, 0.0)
        self.assertLessEqual(deg_b, 180.0)

        # Arm 1 (Bottom arm) at center of PCB
        deg_1a, deg_1b = val.calculate_servo_angles(1, 0.0, 57.5)
        self.assertGreaterEqual(deg_1a, 0.0)
        self.assertLessEqual(deg_1a, 180.0)
        self.assertGreaterEqual(deg_1b, 0.0)
        self.assertLessEqual(deg_1b, 180.0)

    def test_hardware_command_servo_and_gcode(self):
        parser = KiCadPCBParser()
        board = parser.parse_string(SAMPLE_KICAD_PCB)
        planner = AITestPlanner()
        job = planner.generate_plan(board, job_id=303)
        self.assertGreater(len(job.test_pairs), 0)

        cmd = job.test_pairs[0].to_hardware_command(job.job_id)
        # Check servo angles in command
        self.assertIn("arms", cmd)
        self.assertEqual(len(cmd["arms"]), 2)
        self.assertIn("servo_a_deg", cmd["arms"][0])
        self.assertIn("servo_b_deg", cmd["arms"][0])
        self.assertIn("servo_a_deg", cmd["arms"][1])
        self.assertIn("servo_b_deg", cmd["arms"][1])
        # Check G-code string
        self.assertIn("gcode", cmd)
        self.assertTrue(cmd["gcode"].startswith("G0"))
        self.assertIn("S0A=", cmd["gcode"])
        self.assertIn("S1A=", cmd["gcode"])

    def test_serial_monitor_log_buffer(self):
        from parser.serial_dispatcher import append_serial_log, get_serial_logs, clear_serial_logs
        clear_serial_logs()
        append_serial_log("TX", "PING", "COM3")
        append_serial_log("RX", "PONG", "COM3")
        logs = get_serial_logs(0)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["direction"], "TX")
        self.assertEqual(logs[0]["text"], "PING")
        self.assertEqual(logs[1]["direction"], "RX")
        self.assertEqual(logs[1]["text"], "PONG")

        # Test since parameter
        since_id = logs[0]["id"]
        later_logs = get_serial_logs(since_id)
        self.assertEqual(len(later_logs), 1)
        self.assertEqual(later_logs[0]["text"], "PONG")

if __name__ == "__main__":
    unittest.main()

