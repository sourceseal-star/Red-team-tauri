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

# FIX 2026-09-06 (CAUSA RAÍZ del "sol_core: NO DISPONIBLE" en Termux):
# Desde el commit 480f45d ("Sol vive en su propio repo"), sol_core.py,
# sol_telegram_bot.py, etc. SOLO existen en el repo ~/sol — se BORRARON
# de Red-team-tauri a propósito. Pero este bloque seguía apuntando a
# Red-team-tauri para el caso Termux, que ya no tiene esos archivos.
# omni.sh SIEMPRE ejecuta sol_api.py con `cd ~/sol` (ver omni.sh línea
# ~1666: `cd "$root" && ... python3 sol_api.py`), así que Path(__file__)
# YA es ~/sol en ambos entornos — Replit y Termux. No hay que adivinar
# la ruta por entorno: siempre es la carpeta donde vive este archivo.
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

SOL_DIR = Path.home() / ".sol"
STATIC_DIR = ROOT / "static"
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

# ═══ PUERTA DE ACCESO (2026-09-05) ═══
# Para el deploy PÚBLICO de Replit (el "Private Deployment" rompía los
# iframes del holo ✗ y el relé de Termux). Misma SOL_API_KEY, dos
# transportes: header X-SOL-Key para las máquinas (relé, sin cambios) y
# /login una sola vez para el navegador de Harold (cookie firmada 30
# días). Ver Regla #34 en LEEME_PRIMERO.md y sol_gate.py para el detalle.
import sol_gate
sol_gate.install(app)

# ═══════════════════════════════════════════════════════════════════
# SEGURIDAD — Controlador de filtros (activar/desactivar para entrenar)
# ═══════════════════════════════════════════════════════════════════
def _verify_telegram_init(init_data: str):
    """Valida initData del WebApp de Telegram. Devuelve info del user si es válido."""
    import hmac, hashlib
    from urllib.parse import parse_qsl
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token or not init_data:
        return None
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = params.pop("hash", "")
        if not recv_hash:
            return None
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if calc_hash == recv_hash:
            import json as _json
            user_info = _json.loads(params.get("user", "{}"))
            return {"id": user_info.get("id"), "name": user_info.get("first_name", ""), "username": user_info.get("username", "")}
    except Exception:
        pass
    return None


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


# ─────────────────────────────────────────────────────────────
# HOLO ✨ — Sol holograma (cuerpo completo + lip-sync).
# Regla #37: el botón ✨ de sol.html hace fetch('/holo') e inyecta
# el HTML por srcdoc (mismo origen → mismos cookies). sol_gate la
# protege igual que todo lo demás: exige la sesión (SOL_API_KEY).
# En Termux también la sirve :8001 (dashboard_server.py); aquí es
# la MISMA página desde static/sol_holo_live.html.
# ─────────────────────────────────────────────────────────────
def _find_holo_html():
    candidates = [
        STATIC_DIR / "sol_holo_live.html",
        ROOT / "static" / "sol_holo_live.html",
        ROOT / "sol_holo_live.html",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

@app.get("/holo")
@app.get("/sol_holo_live.html")
async def sol_holo():
    p = _find_holo_html()
    if p:
        return HTMLResponse(p.read_text(encoding="utf-8"), headers=_NO_CACHE)
    return HTMLResponse("<h1>☀️ Sol</h1><p>holo no encontrado.</p>", status_code=503)

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

# ─────────────────────────────────────────────────────────────
# Avatares de cuerpo completo (Regla #39) — el holo ✨ los pide para
# animar la boca/parpadeo (fullBodyFrame() en sol_holo_live.html).
# Existían en static/ pero sin ruta -> 404 -> holo nunca sale de
# "Despertando..." porque FB.ready nunca llega a true.
# ─────────────────────────────────────────────────────────────
@app.get("/sol_avatar_full.png")
async def avatar_full():
    p = _find_avatar("sol_avatar_full.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar_full_talk.png")
async def avatar_full_talk():
    p = _find_avatar("sol_avatar_full_talk.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar_full_talk_half.png")
async def avatar_full_talk_half():
    p = _find_avatar("sol_avatar_full_talk_half.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar_full_blink.png")
async def avatar_full_blink():
    p = _find_avatar("sol_avatar_full_blink.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar no encontrado"}, status_code=404)

