#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOL RELAY QUEUE — La cola de tareas Replit ⇄ Termux.

Arquitectura (decisión 2026-09-03, tras el fix del split-brain eb908b9):

    ┌─────────────────┐   orden (enqueue)    ┌──────────────────┐
    │  Sol en Replit  │ ───────────────────► │  COLA (módulo)    │
    │  (cerebro web)  │                      │  sol_relay_queue  │
    └─────────────────┘                      └────────┬─────────┘
             ▲                                        │ poll (HTTP)
             │              resultado (HTTP)          ▼
             │ ───────────────────────────── ┌──────────────────┐
             │                               │ sol_relay.py      │
             └── /api/relay/result ◄──────── │ en TERMUX (Edge) │
                                             └──────────────────┘

- Replit NO puede iniciar conexiones hacia Termux (el teléfono no tiene IP
  pública). Por eso el patrón es PULL: el agente en Termux sondea la cola
  en Replit cada N segundos, ejecuta la tarea con el hardware REAL
  (termux-api) y devuelve el resultado. Es el mismo patrón del
  sol_offline_bridge.py (memoria), aplicado a acciones.

- Este módulo vive DENTRO del proceso de sol_api.py en Replit (misma
  memoria) — sol_tools.execute_tool() hace enqueue aquí directamente
  cuando detecta que no hay hardware local. En Termux este módulo existe
  pero la cola siempre está vacía: ahí el hardware funciona directo.

- Persistencia: resultados y último pong se guardan en
  ~/.sol_relay_state.json para sobrevivir reinicios de Replit. Las tareas
  pendientes viven solo en memoria (si Replit se reinicia con tareas sin
  responder, se pierden — aceptable: el usuario puede re-pedir).

Seguridad:
- Solo se encolan herramientas REGISTRADAS en sol_tools.TOOLS (nombres
  validados por get_tool). Nunca shell arbitrario.
- El agente en Termux solo acepta tareas cuyo `tool` exista localmente.
- Escrituras protegidas por lock (threading.Lock).
"""

import json
import os
import time
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Persistencia ──
STATE_FILE = Path(os.environ.get("SOL_RELAY_STATE", str(Path.home() / ".sol_relay_state.json")))
MAX_RESULTS_KEPT = 50       # resultados en memoria/persistencia
MAX_PENDING = 20            # anti-flood: no encolar más de esto
TASK_TTL = 900              # tarea sin reclamar 15 min → expirada

_lock = threading.Lock()

# ── Estado en memoria ──
_pending = []    # [{id, tool, args, kwargs, enqueued_at, claimed_at, origin}]
_results = []     # [{id, tool, ok, data, enqueued_at, finished_at, device}]
_last_pong = None  # timestamp del último poll exitoso desde Termux
_device = None     # info que Termux reporta en cada pong

# Restaurar resultados de ejecuciones anteriores (si el estado existe)
try:
    if STATE_FILE.exists():
        _saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        _results = _saved.get("results", [])[:MAX_RESULTS_KEPT]
        _last_pong = _saved.get("last_pong")
        _device = _saved.get("device")
except Exception:
    pass  # estado corrupto/ausente → arrancamos limpios


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _save_state():
    """Persiste resultados + pong (nunca lanza — la cola no puede tumbar nada)."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({
            "results": _results[-MAX_RESULTS_KEPT:],
            "last_pong": _last_pong,
            "device": _device,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def enqueue(tool, args=None, kwargs=None, origin="sol"):
    """Agrega una tarea a la cola. Devuelve dict con task_id."""
    with _lock:
        # Expurar tareas viejas no reclamadas
        cutoff = time.time() - TASK_TTL
        _pending[:] = [t for t in _pending
                       if t.get("claimed_at")
                       or t.get("enqueued_ts", 0) > cutoff]
        if len(_pending) >= MAX_PENDING:
            return {"success": False, "error": "cola llena — espera resultados pendientes"}
        task = {
            "id": uuid.uuid4().hex[:12],
            "tool": tool,
            "args": list(args or []),
            "kwargs": dict(kwargs or {}),
            "origin": origin,
            "enqueued_at": _now_iso(),
            "enqueued_ts": time.time(),
            "claimed_at": None,
        }
        _pending.append(task)
        return {"success": True, "task_id": task["id"], "queued": len(_pending)}


def fetch_batch(max_tasks=5, claim=True, device=None):
    """Devuelve (y reclama) tareas pendientes. Actualiza el pong."""
    global _last_pong, _device
    with _lock:
        _last_pong = _now_iso()
        if device:
            _device = device
        _save_state()
        batch = [t for t in _pending if not t.get("claimed_at")][:max_tasks]
        if claim:
            for t in batch:
                t["claimed_at"] = _now_iso()
        return batch


def push_result(task_id, ok, data, device=None):
    """Registra el resultado de una tarea ejecutada en Termux."""
    with _lock:
        task = next((t for t in _pending if t["id"] == task_id), None)
        entry = {
            "id": task_id,
            "tool": task["tool"] if task else "?",
            "ok": bool(ok),
            "data": data,
            "origin": task["origin"] if task else "?",
            "enqueued_at": task["enqueued_at"] if task else None,
            "finished_at": _now_iso(),
            "device": device or _device or {},
        }
        _results.append(entry)
        del _results[:-MAX_RESULTS_KEPT]
        # limpiar la tarea de pending
        _pending[:] = [t for t in _pending if t["id"] != task_id]
        _save_state()
        return entry


def results(since_index=0, limit=10):
    """Últimos resultados (los más recientes al final)."""
    with _lock:
        return list(_results[max(0, since_index):])[-limit:]


def status(pong_timeout=90):
    """Estado del relé. `termux_online` = pong dentro de los últimos 90s."""
    with _lock:
        fresh = False
        if _last_pong:
            try:
                then = datetime.fromisoformat(_last_pong)
                fresh = (datetime.now(timezone.utc) - then).total_seconds() <= pong_timeout
            except Exception:
                fresh = False
        return {
            "termux_online": fresh,
            "last_pong": _last_pong,
            "device": _device,
            "pending": sum(1 for t in _pending if not t.get("claimed_at")),
            "claimed": sum(1 for t in _pending if t.get("claimed_at")),
            "results_total": len(_results),
            "last_result": _results[-1] if _results else None,
        }


# ═══ MODO STANDALONE (diagnóstico rápido) ═══
if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2))
