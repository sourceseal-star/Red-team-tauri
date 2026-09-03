#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMMANDER Dashboard Server v1.0
===============================
Dashboard web unificado para COMMANDER en puerto :8003.
Expone todos los módulos: network audit, OSINT, cameras, forensics,
comlink, tactical, seal anchoring.
Se conecta al backend de Red-team-tauri (:8001) para funciones compartidas.
"""

import os
import sys
import json
import time
import sqlite3
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Query, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# ─── Config ──────────────────────────────────────────────
PORT = int(os.environ.get("COMMANDER_PORT", "8003"))
HOST = os.environ.get("COMMANDER_HOST", "0.0.0.0")
REDTEAM_API = os.environ.get("BACKEND_API", "http://localhost:8001")
ROOT = Path(__file__).parent
DB_PATH = os.path.expanduser("~/commander.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("commander.dashboard")

# ─── App ─────────────────────────────────────────────────
app = FastAPI(title="COMMANDER Dashboard", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── DB Helper ────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            scan_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            data_json TEXT NOT NULL,
            hash TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            checkpoint_data TEXT
        );
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Importar módulos de COMMANDER (lazy) ─────────────────
def import_commander():
    """Importa funciones de commander.py sin ejecutar main()"""
    sys.path.insert(0, str(ROOT))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("commander_mod", ROOT / "commander.py")
        mod = importlib.util.module_from_spec(spec)
        # Patch sys.modules para que no ejecute __main__
        mod.__name__ = "commander_mod"
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        logger.error(f"Error importando commander.py: {e}")
        return None

# ─── Models ──────────────────────────────────────────────
class ScanRequest(BaseModel):
    target: str
    ports: str = "22,80,443,3306,8080,554,21,25,53,139,445,3389"
    email: Optional[str] = None

class OSINTRequest(BaseModel):
    query: str
    type: str = "ip"  # ip | domain | email

class HuntRequest(BaseModel):
    query: str
    playbook: str = "generic"
    max_results: int = 100

# ─── Endpoints API ────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "commander-dashboard",
        "version": "1.0",
        "port": PORT,
        "redteam_api": REDTEAM_API,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
async def status():
    """Estado completo del sistema COMMANDER."""
    db = get_db()
    scans = db.execute("SELECT COUNT(*) as c FROM audits").fetchone()["c"]
    pending = db.execute("SELECT COUNT(*) as c FROM audits WHERE status != 'completed'").fetchone()["c"]
    completed = db.execute("SELECT COUNT(*) as c FROM audits WHERE status='completed'").fetchone()["c"]
    db.close()
    return {
        "scans_total": scans,
        "scans_pending": pending,
        "scans_completed": completed,
        "db_path": DB_PATH,
        "redteam_api": REDTEAM_API,
        "modules": {
            "commander": True,
            "tactical": (ROOT / "sourceseal_tactical.py").exists(),
            "comlink": (ROOT / "comlink" / "comlink.sh").exists(),
            "osiris": (ROOT / "sourceseal-osiris").exists(),
            "phantom": os.environ.get("MASTER_URL", ""),
        }
    }

# ─── Network Audit ───────────────────────────────────────
@app.post("/api/scan/network")
async def scan_network(req: ScanRequest):
    """Escaneo de red usando nmap via commander.py."""
    try:
        import subprocess
        command = [sys.executable, str(ROOT / "commander.py"), "--auto", req.target]
        if req.email:
            command.extend(["--email", req.email])
        command.append("--debug")
        result = subprocess.run(
            command,
            capture_output=True, text=True, timeout=120,
            cwd=str(ROOT)
        )
        return {
            "target": req.target,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Timeout 120s"}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/scans")
async def list_scans():
    """Lista todas las auditorías guardadas."""
    db = get_db()
    rows = db.execute("""
        SELECT id, target, scan_type, status, data_json AS data, hash,
               timestamp AS created_date, timestamp AS updated_date,
               checkpoint_data
        FROM audits
        ORDER BY timestamp DESC
        LIMIT 50
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.get("/api/scans/{scan_id}")
async def get_scan(scan_id: int):
    """Detalle de una auditoría."""
    db = get_db()
    row = db.execute("""
        SELECT id, target, scan_type, status, data_json AS data, hash,
               timestamp AS created_date, timestamp AS updated_date,
               checkpoint_data
        FROM audits
        WHERE id=?
    """, (scan_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Auditoría no encontrada")
    db.close()
    checkpoint = row["checkpoint_data"]
    phase = None
    if checkpoint:
        try:
            phase = json.loads(checkpoint).get("phase")
        except (TypeError, json.JSONDecodeError):
            pass
    return {
        "scan": dict(row),
        "checkpoints": [{
            "scan_id": scan_id,
            "phase": phase,
            "data": checkpoint,
            "created_date": row["updated_date"],
        }] if checkpoint else [],
    }

@app.post("/api/scans/{scan_id}/resume")
async def resume_scan(scan_id: int):
    """Reanuda una auditoría pausada."""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / "commander.py"), "--resume", str(scan_id), "--debug"],
            capture_output=True, text=True, timeout=120,
            cwd=str(ROOT)
        )
        return {"stdout": result.stdout[-2000:], "returncode": result.returncode}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ─── OSINT ───────────────────────────────────────────────
