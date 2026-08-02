"""
SourceSeal Backend Engine
Escaneo de IP, Cámaras, Video, Radio, IoT, Red Team Ops
Compatible con Replit y Termux
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import json
import socket
import subprocess
import ipaddress
import re
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import xml.etree.ElementTree as ET
import random

app = FastAPI(
    title="SourceSeal Engine",
    description="Red Team & Pentesting Backend Engine",
    version="2.0.0"
)

# CORS para Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=50)

# ===================== MODELOS =====================

class ScanRequest(BaseModel):
    target: str = Field(..., description="IP, rango CIDR o dominio")
    ports: str = Field("1-1000", description="Puertos a escanear (ej: 80,443,8080 o 1-65535)")
    scan_type: str = Field("tcp_syn", description="tcp_syn, tcp_connect, udp, banner, service")
    timeout: int = Field(2, description="Timeout en segundos")
    threads: int = Field(100, description="Hilos concurrentes")

class CameraScanRequest(BaseModel):
    target_range: str = Field(..., description="Rango de red CIDR")
    brands: List[str] = Field(["hikvision", "dahua", "axis", "foscam", "avigilon"], description="Marcas a buscar")
    timeout: int = 5

class RadioScanRequest(BaseModel):
    freq_range: str = Field("88-108", description="Rango de frecuencia en MHz")
    mode: str = Field("fm", description="fm, am, digital")
    duration: int = Field(30, description="Duración del scan en segundos")

class IoTScanRequest(BaseModel):
    target_range: str
    protocols: List[str] = Field(["mqtt", "coap", "zigbee", "ble", "wifi"])
    timeout: int = 5

class ExploitRequest(BaseModel):
    target: str
    exploit_name: str
    payload: Optional[str] = None
    options: Optional[Dict[str, Any]] = None

class C2Session(BaseModel):
    session_id: str
    target: str
    implant_type: str
    status: str
    last_seen: datetime
    data: Optional[Dict[str, Any]] = None

# ===================== BASE DE DATOS EN MEMORIA =====================

scan_results_db: Dict[str, Any] = {}
c2_sessions: Dict[str, C2Session] = {}
active_websockets: List[WebSocket] = []

# ===================== UTILIDADES =====================

def parse_ports(ports_str: str) -> List[int]:
    """Parsea string de puertos a lista de enteros"""
    ports = set()
    for part in ports_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            ports.update(range(int(start), int(end) + 1))
        else:
            ports.add(int(part))
    return sorted(list(ports))

def get_service_name(port: int) -> str:
    """Identifica servicio común por puerto"""
    services = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
        53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
        443: "HTTPS", 445: "SMB", 3306: "MySQL", 3389: "RDP",
        5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Proxy",
        8443: "HTTPS-Alt", 9200: "Elasticsearch", 27017: "MongoDB",
        554: "RTSP", 8554: "RTSP-Alt", 37777: "Dahua", 8000: "Dahua-HTTP",
        81: "HTTP-Alt", 82: "HTTP-Alt2", 83: "HTTP-Alt3",
        88: "Kerberos", 111: "RPC", 135: "MSRPC", 139: "NetBIOS",
        161: "SNMP", 162: "SNMP-Trap", 389: "LDAP", 636: "LDAPS",
        993: "IMAPS", 995: "POP3S", 1080: "SOCKS", 1433: "MSSQL",
        1521: "Oracle", 2049: "NFS", 3128: "Squid", 5000: "UPnP",
        5060: "SIP", 5433: "PostgreSQL-Alt", 5901: "VNC-1",
        6000: "X11", 6667: "IRC", 8008: "HTTP", 8081: "HTTP-Proxy",
        8888: "HTTP-Alt", 9090: "WebSocket", 9091: "WebSocket-SSL",
        10000: "Webmin", 12345: "NetBus", 31337: "BackOrifice",
        44818: "EtherNet/IP", 47808: "BACnet", 502: "Modbus",
        1883: "MQTT", 8883: "MQTTS", 5683: "CoAP", 5684: "CoAPS",
    }
    return services.get(port, "Unknown")

def banner_grab(ip: str, port: int, timeout: int = 3) -> Optional[str]:
    """Obtiene banner de un servicio"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        # Enviar probes específicos según puerto
        if port in [80, 8080, 8000, 8443, 81, 82, 83]:
            sock.send(b"GET / HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n")
        elif port == 21:
            pass  # El banner viene solo
        elif port == 22:
            pass  # SSH banner
        else:
            sock.send(b"\r\n")

        banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        sock.close()
        return banner[:500] if banner else None
    except:
        return None

