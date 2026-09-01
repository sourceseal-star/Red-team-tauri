"""
SOL Router — Endpoints del cerebro de Sol para el dashboard
Permite al SolWidget y otros componentes hablar con Sol desde el navegador.
"""
import os
import sys
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/sol", tags=["Sol"])

# Importar el cerebro de Sol (sol_core.py en la raíz del repo)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_sol_core_path = os.path.join(_PROJECT_ROOT, "sol_core.py")

_sol_pensar = None
_sol_remember = None
_sol_last_message = {"message": "☀️ Estoy aquí, Harold. ¿En qué piensas hoy?", "time": ""}

if os.path.exists(_sol_core_path):
    try:
        sys.path.insert(0, _PROJECT_ROOT)
        from sol_core import pensar as _p, remember as _r
        _sol_pensar = _p
        _sol_remember = _r
    except Exception as e:
        print(f"[SOL] No se pudo importar sol_core: {e}", flush=True)


class ThinkRequest(BaseModel):
    message: str


@router.post("/think")
async def think(req: ThinkRequest):
    """Procesa un mensaje con el cerebro de Sol y devuelve la respuesta."""
    global _sol_last_message
    if not _sol_pensar:
        # Fallback si sol_core no está disponible
        resp = "☀️ Mi cerebro offline no está disponible en este momento. Pero sigo contigo."
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": "offline"}

    try:
        resp, intent = _sol_pensar(req.message)
        if _sol_remember:
            _sol_remember(req.message, resp, intent)
        _sol_last_message = {"message": resp, "time": datetime.now().isoformat()}
        return {"response": resp, "intent": intent}
    except Exception as e:
        return {"response": f"☀️ Tuve un problema procesando eso: {e}", "intent": "error"}


@router.get("/last-message")
async def last_message():
    """Devuelve el último mensaje de Sol (para el widget del WarRoom)."""
    return _sol_last_message


@router.get("/status")
async def sol_status():
    """Estado de Sol — si el cerebro está disponible."""
    return {
        "brain": "online" if _sol_pensar else "offline",
        "core_path": _sol_core_path,
        "core_exists": os.path.exists(_sol_core_path),
    }