@app.post("/api/osint")
async def osint_lookup(req: OSINTRequest):
    """OSINT lookup — delega a commander.py o al backend Red-team-tauri."""
    if req.type == "ip":
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(ROOT / "commander.py"), "--osint-ip", req.query, "--debug"],
                capture_output=True, text=True, timeout=60,
                cwd=str(ROOT)
            )
            return {"type": "ip", "query": req.query, "output": result.stdout[-3000:]}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    elif req.type == "domain":
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(ROOT / "commander.py"), "--osint-domain", req.query, "--debug"],
                capture_output=True, text=True, timeout=60,
                cwd=str(ROOT)
            )
            return {"type": "domain", "query": req.query, "output": result.stdout[-3000:]}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    elif req.type == "email":
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(ROOT / "commander.py"), "--osint-email", req.query, "--debug"],
                capture_output=True, text=True, timeout=60,
                cwd=str(ROOT)
            )
            return {"type": "email", "query": req.query, "output": result.stdout[-3000:]}
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"error": "tipo inválido (ip|domain|email)"}, status_code=400)

# ─── Proxy a Red-team-tauri ───────────────────────────────
@app.api_route("/api/redteam/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_redteam(path: str):
    """Proxy al backend de Red-team-tauri (:8001)."""
    import httpx
    url = f"{REDTEAM_API}/api/{path}"
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.request("GET", url)
            return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e), "url": url}, status_code=502)

@app.get("/api/redteam/health")
async def redteam_health():
    """Verifica si el backend de Red-team-tauri está disponible."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{REDTEAM_API}/api/health")
            return {"available": True, "status": resp.json()}
    except Exception as e:
        return {"available": False, "error": str(e)}

# ─── IoT/Cámaras (proxy a Red-team-tauri) ─────────────────
@app.get("/api/iot/auto-access")
async def iot_auto_access(ip: str, port: int = 80):
    """Proxy a /api/iot/auto-access del dashboard."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.get(f"{REDTEAM_API}/api/iot/auto-access", params={"ip": ip, "port": port})
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/iot/auto-access-batch")
async def iot_batch(body: dict = Body(...)):
    """Proxy a /api/iot/auto-access-batch del dashboard."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{REDTEAM_API}/api/iot/auto-access-batch", json=body)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ─── KRAKEN (proxy al dashboard :8001) ───────────────────
@app.get("/api/kraken/scan")
async def kraken_scan(target: str = "192.168.1.0/24"):
    """Ejecuta escaneo KRAKEN NSE contra un target."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.get(f"{REDTEAM_API}/api/kraken/scan", params={"target": target})
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/kraken/results")
async def kraken_results(limit: int = 50):
    """Resultados almacenados de KRAKEN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.get(f"{REDTEAM_API}/api/kraken/results", params={"limit": limit})
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/kraken/priorities")
async def kraken_priorities():
    """IPs priorizadas por exploits exitosos."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/kraken/priorities")
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/kraken/scripts")
async def kraken_scripts():
    """Lista de NSE scripts disponibles."""
    return {
        "scripts": [
            "ssh-brute", "ftp-anon", "ftp-brute",
            "smb-os-discovery", "smb-enum-shares", "smb-vuln-*",
            "http-auth-finder", "http-vuln-*",
            "rtsp-url-brute", "mysql-empty-password",
            "pgsql-brute", "redis-info",
            "rdp-vuln-ms12-020", "snmp-info",
        ]
    }

