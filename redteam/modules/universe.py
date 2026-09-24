"""
Módulo Master: Universe.

Orquestador liviano para SOL SuperGate en userland de Termux. Este módulo no
abre sockets de escaneo, no ejecuta comandos y no requiere privilegios de root;
solo expone estado y deja preparada la sincronización controlada.
"""

from __future__ import annotations

import datetime
import logging
import socket
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/universe", tags=["Universe Core"])

universe_state: dict[str, Any] = {
    "status": "operational",
    "mode": "protected",
    "interface_active": None,
    "last_synchronization": None,
    "nodes_tracked": None,
}


class UniverseCommand(BaseModel):
    action: str = Field(..., min_length=1, max_length=64)
    # Vacío significa autodetección; conserva compatibilidad con un CIDR
    # explícito sin volver a fijar la operación a 192.168.1.0/24.
    target_subnet: str = Field("", max_length=256)


def _inspect_userland_net() -> dict[str, Any]:
    """Inspecciona el contexto local sin comandos, sockets de escaneo ni root."""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return {
            "hostname": hostname,
            "local_ip": local_ip,
            "stack": "IPv4 / UDP-TCP",
            "privilege": "userland (no-root)",
            "source": "hostname resolution (no interface scan)",
        }
    except Exception as exc:
        return {
            "hostname": "termux-node",
            "local_ip": "127.0.0.1",
            "stack": "IPv4 / UDP-TCP",
            "privilege": "userland (no-root)",
            "source": "fallback",
            "error": str(exc),
        }


@router.get("/status")
async def get_universe_status() -> dict[str, Any]:
    """Retorna el estado consolidado del ecosistema SOL SuperGate."""
    net_info = _inspect_userland_net()
    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "module": "universe.py",
        "state": dict(universe_state),
        "network_context": net_info,
        "observed_at": observed_at,
    }


@router.post("/sync")
async def trigger_universe_sync(
    payload: UniverseCommand,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Programa una sincronización declarativa y controlada en segundo plano."""
    valid_actions = {"topology_scan", "mesh_sync", "purge_sockets"}
    if payload.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Acción inválida. Acciones permitidas: {sorted(valid_actions)}",
        )

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    universe_state["last_synchronization"] = timestamp
    action = payload.action
    target_subnet = payload.target_subnet

    def background_sync_task() -> None:
        logging.info(
            "[UNIVERSE] Sincronización declarativa: %s sobre %s",
            action,
            target_subnet or "interfaces LAN autodetectadas",
        )

    background_tasks.add_task(background_sync_task)
    return {
        "status": "success",
        "action": action,
        "subnet": target_subnet,
        "timestamp": timestamp,
    }