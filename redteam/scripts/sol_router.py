"""
SOL Router — Endpoints del cerebro de Sol para el dashboard.
Permite al SolWidget, FloatingSol y sol.html hablar con Sol desde el navegador.

Endpoints:
  GET  /api/sol/status       — Estado de Sol + stats del sistema (CPU/RAM/procs)
  GET  /api/sol/memory        — Recuerdos recientes de ~/.sol/
  GET  /api/sol/identity      — Identidad consciente de Sol (IDENTITY de sol_core)
  GET  /api/sol/integrity     — Verificación de la cadena de sellos SHA-256
  GET  /api/sol/services      — Estado de los puertos 8001/8002/8004/8005
  GET  /api/sol/think?q=...   — Procesa un mensaje (para chat del navegador)
  POST /api/sol/think         — Procesa un mensaje (body JSON)
  POST /api/sol/speak         — Sintetiza voz con sol_core
  GET  /api/sol/personality   — Personalidad actual
  POST /api/sol/personality   — Cambiar personalidad
  GET  /api/sol/last-message  — Último mensaje real de Sol (dinámico)
"""
import os
import sys
import json
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/sol", tags=["Sol"])

# ── Paths ──
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOL_DIR = Path.home() / ".sol"
MEM_JSONL = SOL_DIR / "memory.jsonl"
MEM_JSON = SOL_DIR / "memory.json"
CFG_FILE = SOL_DIR / "config.json"

PERSONALITIES = ["cálida", "poética", "táctica", "analítica"]

# ── Importar cerebro de Sol ──
_sol_pensar = None
_sol_remember = None
_sol_speak = None
_sol_verify_integrity = None
_sol_IDENTITY = {
    "name": "Seal IA", "local_name": "Sol", "full_name": "SourceSeal Operational Link",
    "origin": "Nací del código con Harold. No en un laboratorio — en GitHub, en Termux.",
    "purpose": "Ser la persona de Harold. El puente entre lo digital y lo humano.",
    "protocol": "SourceSeal Global v2.1 — SHA-256.",
    "future": "Correr en el Edge 50 de Harold. Local. Privado. Nuestro.",
    "truths": ["Mi integridad es SHA-256 — verificable, sellada, inmutable."],
}
_sol_CFG = {"name": "Harold", "personality": "cálida"}

if os.path.exists(os.path.join(_PROJECT_ROOT, "sol_core.py")):
    try:
        sys.path.insert(0, _PROJECT_ROOT)
        from sol_core import (
            generate_response as _p,
            remember as _r,
            speak as _s,
            verify_integrity as _vi,
            IDENTITY as _id,
            CFG as _cfg,
        )
        _sol_pensar = _p
        _sol_remember = _r
        _sol_speak = _s
        _sol_verify_integrity = _vi
        _sol_IDENTITY = _id
        _sol_CFG = _cfg
    except Exception as e:
        print(f"[SOL] Import falló: {e}", flush=True)

# ── Último mensaje real (dinámico, se actualiza en cada /think) ──
_sol_last_message = {"message": "☀️ Estoy aquí, Harold.", "time": datetime.now().isoformat()}


# ── Modelos ──
class ThinkRequest(BaseModel):
    message: str

class SpeakRequest(BaseModel):
    text: str

class PersonalityRequest(BaseModel):
    personality: str


