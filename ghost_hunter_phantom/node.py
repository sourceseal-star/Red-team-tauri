"""
GHOST HUNTER v3.0 PHANTOM — Node Worker
Usa los módulos REALES de Red-team-tauri via HTTP al backend :8001.
Sin stubs — todas las llamadas usan endpoints que existen en dashboard_server.py.

Endpoints usados:
  - GET  /api/osint/shodan?query=...  (Shodan + AlienVault OTX fallback)
  - GET  /api/geo?ip=...               (ipwho.is real)
  - GET  /api/network/cameras?target=... (probe TCP a 554/80/8080/8000/8888)
  - GET  /api/iot/video-urls?ip=...     (URLs RTSP/ONVIF construidas)
  - POST /api/phantom/alert             (reportar hallazgos al backend)
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
HEADERS = {"X-Api-Key": API_KEY} if API_KEY else {}
PLAYBOOKS_DIR = Path(__file__).parent / "playbooks"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(f"phantom.node.{NODE_ID}")

if not API_KEY:
    logger.warning("REDTEAM_API_KEY no configurada — los endpoints del backend requieren autenticación")
    logger.warning("Exporta REDTEAM_API_KEY con el mismo valor que en .env del backend")

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
        logger.info(f"Playbooks cargados: {list(self.playbooks.keys())}")

    def get(self, name: str) -> Optional[dict]:
        return self.playbooks.get(name) or self.playbooks.get("generic")


playbooks = PlaybookLoader()

# ─── Acciones reales (endpoints que existen en backend :8001) ──

async def action_shodan_search(query: str, limit: int = 100) -> List[Dict]:
    """
    Búsqueda en Shodan o AlienVault OTX.
    Backend endpoint: GET /api/osint/shodan?query=...
    Respuesta: {query, total, results, source, timestamp}
    """
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
                normalized = []
                for r in results[:limit]:
                    # Shodan usa ip_str, AlienVault usa nombre de pulse
                    ip = r.get("ip_str") or r.get("ip") or r.get("indicator", "")
                    port = r.get("port", 554)
                    if ip:
                        normalized.append({
                            "ip": ip,
                            "port": port,
                            "org": r.get("org", ""),
                            "vendor": _guess_vendor(r),
                            "source": data.get("source", "shodan"),
                        })
                logger.info(f"Shodan: {len(normalized)} resultados para '{query}' (source={data.get('source')})")
                return normalized
            elif resp.status_code == 401 or resp.status_code == 403:
                logger.error(f"Auth rechazada ({resp.status_code}) — verifica REDTEAM_API_KEY")
                return []
            else:
                logger.warning(f"Shodan respondió {resp.status_code}")
                return []
    except Exception as e:
        logger.error(f"Shodan error: {e}")
        return []


async def action_camera_scan(target: Dict) -> Dict:
    """
    Escaneo de cámara — probe a puertos 554/80/8080/8000/8888.
    Backend endpoint: GET /api/network/cameras?target=...
    También obtiene URLs RTSP/ONVIF: GET /api/iot/video-urls?ip=...
    """
    ip = target.get("ip")
    port = target.get("port", 80)
    if not ip:
        return target

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            # 1. Probe de puertos de cámara
            resp = await c.get(
                f"{BACKEND_API}/api/network/cameras",
                params={"target": ip},
                headers=HEADERS,
            )
            if resp.status_code == 200:
                cam_data = resp.json()
                cameras = cam_data.get("cameras", [])
                if cameras:
                    # Hay puertos abiertos — hay cámara
                    ports_found = [c["port"] for c in cameras]
                    target.update({
                        "camera_detected": True,
                        "ports_open": ports_found,
                        "protocols": [c.get("protocol", "") for c in cameras],
                        "rtsp_url": f"rtsp://{ip}:554/" if 554 in ports_found else None,
                        "vulnerable": 554 in ports_found or 80 in ports_found,
                        "severity": "critical" if 554 in ports_found else "high",
                    })
                    logger.info(f"Cámara {ip}: puertos={ports_found}")

                    # 2. Obtener URLs de video construidas
                    resp2 = await c.get(
                        f"{BACKEND_API}/api/iot/video-urls",
                        params={"ip": ip},
                        headers=HEADERS,
                    )
                    if resp2.status_code == 200:
                        video = resp2.json()
                        urls = video.get("urls", [])
                        target["video_urls"] = [{"url": u["url"], "label": u.get("label", "")} for u in urls]
                        target["rtsp_url"] = urls[0]["url"] if urls else target.get("rtsp_url")
                else:
                    target.update({
                        "camera_detected": False,
                        "ports_open": [],
                        "severity": "low",
                    })
            elif resp.status_code in (401, 403):
                logger.error(f"Auth rechazada en camera scan — verifica REDTEAM_API_KEY")
            else:
                logger.warning(f"Camera scan respondió {resp.status_code}")
    except Exception as e:
        logger.error(f"Camera scan error {ip}: {e}")

    return target


async def action_geo_lookup(target: Dict) -> Dict:
    """
    Geolocalización real via ipwho.is.
    Backend endpoint: GET /api/geo?ip=...
    Respuesta: {ip, country, city, region, lat, lon, isp, org, timezone, timestamp}
    """
    ip = target.get("ip")
    if not ip:
        return target
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.get(
                f"{BACKEND_API}/api/geo",
                params={"ip": ip},
                headers=HEADERS,
            )
            if resp.status_code == 200:
                geo = resp.json()
                if geo.get("private"):
                    target["geo"] = {"private": True, "note": "IP privada"}
                    logger.info(f"Geo {ip}: IP privada")
                else:
                    target["geo"] = {
                        "country": geo.get("country", "?"),
                        "city": geo.get("city", "?"),
                        "region": geo.get("region", "?"),
                        "isp": geo.get("isp", "?"),
                        "org": geo.get("org", ""),
                        "lat": geo.get("lat"),
                        "lon": geo.get("lon"),
                        "timezone": geo.get("timezone", ""),
                    }
                    logger.info(f"Geo {ip}: {geo.get('country')}, {geo.get('city')}")
            elif resp.status_code in (401, 403):
                logger.error(f"Auth rechazada en geo — verifica REDTEAM_API_KEY")
            else:
                logger.warning(f"Geo respondió {resp.status_code}")
    except Exception as e:
        logger.error(f"Geo error {ip}: {e}")

    return target


def _guess_vendor(r: dict) -> str:
    """Infiere vendor del campo org/product/hostname de Shodan"""
    org = (r.get("org") or "").lower()
    data = (r.get("data") or "").lower()
    product = (r.get("product") or "").lower()
    hostname = (r.get("hostname") or "").lower()
    combined = f"{org} {data} {product} {hostname}"
    if "hikvision" in combined or "hik" in combined:
        return "Hikvision"
    if "dahua" in combined:
        return "Dahua"
    if "axis" in combined:
        return "Axis"
    if "uniview" in combined or "unv" in combined:
        return "Uniview"
    if "dvr" in combined or "nvr" in combined:
        return "DVR/NVR"
    return "unknown"


# ─── Task Executor ───────────────────────────────────────
async def execute_task(task: Dict, master_ws=None) -> Dict:
    """Ejecuta una tarea completa siguiendo el playbook"""
    task_id = task["id"]
    playbook = playbooks.get(task.get("playbook", "generic"))
    results: List[Dict] = []

    logger.info(f"Ejecutando tarea {task_id} con playbook '{playbook.get('name', '?')}'")

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
            for i, target in enumerate(results):
                results[i] = await action_camera_scan(target)
                await asyncio.sleep(0.1)  # no saturar el backend

        elif action == "geo_lookup":
            for i, target in enumerate(results):
                results[i] = await action_geo_lookup(target)
                await asyncio.sleep(0.05)

        elif action == "report":
            severity = params.get("severity", "high")
            vuln_count = sum(1 for r in results if r.get("vulnerable"))
            cam_count = sum(1 for r in results if r.get("camera_detected"))
            report = {
                "type": "hunt_report",
                "task_id": task_id,
                "target": task.get("query"),
                "total_targets": len(results),
                "vulnerable_targets": vuln_count,
                "cameras_detected": cam_count,
                "severity": severity,
                "title": f"PHANTOM: {len(results)} dispositivos, {cam_count} cámaras, {vuln_count} vulnerables",
                "description": f"Caza completada. {cam_count} cámaras detectadas, {vuln_count} vulnerables.",
                "timestamp": datetime.utcnow().isoformat(),
            }
            if master_ws:
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


# ─── HTTP fallback ────────────────────────────────────────
app = FastAPI(title=f"PHANTOM Node — {NODE_ID}")


@app.post("/api/task/assign")
async def assign_http(task: Dict):
    asyncio.create_task(execute_task(task))
    return {"status": "accepted", "task_id": task.get("id")}


@app.get("/api/node/status")
async def node_status():
    return {
        "node_id": NODE_ID,
        "master_url": MASTER_URL,
        "backend_api": BACKEND_API,
        "api_key_configured": bool(API_KEY),
        "playbooks": list(playbooks.playbooks.keys()),
    }


# ─── WebSocket client al Master ──────────────────────────
async def connect_to_master():
    """Conecta al master via WebSocket y procesa tareas"""
    try:
        import websockets
    except ImportError:
        logger.error("websockets no instalado. Instala con: pip install websockets")
        logger.info("Ejecutando en modo HTTP fallback (sin Master)")
        uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
        return

    ws_url = MASTER_URL.replace("http", "ws") + "/ws/nodes"
    logger.info(f"Conectando a Master: {ws_url}")

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({
                    "type": "register",
                    "node_id": NODE_ID,
                    "capabilities": ["shodan", "camera_scan", "geo_lookup"],
                }))
                logger.info("Registrado en Master ✓")

                async def heartbeat():
                    while True:
                        await asyncio.sleep(10)
                        try:
                            await ws.send(json.dumps({"type": "heartbeat"}))
                        except Exception:
                            break

                hb_task = asyncio.create_task(heartbeat())

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
    if MASTER_URL:
        logger.info(f"PHANTOM Node {NODE_ID} → conectando a {MASTER_URL}")
        asyncio.run(connect_to_master())
    else:
        logger.info(f"PHANTOM Node {NODE_ID} — modo standalone HTTP :8003")
        uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
