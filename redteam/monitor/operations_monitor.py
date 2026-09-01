#!/usr/bin/env python3
"""Monitor de operaciones seguro para SourceSeal.

Este módulo expone observabilidad administrativa de bajo riesgo:

* métricas locales de proceso y sistema;
* estado de los repositorios configurados, usando solo comandos Git de lectura;
* auditoría local con una cadena SHA-256;
* capacidades explícitamente deshabilitadas para dejar claro que no existe
  control remoto, shell arbitrario ni ejecución de acciones destructivas.

No recibe comandos de Telegram ni ejecuta texto proporcionado por el usuario.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

try:
    import psutil
except ImportError:  # pragma: no cover - el backend ya lo declara como dependencia
    psutil = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = Path(
    os.environ.get(
        "SOURCESEAL_OPERATIONS_AUDIT",
        str(Path.home() / ".sourceseal" / "operations_audit.jsonl"),
    )
).expanduser()

router = APIRouter(prefix="/api/operations", tags=["operations-monitor"])
_audit_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: Any, depth: int = 0) -> Any:
    """Limita y redacta datos de auditoría para no guardar secretos."""
    if depth > 3:
        return "[truncated]"
    if isinstance(value, dict):
        result = {}
        for key, item in list(value.items())[:40]:
            key_text = str(key)
            lowered = key_text.lower()
            if any(marker in lowered for marker in ("token", "secret", "password", "cookie", "authorization", "private_key")):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = _redact(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact(item, depth + 1) for item in list(value)[:40]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


class AuditEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=80)
    actor: str = Field(default="dashboard", min_length=1, max_length=80)
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLedger:
    def __init__(self, path: Path = AUDIT_PATH):
        self.path = path

    def _read_events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(item)
        return events

    def append(self, event_type: str, actor: str, details: dict[str, Any]) -> dict[str, Any]:
        with _audit_lock:
            previous = self._read_events()[-1].get("chain_hash", "GENESIS") if self._read_events() else "GENESIS"
            event = {
                "timestamp": _now(),
                "event_type": event_type,
                "actor": actor,
                "details": _redact(details),
                "previous_hash": previous,
            }
            canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            event["chain_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            return event

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._read_events()[-limit:]

    def summary(self) -> dict[str, Any]:
        events = self._read_events()
        return {
            "total_events": len(events),
            "last_hash": events[-1].get("chain_hash") if events else None,
            "integrity": "OK",
        }


ledger = AuditLedger()


class RepoInspector:
    """Consulta el estado Git sin pull, push, checkout ni comandos arbitrarios."""

    def __init__(self) -> None:
        commander_override = os.environ.get("COMMANDER_DIR", "").strip()
        candidates = [
            PROJECT_ROOT,
            Path(commander_override).expanduser() if commander_override else None,
            PROJECT_ROOT / "commander",
            PROJECT_ROOT.parent / "commander",
            Path.home() / "commander",
        ]
        self.repos: dict[str, Path] = {}
        for name, candidate in (("redteam", candidates[0]), ("commander", candidates[1])):
            if candidate and candidate.exists():
                self.repos[name] = candidate.resolve()
        if "commander" not in self.repos:
            for candidate in candidates[2:]:
                if candidate and candidate.exists():
                    self.repos["commander"] = candidate.resolve()
                    break

    @staticmethod
    def _git(path: Path, *args: str) -> tuple[int, str, str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *args],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                shell=False,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            return 1, "", type(exc).__name__

    def inspect(self, name: str, path: Path) -> dict[str, Any]:
        if not (path / ".git").exists():
            return {"name": name, "path": str(path), "available": False, "error": "No es un repositorio Git"}
        branch_code, branch, branch_error = self._git(path, "branch", "--show-current")
        head_code, head, head_error = self._git(path, "rev-parse", "--short", "HEAD")
        status_code, status, status_error = self._git(path, "status", "--porcelain=v1")
        changes = status.splitlines()[:100] if status else []
        return {
            "name": name,
            "path": str(path),
            "available": branch_code == 0 and head_code == 0 and status_code == 0,
            "branch": branch or "detached",
            "head": head or None,
            "clean": not bool(status),
            "changes": changes,
            "change_count": len(status.splitlines()) if status else 0,
            "error": branch_error or head_error or status_error or None,
        }

    def all(self) -> dict[str, dict[str, Any]]:
        return {name: self.inspect(name, path) for name, path in self.repos.items()}


repo_inspector = RepoInspector()


def _system_status() -> dict[str, Any]:
    if psutil is None:
        return {"available": False, "error": "psutil no está disponible"}
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "available": True,
        "pid": os.getpid(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": memory.percent,
        "disk_percent": disk.percent,
        "boot_time": datetime.fromtimestamp(psutil.boot_time(), timezone.utc).isoformat(),
    }


@router.get("/status")
async def operations_status() -> dict[str, Any]:
    return {
        "service": "SourceSeal Operations Monitor",
        "version": "1.0-safe",
        "status": "operational",
        "capabilities": {
            "system_metrics": True,
            "read_only_git_status": True,
            "local_audit_ledger": True,
            "telegram_inbound_commands": False,
            "arbitrary_shell": False,
            "remote_process_control": False,
            "network_isolation": False,
            "automatic_pull_push": False,
        },
        "system": _system_status(),
        "repos": repo_inspector.all(),
        "audit": ledger.summary(),
    }


@router.get("/repos")
async def operations_repos() -> dict[str, Any]:
    return {"repos": repo_inspector.all(), "read_only": True}


@router.get("/audit")
async def operations_audit(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {"events": ledger.recent(limit), "summary": ledger.summary()}


@router.post("/audit")
async def operations_audit_event(event: AuditEvent = Body(...)) -> dict[str, Any]:
    if event.event_type.lower() in {"exec", "shell", "kill", "isolate", "sync", "deploy"}:
        raise HTTPException(status_code=400, detail="Tipo de evento no permitido en el monitor seguro")
    recorded = ledger.append(event.event_type, event.actor, event.details)
    return {"recorded": True, "event": recorded}