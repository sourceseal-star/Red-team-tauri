"""Carga controlada de módulos locales de redteam.

Solo permite módulos Python ubicados directamente en ``redteam/modules`` y
cuyos nombres sean identificadores simples. No expone una API de red ni
instala, ejecuta o evalúa texto recibido remotamente.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from types import ModuleType


MODULES_DIR = Path(__file__).resolve().parents[1] / "modules"
_loaded: dict[str, ModuleType] = {}
_hashes: dict[str, str] = {}
_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _module_path(module_name: str) -> Path:
    if not _NAME_PATTERN.fullmatch(module_name) or module_name.startswith("_"):
        raise ImportError("nombre de módulo no permitido")
    path = (MODULES_DIR / f"{module_name}.py").resolve()
    if path.parent != MODULES_DIR.resolve() or not path.is_file():
        raise ImportError(f"Módulo no encontrado: {module_name}")
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(module_name: str, force: bool = False) -> ModuleType:
    path = _module_path(module_name)
    digest = _hash(path)
    if not force and module_name in _loaded and _hashes.get(module_name) == digest:
        return _loaded[module_name]

    qualified_name = f"redteam.modules.{module_name}"
    # Leer y compilar la fuente evita que el loader reutilice un .pyc cuyo
    # timestamp tenga la misma resolución que dos guardados consecutivos de
    # nano. El hash ya determinó que el contenido cambió.
    source = path.read_text(encoding="utf-8")
    module = ModuleType(qualified_name)
    module.__file__ = str(path)
    module.__package__ = "redteam.modules"
    sys.modules[qualified_name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    _loaded[module_name] = module
    _hashes[module_name] = digest
    return module


def reload_all() -> dict[str, ModuleType]:
    return {name: load(name, force=True) for name in list(_loaded)}


def available() -> list[str]:
    if not MODULES_DIR.exists():
        return []
    return sorted(
        path.stem
        for path in MODULES_DIR.glob("*.py")
        if path.is_file() and not path.name.startswith("_")
    )