"""
GHOST HUNTER v3.0 PHANTOM — Master Node
Orquestador distribuido. Se conecta al backend FastAPI :8001 existente.
Puerto: 8002
"""

import asyncio
import json
import os
import sys
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import httpx

# ─── Config ──────────────────────────────────────────────
BACKEND_API = os.environ.get("BACKEND_API", "http://localhost:8001")
MASTER_PORT = int(os.environ.get("MASTER_PORT", "8002"))
PHANTOM_QUEUE_DB = os.environ.get(
    "PHANTOM_QUEUE_DB",
    str(Path(__file__).parent / "phantom_queue.db"),
)
API_KEY = os.environ.get("REDTEAM_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("phantom.master")

# ─── Queue ───────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from phantom_queue import PhantomQueue

queue = PhantomQueue(db_path=PHANTOM_QUEUE_DB)

# ─── App ─────────────────────────────────────────────────
app = FastAPI(title="GHOST HUNTER v3.0 PHANTOM — Master", version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ───────────────────────────────────────────────
active_nodes: Dict[str, Dict] = {}
pending_tasks: Dict[str, Dict] = {}
completed_tasks: Dict[str, Dict] = {}


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, node_id: str):
        previous = self.connections.get(node_id)
        if previous and previous is not ws:
            try:
                await previous.close(code=4001, reason="Replaced by a newer connection")
            except Exception:
                pass
        self.connections[node_id] = ws
        active_nodes[node_id] = {
            "status": "idle",
            "last_seen": datetime.utcnow().isoformat(),
            "tasks_completed": 0,
            "capabilities": [],
        }
        logger.info(f"Nodo {node_id} conectado ({len(active_nodes)} activos)")

    def disconnect(self, node_id: str, ws: WebSocket | None = None) -> bool:
        if ws is not None and self.connections.get(node_id) is not ws:
            return False
        self.connections.pop(node_id, None)
        active_nodes.pop(node_id, None)
        logger.info(f"Nodo {node_id} desconectado")
        return True

    async def send_to_node(self, node_id: str, message: dict) -> bool:
        ws = self.connections.get(node_id)
        if ws:
            try:
                await ws.send_json(message)
                return True
            except Exception:
                self.disconnect(node_id)
        return False

    async def broadcast(self, message: dict, exclude: str = None):
        for nid in list(self.connections.keys()):
            if nid == exclude:
                continue
            await self.send_to_node(nid, message)


manager = ConnectionManager()
assignment_lock = asyncio.Lock()


# ─── Models ──────────────────────────────────────────────
class NodeRegister(BaseModel):
    node_id: str
    capabilities: List[str] = []


class HuntRequest(BaseModel):
    query: str
    max_results: int = 100
    playbook: str = "generic"
    target_type: str = "all"
    priority: int = 1


# ─── Endpoints ───────────────────────────────────────────
@app.websocket("/ws/nodes")
async def node_ws(websocket: WebSocket):
    node_id = None
    try:
        # El servidor debe aceptar el handshake antes de intentar leer el
        # primer mensaje. Starlette rechaza receive_json() sobre una conexión
        # que aún no fue aceptada, lo que convertía el registro del nodo en
        # un HTTP 500.
        await websocket.accept()
        data = await websocket.receive_json()
        if data.get("type") != "register":
            await websocket.close(code=4000, reason="Register first")
            return

        node_id = data["node_id"]
        await manager.connect(websocket, node_id)
        active_nodes[node_id]["capabilities"] = data.get("capabilities", [])

        await assign_pending_tasks()

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "heartbeat":
                if node_id in active_nodes:
                    active_nodes[node_id]["last_seen"] = datetime.utcnow().isoformat()
                await websocket.send_json({"type": "pong"})

            elif data.get("type") == "task_update":
                tid = data.get("task_id")
                if tid in pending_tasks:
                    updates = data.get("updates", {})
                    if not isinstance(updates, dict):
                        continue
                    pending_tasks[tid].update(updates)
                    queue.update(tid, updates)
                    if updates.get("status") in {"completed", "failed"}:
                        completed_tasks[tid] = pending_tasks.pop(tid)
                        if node_id in active_nodes:
                            if updates.get("status") == "completed":
                                active_nodes[node_id]["tasks_completed"] += 1
                            active_nodes[node_id]["status"] = "idle"
                        logger.info(f"Tarea {tid} {updates.get('status')} por {node_id}")
                        await assign_pending_tasks()

            elif data.get("type") == "result":
                tid = data.get("task_id")
                result = data.get("result", {})
                if not tid or not isinstance(result, dict):
                    continue
                queue.store_result(tid, result)
                # Reportar al backend si es crítico
                if result.get("severity") in ("critical", "high"):
                    await _report_to_backend(result)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Error en la sesión WebSocket del nodo %s", node_id or "?")
    finally:
        if node_id:
            if manager.disconnect(node_id, websocket):
                _requeue_node_tasks(node_id)
                await assign_pending_tasks()


async def _report_to_backend(result: dict):
    """Reporta hallazgos críticos al backend FastAPI existente (:8001)"""
    payload = {
        "alert_type": "phantom_hunt",
        "severity": result.get("severity", "medium"),
        "title": result.get("title", "Hallazgo PHANTOM"),
        "description": result.get("description", ""),
        "target": result.get("target"),
        "evidence": result,
        "source": "ghost_hunter_phantom",
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{BACKEND_API}/api/phantom/alert", json=payload, headers=HEADERS)
            if resp.status_code == 200:
                logger.info(f"Hallazgo reportado al backend: {result.get('target')}")
            else:
                logger.warning(f"Backend respondió {resp.status_code} — guardando local")
                _queue_for_retry(result)
    except Exception as e:
        logger.warning(f"Backend no disponible: {e} — guardando local")
        _queue_for_retry(result)


def _queue_for_retry(result: dict):
    """Guarda hallazgos que no pudieron enviarse al backend"""
    retry_file = Path(__file__).parent / "phantom_retry.json"
    retries = []
    if retry_file.exists():
        try:
            loaded = json.loads(retry_file.read_text(encoding="utf-8"))
            retries = loaded if isinstance(loaded, list) else []
        except (OSError, json.JSONDecodeError):
            logger.warning("phantom_retry.json inválido; se inicia una cola nueva")
    retries.append(result)
    temp_file = retry_file.with_suffix(".json.tmp")
    temp_file.write_text(json.dumps(retries, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_file.replace(retry_file)


def _restore_pending_tasks() -> None:
    """Recupera tareas no terminales de la cola persistente tras un reinicio."""
    recoverable = {"queued", "assigned", "running", "processing"}
    for stored in queue.get_all_tasks():
        task_id = stored.get("id")
        if not task_id or stored.get("status") not in recoverable:
            continue
        task = dict(stored)
        task.update({"status": "queued", "assigned_to": None})
        pending_tasks[task_id] = task
        queue.update(task_id, {"status": "queued", "assigned_to": None})


def _requeue_node_tasks(node_id: str) -> None:
    """Devuelve a cola las tareas que perdió un nodo desconectado."""
    for task in pending_tasks.values():
        if task.get("assigned_to") == node_id:
            task.update({"status": "queued", "assigned_to": None})
            queue.update(task["id"], {"status": "queued", "assigned_to": None})


async def assign_pending_tasks() -> None:
    """Asigna tareas pendientes sin duplicarlas durante reconexiones."""
    async with assignment_lock:
        for task_id in list(pending_tasks):
            task = pending_tasks.get(task_id)
            if task and task.get("assigned_to") is None:
                await _assign_task(task_id)


@app.on_event("startup")
async def startup():
    _restore_pending_tasks()
    await assign_pending_tasks()
    if pending_tasks:
        logger.info("Tareas recuperadas de la cola: %s", len(pending_tasks))


@app.post("/api/nodes/register")
async def register_node_http(node: NodeRegister):
    if node.node_id not in active_nodes:
        active_nodes[node.node_id] = {
            "capabilities": node.capabilities,
            "status": "idle",
            "last_seen": datetime.utcnow().isoformat(),
            "tasks_completed": 0,
        }
        logger.info(f"Nodo {node.node_id} registrado (HTTP)")
    await assign_pending_tasks()
    return {"status": "registered", "node_id": node.node_id}


@app.post("/api/hunt/start")
async def start_hunt(req: HuntRequest, bg: BackgroundTasks):
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "query": req.query,
        "max_results": req.max_results,
        "playbook": req.playbook,
        "target_type": req.target_type,
        "priority": req.priority,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "assigned_to": None,
    }
    queue.enqueue(task)
    pending_tasks[task_id] = task
    bg.add_task(assign_pending_tasks)
    return {"status": "queued", "task_id": task_id, "message": f"Caza {task_id} encolada"}


async def _assign_task(task_id: str):
    task = pending_tasks.get(task_id)
    if not task:
        return

    for node_id, node in list(active_nodes.items()):
        if node.get("status") == "idle":
            task["assigned_to"] = node_id
            task["status"] = "assigned"
            task["assigned_at"] = datetime.utcnow().isoformat()
            pending_tasks[task_id] = task
            queue.update(task_id, task)
            sent = await manager.send_to_node(node_id, {"type": "task", "task": task})
            if not sent or node_id not in active_nodes:
                task.update({"status": "queued", "assigned_to": None})
                queue.update(task_id, {"status": "queued", "assigned_to": None})
                return False
            active_nodes[node_id]["status"] = "busy"
            logger.info(f"Tarea {task_id} → nodo {node_id}")
            return True

    logger.info(f"Tarea {task_id} en cola — sin nodos disponibles")
    return False


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = pending_tasks.get(task_id) or completed_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Tarea no encontrada")
    return {"task": task, "results": queue.get_results(task_id)}


@app.get("/api/status")
async def status():
    return {
        "active_nodes": len(active_nodes),
        "nodes": {nid: {k: v for k, v in n.items() if k != "websocket"} for nid, n in active_nodes.items()},
        "pending_tasks": len(pending_tasks),
        "completed_tasks": len(completed_tasks),
        "queue_size": len(queue.get_all_tasks()),
        "backend_api": BACKEND_API,
        "ready": True,
        "queue_backend": "redis" if queue.use_redis else "sqlite" if queue.use_sqlite else "json",
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "ghost_hunter_phantom",
        "ready": True,
        "active_nodes": len(active_nodes),
        "pending_tasks": len(pending_tasks),
    }


@app.get("/api/tasks")
async def list_tasks():
    return {
        "pending": list(pending_tasks.keys()),
        "completed": list(completed_tasks.keys()),
        "queue": queue.get_all_tasks(),
    }


@app.on_event("shutdown")
async def shutdown():
    queue.cleanup()
    logger.info("PHANTOM Master apagado")


if __name__ == "__main__":
    logger.info(f"GHOST HUNTER v3.0 PHANTOM — Master en :{MASTER_PORT}")
    logger.info(f"Backend API: {BACKEND_API}")
    uvicorn.run(
        app,
        host=os.environ.get("PHANTOM_HOST", "127.0.0.1"),
        port=MASTER_PORT,
        log_level="info",
    )
