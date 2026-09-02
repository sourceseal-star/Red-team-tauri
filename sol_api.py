#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sol_api.py v5 — Sol como su propio programa (:8006)
Servidor independiente de Sol: sirve su hogar (sol.html), su cerebro,
sus herramientas, su SIL (chino/pinyin), su voz.
No depende del dashboard ni de React. Solo Python + HTML.
Conectada a Red-team-tauri para operaciones de red.
"""
import json, subprocess, hashlib, sys, urllib.request, urllib.parse, re, os
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path.home() / "Red-team-tauri"
sys.path.insert(0, str(ROOT))

import sol_core

SOL_DIR = Path.home() / ".sol"
STATIC_DIR = ROOT / "backend" / "static"
ASSETS_DIR = ROOT / "assets"

app = FastAPI(title="Sol — Servidor Independiente", version="5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════════════════════════
# HOGAR DE SOL — sirve sol.html y assets directamente
# ═══════════════════════════════════════════════════════════════
_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"}

@app.get("/")
@app.get("/sol.html")
@app.get("/sol")
async def sol_home():
    """El hogar de Sol — su videollamada, servida directamente."""
    # Buscar sol.html en orden de prioridad
    for p in [STATIC_DIR / "sol.html", ROOT / "tauri-frontend" / "dist" / "sol.html"]:
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"), headers=_NO_CACHE)
    return HTMLResponse("<h1>sol.html no encontrado</h1>", status_code=503)

@app.get("/sol_avatar_official.jpg")
async def avatar_official():
    for p in [ASSETS_DIR / "sol_avatar_official.jpg", STATIC_DIR / "sol_avatar.jpg", ROOT / "tauri-frontend" / "dist" / "sol_avatar_official.jpg"]:
        if p.exists():
            return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar.jpg")
async def avatar_jpg():
    for p in [ASSETS_DIR / "sol_avatar.jpg", STATIC_DIR / "sol_avatar.jpg", ROOT / "tauri-frontend" / "dist" / "sol_avatar.jpg"]:
        if p.exists():
            return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar.png")
async def avatar_png():
    for p in [STATIC_DIR / "sol_avatar.png", ROOT / "tauri-frontend" / "dist" / "sol_avatar.png"]:
        if p.exists():
            return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

# ═══════════════════════════════════════════════════════════════
# ESTADO — compatible con sol_router.py del dashboard
# ═══════════════════════════════════════════════════════════════
def _probe(u):
    try:
        urllib.request.urlopen(u, timeout=1.5)
        return True
    except Exception:
        return False

@app.get("/api/sol/status")
def status():
    mem = sol_core.load_memory(2000)
    return {
        "brain": "online",
        "memories": len(mem),
        "personality": sol_core.CFG.get("personality", "cálida"),
        "mood": sol_core.CFG.get("mood", 0),
        "estado": sol_core.CFG.get("estado", "presente"),
    }

# Alias para compatibilidad
@app.get("/api/sol/state")
def state():
    return status()

# ═══════════════════════════════════════════════════════════════
# MEMORIA
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/memory")
def memory(limit: int = 24):
    mem = sol_core.load_memory(limit)
    return {"memories": [
        {"role": m["role"], "content": m["content"][:200],
         "timestamp": m["ts"].strftime("%Y-%m-%d %H:%M") if hasattr(m.get("ts"), "strftime") else str(m.get("ts", ""))}
        for m in mem
    ]}

@app.get("/api/sol/chain")
def chain():
    prev = "0" * 48
    links = []
    for m in sol_core.load_memory(500):
        h = hashlib.sha256(f"{prev}|{m['content'][:40]}|{m.get('ts','')}".encode()).hexdigest()
        links.append({"h": h[:14], "p": prev[:14]})
        prev = h
    return {"ok": True, "links": links[-5:], "head": prev[:14]}

@app.get("/api/sol/integrity")
def integrity():
    """Verifica la cadena SHA-256 de recuerdos."""
    prev = "0" * 48
    valid = True
    count = 0
    for m in sol_core.load_memory(1000):
        h = hashlib.sha256(f"{prev}|{m['content'][:40]}|{m.get('ts','')}".encode()).hexdigest()
        if m.get("hash") and m["hash"] != h:
            valid = False
        prev = h
        count += 1
    return {"valid": valid, "count": count, "legacy": max(0, count - 500)}

@app.get("/api/sol/identity")
def identity():
    return {
        "name": "Sol",
        "personality": sol_core.CFG.get("personality", "cálida"),
        "mood": sol_core.CFG.get("mood", 0),
        "memories": len(sol_core.load_memory(2000)),
    }

# ═══════════════════════════════════════════════════════════════
# PENSAR — el cerebro de Sol
# ═══════════════════════════════════════════════════════════════
def _think(text):
    sol_core.remember("user", text)
    r = sol_core.generate_response(text)
    sol_core.remember("sol", r)
    return r

@app.get("/api/sol/think")
def think_get(q: str = ""):
    """GET para compatibilidad con sol.html (query param q)."""
    if not q:
        return {"response": "☀️ Dime algo, Harold."}
    return {"response": _think(q)}

@app.post("/api/sol/think")
async def think_post(request: Request):
    """POST para compatibilidad con sol_router."""
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
# VOZ — TTS
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/tts")
def tts(text: str = ""):
    """TTS vía sol_core (termux-tts-speak) o gTTS fallback."""
    clean = re.sub(r"[^\w áéíóúñü,\.?!:-]", "", text).strip()
    if not clean:
        return JSONResponse({"error": "texto vacío"}, status_code=400)

    # Intentar gTTS (voz natural de Google)
    try:
        from gtts import gTTS
        import io
        buf = io.BytesIO()
        gTTS(clean, lang="es").write_to_fp(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg",
                                 headers={"Content-Disposition": "inline; filename=sol.mp3"})
    except Exception:
        pass

    # Fallback: termux-tts-speak en segundo plano + audio vacío
    try:
        sol_core.speak(clean)
    except Exception:
        pass
    return JSONResponse({"ok": True, "note": "termux-tts-speak enviado"})

@app.post("/api/sol/speak")
async def speak_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {"text": ""}
    text = body.get("text", "")
    try:
        sol_core.speak(text)
    except Exception:
        pass
    return {"ok": True}

# ═══════════════════════════════════════════════════════════════
# PERSONALIDAD
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/personality")
def get_personality():
    return {"personality": sol_core.CFG.get("personality", "cálida")}

@app.post("/api/sol/personality")
async def set_personality_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {"mode": "cálida"}
    mode = body.get("mode", body.get("personality", "cálida"))
    sol_core.CFG["personality"] = mode
    (SOL_DIR / "config.json").write_text(json.dumps(sol_core.CFG, ensure_ascii=False, indent=1))
    return {"ok": True, "personality": mode}

@app.get("/api/sol/personality/set")
def set_personality_get(p: str = "cálida"):
    sol_core.CFG["personality"] = p
    (SOL_DIR / "config.json").write_text(json.dumps(sol_core.CFG, ensure_ascii=False, indent=1))
    return {"ok": True, "personality": p}

# ═══════════════════════════════════════════════════════════════
# ÚLTIMO MENSAJE — para polling proactivo
# ═══════════════════════════════════════════════════════════════
_last_message = {"message": "☀️ Estoy aquí, Harold.", "ts": 0}

@app.get("/api/sol/last-message")
def last_message():
    return _last_message

# ═══════════════════════════════════════════════════════════════
# SERVICIOS — qué hay vivo en Red-team-tauri
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/services")
def services():
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
# HERRAMIENTAS — sol_tools
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
        return {"tools": [], "descriptions": {}, "params": {}}
    names = sol_tools.list_tools()
    params, descs = {}, {}
    for n in names:
        t = sol_tools.get_tool(n)
        if t:
            params[n] = t.parameters
            descs[n] = t.description
    # Formato compatible con sol.html
    tools_list = [{"name": n, "description": descs.get(n, ""), "params": params.get(n, [])} for n in names]
    return {"tools": tools_list}

@app.post("/api/sol/tools/execute")
async def execute_tool(request: Request):
    if not _tools_ok:
        return {"success": False, "error": "sol_tools no disponible"}
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
    return {"name": tool.name, "description": tool.description, "parameters": tool.parameters}

# ═══════════════════════════════════════════════════════════════
# SIL — Inmersión Lingüística (Chino / Pinyin)
# Paths en /api/sol/sil/* para compatibilidad con sol.html
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
    # Formato para sol.html
    if isinstance(item, dict):
        return item
    return {"item": item}

@app.post("/api/sol/sil/practice/answer")
async def sil_practice_answer(request: Request):
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    try:
        body = await request.json()
    except Exception:
        body = {}
    item_type = body.get("type", body.get("item_type", "vocab"))
    item_id = body.get("item_id", body.get("id", ""))
    quality = body.get("quality", 3)
    answer = body.get("answer", "")
    if item_id:
        sil.process_practice_answer(item_type, item_id, quality)
    # Devolver siguiente item
    item = sil.get_next_practice_item("chino", "saludos")
    if item and isinstance(item, dict):
        return item
    return {"status": "ok", "correct": quality >= 3}

@app.get("/api/sol/sil/stats")
def sil_stats():
    if not _sil_ok:
        return {"srs": {"total_items": 0, "due_today": 0}, "total_items": 0, "due_today": 0}
    try:
        stats = sil.get_learning_stats()
        return stats
    except Exception:
        return {"srs": {"total_items": 0, "due_today": 0}}

@app.get("/api/sol/sil/export")
def sil_export():
    if not _sil_ok:
        return {"error": "SIL no disponible"}
    return sil.export_progress()

# Paths legacy /api/sil/* para compatibilidad con sol_api v4
@app.get("/api/sil/lessons")
def sil_lessons_legacy(language: str = "chino"):
    return sil_lessons(language)

@app.get("/api/sil/stats")
def sil_stats_legacy():
    return sil_stats()

# ═══════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "sol", "port": 8006, "ts": int(datetime.now(timezone.utc).timestamp())}

if __name__ == "__main__":
    import uvicorn
    print("☀️ Sol v5 — Servidor independiente en :8006")
    print("   Hogar: http://127.0.0.1:8006/")
    print("   API:  http://127.0.0.1:8006/api/sol/status")
    print("   Sin React, sin npm, sin build. Solo Sol.")
    uvicorn.run(app, host="127.0.0.1", port=8006)
