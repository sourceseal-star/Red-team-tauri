"""
SOURCESEAL INTELLIGENCE & OSINT BACKEND ORCHESTRATOR v3.0
==========================================================
Backend unificado con:
- Escaneo táctico de red (multi-layer discovery)
- Validador OSINT de precisión quirúrgica (Anti-Falsos Positivos)
- Persistencia SQLite + Cifrado Fernet AES-256
- Integración con ARTO (operaciones autónomas)
- Integración con SEAL SUPER PACK (escaneo/ataque avanzado)
- Sistema de alertas WebSocket en tiempo real
- Generador de informes profesionales (PDF/HTML)
- API de Threat Intelligence (Shodan, VirusTotal, AbuseIPDB)

Autor: Harold Paredes / SourceSeal Red Team
Uso: python3 source_seal_backend_v3.py
"""

import asyncio
import socket
import subprocess
import re
import json
import ipaddress
import sqlite3
import threading
import time
import os
import urllib.request
import base64
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from cryptography.fernet import Fernet
from pydantic import BaseModel
import aiohttp


# ============================================================
# CONFIGURACIÓN GLOBAL TÁCTICA v3.0
# ============================================================

CONFIG = {
    "db_path": os.path.expanduser("~/seal_tactical.db"),
    "report_dir": os.path.expanduser("~/storage/downloads/seal_reports"),
    "template_dir": os.path.expanduser("~/storage/templates"),

    "network": "192.168.0.0/24",
    "full_ports": [21, 22, 23, 25, 53, 80, 110, 139, 443, 445, 554, 1935, 3306,
                   3389, 5432, 6379, 8000, 8080, 8443, 8554, 8888, 37777, 3702],
    "camera_ports": [80, 443, 554, 8000, 8080, 37777],

    "timeout_tcp": 0.4,
    "timeout_ping": 0.5,
    "timeout_http": 5.0,

    "max_concurrent": 150,

    "encryption_key": os.environ.get("SEAL_MASTER_KEY", Fernet.generate_key().decode()),

    "arto_enabled": True,
    "seal_enabled": True,

    "shodan_api_key": os.environ.get("SHODAN_API_KEY"),
    "virustotal_api_key": os.environ.get("VIRUSTOTAL_API_KEY"),
    "abuseipdb_api_key": os.environ.get("ABUSEIPDB_API_KEY"),

    "ws_ping_interval": 30,
}

os.makedirs(CONFIG["report_dir"], exist_ok=True)
os.makedirs(CONFIG["template_dir"], exist_ok=True)

db_lock = threading.Lock()
active_websocket_connections: List[WebSocket] = []


# ============================================================
# 1. PERSISTENCIA Y SEGURIDAD (SQLite + Fernet)
# ============================================================

