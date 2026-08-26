"""
GHOST HUNTER v3.0 PHANTOM — Node Worker
Usa los módulos REALES de Red-team-tauri:
  - enhanced_recon.scan_camera_full (detección de cámara + credenciales + RTSP)
  - backend.dashboard_server shodan_lookup (Shodan + AlienVault OTX fallback)
  - backend.dashboard_server geo_lookup (ipwho.is)
No hay stubs. Todo son llamadas reales al backend :8001.
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI

# ─── Config ──────────────────────────────────────────────
NODE_ID = os.environ.get("NODE_ID", f"node_{os.getpid()}")
MASTER_URL = os.environ.get("MASTER_URL", "http://localhost:8002")
BACKEND_API = os.environ.get("BACKEND_API", "http://localhost:8001")
API_KEY = os.environ.get("REDTEAM_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}
PLAYBOOKS_DIR = Path(__file__).parent / "playbooks"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(f"phantom.node.{NODE_ID}")

# ─── Playbook Loader ─────────────────────────────────────
class PlaybookLoader:
    def __init__(self, pdir: Path = PLAYBOOKS_DIR):
        self.playbooks = {}
        if pdir.exists():
            for f in pdir.glob("*.json"):
                try:
                    self.playbooks[f.stem] = json.loads(f.read_text())
                except Exception as e:
                    logger.error(f"Playbook {f.name} inválido: {e}")
        logger.info(f"Playbooks: {list(self.playbooks.keys())}")

    def get(self, name: str) -> Optional[dict]:
        return self.playbooks.get(name) or self.playbooks.get("generic")


playbooks = PlaybookLoader()

# ─── Acciones reales (llaman al backend :8001) ───────────
async def action_shodan_search(query: str, limit: int = 100) -> List[Dict]:
    """Búsqueda en Shodan o AlienVault OTX via backend existente"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(
                f"{BACKEND_API}/api/osint/shodan",
                params={"query": query},
                headers=HEADERS,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                # Normalizar formato
                normalized = []
                for r in results[:limit]:
                    ip = r.get("ip_str") or r.get("ip") or r.get("target")
                    port = r.get("port", 554)
                    if ip:
                        normalized.append({
                            "ip": ip,
                            "port": port,
                            "org": r.get("org", ""),
                            "vendor": _guess_vendor(r),
                            "source": data.get("source", "shodan"),
                        })
                logger.info(f"Shodan: {len(normalized)} resultados para '{query}'")
                return normalized
            return []
    except Exception as e:
        logger.error(f"Shodan error: {e}")
        return []


async def action_camera_scan(target: Dict) -> Dict:
    """Escaneo completo de cámara via backend enhanced_recon"""
    ip = target.get("ip")
    port = target.get("port", 80)
    if not ip:
        return target

    try:
        async with httpx.AsyncClient(timeout=20) as c:
            # Probar scan_camera_full via API
            resp = await c.get(
                f"{BACKEND_API}/api/enhanced/camera/{ip}",
                params={"port": port},
                headers=HEADERS,
            )
            if resp.status_code == 200:
                cam = resp.json()
                target.update({
                    "brand": cam.get("brand", "unknown"),
                    "accessible_urls": cam.get("accessible_urls", []),
                    "working_credentials": cam.get("working_credentials"),
                    "rtsp_working": cam.get("rtsp_working"),
                    "snapshot_url": cam.get("snapshot_url"),
                    "vulnerable": bool(cam.get("working_credentials")),
                    "severity": "critical" if cam.get("working_credentials") else "medium",
                })
                logger.info(f"Cámara {ip}: brand={cam.get('brand')}, creds={'SI' if cam.get('working_credentials') else 'NO'}")
            else:
                # Fallback: usar /api/iot
                resp2 = await c.get(f"{BACKEND_API}/api/iot", params={"ip": ip}, headers=HEADERS)
                if resp2.status_code == 200:
                    iot = resp2.json()
                    target.update({
                        "ports": iot.get("open_ports", []),
                        "camera_detected": iot.get("camera_detected", False),
                        "rtsp_url": iot.get("rtsp_url"),
                        "severity": "high" if iot.get("camera_detected") else "low",
                    })
    except Exception as e:
        logger.error(f"Camera scan error {ip}: {e}")
    return target


async def action_geo_lookup(target: Dict) -> Dict:
    """Geolocalización via backend ipwho.is"""
    ip = target.get("ip")
    if not ip:
        return target
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(f"{BACKEND_API}/api/geo", params={"ip": ip}, headers=HEADERS)
            if resp.status_code == 200:
                geo = resp.json()
                target["geo"] = {
                    "country": geo.get("country", "?"),
                    "city": geo.get("city", "?"),
                    "isp": geo.get("connection", {}).get("isp", "?"),
                    "lat": geo.get("latitude"),
                    "lon": geo.get("longitude"),
                    "is_proxy": geo.get("is_proxy", False),
                }
                logger.info(f"Geo {ip}: {geo.get('country')}, {geo.get('city')}")
    except Exception as e:
        logger.error(f"Geo error {ip}: {e}")
    return target


