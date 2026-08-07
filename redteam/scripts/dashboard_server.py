"""
RED-TEAM-TAURI · Dashboard Server Unificado
Puerto único :8001 · FastAPI · Sirve dist/ estático
"""
import asyncio, json, os, socket, subprocess, time, uuid, shlex
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx

BASE = Path(__file__).resolve().parent.parent  # redteam/
DIST = BASE.parent / "tauri-frontend" / "dist"

app = FastAPI(title="Red-Team Tauri", version="2.0-unified")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ---------- WebSocket hub ----------
ws_clients: set[WebSocket] = set()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept(); ws_clients.add(ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong", "ts": int(time.time())})
            except Exception: pass
    finally:
        ws_clients.discard(ws)

async def broadcast(payload: dict):
    dead = []
    for c in ws_clients:
        try: await c.send_json(payload)
        except: dead.append(c)
    for c in dead: ws_clients.discard(c)

# ---------- Utilidades ----------
async def tcp_check(host: str, port: int, timeout=1.5) -> Optional[str]:
    try:
        _, w = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout)
        banner = ""
        try:
            data = await asyncio.wait_for(w.read(256), timeout=0.8)
            banner = data.decode(errors="ignore").strip()[:80]
        except: pass
        w.close()
        return banner
    except Exception:
        return None

def subnet_from_iface() -> str:
    try:
        out = subprocess.check_output(["ip", "route", "show", "dev", "wlan0"],
                                      stderr=subprocess.DEVNULL).decode()
        for line in out.splitlines():
            parts = line.split()
            if "/" in parts[0]:
                return parts[0]
    except: pass
    return "192.168.1.0/24"

# =======================================================
#  ENDPOINTS ABSORBIDOS
# =======================================================

# ---------- Topología (antes faltaba aquí) ----------
@app.post("/api/scan/topology")
async def scan_topology():
    subnet = subnet_from_iface()
    cmd = f"nmap -sn -T3 {subnet}"
    try:
        out = subprocess.check_output(shlex.split(cmd),
                                      stderr=subprocess.DEVNULL, timeout=60).decode()
    except Exception as e:
        return JSONResponse({"error": str(e), "results": []}, status_code=500)

    hosts, current = [], None
    for line in out.splitlines():
        if "Nmap scan report for" in line:
            ip = line.split()[-1].strip("()")
            current = {"ip": ip, "mac": None, "vendor": None,
                       "ports": [], "type": "unknown"}
            hosts.append(current)
        elif current and "MAC Address" in line:
            parts = line.split()
            current["mac"] = parts[2]
            current["vendor"] = " ".join(parts[3:]).strip("()") or "unknown"
        elif current and "Host is up" in line:
            current["status"] = "up"
    return {"results": hosts, "hosts_up": len(hosts), "subnet": subnet}

# ---------- Cámaras ----------
CAM_PORTS = [554, 80, 443, 8000, 8080, 37777, 8554]

@app.post("/api/network/cameras")
@app.post("/api/scan/cameras")
async def scan_cameras():
    subnet = subnet_from_iface()
    base = subnet.rsplit(".", 1)[0]
    tasks = [tcp_check(f"{base}.{i}", 554) for i in range(1, 255)]
    banners = await asyncio.gather(*tasks)
    cams = []
    for i, b in enumerate(banners, start=1):
        if b is not None:
            ip = f"{base}.{i}"
            extra = {p: await tcp_check(ip, p) for p in CAM_PORTS if p != 554}
            cams.append({"ip": ip, "rtsp": b, "ports": extra,
                         "type": "camera", "first_seen": datetime.now().isoformat()})
    await broadcast({"type": "progress",
                     "payload": f"Cámaras encontradas: {len(cams)}"})
    return {"results": cams}

# ---------- Routers ----------
ROUTER_PORTS = [80, 443, 22, 23, 8080, 8443, 1900]

