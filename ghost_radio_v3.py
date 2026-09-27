#!/usr/bin/env python3
"""Ghost Radio v3 — diagnóstico y reconocimiento autorizado, sin transmisión.

Este módulo reúne las capacidades que ya existen en SourceSeal:

* ``doctor`` consulta el diagnóstico local de COM-LINK sin activar hardware.
* ``scan`` usa ``/api/network/radio`` para comprobar puertos de streaming en
  un objetivo autorizado, con confirmación explícita de alcance.

No implementa TX, AX.25, TNC, SDR ni escritura en puertos serie. Un sistema
que no puede demostrar su driver no debe anunciar que transmitió.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
DEFAULT_BACKEND = os.environ.get("GHOST_RADIO_BACKEND", "http://127.0.0.1:8001")
API_KEY = os.environ.get("GHOST_RADIO_API_KEY") or os.environ.get("REDTEAM_API_KEY", "")
TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,253}$")


def _json_output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _load_doctor() -> Any:
    candidates = [
        ROOT / "redteam" / "scripts",
        Path(os.environ["GHOST_RADIO_LIB_DIR"]).expanduser()
        if os.environ.get("GHOST_RADIO_LIB_DIR")
        else ROOT / ".." / "share" / "ghost-radio",
    ]
    scripts = next((path.resolve() for path in candidates if (path / "channel_doctor.py").is_file()), None)
    if scripts is None:
        raise RuntimeError("No existe el diagnóstico COM-LINK junto a Ghost Radio")
    sys.path.insert(0, str(scripts))
    try:
        from channel_doctor import build_report
    except Exception as exc:  # pragma: no cover - depends on runtime packages
        raise RuntimeError(f"No se pudo cargar channel_doctor: {exc}") from exc
    return build_report


def doctor() -> dict[str, Any]:
    report = _load_doctor()()
    report.update(
        {
            "service": "ghost_radio_v3",
            "mode": "diagnostic",
            "read_only": True,
            "transmission_supported": False,
        }
    )
    return report


def _validate_target(target: str) -> str:
    target = target.strip()
    if not target or not TARGET_RE.fullmatch(target):
        raise ValueError("target debe ser un hostname o una IP simple")
    try:
        ipaddress.ip_address(target)
    except ValueError:
        # Hostnames are accepted for the existing backend probe. URL syntax,
        # paths, spaces and shell metacharacters are not.
        if target.startswith(".") or target.endswith(".") or ".." in target:
            raise ValueError("target no es un hostname válido")
    return target


def scan(target: str, backend: str, timeout: int) -> dict[str, Any]:
    target = _validate_target(target)
    parsed = urlparse(backend)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("backend debe ser una URL HTTP(S)")
    query = urlencode({"target": target, "timeout": timeout})
    url = f"{backend.rstrip('/')}/api/network/radio?{query}"
    headers = {"Accept": "application/json", "User-Agent": "ghost-radio-v3/1.0"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=max(timeout + 3, 5)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError(
                f"backend rechazó la autenticación (HTTP {exc.code}); "
                "configura GHOST_RADIO_API_KEY o REDTEAM_API_KEY"
            ) from exc
        raise RuntimeError(f"backend respondió HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"backend no disponible: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("backend devolvió una respuesta no JSON") from exc

    return {
        "service": "ghost_radio_v3",
        "mode": "authorized_stream_probe",
        "read_only": True,
        "transmission_supported": False,
        "scope_confirmed": True,
        "backend": backend,
        "result": payload,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ghost Radio v3: diagnóstico seguro y probe autorizado"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor_parser = sub.add_parser("doctor", help="diagnóstico local COM-LINK")
    doctor_parser.add_argument("--json", action="store_true", help="salida JSON")

    scan_parser = sub.add_parser("scan", help="probe de streams en un objetivo autorizado")
    scan_parser.add_argument("--target", required=True, help="IP o hostname bajo tu control")
    scan_parser.add_argument(
        "--confirm-scope",
        action="store_true",
        help="confirma que el objetivo está dentro del alcance autorizado",
    )
    scan_parser.add_argument("--backend", default=DEFAULT_BACKEND)
    scan_parser.add_argument("--timeout", type=int, choices=range(1, 16), default=5)
    scan_parser.add_argument("--json", action="store_true", help="salida JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            value = doctor()
            if args.json:
                _json_output(value)
            else:
                print(
                    f"Ghost Radio v3 · {value['ready_count']}/{len(value['channels'])} "
                    f"canales listos · transmisión: bloqueada"
                )
                print(value["note"])
            return 0

        if not args.confirm_scope:
            raise ValueError("scan requiere --confirm-scope")
        value = scan(args.target, args.backend, args.timeout)
        if args.json:
            _json_output(value)
        else:
            result = value["result"]
            print(
                f"Probe autorizado de {result.get('target', args.target)}: "
                f"{result.get('total', 0)} stream(s) detectado(s)"
            )
            print("Solo lectura; no se transmitió nada.")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"ghost-radio: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())