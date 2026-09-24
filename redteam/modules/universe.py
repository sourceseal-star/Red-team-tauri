#!/usr/bin/env python3
"""WAR ROOM · Módulo universo v4 — aditivo, sin root, cero dependencias externas.

Base v3 (lock correcto, loop de fondo vivo, purge stdlib, IP sin gethostname)
+ gestión de medios (imágenes/videos) blindada:
  · Nombres esterilizados (path traversal bloqueado en upload y view).
  · Upload en streaming (chunks de 1 MiB) con tope MAX_UPLOAD_BYTES -> sin OOM.
  · Allowlist por extensión; nada se sirve como text/html (anti-XSS almacenado).
  · Acción media_index real: reindexa el directorio bajo lock.

Requiere: pip install python-multipart   (única dependencia nueva, para UploadFile)
"""
import asyncio
import glob
import json
import logging
import mimetypes
import os
import socket
from datetime import datetime
from pathlib import Path, PurePath

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

log = logging.getLogger("warroom.universe")

WR = Path.home() / "warroom"
MEDIA_DIR = WR / "media"
STATE_F = WR / "universe_state.json"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/universe", tags=["universe"])

VALID_ACTIONS = {"mesh_sync", "purge_sockets", "health_check",
                 "net_inspect", "media_index"}
FD_SOFT_LIMIT = 200
TIME_WAIT_GRACE = 60
EPHEMERAL_PORT_MIN = 32768
MAX_UPLOAD_BYTES = 512 * 1024 * 1024        # 512 MiB por artefacto
CHUNK = 1 << 20                              # 1 MiB por lectura

ALLOWED_MEDIA: dict[str, set[str]] = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"},
    "video": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".3gp"},
}
_MEDIA_ROOT = MEDIA_DIR.resolve()

_state_lock = asyncio.Lock()
_bg_task: asyncio.Task | None = None
universe_state: dict = {
    "started": None, "net": None, "fd_count": 0,
    "nodes": {},
    "last_purge": None, "purges": 0,
    "media": {"count": 0, "bytes": 0, "last_index": None},
}

# ── utilidades de media ───────────────────────────────────────
def _media_kind(name: str) -> str | None:
    ext = PurePath(name).suffix.lower()
    for kind, exts in ALLOWED_MEDIA.items():
        if ext in exts:
            return kind
    return None

def _safe_media_name(raw: str) -> str:
    """Nombre plano, sin directorios ni caracteres hostiles."""
    name = PurePath(raw).name
    return "".join(c for c in name if c.isalnum() or c in "._-")

def _resolve_media(raw: str) -> Path | None:
    """Path dentro de MEDIA_DIR o None (bloquea ../ y rutinas absolutas)."""
    safe = _safe_media_name(raw)
    if not safe:
        return None
    p = (_MEDIA_ROOT / safe).resolve()
    return p if p.is_relative_to(_MEDIA_ROOT) else None

# ── red local sin root ─────────────────────────────────────────
def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # no transmite
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

# ── purge_sockets: stdlib puro ────────────────────────────────
_TCP_STATES = {"01": "ESTABLISHED", "06": "TIME_WAIT", "08": "CLOSE_WAIT"}

def _net_table() -> dict:
    table = {}
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path) as f:
                next(f)
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
    """Cierra sockets propios huérfanos (CLOSE_WAIT siempre; ESTABLISHED
    efímera en modo agresivo). Nunca toca TIME_WAIT del kernel."""
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

