#!/usr/bin/env python3
"""Shared credential loading for the Nexus Omni service and its proxy.

The project deliberately avoids a dotenv dependency here because Nexus is also
started as a standalone Python process.  Both processes must resolve the same
credentials from the same file and environment.
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


def ensure_nexus_credentials(*, reset: bool = False, announce: bool = True) -> NexusCredentials:
    """Resolve credentials and create a protected local .env when needed.

    Normal resolution follows environment > .env > generated value.  An
    explicit reset intentionally replaces the effective password for the
    current process and persists it to .env so the next process uses it too.
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
        generated = False
        if not password:
            password = secrets.token_urlsafe(48)
            _write_env_values(ENV_PATH, {"NEXUS_USER": user, "NEXUS_PASS": password})
            generated = True
        elif ENV_PATH.exists():
            # A pre-existing file must never remain world-readable.
            os.chmod(ENV_PATH, 0o600)

    if generated and announce:
        print(f"[NEXUS] Credenciales generadas y guardadas en {ENV_PATH}", flush=True)
        print(f"[NEXUS] NEXUS_USER={user}", flush=True)
        print(f"[NEXUS] NEXUS_PASS={password}", flush=True)

    return NexusCredentials(user=user, password=password, env_path=ENV_PATH, generated=generated)