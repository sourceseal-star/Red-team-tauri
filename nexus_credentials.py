#!/usr/bin/env python3
"""Shared credential loading for the Nexus Omni service and its proxy.

The project deliberately avoids a dotenv dependency here because Nexus is also
started as a standalone Python process.  Both processes must resolve the same
credentials from the same file and environment.

AUTHORITY RULE (permanent):
  .env is the single source of truth for credentials.
  If a value exists in .env or the environment, it is USED — never regenerated,
  never overwritten, never printed to stdout.
  Recovery is always the protected .env file (chmod 600), not console output.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = Path(os.environ.get("NEXUS_ENV_FILE", PROJECT_ROOT / ".env")).expanduser()
DEFAULT_USER = "admin"


@dataclass(frozen=True)
class NexusCredentials:
    user: str
    password: str
    env_path: Path
    generated: bool = False


def _parse_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    key, separator, value = stripped.partition("=")
    if not separator:
        return None
    key = key.strip()
    if not key or not (key[0].isalpha() or key[0] == "_"):
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        return {
            key: value
            for line in path.read_text(encoding="utf-8").splitlines()
            if (parsed := _parse_line(line)) is not None
            for key, value in (parsed,)
        }
    except OSError as exc:
        raise RuntimeError(f"No se pudo leer el archivo de credenciales: {path}") from exc


def _write_env_values(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        original = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        seen: set[str] = set()
        output: list[str] = []
        for line in original:
            parsed = _parse_line(line)
            if parsed and parsed[0] in updates:
                key = parsed[0]
                output.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                output.append(line)
        for key, value in updates.items():
            if key not in seen:
                if output and output[-1] != "":
                    output.append("")
                output.append(f"{key}={value}")

        content = "\n".join(output).rstrip("\n") + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".env.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        raise RuntimeError(f"No se pudo proteger o actualizar {path}") from exc


def update_project_env(values: dict[str, str]) -> None:
    """Persist non-empty managed values without exposing them to callers."""
    _write_env_values(ENV_PATH, values)


def resolve_project_value(name: str, default: str = "") -> str:
    """Resolve one value using environment > local .env > default."""
    file_values = _read_env_file(ENV_PATH)
    return os.environ.get(name, "").strip() or file_values.get(name, "").strip() or default


def ensure_managed_secret(
    name: str,
    *,
    announce: bool = False,
    reset: bool = False,
) -> str:
    """Resolve or generate a project secret and make it available to children.

    AUTHORITY: If the value exists in .env or the environment, it is used
    as-is.  It is never regenerated, never overwritten, and never printed
    to stdout.  Recovery is always the protected .env file.
    Only when the value is truly absent does this function generate one.
    """
    file_values = _read_env_file(ENV_PATH)

    if reset:
        value = secrets.token_urlsafe(48)
        _write_env_values(ENV_PATH, {name: value})
        os.environ[name] = value
        return value

    value = os.environ.get(name, "").strip() or file_values.get(name, "").strip()
    if not value:
        value = secrets.token_urlsafe(48)
        _write_env_values(ENV_PATH, {name: value})

    os.environ[name] = value

    if ENV_PATH.exists():
        os.chmod(ENV_PATH, 0o600)

    return value


def ensure_nexus_credentials(*, reset: bool = False, announce: bool = False) -> NexusCredentials:
    """Resolve Nexus credentials from .env (the single source of truth).

    AUTHORITY: If NEXUS_USER and NEXUS_PASS exist in .env or the environment,
    they are used as-is.  They are never regenerated, never overwritten, and
    never printed to stdout.  Recovery is always the protected .env file.
    Only when NEXUS_PASS is truly absent does this function generate one.
    """
    file_values = _read_env_file(ENV_PATH)
    user = (
        os.environ.get("NEXUS_USER", "").strip()
        or file_values.get("NEXUS_USER", "").strip()
        or DEFAULT_USER
    )

    if reset:
        password = secrets.token_urlsafe(48)
        _write_env_values(ENV_PATH, {"NEXUS_USER": user, "NEXUS_PASS": password})
        os.environ["NEXUS_PASS"] = password
        generated = True
    else:
        password = os.environ.get("NEXUS_PASS", "").strip() or file_values.get("NEXUS_PASS", "").strip()
        if not password:
            password = secrets.token_urlsafe(48)
            _write_env_values(ENV_PATH, {"NEXUS_USER": user, "NEXUS_PASS": password})
            generated = True
        else:
            generated = False

    if ENV_PATH.exists():
        os.chmod(ENV_PATH, 0o600)

    os.environ["NEXUS_USER"] = user
    os.environ["NEXUS_PASS"] = password

    return NexusCredentials(user=user, password=password, env_path=ENV_PATH, generated=generated)
