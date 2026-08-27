#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOURCESEAL NETWORK SWEEP ULTIMATE
==================================
Herramienta de Reconocimiento Profundo para Red Team.

Capacidades:
- Detección híbrida (ARP + Ping asíncrono)
- Fingerprinting de Vendor (Hikvision, Dahua, Axis, TP-Link, Xiaomi)
- Prueba de credenciales por defecto (SOLO para auditoría ética propia)
- Exportación JSON para IA

Autor: Harold Paredes / SourceSeal Red Team
Uso: python3 network_sweep_ultimate.py [--network 192.168.1.0/24] [--deep]
"""

import asyncio
import socket
import subprocess
import re
import json
import ipaddress
from datetime import datetime
from typing import List, Dict, Optional
import sys
import argparse


# ============================================================
# CONFIGURACIÓN DE ATAQUE (Personalizable)
# ============================================================
class Config:
    # Puertos críticos para CCTV/IoT
    CAMERA_PORTS = [80, 443, 8080, 8000, 8001, 8002, 8008, 8088, 554, 1935, 8554, 
                    37777, 8888, 6379, 27017, 1024, 8081, 8082, 3702]
    
    # Puertos de gestión/routers
    MGMT_PORTS = [21, 22, 23, 25, 53, 80, 443, 8080, 8443, 7547, 5000, 3389, 8089, 8090]
    
    # Credenciales por defecto comunes (SOLO PARA AUDITORÍA ÉTICA PROPIA)
    DEFAULT_CREDS = [
        ("admin", "admin"), ("admin", "12345"), ("admin", "123456"), 
        ("admin", "password"), ("admin", ""), ("root", "root"),
        ("user", "user"), ("administrator", "administrator"),
        ("admin", "1234"), ("admin", "pass"), ("root", "12345"),
        ("admin", "1111"), ("admin", "0000"), ("admin", "8888"),
        ("admin", "4321"), ("admin", "54321"), ("admin", "654321"),
        ("admin", "666666"), ("admin", "888888"), ("admin", "999999"),
        ("guest", "guest"), ("guest", "12345"), ("operator", "operator"),
        ("supervisor", "supervisor"), ("service", "service"),
        ("ubnt", "ubnt"), ("admin", "admin123"), ("support", "support")
    ]
    
    # Timeouts (segundos)
    TIMEOUT_SCAN = 0.5
    TIMEOUT_BANNER = 1.0
    TIMEOUT_CONNECTION = 1.5
    
    # User Agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SourceSeal-Scanner/2.0"
    
    # Concurrencia
    MAX_CONCURRENT = 50


# ============================================================
# MOTOR DE DESCUBRIMIENTO
# ============================================================

def get_my_network() -> str:
    """Detecta automáticamente la subred local."""
    try:
        # Método 1: ip route (Linux/Termux)
        result = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=2)
        for line in result.stdout.split('\n'):
            if "src" in line and "dev" in line:
                parts = line.split()
                idx = parts.index("src") if "src" in parts else -1
                if idx + 1 < len(parts):
                    my_ip = parts[idx+1]
                    return f"{'.'.join(my_ip.split('.')[:3])}.0/24"
                    
        # Método 2: ifconfig
        result = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=2)
        for line in result.stdout.split('\n'):
            if "inet addr:" in line or "inet " in line:
                ip_match = re.search(r'inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)', line)
                if ip_match:
                    my_ip = ip_match.group(1)
                    return f"{'.'.join(my_ip.split('.')[:3])}.0/24"
                    
        # Método 3: hostname -I
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            my_ip = result.stdout.strip().split()[0]
            return f"{'.'.join(my_ip.split('.')[:3])}.0/24"
            
    except Exception as e:
        print(f"⚠️ Error detectando red: {e}. Usando fallback 192.168.1.0/24")
    
    return "192.168.1.0/24"


async def arp_scan() -> List[str]:
    """Obtiene IPs de la tabla ARP (dispositivos con los que ya hablaste)."""
    try:
        res = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=2)
        ips = re.findall(r'(\d+\.\d+\.\d+\.\d+)', res.stdout)
        return list(set(ips))
    except:
        return []


async def ping_host(ip: str) -> bool:
    """Ping rápido asíncrono."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "0.3", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await asyncio.wait_for(proc.wait(), timeout=0.8)
        return proc.returncode == 0
    except:
        return False


