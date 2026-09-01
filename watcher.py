#!/data/data/com.termux/files/usr/bin/python
# -*- coding: utf-8 -*-
"""
WATCHER — Recarga automática de módulos cuando cambian.
Monitorea redteam/modules/ y registra cambios en ledger SourceSeal.
Uso: python3 watcher.py [--dashboard-pid PID]
"""
import os, sys, time, json, hashlib, subprocess, signal
from pathlib import Path
from datetime import datetime

MODULES_DIR = Path(__file__).parent / "redteam" / "modules"
LEDGER = Path.home() / ".c2" / "evidence_ledger.json"
STATE_FILE = Path.home() / ".c2" / "module_state.json"
LOG = Path.home() / ".c2" / "logs" / "watcher.log"

LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def seal_module_change(module_name: str, new_hash: str, change_type: str):
    """Registra el cambio en el ledger SourceSeal."""
    if not LEDGER.exists():
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        ledger = {"chain_hash": "genesis", "events": []}
    else:
        try:
            ledger = json.loads(LEDGER.read_text())
        except Exception:
            ledger = {"chain_hash": "genesis", "events": []}

    prev = ledger.get("chain_hash", "genesis")
    payload = f"{prev}|module:{module_name}|{change_type}|{new_hash}|{int(time.time())}"
    new_chain = hashlib.sha256(payload.encode()).hexdigest()
    ledger["events"].append({
        "type": "MODULE_CHANGE",
        "module": module_name,
        "change": change_type,
        "sha256": new_hash,
        "chain_hash": new_chain,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    ledger["chain_hash"] = new_chain
    if len(ledger["events"]) > 1000:
        ledger["events"] = ledger["events"][-1000:]
    LEDGER.write_text(json.dumps(ledger, indent=2))
    log(f"🔗 Sellado: {module_name} ({change_type})")


def signal_dashboard(action: str = "reload"):
    """Envía señal al dashboard para que recargue módulos."""
    pid_file = Path.home() / ".c2" / "pids" / "dashboard.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            sig = signal.SIGUSR1 if action == "reload" else signal.SIGTERM
            os.kill(pid, sig)
            log(f"📡 Señal {action} enviada a dashboard (PID {pid})")
        except Exception as e:
            log(f"⚠️ No se pudo señalizar dashboard: {e}")


def scan_modules() -> dict:
    """Escanea todos los .py en modules/."""
    state = {}
    if not MODULES_DIR.exists():
        return state
    for f in MODULES_DIR.glob("*.py"):
        if f.name.startswith("_"):
            continue
        state[f.stem] = {
            "hash": file_hash(f),
            "size": f.stat().st_size,
            "mtime": f.stat().st_mtime
        }
    return state


def main():
    log("=" * 60)
    log("👁️ WATCHER iniciado — monitoreando módulos Red Team")
    log(f"  Directorio: {MODULES_DIR}")
    log(f"  Ledger: {LEDGER}")
    log("=" * 60)

    previous = load_state()
    if not previous:
        previous = scan_modules()
        save_state(previous)
        log(f"📦 Estado inicial: {len(previous)} módulos catalogados")
        for name in previous:
            seal_module_change(name, previous[name]["hash"], "BASELINE")

    try:
        while True:
            current = scan_modules()
            changes = []

            # Módulos nuevos
            for name in current:
                if name not in previous:
                    changes.append(("ADDED", name, current[name]["hash"]))

            # Módulos eliminados
            for name in previous:
                if name not in current:
                    changes.append(("REMOVED", name, ""))

            # Módulos modificados
            for name in current:
                if name in previous and current[name]["hash"] != previous[name]["hash"]:
                    changes.append(("MODIFIED", name, current[name]["hash"]))

            if changes:
                for change_type, name, h in changes:
                    icon = {"ADDED": "➕", "REMOVED": "➖", "MODIFIED": "🔄"}[change_type]
                    log(f"{icon} {change_type}: {name}.py ({h[:12]})")
                    seal_module_change(name, h, change_type)

                save_state(current)
                signal_dashboard("reload")
                previous = current

            time.sleep(2)

    except KeyboardInterrupt:
        log("🛑 Watcher detenido")


if __name__ == "__main__":
    main()
