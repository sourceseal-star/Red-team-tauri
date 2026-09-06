#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOL RELAY — El brazo de Sol en el Edge 50.

Corre en Termux (arrancado por omni.sh). Sol vive en Replit; cuando Harold
le pide algo de hardware (linterna, SMS, foto, ubicación...), ella no tiene
teléfono en su contenedor — encola la tarea y ESTE agente la ejecuta con el
hardware REAL y le devuelve el resultado.

Patrón PULL (el teléfono no tiene IP pública):
    cada 15s → POST {SOL_PUBLIC_URL}/api/relay/poll  (x-sol-key)
    └─ si hay tareas → ejecutar con sol_tools (termux-api real)
                      → POST /api/relay/result

Ejecuta SOLO herramientas registradas en sol_tools.TOOLS — nunca shell
arbitrario. Y con SOL_RELAY_AGENT=1 el fallback de relé queda desactivado
dentro del propio agente (nunca delega lo que él mismo debe ejecutar).

USO (Termux):
    python3 sol_relay.py            # daemon (loop infinito)
    python3 sol_relay.py --status   # un ping: ¿Replit me ve? ¿y yo a él?
    python3 sol_relay.py --once     # un ciclo de poll y salir (prueba)

Secretos (ya existentes en ~/sol/.env, los mismos del offline bridge):
    SOL_PUBLIC_URL  → https://<tu-repl>.repl.co   (URL pública de Replit)
    SOL_API_KEY     → la misma key que usa el dashboard
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# El agente NUNCA delega hacia el relé (él ES el relé)
os.environ["SOL_RELAY_AGENT"] = "1"

SOL_DIR = Path.home() / ".sol"
LOG_DIR = SOL_DIR / "logs"
LOG_FILE = LOG_DIR / "relay.log"
ENV_FILE = Path(__file__).parent / ".env"

POLL_INTERVAL = int(os.environ.get("SOL_RELAY_INTERVAL", "15"))  # segundos


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_env():
    """Carga ~/sol/.env si las variables no vienen del entorno."""
    if not ENV_FILE.exists():
        return
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception as e:
        log(f"⚠️ No pude leer {ENV_FILE}: {e}")


def device_info():
    """Info del teléfono para que Sol sepa quién respondió."""
    info = {"host": "Edge 50 (Termux)"}
    try:
        model = subprocess.run(["getprop", "ro.product.model"],
                               capture_output=True, text=True, timeout=5)
        if model.returncode == 0 and model.stdout.strip():
            info["device"] = model.stdout.strip()
    except Exception:
        pass
    try:
        android = subprocess.run(["getprop", "ro.build.version.release"],
                                 capture_output=True, text=True, timeout=5)
        if android.returncode == 0 and android.stdout.strip():
            info["android"] = android.stdout.strip()
    except Exception:
        pass
    return info


def _request(url, payload=None, headers=None, timeout=20):
    """POST/GET JSON con urllib (sin dependencias)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers=dict({"Content-Type": "application/json",
                      "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
                     **(headers or {})),
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def poll(base_url, api_key, device):
    """Un ciclo: pedir tareas, ejecutarlas, devolver resultados."""
    headers = {"x-sol-key": api_key}
    r = _request(f"{base_url}/api/relay/poll", payload={"device": device}, headers=headers)
    tasks = r.get("tasks", [])
    for task in tasks:
        tid = task.get("id")
        name = task.get("tool")
        args = task.get("args", [])
        kwargs = task.get("kwargs", {})
        log(f"📨 Tarea {tid}: {name} args={args}")
        try:
            import sol_tools
            if not sol_tools.get_tool(name):
                result = {"success": False, "error": f"tool no registrada: {name}"}
            else:
                result = sol_tools.execute_tool(name, *args, **kwargs)
        except Exception as e:
            result = {"success": False, "error": f"excepción ejecutando {name}: {e}"}
        ok = bool(result.get("success"))
        log(f"{'✅' if ok else '❌'} {tid} {name}: {str(result)[:200]}")
        try:
            _request(f"{base_url}/api/relay/result",
                     payload={"task_id": tid, "ok": ok, "data": result,
                              "device": device},
                     headers=headers)
        except Exception as e:
            log(f"⚠️ No pude devolver el resultado de {tid}: {e}")
    return len(tasks)


def loop():
    load_env()
    base_url = os.environ.get("SOL_PUBLIC_URL", "").rstrip("/")
    api_key = os.environ.get("SOL_API_KEY", "")
    if not base_url or not api_key:
        log("❌ Faltan SOL_PUBLIC_URL o SOL_API_KEY (~/sol/.env) — no puedo arrancar")
        sys.exit(1)

    device = device_info()
    log(f"☀️ Sol Relay activo — teléfono {device}")
    log(f"   Cerebro en: {base_url}")
    log(f"   Sondeo cada {POLL_INTERVAL}s (patrón PULL)")

    fail_streak = 0
    while True:
        try:
            n = poll(base_url, api_key, device)
            fail_streak = 0
            if n:
                log(f"📬 Ciclo completo: {n} tarea(s) ejecutadas")
        except KeyboardInterrupt:
            log("Relay detenido por el usuario")
            break
        except Exception as e:
            fail_streak += 1
            wait = min(POLL_INTERVAL * (1 + fail_streak), 120)
            log(f"⚠️ Sin contacto con Replit ({fail_streak} seguidos): {e}")
            log(f"   Reintentando en {wait}s...")
            time.sleep(wait)
            continue
        time.sleep(POLL_INTERVAL)


def status():
    """Ping manual: ¿Replit está al alcance?"""
    load_env()
    base_url = os.environ.get("SOL_PUBLIC_URL", "").rstrip("/")
    api_key = os.environ.get("SOL_API_KEY", "")
    if not base_url or not api_key:
        print("❌ Faltan SOL_PUBLIC_URL o SOL_API_KEY en ~/sol/.env")
        sys.exit(1)
    print(f"Ping a {base_url} ...")
    try:
        _request(f"{base_url}/api/relay/poll", payload={"device": device_info()},
                 headers={"x-sol-key": api_key})
        print("✅ Replit respondió — relé operativo")
        try:
            s = _request(f"{base_url}/api/relay/status")
            print(f"   Cola pendiente: {s.get('pending')} · resultados: {s.get('results_total')}")
        except Exception:
            pass
        sys.exit(0)
    except Exception as e:
        print(f"❌ Sin respuesta de Replit: {e}")
        sys.exit(1)


def once():
    """Un solo ciclo de poll (prueba end-to-end)."""
    load_env()
    base_url = os.environ.get("SOL_PUBLIC_URL", "").rstrip("/")
    api_key = os.environ.get("SOL_API_KEY", "")
    n = poll(base_url, api_key, device_info())
    print(f"✅ Un ciclo ejecutado: {n} tarea(s)")


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    elif "--once" in sys.argv:
        once()
    else:
        loop()
