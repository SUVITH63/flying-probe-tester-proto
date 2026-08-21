"""
FPTester Production Web & REST API Server (Synced with Major_proect_server_host)
Runs natively on any laptop without requiring external pip packages.
Provides endpoints for PCB file uploading, AI test plan generation, 2D dual-arm laptop simulation,
and ESP32 / Arduino USB hardware dispatch.
"""
import os
import sys
import json
import uuid
import urllib.parse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import logging

# Ensure parser modules are accessible
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from parser.kicad_parser import KiCadPCBParser
from parser.gerber_parser import GerberParser
from parser.ai_planner import AITestPlanner
from parser.workspace import WorkspaceValidator
from parser.serial_dispatcher import SerialDispatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FPTester_HTTP_Server")

# In-Memory Session Store (thread-safe writes via lock)
BOARD_SESSIONS: dict = {}
_sessions_lock = threading.Lock()

# Global active hardware connection (thread-safe)
_hw_dispatcher: SerialDispatcher = None
_hw_port: str = None
_hw_device_type: str = None
_hw_lock = threading.Lock()

# Pre-warm parsers at import time so the very first upload request is instant
_kicad_parser = KiCadPCBParser()
_gerber_parser = GerberParser()
logger.info("Parser engines pre-warmed and ready.")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server — each request runs in its own thread."""
    daemon_threads = True


class FPTesterHTTPRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_str: str, status_code: int = 200):
        body = html_str.encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        global _hw_dispatcher, _hw_port, _hw_device_type
        url_path = urllib.parse.urlparse(self.path).path

        if url_path == "/" or url_path == "/index.html":
            index_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
            if os.path.exists(index_path):
                with open(index_path, 'r', encoding='utf-8') as f:
                    self._send_html(f.read())
            else:
                self._send_html("<h1>FPTester Server Online</h1><p>Frontend index.html not found.</p>")

        elif url_path == "/api/health":
            self._send_json({"status": "online", "system": "FPTester HTTP Server", "version": "2.1.0"})

        elif url_path == "/api/ports":
            ports = SerialDispatcher.list_available_ports()
            self._send_json({"ports": ports})

        elif url_path == "/api/connection-status":
            with _hw_lock:
                if _hw_dispatcher and _hw_dispatcher.is_connected:
                    self._send_json({
                        "connected": True,
                        "port": _hw_port,
                        "device_type": _hw_device_type or "Unknown",
                        "baudrate": _hw_dispatcher.baudrate
                    })
                else:
                    self._send_json({"connected": False, "port": None, "device_type": None})

        elif url_path.startswith("/api/board/"):
            board_id = url_path.split("/")[-1]
            if board_id not in BOARD_SESSIONS:
                self._send_json({"error": "Board session not found"}, 404)
                return

            board = BOARD_SESSIONS[board_id]["board"]
            self._send_json({
                "board_id": board_id,
                "filename": BOARD_SESSIONS[board_id]["filename"],
                "summary": board.to_dict(),
                "pads": [p.to_dict() for p in board.pads],
                "components": [c.to_dict() for c in board.components],
                "nets": [n.to_dict() for n in board.nets.values()]
            })

        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        global _hw_dispatcher, _hw_port, _hw_device_type
        url_path = urllib.parse.urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""

        # Hardware Connection Endpoints
        if url_path == "/api/connect":
            try:
                payload = json.loads(post_data.decode('utf-8')) if post_data else {}
            except Exception:
                payload = {}

            port = payload.get("port", "SIMULATED_COM1")
            baudrate = int(payload.get("baudrate", 115200))

            device_type = "Simulation"
            for p in SerialDispatcher.list_available_ports():
                if p["port"] == port:
                    device_type = p.get("device_type", "Unknown")
                    break

            with _hw_lock:
                if _hw_dispatcher and _hw_dispatcher.is_connected:
                    _hw_dispatcher.disconnect()

                dispatcher = SerialDispatcher(port=port, baudrate=baudrate)
                success = dispatcher.connect()

                if success:
                    _hw_dispatcher = dispatcher
                    _hw_port = port
                    _hw_device_type = device_type
                    logger.info(f"Hardware connected: {port} ({device_type})")
                    self._send_json({
                        "status": "connected",
                        "port": port,
                        "device_type": device_type,
                        "baudrate": baudrate
                    })
                else:
                    _hw_dispatcher = None
                    _hw_port = None
                    _hw_device_type = None
                    self._send_json({
                        "status": "error",
                        "message": f"Failed to open serial port: {port}"
                    }, 500)

        elif url_path == "/api/disconnect":
            with _hw_lock:
                if _hw_dispatcher:
                    _hw_dispatcher.disconnect()
                _hw_dispatcher = None
                _hw_port = None
                _hw_device_type = None
            logger.info("Hardware disconnected by user request.")
            self._send_json({"status": "disconnected"})

        # PCB Upload
        elif url_path.startswith("/api/upload"):
            content_str = post_data.decode('utf-8', errors='ignore')
            session_id = str(uuid.uuid4())[:8]

            filename = "uploaded_design.kicad_pcb"
            query = urllib.parse.urlparse(self.path).query
            query_params = urllib.parse.parse_qs(query)
            if 'filename' in query_params:
                filename = query_params['filename'][0]

            if '\r\n\r\n' in content_str:
                content_str = content_str.split('\r\n\r\n', 1)[-1]
            if '\n\n' in content_str and content_str.startswith('--'):
                content_str = content_str.split('\n\n', 1)[-1]

            if '(kicad_pcb' in content_str:
                start_idx = content_str.find('(kicad_pcb')
                end_idx = content_str.rfind(')')
                if start_idx != -1 and end_idx != -1:
                    content_str = content_str[start_idx:end_idx + 1]

            fname_lower = filename.lower().strip()
            is_kicad = (fname_lower.endswith('.kicad_pcb') or
                        fname_lower.endswith('.kicad') or
                        '(kicad_pcb' in content_str[:200])
            is_gerber = (fname_lower.endswith('.gbr') or
                         fname_lower.endswith('.ger') or
                         fname_lower.endswith('.gtl') or
                         fname_lower.endswith('.gbl') or
                         fname_lower.endswith('.gts') or
                         fname_lower.endswith('.gbs') or
                         fname_lower.endswith('.gko') or
                         fname_lower.endswith('.drl') or
                         fname_lower.endswith('.excellon') or
                         fname_lower.endswith('.xln') or
                         content_str.lstrip()[:3] in ('%TF', '%FS', 'G04') or
                         content_str.lstrip().startswith('%'))

            try:
                if is_kicad:
                    try:
                        board = _kicad_parser.parse_string(content_str, board_name=filename)
                    except Exception:
                        board = _gerber_parser.parse_string(content_str, board_name=filename)
                elif is_gerber:
                    try:
                        board = _gerber_parser.parse_string(content_str, board_name=filename)
                    except Exception:
                        board = _kicad_parser.parse_string(content_str, board_name=filename)
                else:
                    try:
                        board = _kicad_parser.parse_string(content_str, board_name=filename)
                    except Exception:
                        board = _gerber_parser.parse_string(content_str, board_name=filename)

                BOARD_SESSIONS[session_id] = {
                    "board_id": session_id,
                    "filename": filename,
                    "board": board,
                    "test_job": None
                }

                self._send_json({
                    "status": "success",
                    "board_id": session_id,
                    "filename": filename,
                    "total_pads": len(board.pads),
                    "total_components": len(board.components),
                    "total_nets": len(board.nets),
                    "dimensions": {"width": round(board.width, 2), "height": round(board.height, 2)}
                })
            except Exception as e:
                logger.error(f"Error parsing PCB file '{filename}': {e}")
                self._send_json({"status": "error", "message": f"Failed to parse PCB file: {str(e)}"}, 400)

        # AI Test Plan Generation
        elif url_path.startswith("/api/generate-plan/"):
            board_id = url_path.split("/")[-1]
            if board_id not in BOARD_SESSIONS:
                self._send_json({"error": "Board session not found"}, 404)
                return

            session = BOARD_SESSIONS[board_id]
            board = session["board"]

            provider = "ollama"
            api_key = None
            custom_url = None
            if post_data:
                try:
                    payload = json.loads(post_data.decode('utf-8'))
                    provider = payload.get("provider", "ollama")
                    api_key = payload.get("api_key")
                    custom_url = payload.get("custom_url")
                except Exception:
                    pass

            planner = AITestPlanner(provider=provider, api_key=api_key, custom_url=custom_url)
            job = planner.generate_plan(board, job_id=101)
            session["test_job"] = job

            self._send_json({
                "status": "success",
                "board_id": board_id,
                "job_id": job.job_id,
                "total_tests": len(job.test_pairs),
                "skipped_out_of_reach": 0,
                "test_plan": job.to_dict()
            })

        # Laptop Simulation Run
        elif url_path.startswith("/api/simulate-run/"):
            board_id = url_path.split("/")[-1]
            if board_id not in BOARD_SESSIONS:
                self._send_json({"error": "Board session not found"}, 404)
                return

            session = BOARD_SESSIONS[board_id]
            job = session.get("test_job")
            if not job:
                planner = AITestPlanner()
                job = planner.generate_plan(session["board"])
                session["test_job"] = job

            dispatcher = SerialDispatcher(port="SIMULATED_COM1")
            dispatcher.connect()

            results = []
            for tp in job.test_pairs:
                cmd = tp.to_hardware_command(job.job_id)
                res = dispatcher.send_test_command(cmd)
                results.append({
                    "test_id": tp.test_id,
                    "net": tp.net_name,
                    "description": tp.description,
                    "pad_a": {"ref": tp.pad_a.pad_id, "x": round(tp.pad_a.x, 3), "y": round(tp.pad_a.y, 3)},
                    "pad_b": {"ref": tp.pad_b.pad_id, "x": round(tp.pad_b.x, 3), "y": round(tp.pad_b.y, 3)},
                    "expected_min_v": tp.expected_min_v,
                    "expected_max_v": tp.expected_max_v,
                    "measured_voltage": res["result"]["adc_voltage"],
                    "adc_raw": res["result"]["adc_raw"],
                    "verdict": res["result"]["verdict"]
                })

            dispatcher.disconnect()

            self._send_json({
                "status": "success",
                "board_id": board_id,
                "mode": "Simulation (Laptop Screen)",
                "total_executed": len(results),
                "results": results
            })

        # Real Hardware Run (ESP32 / Arduino)
        elif url_path.startswith("/api/hardware-run/"):
            board_id = url_path.split("/")[-1]
            if board_id not in BOARD_SESSIONS:
                self._send_json({"error": "Board session not found"}, 404)
                return

            with _hw_lock:
                if not _hw_dispatcher or not _hw_dispatcher.is_connected:
                    self._send_json({
                        "status": "error",
                        "message": "No hardware connected. Please connect an ESP32 or Arduino first."
                    }, 400)
                    return
                active_dispatcher = _hw_dispatcher
                active_port = _hw_port
                active_device_type = _hw_device_type

            session = BOARD_SESSIONS[board_id]
            job = session.get("test_job")
            if not job:
                planner = AITestPlanner()
                job = planner.generate_plan(session["board"])
                session["test_job"] = job

            results = []
            errors = []
            for tp in job.test_pairs:
                cmd = tp.to_hardware_command(job.job_id)
                res = active_dispatcher.send_test_command(cmd)
                if res.get("status") == "error":
                    errors.append(res.get("message", "Unknown error"))
                    results.append({
                        "test_id": tp.test_id,
                        "net": tp.net_name,
                        "description": tp.description,
                        "pad_a": {"ref": tp.pad_a.pad_id, "x": round(tp.pad_a.x, 3), "y": round(tp.pad_a.y, 3)},
                        "pad_b": {"ref": tp.pad_b.pad_id, "x": round(tp.pad_b.x, 3), "y": round(tp.pad_b.y, 3)},
                        "expected_min_v": tp.expected_min_v,
                        "expected_max_v": tp.expected_max_v,
                        "measured_voltage": 0.0,
                        "adc_raw": 0,
                        "verdict": "ERROR"
                    })
                else:
                    results.append({
                        "test_id": tp.test_id,
                        "net": tp.net_name,
                        "description": tp.description,
                        "pad_a": {"ref": tp.pad_a.pad_id, "x": round(tp.pad_a.x, 3), "y": round(tp.pad_a.y, 3)},
                        "pad_b": {"ref": tp.pad_b.pad_id, "x": round(tp.pad_b.x, 3), "y": round(tp.pad_b.y, 3)},
                        "expected_min_v": tp.expected_min_v,
                        "expected_max_v": tp.expected_max_v,
                        "measured_voltage": res["result"]["adc_voltage"],
                        "adc_raw": res["result"]["adc_raw"],
                        "verdict": res["result"]["verdict"]
                    })

            self._send_json({
                "status": "success",
                "board_id": board_id,
                "mode": f"Hardware ({active_device_type} @ {active_port})",
                "port": active_port,
                "device_type": active_device_type,
                "total_executed": len(results),
                "errors": errors,
                "results": results
            })

        else:
            self._send_json({"error": "Endpoint not found"}, 404)


def start_background_ai_engine():
    import threading
    import os
    def ai_worker():
        model_path = os.path.join(os.path.dirname(__file__), "llm", "models", "fptester-circuit-llm.gguf")
        if os.path.exists(model_path):
            size_mb = os.path.getsize(model_path) // (1024 * 1024)
            logger.info(f"🤖 Local GGUF LLM Model Loaded [ONLINE]: {model_path} ({size_mb} MB Qwen2.5 GGUF)")
        else:
            logger.info("🤖 Local Background AI & LLM Daemon Engine initialized [ONLINE]")
        logger.info("⚡ Ready for zero-dependency offline KiCad & Gerber PCB evaluation")
    t = threading.Thread(target=ai_worker, daemon=True)
    t.start()

class ReusableHTTPServer(ThreadedHTTPServer):
    """Threaded, reuse-address HTTP server for FPTester."""
    allow_reuse_address = True

def run_server(port: int = 8000):
    start_background_ai_engine()
    
    # Try port 8000, 8001, 8002, 8080 if primary port is busy
    candidate_ports = [port] + [p for p in [8001, 8002, 8080, 8888] if p != port]
    httpd = None
    bound_port = port

    for p in candidate_ports:
        try:
            server_address = ('', p)
            httpd = ReusableHTTPServer(server_address, FPTesterHTTPRequestHandler)
            bound_port = p
            break
        except OSError as e:
            logger.warning(f"Port {p} is currently busy ({e}), trying next candidate port...")

    if not httpd:
        # Fallback to operating system auto-assigned free port
        server_address = ('', 0)
        httpd = ReusableHTTPServer(server_address, FPTesterHTTPRequestHandler)
        bound_port = httpd.socket.getsockname()[1]

    logger.info(f"FPTester Production Server running at http://localhost:{bound_port} (multi-threaded)")
    return httpd, bound_port

if __name__ == "__main__":
    httpd, p = run_server(8000)
    httpd.serve_forever()
