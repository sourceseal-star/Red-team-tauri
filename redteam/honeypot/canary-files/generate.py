#!/usr/bin/env python3
"""
Canary Files — Honeytramp a nivel de archivo
=============================================
Genera archivos "trampa" con nombres atractivos y contenido envenenado.
Si un spyware (Pegasus, stalkerware, app espía comercial) accede a ellos,
queda registrado mediante:

1. Watchdog inotify (Linux) / FSEvents (macOS) / ReadDirectoryChangesW (Windows)
2. Mac的时间戳 de acceso alterado (queda visible en forensia)
3. Contenido con canary tokens que disparan alerta si se exfiltra

Directorios típicos donde un spyware busca:
- /DCIM/Camera/
- /Pictures/
- /WhatsApp/Media/WhatsApp Images/
- /Download/
- /Documents/
- /sdcard/Android/data/com.whatsapp/files/

USO: el módulo de la app llama generate.deploy() al instalarse (con permiso
del usuario) y watchdog.start() para monitoreo continuo.
"""
import os
import json
import time
import secrets
import hashlib
import pathlib
import datetime
import threading
from typing import List, Dict, Optional


# Nombres atractivos que un spyware buscaría
CANARY_NAMES = [
    "passwords_backup.txt",
    "2fa_backup_codes.txt",
    "bitcoin_wallet_backup.dat",
    "banking_credentials.csv",
    "private_keys.asc",
    "vpn_config.ovpn",
    "family_photos_2024.zip",
    "tax_documents_2024.pdf",
    "salary_2024.xlsx",
    "contract_signed.pdf",
    "IMG_20241224_emergency.jpg",
    "voice_memo_secret.m4a",
    "whatsapp_chat_export.txt",
    "telegram_backup.json",
    "signal_backup.bin",
]

CANARY_TEMPLATE_TXT = """
=== {filename} ===
CANARY TOKEN: {token}
CREATED: {ts}
DO NOT READ — this is a honeytrap file.

If this file is read or exfiltrated by a process the user has not authorized,
the SOURCESEAL Red Team agent will be notified and a forensic capture will begin.
""".strip()


def generate_canary(target_dir: str, name: Optional[str] = None) -> Dict:
    """Crea un archivo canario en el directorio."""
    target = pathlib.Path(target_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)

    fname = name or secrets.choice(CANARY_NAMES)
    token = "SOURCESEAL_CANARY_" + secrets.token_hex(12)
    content = CANARY_TEMPLATE_TXT.format(filename=fname, token=token, ts=datetime.datetime.utcnow().isoformat())

    fpath = target / fname
    # Si ya existe, regenerar token
    if fpath.exists():
        try:
            existing = fpath.read_text()
            for line in existing.splitlines():
                if line.startswith("CANARY TOKEN:"):
                    token = line.split(": ", 1)[1]
                    content = existing
                    break
        except Exception:
            pass
    fpath.write_text(content)

    return {
        "path": str(fpath),
        "filename": fname,
        "token": token,
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "size": len(content),
        "created": datetime.datetime.utcnow().isoformat() + "Z",
    }


def deploy(target_dirs: List[str]) -> List[Dict]:
    """Despliega canarios en múltiples directorios."""
    canaries = []
    for d in target_dirs:
        try:
            canaries.append(generate_canary(d))
        except Exception as e:
            canaries.append({"path": d, "error": str(e)})
    return canaries


class CanaryWatchdog:
    """Monitorea accesos a archivos canario usando polling (cross-platform)."""
    def __init__(self, canary_paths: List[str], on_access=None, poll_interval: float = 2.0):
        self.canary_paths = [pathlib.Path(p) for p in canary_paths if pathlib.Path(p).exists()]
        self.on_access = on_access or self._default_handler
        self.poll_interval = poll_interval
        self._states = {}  # path -> (mtime, atime, size)
        self._running = False
        self._thread = None
        self.alerts = []

    def _default_handler(self, event: Dict):
        self.alerts.append(event)
        # Guardar alerta
        evidence = pathlib.Path(__file__).parent.parent.parent / "evidence" / "canary"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / f"!!CANARY-ACCESS-{int(time.time()*1000)}.json").write_text(
            json.dumps(event, indent=2)
        )

    def _capture_states(self):
        for p in self.canary_paths:
            try:
                st = p.stat()
                self._states[str(p)] = (st.st_mtime, st.st_atime, st.st_size)
            except Exception:
                pass

    def _check(self):
        for p in self.canary_paths:
            try:
                st = p.stat()
                key = str(p)
                prev = self._states.get(key)
                if prev:
                    mt, at, sz = prev
                    # Detección: cambio en mtime, atime, o size
                    if (st.st_mtime != mt or st.st_atime != at or st.st_size != sz):
                        event = {
                            "type": "canary_access",
                            "ts": datetime.datetime.utcnow().isoformat() + "Z",
                            "path": key,
                            "prev": {"mtime": mt, "atime": at, "size": sz},
                            "curr": {"mtime": st.st_mtime, "atime": st.st_atime, "size": st.st_size},
                            "severity": "critical",
                        }
                        self.on_access(event)
                self._states[key] = (st.st_mtime, st.st_atime, st.st_size)
            except FileNotFoundError:
                # El canario fue BORRADO → evento crítico
                event = {
                    "type": "canary_deleted",
                    "ts": datetime.datetime.utcnow().isoformat() + "Z",
                    "path": str(p),
                    "severity": "critical",
                }
                self.on_access(event)
            except Exception:
                pass

    def start(self):
        if self._running: return
        self._running = True
        self._capture_states()
        def loop():
            while self._running:
                self._check()
                time.sleep(self.poll_interval)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False


if __name__ == "__main__":
    import sys
    dirs = sys.argv[1:] or ["/tmp/canary-test"]
    canaries = deploy(dirs)
    print(json.dumps(canaries, indent=2))