def _guess_vendor(r: dict) -> str:
    """Infiere vendor del campo org/product de Shodan"""
    org = (r.get("org") or "").lower()
    data = (r.get("data") or "").lower()
    product = (r.get("product") or "").lower()
    combined = f"{org} {data} {product}"
    if "hikvision" in combined:
        return "Hikvision"
    if "dahua" in combined:
        return "Dahua"
    if "axis" in combined:
        return "Axis"
    if "uniview" in combined:
        return "Uniview"
    return "unknown"


# ─── Task Executor ───────────────────────────────────────
async def execute_task(task: Dict, master_ws=None) -> Dict:
    """Ejecuta una tarea completa siguiendo el playbook"""
    task_id = task["id"]
    playbook = playbooks.get(task.get("playbook", "generic"))
    results: List[Dict] = []

    logger.info(f"Ejecutando tarea {task_id} con playbook '{playbook.get('name', '?')}'")

    # Notificar inicio
    if master_ws:
        await _send_update(master_ws, task_id, {"status": "running"})

    for step in playbook.get("steps", []):
        action = step.get("action")
        params = step.get("params", {})
        logger.info(f"  Paso: {step.get('name', action)}")

        if action == "shodan_search":
            query = params.get("query", task["query"])
            limit = params.get("limit", task.get("max_results", 100))
            results = await action_shodan_search(query, limit)

        elif action == "camera_scan":
            # Escanear cada resultado
            for i, target in enumerate(results):
                results[i] = await action_camera_scan(target)

        elif action == "geo_lookup":
            for i, target in enumerate(results):
                results[i] = await action_geo_lookup(target)

        elif action == "report":
            severity = params.get("severity", "high")
            vuln_count = sum(1 for r in results if r.get("vulnerable"))
            report = {
                "type": "hunt_report",
                "task_id": task_id,
                "target": task.get("query"),
                "total_targets": len(results),
                "vulnerable_targets": vuln_count,
                "severity": severity,
                "title": f"PHANTOM: {len(results)} dispositivos, {vuln_count} vulnerables",
                "description": f"Caza completada. {vuln_count} de {len(results)} dispositivos tienen credenciales débiles o accesibles.",
                "timestamp": datetime.utcnow().isoformat(),
            }
            # Enviar resultado al master
            if master_ws:
                await _send_update(master_ws, task_id, {"status": "completed", "completed_at": report["timestamp"]})
                await master_ws.send_json({"type": "result", "task_id": task_id, "result": report})

    # Notificar finalización
    if master_ws:
        await _send_update(master_ws, task_id, {
            "status": "completed",
            "results": results,
            "completed_at": datetime.utcnow().isoformat(),
        })

    logger.info(f"Tarea {task_id} completada: {len(results)} resultados")
    return {"task_id": task_id, "results": results}


async def _send_update(ws, task_id: str, updates: Dict):
    try:
        await ws.send_json({"type": "task_update", "task_id": task_id, "updates": updates})
    except Exception as e:
        logger.error(f"Error enviando update: {e}")


# ─── HTTP fallback (para asignación sin WebSocket) ───────
app = FastAPI(title=f"PHANTOM Node — {NODE_ID}")


@app.post("/api/task/assign")
async def assign_http(task: Dict):
    asyncio.create_task(execute_task(task))
    return {"status": "accepted", "task_id": task.get("id")}


@app.get("/api/node/status")
async def node_status():
    return {"node_id": NODE_ID, "master_url": MASTER_URL, "backend_api": BACKEND_API}


# ─── WebSocket client al Master ──────────────────────────
async def connect_to_master():
    """Conecta al master via WebSocket y procesa tareas"""
    import websockets

    ws_url = MASTER_URL.replace("http", "ws") + "/ws/nodes"
    logger.info(f"Conectando a Master: {ws_url}")

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                # Registrar
                await ws.send(json.dumps({
                    "type": "register",
                    "node_id": NODE_ID,
                    "capabilities": ["shodan", "camera_scan", "geo_lookup"],
                }))
                logger.info("Registrado en Master")

                # Heartbeat
                async def heartbeat():
                    while True:
                        await asyncio.sleep(10)
                        try:
                            await ws.send(json.dumps({"type": "heartbeat"}))
                        except Exception:
                            break

                hb_task = asyncio.create_task(heartbeat())

                # Procesar mensajes
                async for raw in ws:
                    data = json.loads(raw)
                    if data.get("type") == "pong":
                        continue
                    elif data.get("type") == "task":
                        task = data["task"]
                        logger.info(f"Tarea recibida: {task['id']}")
                        asyncio.create_task(execute_task(task, master_ws=ws))

                hb_task.cancel()

        except Exception as e:
            logger.warning(f"Master desconectado: {e}. Reintentando en 5s...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    # Si hay MASTER_URL, conectarse como worker
    # Si no, arrancar HTTP standalone
    if MASTER_URL:
        logger.info(f"PHANTOM Node {NODE_ID} — conectando a {MASTER_URL}")
        asyncio.run(connect_to_master())
    else:
        logger.info(f"PHANTOM Node {NODE_ID} — modo standalone HTTP")
        uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