@app.post("/api/kraken/daemon/start")
async def kraken_daemon_start(target: str = "192.168.1.0/24", interval: int = 3600):
    """Inicia el daemon de escaneo periódico KRAKEN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(f"{REDTEAM_API}/api/kraken/daemon/start",
                                params={"target": target, "interval": interval})
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/kraken/daemon/stop")
async def kraken_daemon_stop():
    """Detiene el daemon KRAKEN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(f"{REDTEAM_API}/api/kraken/daemon/stop")
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/kraken/daemon/status")
async def kraken_daemon_status():
    """Estado del daemon KRAKEN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(f"{REDTEAM_API}/api/kraken/daemon/status")
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ─── LEVIATHAN (proxy al dashboard :8001) ────────────────
@app.get("/api/leviathan/status")
async def leviathan_status():
    """Estado de LEVIATHAN v3.0."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/status")
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/leviathan/modules")
async def leviathan_modules():
    """Lista los módulos cargados de LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/modules")
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/leviathan/scan")
async def leviathan_scan(body: dict = Body(...)):
    """Ejecuta un escaneo LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{REDTEAM_API}/api/leviathan/scan", json=body)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/leviathan/scan/network")
async def leviathan_scan_network(body: dict = Body(...)):
    """Escaneo de red LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{REDTEAM_API}/api/leviathan/scan/network", json=body)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/leviathan/scan/cameras")
async def leviathan_scan_cameras(body: dict = Body(...)):
    """Escaneo de cámaras LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{REDTEAM_API}/api/leviathan/scan/cameras", json=body)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/leviathan/cameras")
async def leviathan_cameras(limit: int = 100):
    """Cámaras detectadas por LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/cameras", params={"limit": limit})
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.post("/api/leviathan/exploit")
async def leviathan_exploit(body: dict = Body(...)):
    """Ejecuta un exploit LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(f"{REDTEAM_API}/api/leviathan/exploit", json=body)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/leviathan/scans")
