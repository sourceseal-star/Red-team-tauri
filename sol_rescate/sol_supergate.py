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
import hashlib
import hmac
import ipaddress
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import threading
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, StrictInt, StrictStr, root_validator, validator


app = FastAPI(title="Sol SuperGate", version="3.0.0")
HOST = os.environ.get("SOL_SUPERGATE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SOL_GATE_PORT", os.environ.get("SOL_SUPERGATE_PORT", "8012")))
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$")
_HOUR_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

# Runtime tools are intentionally separate from the legacy, fixed action
# allowlist below. A protected manifest can only launch these executable names;
# shell strings require an explicit full mode in the manifest.
ALLOWED = {
    "python3",
    "termux-tts-speak",
    "termux-notification",
    "termux-torch",
    "nmap",
    "rclone",
    "ss",
    "git",
    "ping",
    "ip",
    "netstat",
}


class _StrictModel(BaseModel):
    class Config:
        extra = "forbid"
        validate_assignment = True


class ToolDef(_StrictModel):
    name: StrictStr = Field(min_length=1, max_length=80)
    argv: Optional[List[StrictStr]] = None
    cmd: Optional[StrictStr] = Field(default=None, max_length=4096)
    policy: Literal["auto", "manual"] = "auto"
    timeout: StrictInt = Field(default=60, ge=1, le=86_400)

    @root_validator(skip_on_failure=True)
    def exactly_one_command(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        argv = values.get("argv")
        cmd = values.get("cmd")
        if bool(argv) == bool(cmd):
            raise ValueError("cada herramienta debe definir exactamente un argv o un cmd")
        if argv is not None and not argv[0].strip():
            raise ValueError("argv debe comenzar con un ejecutable")
        return values


class RitualDef(_StrictModel):
    nombre: StrictStr = Field(min_length=1, max_length=80)
    hora: StrictStr
    tool: StrictStr = Field(min_length=1, max_length=80)
    args: Dict[str, Any] = Field(default_factory=dict)

    @validator("hora")
    def valid_hour(cls, value: str) -> str:
        if not _HOUR_RE.fullmatch(value):
            raise ValueError("hora debe usar el formato HH:MM")
        return value


class ManifestModel(_StrictModel):
    name: StrictStr = Field(min_length=1, max_length=120)
    mode: Literal["protected", "full"] = "protected"
    port: StrictInt = Field(default=8012, ge=1, le=65_535)
    notes: Optional[StrictStr] = Field(default=None, max_length=4_000)
    tools: List[ToolDef] = Field(default_factory=list)
    rituales: List[RitualDef] = Field(default_factory=list)

    @root_validator(skip_on_failure=True)
    def ritual_tools_must_exist(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        tool_defs = values.get("tools", [])
        ritual_defs = values.get("rituales", [])
        tool_names = [tool.name for tool in tool_defs]
        ritual_names = [ritual.nombre for ritual in ritual_defs]
        if len(tool_names) != len(set(tool_names)):
            raise ValueError("no se permiten nombres de herramienta duplicados")
        if len(ritual_names) != len(set(ritual_names)):
            raise ValueError("no se permiten nombres de ritual duplicados")
        tools = set(tool_names)
        missing = sorted({ritual.tool for ritual in ritual_defs} - tools)
        if missing:
            raise ValueError(f"rituales apuntan a herramientas inexistentes: {', '.join(missing)}")
        return values


class RuntimeExecuteRequest(_StrictModel):
    tool: StrictStr = Field(min_length=1, max_length=80)
    args: Dict[str, Any] = Field(default_factory=dict)


RUNTIME: Dict[str, Any] = {
    "hash": None,
    "mode": "protected",
    "tools": {},
    "rituales": [],
    "manifest_error": None,
    "last_loaded_at": None,
    "last_block_hash": "0" * 64,
    "audit_error": None,
}
_RUNTIME_LOCK = threading.RLock()
_AUDIT_LOCK = threading.Lock()
_MANIFEST_TASK: Optional[asyncio.Task] = None
_RITUAL_TASK: Optional[asyncio.Task] = None
_RITUAL_LAST_RUN: Dict[str, str] = {}


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
    project_manifest = Path(__file__).resolve().parents[1] / "redteam" / "data" / "sol_supergate.json"
    if project_manifest.exists():
        return project_manifest
    return Path.cwd() / "data" / "sol_supergate.json"


def _config() -> dict[str, Any]:
    path = _config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _model_dump(model: BaseModel) -> dict[str, Any]:
    """Support the Pydantic 1.x and 2.x APIs used by Termux/Replit."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _audit_log_path() -> Path:
    explicit = os.environ.get("SOL_SUPERGATE_AUDIT_LOG", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return _config_path().with_name("audit_chain.jsonl")


def _restore_chain_head() -> None:
    """Resume only after verifying every persisted block in the chain."""
    path = _audit_log_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError) as exc:
        message = f"No se pudo leer la cadena de auditoría {path}: {exc}"
        with _RUNTIME_LOCK:
            RUNTIME["audit_error"] = message
        raise RuntimeError(message) from exc
    previous = "0" * 64
    try:
        for line_number, line in enumerate(lines, start=1):
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("el bloque no es un objeto JSON")
            candidate = payload.get("block_hash", "")
            if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate):
                raise ValueError("block_hash inválido")
            if payload.get("prev_hash") != previous:
                raise ValueError("prev_hash no coincide con la cabeza anterior")
            unsigned = dict(payload)
            del unsigned["block_hash"]
            block_string = json.dumps(
                unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            if hashlib.sha256(block_string.encode("utf-8")).hexdigest() != candidate:
                raise ValueError("el contenido no coincide con block_hash")
            previous = candidate
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        message = f"Cadena de auditoría corrupta en {path}, línea {line_number}: {exc}"
        with _RUNTIME_LOCK:
            RUNTIME["audit_error"] = message
        raise RuntimeError(message) from exc
    with _RUNTIME_LOCK:
        RUNTIME["last_block_hash"] = previous
        RUNTIME["audit_error"] = None


def _redact_audit_value(value: Any) -> Any:
    """Avoid persisting credentials when a tool receives them as arguments."""
    sensitive = ("key", "token", "password", "passwd", "secret", "credential")
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if any(part in key.lower() for part in sensitive)
                  else _redact_audit_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_audit_value(item) for item in value]
    return value


def seal_event(tool: str, args: dict[str, Any], ok: bool, output_snippet: str) -> str:
    """Append one tamper-evident audit block and return its short identifier."""
    with _AUDIT_LOCK:
        with _RUNTIME_LOCK:
            if RUNTIME["audit_error"]:
                raise RuntimeError(RUNTIME["audit_error"])
            previous = RUNTIME["last_block_hash"]
        payload = {
            "prev_hash": previous,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "args": _redact_audit_value(args),
            "ok": bool(ok),
            "output": (output_snippet or "")[-2_000:],
        }
        block_string = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        block_hash = hashlib.sha256(block_string.encode("utf-8")).hexdigest()
        payload["block_hash"] = block_hash
        path = _audit_log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as audit_file:
                audit_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
                audit_file.flush()
                os.fsync(audit_file.fileno())
        except OSError:
            # A failed audit must never claim success or mutate the chain head.
            raise
        with _RUNTIME_LOCK:
            RUNTIME["last_block_hash"] = block_hash
        return block_hash[:16]


def _runtime_snapshot() -> dict[str, Any]:
    with _RUNTIME_LOCK:
        return {
            "hash": RUNTIME["hash"],
            "mode": RUNTIME["mode"],
            "tools": dict(RUNTIME["tools"]),
            "rituales": list(RUNTIME["rituales"]),
            "manifest_error": RUNTIME["manifest_error"],
            "last_loaded_at": RUNTIME["last_loaded_at"],
            "last_block_hash": RUNTIME["last_block_hash"],
            "audit_error": RUNTIME["audit_error"],
        }


def load_manifest() -> dict[str, Any]:
    """Validate first, then atomically replace the live runtime on change."""
    path = _config_path()
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            raise ValueError("la raíz del manifiesto debe ser un objeto JSON")
        if hasattr(ManifestModel, "model_validate"):
            validated = ManifestModel.model_validate(raw_data)
        else:
            validated = ManifestModel.parse_obj(raw_data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        with _RUNTIME_LOCK:
            RUNTIME["manifest_error"] = f"Error de sintaxis o esquema: {exc}"
        return {"cambio": False, "error": RUNTIME["manifest_error"]}

    data_dict = _model_dump(validated)
    canonical = json.dumps(data_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    manifest_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with _RUNTIME_LOCK:
        if manifest_hash == RUNTIME["hash"]:
            RUNTIME["manifest_error"] = None
            return {"cambio": False, "hash": manifest_hash}
        next_runtime = {
            "hash": manifest_hash,
            "mode": validated.mode,
            "tools": {tool.name: _model_dump(tool) for tool in validated.tools},
            "rituales": [_model_dump(ritual) for ritual in validated.rituales],
            "manifest_error": None,
            "last_loaded_at": datetime.now(timezone.utc).isoformat(),
        }
        RUNTIME.update(next_runtime)
    seal_event(
        "manifest_load",
        {"tools": list(next_runtime["tools"]), "mode": next_runtime["mode"]},
        True,
        f"hash={manifest_hash[:12]}",
    )
    return {"cambio": True, "hash": manifest_hash, "tools": list(next_runtime["tools"])}


def _runtime_policy_error(tool: dict[str, Any], mode: str) -> Optional[str]:
    argv = tool.get("argv")
    if argv:
        executable = Path(str(argv[0])).name
        if mode == "protected" and executable not in ALLOWED:
            return f"ejecutable bloqueado por política protected: {executable}"
        return None
    if tool.get("cmd") and mode != "full":
        return "la ejecución por shell exige mode=full en el manifiesto"
    return None


async def run_runtime_tool(tool: dict[str, Any], args: dict[str, Any], *, ritual: bool = False) -> tuple[bool, str, str, str]:
    """Run a manifest tool without blocking FastAPI's event loop."""
    snapshot = _runtime_snapshot()
    policy_error = _runtime_policy_error(tool, snapshot["mode"])
    if ritual and tool.get("policy") != "auto":
        policy_error = "el ritual solo puede ejecutar herramientas con policy=auto"
    if policy_error:
        seal = seal_event(tool.get("name", "unknown"), args, False, policy_error)
        return False, "", policy_error, seal

    timeout = int(tool.get("timeout", 60))
    stdout_text = ""
    stderr_text = ""
    ok = False
    process: asyncio.subprocess.Process | None = None
    try:
        if tool.get("argv"):
            argv = [str(part).format(**args) for part in tool["argv"]]
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=True,
            )
        else:
            command = str(tool["cmd"]).format(**args)
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        stdout_text = stdout.decode(errors="replace")
        stderr_text = stderr.decode(errors="replace")
        ok = process.returncode == 0
    except asyncio.TimeoutError:
        if process is not None:
            process.kill()
            with suppress(ProcessLookupError):
                await process.wait()
        stderr_text = f"Timeout excedido ({timeout}s)"
    except (OSError, ValueError, KeyError) as exc:
        stderr_text = str(exc)
    seal = seal_event(
        tool.get("name", "unknown"),
        args,
        ok,
        stdout_text or stderr_text,
    )
    return ok, stdout_text[-16_384:], stderr_text[-4_096:], seal


async def manifest_watch(interval: float = 4.0) -> None:
    while True:
        load_manifest()
        await asyncio.sleep(interval)


async def ritual_engine() -> None:
    """Run each matching ritual once per local minute, even after polling."""
    while True:
        now = datetime.now().astimezone()
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        with _RUNTIME_LOCK:
            rituals = list(RUNTIME["rituales"])
            tools = dict(RUNTIME["tools"])
        jobs = []
        for ritual in rituals:
            if ritual["hora"] != now.strftime("%H:%M"):
                continue
            run_key = f"{ritual['nombre']}:{minute_key}"
            if _RITUAL_LAST_RUN.get(run_key):
                continue
            _RITUAL_LAST_RUN[run_key] = minute_key
            tool = tools.get(ritual["tool"])
            if not tool:
                seal_event(ritual["nombre"], ritual.get("args", {}), False, "herramienta inexistente")
                continue
            jobs.append(run_runtime_tool(tool, ritual.get("args", {}), ritual=True))
        if len(_RITUAL_LAST_RUN) > 2_048:
            cutoff = (now.timestamp() - 86_400)
            for key in list(_RITUAL_LAST_RUN):
                try:
                    stamp = datetime.strptime(key.rsplit(":", 1)[-1], "%Y-%m-%d %H:%M").replace(
                        tzinfo=now.tzinfo
                    ).timestamp()
                except ValueError:
                    continue
                if stamp < cutoff:
                    _RITUAL_LAST_RUN.pop(key, None)
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        await asyncio.sleep(5)


@app.on_event("startup")
async def supergate_startup() -> None:
    global _MANIFEST_TASK, _RITUAL_TASK
    _restore_chain_head()
    load_manifest()
    _MANIFEST_TASK = asyncio.create_task(manifest_watch(), name="sol-supergate-manifest-watch")
    _RITUAL_TASK = asyncio.create_task(ritual_engine(), name="sol-supergate-ritual-engine")


@app.on_event("shutdown")
async def supergate_shutdown() -> None:
    global _MANIFEST_TASK, _RITUAL_TASK
    for task in (_MANIFEST_TASK, _RITUAL_TASK):
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    _MANIFEST_TASK = None
    _RITUAL_TASK = None


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


def obtener_interfaces_activas() -> list[dict[str, Any]]:
    """Enumerate every active private IPv4 interface available to Termux."""
    stdout, _, code = run_safe_command(["ip", "-o", "-4", "addr", "show"])
    if code != 0:
        return []
    interfaces: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for line in stdout.splitlines():
        parts = line.split()
        try:
            name = parts[1]
            address_index = parts.index("inet") + 1
            address_cidr = parts[address_index]
            ip, prefix = address_cidr.split("/", 1)
            parsed_ip = ipaddress.ip_address(ip)
            network = ipaddress.ip_network(address_cidr, strict=False)
        except (ValueError, IndexError):
            continue
        rfc1918 = (
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
        )
        if (
            parsed_ip.is_loopback
            or parsed_ip.is_link_local
            or not any(parsed_ip in allowed for allowed in rfc1918)
        ):
            continue
        key = (name, str(network))
        if key in seen:
            continue
        seen.add(key)
        type_hint = (
            "wifi" if name.startswith(("wlan", "wifi"))
            else "mobile" if name.startswith(("rmnet", "ccmni"))
            else "ethernet" if name.startswith(("eth", "en"))
            else "hotspot" if name.startswith(("ap", "swlan"))
            else "unknown"
        )
        interfaces.append({
            "name": name,
            "ip_address": ip,
            "prefix": int(prefix),
            "network_cidr": str(network),
            "type_hint": type_hint,
            "is_up": True,
        })
    return interfaces


def escaneo_mdns_activo() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    multicast_ip = "224.0.0.251"
    port = 5353
    query = (
        b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        b"\x08_services\x07_dns-sd\x04_udp\x05local\x00\x00\x0c\x00\x01"
    )
    interfaces = obtener_interfaces_activas()
    for interface in interfaces or [{"name": "default", "ip_address": ""}]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            sock.bind(("", port))
            local_ip = interface.get("ip_address", "")
            membership = struct.pack(
                "=4s4s", socket.inet_aton(multicast_ip),
                socket.inet_aton(local_ip or "0.0.0.0"),
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            if local_ip:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local_ip))
            sock.settimeout(1.5)
            sock.sendto(query, (multicast_ip, port))
            while True:
                try:
                    data, address = sock.recvfrom(1024)
                    results.append({
                        "ip": address[0], "bytes": len(data),
                        "interface": interface.get("name"),
                    })
                except socket.timeout:
                    break
                except OSError:
                    break
        except OSError:
            pass
        finally:
            sock.close()
    return results


