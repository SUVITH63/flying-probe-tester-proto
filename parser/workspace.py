"""
Workspace Validator & Coordinate Frame Transformer
Computes local arm reference frames and checks reachability limits for 5-bar linkage arms.
Enforces strict anti-crossing & anti-touching clearance rules between Arm 0 (Top) and Arm 1 (Bottom).
"""
import math
from typing import Tuple, Dict, Any
from .models import Pad

class WorkspaceValidator:
    def __init__(
        self,
        l0: float = 80.0,
        l1: float = 35.0,
        l2: float = 70.0,
        arm_spacing_d: float = 115.0
    ):
        self.l0 = l0
        self.l1 = l1
        self.l2 = l2
        self.max_reach = l1 + l2
        self.min_reach = abs(l1 - l2)
        self.d = arm_spacing_d

    def global_to_local(self, arm_id: int, global_x: float, global_y: float) -> Tuple[float, float]:
        """
        Transforms global PCB coordinate (mm) to local arm reference frame.
        Arm 0: (x, y) = (global_x, global_y)
        Arm 1: (x, y) = (-global_x, D - global_y)
        """
        if arm_id == 0:
            return global_x, global_y
        elif arm_id == 1:
            return -global_x, self.d - global_y
        else:
            raise ValueError(f"Invalid arm_id: {arm_id}. Must be 0 or 1.")

    def is_reachable(self, arm_id: int, global_x: float, global_y: float) -> bool:
        """
        Validates if target global point is reachable by the specified 5-bar linkage arm.
        """
        local_x, local_y = self.global_to_local(arm_id, global_x, global_y)

        # Distance to Base Motor A (-L0/2, 0)
        d1_sq = (self.l0 / 2.0 + local_x)**2 + local_y**2
        d1 = math.sqrt(d1_sq)

        # Distance to Base Motor B (+L0/2, 0)
        d2_sq = (self.l0 / 2.0 - local_x)**2 + local_y**2
        d2 = math.sqrt(d2_sq)

        # Triangle inequality & singularity check
        if d1 > self.max_reach or d1 < self.min_reach:
            return False
        if d2 > self.max_reach or d2 < self.min_reach:
            return False

        # Y must be positive (above motor base line)
        if local_y <= 5.0:  # 5mm safety boundary from base line
            return False

        return True

    def validate_pad_pair(self, pad_a: Pad, pad_b: Pad) -> Tuple[bool, str]:
        """
        Validates if Pad A can be probed by Arm 0 and Pad B can be probed by Arm 1.
        Enforces anti-crossing & anti-touching collision rules so Arm 0 (Top) and Arm 1 (Bottom) never cross or touch.
        """
        # Ensure Arm 0 (Top) targets upper pad (smaller Y), Arm 1 (Bottom) targets lower pad (larger Y)
        top_pad = pad_a if pad_a.y <= pad_b.y else pad_b
        bot_pad = pad_b if pad_a.y <= pad_b.y else pad_a

        arm0_ok = self.is_reachable(0, top_pad.x, top_pad.y)
        if not arm0_ok:
            return False, f"Upper Pad ({top_pad.pad_id} at {top_pad.x:.1f},{top_pad.y:.1f}) is out of reach for Arm 0."

        arm1_ok = self.is_reachable(1, bot_pad.x, bot_pad.y)
        if not arm1_ok:
            return False, f"Lower Pad ({bot_pad.pad_id} at {bot_pad.x:.1f},{bot_pad.y:.1f}) is out of reach for Arm 1."

        # Distance & Anti-Collision Tip Clearance Check (Minimum 1.5mm separation)
        dist = math.hypot(top_pad.x - bot_pad.x, top_pad.y - bot_pad.y)
        if dist < 1.5:
            return False, f"Pads are too close ({dist:.2f}mm < 1.5mm safety threshold)."

        return True, "Reachable"

    def calculate_servo_angles(self, arm_id: int, global_x: float, global_y: float) -> Tuple[float, float]:
        """
        Calculates the motor/servo angles (theta_A, theta_B) in degrees for a 5-bar linkage arm.
        Motor A (Left) is at (-L0/2, 0).
        Motor B (Right) is at (+L0/2, 0).
        Both angles are computed in degrees [0 to 180] relative to positive X-axis.
        """
        local_x, local_y = self.global_to_local(arm_id, global_x, global_y)
        xA, yA = -self.l0 / 2.0, 0.0
        xB, yB = self.l0 / 2.0, 0.0

        # Motor A (Left)
        dxA = local_x - xA
        dyA = local_y - yA
        dA = math.hypot(dxA, dyA)
        alphaA = math.atan2(dyA, dxA)
        cos_betaA = (self.l1**2 + dA**2 - self.l2**2) / (2.0 * self.l1 * max(dA, 0.001))
        cos_betaA = max(-1.0, min(1.0, cos_betaA))
        betaA = math.acos(cos_betaA)
        # Outward elbow bending: left motor bends upward/leftward
        thetaA_rad = alphaA + betaA
        thetaA_deg = round(math.degrees(thetaA_rad), 1)

        # Motor B (Right)
        dxB = local_x - xB
        dyB = local_y - yB
        dB = math.hypot(dxB, dyB)
        alphaB = math.atan2(dyB, dxB)
        cos_betaB = (self.l1**2 + dB**2 - self.l2**2) / (2.0 * self.l1 * max(dB, 0.001))
        cos_betaB = max(-1.0, min(1.0, cos_betaB))
        betaB = math.acos(cos_betaB)
        # Outward elbow bending: right motor bends upward/rightward
        thetaB_rad = alphaB - betaB
        thetaB_deg = round(math.degrees(thetaB_rad), 1)

        return thetaA_deg, thetaB_deg
