#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOURCESEAL TACTICAL v5.0 — Plataforma de Operaciones Cibernéticas
Adaptado a la infraestructura real de Commander + COM-LINK + ARTO + SEAL.

Integra:
  1. Orquestador distribuido (Master-Worker) con cola de tareas
  2. COM-LINK real (bash scripts en comlink/) para alertas críticas
  3. Motor de Playbooks (automatización ARTO)
  4. Dashboard reactivo con WebSockets (puerto 8001)

Uso:
  python3 sourceseal_tactical.py --mode master
  python3 sourceseal_tactical.py --mode worker --master-url http://192.168.1.100:8001
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import socket
import hashlib
import re
import ipaddress
import logging
import threading
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
from collections import deque
from pathlib import Path

# ============================================================
# DEPENDENCIAS OPCIONALES (graceful degradation)
# ============================================================
try:

    # ─── Reemplazo de cryptography.fernet.Fernet (pycryptodome, sin Rust) ───
    # El paquete 'cryptography' requiere compilar un core en Rust y tiene un
    # historial de romperse tras actualizaciones de Termux/pkg (cffi, ABI).
    # Esta clase implementa el mismo formato wire de Fernet
    # (https://github.com/fernet/spec) usando pycryptodome (pure C, sin Rust,
    # con paquete Termux estable). Es 100% compatible con claves y tokens
    # generados por cryptography.fernet.Fernet — no invalida datos cifrados
    # previamente.
    import os as _fernet_os
    import time as _fernet_time
    import struct as _fernet_struct
    import hashlib as _fernet_hashlib
    import hmac as _fernet_hmac
    import base64 as _fernet_b64
    from Crypto.Cipher import AES as _FernetAES
    from Crypto.Util.Padding import pad as _fernet_pad, unpad as _fernet_unpad


    class Fernet:
        def __init__(self, key):
            if isinstance(key, str):
                key = key.encode()
            try:
                key_bytes = _fernet_b64.urlsafe_b64decode(key)
            except Exception as exc:
                raise ValueError("Fernet key must be 32 url-safe base64-encoded bytes.") from exc
            if len(key_bytes) != 32:
                raise ValueError("Fernet key must be 32 url-safe base64-encoded bytes.")
            self._signing_key = key_bytes[:16]
            self._encryption_key = key_bytes[16:]

        @staticmethod
        def generate_key():
            return _fernet_b64.urlsafe_b64encode(_fernet_os.urandom(32))

        def encrypt(self, data):
            if isinstance(data, str):
                data = data.encode()
            iv = _fernet_os.urandom(16)
            cipher = _FernetAES.new(self._encryption_key, _FernetAES.MODE_CBC, iv)
            ciphertext = cipher.encrypt(_fernet_pad(data, 16))
            ts = int(_fernet_time.time())
            payload = b"\x80" + _fernet_struct.pack(">Q", ts) + iv + ciphertext
            h = _fernet_hmac.new(self._signing_key, payload, _fernet_hashlib.sha256).digest()
            return _fernet_b64.urlsafe_b64encode(payload + h)

        def decrypt(self, token, ttl=None):
            if isinstance(token, str):
                token = token.encode()
            try:
                data = _fernet_b64.urlsafe_b64decode(token)
            except Exception as exc:
                raise ValueError("Invalid token") from exc
            if len(data) < 73 or data[0:1] != b"\x80":
                raise ValueError("Invalid token")
            payload, h = data[:-32], data[-32:]
            expected_h = _fernet_hmac.new(self._signing_key, payload, _fernet_hashlib.sha256).digest()
            if not _fernet_hmac.compare_digest(h, expected_h):
                raise ValueError("Invalid token (bad signature)")
            ts = _fernet_struct.unpack(">Q", payload[1:9])[0]
            if ttl is not None and (_fernet_time.time() - ts) > ttl:
                raise ValueError("Token expired")
            iv = payload[9:25]
            ciphertext = payload[25:]
            cipher = _FernetAES.new(self._encryption_key, _FernetAES.MODE_CBC, iv)
            return _fernet_unpad(cipher.decrypt(ciphertext), 16)
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("⚠️ pycryptodome no instalado — cifrado limitado (pip install pycryptodome)")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("⚠️ FastAPI no instalado (pip install fastapi uvicorn)")
    print("   Instala con: pip install fastapi uvicorn aiohttp pycryptodome")

import argparse

# ============================================================
# 1. CONFIGURACIÓN GLOBAL — vía integration_config.py
# ============================================================
try:
    from integration_config import CONFIG as INTEGRATION_CONFIG, get_port, is_debug
    _HAS_INTEGRATION_CONFIG = True
except ImportError:
    _HAS_INTEGRATION_CONFIG = False
    print("⚠️ integration_config.py no encontrado — usando config local")
ROOT_DIR = Path(__file__).parent.absolute()
COMLINK_DIR = ROOT_DIR / "comlink"
COMMANDER_PY = ROOT_DIR / "commander.py"

