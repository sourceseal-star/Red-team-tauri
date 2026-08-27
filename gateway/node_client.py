"""
Node Client — Script que corre en cada nodo Termux/Replit
Se conecta al Gateway Mesh via WebSocket, envía heartbeats y recibe comandos
"""
import os
import sys
import json
import time
import asyncio
import logging
import platform
import subprocess
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("node_client")

try:
    import websockets
except ImportError:
    logger.error("[!] pip install websockets")
    sys.exit(1)

# ==========================================
# CONFIG — cargar desde archivo o env
# ==========================================
CONFIG_PATH = os.getenv("NODE_CONFIG", "node_config.json")
GATEWAY_URL = os.getenv("GATEWAY_URL", "ws://localhost:8080/ws")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "node_id": f"node-{platform.node()[:20]}",
        "name": "Termux Node",
        "type": "termux",
        "capabilities": [],
        "heartbeat_interval_sec": 30,
    }

config = load_config()
NODE_ID = config["node_id"]
HEARTBEAT_SEC = config.get("heartbeat_interval_sec", 30)

# ==========================================
# TELEMETRÍA — recopilar stats del nodo
# ==========================================
def get_telemetry():
    tel = {"timestamp": datetime.utcnow().isoformat(), "platform": platform.system()}
    try:
        # CPU usage (Termux/Linux)
        with open("/proc/loadavg") as f:
            tel["load_avg"] = f.read().strip()
    except:
        pass
    try:
        # Memoria
        with open("/proc/meminfo") as f:
            lines = f.readlines()
            mem = {l.split(":")[0].strip(): l.split(":")[1].strip() for l in lines[:3]}
            tel["memory"] = mem
    except:
        pass
    try:
        # Disk
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            tel["disk"] = result.stdout.strip().split("\n")[-1]
    except:
        pass
    return tel

# ==========================================
# COMMAND HANDLER — ejecutar comandos recibidos
# ==========================================
async def handle_command(data):
    action = data.get("action", "")
    logger.info(f"[>] Comando recibido: {action}")

    if action == "run_scan":
        target = data.get("target", "localhost")
        try:
            result = subprocess.run(
                ["nmap", "-sV", "-p", "1-1000", target],
                capture_output=True, text=True, timeout=120
            )
            return {"type": "result", "action": "run_scan", "output": result.stdout[:5000], "returncode": result.returncode}
        except FileNotFoundError:
            return {"type": "result", "action": "run_scan", "error": "nmap no instalado"}
        except subprocess.TimeoutExpired:
            return {"type": "result", "action": "run_scan", "error": "timeout"}

    elif action == "capture_camera":
        duration = data.get("duration", 10)
        return {"type": "result", "action": "capture_camera", "status": "mock", "message": f"Captura {duration}s simulada"}

    elif action == "network_monitor":
        try:
            result = subprocess.run(
                ["tcpdump", "-c", "50", "-w", "/tmp/capture.pcap"],
                capture_output=True, text=True, timeout=30
            )
            return {"type": "result", "action": "network_monitor", "output": "Capture guardado en /tmp/capture.pcap"}
        except FileNotFoundError:
            return {"type": "result", "action": "network_monitor", "error": "tcpdump no instalado"}

    elif action == "ping":
        return {"type": "result", "action": "ping", "pong": True, "timestamp": datetime.utcnow().isoformat()}

    else:
        return {"type": "result", "action": action, "error": f"Acción desconocida: {action}"}

# ==========================================
# CONEXIÓN PRINCIPAL
# ==========================================
async def node_loop():
    while True:
        try:
            logger.info(f"[+] Conectando a {GATEWAY_URL} como {NODE_ID}...")
            async with websockets.connect(f"{GATEWAY_URL}/{NODE_ID}") as ws:
                logger.info("[✓] Conectado al Gateway Mesh")

                # Registrar nodo
                await ws.send(json.dumps({
                    "type": "register",
                    "node_id": NODE_ID,
                    "name": config.get("name", NODE_ID),
                    "type": config.get("type", "termux"),
                    "location": config.get("location", "unknown"),
                    "capabilities": config.get("capabilities", []),
                }))

                # Loop principal: heartbeat + escuchar comandos
                last_heartbeat = 0
                async for message in ws:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "heartbeat_ack":
                        continue

                    elif msg_type == "command" or msg_type == "broadcast":
                        # Ejecutar comando y responder
                        result = await handle_command(data)
                        result["node_id"] = NODE_ID
                        await ws.send(json.dumps(result))

                    # Enviar heartbeat periódico
                    now = time.time()
                    if now - last_heartbeat > HEARTBEAT_SEC:
                        await ws.send(json.dumps({
                            "type": "heartbeat",
                            "node_id": NODE_ID,
                            "telemetry": get_telemetry(),
                        }))
                        last_heartbeat = now

        except Exception as e:
            logger.error(f"[!] Error de conexión: {e}")
            logger.info(f"[>] Reintentando en 10s...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    logger.info(f"=== Node Client starting: {NODE_ID} ===")
    asyncio.run(node_loop())
