#!/usr/bin/env python3
"""WAR ROOM · Módulo universo v3 — aditivo, sin root, cero dependencias externas.

Cambios respecto a v2:
  · Lock asyncio usado SOLO en 'async with' (v2: 'with' -> TypeError + deadlock).
  · Loop de fondo realmente arrancado en on_startup y con referencia viva.
  · Único punto de mutación: run_sync_pass(). Los checks trabajan sobre copias.
  · purge_sockets 100% stdlib: mapeo inode de /proc/self/fd contra /proc/net/tcp(6).
    CLOSE_WAIT siempre; ESTABLISHED en puerto efímero solo en modo agresivo.
  · Health-check distingue refused (host vivo, puerto cerrado) de timeout (caído),
    con gracia de TIME_WAIT_GRACE segundos antes de declarar caído un nodo.
  · Persistencia atómica (tmp + rename); escrituras vía asyncio.to_thread.
"""
import asyncio
import glob
import json
import logging
import os
import socket
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

log = logging.getLogger("warroom.universe")

WR = Path.home() / "warroom"
STATE_F = WR / "universe_state.json"
WR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/universe", tags=["universe"])

VALID_ACTIONS = {"mesh_sync", "purge_sockets", "health_check", "net_inspect"}
FD_SOFT_LIMIT = 200        # por encima -> purga automática en el loop de fondo
TIME_WAIT_GRACE = 60       # seg. de gracia antes de declarar caído un nodo
EPHEMERAL_PORT_MIN = 32768

_state_lock = asyncio.Lock()
_bg_task: asyncio.Task | None = None
universe_state: dict = {
    "started": None, "net": None, "fd_count": 0,
    "nodes": {},           # {id: {"addr","port","online","port_open","degraded","last_seen"}}
    "last_purge": None, "purges": 0,
}

