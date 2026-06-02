import subprocess
import time
import sys
import os
import threading

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import logging
from logging.handlers import RotatingFileHandler
import json
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ==========================================
# Configuration
# ==========================================
APP_SCRIPT = "single_app.py"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            "monitor.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8',
        ),
    ]
)
logger = logging.getLogger("Monitor")


def _port_from_env(*keys: str, default: int) -> int:
    """First non-empty env among keys wins; invalid values log a warning and fall back to default."""
    for k in keys:
        raw = os.environ.get(k, "").strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            logger.warning("Invalid %s=%r; using default port %s", k, raw, default)
    return default


def _tcp_can_bind(host: str, port: int) -> bool:
    """True if we can bind an IPv4 TCP listener (detects Windows reserved ranges and busy ports)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        finally:
            s.close()
    except OSError:
        return False


def _first_bindable_tcp_port(host: str, preferred: int, fallbacks: tuple[int, ...], avoid: frozenset[int]) -> int:
    for p in (preferred,) + fallbacks:
        if p in avoid:
            continue
        if _tcp_can_bind(host, p):
            return p
    return preferred


def _resolve_win32_listen_ports(host: str, app_port: int, monitor_port: int) -> tuple[int, int]:
    """Hyper-V/WSL often reserve 8057-8156; 8080/8081 then fail with WinError 10013. Pick working ports."""
    if sys.platform != "win32":
        return app_port, monitor_port
    mon_fb = (18081, 19081, 28181, 38981, 49876)
    app_fb = (8780, 8781, 8880, 8980, 9080, 9180, 9280)
    new_mon = _first_bindable_tcp_port(host, monitor_port, mon_fb, frozenset())
    if new_mon != monitor_port:
        logger.warning(
            "Monitor: cannot bind %s:%s (reserved range or in use); using %s",
            host,
            monitor_port,
            new_mon,
        )
    new_app = _first_bindable_tcp_port(host, app_port, app_fb, frozenset({new_mon}))
    if new_app != app_port:
        logger.warning(
            "Managed app: cannot bind %s:%s (reserved range or in use); using PORT=%s",
            host,
            app_port,
            new_app,
        )
    return new_app, new_mon


# PORT / APP_PORT: managed app (single_app reads PORT). MONITOR_*: this HTTP monitor only.
APP_PORT = _port_from_env("APP_PORT", "PORT", default=8080)
MONITOR_PORT = _port_from_env("MONITOR_PORT", default=8081)
MONITOR_HOST = (os.environ.get("MONITOR_HOST") or "0.0.0.0").strip() or "0.0.0.0"
APP_PORT, MONITOR_PORT = _resolve_win32_listen_ports(MONITOR_HOST, APP_PORT, MONITOR_PORT)
os.environ["PORT"] = str(APP_PORT)
os.environ["MONITOR_PORT"] = str(MONITOR_PORT)

LICENSE_PORT = _port_from_env("LICENSE_BIND_PORT", default=8088)


def _license_auto_start_enabled() -> bool:
    if (os.environ.get("LICENSE_AUTO_START_SERVER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    return (os.environ.get("LICENSE_ENFORCE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def ensure_license_server_running() -> bool:
    """同机许可服务未监听时自动拉起（逻辑见 license_client.ensure_license_server_running）。"""
    try:
        from license_client import ensure_license_server_running as _ensure

        os.environ.setdefault("LICENSE_BIND_PORT", str(LICENSE_PORT))
        if not _license_auto_start_enabled():
            return is_port_in_use(LICENSE_PORT)
        if is_port_in_use(LICENSE_PORT):
            return True
        logger.info(
            "License server not listening on 127.0.0.1:%s — starting license_server.app",
            LICENSE_PORT,
        )
        ok = _ensure(wait_seconds=15.0)
        if ok:
            logger.info("License server is up on port %s", LICENSE_PORT)
        else:
            logger.warning("License server start timed out (port %s)", LICENSE_PORT)
        return ok
    except Exception as e:
        logger.error("Failed to start license server: %s", e)
        return False


def rotate_plain_log_if_needed(path: str, max_bytes: int = LOG_MAX_BYTES, backup_count: int = LOG_BACKUP_COUNT) -> None:
    """Rotate non-logging plain text files (e.g. subprocess stdout capture) at size limit."""
    try:
        if not os.path.exists(path):
            return
        if os.path.getsize(path) < max_bytes:
            return
        for i in range(backup_count - 1, 0, -1):
            src = f"{path}.{i}"
            dst = f"{path}.{i + 1}"
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.replace(src, dst)
        first = f"{path}.1"
        if os.path.exists(first):
            os.remove(first)
        os.replace(path, first)
    except Exception as e:
        logger.warning(f"Failed to rotate plain log {path}: {e}")

# Require MONITOR_SECRET for restart/stop/start; GET /status remains readable for health checks.
MONITOR_SECRET = os.environ.get("MONITOR_SECRET", "").strip()
if not MONITOR_SECRET:
    logger.warning(
        "MONITOR_SECRET is not set: monitor control POST actions are disabled. "
        "Set MONITOR_SECRET to a strong random value before using /restart, /stop, /start."
    )

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_process_on_port(port):
    try:
        if sys.platform == "win32":
            # Use cmd /c to handle piping in netstat
            cmd = f'netstat -ano | findstr :{port} | findstr LISTENING'
            try:
                output = subprocess.check_output(cmd, shell=True).decode()
                for line in output.strip().split('\n'):
                    parts = line.split()
                    if len(parts) > 4:
                        pid = parts[-1]
                        logger.info(f"Killing orphan process {pid} on port {port}...")
                        subprocess.run(['taskkill', '/F', '/T', '/PID', pid], capture_output=True)
                return True
            except subprocess.CalledProcessError:
                return False
    except Exception as e:
        logger.error(f"Failed to kill process on port {port}: {e}")
    return False

class AppManager:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.is_intentionally_stopped = False

    def get_python_executable(self):
        """Prefer 'python' command over sys.executable to match .bat behavior"""
        try:
            subprocess.check_call(['python', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 'python'
        except:
            return sys.executable

    def start_app(self, force=False):
        with self.lock:
            if is_port_in_use(APP_PORT):
                if force:
                    logger.warning(f"Port {APP_PORT} is in use. Forcing cleanup...")
                    kill_process_on_port(APP_PORT)
                    time.sleep(1)
                else:
                    logger.warning(f"Port {APP_PORT} is already in use.")
            
            if self.process and self.process.poll() is None:
                return False, "Application is already running."
            
            ensure_license_server_running()
            logger.info(f"Starting application: {APP_SCRIPT}")
            try:
                env = os.environ.copy()
                env["PORT"] = str(APP_PORT)
                # Crucial for fixing "character maps to <undefined>" errors in Windows console
                env['PYTHONIOENCODING'] = 'utf-8'
                cwd = os.path.dirname(os.path.abspath(__file__))
                
                # We use CREATE_NEW_CONSOLE so the user can see the window.
                # However, to avoid "flashing" on error, we could wrap it in a cmd /k.
                # But for the monitor to track the PID correctly, we want to launch the python process directly.
                
                python_cmd = self.get_python_executable()
                logger.info(f"Using python: {python_cmd}")

                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = 0x00000010 # CREATE_NEW_CONSOLE

                # Redirect output to a log file instead of the new console to capture errors.
                # If the user wants to SEE the window actually working, we could skip redirection,
                # but then we lose the app_stdout.log. 
                # Better middle ground: Redirect to log, and the console window will just be a placeholder or we can use 'start'
                
                rotate_plain_log_if_needed("app_stdout.log")
                with open("app_stdout.log", "a", encoding="utf-8") as app_log:
                    app_log.write(f"\n--- Starting App at {time.ctime()} ---\n")
                    self.process = subprocess.Popen(
                        [python_cmd, APP_SCRIPT],
                        stdout=app_log,
                        stderr=app_log,
                        cwd=cwd,
                        env=env,
                        creationflags=creation_flags
                    )
                
                self.is_intentionally_stopped = False
                return True, f"Started application with PID {self.process.pid}"
            except Exception as e:
                logger.error(f"Failed to start application: {e}")
                return False, str(e)

    def stop_app(self):
        with self.lock:
            self.is_intentionally_stopped = True
            if self.process and self.process.poll() is None:
                logger.info(f"Stopping managed application (PID: {self.process.pid})...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            kill_process_on_port(APP_PORT)
            self.process = None
            return True, "Application stopped."

    def restart_app(self):
        logger.info("Restart requested.")
        self.stop_app()
        time.sleep(2)
        return self.start_app(force=True)

    def get_status(self):
        with self.lock:
            managed_alive = self.process and self.process.poll() is None
            port_alive = is_port_in_use(APP_PORT)
            if managed_alive:
                return "running", self.process.pid
            elif port_alive:
                return "orphan_detected", "External/Orphan"
            return "stopped", None

manager = AppManager()

class MonitorHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        BaseHTTPRequestHandler.end_headers(self)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/status':
            state, pid = manager.get_status()
            data = {"status": state, "pid": pid, "app_script": APP_SCRIPT, "timestamp": time.time()}
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = f"""
            <html>
                <head>
                    <title>App Monitor</title>
                    <style>
                        body {{ font-family: -apple-system, sans-serif; padding: 40px; background: #f0f2f5; max-width: 800px; margin: 0 auto; }}
                        .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                        .status {{ padding: 20px; border-radius: 8px; margin: 20px 0; font-size: 1.2em; font-weight: bold; border: 1px solid #ddd; }}
                        .running {{ background: #e6f4ea; color: #1e7e34; }}
                        .stopped {{ background: #fce8e6; color: #d93025; }}
                        .btn {{ padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-right: 10px; }}
                        .btn-primary {{ background: #1a73e8; color: white; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>Inbound Recorder Monitor</h1>
                        <div id="status" class="status">Loading...</div>
                        <button class="btn btn-primary" onclick="doAction('restart')">Force Restart</button>
                        <button class="btn" style="background:#666; color:white;" onclick="location.reload()">Refresh</button>
                    </div>
                    <script>
                        function update() {{
                            fetch('/status').then(r=>r.json()).then(d=>{{
                                const s = document.getElementById('status');
                                s.className = 'status ' + (d.status === 'running' ? 'running' : 'stopped');
                                s.innerText = d.status + (d.pid ? ' (PID: ' + d.pid + ')' : '');
                            }});
                        }}
                        update(); setInterval(update, 5000);
                        function doAction(a) {{
                            const t = prompt('Token:'); if(!t) return;
                            fetch('/'+a+'?token='+t, {{method:'POST'}}).then(r=>r.json()).then(d=>{{ alert(d.message || d.error); update(); }});
                        }}
                    </script>
                </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
        else: self.send_error(404)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        query = parse_qs(parsed_path.query)
        token = self.headers.get('X-Monitor-Token') or query.get('token', [None])[0]
        if not MONITOR_SECRET:
            self.send_response(503)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "success": False,
                        "error": "MONITOR_SECRET is not configured",
                    }
                ).encode("utf-8")
            )
            return
        if token != MONITOR_SECRET:
            self.send_response(403); self.end_headers(); return
        success, message = False, ""
        if parsed_path.path == '/restart': success, message = manager.restart_app()
        elif parsed_path.path == '/stop': success, message = manager.stop_app()
        elif parsed_path.path == '/start': success, message = manager.start_app(force=True)
        self.send_response(200 if success else 400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"success": success, "message": message}).encode('utf-8'))

    def log_message(self, format, *args): return

def supervisor_loop():
    while True:
        try:
            state, _ = manager.get_status()
            if (state == "stopped" or state == "orphan_detected") and not manager.is_intentionally_stopped:
                logger.warning(f"Recovery needed: {state}. Restarting in 5s...")
                time.sleep(5)
                manager.start_app(force=True)
        except Exception as e: logger.error(f"SupErr: {e}")
        time.sleep(10)

if __name__ == '__main__':
    ensure_license_server_running()
    threading.Thread(target=supervisor_loop, daemon=True).start()
    logger.info(
        "Monitor listening on %s:%s; managed app port=%s (set MONITOR_PORT / PORT / APP_PORT to override)",
        MONITOR_HOST,
        MONITOR_PORT,
        APP_PORT,
    )
    try:
        server = HTTPServer((MONITOR_HOST, MONITOR_PORT), MonitorHandler)
    except PermissionError as e:
        if sys.platform == "win32" and getattr(e, "winerror", None) == 10013:
            logger.error(
                "Bind failed: %s:%s — WinError 10013 often means the port is in a Windows "
                "reserved TCP range (Hyper-V / WSL / Docker). Run: "
                "netsh interface ipv4 show excludedportrange protocol=tcp\n"
                "Then set ports outside those ranges, e.g. set PORT=8780 & set MONITOR_PORT=18081",
                MONITOR_HOST,
                MONITOR_PORT,
            )
        raise
    try: server.serve_forever()
    except KeyboardInterrupt: manager.stop_app(); server.server_close()
