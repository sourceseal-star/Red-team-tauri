#!/usr/bin/env python3
"""auth_bootstrap.py — Sincroniza el hash de password.json desde .env.

AUTHORITY: .env es la única fuente de verdad para ADMIN_PASSWORD.
Si redteam/scripts/.auth/password.json no existe pero ADMIN_PASSWORD
está en .env, este script crea el hash desde .env — nunca genera
una contraseña nueva.

Uso:
  python3 auth_bootstrap.py            # silencioso
  python3 auth_bootstrap.py --verbose  # muestra qué hizo
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = Path(os.environ.get("NEXUS_ENV_FILE", PROJECT_ROOT / ".env")).expanduser()
AUTH_DIR = PROJECT_ROOT / "redteam" / "scripts" / ".auth"
PASS_FILE = AUTH_DIR / "password.json"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[7:].lstrip()
    key, sep, value = stripped.partition("=")
    if not sep:
        return None
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value if key else None


def _read_env() -> dict[str, str]:
    if not ENV_PATH.is_file():
        return {}
    result: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed:
            result[parsed[0]] = parsed[1]
    return result


def _rehash_from_env(verbose: bool = False) -> bool:
    """Create password.json from ADMIN_PASSWORD in .env if it's missing.

    Returns True if a hash was created, False if nothing changed.
    Never prints the password value.
    """
    if PASS_FILE.exists():
        if verbose:
            print("[auth_bootstrap] password.json ya existe — nada que hacer.")
        return False

    env_values = _read_env()
    admin_password = env_values.get("ADMIN_PASSWORD", "").strip()
    if not admin_password:
        if verbose:
            print("[auth_bootstrap] ADMIN_PASSWORD no está en .env — nada que hacer.")
        return False

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(AUTH_DIR, 0o700)
    except OSError:
        pass

    salt = os.urandom(16)
    iterations = 310000
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", admin_password.encode("utf-8"), salt, iterations
    ).hex()

    with open(PASS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "algorithm": "pbkdf2-sha256",
            "iterations": iterations,
            "salt": salt.hex(),
            "password_hash": password_hash,
            "changed": time.time(),
            "source": "env-bootstrap",
        }, f)
    try:
        os.chmod(PASS_FILE, 0o600)
    except OSError:
        pass

    if verbose:
        print("[auth_bootstrap] Hash creado desde ADMIN_PASSWORD de .env (valor no revelado).")
    return True


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv[1:]
    _rehash_from_env(verbose=verbose)