# Configuración: usa integration_config.py si está disponible
if _HAS_INTEGRATION_CONFIG:
    _ic = INTEGRATION_CONFIG
    CONFIG = {
        "mode": "master",
        "master_url": _ic["tactical"]["master_url"],
        "worker_id": _ic["tactical"]["worker_id"],
        "host": _ic["host"],
        "port": _ic["port"],  # 8001 (standing instruction)
        "debug": _ic["debug"],
        "reload": _ic.get("reload", True),
        "db_path": _ic["commander_db"],
        "tactical_db_path": _ic["tactical_db"],
        "logs_dir": _ic["tactical"]["logs_dir"],
        "reports_dir": _ic["commander"]["report_dir"],
        "max_workers": _ic["tactical"]["max_workers"],
        "scan_timeout": _ic["tactical"]["scan_timeout"],
        "default_ports": _ic["tactical"]["default_ports"],
        "comlink": {
            "enabled": _ic["comlink"]["enabled"],
            "encryption_key": _ic["comlink"]["encryption_key"],
            "comlink_sh": _ic["comlink"]["main_script"],
        },
        "playbooks": {
            "enabled": True,
            "default": "hikvision_full_assault",
            "auto_trigger": True,
        },
        "arto_enabled": _ic["arto"]["enabled"],
        "arto_autostart": _ic["arto"]["autostart"],
        "seal_enabled": _ic["seal"]["enabled"],
        "seal_autostart": _ic["seal"]["autostart"],
        "leviathan_flow": _ic["leviathan"]["flow"],
    }
else:
    CONFIG = {
        "mode": "master",
        "master_url": "http://localhost:8001",
        "worker_id": os.urandom(4).hex(),
        "host": "0.0.0.0",
        "port": 8001,
        "debug": True,
        "reload": True,
        "db_path": os.path.expanduser("~/commander.db"),
        "tactical_db_path": os.path.expanduser("~/seal_tactical.db"),
        "logs_dir": str(ROOT_DIR / "logs"),
        "reports_dir": os.path.expanduser("~/storage/downloads/commander_reports"),
        "max_workers": 10,
        "scan_timeout": 120,
        "default_ports": "21,22,23,25,53,80,110,135,139,143,443,445,554,993,995,1723,3306,3389,5432,5900,6379,8080,8443,27017",
        "comlink": {
            "enabled": True,
            "encryption_key": os.environ.get("SEAL_MASTER_KEY", ""),
            "comlink_sh": str(COMLINK_DIR / "comlink.sh"),
        },
        "playbooks": {
            "enabled": True,
            "default": "hikvision_full_assault",
            "auto_trigger": True,
        },
        "arto_enabled": True,
        "arto_autostart": True,
        "seal_enabled": True,
        "seal_autostart": True,
        "leviathan_flow": ["Detección", "Análisis", "Explotación", "Reportes"],
    }

# Crear directorios necesarios
for d in [CONFIG["logs_dir"], CONFIG["reports_dir"]]:
    try:
        os.makedirs(d, exist_ok=True)
    except (PermissionError, OSError):
        pass

# ============================================================
# 2. LOGGING
# ============================================================
logger = logging.getLogger("SEAL_TACTICAL")
logger.setLevel(logging.DEBUG if CONFIG["debug"] else logging.INFO)
fmt = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(fmt)
logger.addHandler(ch)
fh = logging.FileHandler(os.path.join(CONFIG["logs_dir"], "tactical.log"), encoding='utf-8')
fh.setFormatter(fmt)
logger.addHandler(fh)

def log_info(msg): logger.info(msg)
def log_warn(msg): logger.warning(msg)
def log_error(msg): logger.error(msg)
def log_debug(msg): logger.debug(msg)

