"""
API Gateway Mesh — Registro y orquestación de nodos distribuidos
Centraliza WebSocket relay + HTTP proxy entre Termux/Replit nodes
"""
import os
import json
import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, Set, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("gateway_mesh")

app = FastAPI(title="API Gateway Mesh", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# REGISTRO DE NODOS
# ==========================================
class NodeRegistry:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.websocket_connections: Dict[str, WebSocket] = {}

    def register(self, node_id: str, node_info: dict):
        self.nodes[node_id] = {
            "id": node_id,
            "name": node_info.get("name", node_id),
            "type": node_info.get("type", "termux"),  # termux | replit
            "location": node_info.get("location", "unknown"),
            "capabilities": node_info.get("capabilities", []),
            "status": "online",
            "last_heartbeat": datetime.utcnow().isoformat(),
            "registered_at": datetime.utcnow().isoformat(),
        }
        logger.info(f"[+] Nodo registrado: {node_id} ({node_info.get('type', 'termux')})")

    def heartbeat(self, node_id: str):
        if node_id in self.nodes:
            self.nodes[node_id]["last_heartbeat"] = datetime.utcnow().isoformat()
            self.nodes[node_id]["status"] = "online"

    def unregister(self, node_id: str):
        if node_id in self.nodes:
            self.nodes[node_id]["status"] = "offline"
            logger.info(f"[-] Nodo offline: {node_id}")

    def list_nodes(self):
        return list(self.nodes.values())

    def get_node(self, node_id: str):
        return self.nodes.get(node_id)

registry = NodeRegistry()

# ==========================================
# HEALTH CHECK — detectar nodos muertos
# ==========================================
async def health_check_loop():
    while True:
        await asyncio.sleep(15)
        now = datetime.utcnow()
        for node_id, node in registry.nodes.items():
            if node["status"] == "online":
                try:
                    hb = datetime.fromisoformat(node["last_heartbeat"])
                    if (now - hb).total_seconds() > 60:
                        node["status"] = "stale"
                        logger.warning(f"[!] Nodo stale: {node_id} (sin heartbeat >60s)")
                except:
                    pass

@app.on_event("startup")
async def startup():
    asyncio.create_task(health_check_loop())
    logger.info("[+] Gateway Mesh iniciado")

# ==========================================
# ENDPOINTS HTTP
# ==========================================
@app.post("/nodes/register")
async def register_node(request: Request):
    data = await request.json()
    node_id = data.get("node_id", f"node_{int(time.time())}")
    registry.register(node_id, data)
    return {"status": "registered", "node_id": node_id, "nodes": registry.list_nodes()}

@app.post("/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str):
    registry.heartbeat(node_id)
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/nodes")
async def list_nodes():
    return {"nodes": registry.list_nodes(), "total": len(registry.nodes)}

@app.get("/nodes/{node_id}")
async def get_node(node_id: str):
    node = registry.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    return node

@app.delete("/nodes/{node_id}")
async def unregister_node(node_id: str):
    registry.unregister(node_id)
    return {"status": "unregistered", "node_id": node_id}

@app.get("/health")
async def health():
    online = sum(1 for n in registry.nodes.values() if n["status"] == "online")
    return {
        "status": "ok",
        "version": "1.0.0",
        "nodes_online": online,
        "nodes_total": len(registry.nodes),
    }

# ==========================================
# WEBSOCKET RELAY — comunicación entre nodos
# ==========================================
@app.websocket("/ws/{node_id}")
async def websocket_endpoint(websocket: WebSocket, node_id: str):
    await websocket.accept()
    registry.websocket_connections[node_id] = websocket
    registry.register(node_id, {"name": node_id, "type": "termux"})
    logger.info(f"[WS] Conectado: {node_id}")
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "broadcast")

            if msg_type == "heartbeat":
                registry.heartbeat(node_id)
                await websocket.send_json({"type": "heartbeat_ack", "ts": datetime.utcnow().isoformat()})

            elif msg_type == "command":
                # Enviar comando a un nodo específico
                target = data.get("target")
                if target and target in registry.websocket_connections:
                    await registry.websocket_connections[target].send_json(data)
                    logger.info(f"[WS] Command {node_id} -> {target}: {data.get('action')}")
                else:
                    await websocket.send_json({"type": "error", "message": f"Nodo {target} no conectado"})

            elif msg_type == "broadcast":
                # Broadcast a todos los nodos conectados
                for nid, ws in registry.websocket_connections.items():
                    if nid != node_id:
                        try:
                            await ws.send_json(data)
                        except:
                            pass
                logger.info(f"[WS] Broadcast de {node_id}: {data.get('action', 'message')}")

            elif msg_type == "telemetry":
                # Guardar telemetría (CPU, RAM, temp, etc.)
                registry.nodes[node_id]["telemetry"] = data.get("payload", {})
                registry.heartbeat(node_id)

    except WebSocketDisconnect:
        logger.info(f"[WS] Desconectado: {node_id}")
        registry.unregister(node_id)
        del registry.websocket_connections[node_id]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
