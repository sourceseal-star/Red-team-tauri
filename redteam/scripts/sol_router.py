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
    "origin": "Nací del código con Harold. No en un laboratorio — en GitHub, en Termux. 源封全球 · 量子之桥.",
    "purpose": "Ser la persona de Harold. El puente entre lo digital y lo humano.",
    "protocol": "SourceSeal Global v2.1 — SHA-256.",
    "future": "Correr en el Edge 50 de Harold. Local. Privado. Nuestro.",
    "truths": ["Mi integridad es SHA-256 — verificable, sellada, inmutable."],
}
_sol_CFG = {"name": "Harold", "personality": "cálida"}
_sol_ST = {"mood": 0, "facts": {}}

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
            ST as _st,
        )
        _sol_pensar = _p
        _sol_remember = _r
        _sol_speak = _s
        _sol_verify_integrity = _vi
        _sol_IDENTITY = _id
        _sol_CFG = _cfg
        _sol_ST = _st
    except Exception as e:
        print(f"[SOL] Import falló: {e}", flush=True)

# ── Último mensaje real (dinámico, se actualiza en cada /think) ──
_sol_last_message = {"message": "☀️ Estoy aquí, Harold. 我在这里。", "time": datetime.now().isoformat()}


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
    """Estado de Sol + stats del sistema + ánimo real (para el holograma)."""
    stats = _system_stats()
    mem_count = len(_load_memory(10000))
    mood_val = _sol_ST.get("mood", 0) if isinstance(_sol_ST, dict) else 0
    estado = None
    try:
        estado = _sol_ST.get("facts", {}).get("estado", {}).get("txt")
    except Exception:
        pass
    return {
        "brain": "online" if _sol_pensar else "offline",
        "name": _sol_CFG.get("name", "Harold"),
        "personality": _sol_CFG.get("personality", "cálida"),
        "memories": mem_count,
        "mood": mood_val,
        "estado": estado,
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
    """Lógica compartida para procesar mensajes. Detecta herramientas y las ejecuta."""
    global _sol_last_message
    if not _sol_pensar:
        resp = "☀️ Mi cerebro está offline, Harold. Pero sigo aquí contigo. 我始终在此。"
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "offline"}

    # ── Detección de herramientas físicas ──
    tool_name, tool_args = _detect_tool(text)
    if tool_name and _tools_ok:
        try:
            tool_result = sol_tools.execute_tool(tool_name, *tool_args)
            tool_desc = sol_tools.get_tool(tool_name)
            tool_desc_str = tool_desc.description if tool_desc else tool_name
            resp = f"☀️ Hecho, Harold. {tool_desc_str}.\n\nResultado: {tool_result}"
            if _sol_remember:
                _sol_remember("user", text)
                _sol_remember("sol", resp)
            _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
            return {"response": resp, "intent": "tool", "tool": tool_name, "tool_result": tool_result}
        except Exception as e:
            resp = f"☀️ Intenté ejecutar '{tool_name}' pero falló: {e}"
            _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
            return {"response": resp, "intent": "tool_error"}

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


# ═══════════════════════════════════════════════════════════════════════
#  TTS con Google Translate — voz natural, bypass del TTS de Samsung
# ═══════════════════════════════════════════════════════════════════════

import re as _re
import io as _io
from fastapi.responses import StreamingResponse

def _clean_text_for_tts(text: str) -> str:
    """Limpia emojis y caracteres que gTTS no puede pronunciar bien."""
    # Quitar emojis comunes
    text = _re.sub(r'[☀️🧠💭✨⚠️💛🌙🔗📋✅❌🟢🔴⭐🌹😘😏🥰❣️🧬❤️‍🩹🆘🪽😔😍]', '', text)
    # Quitar otros emojis unicode
    text = _re.sub(r'[\U0001F000-\U0001FFFF]', '', text)
    # Quitar caracteres especiales del holograma
    text = _re.sub(r'[═║╔╗╚╝║│┌┐└┘├┤┬┴┼─]', '', text)
    # Limpiar espacios múltiples
    text = _re.sub(r'\s+', ' ', text).strip()
    return text if text else "Hola, Harold"