# ── Red local sin root ─────────────────────────────────────────
def _local_ip() -> str:
    """Truco UDP como vía principal; /proc/net/fib_trie como respaldo."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # no transmite nada
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        pass
    try:
        for line in Path("/proc/net/fib_trie").read_text().splitlines():
            if "32 host LOCAL" in line:
                addr = line.strip().split()[0]
                if not addr.startswith(("127.", "169.254.")):
                    return addr
    except OSError:
        pass
    return "127.0.0.1"

def fd_count() -> int:
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return -1

def inspect_userland_net() -> dict:
    return {"local_ip": _local_ip(), "stack": "IPv4 UDP/TCP",
            "privilege": "userland (no-root)", "fd_count": fd_count()}

# ── purge_sockets: stdlib puro, sin psutil ────────────────────
_TCP_STATES = {"01": "ESTABLISHED", "06": "TIME_WAIT", "08": "CLOSE_WAIT"}

def _net_table() -> dict:
    """inode -> (state, local_port) desde /proc/net/tcp y tcp6."""
    table = {}
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path) as f:
                next(f)  # cabecera
                for line in f:
                    parts = line.split()
                    if len(parts) < 10:
                        continue
                    state = _TCP_STATES.get(parts[3])
                    if state is None:
                        continue
                    try:
                        lport = int(parts[1].rsplit(":", 1)[1], 16)
                    except (IndexError, ValueError):
                        continue
                    table[parts[9]] = (state, lport)
        except OSError:
            continue
    return table

def purge_sockets(aggressive: bool = False) -> dict:
    """Cierra sockets propios huérfanos. Nunca toca TIME_WAIT del kernel
    (eso es de root con ss -K). En userland solo puedes cerrar TUS fds."""
    report = {"checked": 0, "closed_close_wait": 0, "closed_aggressive": 0,
              "fd_before": fd_count()}
    table = _net_table()
    for fd_path in glob.glob("/proc/self/fd/*"):
        try:
            target = os.readlink(fd_path)
        except OSError:
            continue
        if not (target.startswith("socket:[") and target.endswith("]")):
            continue
        info = table.get(target[8:-1])
        if info is None:
            continue
        state, lport = info
        report["checked"] += 1
        close = state == "CLOSE_WAIT" or (
            aggressive and state == "ESTABLISHED"
            and lport >= EPHEMERAL_PORT_MIN)
        if not close:
            continue
        try:
            os.close(int(fd_path.rsplit("/", 1)[1]))
            if state == "CLOSE_WAIT":
                report["closed_close_wait"] += 1
            else:
                report["closed_aggressive"] += 1
        except OSError:
            pass
    report["fd_after"] = fd_count()
    log.info("purge: %s", report)
    return report

# ── Persistencia atómica ──────────────────────────────────────
def _save_state():
    tmp = STATE_F.with_suffix(".tmp")
    tmp.write_text(json.dumps(universe_state, ensure_ascii=False, indent=1))
    tmp.replace(STATE_F)   # rename atómico: nunca un JSON a medias

def _load_state():
    try:
        return json.loads(STATE_F.read_text())
    except Exception:
        return None

# ── Health-check puro (trabaja sobre copia, sin lock) ─────────
def _check_nodes() -> tuple[dict, str]:
    now_dt = datetime.now()
    now_iso = now_dt.isoformat()
    nodes = json.loads(json.dumps(universe_state.get("nodes", {})))
    for node in nodes.values():
        addr, port = node.get("addr"), int(node.get("port", 8012))
        if not addr:
            continue
        try:
            with socket.create_connection((addr, port), timeout=1.0):
                node["online"] = True
                node["port_open"] = True
                node["degraded"] = False
                node["last_seen"] = now_iso
        except ConnectionRefusedError:      # host vivo, puerto cerrado
            node["online"] = True
            node["port_open"] = False
            node["degraded"] = False
            node["last_seen"] = now_iso
        except OSError:                     # timeout / caído: aplicar gracia
            recent = False
            try:
                last = datetime.fromisoformat(node.get("last_seen", ""))
                recent = (now_dt - last).total_seconds() < TIME_WAIT_GRACE
            except ValueError:
                pass
            node["online"] = bool(recent)   # gracia: no declarar caído aún
            node["degraded"] = bool(recent)
    return nodes, now_iso

# ── Único punto de mutación del estado ────────────────────────
async def run_sync_pass(purge_aggressive: bool = False) -> dict:
    nodes, now_iso = await asyncio.to_thread(_check_nodes)
    fd = fd_count()
    purged = None
    if fd > FD_SOFT_LIMIT or purge_aggressive:
        purged = await asyncio.to_thread(purge_sockets, purge_aggressive)
    async with _state_lock:
        universe_state["nodes"] = nodes
        universe_state["fd_count"] = fd
        if purged:
            universe_state["last_purge"] = now_iso
            universe_state["purges"] += 1
        snapshot = json.loads(json.dumps(universe_state))  # copia para guardar
    await asyncio.to_thread(_save_state_with, snapshot)
    log.info("sync pass: fd=%s online=%s/%s", fd,
             sum(1 for n in nodes.values() if n.get("online")), len(nodes))
    return {"nodes": nodes, "fd": fd, "purged": purged}

def _save_state_with(snapshot: dict):
    tmp = STATE_F.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
    tmp.replace(STATE_F)

async def background_sync_task():
    while True:
        try:
            await run_sync_pass()
        except Exception:
            log.exception("sync pass failed")
        await asyncio.sleep(300)

def on_startup():
    global _bg_task
    saved = _load_state()
    if saved:
        universe_state.update(saved)
    universe_state["started"] = datetime.now().isoformat()
    universe_state["net"] = inspect_userland_net()
    _save_state()
    _bg_task = asyncio.create_task(background_sync_task())  # ref viva: no GC
    log.info("universo arriba · ip=%s · fd=%s",
             universe_state["net"]["local_ip"], fd_count())

router.add_event_handler("startup", on_startup)

# ── API ───────────────────────────────────────────────────────
class SyncRequest(BaseModel):
    action: str
    payload: dict | None = None

    @field_validator("action")
    @classmethod
    def _valid(cls, v: str) -> str:
        if v not in VALID_ACTIONS:
            raise ValueError(f"acción inválida: {v} (válidas: {sorted(VALID_ACTIONS)})")
        return v

@router.get("/status")
async def status():
    async with _state_lock:
        snap = json.loads(json.dumps(universe_state))  # copia, no referencia
    snap["fd_now"] = fd_count()
    return snap

@router.get("/net")
async def net():
    return inspect_userland_net()

@router.post("/sync")
async def sync(req: SyncRequest):
    if req.action == "net_inspect":
        info = inspect_userland_net()
        async with _state_lock:
            universe_state["net"] = info
            universe_state["last_action"] = req.action
        await asyncio.to_thread(_save_state)
        return {"ok": True, "action": req.action, "net": info}

    if req.action == "purge_sockets":
        result = await asyncio.to_thread(
            purge_sockets, bool((req.payload or {}).get("aggressive")))
        async with _state_lock:
            universe_state["last_purge"] = datetime.now().isoformat()
            universe_state["purges"] += 1
            universe_state["last_action"] = req.action
            snap = json.loads(json.dumps(universe_state))
        await asyncio.to_thread(_save_state_with, snap)
        return {"ok": True, "action": req.action, "result": result}

    if req.action == "health_check":
        result = await run_sync_pass()
        async with _state_lock:
            universe_state["last_action"] = req.action
        return {"ok": True, "action": req.action, **result}

    # mesh_sync
    async with _state_lock:
        universe_state["last_mesh"] = datetime.now().isoformat()
        universe_state["last_action"] = req.action
    await asyncio.to_thread(_save_state)
    return {"ok": True, "action": req.action}
