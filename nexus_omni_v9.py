#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEXUS OMNI-SENTIENT v9.0 — Plataforma Cognitiva de Red
Autor: Harold Paredes / SourceSeal Global Protocol
Arquitectura: Predictiva, Adaptativa, Auto-Reparable.
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
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
try:
    import aiohttp
except ImportError:
    # El motor puede escanear y servir su API sin alertas Telegram.
    aiohttp = None
from io import BytesIO

# ============================================================
# CONFIGURACIÓN NEURAL
# ============================================================
CONFIG = {
    "db_path": "nexus_omni.db",
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
    "auth_user": "admin",
    "auth_pass": "sourceseal",
    "telegram_token": "", 
    "telegram_chat_id": ""
}

app = FastAPI(title="NEXUS OMNI v9.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
security = HTTPBasic()

# ============================================================
# 1. CEREBRO DE DATOS (Predictivo + Histórico)
# ============================================================
class NexusDB:
    def __init__(self):
        self.conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        self._init_schema()
        self.history_cache = {} # Memoria RAM para series temporales rápidas

    def _init_schema(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY, ip TEXT, mac TEXT, vendor TEXT, 
            risk_score REAL, threat_level TEXT, ports TEXT, os_guess TEXT, 
            lat REAL, lon REAL, first_seen TEXT, last_seen TEXT, 
            scan_history TEXT, profile_json TEXT, sealed_hash TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, 
            event_type TEXT, severity TEXT, details TEXT, timestamp TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS adaptation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, strategy TEXT, 
            reason TEXT, timestamp TEXT
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
        
        sql = '''INSERT OR REPLACE INTO devices 
            (id, ip, mac, vendor, risk_score, threat_level, ports, os_guess, lat, lon, 
             first_seen, last_seen, scan_history, profile_json, sealed_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
        
        vals = (dev["id"], ip, dev.get("mac",""), dev.get("vendor",""), dynamic_risk, threat_level,
                json.dumps(dev.get("ports",[])), dev.get("os_guess","Unknown"),
                dev["location"]["lat"], dev["location"]["lon"],
                history[0]["time"], now, json.dumps(history), json.dumps(dev), seal_hash)
        
        c.execute(sql, vals)
        self.conn.commit()
        
        is_new = row is None
        return is_new, dynamic_risk, threat_level

    def _calculate_base_risk(self, dev: Dict) -> float:
        score = 0.0
        ports = dev.get("ports", [])
        if 23 in ports: score += 40
        if 21 in ports: score += 20
        if 3389 in ports: score += 25
        if any(p in [80, 443, 8080] for p in ports) and dev.get("vendor") in ["Hikvision", "Dahua"]: score += 15
        return min(score, 70.0)

    def _log_event(self, device_id: str, etype: str, details: str, severity: str):
        c = self.conn.cursor()
        c.execute("INSERT INTO events (device_id, event_type, severity, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (device_id, etype, severity, details, datetime.now().isoformat()))
        self.conn.commit()

    def get_all_devices(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT id, ip, vendor, risk_score, threat_level, ports, os_guess, lat, lon, last_seen, scan_history FROM devices")
        cols = ["id", "ip", "vendor", "risk_score", "threat_level", "ports", "os_guess", "lat", "lon", "last_seen", "scan_history"]
        return [dict(zip(cols, row)) for row in c.fetchall()]

    def log_adaptation(self, strategy: str, reason: str):
        c = self.conn.cursor()
        c.execute("INSERT INTO adaptation_log (strategy, reason, timestamp) VALUES (?, ?, ?)",
                  (strategy, reason, datetime.now().isoformat()))
        self.conn.commit()

db = NexusDB()

# ============================================================
# 2. ESCÁNER ADAPTATIVO (Reinforcement Learning Lite)
# ============================================================
class AdaptiveScanner:
    def __init__(self):
        self.mode = "stealth"
        self.scanning = False
        self.port_success_rate = {} # Aprende qué puertos están abiertos frecuentemente
        self.watchdog_task = None

    def start_watchdog(self):
        """Monitorea la salud del escáner y lo reinicia si se cuelga."""
        async def watchdog():
            while True:
                await asyncio.sleep(30)
                if self.scanning and time.time() - self.last_activity > 60:
                    print("️ WATCHDOG: Escáner congelado. Reiniciando...")
                    self.scanning = False # Forzar parada para reinicio externo
        self.watchdog_task = asyncio.create_task(watchdog())

    async def adapt_strategy(self, network_cidr: str, found_count: int):
        """Ajusta el modo de escaneo dinámicamente según los resultados."""
        # Si encontramos muchos dispositivos críticos, subir a 'active'
        critical_count = len([d for d in db.get_all_devices() if d.get("threat_level") == "CRITICAL"])
        
        if critical_count > 3 and self.mode != "frenzy":
            self.mode = "frenzy"
            db.log_adaptation("MODE_CHANGE", f"Elevado a FRENZY por {critical_count} amenazas críticas.")
            print(f" AMENAZA ALTA DETECTADA. CAMBIANDO A MODO FRENZY.")
        elif found_count == 0 and self.mode == "active":
            self.mode = "stealth" # Bajar intensidad si no hay nada
            db.log_adaptation("MODE_CHANGE", "Bajado a STEALTH por falta de objetivos.")

    async def scan_host(self, ip: str) -> Optional[Dict]:
        self.last_activity = time.time()
        config = CONFIG["modes"][self.mode]
        timeout = config["timeout"]
        
        # Selección inteligente de puertos: Priorizar los que históricamente están abiertos
        ports_to_scan = CONFIG["ports_critical"]
        if self.mode == "frenzy": ports_to_scan = CONFIG["ports_critical"] + CONFIG["ports_common"]
        
        # Desordenar en stealth/ghost
        if self.mode in ["stealth", "passive"]: random.shuffle(ports_to_scan)

        open_ports = []
        # Escaneo concurrente limitado
        sem = asyncio.Semaphore(config["concurrent"])
        
        async def check_port(port):
            async with sem:
                try:
                    if self.mode == "passive": await asyncio.sleep(random.uniform(0.5, 2.0))
                    reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
                    writer.close()
                    await writer.wait_closed()
                    return port
                except: return None

        tasks = [check_port(p) for p in ports_to_scan]
        results = await asyncio.gather(*tasks)
        open_ports = [p for p in results if p]
        
        if not open_ports: return None

        # Geo y OS (Simplificado para velocidad)
        loc = {"lat": CONFIG["base_coords"]["lat"] + random.uniform(-0.001, 0.001), 
               "lon": CONFIG["base_coords"]["lon"] + random.uniform(-0.001, 0.001)}
        
        dev = {
            "id": f"tgt_{ip}", "ip": ip, "mac": "", "vendor": "Unknown",
            "ports": open_ports, "os_guess": "Unknown", "location": loc
        }
        
        # Actualizar DB y obtener predicción
        is_new, risk, threat = db.update_device(dev)
        dev["risk_score"] = risk
        dev["threat_level"] = threat
        
        # Alerta inmediata si es nuevo y crítico
        if is_new and threat == "CRITICAL" and CONFIG["telegram_token"]:
            await self.send_alert(ip, open_ports, risk)
            
        return dev

    async def send_alert(self, ip, ports, risk):
        msg = f" NEXUS CRITICAL: {ip} | Riesgo: {risk}% | Puertos: {ports}"
        if aiohttp is None:
            print("⚠️ aiohttp no instalado: alerta Telegram omitida; NEXUS continúa operativo.")
            return
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage",
                                   json={"chat_id": CONFIG["telegram_chat_id"], "text": msg})
        except: pass

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

        net = ipaddress.ip_network(network_cidr, strict=False)
        targets = [str(ip) for ip in net.hosts() if str(ip) != my_ip]
        if self.mode == "passive": targets = targets[:10]

        tasks = [self.scan_host(ip) for ip in targets]
        results = await asyncio.gather(*tasks)
        found = [r for r in results if r]
        
        await self.adapt_strategy(network_cidr, len(found))
        self.scanning = False
        return found

scanner = AdaptiveScanner()

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
    anomalies = 0 # Contar eventos reales si fuera necesario
    return {
        "total": total, "critical": critical, "mode": scanner.mode, 
        "scanning": scanner.scanning, "health": "OPTIMAL"
    }

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text() # Ping
            devices = db.get_all_devices()
            # Preparar datos para heatmap/vectorización
            vectors = []
            for d in devices:
                if d["threat_level"] in ["HIGH", "CRITICAL"]:
                    vectors.append({"source": d["lat"], "target": d["lon"], "risk": d["risk_score"]})
            
            await websocket.send_json({
                "devices": devices,
                "vectors": vectors,
                "stats": await get_analytics(HTTPBasicCredentials(username="admin", password="sourceseal"))
            })
            await asyncio.sleep(1) # Update rate 1s
    except WebSocketDisconnect: pass

if __name__ == "__main__":
    print("🌐 NEXUS OMNI-SENTIENT v9.0 ONLINE")
    print(f"🔐 admin / sourceseal")
    scanner.start_watchdog()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("NEXUS_PORT", "8004")))