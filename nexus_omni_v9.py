#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS OMNI-SENTIENT v9.0 — Plataforma Cognitiva de Red
Autor: Harold Paredes / SourceSeal Global Protocol
Arquitectura: Predictiva, Adaptativa, Auto-Reparable.

v9.1 — Datos reales:
  - MAC real desde tabla ARP del sistema (ip neigh / arp -n)
  - Vendor por prefijo OUI (tabla parcial, ampliable)
  - Hostname real por DNS inverso
  - Geolocalización real SOLO para IPs públicas (ip-api.com, sin API key)
  - IPs privadas NO se geolocalizan con coordenadas falsas — se marcan
    is_private=True y se muestran en el panel de red local, no en el mapa
  - Eventos reales (anomalías/adaptaciones) expuestos via /api/events
"""

import asyncio
import json
import hashlib
import sqlite3
import subprocess
import ipaddress
import os
import sys
import time
import random
import math
import re
import socket
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from nexus_credentials import ensure_nexus_credentials
try:
    import aiohttp
except ImportError:
    # El motor puede escanear y servir su API sin alertas Telegram ni geo-IP real.
    aiohttp = None
from io import BytesIO

# ============================================================
# CONFIGURACIÓN NEURAL
# ============================================================
RESET_CREDENTIALS = "--reset-credentials" in sys.argv[1:]
NEXUS_CREDENTIALS = ensure_nexus_credentials(reset=RESET_CREDENTIALS)

if RESET_CREDENTIALS:
    print("[NEXUS] Credenciales rotadas en .env. Reinicia el servicio para aplicar el nuevo acceso.", flush=True)
    raise SystemExit(0)

CONFIG = {
    "db_path": os.environ.get("NEXUS_DB", "nexus_omni.db"),
    "ports_critical": [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1433, 1521, 3306, 3389, 5432, 5900, 8080, 8443, 8888, 37777, 34567, 554],
    "ports_common": [80, 443, 8080, 8000, 554],

    # Umbrales de IA
    "anomaly_threshold": 3, # Cambios necesarios para alertar
    "prediction_window": 5, # Escaneos históricos para predecir

    # Modos Adaptativos
    "modes": {
        "passive": {"timeout": 2.0, "concurrent": 2, "delay": 1.0},
        "stealth": {"timeout": 1.2, "concurrent": 10, "delay": 0.2},
        "active": {"timeout": 0.5, "concurrent": 40, "delay": 0.05},
        "frenzy": {"timeout": 0.2, "concurrent": 80, "delay": 0.01} # Solo si se detecta amenaza alta
    },

    "base_coords": {"lat": 4.7110, "lon": -74.0721},
    "auth_user": NEXUS_CREDENTIALS.user,
    "auth_pass": NEXUS_CREDENTIALS.password,
}

# ============================================================
# ENRIQUECIMIENTO DE DATOS REALES
# ============================================================

# Tabla OUI parcial (prefijos MAC -> fabricante). Datos públicos IEEE.
# No es exhaustiva — dispositivos no listados devuelven "Desconocido"
# en vez de inventar un fabricante. Ampliar según necesidad.
MAC_VENDOR_PREFIXES = {
    "B8:27:EB": "Raspberry Pi Foundation", "DC:A6:32": "Raspberry Pi Foundation",
    "E4:5F:01": "Raspberry Pi Foundation",
    "24:0A:C4": "Espressif (ESP32/ESP8266)", "30:AE:A4": "Espressif (ESP32/ESP8266)",
    "3C:71:BF": "Espressif (ESP32/ESP8266)", "68:C6:3A": "Espressif (ESP32/ESP8266)",
    "AC:67:B2": "Espressif (ESP32/ESP8266)",
    "50:C7:BF": "TP-Link", "98:DA:C4": "TP-Link", "EC:08:6B": "TP-Link",
    "5C:0A:5B": "Samsung", "78:1F:DB": "Samsung",
    "00:E0:FC": "Huawei", "48:5D:60": "Huawei",
    "34:CE:00": "Xiaomi", "64:09:80": "Xiaomi",
    "68:37:E9": "Amazon", "FC:65:DE": "Amazon",
    "54:60:09": "Google", "F4:F5:D8": "Google",
    "44:19:B6": "Hikvision", "BC:AD:28": "Hikvision",
    "3C:EF:8C": "Dahua", "9C:8E:CD": "Dahua",
    "24:5A:4C": "Ubiquiti Networks", "FC:EC:DA": "Ubiquiti Networks",
    "5C:AA:FD": "Sonos",
    "00:1A:A1": "Cisco",
    "04:D4:C4": "ASUSTek",
}

_ARP_CACHE: Dict[str, str] = {}
_ARP_CACHE_TS: float = 0.0
_GEO_CACHE: Dict[str, Optional[Dict]] = {}


def _is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True


def _vendor_from_mac(mac: str) -> str:
    if not mac:
        return ""
    prefix = mac.upper()[:8]  # AA:BB:CC
    return MAC_VENDOR_PREFIXES.get(prefix, "Desconocido")


def _get_arp_table(force: bool = False) -> Dict[str, str]:
    """Lee la tabla ARP real del sistema (ip neigh / arp -n).
    Cachea 15s para no golpear el sistema en cada escaneo."""
    global _ARP_CACHE, _ARP_CACHE_TS
    if not force and (time.time() - _ARP_CACHE_TS) < 15 and _ARP_CACHE:
        return _ARP_CACHE

    table: Dict[str, str] = {}
    # Intento 1: ip neigh (Linux moderno / Termux con paquete iproute2)
    try:
        res = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 5 and "lladdr" in parts:
                ip = parts[0]
                mac_idx = parts.index("lladdr") + 1
                if mac_idx < len(parts):
                    table[ip] = parts[mac_idx].upper()
    except Exception:
        pass

    # Intento 2: arp -n (fallback si iproute2 no está disponible)
    if not table:
        try:
            res = subprocess.run(["arp", "-n"], capture_output=True, text=True, timeout=2)
            for line in res.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 3 and re.match(r"^[0-9a-fA-F:]{17}$", parts[2]):
                    table[parts[0]] = parts[2].upper()
        except Exception:
            pass

    if table:
        _ARP_CACHE = table
        _ARP_CACHE_TS = time.time()
    return table


async def _resolve_hostname(ip: str) -> str:
    """DNS inverso real con timeout corto — no bloquea el escaneo."""
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, socket.gethostbyaddr, ip),
            timeout=1.5
        )
        return result[0]
    except Exception:
        return ""


async def _geolocate_public_ip(ip: str) -> Optional[Dict]:
    """Geolocalización REAL solo para IPs públicas. Usa ip-api.com
    (gratis, sin API key, límite ~45 req/min). Nunca se llama para
    rangos privados — ver _is_private_ip(). Resultado cacheado."""
    if ip in _GEO_CACHE:
        return _GEO_CACHE[ip]
    if aiohttp is None:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,lat,lon,city,country,isp,org"},
                timeout=aiohttp.ClientTimeout(total=3)
            ) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    geo = {
                        "lat": data.get("lat"), "lon": data.get("lon"),
                        "city": data.get("city", ""), "country": data.get("country", ""),
                        "isp": data.get("isp", ""), "org": data.get("org", ""),
                    }
                    _GEO_CACHE[ip] = geo
                    return geo
    except Exception:
        pass
    _GEO_CACHE[ip] = None
    return None


# ============================================================
# 1. NÚCLEO COGNITIVO — Base de datos + Predicción
# ============================================================
security = HTTPBasic()
app = FastAPI(title="NEXUS OMNI-SENTIENT v9.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NeuralDB:
    def __init__(self):
        self.conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                ip TEXT, mac TEXT, hostname TEXT,
                ports TEXT, os_guess TEXT, vendor TEXT,
                risk_score REAL, threat_level TEXT,
                first_seen TEXT, last_seen TEXT,
                scan_history TEXT, seal_hash TEXT,
                lat REAL, lon REAL
            )''')
        # Migración: columnas nuevas para datos reales (is_private, geo_meta)
        for col, coltype in [("is_private", "INTEGER DEFAULT 1"),
                              ("geo_city", "TEXT"), ("geo_country", "TEXT"),
                              ("geo_isp", "TEXT")]:
            try:
                self.conn.execute(f"ALTER TABLE devices ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass  # La columna ya existe
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT, event_type TEXT,
                description TEXT, severity TEXT, timestamp TEXT
            )''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS adaptations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT, reason TEXT, timestamp TEXT
            )''')
        self.conn.commit()

    def update_device(self, dev: Dict) -> Tuple[bool, float, str]:
        """Actualiza dispositivo y calcula predicción de amenaza."""
        now = datetime.now().isoformat()
        ip = dev["ip"]

        # Cargar historial
        c = self.conn.cursor()
        c.execute("SELECT scan_history, risk_score FROM devices WHERE id=?", (dev["id"],))
        row = c.fetchone()

        history = []
        old_risk = 0.0
        if row:
            history = json.loads(row[0])
            old_risk = row[1]
            history.append({"time": now, "ports": dev.get("ports", []), "risk": dev.get("risk_score", 0)})
            if len(history) > CONFIG["prediction_window"]: history.pop(0)
        else:
            history = [{"time": now, "ports": dev.get("ports", []), "risk": dev.get("risk_score", 0)}]

        # --- MOTOR DE PREDICCIÓN (IA SIMPLE) ---
        # Detectar anomalía: ¿Cambio drástico de puertos?
        anomaly_detected = False
        if len(history) >= 2:
            prev_ports = set(history[-2]["ports"])
            curr_ports = set(dev.get("ports", []))
            if prev_ports != curr_ports and len(curr_ports) > 0:
                anomaly_detected = True
                self._log_event(dev["id"], "ANOMALY", f"Cambio de puertos: {prev_ports} -> {curr_ports}", "HIGH")

        # Calcular Riesgo Dinámico (Base + Anomalía + Tendencias)
        base_risk = self._calculate_base_risk(dev)
        dynamic_risk = base_risk
        if anomaly_detected: dynamic_risk += 30
        if len(history) > 1 and history[-1]["risk"] > history[-2]["risk"]:
            dynamic_risk += 10 # Tendencia al alza

        threat_level = "LOW"
        if dynamic_risk > 80: threat_level = "CRITICAL"
        elif dynamic_risk > 50: threat_level = "HIGH"
        elif dynamic_risk > 20: threat_level = "MEDIUM"

        # Guardar
        data_str = json.dumps(dev, sort_keys=True)
        seal_hash = hashlib.sha256(data_str.encode()).hexdigest()

        # NOTA: lat/lon ya NO se rellenan con jitter aleatorio. Solo se
        # guardan coordenadas si vinieron de una geolocalización REAL
        # (IP pública consultada en _geolocate_public_ip). Para IPs
        # privadas (LAN) lat/lon quedan NULL — is_private=1 indica al
        # frontend que debe mostrarse en el panel de red local, no en
        # el mapa geográfico.
        self.conn.execute('''
            INSERT OR REPLACE INTO devices
            (id, ip, mac, hostname, ports, os_guess, vendor, risk_score, threat_level,
             first_seen, last_seen, scan_history, seal_hash, lat, lon,
             is_private, geo_city, geo_country, geo_isp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            dev["id"], ip, dev.get("mac", ""), dev.get("hostname", ""),
            json.dumps(dev.get("ports", [])), dev.get("os", ""), dev.get("vendor", ""),
            dynamic_risk, threat_level,
            dev.get("first_seen", now), now, json.dumps(history), seal_hash,
            dev.get("lat"), dev.get("lon"),
            int(dev.get("is_private", True)),
            dev.get("geo_city", ""), dev.get("geo_country", ""), dev.get("geo_isp", ""),
        ))
        self.conn.commit()
        return anomaly_detected, dynamic_risk, threat_level

    def _calculate_base_risk(self, dev: Dict) -> float:
        risk = 0.0
        ports = dev.get("ports", [])
        critical = set(CONFIG["ports_critical"]) & set(ports)
        risk += len(critical) * 15
        if 22 in ports and 445 in ports: risk += 20
        if 3389 in ports: risk += 15
        if 23 in ports: risk += 25 # Telnet = muy riesgoso
        return min(risk, 100)

    def _log_event(self, device_id, etype, desc, sev):
        self.conn.execute("INSERT INTO events (device_id, event_type, description, severity, timestamp) VALUES (?,?,?,?,?)",
                         (device_id, etype, desc, sev, datetime.now().isoformat()))
        self.conn.commit()

    def log_adaptation(self, action, reason):
        self.conn.execute("INSERT INTO adaptations (action, reason, timestamp) VALUES (?,?,?)",
                         (action, reason, datetime.now().isoformat()))
        self.conn.commit()

    def get_all_devices(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM devices ORDER BY risk_score DESC")
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

    def get_recent_events(self, limit: int = 30) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

    def get_recent_adaptations(self, limit: int = 15) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM adaptations ORDER BY id DESC LIMIT ?", (limit,))
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

db = NeuralDB()

# ============================================================
# 2. ESCÁNER ADAPTATIVO — Aprende y se ajusta solo
# ============================================================
class AdaptiveScanner:
    def __init__(self):
        self.mode = "stealth"
        self.scanning = False
        self.port_success_rate = {} # Aprende qué puertos están abiertos frecuentemente
        self.watchdog_task = None
        self.last_activity = time.time()

    def start_watchdog(self):
        """Monitorea la salud del escáner y lo reinicia si se cuelga."""
        if self.watchdog_task and not self.watchdog_task.done():
            return
        async def watchdog():
            while True:
                await asyncio.sleep(30)
                if self.scanning and time.time() - self.last_activity > 60:
                    print("⚠️ WATCHDOG: Escáner congelado. Reiniciando...")
                    self.scanning = False # Forzar parada para reinicio externo
        self.watchdog_task = asyncio.create_task(watchdog())

    async def stop_watchdog(self):
        if self.watchdog_task and not self.watchdog_task.done():
            self.watchdog_task.cancel()
            try:
                await self.watchdog_task
            except asyncio.CancelledError:
                pass

    async def adapt_strategy(self, network_cidr: str, found_count: int):
        """Ajusta el modo de escaneo dinámicamente según los resultados."""
        # Si encontramos muchos dispositivos críticos, subir a 'active'
        critical_count = len([d for d in db.get_all_devices() if d.get("threat_level") == "CRITICAL"])

        if critical_count > 3 and self.mode != "frenzy":
            self.mode = "frenzy"
            db.log_adaptation("MODE_CHANGE", f"Elevado a FRENZY por {critical_count} amenazas críticas.")
            print(f"🚨 AMENAZA ALTA DETECTADA. CAMBIANDO A MODO FRENZY.")
        elif found_count == 0 and self.mode == "active":
            self.mode = "stealth" # Bajar intensidad si no hay nada
            db.log_adaptation("MODE_CHANGE", "Bajado a STEALTH por falta de objetivos.")

    async def scan_host(self, ip: str, arp_table: Optional[Dict[str, str]] = None) -> Optional[Dict]:
        self.last_activity = time.time()
        config = CONFIG["modes"][self.mode]
        timeout = config["timeout"]

        open_ports = []
        concurrent = config["concurrent"]

        async def check_port(port: int):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port), timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                return port
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                return None

        # Escaneo concurrente
        tasks = [check_port(p) for p in CONFIG["ports_critical"]]
        results = await asyncio.gather(*tasks)
        open_ports = [p for p in results if p is not None]

        if not open_ports:
            return None

        # ── Enriquecimiento con datos REALES ──
        arp_table = arp_table or {}
        mac = arp_table.get(ip, "")
        vendor = _vendor_from_mac(mac)
        hostname = await _resolve_hostname(ip)
        is_private = _is_private_ip(ip)

        lat, lon, geo_city, geo_country, geo_isp = None, None, "", "", ""
        if not is_private:
            # Solo se geolocaliza con datos reales si la IP es pública.
            # Los rangos privados (LAN) NUNCA reciben coordenadas — antes
            # se les asignaba una posición aleatoria alrededor de Bogotá,
            # lo cual era información falsa. Ahora se muestran en el
            # panel de "Red Local" del frontend, sin pin en el mapa.
            geo = await _geolocate_public_ip(ip)
            if geo:
                lat, lon = geo.get("lat"), geo.get("lon")
                geo_city, geo_country, geo_isp = geo.get("city", ""), geo.get("country", ""), geo.get("isp", "")

        # Generar ID único
        dev_id = hashlib.md5(f"{ip}:{open_ports}".encode()).hexdigest()

        return {
            "id": dev_id, "ip": ip, "ports": open_ports,
            "os": self._guess_os(open_ports),
            "mac": mac, "vendor": vendor, "hostname": hostname,
            "is_private": is_private,
            "lat": lat, "lon": lon,
            "geo_city": geo_city, "geo_country": geo_country, "geo_isp": geo_isp,
            "first_seen": datetime.now().isoformat(),
            "risk_score": 0, # Se calcula en update_device
        }

    def _guess_os(self, ports: List[int]) -> str:
        if 3389 in ports: return "Windows"
        if 22 in ports and 5432 in ports: return "Linux/PostgreSQL"
        if 22 in ports: return "Linux/Unix"
        if 445 in ports: return "Windows/SMB"
        if 23 in ports: return "Router/IoT"
        return "Unknown"

    async def run_discovery(self, network_cidr: str):
        self.scanning = True
        self.last_activity = time.time()
        print(f"🧠 NEXUS OMNI iniciado en {network_cidr} (Modo: {self.mode.upper()})")

        my_ip = "192.168.1.50"
        try:
            res = subprocess.run(["ip", "route"], capture_output=True, text=True, timeout=1)
            for line in res.stdout.split('\n'):
                if "src" in line: my_ip = line.split()[line.split().index("src")+1]
        except: pass

        # Tabla ARP real del sistema — una sola lectura por corrida de escaneo
        arp_table = _get_arp_table(force=True)

        net = ipaddress.ip_network(network_cidr, strict=False)
        targets = [str(ip) for ip in net.hosts() if str(ip) != my_ip]
        if self.mode == "passive": targets = targets[:10]

        tasks = [self.scan_host(ip, arp_table) for ip in targets]
        results = await asyncio.gather(*tasks)
        found = [r for r in results if r]

        for dev in found:
            db.update_device(dev)

        await self.adapt_strategy(network_cidr, len(found))
        self.scanning = False
        return found

scanner = AdaptiveScanner()

@app.on_event("startup")
async def start_scanner_watchdog():
    scanner.start_watchdog()

@app.on_event("shutdown")
async def stop_scanner_watchdog():
    await scanner.stop_watchdog()

# ============================================================
# 3. API Y WEBSOCKET EN TIEMPO REAL
# ============================================================
def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != CONFIG["auth_user"] or credentials.password != CONFIG["auth_pass"]:
        raise HTTPException(status_code=401, detail="Access Denied")
    return credentials

@app.get("/")
async def root(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    if not os.path.exists("nexus_ui.html"):
        return HTMLResponse("<h1>NEXUS UI Missing</h1><p>Generate nexus_ui.html</p>")
    return FileResponse("nexus_ui.html")

@app.post("/api/scan")
async def trigger_scan(credentials: HTTPBasicCredentials = Depends(verify_auth), network: str = "192.168.1.0/24"):
    if scanner.scanning: return {"status": "running"}
    asyncio.create_task(scanner.run_discovery(network))
    return {"status": "started", "mode": scanner.mode}

@app.get("/api/analytics")
async def get_analytics(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    devices = db.get_all_devices()
    total = len(devices)
    critical = len([d for d in devices if d["threat_level"] == "CRITICAL"])
    anomalies = len(db.get_recent_events(limit=100))
    return {
        "total": total, "critical": critical, "mode": scanner.mode,
        "scanning": scanner.scanning, "health": "OPTIMAL", "anomalies": anomalies
    }

@app.get("/api/events")
async def get_events(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    """Eventos reales (anomalías detectadas + cambios de modo adaptativo)."""
    return {
        "events": db.get_recent_events(30),
        "adaptations": db.get_recent_adaptations(15),
    }

@app.get("/api/state")
async def get_state(credentials: HTTPBasicCredentials = Depends(verify_auth)):
    """Estado completo para el proxy del dashboard unificado.

    Separa dispositivos en:
      - devices_public: tienen lat/lon REAL (geolocalización de IP pública)
      - devices_local: son LAN (is_private=1), sin coordenadas — se listan
        en el panel de red local del frontend, nunca como pin falso en el mapa
    """
    devices = db.get_all_devices()
    devices_public = [d for d in devices if not d.get("is_private") and d.get("lat") is not None]
    devices_local = [d for d in devices if d.get("is_private") or d.get("lat") is None]

    return {
        "devices": devices,                # compatibilidad hacia atrás
        "devices_public": devices_public,
        "devices_local": devices_local,
        "events": db.get_recent_events(15),
        "stats": await get_analytics(credentials),
    }

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text() # Ping
            devices = db.get_all_devices()
            devices_public = [d for d in devices if not d.get("is_private") and d.get("lat") is not None]
            devices_local = [d for d in devices if d.get("is_private") or d.get("lat") is None]

            await websocket.send_json({
                "devices": devices,
                "devices_public": devices_public,
                "devices_local": devices_local,
                "events": db.get_recent_events(15),
                "stats": await get_analytics(
                    HTTPBasicCredentials(
                        username=CONFIG["auth_user"],
                        password=CONFIG["auth_pass"],
                    )
                )
            })
            await asyncio.sleep(1) # Update rate 1s
    except WebSocketDisconnect: pass

if __name__ == "__main__":
    print("🌐 NEXUS OMNI-SENTIENT v9.0 ONLINE")
    print(f"🔐 Acceso configurado para usuario '{NEXUS_CREDENTIALS.user}' — credenciales en .env (no se muestran)")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("NEXUS_PORT", "8004")))
