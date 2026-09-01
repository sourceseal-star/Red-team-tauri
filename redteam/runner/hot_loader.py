# -*- coding: utf-8 -*-
"""
HOT LOADER — Carga y recarga módulos de redteam/modules/ bajo demanda.
Permite al dashboard usar versiones actualizadas sin reiniciar.
"""
import importlib, importlib.util, sys, signal
from pathlib import Path
from typing import Optional, Dict, Any

MODULES_DIR = Path(__file__).parent.parent / "modules"
_loaded: Dict[str, Any] = {}
_mtimes: Dict[str, float] = {}


def _reload_on_signal(signum, frame):
    """Handler SIGUSR1: recarga todos los módulos."""
    print("[HOT-LOADER] Recargando módulos...")
    reload_all()


# Registrar handler
try:
    signal.signal(signal.SIGUSR1, _reload_on_signal)
except AttributeError:
    pass  # Windows no tiene SIGUSR1


def load(module_name: str, force: bool = False):
    """Carga un módulo. Si ya estaba cargado y cambió, lo recarga."""
    path = MODULES_DIR / f"{module_name}.py"
    if not path.exists():
        raise ImportError(f"Módulo no encontrado: {module_name}")

    mtime = path.stat().st_mtime

    if module_name in _loaded and not force:
        if _mtimes.get(module_name) == mtime:
            return _loaded[module_name]

    spec = importlib.util.spec_from_file_location(
        f"redteam.modules.{module_name}", str(path)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _loaded[module_name] = mod
    _mtimes[module_name] = mtime
    print(f"[HOT-LOADER] Cargado: {module_name}.py (mtime={mtime})")
    return mod


def reload_all():
    """Recarga todos los módulos conocidos."""
    for name in list(_loaded.keys()):
        try:
            load(name, force=True)
        except Exception as e:
            print(f"[HOT-LOADER] Error recargando {name}: {e}")


def available() -> list:
    """Lista módulos disponibles."""
    if not MODULES_DIR.exists():
        return []
    return [f.stem for f in MODULES_DIR.glob("*.py")
            if not f.name.startswith("_")]
