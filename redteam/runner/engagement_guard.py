"""Validación fail-closed del alcance autorizado de un engagement."""

from __future__ import annotations

import ipaddress
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redteam.monitor.operations_monitor import ledger


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGAGEMENTS_FILE = Path(
    os.environ.get("SOURCESEAL_ENGAGEMENTS_FILE", str(PROJECT_ROOT / "config" / "engagements.json"))
).expanduser()


def _load_engagements() -> list[dict[str, Any]]:
    try:
        data = json.loads(ENGAGEMENTS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    engagements = data.get("engagements", []) if isinstance(data, dict) else []
    return [item for item in engagements if isinstance(item, dict)]


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def _matches(target: str, scope_entry: str) -> bool:
    target = target.strip().lower().rstrip(".")
    scope_entry = scope_entry.strip().lower().rstrip(".")
    if not target or not scope_entry:
        return False

    try:
        target_ip = ipaddress.ip_address(target)
        if "/" in scope_entry:
            return target_ip in ipaddress.ip_network(scope_entry, strict=False)
        return target_ip == ipaddress.ip_address(scope_entry)
    except ValueError:
        pass

    if "/" in scope_entry:
        return False
    if scope_entry.startswith("*."):
        suffix = scope_entry[1:]
        return target.endswith(suffix) and target != suffix[1:]
    return bool(re.fullmatch(re.escape(scope_entry), target))


def is_target_authorized(target: str, engagement_id: str | None = None) -> bool:
    """Devuelve False ante cualquier configuración ausente o inválida."""
    now = datetime.now(timezone.utc)
    for engagement in _load_engagements():
        if engagement_id and engagement.get("id") != engagement_id:
            continue
        start = _parse_date(engagement.get("start_date"))
        end = _parse_date(engagement.get("end_date"))
        if not start or not end or not (start <= now <= end):
            continue
        if engagement.get("authorization_signed") is not True:
            continue
        if any(_matches(target, item) for item in engagement.get("excluded", []) if isinstance(item, str)):
            decision = False
        else:
            decision = any(
                _matches(target, item)
                for item in engagement.get("scope", [])
                if isinstance(item, str)
            )
        ledger.append(
            "authorization_check",
            "engagement-guard",
            {"engagement_id": engagement.get("id", ""), "target": target, "allowed": decision},
        )
        return decision

    ledger.append(
        "authorization_check",
        "engagement-guard",
        {"engagement_id": engagement_id or "", "target": target, "allowed": False},
    )
    return False


def require_authorization(target: str, engagement_id: str) -> bool:
    if not is_target_authorized(target, engagement_id):
        raise PermissionError(f"Target fuera del alcance autorizado: {target}")
    return True


def get_active_engagement(engagement_id: str) -> dict[str, Any] | None:
    for engagement in _load_engagements():
        if engagement.get("id") == engagement_id:
            return engagement
    return None