"""
Orchestrator — Nodo Maestro Termux
Descubre nodos Replit, enruta APIs, sincroniza SQLite master
Conectado a internet via tunnel permanente
"""
import os
import json
import time
import sqlite3
import asyncio
import logging
import subprocess
from datetime import datetime
from typing import Dict, Optional
from contextlib import contextmanager
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("orchestrator")

app = FastAPI(title="Termux Orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# CONFIG — URLs de los 3 nodos Replit
# ==========================================
REPLIT_NODES = {
    "motor_cierre": {
        "url": os.getenv("REPLIT_MOTOR_URL", "http://localhost:8000"),
        "service": "Motor de Cierre (Stripe)",
        "status": "unknown",
    },
    "frontend": {
        "url": os.getenv("REPLIT_FRONTEND_URL", "http://localhost:5173"),
        "service": "Frontend Dashboard (React)",
        "status": "unknown",
    },
    "threat_intel": {
        "url": os.getenv("REPLIT_THREAT_URL", "http://localhost:8001"),
        "service": "Threat Intel Proxy (AbuseIPDB)",
        "status": "unknown",
    },
}

TUNNEL_URL = os.getenv("TUNNEL_URL", "")
TUNNEL_DOMAIN = os.getenv("TUNNEL_DOMAIN", "tu-subdomain.trycloudflare.com")

# ==========================================
# SQLITE MASTER — fuente unica de verdad
# ==========================================
DB_PATH = os.getenv("DB_PATH", "./master.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS node_status (
                node_id TEXT PRIMARY KEY,
                node_type TEXT,
                url TEXT,
                service TEXT,
                status TEXT DEFAULT 'unknown',
                last_check TEXT,
                response_time_ms INTEGER,
                metadata TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                action TEXT,
                records_synced INTEGER DEFAULT 0,
                status TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS orchestrator_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        c.execute("INSERT OR REPLACE INTO orchestrator_config (key, value) VALUES (?, ?)",
                  ("tunnel_url", TUNNEL_URL or f"https://{TUNNEL_DOMAIN}"))
        conn.commit()
        logger.info("[+] SQLite Master listo.")

init_db()

# ==========================================
# NODE DISCOVERY — health checks periodicos
# ==========================================
async def check_node(node_id: str, node_info: dict):
    import urllib.request as ur
    try:
        start = time.time()
        req = ur.Request(f"{node_info['url']}/health", headers={"User-Agent": "orchestrator"})
        resp = ur.urlopen(req, timeout=10)
        elapsed = int((time.time() - start) * 1000)
        node_info["status"] = "online"
        node_info["response_time_ms"] = elapsed

        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO node_status (node_id, node_type, url, service, status, last_check, response_time_ms)
                VALUES (?, 'replit', ?, ?, 'online', ?, ?)
            """, (node_id, node_info["url"], node_info["service"],
                  datetime.utcnow().isoformat(), elapsed))
            conn.commit()
        logger.info(f"[*] {node_id}: online ({elapsed}ms)")
    except Exception as e:
        node_info["status"] = "offline"
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO node_status (node_id, node_type, url, service, status, last_check)
                VALUES (?, 'replit', ?, ?, 'offline', ?)
            """, (node_id, node_info["url"], node_info["service"], datetime.utcnow().isoformat()))
            conn.commit()
        logger.warning(f"[!] {node_id}: offline ({e})")

async def discovery_loop():
    while True:
        for node_id, info in REPLIT_NODES.items():
            await check_node(node_id, info)
        await asyncio.sleep(30)

@app.on_event("startup")
async def startup():
    asyncio.create_task(discovery_loop())
    logger.info(f"[+] Orchestrator iniciado")

# ==========================================
# API ROUTING — proxy a nodos Replit
# ==========================================
@app.api_route("/proxy/{node_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_to_node(node_id: str, path: str, request: Request):
    if node_id not in REPLIT_NODES:
        raise HTTPException(status_code=404, detail=f"Nodo {node_id} no registrado")

    node = REPLIT_NODES[node_id]
    if node["status"] == "offline":
        raise HTTPException(status_code=503, detail=f"Nodo {node_id} offline")

    import urllib.request as ur
    target_url = f"{node['url']}/{path}"
    method = request.method
    body = await request.body() if method in ("POST", "PUT", "PATCH") else None

    try:
        headers = dict(request.headers)
        headers.pop("host", None)
        req = ur.Request(target_url, data=body, method=method, headers=headers)
        resp = ur.urlopen(req, timeout=30)
        return resp.read()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error proxy a {node_id}: {str(e)}")

# ==========================================
# DB SYNC — sincronizar con nodos
# ==========================================
@app.post("/sync/{node_id}")
async def sync_node(node_id: str):
    if node_id not in REPLIT_NODES:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")

    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO sync_log (node_id, action, status, timestamp)
            VALUES (?, 'full_sync', 'completed', ?)
        """, (node_id, datetime.utcnow().isoformat()))
        conn.commit()

    return {"status": "synced", "node_id": node_id, "timestamp": datetime.utcnow().isoformat()}

# ==========================================
# CORE SERVICES — ejecutar herramientas en Termux
# ==========================================
class CommandRequest(BaseModel):
    tool: str
    args: list = []
    timeout: int = 120

@app.post("/core/exec")
async def exec_tool(cmd: CommandRequest):
    allowed = ["nmap", "aircrack-ng", "airodump-ng", "ffmpeg", "tcpdump", "iwlist", "ifconfig", "ping", "curl"]
    if cmd.tool not in allowed:
        raise HTTPException(status_code=403, detail=f"Herramienta no permitida: {cmd.tool}")

    try:
        result = subprocess.run(
            [cmd.tool] + cmd.args,
            capture_output=True, text=True, timeout=cmd.timeout
        )
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO sync_log (node_id, action, status, timestamp)
                VALUES ('local', ?, ?, ?)
            """, (f"exec:{cmd.tool}", "success" if result.returncode == 0 else "failed",
                  datetime.utcnow().isoformat()))
            conn.commit()

        return {
            "tool": cmd.tool,
            "returncode": result.returncode,
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
        }
    except FileNotFoundError:
        return {"tool": cmd.tool, "error": f"{cmd.tool} no instalado en Termux"}
    except subprocess.TimeoutExpired:
        return {"tool": cmd.tool, "error": "timeout", "timeout_sec": cmd.timeout}

# ==========================================
# ENDPOINTS ORCHESTRATOR
# ==========================================
@app.get("/nodes")
async def list_nodes():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM node_status ORDER BY last_check DESC")
        rows = c.fetchall()
    return {
        "nodes": [dict(r) for r in rows],
        "replit_nodes": REPLIT_NODES,
        "tunnel_url": TUNNEL_URL or f"https://{TUNNEL_DOMAIN}",
    }

@app.get("/nodes/{node_id}")
async def get_node(node_id: str):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM node_status WHERE node_id = ?", (node_id,))
        row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    return dict(row)

@app.get("/sync/log")
async def sync_log(limit: int = 50):
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM sync_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = c.fetchall()
    return {"logs": [dict(r) for r in rows]}

@app.get("/health")
async def health():
    online = sum(1 for n in REPLIT_NODES.values() if n["status"] == "online")
    return {
        "status": "ok",
        "version": "1.0.0",
        "role": "master",
        "replit_nodes_online": online,
        "replit_nodes_total": len(REPLIT_NODES),
        "tunnel": TUNNEL_URL or TUNNEL_DOMAIN,
        "db_path": DB_PATH,
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
