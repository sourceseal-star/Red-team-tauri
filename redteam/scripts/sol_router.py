"""
SOL Router — Endpoints del cerebro de Sol para el dashboard.
Permite al SolWidget y al sol.html hablar con Sol desde el navegador.

Endpoints:
  GET  /api/sol/status       — Estado de Sol + stats del sistema (CPU/RAM/procs)
  GET  /api/sol/memory        — Recuerdos recientes de ~/.sol/
  GET  /api/sol/think?q=...   — Procesa un mensaje (para chat del navegador)
  POST /api/sol/think         — Procesa un mensaje (body JSON)
  POST /api/sol/speak         — Sintetiza voz con sol_core
  GET  /api/sol/personality   — Personalidad actual
  POST /api/sol/personality   — Cambiar personalidad
  GET  /api/sol/last-message  — Último mensaje de Sol
"""
import os
import sys
import json
import subprocess
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

# ── Importar cerebro de Sol ──
_sol_pensar = None
_sol_remember = None
_sol_speak = None
_sol_load_memory = None
_sol_verify = None
_sol_CFG = {"name": "Harold", "personality": "cálida"}

if os.path.exists(os.path.join(_PROJECT_ROOT, "sol_core.py")):
    try:
        sys.path.insert(0, _PROJECT_ROOT)
        from sol_core import (
            generate_response as _p,
            remember as _r,
            speak as _s,
            load_memory as _lm,
            CFG as _cfg,
        )
        _sol_pensar = _p
        _sol_remember = _r
        _sol_speak = _s
        _sol_load_memory = _lm
        _sol_CFG = _cfg
    except Exception as e:
        print(f"[SOL] Import falló: {e}", flush=True)


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
        # Fallback con /proc en Linux/Termux
        try:
            with open("/proc/loadavg") as f:
                load = f.read().split()[0]
            cpu = float(load) * 10  # aproximación burda
            return {"cpu": round(min(cpu, 100), 1), "ram": 0, "processes": 0, "uptime": "--"}
        except Exception:
            return {"cpu": 0, "ram": 0, "processes": 0, "uptime": "--"}


def _load_memory(limit=300):
    """Carga recuerdos de ~/.sol/ — une memory.json y memory.jsonl."""
    memories = []
    # memory.jsonl (formato nuevo, 1 JSON por línea)
    if MEM_JSONL.exists():
        try:
            for line in MEM_JSONL.read_text(encoding="utf-8").strip().splitlines()[-limit:]:
                if line.strip():
                    m = json.loads(line)
                    memories.append(m)
        except Exception:
            pass
    # memory.json (formato viejo, lista de objetos)
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
    mem_count = len(_load_memory(1000)) if _sol_load_memory or MEM_JSONL.exists() or MEM_JSON.exists() else 0
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
    # Formatear timestamps
    formatted = []
    for m in memories[-limit:]:
        ts = m.get("timestamp") or m.get("ts") or ""
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
            "content": m.get("content", "")[:200],
            "timestamp": ts,
        })
    return {
        "memories": formatted,
        "total": total,
        "integrity": "OK" if total > 0 else "empty",
    }


@router.get("/think")
async def think_get(q: str = Query(...)):
    """Procesa un mensaje con GET (para el chat del navegador)."""
    return await _process_message(q)


@router.post("/think")
async def think_post(req: ThinkRequest):
    """Procesa un mensaje con POST."""
    return await _process_message(req.message)


async def _process_message(text: str):
    """Lógica compartida para procesar mensajes."""
    if not _sol_pensar:
        resp = "☀️ Mi cerebro está offline, Harold. Pero sigo aquí contigo."
        return {"response": resp, "intent": "offline"}

    try:
        resp = _sol_pensar(text)
        if _sol_remember:
            _sol_remember("user", text)
            _sol_remember("sol", resp)
        return {"response": resp, "intent": "chat"}
    except Exception as e:
        return {"response": f"☀️ Tuve un problema: {e}", "intent": "error"}


@router.post("/speak")
async def sol_speak(req: SpeakRequest):
    """Sintetiza voz con sol_core."""
    if _sol_speak:
        try:
            # speak() es síncrono, ejecutar en hilo
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
        "available": ["cálida", "estratega", "dulce", "filósofa"],
    }


@router.post("/personality")
async def set_personality(req: PersonalityRequest):
    """Cambiar personalidad de Sol."""
    valid = ["cálida", "estratega", "dulce", "filósofa"]
    if req.personality not in valid:
        raise HTTPException(400, f"Personalidad inválida. Válidas: {valid}")

    _sol_CFG["personality"] = req.personality

    # Guardar en config.json
    try:
        SOL_DIR.mkdir(exist_ok=True)
        cfg = {}
        if CFG_FILE.exists():
            cfg = json.loads(CFG_FILE.read_text())
        cfg["personality"] = req.personality
        CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[SOL] Error guardando personalidad: {e}", flush=True)

    return {"status": "ok", "personality": req.personality}


# GET version para el sol.html que usa fetch sin method
@router.get("/personality")
async def set_personality_get(p: str = Query(...)):
    """Cambiar personalidad con GET (para el navegador)."""
    valid = ["cálida", "estratega", "dulce", "filósofa"]
    if p not in valid:
        raise HTTPException(400, f"Personalidad inválida. Válidas: {valid}")

    _sol_CFG["personality"] = p
    try:
        SOL_DIR.mkdir(exist_ok=True)
        cfg = {}
        if CFG_FILE.exists():
            cfg = json.loads(CFG_FILE.read_text())
        cfg["personality"] = p
        CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    except Exception:
        pass
    return {"status": "ok", "personality": p}


@router.get("/last-message")
async def last_message():
    """Último mensaje de Sol."""
    return {"message": "☀️ Estoy aquí, Harold.", "time": datetime.now().isoformat()}
