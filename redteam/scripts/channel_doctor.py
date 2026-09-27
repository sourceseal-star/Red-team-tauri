#!/usr/bin/env python3
"""Diagnóstico explícito de los canales COM-LINK.

Este módulo no transmite mensajes ni inventa disponibilidad. Las probes de
estado son de solo lectura; /wake solo ejecuta termux-wifi-enable cuando el
operador lo solicita explícitamente.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body


router = APIRouter(prefix="/api/doctor", tags=["channel-doctor"])

CHANNELS = (
    "sms",
    "telegram",
    "voip",
    "mesh_wifi",
    "mesh_bluetooth",
    "radio",
    "satellite",
)

_commander_dir: Path | None = None


def configure_commander_dir(path: str | Path | None) -> None:
    """Usa el commander que ya resolvió el dashboard unificado."""
    global _commander_dir
    _commander_dir = Path(path).expanduser() if path else None


def _resolve_commander_dir() -> Path:
    if _commander_dir:
        return _commander_dir
    configured = os.environ.get("COMMANDER_DIR")
    if configured:
        return Path(configured).expanduser()
    # channel_doctor.py vive en redteam/scripts/.
    return Path(__file__).resolve().parents[2] / "commander"


def _config() -> dict[str, Any]:
    path = _resolve_commander_dir() / "comlink" / "data" / "config.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _command(name: str) -> str | None:
    return shutil.which(name)


def _run(command: list[str], timeout: float = 5) -> dict[str, Any]:
    if not command or not _command(command[0]):
        return {
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{command[0] if command else 'comando'} no disponible",
        }
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "available": True,
            "returncode": result.returncode,
            "stdout": (result.stdout or "").strip()[-1200:],
            "stderr": (result.stderr or "").strip()[-600:],
        }
    except subprocess.TimeoutExpired:
        return {
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": "timeout",
        }
    except OSError as exc:
        return {
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }


def _result(
    channel: str,
    verdict: str,
    ready: bool,
    reason: str,
    requires: list[str],
    *,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": channel,
        "ready": ready,
        "verdict": verdict,
        "reason": reason,
        "requires": requires,
        "evidence": evidence or {},
    }


def _probe_sms() -> dict[str, Any]:
    send_available = _command("termux-sms-send") is not None
    listing = _run(["termux-sms-list", "-l", "1"], timeout=6)
    if not send_available:
        return _result(
            "sms",
            "wakeable",
            False,
            "Falta termux-sms-send; instala Termux:API y concede SMS.",
            ["Termux:API", "permiso SMS", "SIM/cobertura"],
            evidence={"send_command": False, "list_command": listing["available"]},
        )
    if listing["available"] and listing["returncode"] == 0:
        return _result(
            "sms",
            "ready",
            True,
            "Termux:API responde a una lectura de SMS.",
            ["SIM/cobertura"],
            evidence={"send_command": True, "list_probe": "ok"},
        )
    return _result(
        "sms",
        "wakeable",
        False,
        "Termux:API está instalado, pero sms-list no responde; revisa permisos y app SMS predeterminada.",
        ["permiso SMS", "Termux:API como app SMS predeterminada", "SIM/cobertura"],
        evidence={"send_command": True, "list_probe": listing["stderr"] or "falló"},
    )


def _probe_voip() -> dict[str, Any]:
    call_available = _command("termux-telephony-call") is not None
    info = _run(["termux-telephony-deviceinfo"], timeout=6)
    if not call_available:
        return _result(
            "voip",
            "wakeable",
            False,
            "Falta termux-telephony-call; instala Termux:API y concede teléfono.",
            ["Termux:API", "permiso teléfono", "cobertura"],
            evidence={"call_command": False},
        )
    if info["available"] and info["returncode"] == 0:
        return _result(
            "voip",
            "ready",
            True,
            "Termux:API responde al estado de telefonía.",
            ["cobertura"],
            evidence={"call_command": True, "device_probe": "ok"},
        )
    return _result(
        "voip",
        "wakeable",
        False,
        "El comando de llamadas existe, pero el estado de telefonía no responde.",
        ["permiso teléfono", "cobertura"],
        evidence={"call_command": True, "device_probe": info["stderr"] or "falló"},
    )


def _wifi_info() -> tuple[dict[str, Any] | None, dict[str, Any]]:
    probe = _run(["termux-wifi-connectioninfo"], timeout=6)
    if not probe["available"] or probe["returncode"] != 0:
        return None, probe
    try:
        value = json.loads(probe["stdout"])
        return value if isinstance(value, dict) else None, probe
    except json.JSONDecodeError:
        return None, probe


def _probe_wifi() -> dict[str, Any]:
    info, probe = _wifi_info()
    if not probe["available"]:
        return _result(
            "mesh_wifi",
            "wakeable",
            False,
            "Falta termux-wifi-connectioninfo; instala Termux:API.",
            ["Termux:API", "Wi‑Fi conectado", "peer COM-LINK"],
        )
    if info:
        state = str(info.get("state", "")).upper()
        ssid = str(info.get("ssid", "")).strip()
        if state in {"CONNECTED", "CONNECTING"} or ssid:
            return _result(
                "mesh_wifi",
                "ready",
                True,
                "Wi‑Fi conectado; el doctor no confirma que exista un peer.",
                ["peer COM-LINK"],
                evidence={
                    "state": state or "unknown",
                    "ssid_present": bool(ssid),
                    "ip": info.get("ip"),
                },
            )
        return _result(
            "mesh_wifi",
            "wakeable",
            False,
            "Wi‑Fi disponible pero no está conectado.",
            ["red Wi‑Fi", "peer COM-LINK"],
            evidence={"state": state or "disconnected"},
        )
    return _result(
        "mesh_wifi",
        "wakeable",
        False,
        "Termux:API no devolvió información válida de Wi‑Fi.",
        ["permiso ubicación", "Termux:API", "Wi‑Fi conectado"],
        evidence={"probe": probe["stderr"] or "respuesta inválida"},
    )


def _internet_available() -> bool:
    try:
        with socket.create_connection(("api.telegram.org", 443), timeout=2):
            return True
    except OSError:
        return False


def _probe_telegram(config: dict[str, Any]) -> dict[str, Any]:
    telegram = config.get("telegram", {})
    if not isinstance(telegram, dict):
        telegram = {}
    has_token = bool(str(telegram.get("bot_token", "")).strip())
    has_chat = bool(str(telegram.get("default_chat_id", "")).strip())
    online = _internet_available()
    if has_token and has_chat and online:
        return _result(
            "telegram",
            "ready",
            True,
            "Configuración presente y salida a api.telegram.org disponible.",
            [],
            evidence={"token_configured": True, "chat_configured": True, "internet": True},
        )
    missing = []
    if not has_token:
        missing.append("bot_token")
    if not has_chat:
        missing.append("default_chat_id")
    if not online:
        missing.append("internet")
    return _result(
        "telegram",
        "wakeable",
        False,
        "Telegram es software; falta configurar " + ", ".join(missing) + ".",
        ["bot_token", "default_chat_id", "internet"],
        evidence={
            "token_configured": has_token,
            "chat_configured": has_chat,
            "internet": online,
        },
    )


def _probe_bluetooth() -> dict[str, Any]:
    hcitool = _run(["hcitool", "dev"], timeout=4)
    api_scan = _command("termux-bluetooth-scaninfo") is not None
    if hcitool["available"] and hcitool["returncode"] == 0 and "hci" in hcitool["stdout"].lower():
        return _result(
            "mesh_bluetooth",
            "partial",
            False,
            "Hay un adaptador Bluetooth visible, pero no se verificó un peer COM-LINK.",
            ["peer compatible", "puente Bluetooth para discovery"],
            evidence={"hcitool": "adapter-visible", "termux_scan_api": api_scan},
        )
    return _result(
        "mesh_bluetooth",
        "partial",
        False,
        "Android no expone un adaptador Bluetooth utilizable a este proceso.",
        ["app puente Bluetooth o root", "peer compatible"],
        evidence={"hcitool": hcitool["stderr"] or "no adapter", "termux_scan_api": api_scan},
    )


def _probe_radio(config: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(config.get("radio", {}).get("enabled")) if isinstance(config.get("radio"), dict) else False
    if _command("termux-fm"):
        return _result(
            "radio",
            "partial",
            False,
            "termux-fm existe, pero no confirma transmisión ni un módem AX.25/TNC.",
            ["hardware de radio compatible", "driver AX.25/TNC"],
            evidence={"termux_fm": True, "configured": enabled},
        )
    return _result(
        "radio",
        "hardware_unavailable",
        False,
        "No hay termux-fm ni un driver TNC/AX.25 disponible.",
        ["hardware de radio", "driver AX.25/TNC"],
        evidence={"termux_fm": False, "configured": enabled},
    )


def _probe_satellite(config: dict[str, Any]) -> dict[str, Any]:
    satellite = config.get("satellite", {})
    configured = isinstance(satellite, dict) and bool(str(satellite.get("device", "")).strip())
    return _result(
        "satellite",
        "hardware_unavailable",
        False,
        "No existe un driver satelital genérico; hace falta un módem externo compatible.",
        ["módem satelital", "proveedor", "driver específico"],
        evidence={"device_configured": configured},
    )


def build_report() -> dict[str, Any]:
    config = _config()
    channels = {
        "sms": _probe_sms(),
        "telegram": _probe_telegram(config),
        "voip": _probe_voip(),
        "mesh_wifi": _probe_wifi(),
        "mesh_bluetooth": _probe_bluetooth(),
        "radio": _probe_radio(config),
        "satellite": _probe_satellite(config),
    }
    ready = [name for name, item in channels.items() if item["ready"]]
    wakeable = [name for name, item in channels.items() if item["verdict"] == "wakeable"]
    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ready_count": len(ready),
        "ready_channels": ready,
        "wakeable_channels": wakeable,
        "channels": channels,
        "environment": "termux" if os.environ.get("PREFIX", "").startswith("/data/data/com.termux") else "other",
        "safe_to_transmit": bool(ready),
        "note": "Diagnóstico real; no se enviaron mensajes ni se verificó entrega a peers.",
    }


@router.get("/status")
async def doctor_status():
    return build_report()


@router.get("/report")
async def doctor_report():
    return build_report()


@router.post("/wake")
async def doctor_wake(payload: dict[str, Any] = Body(default={})):
    """Ejecuta solo reactivaciones explícitas y no transmisivas."""
    requested = payload.get("channels")
    if requested is None:
        requested = ["mesh_wifi"]
    if not isinstance(requested, list):
        return {"ok": False, "error": "channels debe ser una lista"}

    actions = []
    if "mesh_wifi" in requested and payload.get("enable_wifi", True) is True:
        result = _run(["termux-wifi-enable", "true"], timeout=8)
        actions.append({
            "channel": "mesh_wifi",
            "action": "termux-wifi-enable true",
            "ok": result["available"] and result["returncode"] == 0,
            "detail": result["stderr"] or result["stdout"] or "sin salida",
        })
    for channel in requested:
        if channel == "telegram":
            actions.append({
                "channel": channel,
                "action": "config-check",
                "ok": False,
                "detail": "No se escribe ni se solicita ningún token desde el doctor.",
            })
        elif channel in {"sms", "voip", "mesh_bluetooth", "radio", "satellite"}:
            actions.append({
                "channel": channel,
                "action": "no-op-safe",
                "ok": False,
                "detail": "Requiere permiso, puente o hardware; no se fuerza desde el dashboard.",
            })

    return {
        "ok": any(item["ok"] for item in actions),
        "actions": actions,
        "report": build_report(),
        "note": "Wake no transmite mensajes ni inicia un SOS.",
    }