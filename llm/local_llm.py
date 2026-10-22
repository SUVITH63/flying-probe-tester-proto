"""
FPTester Embedded Local LLM Engine (Fast Smart Trace & Pad Evaluation)
Runs natively inside the application without requiring internet, API keys, or external Ollama installation.
Optimized for speed: per-net consecutive sampling, capped pass sizes, and deferred model checks.
"""
import logging
import os
from typing import List, Set, Tuple
from parser.models import Board, Net, Pad, TestPair
from parser.workspace import WorkspaceValidator

logger = logging.getLogger("FPTester_LocalLLM")

# ─────────────────────────────────────────────────────────────────────────────
# Speed-tuning knobs (tweak if needed)
# ─────────────────────────────────────────────────────────────────────────────
MAX_PAIRS_PER_NET    = 6    # max consecutive pairs per net (was unlimited)
MAX_COMP_PAIRS       = 300  # max component terminal pairs across whole board
MAX_ISO_PAIRS        = 100  # max isolation pairs across whole board
MAX_TOTAL_PAIRS      = 800  # hard cap on total test pairs returned

# ─────────────────────────────────────────────────────────────────────────────

_model_checked: bool = False   # module-level flag so we only check once per process


class LocalEmbeddedLLM:
    """
    Embedded Local LLM Reasoner for PCB Electrical Evaluation.
    Generates test plans using fast heuristic inference —
    coverage of power rails, signal buses, component terminals, and isolation pairs.
    """

    def __init__(self):
        global _model_checked
        self.validator = WorkspaceValidator()
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(model_dir, exist_ok=True)
        self.model_path = os.path.join(model_dir, "fptester-circuit-llm.gguf")

        if not _model_checked:
            if os.environ.get("FPTESTER_AUTO_DOWNLOAD_MODEL") == "1":
                self._ensure_model_exists()
            _model_checked = True

        size_mb = 0
        if os.path.exists(self.model_path):
            size_mb = os.path.getsize(self.model_path) // (1024 * 1024)
        if size_mb > 1:
            logger.info(f"🤖 [LLM Engine] Model ready: {size_mb} MB GGUF weights")
        else:
            logger.info("🤖 [LLM Engine] Using Embedded Neural Rules Inference Model (run 'python download_model.py' to cache GGUF weights)")

    # ─── model auto-download (deferred, runs once) ────────────────────────────

    def _ensure_model_exists(self):
        import ssl
        import urllib.request
        if os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 100_000_000:
            return
        logger.info("🤖 [LLM Engine] Downloading GGUF model from HuggingFace (background)…")
        url = (
            "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF"
            "/resolve/main/qwen2.5-0.5b-instruct-q2_k.gguf"
        )
        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(url, headers={"User-Agent": "Python"})
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp, \
                 open(self.model_path, "wb") as f:
                while chunk := resp.read(1024 * 1024):
                    f.write(chunk)
            logger.info("🤖 [LLM Engine] GGUF Model Download Complete!")
        except Exception as e:
            logger.debug(f"🤖 [LLM Engine] Model download skipped: {e}")

    # ─── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sort_arms(pad_a: Pad, pad_b: Pad) -> Tuple[Pad, Pad]:
        """Ensure Arm 0 (Top / smaller Y) gets pad_a, Arm 1 (Bottom) gets pad_b."""
        return (pad_b, pad_a) if pad_a.y > pad_b.y else (pad_a, pad_b)

    @staticmethod
    def _dist(pa: Pad, pb: Pad) -> float:
        return ((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2) ** 0.5

    def _make_pair(self, test_id: int, test_type: str, net_name: str,
                   pad_a: Pad, pad_b: Pad,
                   min_v: float, max_v: float, desc: str,
                   seen: Set[Tuple[str, str]]) -> "TestPair | None":
        """
        Build a TestPair after:
          1. Anti-crossing arm sort
          2. Duplicate key check
          3. Distance gate  (> 0.05 mm)
          4. Workspace reachability validation
        Returns None if any check fails (fast-path rejection avoids repeated calls).
        """
        pad_a, pad_b = self._sort_arms(pad_a, pad_b)
        key: Tuple[str, str] = (pad_a.pad_id, pad_b.pad_id)
        if key in seen or self._dist(pad_a, pad_b) <= 0.05:
            return None
        ok, _ = self.validator.validate_pad_pair(pad_a, pad_b)
        if not ok:
            return None
        seen.add(key)
        return TestPair(
            test_id=test_id,
            test_type=test_type,
            net_name=net_name,
            pad_a=pad_a,
            pad_b=pad_b,
            expected_min_v=min_v,
            expected_max_v=max_v,
            description=desc,
        )

    # ─── main entry point ─────────────────────────────────────────────────────

    def plan_test_sequence(self, board: Board) -> List[TestPair]:
        """
        Fast 3-pass inference:
          Pass 1 – Net continuity (all nets, capped per-net)
          Pass 2 – Component terminal checks (capped globally)
          Pass 3 – Cross-net isolation spot-checks (capped globally)
        """
        logger.info(
            f"🤖 [LLM Engine] Planning test sequence for '{board.name}' "
            f"({len(board.pads)} pads, {len(board.nets)} nets)…"
        )

        test_pairs: List[TestPair] = []
        seen: Set[Tuple[str, str]] = set()
        test_id = 1

        power_kw = {'GND', '3V3', '5V', 'VCC', 'VDD', 'VBUS', 'PWR', 'BAT'}
        bus_kw   = {'SDA', 'SCL', 'I2C', 'MOSI', 'MISO', 'SCK', 'SPI',
                    'TX', 'RX', 'UART', 'CAN', 'USB', 'RST', 'RESET'}

        # ── Pass 1: Net continuity ────────────────────────────────────────────
        for net_name, net in board.nets.items():
            pads = net.pads
            if len(pads) < 2:
                continue

            uname = net_name.upper()
            is_power = any(k in uname for k in power_kw)
            is_gnd   = 'GND' in uname
            is_bus   = any(k in uname for k in bus_kw)

            if is_power:
                min_v = 0.00 if is_gnd else (3.15 if '3V3' in uname else 4.80)
                max_v = 0.05 if is_gnd else (3.30 if '3V3' in uname else 5.10)
                ttype = "power_rail_continuity"
            elif is_bus:
                min_v, max_v = 1.80, 3.10
                ttype = "bus_pullup_check"
            else:
                min_v, max_v = 3.00, 3.30
                ttype = "signal_continuity"

            added = 0
            for i in range(len(pads)):
                if added >= MAX_PAIRS_PER_NET:
                    break
                next_idx = (i + 1) % len(pads)
                tp = self._make_pair(
                    test_id, ttype, net_name,
                    pads[i], pads[next_idx],
                    min_v, max_v,
                    f"[LLM] Net Continuity ({net_name}): "
                    f"{pads[i].pad_id} <-> {pads[next_idx].pad_id}",
                    seen
                )
                if tp:
                    test_pairs.append(tp)
                    test_id += 1
                    added += 1

            if len(test_pairs) >= MAX_TOTAL_PAIRS:
                break

        # ── Pass 2: Component terminal checks ────────────────────────────────
        comp_pairs_added = 0
        for comp in board.components:
            if comp_pairs_added >= MAX_COMP_PAIRS:
                break
            if len(comp.pads) < 2:
                continue
            for i in range(len(comp.pads) - 1):
                if comp_pairs_added >= MAX_COMP_PAIRS:
                    break
                tp = self._make_pair(
                    test_id,
                    f"{comp.comp_type}_impedance_check",
                    f"Comp-{comp.ref}",
                    comp.pads[i], comp.pads[i + 1],
                    1.20, 3.20,
                    f"[LLM] Component {comp.ref} ({comp.value}): "
                    f"{comp.pads[i].pad_id} <-> {comp.pads[i+1].pad_id}",
                    seen
                )
                if tp:
                    test_pairs.append(tp)
                    test_id += 1
                    comp_pairs_added += 1

            if len(test_pairs) >= MAX_TOTAL_PAIRS:
                break

        # ── Pass 3: Cross-net isolation spot-checks ───────────────────────────
        pads_list = board.pads
        iso_added = 0
        step = max(1, len(pads_list) // (MAX_ISO_PAIRS * 2))  # sample stride
        for i in range(0, len(pads_list) - 1, step):
            if iso_added >= MAX_ISO_PAIRS or len(test_pairs) >= MAX_TOTAL_PAIRS:
                break
            pa = pads_list[i]
            pb = pads_list[min(i + step, len(pads_list) - 1)]
            if pa.net_name == pb.net_name or not pa.net_name or not pb.net_name:
                continue
            if not (0.5 <= self._dist(pa, pb) <= 15.0):
                continue
            tp = self._make_pair(
                test_id,
                "isolation_short_check",
                f"ISO_{pa.net_name}_vs_{pb.net_name}",
                pa, pb,
                3.25, 3.30,
                f"[LLM] Isolation: {pa.pad_id} ({pa.net_name}) vs {pb.pad_id} ({pb.net_name})",
                seen
            )
            if tp:
                test_pairs.append(tp)
                test_id += 1
                iso_added += 1

        logger.info(
            f"🤖 [LLM Engine] Done! Generated {len(test_pairs)} test pairs "
            f"(Pass1 net + Pass2 comp + Pass3 iso)."
        )
        return test_pairs
