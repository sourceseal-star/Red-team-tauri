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
from fastapi.responses import HTMLResponse


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


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    """Small local dashboard for the standalone Termux fallback.

    The key is entered by the operator and kept only in browser memory. It is
    never embedded in this page, a URL, local storage, or a default constant.
    """
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
  <title>Sol SuperGate</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      background: #0b0f19;
      color: #e2e8f0;
    }
    body { margin: 0; padding: 24px; background: #0b0f19; }
    main { max-width: 760px; margin: 0 auto; }
    .card {
      background: #1e293b; border: 1px solid #334155; border-radius: 10px;
      padding: 18px; margin: 0 0 16px;
    }
    h1 { font-size: 1.35rem; margin: 0 0 18px; }
    h2 { font-size: 1rem; margin-top: 0; }
    label { display: block; margin: 10px 0 6px; color: #94a3b8; }
    input {
      box-sizing: border-box; width: 100%; padding: 10px; border-radius: 6px;
      border: 1px solid #475569; background: #0f172a; color: #f8fafc;
    }
    button {
      background: #2563eb; color: #fff; border: 0; border-radius: 6px;
      padding: 10px 14px; cursor: pointer; margin: 10px 8px 0 0;
    }
    button:hover { background: #1d4ed8; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    .muted { color: #94a3b8; }
    .ok { color: #4ade80; }
    .error { color: #f87171; }
    pre {
      white-space: pre-wrap; overflow-wrap: anywhere; min-height: 70px;
      background: #0f172a; border-radius: 6px; padding: 12px; color: #38bdf8;
    }
  </style>
</head>
<body>
  <main>
    <h1>🛡️ SOL SUPERGATE — C2 TÁCTICO</h1>
    <section class="card">
      <h2>Estado del portero y red</h2>
      <p id="status" class="muted">Comprobando servicio…</p>
      <label for="key">Clave X-Sol-Key</label>
      <input id="key" type="password" autocomplete="off"
             placeholder="Escribe la clave configurada en el entorno">
      <button id="connect" type="button">Conectar</button>
      <button id="sweep" type="button" disabled>Ejecutar barrido real</button>
    </section>
    <section class="card">
      <h2>Consola de resultados</h2>
      <pre id="log">Sin acciones ejecutadas.</pre>
    </section>
  </main>
  <script>
    const keyInput = document.getElementById("key");
    const statusNode = document.getElementById("status");
    const logNode = document.getElementById("log");
    const connectButton = document.getElementById("connect");
    const sweepButton = document.getElementById("sweep");
    let sessionKey = "";

    function headers() {
      return { "X-Sol-Key": sessionKey, "Content-Type": "application/json" };
    }

    function showError(message) {
      statusNode.textContent = message;
      statusNode.className = "error";
    }

    async function readResponse(response) {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.detail || "La solicitud fue rechazada.");
      }
      return payload;
    }

    async function checkHealth() {
      try {
        const response = await fetch("/health");
        const payload = await readResponse(response);
        statusNode.textContent = payload.available
          ? "Servicio disponible; falta autenticar el contexto."
          : "Servicio no disponible.";
      } catch (error) {
        showError("No se pudo consultar la salud del SuperGate.");
      }
    }

    async function connect() {
      const candidate = keyInput.value.trim();
      if (!candidate) {
        showError("Escribe la clave del portero.");
        sweepButton.disabled = true;
        return;
      }
      try {
        const response = await fetch("/sol/contexto", {
          headers: { "X-Sol-Key": candidate }
        });
        const payload = await readResponse(response);
        sessionKey = candidate;
        sweepButton.disabled = false;
        statusNode.textContent = "Conectado · " + payload.engine;
        statusNode.className = "ok";
        logNode.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        sessionKey = "";
        sweepButton.disabled = true;
        showError(error.message);
      }
    }

    async function executeSweep() {
      if (!sessionKey) {
        showError("Conecta primero el portero.");
        return;
      }
      logNode.textContent = "Iniciando barrido táctico…";
      try {
        const response = await fetch("/api/network/sweep-real", {
          method: "POST", headers: headers()
        });
        const payload = await readResponse(response);
        logNode.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        logNode.textContent = "Error en ejecución: " + error.message;
      }
    }

    connectButton.addEventListener("click", connect);
    sweepButton.addEventListener("click", executeSweep);
    keyInput.addEventListener("keydown", event => {
      if (event.key === "Enter") connect();
    });
    checkHealth();
  </script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)