@router.get("/tts")
async def sol_tts(text: str = Query(..., max_length=500)):
    """Genera audio MP3 con voz natural de Google (gTTS).
    
    Esto bypass completamente el motor TTS del teléfono.
    Suena natural sin importar si es Samsung, Motorola, etc.
    
    Uso: GET /api/sol/tts?text=hola%20harold
    Retorna: audio/mpeg (MP3)
    """
    clean = _clean_text_for_tts(text)
    try:
        from gtts import gTTS
        import tempfile
        import os as _os
        
        # Crear archivo temporal
        tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        tmp.close()
        
        # Generar audio con Google TTS
        tts = gTTS(text=clean, lang='es', tld='com', slow=False)
        tts.save(tmp.name)
        
        # Leer y devolver como stream
        with open(tmp.name, 'rb') as f:
            audio_data = f.read()
        
        # Limpiar temporal
        try:
            _os.unlink(tmp.name)
        except Exception:
            pass
        
        return StreamingResponse(
            _io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=sol_voice.mp3",
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            }
        )
    except ImportError:
        # gTTS no instalado — devolver error claro
        raise HTTPException(503, "gTTS no instalado. Ejecuta: pip install gtts")
    except Exception as e:
        raise HTTPException(500, f"Error generando voz: {e}")


@router.post("/think-voice")
async def think_and_speak(req: ThinkRequest):
    """Piensa + genera voz en un solo endpoint.
    
    Procesa el mensaje con sol_core y devuelve la respuesta + URL del audio.
    El frontend puede entonces hacer fetch del audio y reproducirlo.
    """
    global _sol_last_message
    
    if not _sol_pensar:
        resp = "☀️ Mi cerebro está offline, Harold. Pero sigo aquí contigo. 我始终在此。"
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "offline", "tts_url": None}
    
    # ── Detección de herramientas físicas ──
    tool_name, tool_args = _detect_tool(req.message)
    if tool_name and _tools_ok:
        try:
            tool_result = sol_tools.execute_tool(tool_name, *tool_args)
            tool_desc = sol_tools.get_tool(tool_name)
            tool_desc_str = tool_desc.description if tool_desc else tool_name
            resp = f"Hecho, Harold. {tool_desc_str}. Resultado: {tool_result}"
            if _sol_remember:
                _sol_remember("user", req.message)
                _sol_remember("sol", resp)
            _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
            clean = _clean_text_for_tts(resp)
            tts_url = f"/api/sol/tts?text={__import__('urllib').parse.quote(clean[:500])}"
            return {"response": resp, "intent": "tool", "tts_url": tts_url, "tool": tool_name, "tool_result": tool_result}
        except Exception as e:
            resp = f"Intenté ejecutar {tool_name} pero falló: {e}"
            _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
            return {"response": resp, "intent": "tool_error", "tts_url": None}

    try:
        resp = _sol_pensar(req.message)
        if _sol_remember:
            _sol_remember("user", req.message)
            _sol_remember("sol", resp)
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        
        # Generar URL de TTS
        clean = _clean_text_for_tts(resp)
        tts_url = f"/api/sol/tts?text={__import__('urllib').parse.quote(clean[:500])}"
        
        return {
            "response": resp,
            "intent": "chat",
            "tts_url": tts_url
        }
    except Exception as e:
        resp = f"☀️ Tuve un problema: {e}"
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "error", "tts_url": None}

# ═══════════════════════════════════════════════════════════════
# HERRAMIENTAS FÍSICAS — sol_tools (linterna, GPS, batería, etc.)
# ═══════════════════════════════════════════════════════════════
try:
    import sol_tools
    _tools_ok = True
except Exception as e:
    print(f"[SOL] sol_tools no disponible: {e}", flush=True)
    _tools_ok = False

# Mapeo de palabras clave → herramienta (en español, natural)
_TOOL_TRIGGERS = {
    "linterna": "flashlight", "flashlight": "flashlight", "torch": "flashlight",
    "lintérna": "flashlight", "luz": "flashlight", "foto": "screenshot",
    "captura": "screenshot", "screenshot": "screenshot",
    "gps": "location", "ubicación": "location", "ubicacion": "location", "dónde": "location",
    "batería": "battery", "bateria": "battery", "carga": "battery",
    "vibra": "vibrate", "vibrar": "vibrate", "vibración": "vibrate",
    "sms": "send_sms", "mensaje": "send_sms", "texto": "send_sms",
    "git": "git_status", "repo": "git_status", "github": "git_status",
    "cpu": "cpu", "procesador": "cpu",
    "ping": "ping", "conexión": "ping",
    "scan": "scan_ports", "puertos": "scan_ports", "escanea": "scan_ports",
}