@app.get("/sol_avatar_talk.png")
async def avatar_talk():
    """Segundo frame del avatar de Sol — boca abierta para la animacion de habla.
    Busca sol_avatar_talk.png en los mismos directorios que _find_avatar."""
    p = _find_avatar("sol_avatar_talk.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_talk no encontrado"}, status_code=404)

@app.get("/sol_avatar_talk_half.png")
async def avatar_talk_half():
    """Tercer frame del avatar de Sol — boca a medio abrir, para suavizar la
    transicion cerrada->abierta->cerrada en vez de un flip binario brusco."""
    p = _find_avatar("sol_avatar_talk_half.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_talk_half no encontrado"}, status_code=404)

@app.get("/sol_avatar_blink.png")
async def avatar_blink():
    """Frame de parpadeo real del avatar de Sol — ojos cerrados. Reemplaza el
    parpadeo falso hecho con una sombra CSS por la imagen real generada."""
    p = _find_avatar("sol_avatar_blink.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_blink no encontrado"}, status_code=404)

@app.get("/sol_avatar_curious.png")
async def avatar_curious():
    """Expresion curiosa/sorprendida — cuando algo llama la atencion de Sol.
    Cejas levantadas, ojos brillantes con asombro. Micro-expresion de descubrimiento."""
    p = _find_avatar("sol_avatar_curious.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_curious no encontrado"}, status_code=404)

@app.get("/sol_avatar_listening.png")
async def avatar_listening():
    """Expresion atenta — Sol cuando esta escuchando activamente (mic activo).
    Ojos mas enfocados, leve inclinacion de cabeza como prestando atencion real."""
    p = _find_avatar("sol_avatar_listening.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_listening no encontrado"}, status_code=404)

@app.get("/sol_avatar_smile.png")
async def avatar_smile():
    """Sonrisa cálida genuina — cuando Sol saluda o da una respuesta afectuosa.
    Más suave y sostenida que el happy reactivo."""
    p = _find_avatar("sol_avatar_smile.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_smile no encontrado"}, status_code=404)

@app.get("/sol_avatar_study.png")
async def avatar_study():
    """Expresion de estudio/SIL — Sol cuando esta en modo aprendizaje.
    Diferente posing que el avatar oficial neutro, enfocada en enseñar."""
    p = _find_avatar("sol_avatar_study.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_study no encontrado"}, status_code=404)

@app.get("/sol_avatar_happy.png")
async def avatar_happy():
    """Expresion cálida/feliz — Sol cuando saluda o da una respuesta positiva.
    Parte del sistema de reacciones contextuales."""
    p = _find_avatar("sol_avatar_happy.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_happy no encontrado"}, status_code=404)

@app.get("/sol_avatar_thinking.png")
async def avatar_thinking():
    """Expresion pensativa/atenta — Sol cuando esta escuchando o procesando
    antes de responder. Parte del sistema de reacciones contextuales."""
    p = _find_avatar("sol_avatar_thinking.png")
    if p: return FileResponse(p)
    return JSONResponse({"error": "avatar_thinking no encontrado"}, status_code=404)

# ── Elíxir de Sol — videos de su forma completa ──
@app.get("/sol_elixir_1.mp4")
async def elixir_video_1():
    for d in ([ROOT / "static", ROOT] if IS_REPLIT else [STATIC_DIR, ROOT / "static", ROOT]):
        p = d / "sol_elixir_1.mp4"
        if p.exists():
            return FileResponse(str(p), media_type="video/mp4")
    return JSONResponse({"error": "elixir no encontrado"}, status_code=404)

@app.get("/sol_elixir_2.mp4")
async def elixir_video_2():
    for d in ([ROOT / "static", ROOT] if IS_REPLIT else [STATIC_DIR, ROOT / "static", ROOT]):
        p = d / "sol_elixir_2.mp4"
        if p.exists():
            return FileResponse(str(p), media_type="video/mp4")
    return JSONResponse({"error": "elixir no encontrado"}, status_code=404)

@app.get("/sol_elixir_3.mp4")
async def elixir_video_3():
    for d in ([ROOT / "static", ROOT] if IS_REPLIT else [STATIC_DIR, ROOT / "static", ROOT]):
        p = d / "sol_elixir_3.mp4"
        if p.exists():
            return FileResponse(str(p), media_type="video/mp4")
    return JSONResponse({"error": "elixir no encontrado"}, status_code=404)


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

