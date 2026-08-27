import asyncio
import socket
import struct
import sqlite3
import json
import hashlib
import re
import subprocess
import ssl
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/enhanced", tags=["enhanced-recon"])

DB_PATH = "./enhanced_recon.db"
CREDENTIALS_DB = {
    "generic": [("admin", "admin"), ("admin", "12345"), ("admin", "123456"), 
                ("root", "root"), ("user", "user"), ("guest", "guest")],
    "hikvision": [("admin", "12345"), ("admin", "admin")],
    "dahua": [("admin", "admin"), ("admin", "123456")],
    "reolink": [("admin", "admin")],
    "foscam": [("admin", "")],
    "ubiquiti": [("ubnt", "ubnt"), ("root", "ubnt")],
    "amcrest": [("admin", "admin")],
}

# ─── DB ───
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cameras (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, port INTEGER,
        brand TEXT, model TEXT, rtsp_url TEXT, snapshot_url TEXT,
        credentials TEXT, discovered TEXT, last_seen TEXT, vulnerable INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS hosts_deep (
        ip TEXT PRIMARY KEY, mac TEXT, hostname TEXT, os_guess TEXT,
        open_ports TEXT, ssl_info TEXT, snmp_info TEXT, upnp_info TEXT,
        mdns_info TEXT, netbios_info TEXT, first_seen TEXT, last_seen TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# ═══════════════════════════════════════════════════════
# ONVIF WS-Discovery (Multicast 239.255.255.250:3702)
# ═══════════════════════════════════════════════════════

WS_DISCOVERY_PROBE = '''<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID>
    <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action a:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>'''

def _onvif_discover_sync(timeout: float = 3.0) -> List[Dict]:
    """Descubre cámaras ONVIF vía multicast WS-Discovery (versión síncrona)"""
    found = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
        
        sock.sendto(WS_DISCOVERY_PROBE.encode(), ("239.255.255.250", 3702))
        
        import time as _time
        start = _time.monotonic()
        while _time.monotonic() - start < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode('utf-8', errors='ignore')
                if "onvif" in text.lower() or "NetworkVideoTransmitter" in text:
                    xaddrs = re.findall(r'XAddrs>(.*?)</', text)
                    found.append({
                        "ip": addr[0], "port": addr[1],
                        "source": "onvif-ws-discovery",
                        "xaddrs": xaddrs,
                        "raw": text[:500]
                    })
            except socket.timeout:
                break
        sock.close()
    except Exception as e:
        print(f"[ONVIF Error] {e}")
    return found

async def onvif_discover(timeout: float = 3.0) -> List[Dict]:
    """Wrapper async que ejecuta el descubrimiento en un thread separado"""
    return await asyncio.to_thread(_onvif_discover_sync, timeout)

# ═══════════════════════════════════════════════════════
# SSDP / UPnP Discovery (239.255.255.250:1900)
# ═══════════════════════════════════════════════════════

SSDP_DISCOVER = '''M-SEARCH * HTTP/1.1\r
HOST: 239.255.255.250:1900\r
MAN: "ssdp:discover"\r
MX: 3\r
ST: ssdp:all\r
\r\n'''

def _ssdp_discover_sync(timeout: float = 3.0) -> List[Dict]:
    """Descubre dispositivos UPnP/SSDP (versión síncrona para thread pool)"""
    found = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.sendto(SSDP_DISCOVER.encode(), ("239.255.255.250", 1900))
        
        import time as _time
        start = _time.monotonic()
        while _time.monotonic() - start < timeout:
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode('utf-8', errors='ignore')
                if "200 OK" in text:
                    location = re.search(r'LOCATION:\s*(.+?)\r\n', text, re.I)
                    server = re.search(r'SERVER:\s*(.+?)\r\n', text, re.I)
                    st = re.search(r'ST:\s*(.+?)\r\n', text, re.I)
                    
                    device = {
                        "ip": addr[0], "port": addr[1],
                        "location": location.group(1).strip() if location else None,
                        "server": server.group(1).strip() if server else "Unknown",
                        "device_type": st.group(1).strip() if st else "Unknown",
                        "source": "ssdp"
                    }
                    # Intentar obtener XML de descripción si hay location
                    if device["location"]:
                        try:
                            import urllib.request
                            req = urllib.request.Request(device["location"], timeout=2)
                            with urllib.request.urlopen(req) as resp:
                                xml = resp.read().decode('utf-8', errors='ignore')
                                mf = re.search(r'<manufacturer>(.*?)</manufacturer>', xml, re.I)
                                md = re.search(r'<modelName>(.*?)</modelName>', xml, re.I)
                                fn = re.search(r'<friendlyName>(.*?)</friendlyName>', xml, re.I)
                                device["manufacturer"] = mf.group(1) if mf else None
                                device["model"] = md.group(1) if md else None
                                device["friendly_name"] = fn.group(1) if fn else None
                        except:
                            pass
                    found.append(device)
            except socket.timeout:
                break
        sock.close()
    except Exception as e:
        print(f"[SSDP Error] {e}")
    return found

async def ssdp_discover(timeout: float = 3.0) -> List[Dict]:
    """Wrapper async que ejecuta el descubrimiento en un thread separado"""
    return await asyncio.to_thread(_ssdp_discover_sync, timeout)

# ═══════════════════════════════════════════════════════
# SNMP Probe (UDP 161)
# ═══════════════════════════════════════════════════════

def snmp_probe(ip: str, community: str = "public", timeout: float = 2.0) -> Optional[Dict]:
    """Query SNMP v1 sysDescr, sysName, sysContact"""
    # SNMP GET request para sysDescr (1.3.6.1.2.1.1.1.0)
    oid_sysdescr = b'\x30\x26\x02\x01\x00\x04\x06' + community.encode() + \
                   b'\xa0\x19\x02\x04\x00\x00\x00\x01\x02\x01\x00\x02\x01\x00' \
                   b'\x30\x0b\x30\x09\x06\x05\x2b\x06\x01\x02\x01\x01\x01\x00\x05\x00'
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(oid_sysdescr, (ip, 161))
        data, _ = sock.recvfrom(1024)
        sock.close()
        
        # Parseo básico del BER
        text = data.decode('utf-8', errors='ignore')
        # Extraer string legible
        readable = ''.join(c for c in text if c.isprintable() or c in ' \t\n')
        # Buscar sysDescr típico
        if len(readable) > 10:
            return {
                "ip": ip, "community": community,
                "response": readable[:300],
                "source": "snmp"
            }
    except:
        pass
    return None

# ═══════════════════════════════════════════════════════
# NetBIOS Name Query (UDP 137)
# ═══════════════════════════════════════════════════════

def netbios_query(ip: str, timeout: float = 2.0) -> Optional[Dict]:
    """Query NetBIOS para nombre de host Windows"""
    # NetBIOS Name Service Query
    packet = b'\x82\x28\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00' \
             b'\x20\x43\x4b\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41' \
             b'\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x00' \
             b'\x00\x21\x00\x01'
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(packet, (ip, 137))
        data, _ = sock.recvfrom(1024)
        sock.close()
        if len(data) > 56:
            # Extraer nombre del offset 57
            name_bytes = data[57:73].replace(b'\x00', b'').replace(b'\x20', b'')
            name = name_bytes.decode('ascii', errors='ignore').strip()
            if name:
                return {"ip": ip, "netbios_name": name, "source": "netbios"}
    except:
        pass
    return None

# ═══════════════════════════════════════════════════════
# mDNS Query (224.0.0.251:5353)
# ═══════════════════════════════════════════════════════

def mdns_query(timeout: float = 2.0) -> List[Dict]:
    """Descubre servicios mDNS/Bonjour en la red local"""
    query = b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00' \
            b'\x09_services\x07_dns-sd\x04_udp\x05local\x00\x00\x0c\x00\x01'
    found = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.sendto(query, ("224.0.0.251", 5353))
        
        import time as _time
        start = _time.monotonic()
        while _time.monotonic() - start < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                text = data.decode('utf-8', errors='ignore')
                # Extraer nombres de servicio
                services = re.findall(r'([a-zA-Z0-9_-]+)\._tcp', text)
                if services:
                    found.append({
                        "ip": addr[0], "services": list(set(services)),
                        "source": "mdns"
                    })
            except socket.timeout:
                break
        sock.close()
    except Exception as e:
        print(f"[mDNS Error] {e}")
    return found

# ═══════════════════════════════════════════════════════
# CÁMARA: Credenciales por defecto + RTSP probing
# ═══════════════════════════════════════════════════════

CAMERA_PATHS = {
    "generic": [
        "/video.mp4", "/live.mp4", "/stream.mp4", "/cgi-bin/mjpg/video.cgi",
        "/snapshot.cgi", "/snap.jpg", "/image.jpg", "/tmpfs/auto.jpg"
    ],
    "hikvision": [
        "/Streaming/channels/1/preview", "/ISAPI/Streaming/channels/101/picture",
        "/onvif-http/snapshot?Profile_1", "/doc/page/login.asp"
    ],
    "dahua": [
        "/cgi-bin/magicBox.cgi?action=getMachineName",
        "/cgi-bin/configManager.cgi?action=getConfig&name=General",
        "/onvif-http/snapshot?Profile_1"
    ],
    "reolink": [
        "/cgi-bin/api.cgi?cmd=GetDevInfo&channel=0",
        "/cgi-bin/api.cgi?cmd=Snap&channel=0"
    ],
    "onvif": ["/onvif/device_service", "/onvif/Media", "/onvif/media_service"],
    "rtsp": ["/live/ch00_0", "/cam/realmonitor?channel=1&subtype=0", "/user=admin_password=tlJwpbo6_channel=1_stream=0.sdp"]
}

async def probe_camera_http(ip: str, port: int, path: str, creds: tuple = None, timeout: float = 3.0) -> Optional[Dict]:
    """Prueba una URL de cámara con credenciales opcionales"""
    import aiohttp
    auth = aiohttp.BasicAuth(creds[0], creds[1]) if creds else None
    url = f"http://{ip}:{port}{path}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, auth=auth, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as resp:
                if resp.status in [200, 401]:
                    content_type = resp.headers.get('Content-Type', '')
                    server = resp.headers.get('Server', '')
                    return {
                        "url": url, "status": resp.status,
                        "content_type": content_type, "server": server,
                        "auth_required": resp.status == 401,
                        "creds_tested": f"{creds[0]}:{creds[1]}" if creds else None
                    }
    except:
        pass
    return None

async def detect_camera_brand(ip: str, port: int) -> str:
    """Detecta marca por banners y rutas características"""
    test_paths = ["/", "/doc/page/login.asp", "/cgi-bin/magicBox.cgi", "/api.cgi"]
    import aiohttp
    for path in test_paths:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{ip}:{port}{path}", timeout=aiohttp.ClientTimeout(total=2), ssl=False) as resp:
                    text = await resp.text()
                    lower = text.lower()
                    if "hikvision" in lower or "webplugin" in lower: return "hikvision"
                    if "dahua" in lower: return "dahua"
                    if "reolink" in lower: return "reolink"
                    if "ubiquiti" in lower or "unifi" in lower: return "ubiquiti"
                    if "foscam" in lower: return "foscam"
                    if "amcrest" in lower: return "amcrest"
        except:
            continue
    return "generic"

async def scan_camera_full(ip: str, port: int = 80) -> Optional[Dict]:
    """Escaneo completo de una cámara: detecta marca, prueba credenciales, encuentra URLs"""
    brand = await detect_camera_brand(ip, port)
    results = {
        "ip": ip, "port": port, "brand": brand,
        "accessible_urls": [], "working_credentials": None,
        "rtsp_working": None, "snapshot_url": None
    }
    
    # Probar URLs sin auth
    paths = CAMERA_PATHS.get(brand, []) + CAMERA_PATHS["generic"] + CAMERA_PATHS["onvif"]
    tested = set()
    
    for path in paths:
        if path in tested: continue
        tested.add(path)
        probe = await probe_camera_http(ip, port, path, timeout=2.5)
        if probe and probe["status"] == 200:
            results["accessible_urls"].append(probe)
            if "image" in probe.get("content_type", "") or "jpg" in path or "snapshot" in path:
                results["snapshot_url"] = probe["url"]
    
    # Probar credenciales si hay 401
    creds_list = CREDENTIALS_DB.get(brand, []) + CREDENTIALS_DB["generic"]
    for user, pwd in creds_list:
        # Probar snapshot con auth
        snap = await probe_camera_http(ip, port, "/snapshot.cgi", (user, pwd), 2.0)
        if snap and snap["status"] == 200:
            results["working_credentials"] = f"{user}:{pwd}"
            if not results["snapshot_url"]:
                results["snapshot_url"] = f"http://{user}:{pwd}@{ip}:{port}/snapshot.cgi"
            break
    
    # Construir RTSP URL
    rtsp_paths = ["/live/ch00_0", "/cam/realmonitor?channel=1&subtype=0", "/Streaming/channels/101"]
    for rp in rtsp_paths:
        test_url = f"rtsp://{ip}:{port if port != 80 else 554}{rp}"
        # Verificación ligera: intentar conectar TCP al puerto RTSP (async)
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port if port != 80 else 554), timeout=1.0)
            writer.close()
            try: await writer.wait_closed()
            except: pass
            results["rtsp_working"] = test_url
            break
        except:
            continue
    
    # Guardar en DB (en thread para no bloquear)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=1.0)
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO cameras 
            (ip, port, brand, rtsp_url, snapshot_url, credentials, discovered, last_seen, vulnerable)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ip, port, brand, results["rtsp_working"], results["snapshot_url"],
             results["working_credentials"], datetime.now().isoformat(), datetime.now().isoformat(),
             1 if results["working_credentials"] else 0))
        conn.commit()
        conn.close()
    except Exception:
        pass
    
    return results

