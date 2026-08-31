#!/usr/bin/env python3
"""Observa cambios locales del código y los registra en SourceSeal.

El watcher no ejecuta archivos modificados, no recibe comandos de red y no
envía señales a procesos. El endpoint /api/scan ya crea un proceso nuevo por
escaneo, por lo que el siguiente escaneo cargará automáticamente el código
actualizado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from redteam.monitor.operations_monitor import ledger


PROJECT_ROOT = Path(__file__).resolve().parent
WATCH_PATHS = (
    PROJECT_ROOT / "redteam" / "runner",
    PROJECT_ROOT / "redteam" / "modules",
)
DEFAULT_STATE_DIR = Path.home() / ".sourceseal"


def state_path() -> Path:
    """Return the state file location configured for this process."""
    configured_dir = os.environ.get("SOURCESEAL_STATE_DIR")
    return Path(configured_dir).expanduser() / "watcher_state.json" if configured_dir else DEFAULT_STATE_DIR / "watcher_state.json"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_files() -> dict[str, dict[str, int | str]]:
    state: dict[str, dict[str, int | str]] = {}
    for directory in WATCH_PATHS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_") or not path.is_file():
                continue
            relative = str(path.relative_to(PROJECT_ROOT))
            state[relative] = {
                "sha256": file_hash(path),
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
            }
    return state


def load_state() -> dict[str, dict[str, int | str]]:
    path = state_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, dict[str, int | str]]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def detect_changes(previous: dict, current: dict) -> list[tuple[str, str, str]]:
    changes: list[tuple[str, str, str]] = []
    for name, metadata in current.items():
        if name not in previous:
            changes.append(("ADDED", name, str(metadata["sha256"])))
        elif metadata["sha256"] != previous[name].get("sha256"):
            changes.append(("MODIFIED", name, str(metadata["sha256"])))
    for name in previous:
        if name not in current:
            changes.append(("REMOVED", name, ""))
    return changes


def record_changes(changes: list[tuple[str, str, str]]) -> None:
    for change_type, name, digest in changes:
        ledger.append(
            "module_change",
            "termux-watcher",
            {"change": change_type, "module": name, "sha256": digest},
        )
        print(f"[watcher] {change_type}: {name} {digest[:12]}", flush=True)


def run_once(previous: dict | None = None) -> dict:
    previous = load_state() if previous is None else previous
    current = scan_files()
    changes = detect_changes(previous, current)
    if changes:
        record_changes(changes)
    save_state(current)
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="Registra cambios locales de módulos SourceSeal")
    parser.add_argument("--interval", type=float, default=2.0, help="segundos entre comprobaciones")
    parser.add_argument("--once", action="store_true", help="comprobar una vez y salir")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval debe ser mayor que cero")

    previous = load_state()
    if not previous:
        previous = run_once({})
        print(f"[watcher] baseline registrado: {len(previous)} archivos", flush=True)
    if args.once:
        return

    print("[watcher] activo; sin señales ni ejecución de archivos modificados", flush=True)
    try:
        while True:
            time.sleep(args.interval)
            previous = run_once(previous)
    except KeyboardInterrupt:
        print("[watcher] detenido", flush=True)


if __name__ == "__main__":
    main()