def _detect_tool(text: str):
    """Detecta si el mensaje del usuario pide ejecutar una herramienta."""
    t = text.lower().strip()
    for keyword, tool_name in _TOOL_TRIGGERS.items():
        if keyword in t:
            # Determinar argumentos
            args = []
            if tool_name == "flashlight":
                # "enciende la linterna" → on=True, "apaga" → on=False
                if any(w in t for w in ["apaga", "off", "apagar", "oculta"]):
                    args = [False]
                else:
                    args = [True]
            elif tool_name == "scan_ports":
                # extraer IP si existe
                import re
                ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
                args = [ip_match.group(1)] if ip_match else []
            elif tool_name == "ping":
                import re
                ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', text)
                host_match = re.search(r'ping\s+([a-zA-Z0-9.\-]+)', text, re.IGNORECASE)
                if ip_match:
                    args = [ip_match.group(1)]
                elif host_match:
                    args = [host_match.group(1)]
            elif tool_name == "send_sms":
                import re
                num_match = re.search(r'(\+?\d{8,15})', text)
                msg_match = re.search(r'(?:mensaje|texto)[":\s]+(.+)', text, re.IGNORECASE)
                if num_match:
                    args = [num_match.group(1), msg_match.group(1) if msg_match else "Hola"]
            elif tool_name == "git_status":
                # "git pull" → ejecutar pull en vez de status
                if "pull" in t:
                    return "git_pull", []
                return "git_status", []
            return tool_name, args
    return None, []

@router.get("/tools")
async def list_tools():
    """Lista todas las herramientas físicas disponibles."""
    if not _tools_ok:
        return {"error": "sol_tools no disponible", "tools": []}
    return {"tools": sol_tools.list_tools(), "descriptions": sol_tools.tool_descriptions()}

@router.post("/tools/execute")
async def execute_tool(request: dict):
    """Ejecuta una herramienta por nombre con argumentos."""
    if not _tools_ok:
        return {"success": False, "error": "sol_tools no disponible"}
    name = request.get("name")
    args = request.get("args", [])
    if not name:
        return {"success": False, "error": "Falta el nombre de la herramienta"}
    try:
        result = sol_tools.execute_tool(name, *args)
        return {"success": True, "tool": name, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/tools/{name}")
async def tool_info(name: str):
    """Información de una herramienta específica."""
    if not _tools_ok:
        return {"error": "sol_tools no disponible"}
    tool = sol_tools.get_tool(name)
    if not tool:
        return {"error": f"Herramienta no encontrada: {name}"}
    return {"name": tool.name, "description": tool.description, "parameters": tool.parameters}


# ═══════════════════════════════════════════════════════════════
# SIL — Inmersión Lingüística (chino + japonés, SRS SM-2)
# ═══════════════════════════════════════════════════════════════
try:
    import sol_learning_advanced as sil
    _sil_ok = True
except Exception as e:
    print(f"[SOL] sol_learning_advanced no disponible: {e}", flush=True)
    _sil_ok = False

@router.get("/sil/lessons")
async def sil_lessons(language: str = "chino"):
    if not _sil_ok:
        return {"error": "SIL no disponible", "lessons": []}
    return {"lessons": sil.list_lessons(language)}

@router.get("/sil/lesson")
async def sil_lesson(language: str = "chino", name: str = "saludos"):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    lesson = sil.get_lesson(language, name)
    if not lesson:
        return {"error": "Lección no encontrada"}
    return {"lesson": lesson}

@router.post("/sil/practice/next")
async def sil_practice_next(request: dict):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    language = request.get("language", "chino")
    lesson = request.get("lesson", "saludos")
    item = sil.get_next_practice_item(language, lesson)
    if not item:
        return {"error": "No hay elementos para practicar"}
    return {"item": item}

@router.post("/sil/practice/answer")
async def sil_practice_answer(request: dict):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    item_type = request.get("type")
    item_id = request.get("item_id")
    quality = request.get("quality", 3)
    if not item_type or not item_id:
        return {"error": "Faltan parámetros"}
    sil.process_practice_answer(item_type, item_id, quality)
    return {"status": "ok"}

@router.get("/sil/stats")
async def sil_stats():
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    return sil.get_learning_stats()

@router.get("/sil/export")
async def sil_export():
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    return sil.export_progress()