# ═══════════════════════════════════════════════════════
# SSL Certificate Extractor
# ═══════════════════════════════════════════════════════

def extract_ssl_info(ip: str, port: int = 443) -> Optional[Dict]:
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=ip) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()
                return {
                    "subject": cert.get("subject"),
                    "issuer": cert.get("issuer"),
                    "not_after": cert.get("notAfter"),
                    "not_before": cert.get("notBefore"),
                    "san": cert.get("subjectAltName"),
                    "serial": cert.get("serialNumber"),
                    "cipher": cipher,
                    "tls_version": version,
                    "source": "ssl_probe"
                }
    except Exception as e:
        return {"error": str(e), "source": "ssl_probe"}

# ═══════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════

def _real_subnet_prefix() -> str:
    """Detecta el prefijo /24 REAL del dispositivo (via socket UDP trick, sin
    depender de rutas). Se usa como fallback cuando el cliente no manda
    'network' -- antes el default hardcodeado '192.168.1' escaneaba una red
    que casi nunca coincide con la red real (hotspots Android suelen usar
    192.168.43.x, 192.168.49.x, etc.), por eso ONVIF/SSDP/camaras siempre
    salian en 0 aunque hubiera dispositivos reales."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    except Exception:
        return "192.168.1"

@router.get("/discover/all")
async def full_discovery_get(network: str = None):
    """Alias GET del POST /discover/all — el frontend usa GET"""
    return await full_discovery(network)

@router.post("/discover/all")
async def full_discovery(network: str = None, custom_ports: str = None):
    """
    Descubrimiento completo: ONVIF + SSDP + TCP scan + credenciales + SNMP + NetBIOS + mDNS
    Timeout total ~30s (ONVIF 4s + SSDP 4s + mDNS 2s + scan 20s). Nunca bloquea el event loop.
    custom_ports: puertos extra separados por coma (ej: "554,8554,37777,9999")
    """
    if not network:
        network = _real_subnet_prefix()
    all_cameras = []
    all_hosts = []

    # 1. Descubrimiento pasivo multicast — con timeout individual
    try:
        onvif_cams = await asyncio.wait_for(onvif_discover(2.0), timeout=4.0)
    except (asyncio.TimeoutError, Exception) as e:
        onvif_cams = []
        print(f"[DISCOVER] ONVIF multicast falló (común en Android/Termux): {e}")

    try:
        ssdp_devices = await asyncio.wait_for(ssdp_discover(2.0), timeout=4.0)
    except (asyncio.TimeoutError, Exception) as e:
        ssdp_devices = []
        print(f"[DISCOVER] SSDP error: {e}")

    try:
        mdns_services = await asyncio.wait_for(asyncio.to_thread(mdns_query, 1.0), timeout=2.0)
    except (asyncio.TimeoutError, Exception) as e:
        mdns_services = []
        print(f"[DISCOVER] mDNS error: {e}")

    # 2. Escanear /24 en puertos clave — paralelo con semaphore y timeout por host
    ports_to_scan = [80, 81, 82, 88, 443, 554, 8000, 8080, 8081, 8554, 37777, 8900, 23, 22, 5000, 8888]
    # Agregar puertos personalizados del usuario
    if custom_ports:
        for p in custom_ports.split(","):
            p = p.strip()
            if p.isdigit() and int(p) not in ports_to_scan:
                ports_to_scan.append(int(p))
    semaphore = asyncio.Semaphore(50)

    async def check_host(ip: str):
        async with semaphore:
            host_data = {"ip": ip, "open_ports": [], "services": []}
            # TCP connect scan rápido con timeout por puerto
            for port in ports_to_scan:
                try:
                    fut = asyncio.open_connection(ip, port)
                    reader, writer = await asyncio.wait_for(fut, timeout=0.5)
                    host_data["open_ports"].append(port)
                    writer.close()
                    try: await writer.wait_closed()
                    except: pass
                    # Si es puerto de cámara (HTTP o RTSP), escanear a fondo
                    if port in [80, 81, 82, 88, 443, 8000, 8080, 8081, 37777, 8900]:
                        try:
                            cam = await asyncio.wait_for(scan_camera_full(ip, port), timeout=3.0)
                            if cam and (cam.get("accessible_urls") or cam.get("snapshot_url") or cam.get("rtsp_working")):
                                all_cameras.append(cam)
                        except (asyncio.TimeoutError, Exception):
                            pass
                    # Si es puerto RTSP (554/8554) o puerto personalizado, agregar como cámara RTSP-only
                    if port in [554, 8554] or (custom_ports and port in [int(p.strip()) for p in custom_ports.split(",") if p.strip().isdigit()]):
                        rtsp_url = f"rtsp://{ip}:{port}/"
                        # Evitar duplicados
                        if not any(c.get("ip") == ip for c in all_cameras):
                            all_cameras.append({
                                "ip": ip, "port": port, "brand": "generic",
                                "accessible_urls": [], "working_credentials": None,
                                "rtsp_working": rtsp_url, "snapshot_url": None,
                                "source": "rtsp-tcp-scan"
                            })
                        try:
                            cam = await asyncio.wait_for(scan_camera_full(ip, port), timeout=3.0)
                            if cam and (cam.get("accessible_urls") or cam.get("snapshot_url")):
                                all_cameras.append(cam)
                        except (asyncio.TimeoutError, Exception):
                            pass
                    # SSL en 443/8443
                    if port in [443, 8443]:
                        try:
                            ssl_info = await asyncio.wait_for(asyncio.to_thread(extract_ssl_info, ip, port), timeout=2.0)
                            host_data["ssl"] = ssl_info
                        except (asyncio.TimeoutError, Exception):
                            pass
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    pass

            # SNMP
            try:
                snmp = await asyncio.wait_for(asyncio.to_thread(snmp_probe, ip, "public", 1.5), timeout=3.0)
                if snmp: host_data["snmp"] = snmp
            except (asyncio.TimeoutError, Exception):
                pass

            # NetBIOS
            try:
                nb = await asyncio.wait_for(asyncio.to_thread(netbios_query, ip, 1.5), timeout=3.0)
                if nb: host_data["netbios"] = nb
            except (asyncio.TimeoutError, Exception):
                pass

            if host_data["open_ports"] or host_data.get("snmp") or host_data.get("netbios"):
                all_hosts.append(host_data)
                # Guardar en DB
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=1.0)
                    c = conn.cursor()
                    c.execute("""INSERT OR REPLACE INTO hosts_deep 
                        (ip, open_ports, snmp_info, netbios_info, mdns_info, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (ip, json.dumps(host_data["open_ports"]),
                         json.dumps(host_data.get("snmp")),
                         json.dumps(host_data.get("netbios")),
                         json.dumps([m for m in mdns_services if m.get("ip") == ip]),
                         datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                except Exception as db_err:
                    print(f"[DISCOVER] DB error para {ip}: {db_err}")

    # Chunking adaptativo: soporta cualquier CIDR sin saturar el celular.
    # Construye la lista de IPs desde el CIDR (no asume /24).
    import ipaddress as _ipa
    try:
        # network viene como prefijo (ej: "192.168.1") — convertir a CIDR
        net_str = network if "/" in network else f"{network}.0/24"
        net_obj = _ipa.ip_network(net_str, strict=False)
        all_ips = [str(h) for h in net_obj.hosts()]
    except Exception:
        all_ips = [f"{network}.{i}" for i in range(1, 255)]

    CHUNK_SIZE = 64  # 64 hosts por chunk para no saturar memoria
    task_group = []
    for chunk_start in range(0, len(all_ips), CHUNK_SIZE):
        chunk = all_ips[chunk_start:chunk_start + CHUNK_SIZE]
        for ip in chunk:
            task_group.append(asyncio.create_task(check_host(ip)))
        # Esperar este chunk antes de lanzar el siguiente
        try:
            await asyncio.wait_for(asyncio.gather(*task_group[-len(chunk):], return_exceptions=True), timeout=15.0)
        except asyncio.TimeoutError:
            print(f"[DISCOVER] Timeout en chunk {chunk_start}-{chunk_start + len(chunk)}, cancelando")
            for t in task_group[-len(chunk):]:
                if not t.done():
                    t.cancel()

    return {
        "onvif_found": len(onvif_cams),
        "ssdp_found": len(ssdp_devices),
        "mdns_found": len(mdns_services),
        "cameras": all_cameras,
        "hosts": all_hosts,
        "onvif_details": onvif_cams,
        "ssdp_details": ssdp_devices,
        "mdns_details": mdns_services,
        "partial": len(all_hosts) < 254
    }


@router.get("/cameras")
async def get_saved_cameras():
    """Recupera todas las cámaras guardadas en la DB"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM cameras ORDER BY last_seen DESC")
    rows = c.fetchall()
    conn.close()
    
    cameras = []
    for row in rows:
        cameras.append({
            "id": row[0], "ip": row[1], "port": row[2],
            "brand": row[3], "model": row[4],
            "rtsp_url": row[5], "snapshot_url": row[6],
            "credentials": row[7], "discovered": row[8],
            "last_seen": row[9], "vulnerable": row[10]
        })
    return {"cameras": cameras}


@router.get("/hosts")
async def get_saved_hosts():
    """Recupera todos los hosts guardados en la DB"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM hosts_deep ORDER BY last_seen DESC")
    rows = c.fetchall()
    conn.close()
    
    hosts = []
    for row in rows:
        hosts.append({
            "ip": row[0], "mac": row[1], "hostname": row[2],
            "os_guess": row[3], "open_ports": json.loads(row[4]) if row[4] else [],
            "ssl_info": json.loads(row[5]) if row[5] else None,
            "snmp_info": json.loads(row[6]) if row[6] else None,
            "upnp_info": json.loads(row[7]) if row[7] else None,
            "mdns_info": json.loads(row[8]) if row[8] else None,
            "netbios_info": json.loads(row[9]) if row[9] else None,
            "first_seen": row[10], "last_seen": row[11]
        })
    return {"hosts": hosts}


@router.post("/camera/scan")
async def scan_single_camera(ip: str, port: int = 80):
    """Escaneo individual de una cámara"""
    result = await scan_camera_full(ip, port)
    if result:
        return result
    raise HTTPException(status_code=404, detail="No se pudo escanear la cámara")


@router.delete("/cameras/{camera_id}")
async def delete_camera(camera_id: int):
    """Elimina una cámara de la DB"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": camera_id}
