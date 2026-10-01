"""HOLO 9.1 · Whisper Protocol — Sincronización Silenciosa con Retry Exponencial
FIX 2026-10-01 (auditoría del bundle): el bundle original anunciaba entregas
que nunca hizo (stubs que devolvían True sin ejecutar nada). Contrato:
ninguna acción externa sin handler REAL. Ahora:
- "latido_offline" es el ÚNICO handler real (escribe un log LOCAL) → delivered.
- Cualquier otro tool SIN handler real → status "no_handler", se archiva con
  su razón y NUNCA se cuenta como entregado. Sin mentiras.
- Fix adicional: obtener_siguiente() ahora persiste las depuraciones antes de
  retornar, y los mensajes deduplicados se retiran de la cola (antes el loop
  los releía por siempre).

El 9.0 encolaba acciones y las drenaba al volver a VERDE. El 9.1 hace lo mismo
pero con INTELIGENCIA: retry exponencial con jitter, deduplicación de mensajes,
priorización de cola, y un hilo whisper que opera en background sin tocar
el threadpool de FastAPI."""

import json, time, threading, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks

BASE = Path(__file__).parent / "data"
COLA_FILE = BASE / "whisper_cola.jsonl"
STATE_FILE = BASE / "whisper_state.json"
HASH_FILE = BASE / "whisper_dedup.json"     # hashes de mensajes ya enviados
RETRY_LOG = BASE / "whisper_retry.jsonl"
LATIDO_LOG = BASE / "whisper_latido.log"    # handler REAL: log local de latidos

router = APIRouter(prefix="/api/whisper", tags=["HOLO 9.1"])

# ─── Configuración de retry exponencial ─────────────────────────────────────

RETRY_CONFIG = {
    "base_delay": 2,          # segundos del primer retry
    "max_delay": 600,         # 10 min máximo (backoff duro)
    "max_attempts": 8,       # intentos totales antes de archivar como fallido
    "jitter": 0.3,           # ±30% de aleatoriedad para evitar thundering herd
    "success_window": 60,    # un peer se considera "vivo" si responde en 60s
}

def _jitter(delay):
    """Aplica jitter uniforme: delay ± jitter*delay"""
    import random
    return delay * (1 + random.uniform(-RETRY_CONFIG["jitter"], RETRY_CONFIG["jitter"]))