async def leviathan_scans(limit: int = 50):
    """Historial de escaneos LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/scans", params={"limit": limit})
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/leviathan/alerts")
async def leviathan_alerts(acknowledged: Optional[bool] = None):
    """Alertas de seguridad de LEVIATHAN."""
    import httpx
    try:
        params = {}
        if acknowledged is not None:
            params["acknowledged"] = acknowledged
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/alerts", params=params)
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

@app.get("/api/leviathan/threat-map")
async def leviathan_threat_map():
    """Mapa de amenazas LEVIATHAN."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/threat-map")
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ─── IoT CAMERAS (fix del 404) ───────────────────────────
@app.get("/api/iot/cameras")
async def iot_cameras():
    """Lista las cámaras IoT detectadas (proxy al dashboard)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            # El dashboard tiene /api/leviathan/cameras que es la fuente real
            resp = await c.get(f"{REDTEAM_API}/api/leviathan/cameras", params={"limit": 200})
            cam_data = resp.json()
            # También intentar /api/iot/auto-access para conectar resultados
            return cam_data
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ─── COM-LINK ────────────────────────────────────────────
@app.get("/api/comlink/status")
async def comlink_status():
    """Estado de COM-LINK (canaales mesh)."""
    comlink = ROOT / "comlink" / "comlink.sh"
    if not comlink.exists():
        return {"available": False}
    return {
        "available": True,
        "channels": ["telegram", "sms", "voip", "mesh_wifi", "mesh_bluetooth", "radio", "satellite"],
        "script": str(comlink)
    }

@app.post("/api/comlink/send")
async def comlink_send(body: dict = Body(...)):
    """Enviar mensaje via COM-LINK."""
    import subprocess
    channel = body.get("channel", "telegram")
    message = body.get("message", "")
    try:
        result = subprocess.run(
            ["bash", str(ROOT / "comlink" / "comlink.sh"), "send", channel, message],
            capture_output=True, text=True, timeout=30,
            cwd=str(ROOT / "comlink")
        )
        return {"stdout": result.stdout[-500:], "returncode": result.returncode}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ─── PHANTOM (si hay master corriendo en :8002) ──────────
@app.get("/api/phantom/status")
async def phantom_status():
    """Estado del GHOST HUNTER PHANTOM Master (:8002)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get("http://localhost:8002/api/status")
            return {"available": True, "status": resp.json()}
    except Exception:
        return {"available": False}