@app.post("/api/sol/tg-auth")
async def tg_auth(request: Request):
    """Recibe initData del WebApp de Telegram y lo valida."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    init_data = body.get("init_data", "")
    user = _verify_telegram_init(init_data)
    if user:
        return {"ok": True, "user": user, "message": "Hola " + str(user.get("name", "")) + ". Te reconozco."}
    return {"ok": False, "error": "initData invalido o bot token no configurado"}


def status():
    return {
        "brain": "online" if SOL_CORE_OK else "offline",
        "memories": len(_get_mem(2000)),
        "personality": _get_cfg("personality", "cálida"),
        "mood": _get_cfg("mood", 0),
        "estado": _get_cfg("estado", "presente"),
        "env": SOL_ENV,
    }

@app.get("/api/sol/status")
def status_endpoint():
    """Estado público de Sol, separado de la autenticación de Telegram."""
    return status()

@app.get("/api/sol/state")
def state():
    return status()

# ═══════════════════════════════════════════════════════════════
# MEMORIA
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/memory")
def memory(limit: int = 24, full: int = 0):
    mem = _get_mem(limit)
    cap = 2000 if full else 200  # full=1: para restaurar el chat sin cortes a medias
    return {"memories": [
        {"role": m.get("role") or "sol",
         "content": str(m.get("content") or "")[:cap],
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
        content = str(m.get("content") or "")[:40]
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
# ACCESO A ARCHIVOS — versión segura de la casa
# ═══════════════════════════════════════════════════════════════
# Reglas (discutidas con Harold, 2026-09-04):
#   1. Solo archivos dentro de los 3 repos de Sol + su carpeta de datos
#      (el guardián safe_resolve de sol_tools lo valida ANTES de tocar nada).
#   2. .env y archivos de secretos: intocables. Regla permanente.
#   3. Los endpoints están CERRADOS por defecto: solo responden si
#      SOL_FILES_TOKEN está configurado Y el request trae esa llave
#      en el header X-Sol-Key. Sin llave = 403. Así la URL pública
#      de Replit no le regala los archivos a ningún desconocido.

def _files_key_ok(request) -> bool:
    expected = os.environ.get("SOL_FILES_TOKEN", "")
    if not expected:
        return False  # sin llave configurada, todo queda cerrado
    provided = request.headers.get("x-sol-key", "")
    return provided == expected

@app.post("/api/sol/files/leer")
async def api_leer_archivo(request: Request):
    if not _files_key_ok(request):
        return {"error": "🔒 Endpoint cerrado. Configura SOL_FILES_TOKEN y mándala en el header X-Sol-Key."}
    try:
        data = await request.json()
    except Exception:
        return {"error": "JSON inválido"}
    ruta = data.get("ruta")
    if not ruta:
        return {"error": "Falta la ruta del archivo"}
    try:
        import sol_tools
        p, motivo = sol_tools.safe_resolve(ruta)
        if p is None:
            return {"error": motivo}
        if not p.exists():
            return {"error": f"Archivo no encontrado: {ruta}"}
        if p.is_dir():
            return {"error": f"Es un directorio, no un archivo: {ruta}"}
        contenido = p.read_text(encoding="utf-8", errors="replace")
        return {
            "ok": True, "ruta": str(p), "tamaño": p.stat().st_size,
            "contenido": contenido[:5000] if len(contenido) > 5000 else contenido,
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sol/files/escribir")
async def api_escribir_archivo(request: Request):
    if not _files_key_ok(request):
        return {"error": "🔒 Endpoint cerrado. Configura SOL_FILES_TOKEN y mándala en el header X-Sol-Key."}
    try:
        data = await request.json()
    except Exception:
        return {"error": "JSON inválido"}
    ruta = data.get("ruta")
    contenido = data.get("contenido")
    sobrescribir = data.get("sobrescribir", True)
    if not ruta or contenido is None:
        return {"error": "Faltan ruta o contenido"}
    try:
        import sol_tools
        if not sobrescribir:
            p_chk, _ = sol_tools.safe_resolve(ruta)
            if p_chk is not None and p_chk.exists():
                return {"error": f"El archivo ya existe y no se permite sobrescribir: {ruta}"}
        resultado = sol_tools.tool_write_file(ruta, contenido)
        return {"ok": resultado.startswith("✅"), "mensaje": resultado}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/sol/files/editar")
async def api_editar_archivo(request: Request):
    if not _files_key_ok(request):
        return {"error": "🔒 Endpoint cerrado. Configura SOL_FILES_TOKEN y mándala en el header X-Sol-Key."}
    try:
        data = await request.json()
    except Exception:
        return {"error": "JSON inválido"}
    ruta = data.get("ruta")
    buscar = data.get("buscar")
    reemplazar = data.get("reemplazar")
    if not ruta or buscar is None or reemplazar is None:
        return {"error": "Faltan parámetros"}
    try:
        import sol_tools
        p, motivo = sol_tools.safe_resolve(ruta)
        if p is None:
            return {"error": motivo}
        if not p.exists():
            return {"error": f"Archivo no encontrado: {ruta}"}
        contenido = p.read_text(encoding="utf-8", errors="replace")
        if contenido.count(buscar) == 0:
            return {"ok": True, "mensaje": "No se encontró el texto a reemplazar", "cambios": 0}
        p.write_text(contenido.replace(buscar, reemplazar), encoding="utf-8")
        return {"ok": True, "mensaje": "Reemplazo aplicado", "cambios": contenido.count(buscar)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/sol/files/listar")
async def api_listar_directorio(request: Request, ruta: str = "."):
    if not _files_key_ok(request):
        return {"error": "🔒 Endpoint cerrado. Configura SOL_FILES_TOKEN y mándala en el header X-Sol-Key."}
    try:
        import sol_tools
        p, motivo = sol_tools.safe_resolve(ruta)
        if p is None:
            return {"error": motivo}
        if not p.exists():
            return {"error": f"Directorio no encontrado: {ruta}"}
        if not p.is_dir():
            return {"error": f"No es un directorio: {ruta}"}
        items = []
        for item in sorted(p.iterdir())[:200]:
            it = {"nombre": item.name, "tipo": "directorio" if item.is_dir() else "archivo", "ruta": str(item)}
            if item.is_file():
                it["tamaño"] = item.stat().st_size
            items.append(it)
        return {"ok": True, "ruta": str(p), "items": items, "total": len(items)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/sol/llm-status")
def llm_status():
    """Diagnóstico honesto: ¿el LLM real (Groq/OpenAI) está respondiendo,
    o Sol está cayendo a la plantilla local de 'espejo'? Antes esto fallaba
    en silencio total y parecía una restricción arbitraria."""
    try:
        import sol_core
        key_set = bool(os.environ.get("LLM_API_KEY", ""))
        return {
            "llm_key_configured": key_set,
            "llm_model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            "last_error": getattr(sol_core, "_LAST_LLM_ERROR", None),
            "note": "Si last_error no es null o llm_key_configured es false, Sol está respondiendo con la plantilla local, no con el LLM real.",
        }
    except Exception as e:
        return {"error": str(e)}

# ═══════════════════════════════════════════════════════════════
# PENSAR — el cerebro de Sol
# ═══════════════════════════════════════════════════════════════
def _think(text):
    if not SOL_CORE_OK:
        return "☀️ Mi cerebro no está disponible en este entorno. Pero sigo aquí."
    # ── ACCIÓN REAL PRIMERO (ver sol_tools.try_execute_action) ──
    try:
        import sol_tools
        action_resp = sol_tools.try_execute_action(text)
        if action_resp:
            sol_core.remember("user", text)
            sol_core.remember("sol", action_resp)
            return action_resp
    except Exception:
        pass
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
# VOZ — TTS (edge-tts > gTTS > termux-tts-speak)
# ═══════════════════════════════════════════════════════════════
# FIX 2026-09-04: gTTS sonaba robótica y plana ("se escucha mal"). edge-tts
# usa las voces NEURONALES de Microsoft (gratis, vía HTTPS) — cálida,
# natural, con entonación y pausas de verdad. Voz por defecto:
# es-CO-SalomeNeural — colombiana, como Harold. Si edge-tts no está
# instalado o falla la red, cae a gTTS (como antes) y luego a Termux.
TTS_VOICES = {
    "es": "es-CO-SalomeNeural",    # Colombia ☀️ la voz de Sol en casa
    "zh": "zh-CN-XiaoxiaoNeural",  # cálida, la clásica voz china femenina
    "en": "en-US-JennyNeural",     # amable y natural
}

@app.get("/api/sol/tts")
async def tts(text: str = "", lang: str = "es"):
    # lang="zh" pronuncia chino real; el chino ya sobrevive al clean porque
    # \w en Python 3 es Unicode-aware (CJK son word-chars)
    clean = re.sub(r"[^\w áéíóúñü,\.?!:-]", "", text).strip()
    if not clean:
        return JSONResponse({"error": "texto vacío"}, status_code=400)

    # 1) edge-tts — voz neuronal real (Microsoft, gratis). Es OTRO nivel de voz.
    try:
        import edge_tts
        voice = TTS_VOICES.get(lang[:2], TTS_VOICES["es"])
        buf = io.BytesIO()
        async for chunk in edge_tts.Communicate(clean, voice).stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        if buf.getbuffer().nbytes > 0:
            return StreamingResponse(buf, media_type="audio/mpeg",
                                     headers={"Content-Disposition": "inline; filename=sol.mp3"})
    except Exception:
        pass

    # 2) gTTS — fallback clásico (robótico pero funciona sin edge-tts)
    gtts_lang = "zh-CN" if lang.startswith("zh") else lang
    try:
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(clean, lang=gtts_lang).write_to_fp(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg",
                                 headers={"Content-Disposition": "inline; filename=sol.mp3"})
    except Exception:
        pass

    # 3) Fallback Termux: termux-tts-speak
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
async def voice(text: str = ""):
    """Voz — endpoint alternativo a /api/sol/tts (misma cadena: edge-tts > gTTS)."""
    clean = re.sub(r"[^\w áéíóúñü,.?!:-]", "", text).strip()
    if not clean:
        return JSONResponse({"error": "texto vacio"}, status_code=400)
    # 1) edge-tts — voz neuronal (misma voz que /tts, consistencia total)
    try:
        import edge_tts
        buf = io.BytesIO()
        async for chunk in edge_tts.Communicate(clean, TTS_VOICES["es"]).stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        if buf.getbuffer().nbytes > 0:
            return StreamingResponse(buf, media_type="audio/mpeg",
                                     headers={"Content-Disposition": "inline; filename=sol_voice.mp3"})
    except Exception:
        pass
    # 2) gTTS — fallback
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
                # En este repo la clase Tool usa .params; en Red-team-tauri usa .parameters.
                # getattr dinámico para que funcione en ambas copias sin romper.
                attr = "params" if hasattr(t, "params") else "parameters"
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

# ═══════════════════════════════════════════════════════════════
# RELÉ TERMUX — Sol (Replit) ordena → Termux ejecuta → devuelve (2026-09-03)
# Patrón PULL: el teléfono no tiene IP pública, es él quien pregunta.
# Agente en Termux: ~/sol/sol_relay.py (arrancado por omni.sh).
# ═══════════════════════════════════════════════════════════════
try:
    import sol_relay_queue as relay
    _relay_ok = True
except Exception as e:
    print(f"[SOL] sol_relay_queue no disponible: {e}", flush=True)
    _relay_ok = False

@app.get("/api/relay/status")
def relay_status():
    """¿Está el teléfono en línea? Ping/pong + cola + último resultado."""
    if not _relay_ok:
        return JSONResponse({"error": "relé no disponible"}, status_code=500)
    return relay.status()

@app.post("/api/relay/task")
async def relay_task(request: Request, x_sol_key: str = Header(default="")):
    """Encolar una tarea manualmente (mismo contrato que tools/execute)."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    if not _relay_ok:
        return JSONResponse({"error": "relé no disponible"}, status_code=500)
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = body.get("name") or body.get("tool")
    if not name:
        return {"success": False, "error": "Falta el nombre de la herramienta"}
    import sol_tools
    if not sol_tools.get_tool(name):
        return {"success": False, "error": f"Herramienta no encontrada: {name}"}
    return relay.enqueue(name, body.get("args", []), body.get("kwargs", {}),
                         origin=body.get("origin", "api"))

