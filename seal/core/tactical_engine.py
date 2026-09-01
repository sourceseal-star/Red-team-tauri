#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEAL TACTICAL ENGINE (Ultimate Edition)
========================================================
Motor de escaneo táctico de máxima potencia con persistencia
transaccional (SQLite), cifrado local (Fernet/AES) y reportes
encriptados en disco.

Integración: este módulo NO levanta su propio servidor por defecto.
Se importa como router en el backend principal
(redteam/scripts/dashboard_server.py), igual que seal_api_router.py.
Uso opcional como script suelto (Termux, sin dashboard):
    python3 -m seal.core.tactical_engine --network 192.168.0.0/24
    python3 -m seal.core.tactical_engine --serve --port 8011   # standalone

Autor: Harold Paredes / SourceSeal Red Team
"""

import asyncio
import subprocess
import json
import ipaddress
import sqlite3
import threading
import time
import os
import stat
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

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

# ============================================================
# CONFIGURACIÓN GLOBAL TÁCTICA (compatible Termux + Replit)
# ============================================================


def _resolve_report_dir() -> str:
    """
    En Termux, ~/storage/downloads solo existe si el usuario corrió
    `termux-setup-storage`. Si no existe o no es escribible, cae a
    un directorio local en el home — igual que el fix aplicado antes
    a COMMANDER para /tmp.
    """
    termux_downloads = os.path.expanduser("~/storage/downloads/seal_reports")
    parent = os.path.dirname(termux_downloads)
    if os.path.isdir(parent) and os.access(parent, os.W_OK):
        return termux_downloads
    return os.path.expanduser("~/seal_reports")


def _resolve_encryption_key() -> str:
    """
    Prioridad: variable de entorno SEAL_MASTER_KEY > llave persistida en
    disco > generar una nueva y persistirla.
    Generar una llave nueva en cada arranque (comportamiento original)
    volvería ilegibles los reportes ya cifrados. Se persiste una sola vez.
    """
    env_key = os.environ.get("SEAL_MASTER_KEY")
    if env_key:
        return env_key

    key_dir = os.path.expanduser("~/.seal")
    key_path = os.path.join(key_dir, "tactical.key")
    os.makedirs(key_dir, exist_ok=True)

    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()

    new_key = Fernet.generate_key().decode()
    with open(key_path, "w") as f:
        f.write(new_key)
    try:
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)  # 600
    except OSError:
        pass
    return new_key


CONFIG = {
    "db_path": os.path.expanduser("~/seal_tactical.db"),
    "report_dir": _resolve_report_dir(),
    "full_ports": [
        21, 22, 23, 25, 53, 80, 110, 139, 443, 445, 554, 1935, 3306,
        3389, 5432, 6379, 8000, 8080, 8443, 8554, 8888, 37777
    ],
    "timeout_tcp": 0.4,
    "timeout_ping": 0.5,
    "max_concurrent": 150,
    "encryption_key": _resolve_encryption_key(),
}

os.makedirs(CONFIG["report_dir"], exist_ok=True)

db_lock = threading.Lock()

# ============================================================
# 1. PERSISTENCIA Y SEGURIDAD (SQLite + Fernet)
# ============================================================


def init_db():
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tactical_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            results_json TEXT NOT NULL,
            vulnerability_index INTEGER,
            status TEXT DEFAULT 'completed'
        )''')
        conn.commit()
        conn.close()


def save_scan_db(target: str, data: dict, vuln_index: int):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT INTO tactical_scans (target, timestamp, results_json, "
            "vulnerability_index, status) VALUES (?, ?, ?, ?, ?)",
            (target, datetime.now(timezone.utc).isoformat(), json.dumps(data),
             vuln_index, 'completed')
        )
        conn.commit()
        conn.close()


def encrypt_data(raw_data: str) -> str:
    f = Fernet(CONFIG["encryption_key"].encode())
    return f.encrypt(raw_data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    f = Fernet(CONFIG["encryption_key"].encode())
    return f.decrypt(encrypted_data.encode()).decode()


# ============================================================
# 2. MOTOR DE ESCANEO DE MÁXIMA POTENCIA
# ============================================================


async def aggressive_tcp_ping(ip: str, port: int = 80) -> bool:
    try:
        conn = asyncio.open_connection(ip, port)
        _, writer = await asyncio.wait_for(conn, timeout=CONFIG["timeout_ping"])
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def multi_layer_discovery(network: str) -> List[str]:
    net = ipaddress.ip_network(network, strict=False)
    all_ips = [str(ip) for ip in net.hosts()]
    active_hosts = set()

    # ARP local pass (requiere paquete iproute2; en Termux: pkg install iproute2)
    try:
        proc = await asyncio.create_subprocess_exec(
            "ip", "neigh", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        for line in stdout.decode().splitlines():
            parts = line.split()
            if parts:
                active_hosts.add(parts[0])
    except Exception:
        pass

    # TCP Fallback pass — funciona siempre, con o sin `ip neigh`
    discovery_ports = [80, 443, 554, 8080, 37777]
    semaphore = asyncio.Semaphore(CONFIG["max_concurrent"])

    async def check_host(ip):
        async with semaphore:
            for port in discovery_ports:
                if await aggressive_tcp_ping(ip, port):
                    return ip
            return None

    tasks = [check_host(ip) for ip in all_ips if ip not in active_hosts]
    results = await asyncio.gather(*tasks)
    for r in results:
        if r:
            active_hosts.add(r)

    return list(active_hosts)


async def deep_port_scan(ip: str) -> List[int]:
    open_ports = []
    semaphore = asyncio.Semaphore(CONFIG["max_concurrent"])

    async def test_port(port):
        async with semaphore:
            try:
                conn = asyncio.open_connection(ip, port)
                _, writer = await asyncio.wait_for(conn, timeout=CONFIG["timeout_tcp"])
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except Exception:
                pass

    tasks = [test_port(p) for p in CONFIG["full_ports"]]
    await asyncio.gather(*tasks)
    return sorted(open_ports)


async def run_full_audit(network: str) -> dict:
    init_db()
    targets = await multi_layer_discovery(network)
    scan_results = []
    total_vuln = 0

    for ip in targets:
        ports = await deep_port_scan(ip)
        vuln_score = len(ports)
        total_vuln += vuln_score
        host_info = {"ip": ip, "open_ports": ports, "vulnerability_score": vuln_score}
        scan_results.append(host_info)
        save_scan_db(ip, host_info, vuln_score)

    report = {
        "network": network,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "active_hosts": len(targets),
        "total_vulnerability_score": total_vuln,
        "hosts": scan_results
    }

    report_filename = os.path.join(
        CONFIG["report_dir"], f"tactical_report_{int(time.time())}.enc"
    )
    encrypted_payload = encrypt_data(json.dumps(report, indent=2))
    with open(report_filename, "w") as f:
        f.write(encrypted_payload)

    report["report_file"] = report_filename
    return report


# ============================================================
# 3. ROUTER FASTAPI (para montar en dashboard_server.py)
# ============================================================
# Prefijo namespaced para no chocar con /api/scan, /api/health, etc.
# ya usados por seal_api_router.py.

router = APIRouter(prefix="/api/seal/tactical", tags=["seal-tactical"])


@router.on_event("startup")
def _startup_event():
    init_db()


@router.post("/scan")
async def trigger_scan(network: str, background_tasks: BackgroundTasks):
    try:
        ipaddress.ip_network(network, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de red CIDR inválido.")

    background_tasks.add_task(run_full_audit, network)
    return {"status": "success", "message": f"Escaneo táctico iniciado para {network}"}


@router.get("/results")
async def get_results():
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM tactical_scans ORDER BY id DESC LIMIT 50")
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
    return {"status": "success", "data": rows}


@router.get("/health")
async def health_check():
    return {
        "status": "online",
        "encryption": "AES-256-Fernet Active",
        "database": "SQLite Thread-Safe",
        "report_dir": CONFIG["report_dir"],
    }


def get_tactical_router() -> APIRouter:
    """Obtiene el router del motor táctico."""
    return router


def include_tactical_routes(app):
    """Incluye las rutas del motor táctico en una app FastAPI existente."""
    app.include_router(router)


# ============================================================
# 4. CLI — uso directo en Termux sin necesidad del dashboard
# ============================================================


def _run_cli():
    parser = argparse.ArgumentParser(
        description="SEAL Tactical Engine — escaneo táctico standalone"
    )
    parser.add_argument("--network", help="Red CIDR a escanear, ej: 192.168.0.0/24")
    parser.add_argument(
        "--serve", action="store_true",
        help="Levanta un servidor FastAPI standalone (NO usar junto al dashboard "
             "principal en el mismo puerto)."
    )
    parser.add_argument(
        "--port", type=int, default=8011,
        help="Puerto para --serve. Default 8011 (el dashboard principal usa 8001)."
    )
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        from fastapi import FastAPI
        standalone_app = FastAPI(title="SEAL Tactical Engine (standalone)")
        include_tactical_routes(standalone_app)
        uvicorn.run(standalone_app, host="0.0.0.0", port=args.port)
        return

    if not args.network:
        parser.error("--network es requerido si no usas --serve")

    report = asyncio.run(run_full_audit(args.network))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[+] Reporte cifrado guardado en: {report['report_file']}")


if __name__ == "__main__":
    _run_cli()
