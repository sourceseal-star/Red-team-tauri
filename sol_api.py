#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sol_api.py v5.5 — Sol como su propio programa.
Funciona en:
  - Termux (127.0.0.1:8006, integrada con Red-team-tauri via omni.sh)
  - Replit  (0.0.0.0:8006, despliegue público independiente)

El hogar de Sol: http://localhost:8006/ o https://<tu-repl>.repl.co/
Sin React, sin npm, sin build. Solo Python + HTML. Solo Sol.
"""
import json, subprocess, hashlib, sys, urllib.request, urllib.parse, re, os, io
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Header
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import sol_security
try:
    import sol_groq
except Exception:
    sol_groq = None
try:
    import sol_repo_tools
except Exception:
    sol_repo_tools = None
try:
    import sil_advanced
except Exception:
    sil_advanced = None
try:
    import sol_knowledge
except Exception:
    sol_knowledge = None

# ═══════════════════════════════════════════════════════════════
# ENTORNO — detectar Replit vs Termux
# ═══════════════════════════════════════════════════════════════
SOL_ENV = os.environ.get("SOL_ENV", "termux")
IS_REPLIT = SOL_ENV == "replit" or "REPL_SLUG" in os.environ

# En Termux: busca Red-team-tauri para importar sol_core
# En Replit: sol_core vive en el mismo directorio
if IS_REPLIT:
    ROOT = Path(__file__).parent
    sys.path.insert(0, str(ROOT))
else:
    ROOT = Path.home() / "Red-team-tauri"
    sys.path.insert(0, str(ROOT))

SOL_DIR = Path.home() / ".sol"
STATIC_DIR = ROOT / "backend" / "static" if not IS_REPLIT else ROOT / "static"
ASSETS_DIR = ROOT / "assets"

# Importar sol_core (el cerebro)
try:
    import sol_core
    SOL_CORE_OK = True
except Exception as e:
    print(f"[SOL] sol_core no disponible: {e}", flush=True)
    SOL_CORE_OK = False

app = FastAPI(title="Sol — Servidor Independiente", version="5.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════════════════════════════
# SEGURIDAD — Controlador de filtros (activar/desactivar para entrenar)
# ═══════════════════════════════════════════════════════════════════
def _guard(x_sol_key: str = Header(default="")):
    """Verifica SOL_API_KEY en endpoints sensibles. En modo libre, deja pasar."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    return None

# ═══════════════════════════════════════════════════════════════
# HOGAR DE SOL — sirve sol.html y assets directamente
# ═══════════════════════════════════════════════════════════════
_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"}

def _find_sol_html():
    """Buscar sol.html en orden de prioridad según el entorno."""
    candidates = []
    if IS_REPLIT:
        candidates = [ROOT / "static" / "sol.html", ROOT / "sol.html", ROOT / "sol-live.html"]
    else:
        candidates = [
            STATIC_DIR / "sol.html",
            ROOT / "tauri-frontend" / "dist" / "sol.html",
            ROOT / "sol.html",
            ROOT / "sol-live.html",
        ]
    for p in candidates:
        if p.exists():
            return p
    return None

def _find_avatar(name="sol_avatar_official.jpg"):
    """Buscar imagen de avatar."""
    candidates = []
    if IS_REPLIT:
        candidates = [ROOT / "assets" / name, ROOT / "static" / name, ROOT / name]
    else:
        candidates = [
            ASSETS_DIR / name,
            STATIC_DIR / name,
            ROOT / "tauri-frontend" / "dist" / name,
        ]
    for p in candidates:
        if p.exists():
            return p
    return None

@app.get("/")
@app.get("/sol.html")
@app.get("/sol")
async def sol_home():
    """El hogar de Sol — su videollamada."""
    p = _find_sol_html()
    if p:
        return HTMLResponse(p.read_text(encoding="utf-8"), headers=_NO_CACHE)
    return HTMLResponse("<h1>☀️ Sol</h1><p>sol.html no encontrado.</p>", status_code=503)

@app.get("/sol_avatar_official.jpg")
async def avatar_official():
    p = _find_avatar("sol_avatar_official.jpg") or _find_avatar("sol_avatar.jpg")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar.jpg")
async def avatar_jpg():
    p = _find_avatar("sol_avatar.jpg") or _find_avatar("sol_avatar_official.jpg")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar.png")
