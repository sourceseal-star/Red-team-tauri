"""Integraciones locales de Android para SourceSeal.

No usa shell para entradas del usuario. Las acciones de red son TCP connect,
requieren confirmación explícita y tienen límites para que el operador conserve
el control del alcance.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import ipaddress
import json
import os
import shutil
import subprocess
import urllib.parse
from typing import Callable, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/android", tags=["Android / Campo"])
_scope_provider: Callable[[], dict] = lambda: {
    "active": False,
    "configured": False,
    "note": "Corset no está configurado en este proceso",
}

SERVICE_NAMES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 139: "NetBIOS", 143: "IMAP",
    443: "HTTPS", 445: "SMB", 554: "RTSP", 631: "IPP",
    1883: "MQTT", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 8000: "HTTP-alt", 8080: "HTTP-alt", 8443: "HTTPS-alt",
    8554: "RTSP-alt", 9000: "Web-alt", 37777: "DVR-Hikvision",
    34567: "DVR-Dahua",
}


def configure_scope(provider: Callable[[], dict]) -> None:
    global _scope_provider
    _scope_provider = provider


def _is_termux() -> bool:
    return (
        os.environ.get("PREFIX", "").startswith("/data/data/com.termux")
        or os.path.exists("/data/data/com.termux")
    )


def _available(command: str) -> bool:
    return shutil.which(command) is not None


def _run_json(command: str, args: Optional[list] = None, timeout: int = 15):
    if not _available(command):
        return False, f"{command} no está instalado"
    try:
        result = subprocess.run(
            [command, *(args or [])],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout or "").strip()
        if result.returncode != 0:
            return False, (result.stderr or output or f"código {result.returncode}").strip()
        try:
            return True, json.loads(output) if output else {}
        except json.JSONDecodeError:
            return True, output
    except subprocess.TimeoutExpired:
        return False, f"{command} excedió {timeout}s"
    except Exception as exc:
        return False, str(exc)


def _package_installed(packages: list[str]) -> Optional[str]:
    for package in packages:
        for command, args in (
            ("cmd", ["package", "path", package]),
            ("pm", ["path", package]),
        ):
            if not _available(command):
                continue
            try:
                result = subprocess.run(
                    [command, *args],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0 and "package:" in (result.stdout or ""):
                    return package
            except Exception:
                pass
    return None


def _interfaces() -> list[dict]:
    if not _available("ip"):
        return []
    try:
        result = subprocess.run(
            ["ip", "-o", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    found = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[2] != "inet":
            continue
        name, cidr = parts[1], parts[3]
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        if name == "lo":
            kind = "loopback"
        elif name.startswith(("wlan", "wifi")):
            kind = "wifi"
        elif name.startswith(("ap", "softap")):
            kind = "hotspot"
        elif name.startswith(("rmnet", "ccmni")):
            kind = "mobile"
        elif name.startswith(("eth", "en")):
            kind = "ethernet"
        else:
            kind = "other"
        found.append({
            "name": name,
            "ip_address": cidr.split("/", 1)[0],
            "network_cidr": str(network),
            "type_hint": kind,
        })
    return found


def _parse_ports(value) -> list[int]:
    values = value if isinstance(value, list) else str(value or "").replace(";", ",").split(",")
    ports = set()
    for raw in values:
        item = str(raw).strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError:
                raise ValueError(f"puerto inválido: {item}")
            if end < start or end - start > 31:
                raise ValueError("cada rango puede contener como máximo 32 puertos")
            ports.update(range(start, end + 1))
        else:
            try:
                ports.add(int(item))
            except ValueError:
                raise ValueError(f"puerto inválido: {item}")
    if not ports:
        ports = {22, 53, 80, 443, 554, 8000, 8080, 8443}
    if any(port < 1 or port > 65535 for port in ports):
        raise ValueError("los puertos deben estar entre 1 y 65535")
    if len(ports) > 32:
        raise ValueError("máximo 32 puertos por escaneo manual")
    return sorted(ports)


@router.get("/status")
async def android_status():
    return {
        "platform": "termux" if _is_termux() else "server",
        "termux_api": {
            "location": _available("termux-location"),
            "wifi_connection": _available("termux-wifi-connectioninfo"),
            "wifi_scan": _available("termux-wifi-scaninfo"),
            "open_url": _available("termux-open-url"),
        },
        "osmand_package": await asyncio.to_thread(
            _package_installed, ["net.osmand", "net.osmand.plus"]
        ),
        "netguard_package": await asyncio.to_thread(
            _package_installed, ["eu.faircode.netguard", "eu.faircode.netguard.debug"]
        ),
        "scope": _scope_provider(),
        "manual_control": True,
        "notes": [
            "La ubicación es puntual; no se mantiene seguimiento.",
            "NetGuard puede abrirse, pero no ofrece una API pública para cambiar sus reglas.",
            "El hotspot se detecta por Termux:API e interfaces visibles; Android puede ocultar su estado.",
        ],
    }


@router.get("/location")
async def android_location():
    errors = []
    for provider in ("gps", "network"):
        ok, data = await asyncio.to_thread(
            _run_json,
            "termux-location",
            ["-p", provider, "-r", "once"],
            20,
        )
        if ok and isinstance(data, dict):
            data.update({"source": "termux-api", "provider_requested": provider})
            return data
        errors.append({"provider": provider, "error": str(data)})
    return JSONResponse(
        {
            "available": False,
            "error": "No se pudo obtener ubicación. Instala Termux:API y concede ubicación.",
            "attempts": errors,
        },
        status_code=503,
    )


@router.get("/wifi")
async def android_wifi():
    ok, connection = await asyncio.to_thread(
        _run_json, "termux-wifi-connectioninfo", [], 10
    )
    interfaces = await asyncio.to_thread(_interfaces)
    hotspot_interfaces = [x for x in interfaces if x["type_hint"] == "hotspot"]
    return {
        "connection": connection if ok else None,
        "connection_available": ok,
        "connection_error": None if ok else str(connection),
        "interfaces": interfaces,
        "hotspot": {
            "detected": bool(hotspot_interfaces),
            "interfaces": hotspot_interfaces,
            "note": "El estado exacto del hotspot depende de los permisos y versión de Android.",
        },
        "source": "termux-api+ip",
    }


def _open_osmand(uri: str) -> dict:
    package = _package_installed(["net.osmand", "net.osmand.plus"])
    if not package:
        return {"opened": False, "error": "OsmAnd no está instalado", "hint": "Instala OsmAnd desde F-Droid o Play Store"}
    if not _available("am"):
        if _available("termux-open-url"):
            try:
                result = subprocess.run(["termux-open-url", uri], capture_output=True, text=True, timeout=10, check=False)
                if result.returncode == 0:
                    return {"opened": True, "method": "termux-open-url", "uri": uri}
            except Exception:
                pass
        return {"opened": False, "error": "Ni 'am' ni 'termux-open-url' disponibles"}

    # Intentar osmand:// deep link primero (más directo para OsmAnd)
    # Construir URI osmand:// si tenemos lat/lon del geo: URI
    osmand_uri = None
    if uri.startswith("geo:"):
        coords = uri[4:].split("?")[0].split(",")
        if len(coords) == 2:
            try:
                lat, lon = float(coords[0]), float(coords[1])
                label_part = ""
                if "?q=" in uri:
                    label_part = "&label=" + uri.split("?q=")[1]
                osmand_uri = f"osmand://goto?lat={lat}&lon={lon}{label_part}"
            except (ValueError, IndexError):
                pass

    attempts = []

    # Método 1: osmand:// deep link (si se pudo construir)
    if osmand_uri:
        try:
            result = subprocess.run(
                ["am", "start", "-a", "android.intent.action.VIEW", "-d", osmand_uri, "-p", package],
                capture_output=True, text=True, timeout=10, check=False
            )
            if result.returncode == 0:
                return {"opened": True, "method": "osmand-deeplink", "package": package, "uri": osmand_uri}
            attempts.append(f"osmand://: {(result.stderr or '').strip()}")
        except Exception as e:
            attempts.append(f"osmand://: {e}")

    # Método 2: geo: URI estándar (fallback)
    try:
        result = subprocess.run(
            ["am", "start", "-a", "android.intent.action.VIEW", "-d", uri, "-p", package],
            capture_output=True, text=True, timeout=10, check=False
        )
        if result.returncode == 0:
            return {"opened": True, "method": "geo-intent", "package": package, "uri": uri}
        attempts.append(f"geo:: {(result.stderr or '').strip()}")
    except Exception as e:
        attempts.append(f"geo:: {e}")

    # Método 3: termux-open-url (último recurso)
    if _available("termux-open-url"):
        try:
            result = subprocess.run(
                ["termux-open-url", uri],
                capture_output=True, text=True, timeout=10, check=False
            )
            if result.returncode == 0:
                return {"opened": True, "method": "termux-open-url", "uri": uri}
            attempts.append(f"termux-open-url: {(result.stderr or '').strip()}")
        except Exception as e:
            attempts.append(f"termux-open-url: {e}")

    return {"opened": False, "error": "No se pudo abrir OsmAnd", "attempts": attempts, "package": package}


@router.post("/open-osmand")
async def open_osmand(body: dict = Body(...)):
    try:
        latitude = float(body.get("latitude", body.get("lat")))
        longitude = float(body.get("longitude", body.get("lon")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="latitude y longitude son obligatorias")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="coordenadas fuera de rango")
    label = str(body.get("label", "")).strip()[:80]
    uri = f"geo:{latitude:.7f},{longitude:.7f}"
    if label:
        encoded = urllib.parse.quote(label, safe="")
        uri += f"?q={latitude:.7f},{longitude:.7f}({encoded})"
    result = await asyncio.to_thread(_open_osmand, uri)
    if not result.get("opened"):
        return JSONResponse(result, status_code=503)
    return result


def _open_netguard() -> dict:
    package = _package_installed(["eu.faircode.netguard", "eu.faircode.netguard.debug"])
    if not package:
        return {"opened": False, "error": "NetGuard no está instalado", "hint": "Instala NetGuard desde F-Droid o Play Store"}
    if not _available("am"):
        return {"opened": False, "error": "Comando 'am' no disponible (¿estás en Termux?)", "package": package}

    # Método 1: am start directo con activity conocida
    # Método 2: am start con MAIN/LAUNCHER
    # Método 3: cmd package resolve-activity (descubre la activity automáticamente)
    # Método 4: Abrir manual (sin error rojo)
    commands = [
        ("am start directo", ["am", "start", "-n", f"{package}/.MainActivity"]),
        ("am start LAUNCHER", ["am", "start", "-a", "android.intent.action.MAIN",
         "-c", "android.intent.category.LAUNCHER", "-p", package]),
    ]

    # Método 3: resolver la activity principal con cmd package
    if _available("cmd"):
        try:
            resolve = subprocess.run(
                ["cmd", "package", "resolve-activity", "--brief", package],
                capture_output=True, text=True, timeout=5, check=False
            )
            if resolve.returncode == 0:
                activity = (resolve.stdout or "").strip().splitlines()[-1].strip()
                if activity and "/" in activity:
                    commands.append(("cmd resolve-activity", ["am", "start", "-n", activity]))
        except Exception:
            pass  # fallback al método 4

    errors = []
    for label, command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
            if result.returncode == 0:
                return {"opened": True, "method": label, "package": package}
            err = (result.stderr or result.stdout or "").strip()
            if err:
                errors.append(f"{label}: {err}")
        except subprocess.TimeoutExpired:
            errors.append(f"{label}: timeout")
        except Exception as e:
            errors.append(f"{label}: {e}")

    # Método 4: abrir manual — no es un error rojo, es una indicación
    return {
        "opened": False,
        "error": "No se pudo abrir automáticamente",
        "hint": f"Abre NetGuard manualmente: Settings → Apps → NetGuard → Open",
        "package": package,
        "attempts": errors,
        "manual": True
    }


@router.post("/open-netguard")
async def open_netguard():
    result = await asyncio.to_thread(_open_netguard)
    if not result.get("opened"):
        return JSONResponse(result, status_code=503)
    return result


@router.post("/port-scan")
async def manual_port_scan(body: dict = Body(...)):
    if body.get("confirm_manual") is not True:
        raise HTTPException(status_code=400, detail="Debes confirmar el objetivo manualmente")
    target = str(body.get("target", "")).strip()
    if not target or len(target) > 43:
        raise HTTPException(status_code=400, detail="target debe ser una IP o CIDR")
    try:
        parsed = ipaddress.ip_network(target, strict=False) if "/" in target else ipaddress.ip_address(target)
    except ValueError:
        raise HTTPException(status_code=400, detail="target debe ser una IP o CIDR válido")
    if isinstance(parsed, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        hosts = list(parsed.hosts()) or [parsed.network_address]
    else:
        hosts = [parsed]
    if len(hosts) > 256:
        raise HTTPException(status_code=400, detail="máximo 256 hosts por escaneo manual (/24 en IPv4)")
    try:
        ports = _parse_ports(body.get("ports"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        timeout = min(1.5, max(0.2, float(body.get("timeout", 0.8))))
    except (TypeError, ValueError):
        timeout = 0.8

    semaphore = asyncio.Semaphore(80)

    async def check(host, port):
        async with semaphore:
            writer = None
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(str(host), port), timeout=timeout
                )
                return {"port": port, "service": SERVICE_NAMES.get(port, "unknown"), "state": "open"}
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                return None
            finally:
                if writer:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass

    checks = await asyncio.gather(*[
        check(host, port) for host in hosts for port in ports
    ])
    results = []
    offset = 0
    for host in hosts:
        opened = [item for item in checks[offset:offset + len(ports)] if item]
        offset += len(ports)
        if opened:
            results.append({"host": str(host), "ports": opened, "open_count": len(opened)})
    return {
        "target": target,
        "hosts_scanned": len(hosts),
        "ports_scanned": len(ports),
        "results": results,
        "open_ports": sum(item["open_count"] for item in results),
        "method": "tcp-connect",
        "manual_control": True,
        "scope": _scope_provider(),
        "timestamp": _dt.datetime.now().isoformat(),
    }