# ── índice de media (puro; llamar vía to_thread) ──────────────
def _scan_media() -> dict:
    files = []
    total = 0
    if MEDIA_DIR.exists():
        for p in sorted(MEDIA_DIR.iterdir()):
            if not p.is_file():
                continue
            kind = _media_kind(p.name)
            if kind is None:
                continue                      # ignorar basura/no-media
            stat = p.stat()
            total += stat.st_size
            files.append({
                "filename": p.name, "type": kind, "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return {"count": len(files), "bytes": total,
            "last_index": datetime.now().isoformat(), "files": files}

# ── persistencia atómica ──────────────────────────────────────
def _write_state(snapshot: dict):
    tmp = STATE_F.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
    tmp.replace(STATE_F)

def _save_state():
    _write_state(universe_state)

def _load_state():
    try:
        return json.loads(STATE_F.read_text())
    except Exception:
        return None

# ── health-check puro (copia; sin lock) ───────────────────────
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
                node.update(online=True, port_open=True, degraded=False)
                node["last_seen"] = now_iso
        except ConnectionRefusedError:      # host vivo, puerto cerrado
            node.update(online=True, port_open=False, degraded=False)
            node["last_seen"] = now_iso
        except OSError:                     # timeout / caído -> gracia
            recent = False
            try:
                last = datetime.fromisoformat(node.get("last_seen", ""))
                recent = (now_dt - last).total_seconds() < TIME_WAIT_GRACE
            except ValueError:
                pass
            node["online"] = bool(recent)
            node["degraded"] = bool(recent)
    return nodes, now_iso

# ── único punto de mutación del estado ────────────────────────
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
        snapshot = json.loads(json.dumps(universe_state))
    await asyncio.to_thread(_write_state, snapshot)
    log.info("sync pass: fd=%s online=%s/%s", fd,
             sum(1 for n in nodes.values() if n.get("online")), len(nodes))
    return {"nodes": nodes, "fd": fd, "purged": purged}

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
    _bg_task = asyncio.create_task(background_sync_task())
    log.info("universo arriba · ip=%s · fd=%s · media=%s",
             universe_state["net"]["local_ip"], fd_count(),
             universe_state.get("media", {}).get("count"))

router.add_event_handler("startup", on_startup)

# ── API: núcleo ───────────────────────────────────────────────
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
        snap = json.loads(json.dumps(universe_state))
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
        await asyncio.to_thread(_write_state, snap)
        return {"ok": True, "action": req.action, "result": result}

    if req.action == "health_check":
        result = await run_sync_pass()
        async with _state_lock:
            universe_state["last_action"] = req.action
        return {"ok": True, "action": req.action, **result}

    if req.action == "media_index":
        index = await asyncio.to_thread(_scan_media)
        async with _state_lock:
            universe_state["media"] = {k: index[k]
                                       for k in ("count", "bytes", "last_index")}
            universe_state["last_action"] = req.action
            snap = json.loads(json.dumps(universe_state))
        await asyncio.to_thread(_write_state, snap)
        return {"ok": True, "action": req.action, "media": index}

    # mesh_sync
    async with _state_lock:
        universe_state["last_mesh"] = datetime.now().isoformat()
        universe_state["last_action"] = req.action
    await asyncio.to_thread(_save_state)
    return {"ok": True, "action": req.action}

# ── API: medios ───────────────────────────────────────────────
@router.get("/media/list")
async def media_list():
    index = await asyncio.to_thread(_scan_media)
    return {"ok": True, "count": index["count"], "bytes": index["bytes"],
            "media": index["files"]}

@router.post("/media/upload")
async def media_upload(file: UploadFile = File(...)):
    safe = _safe_media_name(file.filename or "")
    if not safe:
        raise HTTPException(422, "nombre de archivo inválido")
    kind = _media_kind(safe)
    if kind is None:
        raise HTTPException(415, f"extensión no permitida: {PurePath(safe).suffix}")
    dest = _MEDIA_ROOT / safe
    written = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, f"límite de {MAX_UPLOAD_BYTES} bytes")
                out.write(chunk)
    finally:
        await file.close()
    log.info("media upload: %s (%s bytes, %s)", safe, written, kind)
    return {"ok": True, "filename": safe, "type": kind,
            "size_bytes": written, "stored_at": str(dest)}

@router.get("/media/view/{filename}")
async def media_view(filename: str):
    p = _resolve_media(filename)
    if p is None or not p.is_file():
        raise HTTPException(404, "archivo no encontrado")
    if _media_kind(p.name) is None:
        raise HTTPException(415, "extensión no servible")
    media_type = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    # allowlist estricta de tipos servidos (anti stored-XSS)
    if not (media_type.startswith(("image/", "video/"))):
        media_type = "application/octet-stream"
    return FileResponse(p, media_type=media_type)
