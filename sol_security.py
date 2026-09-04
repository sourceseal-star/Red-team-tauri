#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sol_security.py — Controlador de filtros de seguridad de Sol.

Permite activar/desactivar la protección de endpoints sensibles para
entrenar y experimentar con Sol sin restricciones, y volver a activarla
cuando se quiera seguridad completa.

Funciona en dos modos:
  - MODO PROTEGIDO (default): los endpoints sensibles requieren SOL_API_KEY
  - MODO LIBRE (training): todos los endpoints son accesibles sin key

El modo se controla con:
  1. Env var SOL_SECURITY_MODE = "protected" (default) o "free"
  2. Archivo ~/.sol/security_mode.json — {"mode": "protected"|"free"}
  3. API: POST /api/sol/security/toggle (siempre requiere SOL_API_KEY)

NUNCA se puede desactivar la protección del propio endpoint de toggle —
eso sería un agujero de seguridad.
"""

import os
import json
from pathlib import Path

SOL_DIR = Path.home() / ".sol"
SOL_DIR.mkdir(exist_ok=True)
MODE_FILE = SOL_DIR / "security_mode.json"


def get_mode() -> str:
    """Devuelve el modo actual: 'protected' o 'free'."""
    env_mode = os.environ.get("SOL_SECURITY_MODE", "").lower()
    if env_mode in ("protected", "free"):
        return env_mode
    try:
        if MODE_FILE.exists():
            data = json.loads(MODE_FILE.read_text())
            return data.get("mode", "protected").lower()
    except Exception:
        pass
    return "protected"


def set_mode(mode: str) -> str:
    """Cambia el modo. Solo acepta 'protected' o 'free'."""
    mode = mode.lower().strip()
    if mode not in ("protected", "free"):
        return get_mode()
    MODE_FILE.write_text(json.dumps({"mode": mode}, ensure_ascii=False))
    return mode


def is_protected() -> bool:
    """True si los endpoints sensibles requieren SOL_API_KEY."""
    return get_mode() == "protected"


def is_free() -> bool:
    """True si estamos en modo libre (training/experimentacion)."""
    return get_mode() == "free"


def get_sol_key() -> str:
    """Devuelve la SOL_API_KEY configurada, o string vacio si no hay."""
    return os.environ.get("SOL_API_KEY", "")


def check_access(x_sol_key: str = "") -> bool:
    """Verifica si una peticion tiene acceso a endpoints sensibles.
    En modo libre, siempre True.
    En modo protegido, requiere que x_sol_key coincida con SOL_API_KEY."""
    if is_free():
        return True
    key = get_sol_key()
    if not key:
        return True
    return x_sol_key == key


def status() -> dict:
    """Estado completo del controlador de seguridad."""
    return {
        "mode": get_mode(),
        "protected": is_protected(),
        "free": is_free(),
        "has_key": bool(get_sol_key()),
        "key_configured": bool(get_sol_key()),
    }