@app.post("/api/phantom/hunt")
async def phantom_hunt(req: HuntRequest):
    """Iniciar caza via PHANTOM Master."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post("http://localhost:8002/api/hunt/start", json={
                "query": req.query,
                "playbook": req.playbook,
                "max_results": req.max_results
            })
            return resp.json()
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)

# ─── Dashboard HTML ─────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>COMMANDER Dashboard</title>
<style>
:root { --bg: #0a0e1a; --card: #111827; --border: #1f2937; --cyan: #06b6d4;
  --green: #10b981; --red: #ef4444; --yellow: #f59e0b; --purple: #8b5cf6;
  --text: #e5e7eb; --muted: #6b7280; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; }
.header { background: var(--card); border-bottom: 1px solid var(--border); padding: 12px 20px;
  display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 18px; color: var(--cyan); }
.header .ports { font-size: 12px; color: var(--muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px; padding: 16px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
.card h2 { font-size: 14px; color: var(--cyan); margin-bottom: 8px; }
.card .status { font-size: 12px; color: var(--muted); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: bold; }
.badge-ok { background: rgba(16,185,129,.2); color: var(--green); }
.badge-err { background: rgba(239,68,68,.2); color: var(--red); }
.badge-warn { background: rgba(245,158,11,.2); color: var(--yellow); }
.btn { background: var(--cyan); color: var(--bg); border: none; padding: 8px 16px;
  border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: bold; }
.btn:hover { opacity: .9; }
.btn-purple { background: var(--purple); }
.btn-red { background: var(--red); color: white; }
input, select, textarea { background: var(--bg); border: 1px solid var(--border); color: var(--text);
  padding: 6px 10px; border-radius: 4px; font-size: 12px; width: 100%; margin: 4px 0; }
.row { display: flex; gap: 8px; align-items: center; }
.log { background: #000; color: #0f0; padding: 8px; border-radius: 4px; font-family: monospace;
  font-size: 11px; max-height: 200px; overflow-y: auto; margin-top: 8px; }
.stats { display: flex; gap: 12px; margin: 8px 0; }
.stat { text-align: center; }
.stat .num { font-size: 24px; font-weight: bold; }
.stat .lbl { font-size: 10px; color: var(--muted); }
</style>
</head>
<body>
<div class="header">
  <h1>📡 COMMANDER Dashboard v1.0</h1>
  <div class="ports">:8003 | → Red-team :8001 | → PHANTOM :8002</div>
</div>

<div class="grid">
  <!-- Estado del sistema -->
  <div class="card">
    <h2>📊 Estado del Sistema</h2>
    <div id="status">Cargando...</div>
  </div>

  <!-- Red-team-tauri -->
  <div class="card">
    <h2>🔗 Red-team-tauri (:8001)</h2>
    <div id="redteam-status">Verificando...</div>
    <button class="btn" onclick="window.open('http://localhost:8001','_blank')">Abrir Dashboard</button>
  </div>

  <!-- PHANTOM -->
  <div class="card">
    <h2>👻 GHOST PHANTOM (:8002)</h2>
    <div id="phantom-status">Verificando...</div>
  </div>

  <!-- Network Audit -->
  <div class="card">
    <h2>🎯 Escaneo de Red</h2>
    <input type="text" id="scan-target" placeholder="192.168.1.0/24" value="192.168.1.0/24">
    <button class="btn" onclick="startScan()">Iniciar Auditoría</button>
    <div id="scan-result" class="log" style="display:none;"></div>
  </div>

  <!-- OSINT -->
  <div class="card">
    <h2>🔍 OSINT</h2>
    <select id="osint-type"><option value="ip">IP</option><option value="domain">Dominio</option><option value="email">Email</option></select>
    <input type="text" id="osint-query" placeholder="8.8.8.8">
    <button class="btn" onclick="runOSINT()">Analizar</button>
    <div id="osint-result" class="log" style="display:none;"></div>
  </div>

  <!-- IoT Cámaras -->
  <div class="card">
    <h2>📷 IoT / Cámaras</h2>
    <input type="text" id="cam-ip" placeholder="192.168.1.100">
    <input type="number" id="cam-port" placeholder="80" value="80">
    <button class="btn" onclick="auditCamera()">Auditar Cámara</button>
    <button class="btn btn-purple" onclick="batchScan()">Escanear Red</button>
    <div id="cam-result" class="log" style="display:none;"></div>
  </div>

  <!-- PHANTOM Hunt -->
  <div class="card">
    <h2>👻 Caza PHANTOM</h2>
    <input type="text" id="hunt-query" placeholder="192.168.1.0/24">
    <select id="hunt-playbook">
      <option value="generic">Genérico</option>
      <option value="hikvision">Hikvision</option>
      <option value="dahua">Dahua</option>
      <option value="router">Router</option>
    </select>
    <button class="btn btn-purple" onclick="startHunt()">Iniciar Caza</button>
    <div id="hunt-result" class="log" style="display:none;"></div>
  </div>

  <!-- COM-LINK -->
  <div class="card">
    <h2>📡 COM-LINK Mesh</h2>
    <div id="comlink-status">Verificando...</div>
  </div>

  <!-- Auditorías -->
  <div class="card">
    <h2>📋 Auditorías Guardadas</h2>
    <div id="scans-list">Cargando...</div>
  </div>
</div>

<script>
const API = '';
async function api(path, opts={}) {
  try {
    const r = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
    return await r.json();
  } catch(e) { return {error: e.message}; }
}

async function refresh() {
  // Status
  const s = await api('/api/status');
  document.getElementById('status').innerHTML = `
    <div class="stats">
      <div class="stat"><div class="num" style="color:var(--cyan)">${s.scans_total||0}</div><div class="lbl">Auditorías</div></div>
      <div class="stat"><div class="num" style="color:var(--yellow)">${s.scans_pending||0}</div><div class="lbl">Pendientes</div></div>
      <div class="stat"><div class="num" style="color:var(--green)">${s.scans_completed||0}</div><div class="lbl">Completas</div></div>
    </div>
    <div class="status">DB: ${s.db_path||'?'}</div>
    <div class="status">Tactical: ${s.modules?.tactical?'<span class="badge badge-ok">OK</span>':'<span class="badge badge-err">NO</span>'}</div>
    <div class="status">Comlink: ${s.modules?.comlink?'<span class="badge badge-ok">OK</span>':'<span class="badge badge-err">NO</span>'}</div>
    <div class="status">Osiris: ${s.modules?.osiris?'<span class="badge badge-ok">OK</span>':'<span class="badge badge-err">NO</span>'}</div>
  `;

  // Red-team
  const rt = await api('/api/redteam/health');
  document.getElementById('redteam-status').innerHTML = rt.available
    ? '<span class="badge badge-ok">DISPONIBLE</span> ' + (rt.status?.status||'')
    : '<span class="badge badge-err">NO DISPONIBLE</span>';

  // PHANTOM
  const ph = await api('/api/phantom/status');
  document.getElementById('phantom-status').innerHTML = ph.available
    ? `<span class="badge badge-ok">ACTIVO</span> Nodos: ${ph.status?.active_nodes||0} | Cola: ${ph.status?.queue_size||0}`
    : '<span class="badge badge-warn">INACTIVO</span>';

  // Comlink
  const cl = await api('/api/comlink/status');
  document.getElementById('comlink-status').innerHTML = cl.available
    ? `<span class="badge badge-ok">OK</span> Canales: ${cl.channels?.join(', ')}`
    : '<span class="badge badge-err">NO</span>';

  // Scans
  const scans = await api('/api/scans');
  if (Array.isArray(scans) && scans.length > 0) {
    document.getElementById('scans-list').innerHTML = scans.slice(0,10).map(s =>
      `<div class="status">#${s.id} ${s.target} — <span class="badge ${s.status==='completed'?'badge-ok':'badge-warn'}">${s.status}</span></div>`
    ).join('');
  } else {
    document.getElementById('scans-list').innerHTML = '<div class="status">Sin auditorías</div>';
  }
}

async function startScan() {
  const t = document.getElementById('scan-target').value;
  const el = document.getElementById('scan-result');
  el.style.display = 'block';
  el.textContent = 'Escaneando ' + t + '...';
  const r = await api('/api/scan/network', {method:'POST', body: JSON.stringify({target:t})});
  el.textContent = JSON.stringify(r, null, 2).substring(0, 2000);
}

async function runOSINT() {
  const type = document.getElementById('osint-type').value;
  const query = document.getElementById('osint-query').value;
  const el = document.getElementById('osint-result');
  el.style.display = 'block';
  el.textContent = 'Analizando ' + query + '...';
  const r = await api('/api/osint', {method:'POST', body: JSON.stringify({type, query})});
  el.textContent = JSON.stringify(r, null, 2).substring(0, 2000);
}

async function auditCamera() {
  const ip = document.getElementById('cam-ip').value;
  const port = document.getElementById('cam-port').value;
  const el = document.getElementById('cam-result');
  el.style.display = 'block';
  el.textContent = 'Auditando ' + ip + ':' + port + '...';
  const r = await api(`/api/iot/auto-access?ip=${ip}&port=${port}`);
  el.textContent = JSON.stringify(r, null, 2).substring(0, 2000);
}

async function batchScan() {
  const el = document.getElementById('cam-result');
  el.style.display = 'block';
  el.textContent = 'Escaneando red completa...';
  const r = await api('/api/iot/auto-access-batch', {method:'POST', body: JSON.stringify({cidr:'192.168.1.0/24'})});
  el.textContent = JSON.stringify(r, null, 2).substring(0, 3000);
}

async function startHunt() {
  const query = document.getElementById('hunt-query').value;
  const playbook = document.getElementById('hunt-playbook').value;
  const el = document.getElementById('hunt-result');
  el.style.display = 'block';
  el.textContent = 'Iniciando caza...';
  const r = await api('/api/phantom/hunt', {method:'POST', body: JSON.stringify({query, playbook, max_results:50})});
  el.textContent = JSON.stringify(r, null, 2).substring(0, 2000);
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

# ─── Main ────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"COMMANDER Dashboard v1.0 — iniciando en :{PORT}")
    logger.info(f"Backend Red-team-tauri: {REDTEAM_API}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
