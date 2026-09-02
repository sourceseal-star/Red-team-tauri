#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAR ROOM — Centro de mando local sin React, sin build, sin internet.

FastAPI en :8010 que muestra el estado de todo el ecosistema SourceSeal:
- Sol (local :8006 o remoto via SOL_PUBLIC_URL)
- COM-LINK (canales disponibles via comlink_real.py)
- Dashboard (:8001)
- GHOST PHANTOM (:8002)
- Nexus (:8003/)
- SourceSeal Controller (:8005)
- Seal IA (proceso)
- Internet (conectado/desconectado)

Todo es local. No necesita internet. No necesita npm/React/build.

USO:
    python3 warroom.py                    # arranca en :8010
    python3 warroom.py --port 8010        # puerto custom
    curl http://127.0.0.1:8010/api/warroom/status   # JSON
"""

import os
import sys
import json
import time
import socket
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Paths ──
ROOT = Path(__file__).parent.resolve()
SOL_DIR = Path.home() / ".sol"

# ── Puertos de servicios ──
SERVICES = [
    {"name": "Dashboard", "port": 8001, "path": "/api/health", "critical": True},
    {"name": "GHOST PHANTOM", "port": 8002, "path": "/api/status", "critical": True},
    {"name": "Sol API", "port": 8006, "path": "/api/sol/state", "critical": False},
    {"name": "SourceSeal Controller", "port": 8005, "path": "/api/status", "critical": False},
]

# ── Internet check ──
INTERNET_HOSTS = [("8.8.8.8", 53), ("1.1.1.1", 53)]


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [WARROOM] {msg}")


def check_internet(timeout=2):
    """Verifica si hay internet."""
    for host, port in INTERNET_HOSTS:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except (socket.timeout, OSError):
            continue
    return False


def check_http(url, timeout=2):
    """Verifica si un endpoint HTTP responde. Devuelve (ok, status_code)."""
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return True, resp.getcode()
    except urllib.error.HTTPError as e:
        # 401/403 cuentan como "servicio vivo"
        return True, e.code
    except Exception:
        return False, 0


def check_process(pattern):
    """Verifica si un proceso está corriendo via pgrep."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def get_service_status(svc):
    """Obtiene el estado de un servicio."""
    url = f"http://127.0.0.1:{svc['port']}{svc['path']}"
    ok, code = check_http(url)
    return {
        "name": svc["name"],
        "port": svc["port"],
        "url": url,
        "online": ok,
        "http_code": code,
        "critical": svc["critical"],
    }


def get_sol_status():
    """Estado de Sol (local o remoto)."""
    # Intentar local primero
    ok, code = check_http("http://127.0.0.1:8006/api/sol/state")
    if ok:
        try:
            req = urllib.request.Request("http://127.0.0.1:8006/api/sol/state")
            resp = urllib.request.urlopen(req, timeout=3)
            data = json.loads(resp.read())
            return {
                "location": "local",
                "online": True,
                "data": data,
                "url": "http://127.0.0.1:8006"
            }
        except Exception:
            pass

    # Intentar remoto
    sol_url = os.environ.get("SOL_PUBLIC_URL", "")
    if sol_url:
        try:
            req = urllib.request.Request(f"{sol_url}/api/sol/state")
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            return {
                "location": "remote",
                "online": True,
                "data": data,
                "url": sol_url
            }
        except Exception:
            return {
                "location": "remote",
                "online": False,
                "url": sol_url
            }

    return {"location": "unknown", "online": False}