async def discover_active_ips(network: str) -> List[str]:
    """Descubre IPs activas usando ARP + Ping."""
    print(f"🔍 Escaneando red: {network}...")
    
    net = ipaddress.ip_network(network, strict=False)
    all_ips = [str(ip) for ip in net.hosts()]
    
    # Fase 1: ARP (Instantáneo - dispositivos que ya han comunicado)
    print("  📡 Probando ARP...")
    arp_ips = await arp_scan()
    active_ips = list(set(arp_ips).intersection(set(all_ips)))
    print(f"     ✅ {len(active_ips)} dispositivos vía ARP")
    
    # Fase 2: Ping a los que faltan (Profundo)
    missing = [ip for ip in all_ips if ip not in active_ips]
    if missing:
        print(f"  📡 Probando {len(missing)} IPs con ping...")
        tasks = [ping_host(ip) for ip in missing]
        results = await asyncio.gather(*tasks)
        
        for i, alive in enumerate(results):
            if alive:
                active_ips.append(missing[i])
    
    print(f"  ✅ Total IPs activas: {len(active_ips)}")
    return list(set(active_ips))


# ============================================================
# MOTOR DE FINGERPRINTING & EXPLOTACIÓN
# ============================================================

async def grab_banner(ip: str, port: int, path: str = "/") -> Optional[str]:
    """Intenta obtener banner HTTP o servicio."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=Config.TIMEOUT_CONNECTION
        )
        
        # Request según protocolo
        if port in [80, 443, 8080, 8000, 8001, 8002, 8008, 8088]:
            req = (f"GET {path} HTTP/1.1\r\n"
                   f"Host: {ip}\r\n"
                   f"User-Agent: {Config.USER_AGENT}\r\n"
                   f"Connection: close\r\n\r\n")
        else:
            req = b"\r\n"  # Generic probe
            
        writer.write(req.encode() if isinstance(req, str) else req)
        await writer.drain()
        
        data = await asyncio.wait_for(
            reader.read(1024),
            timeout=Config.TIMEOUT_BANNER
        )
        writer.close()
        await writer.wait_closed()
        
        return data.decode(errors='ignore')[:500]
        
    except:
        return None


async def check_rtsp_auth(ip: str, port: int = 554) -> Dict:
    """Verifica RTSP y prueba credenciales por defecto."""
    status = {
        "port": port,
        "service": "rtsp",
        "open": False,
        "vulnerable": False,
        "creds": None,
        "banner": None,
        "rtsp_url": None
    }
    
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=Config.TIMEOUT_CONNECTION
        )
        
        # Enviar OPTIONS RTSP
        req = f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n"
        writer.write(req.encode())
        await writer.drain()
        
        resp = await asyncio.wait_for(
            reader.read(1024),
            timeout=Config.TIMEOUT_BANNER
        )
        writer.close()
        await writer.wait_closed()
        
        response = resp.decode(errors='ignore')
        status["banner"] = response[:200]
        
        if "RTSP/1.0" in response or "RTSP/1.1" in response:
            status["open"] = True
            status["rtsp_url"] = f"rtsp://{ip}:{port}"
            
            # Si pide autenticación, probar credenciales por defecto
            if "401 Unauthorized" in response or "403 Forbidden" in response:
                for user, passwd in Config.DEFAULT_CREDS:
                    if await test_rtsp_cred(ip, port, user, passwd):
                        status["vulnerable"] = True
                        status["creds"] = f"{user}:{passwd}"
                        status["rtsp_url"] = f"rtsp://{user}:{passwd}@{ip}:{port}"
                        break
        
        return status
        
    except:
        return status


async def test_rtsp_cred(ip: str, port: int, user: str, passwd: str) -> bool:
    """Prueba un par de credenciales específico en RTSP."""
    try:
        import base64
        creds = base64.b64encode(f"{user}:{passwd}".encode()).decode()
        
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=Config.TIMEOUT_CONNECTION
        )
        
        req = (f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
               f"CSeq: 1\r\n"
               f"Authorization: Basic {creds}\r\n\r\n")
        writer.write(req.encode())
        await writer.drain()
        
        resp = await asyncio.wait_for(
            reader.read(512),
            timeout=Config.TIMEOUT_BANNER
        )
        writer.close()
        await writer.wait_closed()
        
        response = resp.decode(errors='ignore')
        return "200 OK" in response or "401" not in response
        
    except:
        return False


async def check_onvif(ip: str, port: int = 80) -> Dict:
    """Verifica si hay un dispositivo ONVIF."""
    try:
        # Probar endpoint ONVIF
        banner = await grab_banner(ip, port, "/onvif/device_service")
        if banner and "ONVIF" in banner.upper():
            return {
                "port": port,
                "service": "onvif",
                "open": True,
                "banner": banner[:200]
            }
        
        # Probar WS-Discovery (puerto 3702)
        if port == 80:
            ws_result = await check_onvif_ws_discovery(ip)
            if ws_result:
                return ws_result
        
        return {"port": port, "service": "unknown", "open": False}
        
    except:
        return {"port": port, "service": "unknown", "open": False}


async def check_onvif_ws_discovery(ip: str) -> Optional[Dict]:
    """Verifica ONVIF usando WS-Discovery (puerto 3702)."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 3702),
            timeout=Config.TIMEOUT_CONNECTION
        )
        
        soap_message = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
              xmlns:tds="http://www.onvif.org/ver10/network/wsdl">
  <soap:Body>
    <tds:GetDevices xmlns="http://www.onvif.org/ver10/device/wsdl"/>
  </soap:Body>