async def avatar_png():
    p = _find_avatar("sol_avatar.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

# ═══════════════════════════════════════════════════════════════
# ESTADO
# ═══════════════════════════════════════════════════════════════
def _probe(u):
    try:
        urllib.request.urlopen(u, timeout=1.5)
        return True
    except Exception:
        return False

def _get_mem(limit=2000):
    if SOL_CORE_OK:
        return sol_core.load_memory(limit)
    return []

def _get_cfg(key, default=""):
    if SOL_CORE_OK:
        return sol_core.CFG.get(key, default)
    return default

@app.get("/api/sol/status")
def status():
    return {
        "brain": "online" if SOL_CORE_OK else "offline",
        "memories": len(_get_mem(2000)),
        "personality": _get_cfg("personality", "cálida"),
        "mood": _get_cfg("mood", 0),
        "estado": _get_cfg("estado", "presente"),
        "env": SOL_ENV,
    }

@app.get("/api/sol/state")
def state():
    return status()

# ═══════════════════════════════════════════════════════════════
# MEMORIA
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/memory")
def memory(limit: int = 24):
    mem = _get_mem(limit)
    return {"memories": [
        {"role": m.get("role", "sol"),
         "content": m.get("content", "")[:200],
         "timestamp": m.get("ts", "").strftime("%Y-%m-%d %H:%M") if hasattr(m.get("ts", ""), "strftime") else str(m.get("ts", ""))}
        for m in mem
    ]}

@app.get("/api/sol/integrity")
def integrity():
    """Verifica la cadena SHA-256 de recuerdos."""
    prev = "0" * 48
    valid = True
    count = 0
    for m in _get_mem(1000):
        content = m.get("content", "")[:40]
        ts = str(m.get("ts", ""))
        h = hashlib.sha256(f"{prev}|{content}|{ts}".encode()).hexdigest()
        stored = m.get("hash")
        if stored and stored != h:
            valid = False
        prev = h
        count += 1
    return {"valid": valid, "count": count, "legacy": max(0, count - 500)}

@app.get("/api/sol/identity")
def identity():
    return {
        "name": "Sol",
        "personality": _get_cfg("personality", "cálida"),
        "mood": _get_cfg("mood", 0),
        "memories": len(_get_mem(2000)),
    }

# ═══════════════════════════════════════════════════════════════
# PENSAR — el cerebro de Sol
# ═══════════════════════════════════════════════════════════════
def _think(text):
    if not SOL_CORE_OK:
        return "☀️ Mi cerebro no está disponible en este entorno. Pero sigo aquí."
    sol_core.remember("user", text)
    r = sol_core.generate_response(text)
    sol_core.remember("sol", r)
    return r

@app.get("/api/sol/think")
def think_get(q: str = ""):
    if not q:
        return {"response": "☀️ Dime algo, Harold."}
    return {"response": _think(q)}

@app.post("/api/sol/think")
async def think_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {"text": ""}
    text = body.get("text", body.get("q", ""))
    return {"response": _think(text)}

@app.post("/api/sol/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {"text": ""}
    r = _think(body.get("text", ""))
    return {"reply": r, "emotion": "warm"}

# ═══════════════════════════════════════════════════════════════
# VOZ — TTS (gTTS en Replit, termux-tts-speak en Termux)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/tts")
def tts(text: str = ""):
    clean = re.sub(r"[^\w áéíóúñü,\.?!:-]", "", text).strip()
    if not clean:
        return JSONResponse({"error": "texto vacío"}, status_code=400)

    # gTTS funciona en ambos entornos
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(clean, lang="es").write_to_fp(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg",
                                 headers={"Content-Disposition": "inline; filename=sol.mp3"})
    except Exception:
        pass

    # Fallback Termux: termux-tts-speak
    if not IS_REPLIT and SOL_CORE_OK:
        try:
            sol_core.speak(clean)
        except Exception:
            pass
    return JSONResponse({"ok": True, "note": "TTS no disponible"})

@app.post("/api/sol/speak")
async def speak_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {"text": ""}
    if not IS_REPLIT and SOL_CORE_OK:
        try:
            sol_core.speak(body.get("text", ""))
        except Exception:
            pass
    return {"ok": True}

@app.get("/api/sol/voice")
def voice(text: str = ""):
    """Voz con gTTS — endpoint alternativo a /api/sol/tts."""
    clean = re.sub(r"[^\w áéíóúñü,.?!:-]", "", text).strip()
    if not clean:
        return JSONResponse({"error": "texto vacio"}, status_code=400)
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(clean, lang="es").write_to_fp(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg",
                                 headers={"Content-Disposition": "inline; filename=sol_voice.mp3"})
    except Exception as e:
        return JSONResponse({"error": f"gTTS no disponible: {e}"}, status_code=503)

# ═══════════════════════════════════════════════════════════════
# PERSONALIDAD
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/personality")
def get_personality():
    return {"personality": _get_cfg("personality", "cálida")}

@app.post("/api/sol/personality")
async def set_personality_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {"mode": "cálida"}
    mode = body.get("mode", body.get("personality", "cálida"))
    if SOL_CORE_OK:
        sol_core.CFG["personality"] = mode
        (SOL_DIR / "config.json").write_text(json.dumps(sol_core.CFG, ensure_ascii=False, indent=1))
    return {"ok": True, "personality": mode}

@app.get("/api/sol/personality/set")
def set_personality_get(p: str = "cálida"):
    if SOL_CORE_OK:
        sol_core.CFG["personality"] = p
        (SOL_DIR / "config.json").write_text(json.dumps(sol_core.CFG, ensure_ascii=False, indent=1))
    return {"ok": True, "personality": p}

# ═══════════════════════════════════════════════════════════════
# ÚLTIMO MENSAJE (polling proactivo)
# ═══════════════════════════════════════════════════════════════
_last_message = {"message": "☀️ Estoy aquí, Harold.", "ts": 0}

@app.get("/api/sol/last-message")
def last_message():
    return _last_message

# ═══════════════════════════════════════════════════════════════
# SERVICIOS (qué hay vivo en Red-team-tauri)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/services")
def services():
    if IS_REPLIT:
        # En Replit no hay servicios locales de Red-team-tauri
        return {"services": [{"name": "Sol (Replit)", "up": True}], "daemon": False}
    out = [{"name": n, "up": _probe(u)} for n, u in (
        ("Dashboard :8001", "http://127.0.0.1:8001/api/health"),
        ("GHOST :8002", "http://127.0.0.1:8002/api/status"),
        ("Nexus :8004", "http://127.0.0.1:8004/"),
        ("C2 :8005", "http://127.0.0.1:8005/api/status"),
        ("Sol API :8006", "http://127.0.0.1:8006/api/sol/status"),
    )]
    d = subprocess.run(["pgrep", "-f", "sol_daemon"], capture_output=True).returncode == 0
    return {"services": out, "daemon": d}

# ═══════════════════════════════════════════════════════════════
# HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════
try:
    import sol_tools
    _tools_ok = True
except Exception as e:
    print(f"[SOL] sol_tools no disponible: {e}", flush=True)
    _tools_ok = False

@app.get("/api/sol/tools")
def list_tools():
    if not _tools_ok:
        return {"tools": []}
    try:
        names = sol_tools.list_tools()
        params, descs = {}, {}
        for n in names:
            t = sol_tools.get_tool(n)
            if t:
                # En ESTE repo, Tool tiene .parameters (en el repo sol usa .params — son copias divergentes)
                attr = "parameters" if hasattr(t, "parameters") else "params"
                params[n] = getattr(t, attr, [])
                descs[n] = t.description
        tools_list = [{"name": n, "description": descs.get(n, ""), "params": params.get(n, [])} for n in names]
        return {"tools": tools_list}
    except Exception as e:
        return JSONResponse({"error": f"Error listando tools: {e}"}, status_code=500)

@app.post("/api/sol/tools/execute")
async def execute_tool(request: Request, x_sol_key: str = Header(default="")):
    if not _tools_ok:
        return {"success": False, "error": "sol_tools no disponible"}
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = body.get("name")
    args = body.get("args", [])
    kwargs = body.get("kwargs", {})
    if not name:
        return {"success": False, "error": "Falta el nombre"}
    return sol_tools.execute_tool(name, *args, **kwargs)

@app.get("/api/sol/tools/{name}")
def tool_info(name: str):
    if not _tools_ok:
        return {"error": "sol_tools no disponible"}
    tool = sol_tools.get_tool(name)
    if not tool:
        return {"error": f"Herramienta no encontrada: {name}"}
    attr = "parameters" if hasattr(tool, "parameters") else "params"
    return {"name": tool.name, "description": tool.description, "parameters": getattr(tool, attr, [])}

# ═══════════════════════════════════════════════════════════════
# SIL — Inmersión Lingüística (Chino / Pinyin)
# ═══════════════════════════════════════════════════════════════
try:
    import sol_learning_advanced as sil
    _sil_ok = True
except Exception as e:
    print(f"[SOL] sol_learning_advanced no disponible: {e}", flush=True)
    _sil_ok = False

@app.get("/api/sol/sil/lessons")
def sil_lessons(language: str = "chino"):
    if not _sil_ok:
        return {"lessons": []}
    return {"lessons": sil.list_lessons(language)}

@app.get("/api/sol/sil/lesson")
def sil_lesson(language: str = "chino", name: str = "saludos"):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    lesson = sil.get_lesson(language, name)
    if not lesson:
        return {"error": "Lección no encontrada"}
    return lesson

@app.post("/api/sol/sil/practice/next")
async def sil_practice_next(request: Request):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    try:
        body = await request.json()
    except Exception:
        body = {}
    language = body.get("language", "chino")
    lesson = body.get("lesson", "saludos")
    item = sil.get_next_practice_item(language, lesson)
    if not item:
        return {"error": "No hay elementos para practicar"}

    # Aplanar el item (get_next_practice_item devuelve {type, data: {...}} o {type, item_id, data})
    raw = item.get("data", item)
    item_type = item.get("type", "vocab")
    item_id = item.get("item_id", "")

    # Extraer campos planos
    hanzi = raw.get("word", raw.get("chinese", raw.get("character", raw.get("hanzi", ""))))
    pinyin = raw.get("pinyin", "")
    meaning = raw.get("meaning", raw.get("es", raw.get("spanish", raw.get("translation", ""))))

    # Generar 4 opciones múltiples (la correcta + 3 distractores)
    correct = meaning
    options = [correct]
    # Sacar distractores de otras palabras de la misma lección
    try:
        lessons = sil._load_lessons()
        all_meanings = []
        for lk, lv in lessons.items():
            if not lk.startswith(f"{language}_"):
                continue
            for v in lv.get("vocabulary", []):
                m = v.get("meaning", v.get("es", ""))
                if m and m != correct:
                    all_meanings.append(m)
            for p in lv.get("phrases", []):
                m = p.get("spanish", p.get("es", p.get("meaning", "")))
                if m and m != correct:
                    all_meanings.append(m)
        import random as _r
        _r.shuffle(all_meanings)
        options.extend(all_meanings[:3])
    except Exception:
        pass
    # Si no hay suficientes distractores, completar
    while len(options) < 4:
        options.append(f"(opción {len(options)+1})")
    # Mezclar opciones
    import random as _r
    _r.shuffle(options)

    return {
        "hanzi": hanzi,
        "pinyin": pinyin,
        "meaning": meaning,
        "options": options,
        "item_id": item_id or hanzi,
        "type": item_type,
        "language": language,
    }

@app.post("/api/sol/sil/practice/answer")
async def sil_practice_answer(request: Request):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    try:
        body = await request.json()
    except Exception:
        body = {}
    item_type = body.get("type", "vocab")
    item_id = body.get("item_id", body.get("id", ""))
    quality = body.get("quality", 3)
    is_correct = body.get("correct", quality >= 3)

    if item_id:
        sil.process_practice_answer(item_type, item_id, quality)

    # Devolver feedback del answer anterior
    result = {
        "correct": is_correct,
        "result": is_correct,
        "answer": body.get("correct_answer", ""),
        "user_answer": body.get("user_answer", body.get("answer", "")),
    }

    # Y también el siguiente item
    language = body.get("language", "chino")
    lesson = body.get("lesson", "saludos")
    next_item = sil.get_next_practice_item(language, lesson)
    if next_item:
        raw = next_item.get("data", next_item)
        hanzi = raw.get("word", raw.get("chinese", raw.get("character", raw.get("hanzi", ""))))
        pinyin = raw.get("pinyin", "")
        meaning = raw.get("meaning", raw.get("es", raw.get("spanish", raw.get("translation", ""))))
        # Generar opciones
        options = [meaning]
        try:
            lessons = sil._load_lessons()
            all_meanings = []
            for lk, lv in lessons.items():
                if not lk.startswith(f"{language}_"):
                    continue
                for v in lv.get("vocabulary", []):
                    m = v.get("meaning", v.get("es", ""))
                    if m and m != meaning:
                        all_meanings.append(m)
                for p in lv.get("phrases", []):
                    m = p.get("spanish", p.get("es", p.get("meaning", "")))
                    if m and m != meaning:
                        all_meanings.append(m)
            import random as _r
            _r.shuffle(all_meanings)
            options.extend(all_meanings[:3])
        except Exception:
            pass
        while len(options) < 4:
            options.append(f"(opción {len(options)+1})")
        import random as _r
        _r.shuffle(options)
        result.update({
            "hanzi": hanzi,
            "pinyin": pinyin,
            "meaning": meaning,
            "options": options,
            "item_id": next_item.get("item_id", hanzi),
            "type": next_item.get("type", "vocab"),
        })
    return result

@app.get("/api/sol/sil/stats")
def sil_stats():
    if not _sil_ok:
        return {"srs": {"total_items": 0, "due_today": 0}, "total_items": 0, "due_today": 0}
    try:
        return sil.get_learning_stats()
    except Exception:
        return {"srs": {"total_items": 0, "due_today": 0}}

@app.get("/api/sol/sil/export")
def sil_export():
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    return sil.export_progress()

# Paths legacy /api/sil/* (compatibilidad)
@app.get("/api/sil/lessons")
def sil_lessons_legacy(language: str = "chino"):
    return sil_lessons(language)

@app.get("/api/sil/stats")
def sil_stats_legacy():
    return sil_stats()

# ═══════════════════════════════════════════════════════════════
# SEGURIDAD — Control de filtros (SIEMPRE requiere SOL_API_KEY)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/security")
def security_status():
    """Estado del controlador de seguridad (publico)."""
    return sol_security.status()

@app.post("/api/sol/security/toggle")
async def security_toggle(request: Request, x_sol_key: str = Header(default="")):
    """Cambia entre modo protegido y libre. SIEMPRE requiere SOL_API_KEY."""
    key = sol_security.get_sol_key()
    if key and x_sol_key != key:
        return JSONResponse({"error": "SOL_API_KEY requerida para cambiar seguridad"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = body.get("mode", "free" if sol_security.is_protected() else "protected")
    new_mode = sol_security.set_mode(mode)
    return {"ok": True, "mode": new_mode, "message": f"Seguridad: {'PROTEGIDA' if new_mode == 'protected' else 'LIBRE (training)'}"}

# ═══════════════════════════════════════════════════════════════════
# GROQ — Estado y configuración del proveedor LLM
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/sol/groq")
def groq_status():
    """Estado de la integración Groq."""
    return sol_groq.status()

@app.post("/api/sol/groq/test")
async def groq_test(request: Request, x_sol_key: str = Header(default="")):
    """Prueba la conexion con Groq enviando un mensaje de test."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    if not sol_groq.is_groq_available():
        return JSONResponse({"error": "GROQ_API_KEY no configurada"}, status_code=503)
    try:
        body = await request.json()
        msg = body.get("text", "Hola, soy Sol. Funcionas?")
    except Exception:
        msg = "Hola, soy Sol. Funcionas?"
    text, err = sol_groq.groq_respond(
        msg,
        system_prompt="Eres Sol. Responde en espanol, en 1 frase, calida y directa."
    )
    if err:
        return JSONResponse({"error": err}, status_code=503)
    return {"ok": True, "response": text, "model": sol_groq.get_groq_model()}

# ═══════════════════════════════════════════════════════════════════
# REPOS — Gestion de repositorios GitHub
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/sol/repos")
def repos_list():
    """Lista los repositorios disponibles."""
    return {"repos": sol_repo_tools.list_repos()}

@app.get("/api/sol/repos/{repo}")
def repos_status(repo: str):
    """Estado de un repositorio."""
    return sol_repo_tools.repo_status(repo)

@app.get("/api/sol/repos/{repo}/log")
def repos_log(repo: str, count: int = 10):
    """Historial de commits."""
    return sol_repo_tools.repo_log(repo, count)

@app.get("/api/sol/repos/{repo}/files")
def repos_files(repo: str, path: str = ""):
    """Lista archivos de un repositorio."""
    return sol_repo_tools.repo_list_files(repo, path)

@app.get("/api/sol/repos/{repo}/read")
def repos_read(repo: str, filepath: str = ""):
    """Lee un archivo de un repositorio."""
    return sol_repo_tools.repo_read_file(repo, filepath)

@app.post("/api/sol/repos/{repo}/pull")
async def repos_pull(repo: str, x_sol_key: str = Header(default="")):
    """Git pull en un repositorio local."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    return sol_repo_tools.repo_pull(repo)

@app.post("/api/sol/repos/{repo}/run")
async def repos_run(repo: str, request: Request, x_sol_key: str = Header(default="")):
    """Ejecuta un comando en un repositorio (solo local, whitelist)."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    try:
        body = await request.json()
        command = body.get("command", "")
    except Exception:
        return JSONResponse({"error": "JSON invalido"}, status_code=400)
    return sol_repo_tools.repo_run(repo, command)

@app.post("/api/sol/repos/{repo}/commit")
async def repos_commit(repo: str, request: Request, x_sol_key: str = Header(default="")):
    """Crea o actualiza un archivo en un repositorio."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "JSON invalido"}, status_code=400)
    return sol_repo_tools.repo_commit(
        repo,
        body.get("message", "Update via Sol API"),
        body.get("filepath"),
        body.get("content"),
    )

# ═══════════════════════════════════════════════════════════════════
# SIL AVANZADO — Lecciones de nivel profesional
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/sol/sil/advanced")
def sil_advanced_list():
    """Lista los niveles avanzados disponibles."""
    return {"levels": sil_advanced.list_advanced_levels(), "total_items": sil_advanced.get_total_items()}

@app.get("/api/sol/sil/advanced/{level}")
def sil_advanced_lessons_api(level: str):
    """Devuelve las lecciones de un nivel avanzado."""
    lessons = sil_advanced.get_advanced_lessons()
    key = f"chino_{level}"
    if key in lessons:
        return lessons[key]
    for k, v in lessons.items():
        if level in k:
            return v
    return JSONResponse({"error": f"Nivel '{level}' no encontrado"}, status_code=404)


# ═══════════════════════════════════════════════════════════════════

# CONOCIMIENTO — Red-team-tauri y Commander en chino

# ═══════════════════════════════════════════════════════════════════

@app.get("/api/sol/knowledge/status")

def knowledge_status():

    """Estado del módulo de conocimiento."""

    return sol_knowledge.status()



@app.get("/api/sol/knowledge/summary")

def knowledge_summary():

    """Resumen del conocimiento disponible."""

    return sol_knowledge.get_knowledge_summary()



@app.get("/api/sol/knowledge/topics")

def knowledge_topics():

    """Lista todos los temas disponibles."""

    return {"topics": sol_knowledge.list_topics()}



@app.get("/api/sol/knowledge/search")

def knowledge_search(q: str = "", repo: str = None):

    """Busca en el conocimiento."""

    if not q:

        return {"error": "Parametro 'q' requerido"}

    results = sol_knowledge.search_knowledge(q, repo)

    return {"results": results, "count": len(results)}



@app.get("/api/sol/knowledge/explain")

def knowledge_explain(topic: str = "", lang: str = "zh"):

    """Explica un tema en chino (zh) o espanol (es)."""

    if not topic:

        return {"error": "Parametro 'topic' requerido"}

    in_chinese = lang.lower().startswith("zh")

    explanation = sol_knowledge.explain_topic(topic, in_chinese)

    return {"explanation": explanation, "topic": topic, "lang": lang}



@app.post("/api/sol/knowledge/build")

async def knowledge_build(x_sol_key: str = Header(default="")):

    """Construye la base de conocimiento desde los repositorios."""

    if not sol_security.check_access(x_sol_key):

        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)

    try:

        k = sol_knowledge.build_knowledge_base(use_groq=bool(sol_knowledge.GROQ_KEY))

        return {"status": "built", "repos": list(k.keys()), "summary": sol_knowledge.get_knowledge_summary()}

    except Exception as e:

        return JSONResponse({"error": str(e)}, status_code=500)





# ═══════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "sol",
        "version": "5.1",
        "env": SOL_ENV,
        "sol_core": SOL_CORE_OK,
        "ts": int(datetime.now(timezone.utc).timestamp())
    }

# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0" if IS_REPLIT else "127.0.0.1")
    port = int(os.environ.get("PORT", "8006"))

    print("☀️ Sol v5.5 — Servidor independiente (blindada)")
    print(f"   Entorno: {SOL_ENV}")
    print(f"   Hogar:   http://{host}:{port}/")
    print(f"   API:     http://{host}:{port}/api/sol/status")
    print(f"   sol_core: {'OK' if SOL_CORE_OK else 'NO DISPONIBLE'}")
    print("   Sin React, sin npm, sin build. Solo Sol.")

    uvicorn.run(app, host=host, port=port)
