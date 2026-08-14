#!/usr/bin/env python3
"""
canary_monitor.py — Real-time Canary Alert Dashboard
=====================================================
Monitor en tiempo real que:
- Escucha triggers del SVG canary
- Muestra alertas en consola con colores
- Guarda timeline de eventos
- Envía notificaciones push (webhook/telegram/slack)
- Genera reporte forense acumulado

Uso:
    python canary_monitor.py --watch ./evidence/canary
    python canary_monitor.py --dashboard --port 8888
"""

import argparse
import json
import os
import time
import sys
from datetime import datetime
from pathlib import Path
import threading
import requests

# Colores para terminal
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

class CanaryMonitor:
    def __init__(self, evidence_dir="./evidence/canary", webhook_url=None):
        self.evidence_dir = Path(evidence_dir)
        self.webhook_url = webhook_url
        self.known_files = set()
        self.alert_count = 0
        self.timeline = []

    def start_watching(self):
        """Monitorea el directorio de evidencia en tiempo real"""

        print(f"{BOLD}{RED}🔴 SOURCESEAL CANARY MONITOR{RESET}")
        print(f"{CYAN}📁 Directorio: {self.evidence_dir}{RESET}")
        print(f"{CYAN}⏳ Escaneando cada 2 segundos...{RESET}")
        print(f"{CYAN}{'='*60}{RESET}\n")

        # Cargar archivos existentes
        if self.evidence_dir.exists():
            self.known_files = {f.name for f in self.evidence_dir.glob("*.json")}

        try:
            while True:
                self._check_new_triggers()
                time.sleep(2)
        except KeyboardInterrupt:
            self._print_summary()

    def _check_new_triggers(self):
        """Busca nuevos archivos de trigger"""

        if not self.evidence_dir.exists():
            return

        current_files = {f.name for f in self.evidence_dir.glob("*.json")}
        new_files = current_files - self.known_files

        for filename in new_files:
            filepath = self.evidence_dir / filename
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                self._process_trigger(data, filename)
            except Exception as e:
                print(f"{YELLOW}⚠️ Error leyendo {filename}: {e}{RESET}")

        self.known_files = current_files

    def _process_trigger(self, data, filename):
        """Procesa un trigger y muestra alerta"""

        self.alert_count += 1
        self.timeline.append(data)

        # Extraer datos clave
        token_id = data.get("token_id", "UNKNOWN")
        ip = data.get("client_ip", "UNKNOWN")
        ua = data.get("user_agent", "UNKNOWN")
        timestamp = data.get("timestamp", "UNKNOWN")
        geo = data.get("geo", {})
        screenshot = data.get("screenshot", None)

        # Banner de alerta
        print(f"\n{BOLD}{RED}{'🚨'*20}{RESET}")
        print(f"{BOLD}{RED}  CANARY TOKEN TRIGGERED! #{self.alert_count}{RESET}")
        print(f"{BOLD}{RED}{'🚨'*20}{RESET}")

        # Detalles
        print(f"{CYAN}  📋 Token ID:{RESET} {token_id}")
        print(f"{CYAN}  🌐 IP:{RESET} {ip}")
        print(f"{CYAN}  🕐 Time:{RESET} {timestamp}")

        # Geolocalización
        if geo and geo.get("status") == "success":
            print(f"{GREEN}  📍 Location:{RESET} {geo.get('city', 'N/A')}, {geo.get('country', 'N/A')}")
            print(f"{GREEN}  🏢 ISP:{RESET} {geo.get('isp', 'N/A')}")
            print(f"{GREEN}  🗺️  Coords:{RESET} {geo.get('lat', 'N/A')}, {geo.get('lon', 'N/A')}")

        # User Agent
        print(f"{YELLOW}  🔍 User-Agent:{RESET} {ua[:80]}...")

        # Screenshot
        if screenshot:
            print(f"{MAGENTA}  📸 Screenshot:{RESET} {screenshot}")

        # Headers sospechosos
        headers = data.get("headers", {})
        if headers:
            print(f"{BLUE}  📨 Headers clave:{RESET}")
            for key in ["Accept-Language", "Accept-Encoding", "Cookie", "Authorization"]:
                if key in headers:
                    print(f"     {key}: {headers[key][:50]}...")

        print(f"{CYAN}{'='*60}{RESET}\n")

        # Enviar notificación
        self._send_notification(data)

    def _send_notification(self, data):
        """Envía notificación webhook/telegram/slack"""

        if not self.webhook_url:
            return

        try:
            payload = {
                "text": f"🚨 CANARY TRIGGERED!\n"
                        f"Token: {data.get('token_id')}\n"
                        f"IP: {data.get('client_ip')}\n"
                        f"Time: {data.get('timestamp')}\n"
                        f"UA: {data.get('user_agent', 'N/A')[:50]}",
                "priority": "critical",
                "source": "sourceseal-canary",
            }

            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"{YELLOW}⚠️ Error enviando notificación: {e}{RESET}")

    def _print_summary(self):
        """Imprime resumen al detener"""

        print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
        print(f"{BOLD}{CYAN}  RESUMEN DE MONITOREO{RESET}")
        print(f"{BOLD}{CYAN}{'='*60}{RESET}")
        print(f"{GREEN}  Total alertas: {self.alert_count}{RESET}")
        print(f"{GREEN}  Archivos procesados: {len(self.known_files)}{RESET}")
        print(f"{GREEN}  Timeline guardado: {len(self.timeline)} eventos{RESET}")

        # Guardar reporte acumulado
        if self.timeline:
            report_path = self.evidence_dir / f"timeline_report_{int(time.time())}.json"
            with open(report_path, "w") as f:
                json.dump(self.timeline, f, indent=2, default=str)
            print(f"{GREEN}  Reporte: {report_path}{RESET}")

        print(f"{CYAN}{'='*60}{RESET}\n")