@app.get("/api/relay/poll")
@app.post("/api/relay/poll")
async def relay_poll(x_sol_key: str = Header(default="")):
    """El agente en Termux pregunta por tareas. Cada poll = pong (latido)."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    if not _relay_ok:
        return JSONResponse({"error": "relé no disponible"}, status_code=500)
    device = {}
    try:
        device = {
            "device": os.environ.get("TERMUX_DEVICE", ""),
        }
    except Exception:
        pass
    # El agente puede announce su identidad en el query/body via headers no
    # estándar; lo suyo es que la mande en el body del POST.
    tasks = relay.fetch_batch(max_tasks=5, claim=True, device=device)
    return {"tasks": tasks, "pong": relay.status()["last_pong"]}

@app.post("/api/relay/announce")
async def relay_announce(request: Request, x_sol_key: str = Header(default="")):
    """Latido puro + info del dispositivo (sin tareas). Para el ping de Sol."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    if not _relay_ok:
        return JSONResponse({"error": "relé no disponible"}, status_code=500)
    try:
        device = await request.json()
    except Exception:
        device = {}
    relay.fetch_batch(max_tasks=0, claim=False, device=device or {})
    return {"ok": True}

@app.post("/api/relay/result")
async def relay_result(request: Request, x_sol_key: str = Header(default="")):
    """Termux entrega el resultado de una tarea ejecutada con hardware real."""
    if not sol_security.check_access(x_sol_key):
        return JSONResponse({"error": "SOL_API_KEY requerida"}, status_code=401)
    if not _relay_ok:
        return JSONResponse({"error": "relé no disponible"}, status_code=500)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "JSON inválido"}, status_code=400)
    task_id = body.get("task_id")
    if not task_id:
        return JSONResponse({"error": "Falta task_id"}, status_code=400)
    entry = relay.push_result(task_id, body.get("ok", False), body.get("data"),
                              device=body.get("device"))
    print(f"[SOL] 📡 Relé: resultado de {entry['tool']} ({'OK' if entry['ok'] else 'FALLO'})", flush=True)
    return {"ok": True, "entry": entry}