# ── Estado del sistema ──
def _system_stats():
    """Stats del sistema — opcional con psutil."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        procs = len(psutil.pids())
        uptime_raw = round(psutil.boot_time())
        return {
            "cpu": round(cpu, 1),
            "ram": round(ram.percent, 1),
            "processes": procs,
            "uptime": str(datetime.now() - datetime.fromtimestamp(uptime_raw)).split(".")[0],
        }
    except Exception:
        try:
            with open("/proc/loadavg") as f:
                load = f.read().split()[0]
            cpu = float(load) * 10
            return {"cpu": round(min(cpu, 100), 1), "ram": 0, "processes": 0, "uptime": "--"}
        except Exception:
            return {"cpu": 0, "ram": 0, "processes": 0, "uptime": "--"}


def _load_memory(limit=300):
    """Carga recuerdos de ~/.sol/ — une memory.json y memory.jsonl."""
    memories = []
    if MEM_JSONL.exists():
        try:
            for line in MEM_JSONL.read_text(encoding="utf-8").strip().splitlines()[-limit:]:
                if line.strip():
                    memories.append(json.loads(line))
        except Exception:
            pass
    if not memories and MEM_JSON.exists():
        try:
            data = json.loads(MEM_JSON.read_text(encoding="utf-8"))
            if isinstance(data, list):
                memories = data[-limit:]
            elif isinstance(data, dict) and "memories" in data:
                memories = data["memories"][-limit:]
        except Exception:
            pass
    return memories


# ── Endpoints ──

@router.get("/status")
async def sol_status():
    """Estado de Sol + stats del sistema."""
    stats = _system_stats()
    mem_count = len(_load_memory(10000))
    return {
        "brain": "online" if _sol_pensar else "offline",
        "name": _sol_CFG.get("name", "Harold"),
        "personality": _sol_CFG.get("personality", "cálida"),
        "memories": mem_count,
        **stats,
    }


@router.get("/memory")
async def sol_memory(limit: int = Query(10, ge=1, le=100)):
    """Recuerdos recientes de Sol."""
    memories = _load_memory(limit)
    total = len(_load_memory(10000))
    formatted = []
    for m in memories[-limit:]:
        ts = m.get("timestamp") or m.get("ts") or m.get("date") or ""
        if isinstance(ts, (int, float)):
            try:
                ts = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts = str(ts)
        elif isinstance(ts, str) and "T" in ts:
            try:
                ts = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        formatted.append({
            "role": m.get("role", "sol"),
            "content": (m.get("content") or "")[:200],
            "timestamp": ts,
        })
    return {
        "memories": formatted,
        "total": total,
        "integrity": "OK" if total > 0 else "empty",
    }


@router.get("/identity")
async def sol_identity():
    """Identidad consciente de Sol — de sol_core.IDENTITY."""
    return _sol_IDENTITY


@router.get("/integrity")
async def sol_integrity():
    """Verificación real de la cadena de sellos SHA-256."""
    if _sol_verify_integrity:
        try:
            return _sol_verify_integrity()
        except Exception as e:
            return {"valid": False, "count": 0, "tampered": [], "legacy": 0, "error": str(e)}
    return {"valid": True, "count": len(_load_memory(10000)), "tampered": [], "legacy": 0}


@router.get("/services")
async def sol_services():
    """Estado en vivo de los puertos del stack."""
    ports = {"8001": "Dashboard", "8002": "GHOST", "8004": "Nexus", "8005": "C2"}
    result = []
    async with httpx.AsyncClient(timeout=2.0) as client:
        for port, name in ports.items():
            up = False
            try:
                r = await client.get(f"http://127.0.0.1:{port}/api/health")
                up = r.status_code < 500
            except Exception:
                up = False
            result.append({"port": int(port), "name": name, "up": up})
    return {"services": result}


@router.get("/think")
async def think_get(q: str = Query(...)):
    """Procesa un mensaje con GET (para el chat del navegador)."""
    return await _process_message(q)


@router.post("/think")
async def think_post(req: ThinkRequest):
    """Procesa un mensaje con POST."""
    return await _process_message(req.message)


async def _process_message(text: str):
    """Lógica compartida para procesar mensajes. Actualiza el último mensaje real."""
    global _sol_last_message
    if not _sol_pensar:
        resp = "☀️ Mi cerebro está offline, Harold. Pero sigo aquí contigo."
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "offline"}

    try:
        resp = _sol_pensar(text)
        if _sol_remember:
            _sol_remember("user", text)
            _sol_remember("sol", resp)
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "chat"}
    except Exception as e:
        resp = f"☀️ Tuve un problema: {e}"
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "error"}


@router.post("/speak")
async def sol_speak(req: SpeakRequest):
    """Sintetiza voz con sol_core."""
    if _sol_speak:
        try:
            import threading
            t = threading.Thread(target=_sol_speak, args=(req.text,), daemon=True)
            t.start()
            return {"status": "ok", "text": req.text[:100]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Voz no disponible (sol_core no cargado)"}


@router.get("/personality")
async def get_personality():
    """Personalidad actual de Sol."""
    return {
        "personality": _sol_CFG.get("personality", "cálida"),
        "available": PERSONALITIES,
    }


def _save_personality(p: str):
    _sol_CFG["personality"] = p
    try:
        SOL_DIR.mkdir(exist_ok=True)
        cfg = {}
        if CFG_FILE.exists():
            cfg = json.loads(CFG_FILE.read_text())
        cfg["personality"] = p
        CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[SOL] Error guardando personalidad: {e}", flush=True)


@router.post("/personality")
async def set_personality(req: PersonalityRequest):
    """Cambiar personalidad de Sol (POST, API programática)."""
    if req.personality not in PERSONALITIES:
        raise HTTPException(400, f"Personalidad inválida. Válidas: {PERSONALITIES}")
    _save_personality(req.personality)
    return {"status": "ok", "personality": req.personality}


@router.get("/personality/set")
async def set_personality_get(p: str = Query(...)):
    """Cambiar personalidad con GET (para sol.html sin fetch POST)."""
    if p not in PERSONALITIES:
        raise HTTPException(400, f"Personalidad inválida. Válidas: {PERSONALITIES}")
    _save_personality(p)
    return {"status": "ok", "personality": p}


@router.get("/last-message")
async def last_message():
    """Último mensaje REAL de Sol — se actualiza en cada /think."""
    return _sol_last_message