def start_dashboard(port=8888):
    """Inicia un dashboard web simple para ver alertas"""

    from http.server import HTTPServer, BaseHTTPRequestHandler

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self._serve_dashboard()
            elif self.path == "/api/alerts":
                self._serve_alerts_api()
            else:
                self.send_error(404)

        def _serve_dashboard(self):
            html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SourceSeal Canary Dashboard</title>
    <style>
        body { background: #0a0a0f; color: #e2e2e8; font-family: monospace; margin: 0; padding: 20px; }
        h1 { color: #ef4444; text-align: center; }
        .alert { background: #141419; border: 1px solid #2a2a3a; border-radius: 8px; padding: 15px; margin: 10px 0; }
        .alert.critical { border-color: #ef4444; }
        .timestamp { color: #6b7280; font-size: 12px; }
        .ip { color: #06b6d4; font-weight: bold; }
        .token { color: #f59e0b; }
        .location { color: #10b981; }
        .ua { color: #a1a1aa; font-size: 11px; word-break: break-all; }
        #stats { display: flex; gap: 20px; justify-content: center; margin: 20px 0; }
        .stat { background: #141419; padding: 15px 25px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #ef4444; }
        .stat-label { font-size: 12px; color: #6b7280; }
    </style>
</head>
<body>
    <h1>🔴 SOURCESEAL CANARY DASHBOARD</h1>
    <div id="stats">
        <div class="stat"><div class="stat-value" id="alert-count">0</div><div class="stat-label">ALERTAS</div></div>
        <div class="stat"><div class="stat-value" id="unique-ips">0</div><div class="stat-label">IPs ÚNICAS</div></div>
        <div class="stat"><div class="stat-value" id="tokens">0</div><div class="stat-label">TOKENS</div></div>
    </div>
    <div id="alerts"></div>
    <script>
        async function loadAlerts() {
            const resp = await fetch('/api/alerts');
            const data = await resp.json();

            document.getElementById('alert-count').textContent = data.length;
            const uniqueIps = new Set(data.map(a => a.client_ip)).size;
            document.getElementById('unique-ips').textContent = uniqueIps;
            const uniqueTokens = new Set(data.map(a => a.token_id)).size;
            document.getElementById('tokens').textContent = uniqueTokens;

            const container = document.getElementById('alerts');
            container.innerHTML = data.slice(-20).reverse().map(alert => `
                <div class="alert critical">
                    <div class="timestamp">🕐 ${alert.timestamp}</div>
                    <div>🔑 Token: <span class="token">${alert.token_id}</span></div>
                    <div>🌐 IP: <span class="ip">${alert.client_ip}</span></div>
                    ${alert.geo && alert.geo.city ? `<div class="location">📍 ${alert.geo.city}, ${alert.geo.country}</div>` : ''}
                    <div class="ua">🔍 ${alert.user_agent}</div>
                    ${alert.screenshot ? `<div>📸 Screenshot: ${alert.screenshot}</div>` : ''}
                </div>
            `).join('');
        }

        loadAlerts();
        setInterval(loadAlerts, 3000);
    </script>
</body>
</html>"""

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        def _serve_alerts_api(self):
            evidence_dir = Path("./evidence/canary")
            alerts = []

            if evidence_dir.exists():
                for f in sorted(evidence_dir.glob("canary_trigger_*.json")):
                    try:
                        with open(f) as file:
                            alerts.append(json.load(file))
                    except:
                        pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(alerts).encode())

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"{GREEN}📊 Dashboard iniciado en http://localhost:{port}{RESET}")
    print(f"{CYAN}🌐 Abre el navegador para ver alertas en tiempo real{RESET}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}🛑 Dashboard detenido{RESET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SourceSeal Canary Monitor")
    parser.add_argument("--watch", default="./evidence/canary", help="Directorio de evidencia")
    parser.add_argument("--webhook", help="URL de webhook para notificaciones")
    parser.add_argument("--dashboard", action="store_true", help="Iniciar dashboard web")
    parser.add_argument("--port", type=int, default=8888, help="Puerto del dashboard")

    args = parser.parse_args()

    if args.dashboard:
        start_dashboard(args.port)
    else:
        monitor = CanaryMonitor(args.watch, args.webhook)
        monitor.start_watching()