def _hash_msg(tool, payload):
    """Hash para deduplicación: mismo tool+payload no se reenvía."""
    s = json.dumps({"tool": tool, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()[:16]

# ─── Cola de mensajes ─────────────────────────────────────────────────────────

def encolar(tool: str, payload: dict, prioridad: int = 1, peer: str = "default"):
    """
    Encola un mensaje para sync.
    prioridad: 1=normal, 2=urgente, 3=crítico (no se pierde ni en ROJO sostenido)
    peer: identificador del peer destino (mesh)
    """
    BASE.mkdir(exist_ok=True, parents=True)
    msg_id = _hash_msg(tool, payload)
    timestamp = datetime.now().isoformat()

    msg = {
        "id": msg_id,
        "tool": tool,
        "payload": payload,
        "prioridad": prioridad,
        "peer": peer,
        "timestamp": timestamp,
        "attempts": 0,
        "next_retry": timestamp,  # ISO string, se convierte luego
        "status": "pending",       # pending | retrying | delivered | failed | no_handler | archived
    }

    with open(COLA_FILE, "a") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    _actualizar_estado()
    return msg_id

def leer_cola() -> list:
    if not COLA_FILE.exists():
        return []
    mensajes = []
    for linea in COLA_FILE.read_text().strip().splitlines():
        try:
            mensajes.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    # Ordenar por prioridad desc, luego por timestamp
    mensajes.sort(key=lambda m: (-m.get("prioridad", 1), m.get("timestamp", "")))
    return mensajes

def reescribir_cola(mensajes: list):
    """Reescribe la cola con la lista actual."""
    COLA_FILE.unlink(missing_ok=True)
    for m in mensajes:
        with open(COLA_FILE, "a") as f:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

def obtener_siguiente() -> Optional[dict]:
    """Obtiene el siguiente mensaje listo para enviar (attempts < max y next_retry pasado).
    FIX: persiste las depuraciones (delivered/archived) ANTES de retornar,
    para que no se pierdan si el ciclo termina temprano."""
    ahora = datetime.now()
    cola = leer_cola()
    cambio = False

    for msg in list(cola):
        if msg["status"] == "delivered":
            cola.remove(msg)
            cambio = True
            continue

        if msg["attempts"] >= RETRY_CONFIG["max_attempts"]:
            msg["status"] = "archived"
            with open(RETRY_LOG, "a") as f:
                f.write(json.dumps({**msg, "archived_at": ahora.isoformat()}, ensure_ascii=False) + "\n")
            cola.remove(msg)
            cambio = True
            continue

        next_retry = datetime.fromisoformat(msg["next_retry"])
        if next_retry > ahora:
            continue  # No está listo para retry aún

    # FIX: lo que quedó listo
    for msg in cola:
        if msg["status"] in ("pending", "retrying"):
            next_retry = datetime.fromisoformat(msg["next_retry"])
            if next_retry <= ahora and msg["attempts"] < RETRY_CONFIG["max_attempts"]:
                if cambio:
                    reescribir_cola(cola)
                return msg
    if cambio:
        reescribir_cola(cola)
    return None

# ─── Deduplicación ───────────────────────────────────────────────────────────

def es_deduplicado(msg_id: str) -> bool:
    """Check if message was already delivered successfully."""
    if not HASH_FILE.exists():
        return False
    try:
        hashes = json.loads(HASH_FILE.read_text())
        return msg_id in hashes
    except (json.JSONDecodeError, ValueError):
        return False

def marcar_entregado(msg_id: str):
    """Registra que el mensaje fue entregado exitosamente (SOLO tras handler real)."""
    BASE.mkdir(exist_ok=True, parents=True)
    try:
        hashes = json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}
    except (json.JSONDecodeError, ValueError):
        hashes = {}

    hashes[msg_id] = datetime.now().isoformat()
    # Mantener solo los últimos 1000 hashes
    if len(hashes) > 1000:
        items = sorted(hashes.items(), key=lambda kv: kv[1])
        hashes = dict(items[-500:])

    HASH_FILE.write_text(json.dumps(hashes, ensure_ascii=False, indent=2))

# ─── Consciencia de peer (Mesh) ──────────────────────────────────────────────

def marcar_peer_activo(peer: str):
    """Un peer respondió recientemente → se considera vivo."""
    peers = _cargar_state().get("peers", {})
    peers[peer] = {
        "ultimo_contacto": datetime.now().isoformat(),
        "vivo": True,
    }
    _guardar_state_field("peers", peers)

def peer_activo(peer: str) -> bool:
    peers = _cargar_state().get("peers", {})
    if peer not in peers:
        return False
    try:
        ultimo = datetime.fromisoformat(peers[peer]["ultimo_contacto"])
    except (KeyError, ValueError):
        return False
    return (datetime.now() - ultimo).total_seconds() < RETRY_CONFIG["success_window"]

def _cargar_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return {"whisper_vivo": False, "cola_size": 0, "peers": {}, "stats": {}}

def _guardar_state_field(key: str, value):
    state = _cargar_state()
    state[key] = value
    BASE.mkdir(exist_ok=True, parents=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def _actualizar_estado():
    cola = leer_cola()
    pendientes = [m for m in cola if m["status"] in ("pending", "retrying")]
    _guardar_state_field("cola_size", len(pendientes))
    _guardar_state_field("whisper_vivo", True)

# ─── Ejecutor de sync — SOLO handlers REALES ────────────────────────────────
# FIX CRÍTICO (auditoría 2026-10-01): el bundle original tenía stubs que
# devolvían (True, "git push executed") SIN ejecutar nada → Whisper "anunciaba
# entregas que nunca hizo". Contrato del sistema: NINGUNA acción externa sin
# handler real. Los tools sin handler quedan en "no_handler" y NUNCA se
# marcan como entregados. Cuando exista un handler real (p.ej. git push
# verificado), se registra aquí y solo entonces contará como entrega.

def _handler_latido_offline(payload: dict):
    """Handler REAL (interno): registra el latido en un log local. Nada externo."""
    BASE.mkdir(exist_ok=True, parents=True)
    with open(LATIDO_LOG, "a") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "payload": payload,
        }, ensure_ascii=False) + "\n")
    return True, "latido registrado localmente"