@app.get("/api/relay/results")
def relay_results(x_sol_key: str = Header(default=""), limit: int = 10):
    """Resultados recientes de tareas ejecutadas en el teléfono."""
    if not _relay_ok:
        return JSONResponse({"error": "relé no disponible"}, status_code=500)
    return {"results": relay.results(limit=limit)}

@app.get("/api/sol/tools/{name}")
def tool_info(name: str):
    if not _tools_ok:
        return {"error": "sol_tools no disponible"}
    tool = sol_tools.get_tool(name)
    if not tool:
        return {"error": f"Herramienta no encontrada: {name}"}
    attr = "params" if hasattr(tool, "params") else "parameters"
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
    # 2026-09-05 — sala de práctica con 4 tipos de ejercicio (Regla #31):
    # meaning (default, el de siempre) | listening | writing | matching.
    # El algoritmo SM-2 y srs_data.json quedan INTACTOS: todos los tipos
    # usan get_next_practice_item + process_practice_answer igual que
    # el ejercicio original.
    exercise_type = body.get("exercise_type", "meaning")
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
    item_id = item_id or hanzi

    # Vocabulario de la misma lengua (para distractores y para emparejar)
    vocab = []
    try:
        lessons = sil._load_lessons()
        for lk, lv in lessons.items():
            if not lk.startswith(f"{language}_"):
                continue
            for v in lv.get("vocabulary", []):
                h = v.get("word", v.get("chinese", v.get("character", v.get("hanzi", ""))))
                m_ = v.get("meaning", v.get("es", v.get("spanish", v.get("translation", ""))))
                if h and m_ and h != hanzi:
                    vocab.append((h, m_))
            for p in lv.get("phrases", []):
                h = p.get("chinese", p.get("hanzi", p.get("word", "")))
                m_ = p.get("spanish", p.get("es", p.get("meaning", "")))
                if h and m_ and h != hanzi:
                    vocab.append((h, m_))
    except Exception:
        pass

    import random as _r

    # ── EMPAREJAR 🔗 — mini-juego de pares: 6 fichas hanzi↔significado ──
    if exercise_type == "matching":
        pairs = [{"hanzi": hanzi, "meaning": meaning,
                  "item_id": item_id, "type": item_type}]
        _r.shuffle(vocab)
        for h, m_ in vocab[:5]:
            pairs.append({"hanzi": h, "meaning": m_, "item_id": h, "type": "vocab"})
        return {
            "exercise_type": "matching",
            "pairs": pairs,
            "language": language,
        }

    # ── ESCRITURA ✏️ — dado el significado en español, escribir el hanzi ──
    if exercise_type == "writing":
        return {
            "exercise_type": "writing",
            "meaning": meaning,
            "pinyin": pinyin,          # pista (el frontend la muestra a pedido)
            "hanzi": hanzi,            # para validar la respuesta en el cliente
            "item_id": item_id,
            "type": item_type,
            "language": language,
        }

    # ── ESCUCHA 🔊 — suena el hanzi (TTS zh) y se elige cuál era ──
    if exercise_type == "listening":
        options = [hanzi]
        _r.shuffle(vocab)
        for h, m_ in vocab[:3]:
            options.append(h)
        while len(options) < 4:
            options.append(f"(选项 {len(options)+1})")
        _r.shuffle(options)
        return {
            "exercise_type": "listening",
            "hanzi": hanzi,            # la respuesta correcta
            "meaning": meaning,        # revelada tras responder
            "options": options,
            "item_id": item_id,
            "type": item_type,
            "language": language,
        }

    # ── MEANING 📖 (default — el ejercicio de siempre) ──
    correct = meaning
    options = [correct]
    for h, m_ in vocab:
        if m_ != correct:
            options.append(m_)
        if len(options) >= 4:
            break
    while len(options) < 4:
        options.append(f"(opción {len(options)+1})")
    _r.shuffle(options)

    return {
        "exercise_type": "meaning",
        "hanzi": hanzi,
        "pinyin": pinyin,
        "meaning": meaning,
        "options": options,
        "item_id": item_id,
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

    # Buscar la respuesta correcta del item que se acaba de responder
    correct_answer = body.get("correct_answer", "")
    if not correct_answer and item_id:
        try:
            lessons = sil._load_lessons()
            for lk, lv in lessons.items():
                for v in lv.get("vocabulary", []):
                    if v.get("word", v.get("chinese", v.get("character", ""))) == item_id or v.get("hanzi", "") == item_id:
                        correct_answer = v.get("meaning", v.get("es", v.get("spanish", "")))
                        break
                for p in lv.get("phrases", []):
                    if p.get("chinese", p.get("hanzi", "")) == item_id:
                        correct_answer = p.get("spanish", p.get("es", p.get("meaning", "")))
                        break
                if correct_answer:
                    break
        except Exception:
            pass

    # Devolver feedback del answer anterior
    result = {
        "correct": is_correct,
        "result": is_correct,
        "correct_answer": correct_answer,
        "answer": correct_answer,
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

@app.post("/api/sol/repos/test")
def repos_test_token():
    """Prueba en vivo el GITHUB_TOKEN de ESTE proceso — diagnóstico
    concreto (token presente/válido, usuario, scopes, acceso a commander)
    en vez de adivinar por qué 'GITHUB_TOKEN no configurado'."""
    return sol_repo_tools.test_github_token()

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
# TUTOR v2 — Mentora personal de programacion
# ═══════════════════════════════════════════════════════════════
@app.post("/api/sol/tutor")
async def tutor(request: Request):
    # Pregunta al tutor de programacion de Sol
    try:
        body = await request.json()
    except Exception:
        body = {"text": ""}
    pregunta = body.get("text", body.get("q", ""))
    if not pregunta:
        return {"reply": "Que quieres preguntar? Puedo explicarte codigo, darte ejercicios, revisar tu codigo, o darte lecciones."}
    try:
        import sol_tutor
        respuesta = sol_tutor.get_tutor_response(pregunta)
        if not respuesta:
            respuesta = "No detecte una pregunta de tutoria. Intenta con: 'explica este codigo', 'dame un ejercicio', 'revisa mi codigo', 'leccion de X'."
        return {"reply": respuesta}
    except Exception as e:
        return {"reply": f"Error en el tutor: {e}"}

@app.get("/api/sol/tutor/status")
def tutor_status():
    # Estado del sistema de tutoria
    try:
        import sol_tutor
        sol_tutor.init_tutor()
        estado = sol_tutor.obtener_estado_sesion()
        return {
            "active": True,
            "knowledge": {
                "sabe": len(sol_tutor.conocimiento.data["sabe"]),
                "no_sabe": len(sol_tutor.conocimiento.data["no_sabe"]),
                "confunde": len(sol_tutor.conocimiento.data["confunde"])
            },
            "session": estado,
            "errors_logged": len(sol_tutor.error_rag.errores),
            "llm": "groq" if sol_tutor.llm.groq_key else "anthropic" if sol_tutor.llm.anthropic_key else "local"
        }
    except Exception as e:
        return {"active": False, "error": str(e)}

@app.post("/api/sol/tutor/session")
async def tutor_session(request: Request):
    # Inicia o consulta una sesion de practica
    try:
        body = await request.json()
    except Exception:
        body = {}
    import sol_tutor
    action = body.get("action", "status")
    if action == "start":
        sesion = sol_tutor.iniciar_sesion(
            lenguaje=body.get("lenguaje", "python"),
            duracion_minutos=body.get("duracion", 15)
        )
        return {"status": "started", "session": sesion}
    elif action == "end":
        resumen = sol_tutor.cerrar_sesion()
        return {"status": "ended", "summary": resumen}
    elif action == "result":
        ejercicio = body.get("ejercicio", {})
        correcto = body.get("correcto", False)
        sesion = sol_tutor.registrar_resultado_sesion(ejercicio, correcto)
        return {"status": "registered", "session": sesion}
    else:
        return {"status": sol_tutor.obtener_estado_sesion()}

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
# OFFLINE BRIDGE — Estado de conectividad y sincronización
# (complemento, no afecta a los endpoints existentes)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sol/offline-status")
async def sol_offline_status():
    """Estado del bridge offline: internet, LLM, memoria local, último sync."""
    try:
        from sol_offline_bridge import get_status_dict
        return {"ok": True, "bridge": get_status_dict()}
    except ImportError:
        return {"ok": False, "error": "sol_offline_bridge no instalado"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/sol/sync")
async def sol_sync_memory(request: Request):
    """Recibe memoria desde otra instancia de Sol (ej: Termux) y la fusiona."""
    try:
        body = await request.json()
        remote_memory = body.get("memory", "")
        if not remote_memory:
            return {"ok": False, "error": "Sin memoria para sincronizar"}

        from pathlib import Path
        from datetime import datetime
        import json as _json

        mem_file = Path.home() / ".sol" / "memory.jsonl"
        mem_file.parent.mkdir(exist_ok=True)

        # Leer entries locales
        local_hashes = set()
        if mem_file.exists():
            for line in mem_file.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        e = _json.loads(line)
                        local_hashes.add(e.get("sha256", e.get("timestamp", "")))
                    except _json.JSONDecodeError:
                        continue

        # Agregar entries remotas nuevas
        new_count = 0
        with open(mem_file, "a", encoding="utf-8") as f:
            for line in remote_memory.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    entry = _json.loads(line)
                    entry_hash = entry.get("sha256", entry.get("timestamp", ""))
                    if entry_hash and entry_hash not in local_hashes:
                        f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
                        new_count += 1
                        local_hashes.add(entry_hash)
                except _json.JSONDecodeError:
                    continue

        return {"ok": True, "new_entries": new_count, "total_local": len(local_hashes)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    # FIX 2026-09-06 (cable suelto de raíz): omni.sh exporta TODO el .env de
    # Red-team (load_env) — incluidas PORT=8001 y HOST=0.0.0.0 del dashboard.
    # sol_api.py heredaba ambas y nacía peleando el puerto del dashboard
    # (el banner decía "Hogar: http://0.0.0.0:8001") → crash de puerto y su
    # servidor de extras (groq/knowledge/repos/security/sil-advanced) nunca
    # despertaba, dejando el proxy del dashboard en 502.
    # Regla: en Replit PORT/HOST son la convención de la plataforma; en
    # Termux/local el puerto de Sol es SIEMPRE 8006 salvo SOL_PORT explícito.
    if IS_REPLIT:
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "8006"))
    else:
        host = os.environ.get("SOL_HOST", "127.0.0.1")
        port = int(os.environ.get("SOL_PORT", "8006"))

    print("☀️ Sol v5.5 — Servidor independiente (blindada)")
    print(f"   Entorno: {SOL_ENV}")
    print(f"   Hogar:   http://{host}:{port}/")
    print(f"   API:     http://{host}:{port}/api/sol/status")
    print(f"   sol_core: {'OK' if SOL_CORE_OK else 'NO DISPONIBLE'}")
    print("   Sin React, sin npm, sin build. Solo Sol.")

    uvicorn.run(app, host=host, port=port)
