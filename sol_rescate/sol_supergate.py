#!/usr/bin/env python3
"""
SOL SUPERGATE — companion non-root gate for Android/Termux.

This is an additive fallback for omni.sh. The existing ~/sol/sol_portero.py
always has priority. This module is only started when that file is absent.

Safety decisions:
* no default credential: SOL_API_KEY or SOL_KEY is mandatory;
* loopback-only listener by default;
* subprocesses use argument arrays, close_fds and short timeouts;
* action execution is an explicit allowlist;
* network sweep is bounded and returns metadata only.
"""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import os
import re
import shutil
import socket
import struct
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request


app = FastAPI(title="Sol SuperGate", version="3.0.0")
HOST = os.environ.get("SOL_SUPERGATE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SOL_GATE_PORT", os.environ.get("SOL_SUPERGATE_PORT", "8012")))
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")


def _secret() -> str:
    """Use the canonical Sol key, with SOL_KEY kept as compatibility alias."""
    return os.environ.get("SOL_API_KEY", "").strip() or os.environ.get("SOL_KEY", "").strip()


def _config_path() -> Path:
    explicit = os.environ.get("SOL_SUPERGATE_CONFIG", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    redteam_dir = os.environ.get("REDTEAM_DIR", "").strip()
    if redteam_dir:
        return Path(redteam_dir) / "data" / "sol_supergate.json"
    return Path.cwd() / "data" / "sol_supergate.json"


def _config() -> dict[str, Any]:
    path = _config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def verify_sol_gate(x_sol_key: str | None = Header(default=None)) -> bool:
    key = _secret()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="SOL_API_KEY no está configurada; el portero permanece cerrado.",
        )
    if not x_sol_key or not hmac.compare_digest(x_sol_key, key):
        raise HTTPException(status_code=403, detail="Credencial de portero inválida.")
    return True


def run_safe_command(command: list[str], timeout: float = 8.0) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            close_fds=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout[-16_384:], result.stderr[-4_096:], result.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 124
    except (OSError, ValueError) as exc:
        return "", str(exc), 1


def _valid_target(target: str) -> bool:
    if not target or len(target) > 253 or not _HOSTNAME_RE.fullmatch(target):
        return False
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return True


def obtener_vecinos_netlink() -> list[dict[str, str]]:
    stdout, _, code = run_safe_command(["ip", "neighbor"])
    if code != 0:
        return []
    devices: list[dict[str, str]] = []
    for line in stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        address = parts[0]
        try:
            ipaddress.ip_address(address)
        except ValueError:
            continue
        mac = "desconocida"
        if "lladdr" in parts:
            index = parts.index("lladdr")
            if index + 1 < len(parts):
                mac = parts[index + 1]
        state = parts[-1] if parts[-1] in {
            "REACHABLE", "STALE", "DELAY", "FAILED", "PROBE", "INCOMPLETE"
        } else "activo"
        if state not in {"FAILED", "INCOMPLETE"}:
            devices.append({"ip": address, "mac": mac, "state": state})
    return devices


def escaneo_mdns_activo() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    multicast_ip = "224.0.0.251"
    port = 5353
    query = (
        b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        b"\x08_services\x07_dns-sd\x04_udp\x05local\x00\x00\x0c\x00\x01"
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        sock.bind(("", port))
        membership = struct.pack("4sl", socket.inet_aton(multicast_ip), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.settimeout(1.5)
        sock.sendto(query, (multicast_ip, port))
        while True:
            try:
                data, address = sock.recvfrom(1024)
                results.append({"ip": address[0], "bytes": len(data)})
            except socket.timeout:
                break
            except OSError:
                break
    except OSError:
        return []
    finally:
        sock.close()
    return results


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "available": True,
        "engine": "sol_supergate_nonroot",
        "auth_required": True,
        "port": PORT,
        "config_loaded": bool(_config()),
    }


@app.get("/sol/contexto")
async def contexto(x_sol_key: str | None = Header(default=None)) -> dict[str, Any]:
    verify_sol_gate(x_sol_key)
    config = _config()
    return {
        "aprobaciones_pendientes": 0,
        "repos": {"Red-team-tauri": "activo", "sol_supergate": "operativo"},
        "pendientes": {},
        "engine": "sol_supergate_nonroot",
        "mode": config.get("mode", "protected"),
    }


@app.post("/api/network/sweep-real")
async def sweep_real(x_sol_key: str | None = Header(default=None)) -> dict[str, Any]:
    verify_sol_gate(x_sol_key)
    neighbors, mdns = await asyncio.gather(
        asyncio.to_thread(obtener_vecinos_netlink),
        asyncio.to_thread(escaneo_mdns_activo),
    )
    return {
        "status": "success",
        "engine": "sol_supergate_nonroot",
        "arp_table": neighbors,
        "mdns_responses": mdns,
        "total_activos": len(neighbors),
    }


@app.post("/api/action/execute")
async def execute_action(
    request: Request, x_sol_key: str | None = Header(default=None)
) -> dict[str, Any]:
    verify_sol_gate(x_sol_key)
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON inválido.") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="El cuerpo debe ser un objeto JSON.")

    action = str(body.get("action", "")).strip()
    commands: dict[str, list[str]] = {
        "netstat": ["netstat", "-tuln"],
        "ip_neigh": ["ip", "neighbor"],
    }
    if action == "ping":
        target = str(body.get("target", "127.0.0.1")).strip()
        if not _valid_target(target):
            raise HTTPException(status_code=400, detail="target inválido.")
        commands[action] = ["ping", "-c", "3", "-W", "2", target]
    elif action not in commands:
        raise HTTPException(
            status_code=400,
            detail="Acción no soportada. Usa: ping, netstat o ip_neigh.",
        )
    if action == "netstat" and not shutil.which("netstat"):
        if shutil.which("ss"):
            commands[action] = ["ss", "-tuln"]
        else:
            raise HTTPException(status_code=503, detail="No hay netstat ni ss disponible.")

    stdout, stderr, code = await asyncio.to_thread(run_safe_command, commands[action])
    return {"executed": code == 0, "action": action, "stdout": stdout, "stderr": stderr}


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "sol_supergate",
        "engine": "sol_supergate_nonroot",
        "hint": "Usa /health o autentica las rutas /sol/contexto y /api/*.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)