# Registry de handlers REALES. Agregar aquí SOLO cuando el handler exista de verdad.
SYNC_HANDLERS = {
    "latido_offline": _handler_latido_offline,
}

def sync_tool(tool: str, payload: dict) -> tuple[bool, str]:
    """
    Ejecuta la herramienta de sync. Devuelve (éxito, mensaje).
    - Si hay handler REAL registrado → lo ejecuta y reporta su resultado real.
    - Si NO hay handler real → (False, "sin handler real") — NUNCA finge éxito.
    """
    handler = SYNC_HANDLERS.get(tool)
    if handler:
        try:
            return handler(payload)
        except Exception as e:
            return False, f"handler falló: {e}"
    return False, f"sin handler real para '{tool}' (contrato: sin handler, sin entrega)"

# ─── Hilo Whisper ────────────────────────────────────────────────────────────

class WhisperThread:
    """
    Hilo daemon que procesa la cola con retry exponencial.
    No toca el threadpool de FastAPI — es un thread puro de Python.
    """
    def __init__(self):
        self._running = True
        self._idle_since = time.time()
        self.stats = {"enviados": 0, "fallidos": 0, "deduplicados": 0, "sin_handler": 0}

    def tick(self):
        """Un ciclo del loop de whisper. Devuelve True si procesó algo."""
        msg = obtener_siguiente()
        if not msg:
            return False

        msg_id = msg["id"]

        # Deduplicación — FIX: retirar el mensaje de la cola (antes quedaba
        # pendiente por siempre y el tick lo releía eternamente)
        if es_deduplicado(msg_id):
            self.stats["deduplicados"] += 1
            cola = leer_cola()
            cola = [m for m in cola if m["id"] != msg_id]
            reescribir_cola(cola)
            _actualizar_estado()
            return True

        # Ejecutar sync (solo handlers reales)
        exito, respuesta = sync_tool(msg["tool"], msg["payload"])
        msg["attempts"] += 1

        if exito:
            marcar_entregado(msg_id)
            msg["status"] = "delivered"
            marcar_peer_activo(msg.get("peer", "default"))
            self.stats["enviados"] += 1
        elif respuesta.startswith("sin handler real") or "sin handler real" in respuesta:
            # Contrato: sin handler real NO se reintenta ni se "entrega".
            # Se archiva con su razón para auditar qué faltó.
            msg["status"] = "no_handler"
            msg["razon"] = respuesta
            self.stats["sin_handler"] += 1
        else:
            # Handler real que falló → retry exponencial honesto
            delay = min(RETRY_CONFIG["max_delay"],
                       RETRY_CONFIG["base_delay"] * (2 ** (msg["attempts"] - 1)))
            delay = _jitter(delay)
            msg["status"] = "retrying"
            msg["next_retry"] = (datetime.now() + timedelta(seconds=delay)).isoformat()
            self.stats["fallidos"] += 1

        # Log del ciclo
        with open(RETRY_LOG, "a") as f:
            f.write(json.dumps({
                "id": msg_id, "tool": msg["tool"],
                "attempts": msg["attempts"],
                "status": msg["status"],
                "respuesta": respuesta,
                "ts": datetime.now().isoformat(),
            }, ensure_ascii=False) + "\n")

        # Actualizar cola
        cola = leer_cola()
        for i, m in enumerate(cola):
            if m["id"] == msg_id:
                cola[i] = msg
                break
        reescribir_cola(cola)
        _actualizar_estado()
        return True

    def run(self):
        """Loop principal del hilo whisper."""
        while self._running:
            try:
                proceso = self.tick()
                if not proceso:
                    self._idle_since = time.time()
                    time.sleep(1)  # Idle: esperar 1s antes del siguiente ciclo
                else:
                    time.sleep(0.05)  # Procesó algo: ciclo rápido
            except Exception:
                time.sleep(2)  # Error: esperar más

    def detener(self):
        self._running = False

