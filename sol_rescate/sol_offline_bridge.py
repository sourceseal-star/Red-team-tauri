#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOL OFFLINE BRIDGE — Complemento que permite a Sol funcionar sin internet.

NO reemplaza nada. NO modifica sol_core.py, sol_api.py, ni ningún archivo
existente. Es un módulo ADICIONAL que:

1. Detecta si hay internet (ping a Groq API)
2. Si HAY internet: sincroniza memoria local ↔ Replit
3. Si NO hay internet: asegura que Sol siga funcionando con:
   - Memoria local intacta (~/.sol/memory.jsonl)
   - Cerebro local (sol_core.py funciona sin LLM)
   - Secrets cacheados del .env de Replit
4. Cuando vuelve internet: re-sincroniza memoria automáticamente

USO (desde start_replit.sh o sol.sh):
    # Línea única, no rompe nada si el bridge no está:
    python3 sol_offline_bridge.py &

O desde Python:
    from sol_offline_bridge import OfflineBridge
    bridge = OfflineBridge()
    bridge.start()  # loop en background
"""

import os
import sys
import json
import time
import socket
import urllib.request
from pathlib import Path
from datetime import datetime

# ── Paths ──
SOL_DIR = Path.home() / ".sol"
MEMORY_FILE = SOL_DIR / "memory.jsonl"
BRIDGE_LOG = SOL_DIR / "offline_bridge.log"
SYNC_FILE = SOL_DIR / "last_sync.json"

# ── Configuración (lee del .env que ya existe) ──
GROQ_URL = os.environ.get("LLM_API_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("LLM_API_KEY", "")
REPLIT_URL = os.environ.get("SOL_PUBLIC_URL", "")  # URL pública de Replit
SOL_API_KEY = os.environ.get("SOL_API_KEY", "")

# Internet check: Groq API + fallback a DNS
INTERNET_HOSTS = [
    ("api.groq.com", 443),
    ("8.8.8.8", 53),
]


def log(msg):
    """Log con timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(BRIDGE_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def check_internet(timeout=3):
    """Verifica si hay internet. True si cualquiera de los hosts responde."""
    for host, port in INTERNET_HOSTS:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            sock.close()
            return True
        except (socket.timeout, OSError):
            continue
    return False


def has_llm():
    """True si Sol tiene LLM configurado (Groq/Anthropic)."""
    return bool(GROQ_KEY)


def sync_memory_to_replit():
    """Envía memoria local a Replit para sincronización bidireccional.
    Solo funciona si SOL_PUBLIC_URL está configurada."""
    if not REPLIT_URL or not SOL_API_KEY:
        log("Sync: SOL_PUBLIC_URL o SOL_API_KEY no configuradas — saltando")
        return False

    if not MEMORY_FILE.exists():
        log("Sync: Sin memoria local para enviar")
        return False

    try:
        mem_content = MEMORY_FILE.read_text(encoding="utf-8")
        body = json.dumps({"memory": mem_content}).encode()
        req = urllib.request.Request(
            f"{REPLIT_URL}/api/sol/sync",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-sol-key": SOL_API_KEY,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        # Guardar timestamp de sync
        SYNC_FILE.write_text(json.dumps({
            "last_sync": datetime.now().isoformat(),
            "entries_sent": mem_content.count("\n"),
            "result": result,
        }), encoding="utf-8")
        log(f"Sync: ✅ {mem_content.count(chr(10))} entries enviadas a Replit")
        return True
    except Exception as e:
        log(f"Sync: ⚠️ Sin internet o error: {e}")
        return False


def fetch_memory_from_replit():
    """Trae memoria de Replit y la fusiona con la local."""
    if not REPLIT_URL or not SOL_API_KEY:
        return False

    try:
        req = urllib.request.Request(
            f"{REPLIT_URL}/api/sol/memory",
            headers={
                "x-sol-key": SOL_API_KEY,
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            },
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())

        remote_entries = resp.get("entries", [])
        if not remote_entries:
            log("Fetch: Replit no tiene memoria nueva")
            return True

        # Leer memoria local
        local_entries = []
        if MEMORY_FILE.exists():
            for line in MEMORY_FILE.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        local_entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Fusionar: agregar entries remotas que no existan localmente
        local_hashes = {e.get("sha256", e.get("timestamp", "")) for e in local_entries}
        new_entries = 0
        for entry in remote_entries:
            entry_hash = entry.get("sha256", entry.get("timestamp", ""))
            if entry_hash and entry_hash not in local_hashes:
                with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False)
                    f.write("\n")
                new_entries += 1

        log(f"Fetch: ✅ {new_entries} entries nuevas desde Replit")
        return True
    except Exception as e:
        log(f"Fetch: ⚠️ Error trayendo memoria: {e}")
        return False


class OfflineBridge:
    """Bridge que mantiene a Sol funcionando con o sin internet.

    Uso:
        bridge = OfflineBridge()
        bridge.start()  # loop en background (no bloquea)
        bridge.stop()   # detener
    """

    def __init__(self, sync_interval=300):
        self.sync_interval = sync_interval  # 5 min por defecto
        self.running = False
        self._was_offline = False

    def status(self):
        """Estado del bridge para diagnóstico."""
        online = check_internet()
        return {
            "online": online,
            "llm_available": has_llm() and online,  # LLM necesita internet
            "local_memory": MEMORY_FILE.exists(),
            "memory_entries": self._count_memory(),
            "last_sync": self._last_sync(),
            "replit_url": bool(REPLIT_URL),
            "sol_api_key": bool(SOL_API_KEY),
            "groq_key": bool(GROQ_KEY),
            "bridge_log": str(BRIDGE_LOG),
        }

    def _count_memory(self):
        if not MEMORY_FILE.exists():
            return 0
        try:
            return sum(1 for line in MEMORY_FILE.read_text(encoding="utf-8")
                       if line.strip())
        except Exception:
            return 0

    def _last_sync(self):
        if SYNC_FILE.exists():
            try:
                return json.loads(SYNC_FILE.read_text()).get("last_sync")
            except Exception:
                return None
        return None

    def _loop(self):
        """Loop principal del bridge."""
        log("☀️ Sol Offline Bridge activo")
        log(f"   LLM: {'✅ Groq' if has_llm() else '❌ Solo cerebro local'}")
        log(f"   Replit sync: {'✅' if REPLIT_URL else '❌ SIN_PUBLIC_URL'}")
        log(f"   Memoria local: {self._count_memory()} entries")

        while self.running:
            online = check_internet()

            if online and self._was_offline:
                log("🌐 Internet recuperado — re-sincronizando...")
                fetch_memory_from_replit()
                sync_memory_to_replit()
                self._was_offline = False
            elif online and not self._was_offline:
                # Sync periódico normal
                sync_memory_to_replit()
            elif not online and not self._was_offline:
                log("📵 Sin internet — Sol sigue funcionando con cerebro local")
                log("   Memoria local intacta, LLM no disponible")
                self._was_offline = True

            time.sleep(self.sync_interval)

    def start(self):
        """Inicia el bridge en background (no bloquea)."""
        import threading
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        log("Bridge iniciado en background")
        return t

    def stop(self):
        """Detiene el bridge."""
        self.running = False
        log("Bridge detenido")


# ═══ API endpoint para integrar con sol_api.py sin modificarlo ═══
def get_status_dict():
    """Devuelve el estado del bridge como dict.
    Puede importarse desde sol_api.py o usarse standalone."""
    bridge = OfflineBridge()
    return bridge.status()


# ═══ MODO STANDALONE ═══
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sol Offline Bridge")
    parser.add_argument("--status", action="store_true", help="Solo mostrar estado")
    parser.add_argument("--sync", action="store_true", help="Sincronizar una vez y salir")
    parser.add_argument("--check", action="store_true", help="Verificar internet y salir")
    args = parser.parse_args()

    SOL_DIR.mkdir(exist_ok=True)

    if args.check:
        online = check_internet()
        print(f"Internet: {'✅ SÍ' if online else '❌ NO'}")
        print(f"LLM disponible: {'✅' if has_llm() and online else '❌'}")
        sys.exit(0 if online else 1)

    if args.status:
        status = get_status_dict()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.sync:
        sync_memory_to_replit()
        fetch_memory_from_replit()
        sys.exit(0)

    # Modo continuo
    bridge = OfflineBridge()
    try:
        bridge._loop()
    except KeyboardInterrupt:
        log("Bridge detenido por el usuario")