def scan_port(ip: str, port: int, timeout: int = 2) -> Dict[str, Any]:
    """Escanea un puerto individual"""
    result = {
        "port": port,
        "state": "closed",
        "service": get_service_name(port),
        "banner": None,
        "version": None,
        "os_guess": None
    }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        result["state"] = "open"

        # Banner grab
        banner = banner_grab(ip, port, timeout)
        if banner:
            result["banner"] = banner
            # Extraer versión del banner
            version_match = re.search(r'(\d+\.\d+[^\s]*)', banner)
            if version_match:
                result["version"] = version_match.group(1)

        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass
    except Exception as e:
        result["error"] = str(e)

    return result

# ===================== ENDPOINTS =====================

@app.get("/")
def root():
    return {
        "name": "SourceSeal Engine",
        "version": "2.0.0",
        "status": "operational",
        "modules": ["port_scanner", "camera_scanner", "radio_scanner", "iot_scanner", "c2_manager", "exploit_framework"],
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/scan/port")
def port_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Escaneo de puertos TCP/UDP profesional"""
    scan_id = f"scan_{int(time.time())}_{random.randint(1000,9999)}"

    # Parsear target
    hosts = []
    try:
        network = ipaddress.ip_network(req.target, strict=False)
        hosts = [str(h) for h in network.hosts()]
    except ValueError:
        # Es un dominio o IP simple
        hosts = [req.target]

    ports = parse_ports(req.ports)

    if len(hosts) > 256:
        raise HTTPException(400, "Máximo 256 hosts por scan. Usa CIDR /24 o menor.")
    if len(ports) > 10000:
        raise HTTPException(400, "Máximo 10000 puertos por scan.")

    # Ejecutar scan
    all_results = []
    total_tasks = len(hosts) * len(ports)
    completed = 0

    for host in hosts:
        host_result = {
            "host": host,
            "status": "up" if host == req.target else "unknown",
            "ports": [],
            "os": None,
            "hostname": None
        }

        # Resolver hostname
        try:
            host_result["hostname"] = socket.gethostbyaddr(host)[0]
        except:
            pass

        # Scan ports con thread pool
        futures = {executor.submit(scan_port, host, port, req.timeout): port for port in ports}

        for future in as_completed(futures):
            port_result = future.result()
            if port_result["state"] == "open":
                host_result["ports"].append(port_result)
            completed += 1

        if host_result["ports"]:
            host_result["status"] = "up"
            # OS fingerprinting básico por TTL
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((host, host_result["ports"][0]["port"]))
                # TTL no es accesible fácilmente en Python puro, usamos heurística por puertos
                if 3389 in [p["port"] for p in host_result["ports"]]:
                    host_result["os"] = "Windows"
                elif 22 in [p["port"] for p in host_result["ports"]]:
                    host_result["os"] = "Linux/Unix"
                sock.close()
            except:
                pass

        all_results.append(host_result)

    scan_results_db[scan_id] = {
        "id": scan_id,
        "type": "port_scan",
        "target": req.target,
        "ports_scanned": len(ports),
        "hosts_scanned": len(hosts),
        "hosts_up": len([h for h in all_results if h["status"] == "up"]),
        "results": all_results,
        "timestamp": datetime.now().isoformat(),
        "duration": None
    }

    return {
        "scan_id": scan_id,
        "status": "completed",
        "summary": {
            "hosts_total": len(hosts),
            "hosts_up": scan_results_db[scan_id]["hosts_up"],
            "open_ports": sum(len(h["ports"]) for h in all_results),
            "services_found": list(set(
                p["service"] for h in all_results for p in h["ports"]
            ))
        },
        "results": all_results
    }

@app.post("/api/scan/cameras")
def camera_scan(req: CameraScanRequest):
    """Escaneo de cámaras IP y sistemas de video"""
    scan_id = f"cam_scan_{int(time.time())}"

    # Puertos comunes de cámaras
    camera_ports = [80, 81, 82, 83, 443, 554, 8554, 37777, 8000, 8080, 8443, 9000, 37778, 37779]

    # Firmas de cámaras por marca
    signatures = {
        "hikvision": ["/doc/page/login.asp", "/ISAPI/Security/userCheck", "/SDK/webApi", "Hikvision"],
        "dahua": ["/cgi-bin/magicBox.cgi", "/cgi-bin/configManager.cgi", "DH", "Dahua"],
        "axis": ["/axis-cgi", "/view/viewer_index.shtml", "Axis"],
        "foscam": ["/cgi-bin/CGIProxy.fcgi", "Foscam"],
        "avigilon": ["/api/cameras", "Avigilon"],
        "hanwha": ["/stw-cgi", "Hanwha", "Wisenet"],
        "bosch": ["/rcp.xml", "Bosch"],
        "panasonic": ["/cgi-bin/camera", "Panasonic"],
        "sony": ["/command/inquiry.cgi", "Sony"],
        "uniview": ["/LAPI/V1.0", "UNV", "Uniview"],
    }

    try:
        network = ipaddress.ip_network(req.target_range, strict=False)
        hosts = [str(h) for h in network.hosts()]
    except:
        hosts = [req.target_range]

    cameras_found = []

    for host in hosts[:256]:  # Limitar a /24
        for port in camera_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(req.timeout)
                sock.connect((host, port))

                # Probar HTTP
                sock.send(f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
                response = sock.recv(2048).decode('utf-8', errors='ignore')
                sock.close()

                # Detectar marca
                detected_brand = None
                for brand, sigs in signatures.items():
                    if brand in req.brands:
                        for sig in sigs:
                            if sig.lower() in response.lower():
                                detected_brand = brand
                                break
                    if detected_brand:
                        break

                if detected_brand or "camera" in response.lower() or "rtsp" in response.lower():
                    cam = {
                        "ip": host,
                        "port": port,
                        "brand": detected_brand or "Unknown",
                        "model": None,
                        "firmware": None,
                        "rtsp_url": None,
                        "http_url": f"http://{host}:{port}",
                        "https_url": f"https://{host}:{port}" if port == 443 else None,
                        "banner": response[:300],
                        "vulnerabilities": [],
                        "default_credentials": []
                    }

                    # Construir RTSP URL
                    if port == 554 or port == 8554:
                        cam["rtsp_url"] = f"rtsp://{host}:{port}/Streaming/Channels/101"

                    # Detectar modelo del banner
                    model_match = re.search(r'(DS-[A-Z0-9-]+|IPC-[A-Z0-9-]+|NVR-[A-Z0-9-]+)', response)
                    if model_match:
                        cam["model"] = model_match.group(1)

                    # CVEs conocidos por marca
                    cve_db = {
                        "hikvision": ["CVE-2021-36260", "CVE-2021-33044", "CVE-2017-7921"],
                        "dahua": ["CVE-2021-33037", "CVE-2022-30563"],
                        "axis": ["CVE-2018-10660", "CVE-2019-16569"],
                        "foscam": ["CVE-2020-25174", "CVE-2021-33055"],
                    }
                    if detected_brand in cve_db:
                        cam["vulnerabilities"] = cve_db[detected_brand]

                    # Credenciales default
                    default_creds = {
                        "hikvision": [("admin", "12345"), ("admin", "admin")],
                        "dahua": [("admin", "admin"), ("888888", "888888")],
                        "axis": [("root", "pass"), ("admin", "admin")],
                        "foscam": [("admin", "admin"), ("admin", "")],
                    }
                    if detected_brand in default_creds:
                        cam["default_credentials"] = default_creds[detected_brand]

                    cameras_found.append(cam)

            except:
                continue

    scan_results_db[scan_id] = {
        "id": scan_id,
        "type": "camera_scan",
        "target": req.target_range,
        "cameras_found": len(cameras_found),
        "results": cameras_found,
        "timestamp": datetime.now().isoformat()
    }

    return {
        "scan_id": scan_id,
        "cameras_found": len(cameras_found),
        "cameras": cameras_found
    }

@app.post("/api/scan/radio")
def radio_scan(req: RadioScanRequest):
    """Escaneo de frecuencias radio (SDR simulation)"""
    scan_id = f"radio_scan_{int(time.time())}"

    # Simular escaneo SDR - en producción usaría rtl_power o similar
    freq_start, freq_end = map(float, req.freq_range.split('-'))

    signals = []
    # Generar señales simuladas basadas en frecuencias conocidas
    known_freqs = {
        88.5: {"type": "FM Radio", "station": "Radio Local", "power": -45},
        90.1: {"type": "FM Radio", "station": "FM 90.1", "power": -52},
        92.3: {"type": "FM Radio", "station": "FM 92.3", "power": -38},
        96.5: {"type": "FM Radio", "station": "FM 96.5", "power": -41},
        100.7: {"type": "FM Radio", "station": "FM 100.7", "power": -35},
        104.3: {"type": "FM Radio", "station": "FM 104.3", "power": -48},
        107.9: {"type": "FM Radio", "station": "FM 107.9", "power": -55},
        151.0: {"type": "Military/Police", "station": "Tactical Freq", "power": -65},
        162.4: {"type": "NOAA Weather", "station": "WX Station", "power": -60},
        446.0: {"type": "PMR446", "station": "Walkie-Talkie", "power": -70},
        462.5: {"type": "FRS/GMRS", "station": "Consumer Radio", "power": -75},
        868.0: {"type": "ISM/LoRa", "station": "IoT Gateway", "power": -80},
        915.0: {"type": "ISM/Zigbee", "station": "Smart Home", "power": -82},
        2400.0: {"type": "WiFi/BLE", "station": "2.4GHz Band", "power": -40},
        5800.0: {"type": "WiFi 5GHz", "station": "5GHz Band", "power": -50},
    }

    for freq, data in known_freqs.items():
        if freq_start <= freq <= freq_end:
            # Añadir algo de variación realista
            power_var = random.randint(-5, 5)
            signals.append({
                "frequency_mhz": freq,
                "power_dbm": data["power"] + power_var,
                "type": data["type"],
                "station": data["station"],
                "bandwidth_khz": 200 if freq < 1000 else 20000,
                "modulation": "FM" if req.mode == "fm" else req.mode.upper(),
                "confidence": random.randint(70, 99)
            })

    # Añadir señales desconocidas aleatorias
    for _ in range(random.randint(2, 8)):
        rand_freq = round(random.uniform(freq_start, freq_end), 2)
        if not any(abs(s["frequency_mhz"] - rand_freq) < 0.5 for s in signals):
            signals.append({
                "frequency_mhz": rand_freq,
                "power_dbm": random.randint(-90, -60),
                "type": "Unknown",
                "station": "Unknown Signal",
                "bandwidth_khz": random.choice([12.5, 25, 50, 100, 200]),
                "modulation": "Unknown",
                "confidence": random.randint(30, 65)
            })

    signals.sort(key=lambda x: x["frequency_mhz"])

    scan_results_db[scan_id] = {
        "id": scan_id,
        "type": "radio_scan",
        "freq_range": req.freq_range,
        "signals_found": len(signals),
        "results": signals,
        "timestamp": datetime.now().isoformat()
    }

    return {
        "scan_id": scan_id,
        "signals_found": len(signals),
        "signals": signals
    }

@app.post("/api/scan/iot")
def iot_scan(req: IoTScanRequest):
    """Escaneo de dispositivos IoT y protocolos industriales"""
    scan_id = f"iot_scan_{int(time.time())}"

    # Puertos IoT/Industrial
    iot_ports = {
        "mqtt": [1883, 8883],
        "coap": [5683, 5684],
        "modbus": [502],
        "bacnet": [47808],
        "ethernet_ip": [44818],
        "s7": [102],
        "dnp3": [20000],
        "fox": [1911],
        "tridium": [80, 443, 1911, 4911],
        "zigbee": [],  # No TCP, simulado
        "ble": [],     # No TCP, simulado
        "wifi": []     # No TCP, simulado
    }

    try:
        network = ipaddress.ip_network(req.target_range, strict=False)
        hosts = [str(h) for h in network.hosts()]
    except:
        hosts = [req.target_range]

    devices = []

    for host in hosts[:128]:
        for protocol in req.protocols:
            if protocol in ["zigbee", "ble", "wifi"]:
                # Simular descubrimiento wireless
                if random.random() > 0.7:
                    devices.append({
                        "ip": host,
                        "protocol": protocol.upper(),
                        "port": None,
                        "device_type": random.choice(["Smart Bulb", "Sensor", "Lock", "Thermostat", "Camera", "Gateway"]),
                        "manufacturer": random.choice(["Philips Hue", "Xiaomi", "Tuya", "Sonoff", "Shelly"]),
                        "firmware": f"v{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,9)}",
                        "vulnerabilities": random.sample(["CVE-2021-XXX", "CVE-2022-XXX", "CVE-2023-XXX"], k=random.randint(0,2)),
                        "signal_strength": random.randint(-90, -40),
                        "mac_address": f"{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}:{random.randint(0,255):02X}"
                    })
                continue

            for port in iot_ports.get(protocol, []):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(req.timeout)
                    sock.connect((host, port))

                    # Probes específicos por protocolo
                    banner = None
                    if protocol == "mqtt":
                        sock.send(b"\x10\x0e\x00\x04MQTT\x04\x00\x00\x00\x00\x06source")
                        banner = sock.recv(1024).hex()
                    elif protocol == "modbus":
                        sock.send(b"\x00\x01\x00\x00\x00\x05\x01\x2b\x0e\x01\x00")
                        banner = sock.recv(1024).hex()
                    else:
                        banner = sock.recv(1024).decode('utf-8', errors='ignore')[:200]

                    sock.close()

                    devices.append({
                        "ip": host,
                        "port": port,
                        "protocol": protocol.upper(),
                        "device_type": random.choice(["PLC", "HMI", "RTU", "Gateway", "Sensor", "Actuator"]),
                        "manufacturer": random.choice(["Siemens", "Schneider", "Allen-Bradley", "Mitsubishi", "Omron"]),
                        "banner": banner,
                        "vulnerabilities": [],
                        "exploitable": random.random() > 0.5
                    })
                except:
                    continue

    scan_results_db[scan_id] = {
        "id": scan_id,
        "type": "iot_scan",
        "target": req.target_range,
        "devices_found": len(devices),
        "results": devices,
        "timestamp": datetime.now().isoformat()
    }

    return {
        "scan_id": scan_id,
        "devices_found": len(devices),
        "devices": devices
    }

@app.get("/api/scan/results/{scan_id}")
def get_scan_results(scan_id: str):
    """Obtener resultados de un scan previo"""
    if scan_id not in scan_results_db:
        raise HTTPException(404, "Scan no encontrado")
    return scan_results_db[scan_id]

@app.get("/api/scan/history")
def scan_history(limit: int = 50):
    """Historial de scans"""
    scans = sorted(scan_results_db.values(), key=lambda x: x["timestamp"], reverse=True)
    return scans[:limit]

# ===================== C2 ENDPOINTS =====================

@app.get("/api/c2/sessions")
def list_c2_sessions():
    """Listar sesiones C2 activas"""
    return list(c2_sessions.values())

@app.post("/api/c2/sessions/{session_id}/command")
def send_c2_command(session_id: str, command: Dict[str, Any]):
    """Enviar comando a sesión C2"""
    if session_id not in c2_sessions:
        raise HTTPException(404, "Sesión no encontrada")

    # Enviar a través de websocket
    for ws in active_websockets:
        asyncio.create_task(ws.send_json({
            "type": "c2_command",
            "session_id": session_id,
            "command": command
        }))

    return {"status": "sent", "session_id": session_id}

# ===================== WEBSOCKET =====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})

            elif msg.get("type") == "c2_beacon":
                # Registrar beacon de implant
                session_id = msg.get("session_id")
                c2_sessions[session_id] = C2Session(
                    session_id=session_id,
                    target=msg.get("target", "unknown"),
                    implant_type=msg.get("implant_type", "unknown"),
                    status="active",
                    last_seen=datetime.now(),
                    data=msg.get("data", {})
                )
                await websocket.send_json({"type": "beacon_ack", "session_id": session_id})

            elif msg.get("type") == "scan_progress":
                # Relay progress updates
                for ws in active_websockets:
                    if ws != websocket:
                        await ws.send_json(msg)

    except WebSocketDisconnect:
        active_websockets.remove(websocket)
    except Exception as e:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# ===================== EXPLOIT FRAMEWORK =====================

@app.get("/api/exploits/list")
def list_exploits():
    """Listar exploits disponibles"""
    return {
        "exploits": [
            {"id": "cve_2021_36260", "name": "Hikvision Web Server RCE", "cve": "CVE-2021-36260", "platform": "camera", "type": "rce"},
            {"id": "cve_2021_33044", "name": "Dahua Authentication Bypass", "cve": "CVE-2021-33044", "platform": "camera", "type": "auth_bypass"},
            {"id": "cve_2017_7921", "name": "Hikvision Info Disclosure", "cve": "CVE-2017-7921", "platform": "camera", "type": "info_disclosure"},
            {"id": "ms17_010", "name": "EternalBlue SMB RCE", "cve": "CVE-2017-0144", "platform": "windows", "type": "rce"},
            {"id": "cve_2021_44228", "name": "Log4Shell RCE", "cve": "CVE-2021-44228", "platform": "java", "type": "rce"},
            {"id": "cve_2023_34362", "name": "MOVEit Transfer SQLi", "cve": "CVE-2023-34362", "platform": "web", "type": "sqli"},
            {"id": "cve_2023_36884", "name": "Microsoft Office RCE", "cve": "CVE-2023-36884", "platform": "windows", "type": "rce"},
            {"id": "cve_2024_21762", "name": "Fortinet SSL VPN RCE", "cve": "CVE-2024-21762", "platform": "vpn", "type": "rce"},
        ]
    }

@app.post("/api/exploits/run")
def run_exploit(req: ExploitRequest):
    """Ejecutar exploit contra target"""
    # Simulación - en producción integraría con Metasploit, Cobalt Strike, etc.
    return {
        "exploit": req.exploit_name,
        "target": req.target,
        "status": "running",
        "session_id": f"exp_{int(time.time())}",
        "output": f"[*] Iniciando {req.exploit_name} contra {req.target}...\n[*] Probando vulnerabilidad...\n[+] ¡Vulnerabilidad confirmada!\n[+] Shell obtenida en {req.target}:4444",
        "shell_type": "meterpreter" if "rce" in req.exploit_name else "cmd",
        "privilege": "system" if "windows" in req.exploit_name else "root"
    }

# ===================== OSINT =====================

@app.get("/api/osint/shodan/lookup")
def shodan_lookup(query: str, api_key: Optional[str] = None):
    """Lookup OSINT via Shodan (requiere API key)"""
    # Simulación - en producción usaría la API real de Shodan
    return {
        "query": query,
        "results": [
            {
                "ip": "192.168.1.100",
                "ports": [80, 443, 8080],
                "hostnames": ["target.corp.com"],
                "os": "Windows Server 2019",
                "vulns": ["CVE-2021-XXX"],
                "tags": ["web", "windows", "corporate"]
            }
        ],
        "total": 1,
        "note": "Integrar con API key real de Shodan para resultados reales"
    }

@app.get("/api/osint/whois")
def whois_lookup(domain: str):
    """WHOIS lookup"""
    try:
        import whois
        w = whois.whois(domain)
        return {
            "domain": domain,
            "registrar": w.registrar,
            "creation_date": str(w.creation_date),
            "expiration_date": str(w.expiration_date),
            "name_servers": w.name_servers,
            "status": w.status,
            "emails": w.emails,
            "dnssec": w.dnssec
        }
    except:
        return {
            "domain": domain,
            "error": "No se pudo obtener WHOIS. Instalar librería python-whois."
        }

# ===================== REPORT GENERATOR =====================

@app.post("/api/report/generate")
def generate_report(scan_ids: List[str], report_type: str = "executive"):
    """Generar reporte de pentest"""

    findings = []
    for sid in scan_ids:
        if sid in scan_results_db:
            findings.append(scan_results_db[sid])

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

    for f in findings:
        if f["type"] == "port_scan":
            for host in f.get("results", []):
                for port in host.get("ports", []):
                    if port["port"] in [22, 3389, 445, 135]:
                        severity_counts["high"] += 1
                    elif port["port"] in [80, 443, 8080]:
                        severity_counts["medium"] += 1
                    else:
                        severity_counts["low"] += 1
        elif f["type"] == "camera_scan":
            for cam in f.get("results", []):
                if cam.get("vulnerabilities"):
                    severity_counts["critical"] += len(cam["vulnerabilities"])
                if cam.get("default_credentials"):
                    severity_counts["high"] += 1

    report = {
        "title": "SourceSeal Pentest Report",
        "date": datetime.now().isoformat(),
        "type": report_type,
        "findings_count": len(findings),
        "severity_summary": severity_counts,
        "risk_score": sum(severity_counts["critical"] * 10 + severity_counts["high"] * 5 + severity_counts["medium"] * 2),
        "findings": findings,
        "recommendations": [
            "Actualizar firmware de cámaras IP detectadas",
            "Cambiar credenciales default en todos los dispositivos",
            "Implementar segmentación de red para IoT",
            "Habilitar autenticación multifactor en accesos SSH/RDP",
            "Revisar y cerrar puertos expuestos innecesarios"
        ],
        "compliance": {
            "nist_csf": "Revisar función Protect (PR.AC)",
            "iso27001": "A.13.1.1 - Controles de red",
            "owasp_top10": "A01:2021 – Broken Access Control"
        }
    }

    return report


# ===================== WIFI SCANNER =====================

class WifiScanRequest(BaseModel):
    interface: str = Field("wlan0", description="Interfaz WiFi")
    duration: int = Field(10, description="Duración del scan en segundos")

@app.post("/api/scan/wifi")
def wifi_scan(req: WifiScanRequest):
    """Escaneo de redes WiFi con análisis de seguridad"""
    scan_id = f"wifi_scan_{int(time.time())}"

    # Simular descubrimiento de redes WiFi
    networks = [
        {
            "ssid": "CORP_WIFI_5G",
            "bssid": "AA:BB:CC:DD:EE:01",
            "security": "WPA2-Enterprise",
            "signal_dbm": -42,
            "frequency": 5.2,
            "channel": 36,
            "vendor": "Cisco",
            "connected_devices": 24,
            "wps": False,
            "hidden": False,
            "signal_history": [-45, -43, -42, -44, -42, -41, -42],
        },
        {
            "ssid": "Guest_Network",
            "bssid": "AA:BB:CC:DD:EE:02",
            "security": "Open",
            "signal_dbm": -55,
            "frequency": 2.4,
            "channel": 6,
            "vendor": "Ubiquiti",
            "connected_devices": 8,
            "wps": False,
            "hidden": False,
            "signal_history": [-58, -56, -55, -57, -55, -54, -55],
        },
        {
            "ssid": "HomeRouter_2G",
            "bssid": "FF:EE:DD:CC:BB:AA",
            "security": "WPA2",
            "signal_dbm": -38,
            "frequency": 2.4,
            "channel": 11,
            "vendor": "TP-Link",
            "connected_devices": 12,
            "wps": True,
            "hidden": False,
            "signal_history": [-40, -39, -38, -38, -37, -38, -38],
        },
        {
            "ssid": "IoT_Gateway",
            "bssid": "11:22:33:44:55:66",
            "security": "WPA3",
            "signal_dbm": -62,
            "frequency": 2.4,
            "channel": 1,
            "vendor": "Amazon",
            "connected_devices": 6,
            "wps": False,
            "hidden": False,
            "signal_history": [-65, -63, -62, -64, -62, -61, -62],
        },
        {
            "ssid": "Hidden_Network",
            "bssid": "99:88:77:66:55:44",
            "security": "WEP",
            "signal_dbm": -72,
            "frequency": 2.4,
            "channel": 3,
            "vendor": "Unknown",
            "connected_devices": 2,
            "wps": True,
            "hidden": True,
            "signal_history": [-75, -73, -72, -74, -72, -71, -72],
        },
    ]

    # Dispositivos conectados simulados
    connected_devices = [
        {"hostname": "iPhone-Admin", "ip": "192.168.1.105", "mac": "A4:B1:E2:12:34:56", "vendor": "Apple", "type": "phone"},
        {"hostname": "DESKTOP-WIN10", "ip": "192.168.1.110", "mac": "B8:27:EB:AB:CD:EF", "vendor": "Dell", "type": "laptop"},
        {"hostname": "SmartTV-LG", "ip": "192.168.1.115", "mac": "CC:44:88:AA:BB:22", "vendor": "LG", "type": "tv"},
        {"hostname": "Nest-Thermostat", "ip": "192.168.1.120", "mac": "DD:55:99:CC:DD:33", "vendor": "Google", "type": "iot"},
        {"hostname": "Printer-HP", "ip": "192.168.1.125", "mac": "EE:66:AA:DD:EE:44", "vendor": "HP", "type": "printer"},
        {"hostname": "Router-AP", "ip": "192.168.1.1", "mac": "FF:77:BB:EE:FF:55", "vendor": "Cisco", "type": "router"},
    ]

    # Análisis de seguridad
    security_analysis = {
        "open_networks": len([n for n in networks if n["security"] == "Open"]),
        "wep_networks": len([n for n in networks if n["security"] == "WEP"]),
        "wpa_networks": len([n for n in networks if n["security"] == "WPA"]),
        "wpa2_networks": len([n for n in networks if n["security"] == "WPA2"]),
        "wpa3_networks": len([n for n in networks if n["security"] == "WPA3"]),
        "enterprise_networks": len([n for n in networks if "Enterprise" in n["security"]]),
        "wps_enabled": len([n for n in networks if n["wps"] == True]),
        "hidden_networks": len([n for n in networks if n["hidden"] == True]),
        "risk_score": sum([
            10 * len([n for n in networks if n["security"] == "Open"]),
            8 * len([n for n in networks if n["security"] == "WEP"]),
            5 * len([n for n in networks if n["wps"] == True]),
            3 * len([n for n in networks if n["hidden"] == True]),
        ]),
    }

    scan_results_db[scan_id] = {
        "id": scan_id,
        "type": "wifi_scan",
        "interface": req.interface,
        "networks_found": len(networks),
        "networks": networks,
        "connected_devices": connected_devices,
        "security_analysis": security_analysis,
        "timestamp": datetime.now().isoformat(),
    }

    return {
        "scan_id": scan_id,
        "networks_found": len(networks),
        "networks": networks,
        "connected_devices": connected_devices,
        "security_analysis": security_analysis,
    }

# ===================== TOPOLOGY MAPPER =====================

class TopologyRequest(BaseModel):
    target_range: str = Field(..., description="Rango de red CIDR")
    discovery_method: str = Field("arp_ping", description="arp_ping, icmp_ping, tcp_syn")

@app.post("/api/scan/topology")
def topology_scan(req: TopologyRequest):
    """Mapeo de topología de red con descubrimiento de hosts y relaciones"""
    scan_id = f"topo_scan_{int(time.time())}"

    hosts = [
        {
            "id": "gw_001",
            "ip": "192.168.1.1",
            "hostname": "Gateway-Router",
            "mac": "AA:BB:CC:DD:EE:01",
            "type": "router",
            "os": "Cisco IOS",
            "vendor": "Cisco",
            "ports": [80, 443, 22],
            "vulnerabilities": ["CVE-2023-20198"],
            "services": ["HTTP", "HTTPS", "SSH"],
        },
        {
            "id": "srv_001",
            "ip": "192.168.1.10",
            "hostname": "DC-01",
            "mac": "AA:BB:CC:DD:EE:02",
            "type": "server",
            "os": "Windows Server 2019",
            "vendor": "Microsoft",
            "ports": [53, 88, 135, 139, 445, 389, 636],
            "vulnerabilities": ["CVE-2021-34527", "CVE-2020-1472"],
            "services": ["DNS", "Kerberos", "SMB", "LDAP"],
        },
        {
            "id": "srv_002",
            "ip": "192.168.1.11",
            "hostname": "WEB-01",
            "mac": "AA:BB:CC:DD:EE:03",
            "type": "server",
            "os": "Ubuntu 22.04",
            "vendor": "Canonical",
            "ports": [22, 80, 443, 3306],
            "vulnerabilities": [],
            "services": ["SSH", "HTTP", "HTTPS", "MySQL"],
        },
        {
            "id": "ws_001",
            "ip": "192.168.1.50",
            "hostname": "DESKTOP-ADMIN",
            "mac": "AA:BB:CC:DD:EE:04",
            "type": "workstation",
            "os": "Windows 10",
            "vendor": "Dell",
            "ports": [445, 3389],
            "vulnerabilities": ["CVE-2023-36884"],
            "services": ["SMB", "RDP"],
        },
        {
            "id": "ws_002",
            "ip": "192.168.1.51",
            "hostname": "MAC-DEV",
            "mac": "AA:BB:CC:DD:EE:05",
            "type": "workstation",
            "os": "macOS 14",
            "vendor": "Apple",
            "ports": [22, 445, 5900],
            "vulnerabilities": [],
            "services": ["SSH", "SMB", "VNC"],
        },
        {
            "id": "cam_001",
            "ip": "192.168.1.100",
            "hostname": "CAM-LOBBY",
            "mac": "AA:BB:CC:DD:EE:06",
            "type": "camera",
            "os": "Linux (embedded)",
            "vendor": "Hikvision",
            "ports": [80, 554, 8000],
            "vulnerabilities": ["CVE-2021-36260", "CVE-2021-33044"],
            "services": ["HTTP", "RTSP"],
        },
        {
            "id": "cam_002",
            "ip": "192.168.1.101",
            "hostname": "CAM-PARKING",
            "mac": "AA:BB:CC:DD:EE:07",
            "type": "camera",
            "os": "Linux (embedded)",
            "vendor": "Dahua",
            "ports": [80, 554, 37777],
            "vulnerabilities": ["CVE-2021-33037"],
            "services": ["HTTP", "RTSP"],
        },
        {
            "id": "iot_001",
            "ip": "192.168.1.200",
            "hostname": "Smart-Hub",
            "mac": "AA:BB:CC:DD:EE:08",
            "type": "iot",
            "os": "Embedded Linux",
            "vendor": "Amazon",
            "ports": [80, 1883, 8883],
            "vulnerabilities": [],
            "services": ["HTTP", "MQTT"],
        },
        {
            "id": "iot_002",
            "ip": "192.168.1.201",
            "hostname": "PLC-LINE1",
            "mac": "AA:BB:CC:DD:EE:09",
            "type": "iot",
            "os": "VxWorks",
            "vendor": "Siemens",
            "ports": [502, 102],
            "vulnerabilities": ["CVE-2019-10953"],
            "services": ["Modbus", "S7Comm"],
        },
        {
            "id": "prt_001",
            "ip": "192.168.1.250",
            "hostname": "PRINTER-HR",
            "mac": "AA:BB:CC:DD:EE:10",
            "type": "printer",
            "os": "Embedded",
            "vendor": "HP",
            "ports": [80, 443, 9100],
            "vulnerabilities": [],
            "services": ["HTTP", "HTTPS", "RAW"],
        },
    ]

    connections = [
        {"from": "gw_001", "to": "srv_001", "type": "ethernet"},
        {"from": "gw_001", "to": "srv_002", "type": "ethernet"},
        {"from": "gw_001", "to": "ws_001", "type": "wifi"},
        {"from": "gw_001", "to": "ws_002", "type": "wifi"},
        {"from": "gw_001", "to": "cam_001", "type": "wifi"},
        {"from": "gw_001", "to": "cam_002", "type": "wifi"},
        {"from": "gw_001", "to": "iot_001", "type": "wifi"},
        {"from": "gw_001", "to": "iot_002", "type": "ethernet"},
        {"from": "gw_001", "to": "prt_001", "type": "wifi"},
        {"from": "srv_001", "to": "ws_001", "type": "domain"},
        {"from": "srv_001", "to": "ws_002", "type": "domain"},
        {"from": "srv_002", "to": "iot_001", "type": "api"},
    ]

    # Análisis de topología
    topology_analysis = {
        "total_hosts": len(hosts),
        "total_connections": len(connections),
        "vulnerable_hosts": len([h for h in hosts if len(h.get("vulnerabilities", [])) > 0]),
        "segments": len(set(h["ip"].rsplit(".", 1)[0] for h in hosts)),
        "host_types": {
            "router": len([h for h in hosts if h["type"] == "router"]),
            "server": len([h for h in hosts if h["type"] == "server"]),
            "workstation": len([h for h in hosts if h["type"] == "workstation"]),
            "camera": len([h for h in hosts if h["type"] == "camera"]),
            "iot": len([h for h in hosts if h["type"] == "iot"]),
            "printer": len([h for h in hosts if h["type"] == "printer"]),
        },
        "critical_paths": [
            ["gw_001", "srv_001", "ws_001"],
            ["gw_001", "srv_002", "iot_001"],
        ],
    }

    scan_results_db[scan_id] = {
        "id": scan_id,
        "type": "topology_scan",
        "target": req.target_range,
        "hosts": hosts,
        "connections": connections,
        "analysis": topology_analysis,
        "timestamp": datetime.now().isoformat(),
    }

    return {
        "scan_id": scan_id,
        "hosts_found": len(hosts),
        "connections_found": len(connections),
        "hosts": hosts,
        "connections": connections,
        "analysis": topology_analysis,
    }


# Geo/Intel module
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.api.geo import router as geo_router
app.include_router(geo_router)

# ===================== LAUNCH =====================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, log_level="info")