@app.get("/health")
async def health() -> dict[str, Any]:
    runtime = _runtime_snapshot()
    return {
        "available": True,
        "engine": "sol_supergate_nonroot",
        "auth_required": True,
        "port": PORT,
        "config_loaded": bool(_config()),
        "manifest": {
            "loaded": runtime["hash"] is not None,
            "hash": runtime["hash"],
            "tools": list(runtime["tools"]),
            "rituales": len(runtime["rituales"]),
            "error": runtime["manifest_error"],
        },
        "audit": {
            "last_block_hash": runtime["last_block_hash"],
            "error": runtime["audit_error"],
        },
    }


@app.get("/sol/contexto")
async def contexto(x_sol_key: str | None = Header(default=None)) -> dict[str, Any]:
    verify_sol_gate(x_sol_key)
    config = _config()
    runtime = _runtime_snapshot()
    return {
        "aprobaciones_pendientes": 0,
        "repos": {"Red-team-tauri": "activo", "sol_supergate": "operativo"},
        "pendientes": {},
        "engine": "sol_supergate_nonroot",
        "mode": runtime["mode"] if runtime["hash"] else config.get("mode", "protected"),
        "manifest": {
            "hash": runtime["hash"],
            "tools": list(runtime["tools"]),
            "rituales": len(runtime["rituales"]),
            "error": runtime["manifest_error"],
        },
        "audit": {
            "last_block_hash": runtime["last_block_hash"],
            "error": runtime["audit_error"],
        },
    }