</soap:Envelope>"""
        
        soap_msg = (f"POST /onvif/device_service HTTP/1.1\r\n"
                    f"Host: {ip}:3702\r\n"
                    f"Content-Type: application/soap+xml\r\n"
                    f"Content-Length: {len(soap_message)}\r\n"
                    f"Connection: close\r\n\r\n" + soap_message)
        
        writer.write(soap_msg.encode())
        await writer.drain()
        
        data = await asyncio.wait_for(
            reader.read(2048),
            timeout=Config.TIMEOUT_BANNER
        )
        writer.close()
        await writer.wait_closed()
        
        response = data.decode(errors='ignore')
        
        if "GetDevicesResponse" in response or "ONVIF" in response.upper():
            return {
                "port": 3702,
                "service": "onvif_ws",
                "open": True,
                "banner": response[:200]
            }
        
        return None
        
    except:
        return None


# ============================================================
# FINGERPRINTING DE DISPOSITIVOS
# ============================================================

VENDOR_SIGNATURES = {
    # Cámaras
    "hikvision": [
        r"hikvision", r"isapi", r"hik", r"ds-2", r"iVMS", r"Hikvision",
        r"Server: Hikvision", r"Hikvision Web Server", r"DS-2CD"
    ],
    "dahua": [
        r"dahua", r"dahuatech", r"Dahua", r"DH-", r"IPC",
        r"Server: Dahua", r"Dahua Web Server", r"Dahua Technology"
    ],
    "axis": [
        r"axis", r"AXIS", r"2100", r"2120", r"2130", r"2140",
        r"Server: AXIS", r"AXIS Communications", r"AXIS Camera"
    ],
    "uniview": [
        r"uniview", r"UNIVIEW", r"UniView", r"NVR", r"IPC",
        r"Server: UniView", r"UniView Technologies"
    ],
    "honeywell": [
        r"honeywell", r"Honeywell", r"Performance Series", r"Pro-Watch"
    ],
    "bosch": [
        r"bosch", r"BOSCH", r"Bosch Security", r"VIP"
    ],
    
    # Routers
    "tenda": [
        r"tenda", r"Tenda", r"AC5", r"AC6", r"AC10", r"AC15",
        r"Server: Tenda", r"Tenda Technology", r"Tenda Wireless"
    ],
    "tp-link": [
        r"tp-link", r"TP-Link", r"Archer", r"TL-WR", r"TL-MR",
        r"Server: TP-LINK", r"TP-LINK Technologies", r"TP-Link Wireless"
    ],
    "asus": [
        r"asus", r"ASUS", r"RT-AC", r"RT-AX", r"RT-N",
        r"Server: ASUS", r"ASUSTek", r"ASUS Wireless"
    ],
    "mercury": [
        r"mercury", r"Mercury", r"DW", r"Mercusys",
        r"Server: Mercury"
    ],
    "netgear": [
        r"netgear", r"NETGEAR", r"R6", r"R7", r"R8",
        r"Server: NETGEAR"
    ],
    "linksys": [
        r"linksys", r"Linksys", r"EA", r"WRT",
        r"Server: Linksys"
    ],
    
    # DVRs/NVRs
    "xiongmai": [
        r"xm", r"Xiongmai", r"XM", r"Goolink", r"Goke"
    ],
    "lorex": [
        r"lorex", r"Lorex", r"LH", r"LNR", r"Lorex Technology"
    ],
    "swann": [
        r"swann", r"Swann", r"SWV", r"Swann Security"
    ],
    "annke": [
        r"annke", r"Annke", r"I61", r"Annke Security"
    ],
    
    # IoT
    "xiaomi": [
        r"xiaomi", r"mi", r"Mi Camera", r"Mi Home", r"Mi WiFi",
        r"Server: nginx/1.8.0", r"Xiaomi", r"MiJia"
    ],
    "ezviz": [
        r"ezviz", r"EZVIZ", r"CS-", r"EZVIZ Security"
    ],
    "wyzecam": [
        r"wyze", r"Wyze", r"Wyze Cam", r"Wyze Labs"
    ],
    
    # Servidores
    "nginx": [r"nginx", r"nginx/", r"Server: nginx"],
    "apache": [r"apache", r"Apache", r"Server: Apache"],
    "iis": [r"IIS", r"Microsoft-IIS", r"Server: Microsoft-IIS"],
    "lighttpd": [r"lighttpd", r"Server: lighttpd"],
    "tomcat": [r"tomcat", r"Apache-Coyote", r"Server: Apache-Coyote"],
    "busybox": [r"BusyBox", r"Server: BusyBox"],
    "mikrotik": [r"MikroTik", r"RouterOS", r"Server: MikroTik"],
}

PORT_SIGNATURES = {
    21: {"service": "FTP", "risk": "medium", "category": "file_transfer"},
    22: {"service": "SSH", "risk": "low", "category": "remote_access"},
    23: {"service": "Telnet", "risk": "critical", "category": "remote_access"},
    25: {"service": "SMTP", "risk": "medium", "category": "email"},
    53: {"service": "DNS", "risk": "medium", "category": "network"},
    80: {"service": "HTTP", "risk": "low", "category": "web"},
    443: {"service": "HTTPS", "risk": "low", "category": "web"},
    554: {"service": "RTSP", "risk": "medium", "category": "streaming"},
    1935: {"service": "RTMP", "risk": "medium", "category": "streaming"},
    8000: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8080: {"service": "HTTP-Proxy", "risk": "low", "category": "web"},
    8081: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8082: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8443: {"service": "HTTPS-Alt", "risk": "low", "category": "web"},
    7547: {"service": "TR-069", "risk": "high", "category": "management"},
    3389: {"service": "RDP", "risk": "critical", "category": "remote_access"},
    3702: {"service": "ONVIF-WS", "risk": "low", "category": "camera"},
    8008: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8088: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
    8888: {"service": "HTTP-Alt", "risk": "low", "category": "web"},
}


def identify_device(banner: Optional[str], port: int, ip: str) -> Dict:
    """Identifica el vendor, tipo y sistema operativo del dispositivo."""
    info = {
        "ip": ip,
        "port": port,
        "vendor": "Unknown",
        "type": "Unknown",
        "os": "Unknown",
        "model": "Unknown",
        "risk": "low"
    }
    
    if not banner:
        if port in PORT_SIGNATURES:
            info.update(PORT_SIGNATURES[port])
        return info
    
    banner_lower = banner.lower()
    
    # Buscar por vendor
    for vendor, signatures in VENDOR_SIGNATURES.items():
        for signature in signatures:
            if re.search(signature, banner_lower, re.I):
                info["vendor"] = vendor.capitalize()
                
                # Extraer modelo para cámaras
                if vendor in ["hikvision", "dahua", "axis", "uniview"]:
                    model_match = re.search(r'(ds-[\w-]+|dh-[\w-]+|axis [\w-]+|ipc[\w-]+)', banner_lower, re.I)
                    if model_match:
                        info["model"] = model_match.group(0).upper()
                break
    
    # Buscar por tipo
    if "camera" in banner_lower or "ip camera" in banner_lower or "nvr" in banner_lower or "dvr" in banner_lower:
        info["type"] = "Camera/DVR"
    elif "router" in banner_lower or "gateway" in banner_lower or "ap" in banner_lower or "wireless" in banner_lower:
        info["type"] = "Router/AP"
    elif "switch" in banner_lower:
        info["type"] = "Switch"
    elif "printer" in banner_lower:
        info["type"] = "Printer"
    elif "nas" in banner_lower or "storage" in banner_lower:
        info["type"] = "NAS/Storage"
    elif "iot" in banner_lower or "smart" in banner_lower:
        info["type"] = "IoT Device"
    elif "server" in banner_lower or "web server" in banner_lower:
        info["type"] = "Server"
    
    # Buscar por OS
    if "linux" in banner_lower:
        info["os"] = "Linux"
    elif "busybox" in banner_lower:
        info["os"] = "BusyBox (Embedded Linux)"
    elif "windows" in banner_lower:
        info["os"] = "Windows"
    elif "mikrotik" in banner_lower or "routeros" in banner_lower:
        info["os"] = "MikroTik RouterOS"
    elif "embedded" in banner_lower:
        info["os"] = "Embedded OS"
    
    # Riesgo por puerto
    if port in PORT_SIGNATURES:
        info["risk"] = PORT_SIGNATURES[port]["risk"]
        info["category"] = PORT_SIGNATURES[port]["category"]
    
    return info


# ============================================================
# ESCANEO DE PUERTOS
# ============================================================

async def scan_ports(ip: str, ports: List[int]) -> List[int]:
    """Escanea una lista de puertos en una IP."""
    open_ports = []
    semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT)
    
    async def check_port(port):
        async with semaphore:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=Config.TIMEOUT_SCAN
                )
                writer.close()
                await writer.wait_closed()
                return port
            except:
                return None
    
    tasks = [check_port(port) for port in ports]
    results = await asyncio.gather(*tasks)
    
    return [p for p in results if p is not None]


# ============================================================
# ORQUESTADOR PRINCIPAL
# ============================================================

async def scan_target(ip: str, deep: bool = False) -> Dict:
    """Escanea un objetivo completo."""
    target_data = {
        "ip": ip,
        "services": [],
        "info": {"vendor": "Unknown", "type": "Unknown", "os": "Unknown", "model": "Unknown"},
        "timestamp": datetime.now().isoformat()
    }
    
    # Puertos a escanear
    ports_to_scan = list(set(Config.CAMERA_PORTS + Config.MGMT_PORTS))
    if deep:
        ports_to_scan = list(range(1, 10001))
    
    # Escaneo de puertos
    open_ports = await scan_ports(ip, ports_to_scan)
    print(f"    🔌 {len(open_ports)} puertos abiertos en {ip}")
    
    # Analizar cada puerto
    for port in sorted(open_ports):
        service_info = {
            "port": port,
            "service": "unknown",
            "banner": None,
            "vulnerable": False,
            "creds": None,
            "rtsp_url": None
        }
        
        # Obtener banner
        banner = await grab_banner(ip, port)
        service_info["banner"] = banner[:200] if banner else None
        
        # Identificar servicio
        if port == 554:
            rtsp_check = await check_rtsp_auth(ip, port)
            service_info.update(rtsp_check)
            if rtsp_check["open"]:
                service_info["service"] = "rtsp"
        elif port == 3702:
            onvif_check = await check_onvif(ip, port)
            if onvif_check["open"]:
                service_info.update(onvif_check)
                service_info["service"] = "onvif"
        elif port in [80, 443, 8080, 8000, 8001, 8002, 8008, 8088]:
            onvif_check = await check_onvif(ip, port)
            if onvif_check["open"]:
                service_info.update(onvif_check)
                service_info["service"] = "onvif"
            else:
                service_info["service"] = "http"
        else:
            if port in PORT_SIGNATURES:
                service_info["service"] = PORT_SIGNATURES[port]["service"]
        
        # Identificar dispositivo
        device_info = identify_device(banner, port, ip)
        service_info["device_info"] = device_info
        
        # Actualizar info global
        if device_info["vendor"] != "Unknown":
            target_data["info"] = device_info
        
        target_data["services"].append(service_info)
    
    return target_data


async def main(deep: bool = False, network: Optional[str] = None):
    """Función principal."""
    print("\n" + "="*70)
    print("  🛡️  SOURCESEAL NETWORK SWEEP ULTIMATE v2.0")
    print("  Autor: Harold Paredes | SourceSeal Red Team")
    print("="*70)
    
    # Detectar red
    net = network or get_my_network()
    print(f"\n🌐 Red a escanear: {net}")
    
    # Escanear IPs activas
    active_ips = await discover_active_ips(net)
    
    if not active_ips:
        print("\n❌ No se encontraron dispositivos activos.")
        return
    
    print(f"\n🔍 Escaneando {len(active_ips)} dispositivos...")
    print("   Esto puede tardar unos minutos...")
    
    # Escaneo concurrente
    semaphore = asyncio.Semaphore(20)
    
    async def worker(ip):
        async with semaphore:
            return await scan_target(ip, deep)
    
    results = await asyncio.gather(*[worker(ip) for ip in active_ips])
    
    # Filtrar solo resultados con servicios
    targets = [r for r in results if r['services']]
    
    # Resumen
    print("\n" + "="*70)
    print("  📊 REPORTE DE INTELIGENCIA")
    print("="*70)
    
    total_devices = len(targets)
    camera_count = sum(1 for t in targets if any(
        s.get('device_info', {}).get('type') == 'Camera/DVR' 
        for s in t['services']
    ))
    router_count = sum(1 for t in targets if any(
        s.get('device_info', {}).get('type') == 'Router/AP' 
        for s in t['services']
    ))
    vulnerable_count = sum(1 for t in targets if any(
        s.get('vulnerable') for s in t['services']
    ))
    
    print(f"\n📈 ESTADÍSTICAS:")
    print(f"  🌐 Dispositivos totales: {total_devices}")
    print(f"  📹 Cámaras/DVRs: {camera_count}")
    print(f"  📡 Routers/APs: {router_count}")
    print(f"  ⚠️  Dispositivos vulnerables: {vulnerable_count}")
    
    # Mostrar detalles
    print("\n" + "-"*70)
    print("  DETALLES POR DISPOSITIVO")
    print("-"*70)
    
    for i, target in enumerate(targets, 1):
        print(f"\n[{i}] 📍 {target['ip']}")
        print(f"     🏭 Vendor: {target['info']['vendor']}")
        print(f"     🏷️  Tipo: {target['info']['type']}")
        print(f"     🖥️  OS: {target['info']['os']}")
        if target['info']['model'] != "Unknown":
            print(f"     📱 Modelo: {target['info']['model']}")
        
        for service in target['services']:
            banner_preview = service['banner'][:60] if service['banner'] else "No banner"
            vulnerable_flag = " ⚠️ VULNERABLE" if service.get('vulnerable') else ""
            creds_flag = f" 🔑 {service.get('creds')}" if service.get('creds') else ""
            rtsp_flag = f" 🎥 {service.get('rtsp_url')}" if service.get('rtsp_url') else ""
            
            print(f"     🔌 Puerto {service['port']}: {service['service']} | {banner_preview}{vulnerable_flag}{creds_flag}{rtsp_flag}")
    
    # Guardar JSON
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"seal_intel_{timestamp}.json"
    
    output_data = {
        "scan": {
            "timestamp": datetime.now().isoformat(),
            "network": net,
            "total_devices": total_devices,
            "camera_count": camera_count,
            "router_count": router_count,
            "vulnerable_count": vulnerable_count
        },
        "targets": targets
    }
    
    with open(filename, 'w') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*70)
    print(f"  ✅ Resultados guardados en: {filename}")
    print(f"  💡 Usa: python3 seal/scanners/fingerprint_engine.py {filename}")
    print("  🤖 Listo para análisis con IA")
    print("="*70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SOURCESEAL Network Sweep Ultimate - Escáner de inteligencia de red"
    )
    parser.add_argument(
        "--network",
        type=str,
        default=None,
        help="Red a escanear (ej: 192.168.1.0/24)"
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Escaneo profundo (todos los puertos 1-10000)"
    )
    
    args = parser.parse_args()
    asyncio.run(main(args.deep, args.network))