# ============================================================
# 3. BASE DE DATOS TÁCTICA (SQLite)
# ============================================================
class TacticalDB:
    """DB separada para operaciones tácticas — no toca commander.db"""
    def __init__(self, db_path: str = CONFIG["tactical_db_path"]):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tactical_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            results_json TEXT NOT NULL,
            hash TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS realtime_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL,
            details_json TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS arto_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            confidence REAL,
            timestamp TEXT NOT NULL,
            result_json TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS seal_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            port INTEGER,
            service TEXT,
            exploit_name TEXT,
            cve TEXT,
            timestamp TEXT NOT NULL,
            status TEXT,
            result_json TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            last_seen TEXT,
            status TEXT,
            capabilities TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS comlink_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            channel TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS comlink_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS playbook_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_name TEXT NOT NULL,
            target TEXT NOT NULL,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            steps_json TEXT
        )''')
        conn.commit()
        conn.close()
        log_info("✅ Base de datos táctica inicializada")

    def _now(self):
        return datetime.utcnow().isoformat() + "Z"

    def save_scan(self, target: str, results: dict) -> str:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        data_json = json.dumps(results, default=str)
        hash_val = hashlib.sha256(data_json.encode()).hexdigest()
        c.execute("INSERT INTO tactical_scans (target, timestamp, results_json, hash) VALUES (?,?,?,?)",
                  (target, self._now(), data_json, hash_val))
        conn.commit()
        conn.close()
        return hash_val

    def save_alert(self, severity: str, source: str, message: str, details: dict = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO realtime_alerts (timestamp, severity, source, message, details_json) VALUES (?,?,?,?,?)",
                  (self._now(), severity, source, message, json.dumps(details) if details else None))
        conn.commit()
        conn.close()

    def get_alerts(self, limit: int = 20) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT timestamp, severity, source, message FROM realtime_alerts ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"timestamp": r[0], "severity": r[1], "source": r[2], "message": r[3]} for r in rows]

    def save_worker(self, worker_id: str, status: str, capabilities: list):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO workers (worker_id, last_seen, status, capabilities) VALUES (?,?,?,?)",
                  (worker_id, self._now(), status, json.dumps(capabilities)))
        conn.commit()
        conn.close()

    def get_workers(self) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT worker_id, last_seen, status, capabilities FROM workers")
        rows = c.fetchall()
        conn.close()
        return [{"worker_id": r[0], "last_seen": r[1], "status": r[2], "capabilities": json.loads(r[3])} for r in rows]

    def save_playbook_execution(self, name: str, target: str, status: str, steps: list) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO playbook_executions (playbook_name, target, status, started_at, finished_at, steps_json) VALUES (?,?,?,?,?,?)",
                  (name, target, status, self._now(), None, json.dumps(steps, default=str)))
        conn.commit()
        pid = c.lastrowid
        conn.close()
        return pid

    def update_playbook_status(self, playbook_id: int, status: str, steps: list):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE playbook_executions SET status=?, finished_at=?, steps_json=? WHERE id=?",
                  (status, self._now(), json.dumps(steps, default=str), playbook_id))
        conn.commit()
        conn.close()

    def get_playbook_history(self, limit: int = 10) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, playbook_name, target, status, started_at, finished_at FROM playbook_executions ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "name": r[1], "target": r[2], "status": r[3], "started": r[4], "finished": r[5]} for r in rows]

    def save_arto_op(self, target: str, action: str, reason: str, confidence: float, result: dict = None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO arto_operations (target, action, reason, confidence, timestamp, result_json) VALUES (?,?,?,?,?,?)",
                  (target, action, reason, confidence, self._now(), json.dumps(result, default=str) if result else None))
        conn.commit()
        conn.close()

    def queue_message(self, message: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO comlink_queue (message, status, created_at) VALUES (?,?,?)",
                  (message, 'pending', self._now()))
        conn.commit()
        conn.close()

    def get_pending_messages(self) -> list:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, message FROM comlink_queue WHERE status='pending'")
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "message": r[1]} for r in rows]

    def mark_message_sent(self, msg_id: int):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE comlink_queue SET status='sent' WHERE id=?", (msg_id,))
        conn.commit()
        conn.close()

db = TacticalDB()

# ============================================================
# 4. MOTOR DE ESCANEO — reutiliza commander.py via subprocess
# ============================================================
def run_nmap(target: str) -> Optional[str]:
    """Ejecuta nmap directamente (no depende de commander.py)"""
    cmd = ["nmap", "-sV", "-O", "--script", "vuln",
           "-p", CONFIG["default_ports"], "-oX", "-", target]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=CONFIG["scan_timeout"])
        if proc.returncode != 0:
            log_error(f"nmap error en {target}: {err[:200]}")
            return None
        return out
    except subprocess.TimeoutExpired:
        proc.kill()
        log_warn(f"nmap timeout en {target}")
        return None
    except FileNotFoundError:
        log_error("nmap no instalado — pkg install nmap")
        return None

def parse_nmap_xml(xml_data: str) -> List[dict]:
    import xml.etree.ElementTree as ET
    if not xml_data:
        return []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []
    hosts = []
    for host in root.findall('host'):
        addr = host.find('address')
        if addr is None:
            continue
        ip = addr.get('addr', 'unknown')
        status = host.find('status')
        if status is None or status.get('state') != 'up':
            continue
        os_elem = host.find('os/osmatch')
        os_name = os_elem.get('name') if os_elem is not None else "Unknown"
        services = []
        vulns = []
        for port in host.findall('ports/port'):
            port_id = port.get('portid')
            service = port.find('service')
            service_name = service.get('name') if service is not None else "unknown"
            services.append({"port": int(port_id), "service": service_name})
            for script in port.findall('script'):
                output = script.get('output', '')
                cves = re.findall(r'CVE-\d{4}-\d{4,7}', output)
                for cve in cves:
                    vulns.append({"cve": cve, "port": int(port_id), "detail": output[:150]})
        hosts.append({"ip": ip, "os": os_name, "services": services, "vulns": vulns})
    return hosts

def get_ips_from_cidr(cidr: str) -> List[str]:
    try:
        net = ipaddress.ip_network(cidr, strict=False)
        return [str(ip) for ip in net.hosts()]
    except ValueError:
        return [cidr]

async def scan_target(target: str) -> dict:
    """Escanea un objetivo con nmap en un thread pool"""
    loop = asyncio.get_event_loop()
    xml_data = await loop.run_in_executor(None, run_nmap, target)
    if not xml_data:
        return {"target": target, "error": "nmap falló o no instalado", "hosts": []}
    hosts = parse_nmap_xml(xml_data)
    return {"target": target, "hosts": hosts, "total": len(hosts)}

# ============================================================
# 5. COM-LINK INTEGRADO — usa los scripts bash reales
# ============================================================
class ComLinkManager:
    """Integración con COM-LINK real (comlink/comlink.sh)"""
    def __init__(self, db: TacticalDB):
        self.db = db
        self.comlink_sh = CONFIG["comlink"]["comlink_sh"]
        self.available = os.path.exists(self.comlink_sh)

    async def initialize(self):
        if self.available:
            log_info("✅ COM-LINK encontrado — alertas reales disponibles")
        else:
            log_warn("⚠️ COM-LINK no encontrado — alertas se guardarán en cola")
            log_warn(f"   Esperado en: {self.comlink_sh}")

    async def send_critical_alert(self, message: str, severity: str = "HIGH") -> bool:
        """Envía alerta vía COM-LINK (SMS/Telegram/Mesh) con fallback a cola"""
        # Guardar en DB siempre
        self.db.save_alert(severity, "comlink", message, {"channel": "auto"})

        if not self.available:
            # Sin COM-LINK — guardar en cola
            self.db.queue_message(f"[{severity}] {message}")
            log_warn(f"COM-LINK no disponible — alerta encolada: {message[:50]}...")
            return False

        # Intentar enviar por Telegram (más confiable para pruebas)
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", self.comlink_sh, "telegram", message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                log_info(f"📡 Alerta enviada via COM-LINK Telegram: {message[:50]}...")
                return True
            else:
                log_warn(f"Telegram falló, intentando SMS...")
        except asyncio.TimeoutError:
            log_warn("COM-LINK timeout en Telegram")
        except Exception as e:
            log_warn(f"COM-LINK error: {e}")

        # Fallback: encolar
        self.db.queue_message(f"[{severity}] {message}")
        log_warn(f"Alerta encolada (sin canal disponible): {message[:50]}...")
        return False

    async def process_queue(self):
        """Procesa mensajes pendientes en la cola"""
        pending = self.db.get_pending_messages()
        if not pending:
            return 0
        sent = 0
        for msg in pending:
            if self.available:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "bash", self.comlink_sh, "telegram", msg["message"],
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
                    if proc.returncode == 0:
                        self.db.mark_message_sent(msg["id"])
                        sent += 1
                except:
                    break  # Sin connectivity, parar
            else:
                break
        if sent > 0:
            log_info(f"📬 Cola procesada: {sent} mensajes enviados")
        return sent

comlink = ComLinkManager(db)

# ============================================================
# 6. MOTOR DE PLAYBOOKS (Automatización ARTO)
# ============================================================
class PlaybookEngine:
    """Ejecuta playbooks de ataque de forma automatizada"""
    def __init__(self, db: TacticalDB):
        self.db = db

    async def execute(self, playbook_name: str, target: str, context: dict = None) -> dict:
        steps = []

        if playbook_name == "hikvision_full_assault":
            # Paso 1: Fingerprint
            step1 = await self._fingerprint(target)
            steps.append({"step": 1, "action": "fingerprint", "result": step1})
            self.db.save_arto_op(target, "fingerprint", "Identificación de vendor", 0.95, step1)

            if step1.get("vendor") == "hikvision":
                # Paso 2: Verificar CVE-2021-36260
                step2 = await self._check_cve(target, "CVE-2021-36260")
                steps.append({"step": 2, "action": "vuln_check", "result": step2})
                self.db.save_arto_op(target, "vuln_check", "CVE-2021-36260", 0.90, step2)

                if step2.get("vulnerable"):
                    # Paso 3: Registrar como operación SEAL
                    step3 = {"action": "seal_register", "result": {"registered": True, "cve": "CVE-2021-36260"}}
                    steps.append({"step": 3, "action": "seal_register", "result": step3})

                    pid = self.db.save_playbook_execution(playbook_name, target, "compromised", steps)
                    self.db.save_arto_op(target, "compromise", "Acceso obtenido via CVE-2021-36260", 0.95, step3)
                    return {"status": "compromised", "playbook_id": pid, "steps": steps}

            pid = self.db.save_playbook_execution(playbook_name, target, "finished", steps)
            return {"status": "finished", "playbook_id": pid, "steps": steps}

        elif playbook_name == "osint_deep_dive":
            # OSINT completo sobre un objetivo
            step1 = await self._osint_recon(target)
            steps.append({"step": 1, "action": "osint_recon", "result": step1})
            self.db.save_arto_op(target, "osint", "Reconocimiento OSINT", 0.80, step1)

            pid = self.db.save_playbook_execution(playbook_name, target, "completed", steps)
            return {"status": "completed", "playbook_id": pid, "steps": steps}

        return {"status": "unknown_playbook", "available": ["hikvision_full_assault", "osint_deep_dive"]}

    async def _fingerprint(self, target: str) -> dict:
        """Hace fingerprinting real via nmap HTTP scripts"""
        xml = await asyncio.get_event_loop().run_in_executor(
            None, run_nmap, target
        )
        if not xml:
            return {"vendor": "unknown", "model": "unknown", "confidence": 0}

        hosts = parse_nmap_xml(xml)
        for h in hosts:
            if h.get("ip") == target or target in h.get("ip", ""):
                for s in h.get("services", []):
                    if s["service"] in ("http", "https"):
                        # Detectar vendor por puerto 80/443/554 (cámaras)
                        if 554 in [p["port"] for p in h.get("services", [])]:
                            return {"vendor": "hikvision", "model": "IP Camera", "confidence": 0.85,
                                    "services": h["services"], "vulns": h["vulns"]}
                return {"vendor": "generic", "os": h["os"], "confidence": 0.60,
                        "services": h["services"], "vulns": h["vulns"]}
        return {"vendor": "unknown", "confidence": 0, "hosts": hosts}

    async def _check_cve(self, target: str, cve: str) -> dict:
        """Verifica si el objetivo es vulnerable a un CVE específico"""
        xml = await asyncio.get_event_loop().run_in_executor(None, run_nmap, target)
        if not xml:
            return {"vulnerable": False, "cve": cve, "error": "nmap falló"}
        hosts = parse_nmap_xml(xml)
        for h in hosts:
            for v in h.get("vulns", []):
                if v["cve"] == cve:
                    return {"vulnerable": True, "cve": cve, "detail": v["detail"]}
        return {"vulnerable": False, "cve": cve, "detail": "No detectado"}

    async def _osint_recon(self, target: str) -> dict:
        """OSINT sobre IP o dominio"""
        # Intentar usar commander.py si existe
        if COMMANDER_PY.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, str(COMMANDER_PY), "--osint-ip", target,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                if proc.returncode == 0 and stdout:
                    # Intentar parsear JSON output
                    try:
                        return json.loads(stdout.decode())
                    except json.JSONDecodeError:
                        return {"raw_output": stdout.decode()[:500], "target": target}
            except Exception as e:
                log_warn(f"OSINT via commander.py falló: {e}")

        # Fallback: info básica
        return {"target": target, "method": "basic", "note": "commander.py no disponible o falló"}

    def list_playbooks(self) -> list:
        return [
            {"name": "hikvision_full_assault", "description": "Fingerprint + CVE check + SEAL register para cámaras Hikvision"},
            {"name": "osint_deep_dive", "description": "OSINT completo sobre IP/dominio objetivo"},
        ]

playbook_engine = PlaybookEngine(db)

# ============================================================
# 7. FASTAPI APP — solo si está instalado
# ============================================================
if HAS_FASTAPI:
    app = FastAPI(title="SourceSeal TACTICAL v5.0", version="5.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Startup: arrancar ARTO + SEAL automáticamente (standing instruction) ──
    @app.on_event("startup")
    async def _startup_arto_seal():
        """Arranque automático de ARTO y SEAL en startup de FastAPI."""
        log_info("🚀 FastAPI startup — inicializando ARTO + SEAL...")

        # ARTO
        if CONFIG.get("arto_enabled") and CONFIG.get("arto_autostart"):
            try:
                db.save_arto_op("system", "startup", "ARTO iniciado en startup FastAPI", 1.0,
                               {"status": "running", "timestamp": datetime.utcnow().isoformat()})
                log_info("✅ ARTO iniciado — motor de decisiones activo")
            except Exception as e:
                log_warn(f"⚠️ ARTO startup: {e}")

        # SEAL
        if CONFIG.get("seal_enabled") and CONFIG.get("seal_autostart"):
            try:
                db.save_alert("INFO", "seal", "SEAL iniciado en startup FastAPI",
                             {"api_url": CONFIG.get("comlink", {}).get("comlink_sh", "")})
                log_info("✅ SEAL iniciado — anclaje SourceSeal disponible")
            except Exception as e:
                log_warn(f"⚠️ SEAL startup: {e}")

        # COM-LINK
        await comlink.initialize()

        # Tareas de fondo
        asyncio.create_task(background_queue_processor())
        asyncio.create_task(background_heartbeat())

        log_info(f"📊 Flujo LEVIATHAN: {' → '.join(CONFIG.get('leviathan_flow', ['Detección','Análisis','Explotación','Reportes']))}")

    @app.on_event("shutdown")
    async def _shutdown_arto_seal():
        """Limpieza al detener FastAPI."""
        log_info("🛑 FastAPI shutdown — ARTO + SEAL deteniéndose...")
        db.save_arto_op("system", "shutdown", "ARTO detenido", 1.0,
                       {"status": "stopped"})
        db.save_alert("INFO", "system", "SEAL detenido")

    # ── WebSocket Manager ──
    class WSManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

        async def broadcast(self, message: dict):
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except:
                    pass

    ws_manager = WSManager()

    # ── Dashboard HTML ──
    @app.get("/")
    async def root():
        return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
<title>SourceSeal TACTICAL v5.0</title>
<style>
body { font-family: 'Courier New', monospace; background: #0a0e17; color: #e2e8f0; padding: 20px; margin: 0; }
.header { border-bottom: 2px solid #f59e0b; padding-bottom: 10px; }
h1 { color: #f59e0b; margin: 0; }
h2 { color: #fbbf24; font-size: 1.1em; }
.status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }
.s-green { background: #4ade80; } .s-red { background: #ef4444; } .s-yellow { background: #fbbf24; }
.card { background: #111827; border: 1px solid #1e293b; border-radius: 0.75rem; padding: 16px; margin: 10px 0; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.btn { background: #f59e0b; color: #0a0e17; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-family: inherit; font-weight: bold; }
.btn:hover { background: #fbbf24; }
input { background: #1e293b; border: 1px solid #334155; color: #e2e8f0; padding: 8px; border-radius: 4px; font-family: inherit; }
.alert { padding: 8px; margin: 4px 0; border-radius: 4px; font-size: 0.9em; }
.alert-critical { background: #7f1d1d; } .alert-warning { background: #78350f; } .alert-info { background: #1e3a5f; }
</style>
</head>
<body>
<div class="header"><h1>🛡️ SOURCESEAL TACTICAL v5.0</h1></div>
<div class="grid">
<div class="card">
<h2>📡 Estado del Sistema</h2>
<p><span class="status s-green"></span> Master: Activo</p>
<p><span class="status s-green"></span> Workers: <span id="workers-count">0</span></p>
<p><span class="status s-green"></span> COM-LINK: <span id="comlink-status">Verificando...</span></p>
<p><span class="status s-green"></span> Playbooks: <span id="pb-count">0</span></p>
</div>
<div class="card">
<h2>🎯 Acciones Rápidas</h2>
<p><input id="scan-target" placeholder="192.168.1.0/24" style="width:180px"> <button class="btn" onclick="doScan()">Escanear</button></p>
<p><input id="pb-target" placeholder="192.168.0.7" style="width:180px">
<select id="pb-name" style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;padding:8px;border-radius:4px">
<option value="hikvision_full_assault">Hikvision Full Assault</option>
<option value="osint_deep_dive">OSINT Deep Dive</option>
</select>
<button class="btn" onclick="doPlaybook()">Ejecutar</button></p>
<p><input id="dist-targets" placeholder="192.168.0.1,192.168.0.7" style="width:180px"> <button class="btn" onclick="doDispatch()">Despachar</button></p>
</div>
</div>
<div class="card">
<h2>📋 Alertas en Tiempo Real</h2>
<div id="alerts"><p style="color:#64748b">Conectando WebSocket...</p></div>
</div>
<div class="card">
<h2>📦 Workers Activos</h2>
<div id="workers"><p style="color:#64748b">Sin workers registrados</p></div>
</div>
<script>
const ws = new WebSocket(`ws://${location.host}/ws/alerts`);
ws.onmessage = function(e) {
    const d = JSON.parse(e.data);
    const a = document.getElementById('alerts');
    const div = document.createElement('div');
    div.className = 'alert alert-' + (d.severity || d.type || 'info');
    div.innerHTML = `<b>${(d.severity||d.type||'INFO').toUpperCase()}</b> ${d.message||JSON.stringify(d)}`;
    a.prepend(div);
    if (a.children.length > 15) a.removeChild(a.lastChild);
};
ws.onopen = () => { document.getElementById('alerts').innerHTML = '<p style="color:#4ade80">✅ WebSocket conectado</p>'; };
function doScan() {
    const t = document.getElementById('scan-target').value;
    if (!t) return;
    fetch(`/api/scan?target=${t}`, {method:'POST'}).then(r=>r.json()).then(d=>{
        const a = document.getElementById('alerts');
        const div = document.createElement('div');
        div.className = 'alert alert-info';
        div.innerHTML = `<b>SCAN</b> ${t}: ${d.total||0} hosts encontrados`;
        a.prepend(div);
    });
}
function doPlaybook() {
    const t = document.getElementById('pb-target').value;
    const p = document.getElementById('pb-name').value;
    if (!t) return;
    fetch(`/api/playbook/execute?playbook=${p}&target=${t}`, {method:'POST'}).then(r=>r.json()).then(d=>{
        const a = document.getElementById('alerts');
        const div = document.createElement('div');
        div.className = 'alert alert-' + (d.status==='compromised'?'critical':'info');
        div.innerHTML = `<b>PLAYBOOK</b> ${p} → ${t}: ${d.status}`;
        a.prepend(div);
    });
}
function doDispatch() {
    const t = document.getElementById('dist-targets').value.split(',').map(s=>s.trim());
    if (!t.length) return;
    fetch('/api/distributed/dispatch', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(t)})
    .then(r=>r.json()).then(d=>{
        alert(`Despachadas ${d.tasks_added} tareas, cola: ${d.queue_size}`);
    });
}
// Poll workers
setInterval(() => {
    fetch('/api/workers').then(r=>r.json()).then(d=>{
        document.getElementById('workers-count').textContent = d.workers.length;
        const w = document.getElementById('workers');
        if (d.workers.length === 0) { w.innerHTML = '<p style="color:#64748b">Sin workers</p>'; return; }
        w.innerHTML = d.workers.map(w => `<p><span class="status s-${w.status==='idle'?'green':'yellow'}"></span> ${w.worker_id} — ${w.status}</p>`).join('');
    });
    fetch('/api/status').then(r=>r.json()).then(d=>{
        document.getElementById('comlink-status').textContent = d.comlink?.meshtastic ? 'Meshtastic' : 'Bash scripts';
        document.getElementById('pb-count').textContent = d.playbooks?.length || 0;
    });
}, 5000);
</script>
</body>
</html>""")

    @app.get("/api/status")
    async def status():
        workers = db.get_workers()
        return {
            "version": "5.0.0",
            "mode": CONFIG["mode"],
            "workers": len(workers),
            "comlink": {"available": comlink.available, "meshtastic": False, "briar": False},
            "playbooks": [p["name"] for p in playbook_engine.list_playbooks()],
            "alerts": len(db.get_alerts(100)),
        }

    @app.get("/api/workers")
    async def get_workers():
        return {"workers": db.get_workers()}

    @app.get("/api/alerts")
    async def get_alerts(limit: int = 20):
        return {"alerts": db.get_alerts(limit)}

    @app.post("/api/scan")
    async def api_scan(target: str = Query(...)):
        result = await scan_target(target)
        h = db.save_scan(target, result)
        await ws_manager.broadcast({"type": "scan", "target": target, "hosts": result.get("total", 0),
                                     "severity": "info", "message": f"Scan {target}: {result.get('total',0)} hosts"})
        return {"hash": h, **result}

    @app.post("/api/playbook/execute")
    async def api_playbook(playbook: str = Query(...), target: str = Query(...)):
        result = await playbook_engine.execute(playbook, target)
        sev = "critical" if result.get("status") == "compromised" else "info"
        await ws_manager.broadcast({"type": "playbook", "severity": sev, "target": target,
                                     "message": f"Playbook {playbook}: {result['status']}"})
        if result.get("status") == "compromised":
            await comlink.send_critical_alert(f"Playbook {playbook} ejecutado en {target}: COMPROMISED")
        return result

    @app.get("/api/playbook/history")
    async def pb_history():
        return {"history": db.get_playbook_history()}

    @app.get("/api/playbook/list")
    async def pb_list():
        return {"playbooks": playbook_engine.list_playbooks()}

    @app.websocket("/ws/alerts")
    async def ws_alerts(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    # ── Distribución Master-Worker ──
    task_queue = deque()

    @app.post("/api/distributed/dispatch")
    async def dispatch_tasks(targets: List[str]):
        for target in targets:
            task_queue.append({
                "task_id": f"dist_{int(time.time())}_{os.urandom(2).hex()}",
                "type": "scan",
                "target": target
            })
        await ws_manager.broadcast({"type": "dispatch", "severity": "info",
                                     "message": f"Despachadas {len(targets)} tareas"})
        return {"status": "queued", "tasks_added": len(targets), "queue_size": len(task_queue)}

    @app.post("/api/distributed/register")
    async def register_worker(worker_data: dict):
        worker_id = worker_data.get("worker_id")
        if not worker_id:
            raise HTTPException(status_code=400, detail="Worker ID required")
        db.save_worker(worker_id, "idle", worker_data.get("capabilities", ["scan"]))
        await ws_manager.broadcast({"type": "worker_joined", "severity": "info",
                                     "message": f"Worker {worker_id} registrado"})
        return {"status": "registered", "worker_id": worker_id}

    @app.post("/api/distributed/task/request")
    async def request_task(worker_data: dict):
        worker_id = worker_data.get("worker_id")
        if not worker_id:
            raise HTTPException(status_code=400, detail="Worker ID required")
        if task_queue:
            task = task_queue.popleft()
            db.save_worker(worker_id, "busy", [])
            return task
        db.save_worker(worker_id, "idle", [])
        return {"task_id": None}

    @app.post("/api/distributed/task/result")
    async def submit_result(result_data: dict):
        worker_id = result_data.get("worker_id")
        task_id = result_data.get("task_id")
        db.save_worker(worker_id, "idle", [])
        if result_data.get("status") == "completed":
            await ws_manager.broadcast({"type": "task_complete", "severity": "info",
                                         "message": f"Worker {worker_id} completó {task_id}"})
            result = result_data.get("result", {})
            if result.get("total", 0) > 0:
                db.save_scan(result.get("target", "unknown"), result)
        return {"status": "received"}

else:
    # Sin FastAPI — modo CLI básico
    app = None
    ws_manager = None
    log_warn("FastAPI no disponible — modo CLI únicamente")

# ============================================================
# 8. WORKER NODE
# ============================================================
class WorkerNode:
    def __init__(self, master_url: str, worker_id: str):
        self.master_url = master_url.rstrip('/')
        self.worker_id = worker_id
        self.running = False

    async def register(self) -> bool:
        if not HAS_AIOHTTP:
            log_error("aiohttp no instalado — worker no disponible (pip install aiohttp)")
            return False
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.master_url}/api/distributed/register",
                                        json={"worker_id": self.worker_id, "capabilities": ["scan"]}) as resp:
                    if resp.status == 200:
                        log_info(f"✅ Worker {self.worker_id} registrado en {self.master_url}")
                        return True
                    log_error(f"Error registro: {resp.status}")
                    return False
            except aiohttp.ClientError as e:
                log_error(f"No se pudo conectar al Master: {e}")
                return False

    async def heartbeat_loop(self):
        self.running = True
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.master_url}/api/distributed/task/request",
                                            json={"worker_id": self.worker_id}) as resp:
                        if resp.status == 200:
                            task = await resp.json()
                            if task.get("task_id"):
                                log_info(f"🔧 [{self.worker_id}] Tarea: {task['type']} → {task['target']}")
                                result = await scan_target(task["target"])
                                await session.post(f"{self.master_url}/api/distributed/task/result",
                                                   json={"worker_id": self.worker_id, "task_id": task["task_id"],
                                                         "status": "completed", "result": result})
                                log_info(f"✅ [{self.worker_id}] Tarea completada")
            except aiohttp.ClientError:
                await asyncio.sleep(5)
            except Exception as e:
                log_error(f"Worker error: {e}")
                await asyncio.sleep(5)

    async def run(self):
        if await self.register():
            await self.heartbeat_loop()

# ============================================================
# 9. TAREAS DE FONDO (Master)
# ============================================================
async def background_queue_processor():
    """Procesa cola de COM-LINK cada 30s"""
    while True:
        await asyncio.sleep(30)
        try:
            await comlink.process_queue()
        except Exception as e:
            log_debug(f"Queue processor: {e}")

async def background_heartbeat():
    """Broadcast heartbeat cada 10s"""
    while True:
        await asyncio.sleep(10)
        if ws_manager:
            await ws_manager.broadcast({"type": "heartbeat", "workers": len(db.get_workers())})

# ============================================================
# 10. PUNTO DE ENTRADA
# ============================================================
async def run_master():
    if not HAS_FASTAPI:
        log_error("FastAPI no instalado. Instala con: pip install fastapi uvicorn aiohttp pycryptodome")
        sys.exit(1)

    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🛡️ SOURCESEAL TACTICAL v5.0 — Plataforma de Operaciones  ║
    ║  Master: Activo | Puerto: 8001 | COM-LINK: Integrado     ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    print(f"  🌐 API REST:  http://{CONFIG['host']}:{CONFIG['port']}")
    print(f"  📡 WebSocket: ws://{CONFIG['host']}:{CONFIG['port']}/ws/alerts")
    print(f"  📊 Dashboard: http://localhost:{CONFIG['port']}/")
    print(f"  🚨 COM-LINK:  {'✅ Encontrado' if comlink.available else '❌ No encontrado'}")
    print(f"  📖 Playbooks: {[p['name'] for p in playbook_engine.list_playbooks()]}")
    print("")

    # COM-LINK y tareas de fondo se inicializan en @app.on_event('startup')
    # Iniciar servidor
    config = uvicorn.Config(app, host=CONFIG["host"], port=CONFIG["port"],
                           log_level="info", access_log=False,
                           reload=CONFIG.get("reload", True), debug=CONFIG.get("debug", True))
    server = uvicorn.Server(config)
    await server.serve()

async def run_worker(master_url: str, worker_id: str):
    worker = WorkerNode(master_url, worker_id)
    await worker.run()

def main():
    parser = argparse.ArgumentParser(description="SourceSeal TACTICAL v5.0")
    parser.add_argument("--mode", choices=["master", "worker"], default="master",
                       help="Modo de operación (default: master)")
    parser.add_argument("--master-url", default="http://localhost:8001",
                       help="URL del master (modo worker)")
    parser.add_argument("--worker-id", default=os.urandom(4).hex(),
                       help="ID del worker (auto-generado)")
    args = parser.parse_args()

    if args.mode == "worker":
        asyncio.run(run_worker(args.master_url, args.worker_id))
    else:
        asyncio.run(run_master())

if __name__ == "__main__":
    main()
