import os
import json
import time
import asyncio
import aiohttp
import sqlite3
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

app = FastAPI(title="SourceSeal Orchestrator", version="1.0")

# ==========================================
# CONFIGURACION DE NODOS
# ==========================================
NODES_CONFIG = {
    "replit_motor": {
        "name": "Motor de Cierre",
        "url": os.getenv("NODE_MOTOR_URL", "https://tu-motor.replit.app"),
        "api_key": os.getenv("NODE_MOTOR_KEY", ""),
        "type": "replit",
        "services": ["stripe", "openai", "checkout"],
        "priority": 1,
    },
    "replit_frontend": {
        "name": "Dashboard Web",
        "url": os.getenv("NODE_FRONTEND_URL", "https://tu-frontend.replit.app"),
        "api_key": "",
        "type": "replit",
        "services": ["ui", "websocket"],
        "priority": 2,
    },
    "replit_intel": {
        "name": "Threat Intel Proxy",
        "url": os.getenv("NODE_INTEL_URL", ""),
        "api_key": os.getenv("NODE_INTEL_KEY", ""),
        "type": "replit",
        "services": ["abuseipdb", "shodan"],
        "priority": 3,
    },
}

DB_PATH = "./orchestrator.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY, name TEXT, url TEXT, type TEXT,
            status TEXT DEFAULT 'unknown', last_seen TEXT, latency REAL,
            services TEXT, errors INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, source TEXT, event_type TEXT,
            payload TEXT, delivered_to TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==========================================
# MODELOS
# ==========================================
class NodeStatus(BaseModel):
    id: str
    name: str
    url: str
    status: str
    latency: float
    services: List[str]
    last_seen: str

class ProxyRequest(BaseModel):
    target_node: str
    endpoint: str
    method: str = "GET"
    payload: Optional[dict] = None

class EventBroadcast(BaseModel):
    event_type: str
    payload: dict
    target_nodes: Optional[List[str]] = None

# ==========================================
# HEALTH CHECK DE NODOS
# ==========================================
async def check_node_health(node_id: str, config: dict) -> dict:
    start = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{config['url']}/health",
                headers={"Authorization": f"Bearer {config['api_key']}"} if config['api_key'] else {},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                latency = (time.time() - start) * 1000
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "online",
                        "latency": round(latency, 2),
                        "version": data.get("version", "unknown"),
                        "services": config['services']
                    }
                return {"status": "degraded", "latency": round(latency, 2), "services": config['services']}
    except Exception as e:
        return {"status": "offline", "latency": -1, "error": str(e), "services": config['services']}

async def health_check_loop():
    while True:
        for node_id, config in NODES_CONFIG.items():
            result = await check_node_health(node_id, config)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO nodes (id, name, url, type, status, last_seen, latency, services)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id, config['name'], config['url'], config['type'],
                result['status'], datetime.utcnow().isoformat(),
                result['latency'], json.dumps(result['services'])
            ))
            if result['status'] == 'offline':
                c.execute("UPDATE nodes SET errors = errors + 1 WHERE id = ?", (node_id,))
            conn.commit()
            conn.close()
            print(f"[{node_id}] {result['status']} | {result.get('latency', 'N/A')}ms")
        await asyncio.sleep(30)

# ==========================================
# PROXY ENTRE NODOS
# ==========================================
@app.post("/proxy")
async def proxy_request(req: ProxyRequest):
    """Enruta una peticion a otro nodo de la federacion."""
    config = NODES_CONFIG.get(req.target_node)
    if not config:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    
    url = f"{config['url']}{req.endpoint}"
    headers = {"Authorization": f"Bearer {config['api_key']}"} if config['api_key'] else {}
    
    try:
        async with aiohttp.ClientSession() as session:
            method = getattr(session, req.method.lower())
            kwargs = {"headers": headers}
            if req.payload:
                kwargs["json"] = req.payload
            
            async with method(url, **kwargs) as resp:
                body = await resp.json()
                return {
                    "proxied": True,
                    "target": req.target_node,
                    "status": resp.status,
                    "response": body
                }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error proxy: {str(e)}")

# ==========================================
# BROADCAST DE EVENTOS
# ==========================================
@app.post("/broadcast")
async def broadcast_event(event: EventBroadcast):
    """Envia un evento a todos los nodos suscritos."""
    targets = event.target_nodes or list(NODES_CONFIG.keys())
    results = []
    
    for node_id in targets:
        config = NODES_CONFIG.get(node_id)
        if not config:
            continue
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config['url']}/webhook/event",
                    headers={"Authorization": f"Bearer {config['api_key']}"} if config['api_key'] else {},
                    json={"event_type": event.event_type, "payload": event.payload},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    results.append({"node": node_id, "status": resp.status})
        except Exception as e:
            results.append({"node": node_id, "status": "failed", "error": str(e)})
    
    # Guardar en DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO events (timestamp, source, event_type, payload, delivered_to)
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(), "orchestrator",
        event.event_type, json.dumps(event.payload), json.dumps(targets)
    ))
    conn.commit()
    conn.close()
    
    return {"broadcasted": True, "results": results}

# ==========================================
# ENDPOINTS LOCALES
# ==========================================
@app.get("/nodes")
async def list_nodes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM nodes ORDER BY last_seen DESC")
    rows = c.fetchall()
    conn.close()
    return {"nodes": [
        {"id": r[0], "name": r[1], "url": r[2], "status": r[4],
         "latency": r[6], "services": json.loads(r[7] or "[]")}
        for r in rows
    ]}

@app.get("/events")
async def list_events(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return {"events": [
        {"id": r[0], "timestamp": r[1], "source": r[2], "type": r[3], "payload": r[4]}
        for r in rows
    ]}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "role": "orchestrator",
        "nodes_monitored": len(NODES_CONFIG),
        "timestamp": datetime.utcnow().isoformat()
    }

# ==========================================
# ARRANQUE
# ==========================================
@app.on_event("startup")
async def startup():
    asyncio.create_task(health_check_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
