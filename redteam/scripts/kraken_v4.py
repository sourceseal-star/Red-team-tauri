#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRAKEN v4.0 — Motor de Explotación con NSE scripts (sin dependencias externas)
Uso: python3 kraken_v4.py
"""

import os, sys, time, json, sqlite3, subprocess, re, signal
from datetime import datetime
import xml.etree.ElementTree as ET

# ============================================================
# 1. CONFIGURACIÓN
# ============================================================
TARGETS = ["192.168.1.0/24"]
SCAN_INTERVAL = 3600  # 1 hora
DB_PATH = os.path.expanduser("~/kraken_v4.db")
LOG_FILE = os.path.expanduser("~/kraken_v4.log")
NSE_SCRIPTS = [
    "ssh-brute", "ftp-anon", "ftp-brute",
    "smb-os-discovery", "smb-enum-shares", "smb-vuln-*",
    "http-auth-finder", "http-vuln-*",
    "rtsp-url-brute", "mysql-empty-password",
    "pgsql-brute", "redis-info",
    "rdp-vuln-ms12-020", "snmp-info",
]
KRAKEN_PORTS = "21,22,23,25,80,110,139,143,443,445,554,993,995,1723,3306,3389,5432,5900,6379,8080,8443,27017"

# ============================================================
# 2. LOGGER
# ============================================================
def log(msg, level="INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{ts}] [{level}] {msg}\n")
    print(f"[{ts}] {msg}")

# ============================================================
# 3. BASE DE DATOS
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS hosts (ip TEXT PRIMARY KEY, last_seen TEXT, os TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS exploits (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, port INTEGER, service TEXT, vulnerability TEXT, cve TEXT, attempted_at TEXT, success INTEGER DEFAULT 0, output TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS scan_log (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, started_at TEXT, hosts_found INTEGER, exploits_found INTEGER)")
    conn.commit()
    conn.close()
    log("Base de datos inicializada")

# ============================================================
# 4. ESCANEO CON NSE SCRIPTS
# ============================================================
def run_nse_scan(target):
    scripts_str = ",".join(NSE_SCRIPTS)
    cmd = [
        "nmap", "-sV", "-O", "--script", scripts_str,
        "-p", KRAKEN_PORTS, "-oX", "-", target
    ]
    log(f"Ejecutando NSE contra {target}...")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=180)
        if proc.returncode != 0:
            log(f"Error en nmap: {err[:200]}", "ERROR")
            return None
        return out
    except subprocess.TimeoutExpired:
        proc.kill()
        log("Tiempo de escaneo agotado", "ERROR")
        return None
    except FileNotFoundError:
        log("nmap no instalado. Instala con: pkg install nmap", "ERROR")
        return None

# ============================================================
# 5. PARSEO AVANZADO
# ============================================================
def parse_nse_output(xml_data):
    if not xml_data:
        return []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        log("Error parseando XML", "WARN")
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
        os_name = os_elem.get('name') if os_elem is not None else "Unknown"
        host_data = {"ip": ip, "os": os_name, "exploits": []}

        for port in host.findall('ports/port'):
            port_id = port.get('portid')
            service = port.find('service')
            service_name = service.get('name') if service is not None else "unknown"
            for script in port.findall('script'):
                script_id = script.get('id')
                output = script.get('output', '')
                keywords = ['VULNERABLE', 'password', 'credentials', 'anonymous', 'Null', 'brute', 'weak', 'empty password', 'default']
                found = any(k.lower() in output.lower() for k in keywords)
                if found:
                    cve_match = re.search(r'(CVE-\d{4}-\d{4,7})', output)
                    cve = cve_match.group(1) if cve_match else "N/A"
                    host_data["exploits"].append({
                        "port": int(port_id),
                        "service": service_name,
                        "script": script_id,
                        "vulnerability": output[:200],
                        "cve": cve,
                        "success": 1
                    })
        if host_data["exploits"]:
            hosts.append(host_data)
    return hosts

# ============================================================
# 6. GUARDAR RESULTADOS
# ============================================================
def save_results(target, hosts_data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    total_exploits = 0
    for host in hosts_data:
        ip = host["ip"]
        c.execute("INSERT OR REPLACE INTO hosts (ip, last_seen, os) VALUES (?, ?, ?)",
                  (ip, datetime.utcnow().isoformat(), host["os"]))
        for exp in host["exploits"]:
            c.execute("INSERT INTO exploits (ip, port, service, vulnerability, cve, attempted_at, success, output) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (ip, exp["port"], exp["service"], exp["vulnerability"], exp["cve"],
                       datetime.utcnow().isoformat(), exp["success"], exp["vulnerability"]))
            if exp["success"]:
                total_exploits += 1
                log(f"  {exp['service']}:{exp['port']} -> {exp['vulnerability'][:60]}...")
    c.execute("INSERT INTO scan_log (target, started_at, hosts_found, exploits_found) VALUES (?, ?, ?, ?)",
              (target, datetime.utcnow().isoformat(), len(hosts_data), total_exploits))
    conn.commit()
    conn.close()
    return total_exploits

# ============================================================
# 7. APRENDIZAJE
# ============================================================
def get_priorities():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ip, COUNT(*) as cnt FROM exploits WHERE success = 1 GROUP BY ip ORDER BY cnt DESC LIMIT 5")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

# ============================================================
# 8. DAEMON
# ============================================================
running = True

def signal_handler(sig, frame):
    global running
    log("Senal recibida. Cerrando...")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main_loop():
    init_db()
    log("KRAKEN v4.0 iniciado (NSE scripts)")
    log(f"Targets: {TARGETS}")
    log(f"Intervalo: {SCAN_INTERVAL // 60} min")
    log(f"Scripts NSE: {len(NSE_SCRIPTS)}")

    while running:
        for target in TARGETS:
            if not running:
                break
            xml = run_nse_scan(target)
            if xml:
                hosts = parse_nse_output(xml)
                if hosts:
                    total = save_results(target, hosts)
                    log(f"Ciclo completado. Hosts vulnerables: {len(hosts)} | Exploits: {total}")
                    priorities = get_priorities()
                    if priorities:
                        log(f"Prioridades (IPs mas explotables): {priorities}")
                else:
                    log("No se encontraron vulnerabilidades en este ciclo.")
            else:
                log("Fallo el escaneo.")
        if running:
            log(f"Esperando {SCAN_INTERVAL // 60} min...")
            for _ in range(SCAN_INTERVAL // 10):
                if not running:
                    break
                time.sleep(10)
    log("KRAKEN detenido.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--target":
        TARGETS = [sys.argv[2]]
    if len(sys.argv) > 2 and sys.argv[2] == "--interval":
        SCAN_INTERVAL = int(sys.argv[3])
    main_loop()