@app.post("/api/scan/routers")
async def scan_routers():
    subnet = subnet_from_iface()
    base = subnet.rsplit(".", 1)[0]
    candidates = [f"{base}.{i}" for i in [1, 2, 3, 4, 254]]
    results = []
    for ip in candidates:
        ports = {p: await tcp_check(ip, p) for p in ROUTER_PORTS}
        if any(ports.values()):
            results.append({"ip": ip, "ports": ports, "type": "router"})
    return {"results": results}

# ---------- IoT genérico ----------
@app.post("/api/scan/iot")
async def scan_iot():
    subnet = subnet_from_iface()
    cmd = f"nmap -sV -p 1883,5683,502,47808 -T3 {subnet}"
    try:
        out = subprocess.check_output(shlex.split(cmd), timeout=90,
                                      stderr=subprocess.DEVNULL).decode()
    except Exception as e:
        return {"error": str(e), "results": []}
    return {"results": out.splitlines(), "raw": out}

# ---------- WiFi ----------
@app.post("/api/scan/wifi")
async def scan_wifi():
    try:
        out = subprocess.check_output(["iwlist", "wlan0", "scan"],
                                      timeout=20, stderr=subprocess.DEVNULL).decode()
    except Exception:
        try:
            out = subprocess.check_output(["iw", "dev", "wlan0", "scan"],
                                          timeout=20, stderr=subprocess.DEVNULL).decode()
        except Exception as e:
            return {"error": str(e)}
    return {"results": out[:4000]}

# ---------- Shodan (absorbido de main.py) ----------
@app.get("/api/osint/shodan")
async def shodan_lookup(ip: str = "8.8.8.8"):
    key = os.environ.get("SHODAN_API_KEY", "")
    if not key:
        return {"error": "SHODAN_API_KEY no configurada", "ip": ip}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"https://api.shodan.io/shodan/host/{ip}?key={key}")
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "ip": ip}
        return r.json()

# ---------- Exploits (absorbido de main.py) ----------
@app.get("/api/exploits/list")
async def exploits_list():
    d = BASE / "exploits"
    if not d.exists():
        return {"results": []}
    return {"results": [p.name for p in d.iterdir() if p.is_file()]}

# ---------- Honeypot (absorbido de server.js) ----------
honeypot_proc = None

@app.post("/api/honeypot/start")
async def honeypot_start(port: int = 8888):
    global honeypot_proc
    if honeypot_proc and honeypot_proc.poll() is None:
        return {"status": "already_running", "pid": honeypot_proc.pid}
    script = BASE / "scripts" / "honeypot.py"
    if not script.exists():
        return {"error": "honeypot.py no encontrado"}
    honeypot_proc = subprocess.Popen(["python", str(script), str(port)])
    await broadcast({"type": "alert", "payload": f"Honeypot iniciado en puerto {port}"})
    return {"status": "started", "pid": honeypot_proc.pid, "port": port}

@app.post("/api/honeypot/stop")
async def honeypot_stop():
    global honeypot_proc
    if honeypot_proc:
        honeypot_proc.terminate()
        honeypot_proc = None
    return {"status": "stopped"}

# ---------- Canary (conservado) ----------
@app.post("/api/canary/generate")
async def canary_generate():
    cid = uuid.uuid4().hex[:10]
    out_dir = BASE / "canary_output"
    out_dir.mkdir(exist_ok=True)
    html = out_dir / f"canary_{cid}.html"
    html.write_text(f"<img src='/canary/callback?id={cid}'/>")
    return {"canary_id": cid, "file": str(html)}

@app.get("/canary/callback")
async def canary_callback(id: str):
    await broadcast({"type": "alert", "payload": f"Canary triggered: {id}"})
    # GIF 1x1 transparente
    return HTMLResponse(
        "GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
        media_type="image/gif")

# ---------- Network stats ----------
@app.get("/api/network/stats")
async def network_stats():
    return {"hosts": 0, "cameras": 0, "routers": 0, "alerts": 0}

# ---------- Serve static dist/ ----------
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"status": "ok", "backend": "red-team-tauri-unified"})
else:
    @app.get("/")
    async def root():
        return {"status": "ok", "backend": "red-team-tauri-unified",
                "dist_missing": True, "hint": f"Build frontend en {DIST}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
