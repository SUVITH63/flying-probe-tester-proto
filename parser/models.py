"""
Data models for FPTester PCB elements, coordinates, nets, and test plans.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

@dataclass
class Pad:
    pad_id: str                   # Unique identifier (e.g., "R1-1", "J1-pin2")
    component_ref: str           # Component designator (e.g., "R1", "U1")
    pad_number: str              # Pin/Pad number (e.g., "1", "A1")
    x: float                     # Absolute X coordinate in mm
    y: float                     # Absolute Y coordinate in mm
    width: float = 1.0           # Pad width in mm
    height: float = 1.0          # Pad height in mm
    shape: str = "rect"          # "rect", "circle", "oval", "trapezoid"
    layer: str = "F.Cu"          # "F.Cu", "B.Cu"
    net_id: int = 0              # Numeric net ID
    net_name: str = ""           # Human readable net name (e.g., "GND", "+3V3")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pad_id": self.pad_id,
            "component_ref": self.component_ref,
            "pad_number": self.pad_number,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "width": round(self.width, 3),
            "height": round(self.height, 3),
            "shape": self.shape,
            "layer": self.layer,
            "net_id": self.net_id,
            "net_name": self.net_name,
        }

@dataclass
class Component:
    ref: str                     # Reference designator (e.g., "R1")
    value: str                   # Component value (e.g., "10k", "100nF")
    footprint: str               # Footprint package name
    x: float                     # Component origin X in mm
    y: float                     # Component origin Y in mm
    rotation: float = 0.0        # Rotation angle in degrees
    comp_type: str = "unknown"   # "resistor", "capacitor", "ic", "connector", etc.
    pads: List[Pad] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "value": self.value,
            "footprint": self.footprint,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "rotation": round(self.rotation, 1),
            "comp_type": self.comp_type,
            "pad_count": len(self.pads),
        }

@dataclass
class Net:
    net_id: int
    name: str
    pads: List[Pad] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "net_id": self.net_id,
            "name": self.name,
            "pad_count": len(self.pads),
            "pad_ids": [p.pad_id for p in self.pads],
        }

@dataclass
class Board:
    name: str
    width: float = 0.0           # Board bounding box width in mm
    height: float = 0.0          # Board bounding box height in mm
    pads: List[Pad] = field(default_factory=list)
    components: List[Component] = field(default_factory=list)
    nets: Dict[str, Net] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dimensions": {"width": round(self.width, 2), "height": round(self.height, 2)},
            "total_components": len(self.components),
            "total_pads": len(self.pads),
            "total_nets": len(self.nets),
        }

@dataclass
class TestPair:
    test_id: int
    test_type: str               # "continuity", "isolation", "resistor_check"
    net_name: str
    pad_a: Pad                   # Probed by Arm 0
    pad_b: Pad                   # Probed by Arm 1
    expected_min_v: float = 3.0  # Expected minimum ADC voltage
    expected_max_v: float = 3.3  # Expected maximum ADC voltage
    description: str = ""

    def to_hardware_command(self, job_id: int) -> Dict[str, Any]:
        """
        Formats test command to match ESP32 USB JSON protocol with 5-bar linkage servo angles.
        """
        # Calculate servo angles for both 5-bar arms
        s0a, s0b = 90.0, 90.0
        s1a, s1b = 90.0, 90.0
        try:
            from .workspace import WorkspaceValidator
            val = WorkspaceValidator()
            s0a, s0b = val.calculate_servo_angles(0, self.pad_a.x, self.pad_a.y)
            s1a, s1b = val.calculate_servo_angles(1, self.pad_b.x, self.pad_b.y)
        except Exception:
            pass

        return {
            "msg_type": "run_test",
            "job_id": job_id,
            "test_type": "digital_high_adc_read",
            "arms": [
                {
                    "arm_id": 0,
                    "x": round(self.pad_a.x, 3),
                    "y": round(self.pad_a.y, 3),
                    "servo_a_deg": s0a,
                    "servo_b_deg": s0b,
                    "pad_ref": self.pad_a.pad_id
                },
                {
                    "arm_id": 1,
                    "x": round(self.pad_b.x, 3),
                    "y": round(self.pad_b.y, 3),
                    "servo_a_deg": s1a,
                    "servo_b_deg": s1b,
                    "pad_ref": self.pad_b.pad_id
                },
            ],
            "gcode": f"G0 X0={self.pad_a.x:.2f} Y0={self.pad_a.y:.2f} S0A={s0a} S0B={s0b} X1={self.pad_b.x:.2f} Y1={self.pad_b.y:.2f} S1A={s1a} S1B={s1b}",
            "test_params": {
                "tx_arm_id": 0,
                "rx_arm_id": 1,
                "tx_high_time_ms": 100
            },
            "meta": {
                "test_id": self.test_id,
                "net": self.net_name,
                "pad_a_ref": self.pad_a.pad_id,
                "pad_b_ref": self.pad_b.pad_id,
                "expected_min_v": self.expected_min_v,
                "expected_max_v": self.expected_max_v,
                "description": self.description
            }
        }

@dataclass
class TestJob:
    job_id: int
    board_name: str
    test_pairs: List[TestPair] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "board_name": self.board_name,
            "total_tests": len(self.test_pairs),
            "commands": [tp.to_hardware_command(self.job_id) for tp in self.test_pairs]
        }