def get_comlink_status():
    """Estado de COM-LINK via comlink_real.py o comlink.sh."""
    try:
        comlink_real = ROOT / "comlink_real.py"
        if comlink_real.exists():
            result = subprocess.run(
                [sys.executable, str(comlink_real), "--status"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
    except Exception:
        pass

    # Fallback: comlink.sh
    try:
        comlink_sh = ROOT / "commander" / "comlink" / "comlink.sh"
        if comlink_sh.exists():
            result = subprocess.run(
                ["bash", str(comlink_sh), "status-json"],
                capture_output=True, text=True, timeout=10,
                cwd=str(comlink_sh.parent)
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
    except Exception:
        pass

    return {"available": False, "ready_count": 0, "channels": []}


def get_all_status():
    """Snapshot completo del ecosistema."""
    internet = check_internet()
    services = [get_service_status(s) for s in SERVICES]

    # Procesos adicionales
    processes = {
        "Sol API": check_process("sol_api.py"),
        "Sol Daemon": check_process("sol_daemon.py"),
        "Sol Telegram": check_process("sol_telegram_bridge"),
        "Seal IA": check_process("seal_orchestrator.py"),
        "Nexus": check_process("nexus_omni_v9.py"),
        "War Room": True,  # nosotros mismos
    }

    sol = get_sol_status()
    comlink = get_comlink_status()

    return {
        "timestamp": datetime.now().isoformat(),
        "internet": internet,
        "services": services,
        "processes": processes,
        "sol": sol,
        "comlink": comlink,
        "warroom": {
            "port": int(os.environ.get("WARROOM_PORT", "8010")),
            "pid": os.getpid(),
        }
    }


# ── Dashboard HTML (embebido, sin build) ──
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ War Room — SourceSeal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0a0a0f;
            color: #e0e0e0;
            font-family: 'Courier New', monospace;
            padding: 16px;
            min-height: 100vh;
        }
        h1 { color: #ff9500; margin-bottom: 4px; font-size: 1.5rem; }
        .subtitle { color: #666; margin-bottom: 16px; font-size: 0.8rem; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }
        .card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 14px;
        }
        .card h2 { font-size: 0.9rem; margin-bottom: 8px; color: #888; text-transform: uppercase; }
        .status-row {
            display: flex; align-items: center; gap: 8px;
            padding: 6px 0; border-bottom: 1px solid #222;
        }
        .status-row:last-child { border-bottom: none; }
        .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
        .dot.on { background: #00ff88; box-shadow: 0 0 6px #00ff88; }
        .dot.off { background: #ff4444; box-shadow: 0 0 6px #ff4444; }
        .dot.warn { background: #ffaa00; box-shadow: 0 0 6px #ffaa00; }
        .label { flex: 1; font-size: 0.85rem; }
        .value { font-size: 0.75rem; color: #666; }
        .big-status {
            text-align: center; padding: 20px; font-size: 1.2rem; font-weight: bold;
        }
        .online { color: #00ff88; }
        .offline { color: #ff4444; }
        .refresh-bar {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: #111; padding: 8px; text-align: center;
            font-size: 0.75rem; color: #555;
        }
        .channel-badge {
            display: inline-block; padding: 2px 8px; margin: 2px;
            border-radius: 4px; font-size: 0.7rem;
        }
        .channel-ready { background: #0a3; color: #fff; }
        .channel-nready { background: #333; color: #888; }
        #last-update { color: #ff9500; }
    </style>
</head>
<body>
    <h1>⚔️ WAR ROOM — SourceSeal</h1>
    <div class="subtitle">Centro de mando local — sin React, sin build, sin internet</div>
    <div id="content"><p style="color:#666">Cargando estado...</p></div>
    <div class="refresh-bar">
        Auto-refresh cada 10s — Última actualización: <span id="last-update">--</span>
    </div>
    <script>
        async function refresh() {
            try {
                const resp = await fetch('/api/warroom/status');
                const data = await resp.json();
                render(data);
            } catch(e) {
                document.getElementById('content').innerHTML = '<p style="color:#ff4444">Error: ' + e + '</p>';
            }
        }

        function dot(on) {
            return '<span class="dot ' + (on ? 'on' : 'off') + '"></span>';
        }

        function render(data) {
            let html = '';

            // Internet
            html += '<div class="grid"><div class="card" style="grid-column:1/-1">';
            html += '<h2>🌐 Internet</h2>';
            html += '<div class="big-status ' + (data.internet ? 'online' : 'offline') + '">';
            html += data.internet ? '✅ CONECTADO' : '📵 DESCONECTADO';
            html += '</div></div></div>';

            // Servicios
            html += '<div class="grid"><div class="card">';
            html += '<h2>🖥️ Servicios</h2>';
            data.services.forEach(s => {
                html += '<div class="status-row">' + dot(s.online);
                html += '<span class="label">' + s.name + ' :' + s.port + '</span>';
                html += '<span class="value">' + (s.online ? 'HTTP ' + s.http_code : 'OFFLINE') + '</span>';
                html += '</div>';
            });
            html += '</div>';

            // Procesos
            html += '<div class="card"><h2>⚙️ Procesos</h2>';
            for (const [name, running] of Object.entries(data.processes)) {
                html += '<div class="status-row">' + dot(running);
                html += '<span class="label">' + name + '</span>';
                html += '<span class="value">' + (running ? 'activo' : 'detenido') + '</span>';
                html += '</div>';
            }
            html += '</div>';

            // Sol
            html += '<div class="card"><h2>☀️ Sol</h2>';
            if (data.sol.online) {
                html += '<div class="status-row">' + dot(true);
                html += '<span class="label">' + (data.sol.location || 'local') + '</span>';
                html += '<span class="value">' + (data.sol.url || '') + '</span></div>';
                if (data.sol.data) {
                    html += '<div class="status-row"><span class="label" style="padding-left:18px;font-size:0.75rem;color:#888">Estado: ' + (data.sol.data.state || data.sol.data.status || 'OK') + '</span></div>';
                }
            } else {
                html += '<div class="status-row">' + dot(false);
                html += '<span class="label">Sin Sol disponible</span></div>';
            }
            html += '</div>';

            // COM-LINK
            html += '<div class="card"><h2>📡 COM-LINK</h2>';
            if (data.comlink.available !== false) {
                html += '<div class="status-row">' + dot(data.comlink.ready_count > 0);
                html += '<span class="label">' + (data.comlink.ready_count || 0) + '/7 canales listos</span></div>';
                let channels = data.comlink.channels || {};
                for (const [name, info] of Object.entries(channels)) {
                    let ready = info.ready;
                    html += '<div class="status-row">' + dot(ready);
                    html += '<span class="label" style="font-size:0.8rem">' + name + '</span>';
                    html += '<span class="channel-badge ' + (ready ? 'channel-ready' : 'channel-nready') + '">' + (ready ? 'OK' : 'N/A') + '</span>';
                    html += '</div>';
                }
            } else {
                html += '<div class="status-row">' + dot(false);
                html += '<span class="label">COM-LINK no disponible</span></div>';
            }
            html += '</div></div>';

            document.getElementById('content').innerHTML = html;
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }

        refresh();
        setInterval(refresh, 10000);
    </script>
</body>
</html>"""


def create_app():
    """Crea la app FastAPI o fallback HTTP."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
        import uvicorn

        app = FastAPI(title="War Room", docs_url="/docs")

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return DASHBOARD_HTML

        @app.get("/api/warroom/status")
        async def status():
            return get_all_status()

        @app.get("/api/health")
        async def health():
            return {"ok": True, "service": "warroom", "timestamp": datetime.now().isoformat()}

        return app, "fastapi"

    except ImportError:
        # Fallback: HTTP server estándar sin FastAPI
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class WarRoomHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
                elif self.path == "/api/warroom/status":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps(get_all_status(), ensure_ascii=False).encode("utf-8"))
                elif self.path == "/api/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "service": "warroom"}).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                log(f"{self.client_address[0]} {format % args}")

        return WarRoomHandler, "http_server"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="War Room — SourceSeal")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WARROOM_PORT", "8010")),
                        help="Puerto (default: 8010)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    args = parser.parse_args()

    app, mode = create_app()
    log(f"War Room arrancando en :{args.port} (modo: {mode})")

    if mode == "fastapi":
        import uvicorn
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    else:
        server = HTTPServer((args.host, args.port), app)
        log(f"HTTP server en http://{args.host}:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log("Detenido por el usuario")
            server.shutdown()


if __name__ == "__main__":
    main()