@app.get("/api/runtime/status")
async def runtime_status(_: bool = Depends(verify_sol_gate)) -> dict[str, Any]:
    """Return the validated live manifest without exposing command contents."""
    runtime = _runtime_snapshot()
    return {
        "loaded": runtime["hash"] is not None,
        "hash": runtime["hash"],
        "mode": runtime["mode"],
        "tools": [
            {"name": name, "policy": tool.get("policy"), "timeout": tool.get("timeout")}
            for name, tool in runtime["tools"].items()
        ],
        "rituales": runtime["rituales"],
        "manifest_error": runtime["manifest_error"],
        "last_loaded_at": runtime["last_loaded_at"],
        "last_block_hash": runtime["last_block_hash"],
        "audit_error": runtime["audit_error"],
    }


@app.post("/api/runtime/execute")
async def runtime_execute(
    payload: RuntimeExecuteRequest = Body(...),
    _: bool = Depends(verify_sol_gate),
) -> dict[str, Any]:
    """Execute one validated manifest tool using an async subprocess."""
    runtime = _runtime_snapshot()
    tool = runtime["tools"].get(payload.tool)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Herramienta no encontrada: {payload.tool}")
    ok, stdout, stderr, seal = await run_runtime_tool(tool, payload.args)
    if stderr.startswith("ejecutable bloqueado") or stderr.startswith("la ejecución por shell"):
        raise HTTPException(status_code=403, detail=stderr)
    return {
        "executed": ok,
        "tool": payload.tool,
        "stdout": stdout,
        "stderr": stderr,
        "seal": seal,
    }


@app.post("/api/network/sweep-real")
async def sweep_real(x_sol_key: str | None = Header(default=None)) -> dict[str, Any]:
    verify_sol_gate(x_sol_key)
    neighbors, mdns, interfaces = await asyncio.gather(
        asyncio.to_thread(obtener_vecinos_netlink),
        asyncio.to_thread(escaneo_mdns_activo),
        asyncio.to_thread(obtener_interfaces_activas),
    )
    return {
        "status": "success",
        "engine": "sol_supergate_nonroot",
        "interfaces": interfaces,
        "network_cidrs": list(dict.fromkeys(
            item["network_cidr"] for item in interfaces if item.get("network_cidr")
        )),
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
    seal = seal_event(action, {"command": commands[action]}, code == 0, stdout or stderr)
    return {
        "executed": code == 0,
        "action": action,
        "stdout": stdout,
        "stderr": stderr,
        "seal": seal,
    }


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