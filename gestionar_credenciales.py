#!/usr/bin/env python3
"""Operator-only credential status, recovery and rotation helper."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from nexus_credentials import (
    ENV_PATH,
    ensure_managed_secret,
    ensure_nexus_credentials,
    resolve_project_value,
)


MANAGED_SECRETS = (
    "NEXUS_USER",
    "NEXUS_PASS",
    "REDTEAM_API_KEY",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "C2_API_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SHODAN_API_KEY",
    "ABUSEIPDB_KEY",
    "HUNTER_API_KEY",
    "VIRUSTOTAL_API_KEY",
    "CENSYS_API_ID",
    "CENSYS_API_SECRET",
    "GOOGLE_API_KEY",
    "GOOGLE_CSE_ID",
    "GITHUB_TOKEN",
    "CORSET_SCOPE_B64",
    "ORCHESTRATOR_KEY",
    "NODE_MOTOR_KEY",
    "NODE_INTEL_KEY",
    "REDIS_URL",
)


def _file_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def show_status() -> None:
    values = _file_values()
    print(f"Archivo local: {ENV_PATH}")
    print(f"Permisos: {oct(ENV_PATH.stat().st_mode & 0o777) if ENV_PATH.exists() else 'no existe'}")
    for name in MANAGED_SECRETS:
        source = "entorno" if os.environ.get(name) else ("archivo .env" if values.get(name) else "no configurado")
        print(f"{name}: {source}")


def show_values() -> None:
    """Explicit local recovery; never call this from application startup."""
    credentials = {
        "NEXUS_USER": resolve_project_value("NEXUS_USER", "admin"),
        "NEXUS_PASS": resolve_project_value("NEXUS_PASS"),
        "REDTEAM_API_KEY": resolve_project_value("REDTEAM_API_KEY"),
        "ADMIN_EMAIL": resolve_project_value("ADMIN_EMAIL", "admin@redteam.local"),
        "ADMIN_PASSWORD": resolve_project_value("ADMIN_PASSWORD"),
    }
    print(f"# Recuperación local desde {ENV_PATH}")
    for name, value in credentials.items():
        print(f"{name}={value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestiona credenciales del sistema SourceSeal")
    parser.add_argument("--status", action="store_true", help="muestra nombres, origen y permisos sin valores")
    parser.add_argument("--show", action="store_true", help="muestra las credenciales internas al operador local")
    parser.add_argument("--generate-missing", action="store_true", help="genera Nexus y dashboard si faltan")
    parser.add_argument("--reset-nexus", action="store_true", help="rota NEXUS_PASS")
    parser.add_argument("--reset-dashboard", action="store_true", help="rota REDTEAM_API_KEY y ADMIN_PASSWORD")
    args = parser.parse_args()

    if args.reset_nexus:
        ensure_nexus_credentials(reset=True)
        print("[SECRETS] Reinicia el dashboard para que la nueva credencial sea efectiva.")
    if args.reset_dashboard:
        ensure_managed_secret("REDTEAM_API_KEY", reset=True)
        ensure_managed_secret("ADMIN_PASSWORD", reset=True)
        print("[SECRETS] Reinicia el dashboard para que las nuevas credenciales sean efectivas.")
    if args.generate_missing:
        ensure_nexus_credentials()
        ensure_managed_secret("REDTEAM_API_KEY")
        ensure_managed_secret("ADMIN_PASSWORD")
    if args.status or not any((args.show, args.generate_missing, args.reset_nexus, args.reset_dashboard)):
        show_status()
    if args.show:
        show_values()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())