def init_db():
    """Inicializa la base de datos con todas las tablas"""
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS tactical_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            results_json TEXT NOT NULL,
            vulnerability_index INTEGER,
            status TEXT DEFAULT 'completed',
            scan_type TEXT DEFAULT 'basic'
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS osint_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            results_json TEXT NOT NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS realtime_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            target TEXT,
            evidence TEXT,
            timestamp TEXT NOT NULL,
            resolved INTEGER DEFAULT 0,
            mitre_attack TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS arto_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            target TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            result_json TEXT,
            timestamp TEXT NOT NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS threat_intel_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            source TEXT NOT NULL,
            result_json TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            UNIQUE(query, source)
        )''')

        conn.commit()
        conn.close()


def save_scan_db(target: str, data: dict, vuln_index: int, scan_type: str = "basic"):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT INTO tactical_scans (target, timestamp, results_json, vulnerability_index, status, scan_type) VALUES (?, ?, ?, ?, ?, ?)",
            (target, datetime.utcnow().isoformat(), json.dumps(data), vuln_index, 'completed', scan_type)
        )
        conn.commit()
        conn.close()


def save_osint_db(username: str, data: dict):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT INTO osint_checks (username, timestamp, results_json) VALUES (?, ?, ?)",
            (username, datetime.utcnow().isoformat(), json.dumps(data))
        )
        conn.commit()
        conn.close()


def save_alert_db(alert: dict):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            """INSERT INTO realtime_alerts
            (alert_type, severity, title, description, target, evidence, timestamp, mitre_attack)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.get("alert_type", "unknown"),
                alert.get("severity", "info"),
                alert.get("title", ""),
                alert.get("description", ""),
                alert.get("target", ""),
                json.dumps(alert.get("evidence", {})),
                datetime.utcnow().isoformat(),
                alert.get("mitre_attack", "")
            )
        )
        conn.commit()
        conn.close()


def save_arto_operation_db(operation: dict):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            """INSERT INTO arto_operations
            (operation_type, target, status, result_json, timestamp)
            VALUES (?, ?, ?, ?, ?)""",
            (
                operation.get("operation_type", "unknown"),
                operation.get("target", ""),
                operation.get("status", "running"),
                json.dumps(operation.get("result", {})),
                datetime.utcnow().isoformat()
            )
        )
        conn.commit()
        conn.close()


def encrypt_data(raw_data: str) -> str:
    f = Fernet(CONFIG["encryption_key"].encode())
    return f.encrypt(raw_data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    f = Fernet(CONFIG["encryption_key"].encode())
    return f.decrypt(encrypted_data.encode()).decode()


# ============================================================
# 2. VALIDADOR OSINT DE PRECISIÓN (Anti-Falsos Positivos) v2.0
# ============================================================

def check_platform(url: str, headers: dict = None, timeout: int = 5) -> tuple:
    if not headers:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SourceSeal-OSINT/3.0"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            code = response.getcode()
            body = response.read().decode("utf-8", errors="ignore")
            return code, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def verify_username_osint(username: str) -> Dict[str, Any]:
    results = {}
    username_clean = username.strip()

    if not username_clean or len(username_clean) < 2:
        return results

    # 1. GitHub
    code, body = check_platform(f"https://github.com/{username_clean}")
    results["GitHub"] = True if code == 200 else False

    # 2. GitLab (API)
    code, body = check_platform(f"https://gitlab.com/api/v4/users?username={username_clean}")
    results["GitLab"] = True if (code == 200 and body.strip() != "[]") else False

    # 3. YouTube
    code, body = check_platform(f"https://www.youtube.com/@{username_clean}")
    results["YouTube"] = True if (code == 200 and "PageNotFound" not in body) else False

    # 4. Telegram
    code, body = check_platform(f"https://t.me/{username_clean}")
    results["Telegram"] = True if (code == 200 and "tgme_page_extra" in body) else False

    # 5. Twitch
    code, body = check_platform(f"https://www.twitch.tv/{username_clean}")
    results["Twitch"] = True if (code == 200 and ("isLiveBroadcast" in body or "user-card" in body)) else False

    # 6. Snapchat
    code, body = check_platform(f"https://www.snapchat.com/add/{username_clean}")
    results["Snapchat"] = True if (code == 200 and "profilePage" in body) else False

    # 7. TikTok
    code, body = check_platform(f"https://www.tiktok.com/@{username_clean}")
    results["TikTok"] = True if (code == 200 and "user-info" in body) else False

    # 8. Medium (RSS)
    code, body = check_platform(f"https://medium.com/feed/@{username_clean}")
    results["Medium"] = True if code == 200 else False

    # 9. Pinterest
    code, body = check_platform(f"https://www.pinterest.com/{username_clean}/_/_/")
    results["Pinterest"] = True if code == 200 else False

    # Plataformas no verificables por bloqueo de scraping anónimo
    results["Instagram"] = None
    results["LinkedIn"] = None
    results["X_Twitter"] = None
    results["Facebook"] = None
    results["Reddit"] = None

    return results


# ============================================================
# 3. INTEGRACIÓN CON ARTO
# ============================================================

class ARTOIntegration:
    """Integración con el sistema ARTO para operaciones autónomas"""

    def __init__(self):
        self.enabled = CONFIG["arto_enabled"]
        self.operations: List[Dict] = []

    async def start(self):
        if not self.enabled:
            return False

        try:
            from arto import ARTO
            self.arto = ARTO()
            await self.arto.start()
            return True
        except Exception as e:
            print(f"[ARTO] Error al iniciar: {e}")
            self.enabled = False
            return False

    async def autonomous_scan(self, target: str) -> Dict:
        if not self.enabled or not hasattr(self, 'arto'):
            return {"error": "ARTO no está disponible"}

        try:
            result = await self.arto.autonomous_operation(target, "scan")
            save_arto_operation_db({
                "operation_type": "scan",
                "target": target,
                "status": "completed",
                "result": result
            })
            return result
        except Exception as e:
            return {"error": str(e)}

    async def get_decision(self, context: Dict) -> Dict:
        if not self.enabled or not hasattr(self, 'arto'):
            return {"error": "ARTO no está disponible"}

        try:
            decision = await self.arto.decision_engine.decide_action(context)
            return decision.to_dict()
        except Exception as e:
            return {"error": str(e)}

    async def predict_attacks(self, timeframe: int = 24) -> Dict:
        if not self.enabled or not hasattr(self, 'arto'):
            return {"error": "ARTO no está disponible"}

        try:
            predictions = await self.arto.predict_attacks(timeframe)
            return predictions
        except Exception as e:
            return {"error": str(e)}

    async def simulate_attack(self, attack_type: str, target: str) -> Dict:
        if not self.enabled or not hasattr(self, 'arto'):
            return {"error": "ARTO no está disponible"}

        try:
            result = await self.arto.attack_simulator.simulate_attack(attack_type, target)
            save_arto_operation_db({
                "operation_type": "simulate",
                "target": target,
                "status": "completed",
                "result": result.to_dict()
            })
            return result.to_dict()
        except Exception as e:
            return {"error": str(e)}


arto_integration = ARTOIntegration()


# ============================================================
# 4. INTEGRACIÓN CON SEAL SUPER PACK
# ============================================================

class SEALIntegration:
    """Integración con SEAL SUPER PACK"""

    def __init__(self):
        self.enabled = CONFIG["seal_enabled"]

    async def network_sweep(self, network: str = None, deep: bool = False) -> Dict:
        if not self.enabled:
            return {"error": "SEAL no está disponible"}

        try:
            from seal.scanners.network_sweep_ultimate import discover_active_ips, scan_target

            net = network or CONFIG["network"]
            active_ips = await discover_active_ips(net)

            results = []
            for ip in active_ips:
                target_data = await scan_target(ip, deep)
                results.append(target_data)

            targets = [r for r in results if r.get('services')]

            return {
                "network": net,
                "scanned_ips": len(active_ips),
                "targets": targets
            }
        except Exception as e:
            return {"error": str(e)}

    async def hikvision_attack(self, ip: str) -> Dict:
        if not self.enabled:
            return {"error": "SEAL no está disponible"}

        try:
            from seal.attackers.hikvision_killer import scan_and_attack
            return await scan_and_attack(ip)
        except Exception as e:
            return {"error": str(e)}

    async def onvif_scan(self, network: str = None) -> Dict:
        if not self.enabled:
            return {"error": "SEAL no está disponible"}

        try:
            from seal.scanners.onvif_scanner import scan_network
            net = network or CONFIG["network"]
            return await scan_network(net)
        except Exception as e:
            return {"error": str(e)}

    async def get_vendor_creds(self, vendor: str) -> List[Tuple[str, str]]:
        if not self.enabled:
            return []

        try:
            from seal.utils.vendor_dicts import get_vendor_creds
            return get_vendor_creds(vendor)
        except Exception as e:
            print(f"[SEAL] Error al obtener credenciales: {e}")
            return []

    async def fingerprint_device(self, ip: str) -> Dict:
        if not self.enabled:
            return {}

        try:
            from seal.scanners.fingerprint_engine import FingerprintEngine
            from seal.scanners.network_sweep_ultimate import scan_target

            engine = FingerprintEngine()
            target_data = await scan_target(ip)

            if target_data.get("services"):
                service = target_data["services"][0]
                fingerprint = engine.identify(
                    banner=service.get("banner"),
                    port=service.get("port"),
                    ip=ip
                )
                return fingerprint
            return {}
        except Exception as e:
            return {"error": str(e)}


seal_integration = SEALIntegration()


# ============================================================
# 5. SISTEMA DE ALERTAS WEBSOCKET
# ============================================================

class AlertSystem:
    """Sistema de alertas en tiempo real mediante WebSocket"""

    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        print(f"[WebSocket] Nuevo cliente conectado. Total: {len(self.connections)}")

        await self._send_to_client(websocket, {
            "type": "system_status",
            "data": {
                "message": "Conectado a SourceSeal Backend v3.0",
                "timestamp": datetime.utcnow().isoformat(),
                "features": ["OSINT", "Scanning", "ARTO", "SEAL", "ThreatIntel", "Reports"]
            }
        })

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        print(f"[WebSocket] Cliente desconectado. Total: {len(self.connections)}")

    async def broadcast_alert(self, alert: Dict):
        alert["timestamp"] = datetime.utcnow().isoformat()
        save_alert_db(alert)

        for connection in self.connections:
            try:
                await connection.send_json(alert)
            except:
                if connection in self.connections:
                    self.connections.remove(connection)

    async def _send_to_client(self, websocket: WebSocket, data: Dict):
        try:
            await websocket.send_json(data)
        except:
            if websocket in self.connections:
                self.connections.remove(websocket)


alert_system = AlertSystem()


# ============================================================
# 6. GENERADOR DE INFORMES PROFESIONALES
# ============================================================

class ReportGenerator:
    """Genera informes profesionales en HTML y PDF"""

    def __init__(self):
        self.template_html = self._load_template("report_template.html")

    def _load_template(self, filename: str) -> str:
        template_path = os.path.join(CONFIG["template_dir"], filename)
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>SourceSeal Report - {{title}}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #1a1a1a; color: white; padding: 20px; text-align: center; }
                .section { margin: 20px 0; }
                .vulnerability { background: #ffebee; padding: 10px; margin: 5px 0; border-left: 4px solid #f44336; }
                .safe { background: #e8f5e9; padding: 10px; margin: 5px 0; border-left: 4px solid #4caf50; }
                table { width: 100%; border-collapse: collapse; }
                th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>SourceSeal Intelligence Report</h1>
                <p>Generated: {{timestamp}}</p>
            </div>
            <div class="section">
                <h2>Executive Summary</h2>
                <p>{{summary}}</p>
            </div>
            <div class="section">
                <h2>Details</h2>
                {{details}}
            </div>
            <div class="footer">
                <p>SourceSeal Red Team | {{timestamp}}</p>
            </div>
        </body>
        </html>
        """

    def generate_html_report(self, data: Dict, report_type: str = "scan") -> str:
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

        if report_type == "scan":
            title = f"Network Scan Report - {data.get('network', 'Unknown')}"
            summary = f"""
            <p>Scanned <strong>{data.get('active_hosts', 0)}</strong> hosts in network <strong>{data.get('network', 'Unknown')}</strong>.</p>
            <p>Found <strong>{data.get('vulnerable_hosts', 0)}</strong> hosts with open ports.</p>
            """

            details = "<h3>Discovered Hosts</h3><table><tr><th>IP</th><th>Open Ports</th><th>Vulnerability Score</th></tr>"
            for host in data.get('hosts', []):
                details += f"<tr><td>{host.get('ip')}</td><td>{', '.join(map(str, host.get('open_ports', [])))}</td><td>{host.get('vulnerability_score', 0)}</td></tr>"
            details += "</table>"

        elif report_type == "osint":
            title = f"OSINT Report - {data.get('username', 'Unknown')}"
            summary = f"""
            <p>OSINT analysis for username <strong>{data.get('username', 'Unknown')}</strong>.</p>
            <p>Checked <strong>{len(data.get('results', {}))}</strong> platforms.</p>
            """

            details = "<h3>Platform Results</h3><table><tr><th>Platform</th><th>Exists</th><th>Status</th></tr>"
            for platform, exists in data.get('results', {}).items():
                if exists is True:
                    status = "Found"
                    css_class = "safe"
                elif exists is False:
                    status = "Not Found"
                    css_class = "safe"
                else:
                    status = "Not Verifiable"
                    css_class = "vulnerability"

                details += f'<tr><td>{platform}</td><td><span class="{css_class}">{status}</span></td><td>{status}</td></tr>'
            details += "</table>"

        else:  # integrated
            title = f"Integrated Analysis - {data.get('network', 'Unknown')}"
            summary = f"""
            <p>Integrated ARTO + SEAL analysis for network <strong>{data.get('network', 'Unknown')}</strong>.</p>
            <p>Discovered <strong>{data.get('active_hosts', 0)}</strong> hosts with <strong>{data.get('vulnerable_hosts', 0)}</strong> vulnerabilities.</p>
            """

            details = "<h3>Analysis Results</h3>"
            if 'arto_analysis' in data:
                details += "<h4>ARTO Analysis</h4><pre>" + json.dumps(data['arto_analysis'], indent=2) + "</pre>"
            if 'seal_results' in data:
                details += "<h4>SEAL Results</h4><pre>" + json.dumps(data['seal_results'], indent=2) + "</pre>"

        report_html = self.template_html
        report_html = report_html.replace("{{title}}", title)
        report_html = report_html.replace("{{timestamp}}", timestamp)
        report_html = report_html.replace("{{summary}}", summary)
        report_html = report_html.replace("{{details}}", details)

        return report_html

    def generate_pdf_report(self, data: Dict, report_type: str = "scan") -> str:
        html = self.generate_html_report(data, report_type)

        temp_html = os.path.join(CONFIG["report_dir"], f"temp_report_{int(time.time())}.html")
        with open(temp_html, 'w', encoding='utf-8') as f:
            f.write(html)

        try:
            pdf_path = os.path.join(CONFIG["report_dir"], f"report_{report_type}_{int(time.time())}.pdf")

            result = subprocess.run(["weasyprint", temp_html, pdf_path], capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(pdf_path):
                os.remove(temp_html)
                return pdf_path

            result = subprocess.run(["wkhtmltopdf", temp_html, pdf_path], capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(pdf_path):
                os.remove(temp_html)
                return pdf_path

            return temp_html

        except:
            return temp_html

    def save_report(self, data: Dict, report_type: str = "scan", format: str = "html") -> str:
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        if format == "html":
            report_content = self.generate_html_report(data, report_type)
            report_path = os.path.join(CONFIG["report_dir"], f"report_{report_type}_{timestamp}.html")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)

            encrypted_path = os.path.join(CONFIG["report_dir"], f"report_{report_type}_{timestamp}.enc")
            with open(encrypted_path, 'w') as f:
                f.write(encrypt_data(report_content))

            return report_path

        else:  # pdf
            report_path = self.generate_pdf_report(data, report_type)
            return report_path


report_generator = ReportGenerator()


# ============================================================
# 7. API DE THREAT INTELLIGENCE
# ============================================================

class ThreatIntelligence:
    """API de inteligencia de amenazas"""

    def __init__(self):
        self.shodan_key = CONFIG["shodan_api_key"]
        self.virustotal_key = CONFIG["virustotal_api_key"]
        self.abuseipdb_key = CONFIG["abuseipdb_api_key"]

    async def check_shodan(self, ip: str) -> Dict:
        if not self.shodan_key:
            return {"error": "Shodan API key no configurada"}

        try:
            url = f"https://api.shodan.io/shodan/host/{ip}?key={self.shodan_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "ip": ip,
                            "ports": data.get("ports", []),
                            "vulnerabilities": data.get("vulns", []),
                            "hostnames": data.get("hostnames", []),
                            "org": data.get("org", ""),
                            "asn": data.get("asn", ""),
                            "source": "shodan"
                        }
                    return {"error": f"Shodan error: {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def check_virustotal(self, ip: str) -> Dict:
        if not self.virustotal_key:
            return {"error": "VirusTotal API key no configurada"}

        try:
            url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip}"
            headers = {"x-apikey": self.virustotal_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        attributes = data.get("data", {}).get("attributes", {})
                        return {
                            "ip": ip,
                            "reputation": attributes.get("reputation", 0),
                            "malicious": attributes.get("last_analysis_stats", {}).get("malicious", 0),
                            "suspicious": attributes.get("last_analysis_stats", {}).get("suspicious", 0),
                            "harmless": attributes.get("last_analysis_stats", {}).get("harmless", 0),
                            "undetected": attributes.get("last_analysis_stats", {}).get("undetected", 0),
                            "source": "virustotal"
                        }
                    return {"error": f"VirusTotal error: {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def check_abuseipdb(self, ip: str) -> Dict:
        if not self.abuseipdb_key:
            return {"error": "AbuseIPDB API key no configurada"}

        try:
            url = "https://api.abuseipdb.com/api/v2/check"
            params = {"ipAddress": ip, "maxAgeInDays": "90"}
            headers = {"Key": self.abuseipdb_key, "Accept": "application/json"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        data = data.get("data", {})
                        return {
                            "ip": ip,
                            "abuse_confidence_score": data.get("abuseConfidenceScore", 0),
                            "country": data.get("countryCode", ""),
                            "isp": data.get("isp", ""),
                            "domain": data.get("domain", ""),
                            "total_reports": data.get("totalReports", 0),
                            "last_reported": data.get("lastReportedAt", ""),
                            "source": "abuseipdb"
                        }
                    return {"error": f"AbuseIPDB error: {resp.status}"}
        except Exception as e:
            return {"error": str(e)}

    async def check_all_sources(self, ip: str) -> Dict:
        results = {
            "ip": ip,
            "shodan": await self.check_shodan(ip),
            "virustotal": await self.check_virustotal(ip),
            "abuseipdb": await self.check_abuseipdb(ip)
        }

        threat_score = 0
        sources = 0

        for source, data in results.items():
            if source == "ip":
                continue
            if "error" not in data:
                sources += 1
                if source == "shodan":
                    if data.get("vulnerabilities"):
                        threat_score += 30
                elif source == "virustotal":
                    if data.get("malicious", 0) > 0:
                        threat_score += 40
                elif source == "abuseipdb":
                    if data.get("abuse_confidence_score", 0) > 50:
                        threat_score += 30

        if sources > 0:
            results["threat_score"] = min(100, threat_score)
            results["threat_level"] = self._get_threat_level(threat_score)

        return results

    def _get_threat_level(self, score: int) -> str:
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        elif score >= 20:
            return "LOW"
        else:
            return "SAFE"


threat_intel = ThreatIntelligence()


# ============================================================
# 8. MOTOR DE ESCANEO DE MÁXIMA POTENCIA
# ============================================================

async def aggressive_tcp_ping(ip: str, port: int = 80) -> bool:
    try:
        conn = asyncio.open_connection(ip, port)
        _, writer = await asyncio.wait_for(conn, timeout=CONFIG["timeout_ping"])
        writer.close()
        await writer.wait_closed()
        return True
    except:
        return False


async def multi_layer_discovery(network: str) -> List[str]:
    net = ipaddress.ip_network(network, strict=False)
    all_ips = [str(ip) for ip in net.hosts()]
    active_hosts = set()

    # Capa 1: ARP
    try:
        proc = await asyncio.create_subprocess_exec("ip", "neigh", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        stdout, _ = await proc.communicate()
        for line in stdout.decode().splitlines():
            parts = line.split()
            if parts:
                active_hosts.add(parts[0])
    except:
        pass

    # Capa 2: Ping a puertos críticos
    discovery_ports = CONFIG["camera_ports"]
    semaphore = asyncio.Semaphore(CONFIG["max_concurrent"])

    async def check_host(ip):
        async with semaphore:
            for port in discovery_ports:
                if await aggressive_tcp_ping(ip, port):
                    return ip
            return None

    tasks = [check_host(ip) for ip in all_ips if ip not in active_hosts]
    results = await asyncio.gather(*tasks)
    for r in results:
        if r:
            active_hosts.add(r)

    return list(active_hosts)


async def deep_port_scan(ip: str) -> List[int]:
    open_ports = []
    semaphore = asyncio.Semaphore(CONFIG["max_concurrent"])

    async def test_port(port):
        async with semaphore:
            try:
                conn = asyncio.open_connection(ip, port)
                _, writer = await asyncio.wait_for(conn, timeout=CONFIG["timeout_tcp"])
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except:
                pass

    tasks = [test_port(p) for p in CONFIG["full_ports"]]
    await asyncio.gather(*tasks)
    return sorted(open_ports)


async def scan_with_seal(ip: str, deep: bool = False) -> Dict:
    try:
        from seal.scanners.network_sweep_ultimate import scan_target
        return await scan_target(ip, deep)
    except Exception as e:
        print(f"[SEAL] Error al escanear {ip}: {e}")
        return {"ip": ip, "error": str(e)}


async def run_full_audit(network: str, deep: bool = False, use_seal: bool = True,
                        use_arto: bool = True) -> Dict:
    init_db()

    targets = await multi_layer_discovery(network)

    if use_seal:
        seal_results = []
        for ip in targets:
            result = await scan_with_seal(ip, deep)
            seal_results.append(result)
        targets_data = [r for r in seal_results if r.get('services')]
    else:
        targets_data = []
        for ip in targets:
            ports = await deep_port_scan(ip)
            host_info = {"ip": ip, "open_ports": ports, "vulnerability_score": len(ports)}
            targets_data.append(host_info)
            save_scan_db(ip, host_info, len(ports), "basic")

    arto_analysis = {}
    if use_arto and CONFIG["arto_enabled"]:
        try:
            for target in targets_data:
                ip = target.get("ip")
                analysis = await arto_integration.autonomous_scan(ip)
                arto_analysis[ip] = analysis
        except Exception as e:
            print(f"[ARTO] Error en análisis: {e}")

    threat_results = {}
    for target in targets_data:
        ip = target.get("ip")
        threat_results[ip] = await threat_intel.check_all_sources(ip)

    total_vuln = sum(t.get("vulnerability_score", 0) for t in targets_data)
    high_risk_ips = [t.get("ip") for t in targets_data if t.get("vulnerability_score", 0) > 5]

    report = {
        "network": network,
        "scanned_at": datetime.utcnow().isoformat(),
        "active_hosts": len(targets),
        "total_vulnerabilities": total_vuln,
        "high_risk_hosts": high_risk_ips,
        "hosts": targets_data,
        "arto_analysis": arto_analysis,
        "threat_intel": threat_results
    }

    for target in targets_data:
        ip = target.get("ip")
        vuln_score = target.get("vulnerability_score", 0)
        save_scan_db(ip, target, vuln_score, "integrated" if use_seal else "basic")

    report_path = report_generator.save_report(report, "scan", "html")

    if high_risk_ips:
        await alert_system.broadcast_alert({
            "alert_type": "high_risk_hosts",
            "severity": "high",
            "title": f"Hosts de alto riesgo detectados en {network}",
            "description": f"Se detectaron {len(high_risk_ips)} hosts con alta vulnerabilidad",
            "target": network,
            "evidence": {"high_risk_ips": high_risk_ips},
            "mitre_attack": "T1190"
        })

    pdf_path = report_generator.save_report(report, "scan", "pdf")

    return {
        **report,
        "report_html": report_path,
        "report_pdf": pdf_path if pdf_path != report_path else None
    }


# ============================================================
# 9. FASTAPI BACKEND ORCHESTRATOR v3.0
# ============================================================

app = FastAPI(
    title="SourceSeal Tactical & OSINT Intelligence API v3.0",
    description="API unificada con ARTO, SEAL y Threat Intelligence",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.mount("/reports", StaticFiles(directory=CONFIG["report_dir"]), name="reports")


@app.on_event("startup")
async def startup_event():
    init_db()

    if CONFIG["arto_enabled"]:
        await arto_integration.start()
        print("  ARTO inicializado")

    if CONFIG["seal_enabled"]:
        print("  SEAL SUPER PACK listo")

    print("  SourceSeal Backend v3.0 - Listo para operar")


@app.on_event("shutdown")
async def shutdown_event():
    print("  Deteniendo SourceSeal Backend...")


# ============================================================
# ENDPOINTS DE ESCANEO
# ============================================================

class ScanRequest(BaseModel):
    network: str = "192.168.0.0/24"
    deep: bool = False
    use_seal: bool = True
    use_arto: bool = True


@app.post("/api/v1/scan")
async def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    try:
        ipaddress.ip_network(request.network, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de red CIDR inválido")

    background_tasks.add_task(
        run_full_audit,
        request.network,
        request.deep,
        request.use_seal,
        request.use_arto
    )

    return {
        "status": "success",
        "message": f"Escaneo iniciado para {request.network}",
        "scan_id": f"scan_{int(time.time())}",
        "features": {
            "use_seal": request.use_seal,
            "use_arto": request.use_arto,
            "deep_scan": request.deep
        }
    }


@app.get("/api/v1/scan/quick")
async def quick_scan(network: str = "192.168.0.0/24"):
    try:
        ipaddress.ip_network(network, strict=False)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de red CIDR inválido")

    targets = await multi_layer_discovery(network)

    return {
        "status": "success",
        "network": network,
        "active_hosts": targets,
        "count": len(targets)
    }


@app.get("/api/v1/scan/{ip}")
async def scan_single_ip(ip: str, deep: bool = False):
    try:
        result = await scan_with_seal(ip, deep)
        threat_data = await threat_intel.check_all_sources(ip)

        arto_data = {}
        if CONFIG["arto_enabled"]:
            arto_data = await arto_integration.autonomous_scan(ip)

        return {
            "status": "success",
            "ip": ip,
            "scan_result": result,
            "threat_intel": threat_data,
            "arto_analysis": arto_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ENDPOINTS DE OSINT
# ============================================================

@app.get("/api/v1/osint")
async def trigger_osint(username: str):
    if not username or len(username.strip()) < 2:
        raise HTTPException(status_code=400, detail="Nombre de usuario inválido")

    data = verify_username_osint(username.strip())
    save_osint_db(username.strip(), data)

    report_data = {"username": username, "results": data}
    report_path = report_generator.save_report(report_data, "osint", "html")

    return {
        "status": "success",
        "username": username,
        "results": data,
        "report": report_path
    }


@app.post("/api/v1/osint/batch")
async def batch_osint(usernames: List[str]):
    results = {}
    for username in usernames:
        if username and len(username.strip()) >= 2:
            results[username] = verify_username_osint(username.strip())
            save_osint_db(username.strip(), results[username])

    return {
        "status": "success",
        "count": len(results),
        "results": results
    }


# ============================================================
# ENDPOINTS DE ARTO
# ============================================================

@app.get("/api/v1/arto/analyze")
async def arto_analyze(target: str):
    if not CONFIG["arto_enabled"]:
        raise HTTPException(status_code=503, detail="ARTO no está disponible")

    result = await arto_integration.autonomous_scan(target)
    return {"status": "success", "target": target, "result": result}


@app.get("/api/v1/arto/decision")
async def arto_decision(target: str, context: Optional[Dict] = None):
    if not CONFIG["arto_enabled"]:
        raise HTTPException(status_code=503, detail="ARTO no está disponible")

    if not context:
        context = {"target": target}

    result = await arto_integration.get_decision(context)
    return {"status": "success", "target": target, "decision": result}


@app.get("/api/v1/arto/predictions")
async def arto_predictions(timeframe: int = 24):
    if not CONFIG["arto_enabled"]:
        raise HTTPException(status_code=503, detail="ARTO no está disponible")

    result = await arto_integration.predict_attacks(timeframe)
    return {"status": "success", "timeframe": timeframe, "predictions": result}


@app.post("/api/v1/arto/simulate")
async def arto_simulate(attack_type: str, target: str):
    if not CONFIG["arto_enabled"]:
        raise HTTPException(status_code=503, detail="ARTO no está disponible")

    result = await arto_integration.simulate_attack(attack_type, target)
    return {"status": "success", "attack_type": attack_type, "target": target, "result": result}


# ============================================================
# ENDPOINTS DE SEAL
# ============================================================

@app.get("/api/v1/seal/network-sweep")
async def seal_network_sweep(network: str = "192.168.0.0/24", deep: bool = False):
    if not CONFIG["seal_enabled"]:
        raise HTTPException(status_code=503, detail="SEAL no está disponible")

    result = await seal_integration.network_sweep(network, deep)
    return {"status": "success", **result}


@app.get("/api/v1/seal/hikvision-attack")
async def seal_hikvision_attack(ip: str):
    if not CONFIG["seal_enabled"]:
        raise HTTPException(status_code=503, detail="SEAL no está disponible")

    result = await seal_integration.hikvision_attack(ip)

    if result.get("success"):
        await alert_system.broadcast_alert({
            "alert_type": "hikvision_attack",
            "severity": "critical",
            "title": f"Cámara Hikvision comprometida: {ip}",
            "description": f"Acceso exitoso a cámara en {ip}",
            "target": ip,
            "evidence": result,
            "mitre_attack": "T1110"
        })

    return {"status": "success", "ip": ip, "result": result}


@app.get("/api/v1/seal/onvif-scan")
async def seal_onvif_scan(network: str = "192.168.0.0/24"):
    if not CONFIG["seal_enabled"]:
        raise HTTPException(status_code=503, detail="SEAL no está disponible")

    result = await seal_integration.onvif_scan(network)
    return {"status": "success", "network": network, "result": result}


@app.get("/api/v1/seal/fingerprint/{ip}")
async def seal_fingerprint(ip: str):
    if not CONFIG["seal_enabled"]:
        raise HTTPException(status_code=503, detail="SEAL no está disponible")

    result = await seal_integration.fingerprint_device(ip)
    return {"status": "success", "ip": ip, "fingerprint": result}


# ============================================================
# ENDPOINTS DE THREAT INTELLIGENCE
# ============================================================

@app.get("/api/v1/threat/shodan/{ip}")
async def threat_shodan(ip: str):
    result = await threat_intel.check_shodan(ip)
    return {"status": "success", "ip": ip, "result": result}


@app.get("/api/v1/threat/virustotal/{ip}")
async def threat_virustotal(ip: str):
    result = await threat_intel.check_virustotal(ip)
    return {"status": "success", "ip": ip, "result": result}


@app.get("/api/v1/threat/abuseipdb/{ip}")
async def threat_abuseipdb(ip: str):
    result = await threat_intel.check_abuseipdb(ip)
    return {"status": "success", "ip": ip, "result": result}


@app.get("/api/v1/threat/all/{ip}")
async def threat_all(ip: str):
    result = await threat_intel.check_all_sources(ip)
    return {"status": "success", **result}


# ============================================================
# ENDPOINTS DE ALERTAS
# ============================================================

@app.get("/api/v1/alerts")
async def list_alerts(resolved: bool = False, limit: int = 100):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()

        if resolved:
            c.execute("SELECT * FROM realtime_alerts WHERE resolved = 1 ORDER BY id DESC LIMIT ?", (limit,))
        else:
            c.execute("SELECT * FROM realtime_alerts WHERE resolved = 0 ORDER BY id DESC LIMIT ?", (limit,))

        alerts = []
        for row in c.fetchall():
            alerts.append({
                "id": row[0],
                "alert_type": row[1],
                "severity": row[2],
                "title": row[3],
                "description": row[4],
                "target": row[5],
                "evidence": json.loads(row[6]) if row[6] else {},
                "timestamp": row[7],
                "resolved": bool(row[8]),
                "mitre_attack": row[9]
            })

        conn.close()

    return {"status": "success", "count": len(alerts), "alerts": alerts}


@app.post("/api/v1/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute("UPDATE realtime_alerts SET resolved = 1 WHERE id = ?", (alert_id,))
        conn.commit()
        conn.close()

    await alert_system.broadcast_alert({
        "alert_type": "alert_resolved",
        "severity": "info",
        "title": f"Alerta {alert_id} resuelta",
        "description": f"La alerta {alert_id} ha sido marcada como resuelta",
        "evidence": {"alert_id": alert_id}
    })

    return {"status": "success", "message": f"Alerta {alert_id} resuelta"}


# ============================================================
# ENDPOINTS DE INFORMES
# ============================================================

@app.get("/api/v1/reports")
async def list_reports(limit: int = 20):
    reports = []
    for filename in os.listdir(CONFIG["report_dir"]):
        if filename.endswith(('.html', '.pdf', '.enc')):
            filepath = os.path.join(CONFIG["report_dir"], filename)
            stat = os.stat(filepath)
            reports.append({
                "filename": filename,
                "path": f"/reports/{filename}",
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    reports.sort(key=lambda x: x["modified"], reverse=True)
    return {"status": "success", "count": len(reports), "reports": reports[:limit]}


@app.get("/api/v1/reports/{filename}")
async def get_report(filename: str):
    filepath = os.path.join(CONFIG["report_dir"], filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    if filename.endswith('.enc'):
        with open(filepath, 'r') as f:
            encrypted = f.read()
        decrypted = decrypt_data(encrypted)
        return HTMLResponse(content=decrypted, media_type="text/html")

    return FileResponse(filepath)


# ============================================================
# ENDPOINTS DE ESTADO
# ============================================================

@app.get("/api/v1/health")
async def health_check():
    arto_status = {"enabled": CONFIG["arto_enabled"]}
    if CONFIG["arto_enabled"]:
        arto_status["running"] = hasattr(arto_integration, 'arto') and getattr(arto_integration.arto, 'running', False)

    seal_status = {"enabled": CONFIG["seal_enabled"]}

    db_status = {"connected": True}
    try:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        conn.close()
    except:
        db_status["connected"] = False

    ws_status = {"active_connections": len(alert_system.connections)}

    return {
        "status": "online",
        "version": "3.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "encryption": "AES-256-Fernet Active",
        "osint_module": "Anti-False-Positive Verified",
        "components": {
            "arto": arto_status,
            "seal": seal_status,
            "database": db_status,
            "websocket": ws_status
        },
        "features": [
            "OSINT Validation",
            "Network Scanning",
            "ARTO Integration",
            "SEAL Integration",
            "Threat Intelligence",
            "Real-time Alerts",
            "Report Generation"
        ]
    }


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await alert_system.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_system.disconnect(websocket)


# ============================================================
# INICIO DEL SERVIDOR
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("    SOURCESEAL BACKEND v3.0 - INTELIGENCIA + OSINT + ARTO + SEAL")
    print("=" * 70)
    print("\n  Iniciando servidor...")
    print("    OSINT: Validador anti-falsos positivos")
    print("    ARTO: Operaciones autónomas con IA")
    print("    SEAL: Escaneo y ataque avanzado")
    print("    Threat Intelligence: Shodan, VirusTotal, AbuseIPDB")
    print("    WebSocket: Alertas en tiempo real")
    print("    Reports: Generación de informes profesionales")
    print("\n  API disponible en: http://localhost:8001")
    print("   Docs: http://localhost:8001/docs")
    print("   WebSocket: ws://localhost:8001/ws/alerts")
    print("=" * 70 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        reload=CONFIG.get("debug", True)
    )