# Instancia singleton
_whisper: Optional[WhisperThread] = None

def obtener_whisper() -> WhisperThread:
    global _whisper
    if _whisper is None:
        _whisper = WhisperThread()
    return _whisper

def iniciar_whisper():
    w = obtener_whisper()
    t = threading.Thread(target=w.run, daemon=True)
    t.start()
    _actualizar_estado()

# ─── Rutas API ────────────────────────────────────────────────────────────────

@router.on_event("startup")
def startup():
    threading.Thread(target=iniciar_whisper, daemon=True).start()

@router.post("/enviar")
def whisper_enviar(payload: dict, background_tasks: BackgroundTasks):
    """
    Envía un mensaje silencioso. Se encola y se procesa en background.
    El cliente puede seguir sin esperar. NOTA: si el tool no tiene handler
    real, quedará archivado como "no_handler" (no se finge entrega).
    """
    tool = payload.get("tool", "generic")
    data = payload.get("payload", {})
    prioridad = payload.get("prioridad", 1)
    peer = payload.get("peer", "default")

    msg_id = encolar(tool, data, prioridad, peer)
    return {"ok": True, "msg_id": msg_id, "status": "enqueued"}

@router.post("/enviar-ahora")
def whisper_sync(payload: dict):
    """Envío síncrono: intenta inmediatamente, sin cola. Resultado REAL."""
    tool = payload.get("tool", "generic")
    data = payload.get("payload", {})

    exito, msg = sync_tool(tool, data)
    return {"ok": exito, "msg": msg}

@router.get("/cola")
def whisper_cola():
    """Estado de la cola."""
    cola = leer_cola()
    pendientes = [m for m in cola if m["status"] in ("pending", "retrying")]
    return {
        "pendientes": len(pendientes),
        "total": len(cola),
        "mensajes": cola[-20:],  # últimos 20
    }

@router.delete("/cola/{msg_id}")
def whisper_borrar(msg_id: str):
    cola = leer_cola()
    nueva = [m for m in cola if m["id"] != msg_id]
    reescribir_cola(nueva)
    _actualizar_estado()
    return {"ok": True, "borrado": msg_id}

@router.delete("/cola")
def whisper_limpiar():
    reescribir_cola([])
    _actualizar_estado()
    return {"ok": True, "cola_vaciada": True}

@router.get("/peers")
def whisper_peers():
    peers = _cargar_state().get("peers", {})
    for p, info in peers.items():
        info["vivo"] = peer_activo(p)
    return {"peers": peers}

@router.get("/stats")
def whisper_stats():
    w = obtener_whisper()
    return {**w.stats, "cola_pendiente": _cargar_state().get("cola_size", 0)}

@router.get("/retry-log")
def whisper_retry_log(n: int = 30):
    if not RETRY_LOG.exists():
        return {"lineas": []}
    lineas = RETRY_LOG.read_text().strip().splitlines()
    return {"lineas": lineas[-n:]}

@router.post("/forzar-ciclo")
def whisper_forzar():
    """Fuerza un tick inmediato del hilo (para pruebas)."""
    w = obtener_whisper()
    proceso = w.tick()
    return {"ok": True, "proceso_algo": proceso, "stats": w.stats}

@router.get("/handlers")
def whisper_handlers():
    """Transparencia: qué tools tienen handler REAL y cuáles no."""
    return {
        "con_handler_real": sorted(SYNC_HANDLERS.keys()),
        "contrato": "cualquier tool fuera de esta lista se archiva como no_handler (sin fingir entrega)",
    }
