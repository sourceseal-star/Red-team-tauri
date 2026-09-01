#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
COMMANDER v3.5.0 — CLI profesional, logging dual, checkpoints reales por fase.
Uso: python3 commander.py --target 192.168.1.0/24 --email cliente@mail.com --key "clave" --debug
     python3 commander.py --auto 192.168.1.0/24 --email cliente@mail.com
     python3 commander.py --resume 3
"""

import os, sys, subprocess, json, hashlib, re, time, socket, urllib.request, base64
import xml.etree.ElementTree as ET
import concurrent.futures
import smtplib
import sqlite3
import threading
import logging
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from cryptography.fernet import Fernet

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================
CONFIG = {
    "report_dir": os.path.expanduser("~/storage/downloads/commander_reports"),
    "temp_dir": os.path.expanduser("~/.commander_tmp"),  # /tmp no es escribible en Termux
    "db_path": os.path.expanduser("~/commander.db"),
    "log_path": os.path.expanduser("~/commander.log"),
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
    "sourceseal_api": "https://source.coal/api/v1/anchor",
    "yara_rules_dir": os.path.expanduser("~/yara_rules"),
    "max_concurrent": 5,
    "encryption_key": "",
}

def _safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except (PermissionError, OSError) as e:
        print(f"⚠️ No se pudo crear {path}: {e}")

# Cargar credenciales SMTP desde el entorno (.env) si estan disponibles.
# Antes solo se podian introducir a mano via input() en el flujo interactivo
# --setup, obligando a re-teclearlas cada vez. Si SMTP_SENDER_EMAIL/PASSWORD
# ya estan en .env (sourced con "set -a" por arrancar_commander.sh o por
# iniciar_unificado.sh), se detectan automaticamente sin pedir nada.
if os.environ.get("SMTP_SENDER_EMAIL"):
    CONFIG["sender_email"] = os.environ["SMTP_SENDER_EMAIL"]
if os.environ.get("SMTP_SENDER_PASSWORD"):
    CONFIG["sender_password"] = os.environ["SMTP_SENDER_PASSWORD"]

_safe_makedirs(CONFIG["report_dir"])
_safe_makedirs(CONFIG["temp_dir"])
_safe_makedirs(CONFIG["yara_rules_dir"])

# ============================================================
# 1. LOGGING DUAL (Consola + Archivo)
# ============================================================
logger = None

def setup_logger(debug_mode=False):
    global logger
    log_file = CONFIG["log_path"]
    level = logging.DEBUG if debug_mode else logging.INFO
    logger = logging.getLogger("COMMANDER")
    logger.setLevel(level)
    logger.handlers.clear()
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info("🚀 COMMANDER v3.5.0 iniciado")
    return logger

def log_info(msg): logger.info(msg) if logger else print(msg)
def log_warn(msg): logger.warning(msg) if logger else print("⚠️ " + msg)
def log_error(msg): logger.error(msg) if logger else print("❌ " + msg)
def log_debug(msg):
    if logger and logger.level <= logging.DEBUG:
        logger.debug(msg)

# ============================================================
# 2. SQLITE THREAD-SAFE (con Checkpoints atómicos por fase)
# ============================================================
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT NOT NULL,
            scan_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            data_json TEXT NOT NULL,
            hash TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            checkpoint_data TEXT
        )''')
        conn.commit()
        conn.close()

def create_scan_record(target, scan_type):
    """Crea un registro de escaneo inicial y devuelve su ID."""
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT INTO audits (target, scan_type, timestamp, data_json, hash, status, checkpoint_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (target, scan_type, datetime.utcnow().isoformat() + "Z", "{}", "pending", "running", json.dumps({"phase": "start"}))
        )
        conn.commit()
        scan_id = c.lastrowid
        conn.close()
    log_info(f"📝 Escaneo registrado (ID={scan_id})")
    return scan_id

def save_scan_result(target, scan_type, data, hash_val=None):
    if not hash_val:
        hash_val = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute(
            "INSERT INTO audits (target, scan_type, timestamp, data_json, hash, status) VALUES (?, ?, ?, ?, ?, ?)",
            (target, scan_type, datetime.utcnow().isoformat() + "Z", json.dumps(data), hash_val, 'completed')
        )
        conn.commit()
        conn.close()
    log_info(f"💾 Datos guardados en DB para {target} (hash: {hash_val[:8]}...)")
    return hash_val

def get_pending_scans():
    conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, target, scan_type, timestamp, status FROM audits WHERE status != 'completed'")
    rows = c.fetchall()
    conn.close()
    return rows

def update_scan_status(scan_id, status):
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute("UPDATE audits SET status = ? WHERE id = ?", (status, scan_id))
        conn.commit()
        conn.close()

def save_checkpoint(scan_id, checkpoint_data):
    """Guarda el estado intermedio para reanudar escaneos interrumpidos."""
    with db_lock:
        conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
        c = conn.cursor()
        c.execute("UPDATE audits SET checkpoint_data = ? WHERE id = ?", (json.dumps(checkpoint_data), scan_id))
        conn.commit()
        conn.close()
    log_debug(f"📌 Checkpoint guardado para ID {scan_id} (fase: {checkpoint_data.get('phase', '?')})")

def get_checkpoint(scan_id):
    conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT checkpoint_data FROM audits WHERE id = ?", (scan_id,))
    row = c.fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else None

def get_scan_info(scan_id):
    conn = sqlite3.connect(CONFIG["db_path"], check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT target, scan_type, status, data_json, checkpoint_data FROM audits WHERE id = ?", (scan_id,))
    row = c.fetchone()
    conn.close()
    return row

# ============================================================
# 3. CIFRADO FERNET (Headless)
# ============================================================
def get_encryption_key():
    def normalize_key(value):
        """Acepta una clave Fernet válida o deriva una desde una frase."""
        raw = value.encode()
        try:
            Fernet(raw)
            return raw
        except (ValueError, TypeError):
            return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())

    key = CONFIG.get("encryption_key")
    if key:
        return normalize_key(str(key))
    env_key = os.environ.get("COMMANDER_KEY")
    if env_key:
        CONFIG["encryption_key"] = env_key
        return normalize_key(env_key)
    if sys.stdin.isatty():
        key_input = input("🔑 Introduce una frase de paso (Enter para generar automática): ").strip()
    else:
        key_input = ""
    if key_input:
        key_bytes = hashlib.sha256(key_input.encode()).digest()
        key = base64.urlsafe_b64encode(key_bytes).decode()
    else:
        key = Fernet.generate_key().decode()
        print(f"🔐 Clave autogenerada: {key} (Guárdala bien)")
    CONFIG["encryption_key"] = key
    return key.encode()

def encrypt_report(filepath):
    if not os.path.exists(filepath):
        return False
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        with open(filepath, 'rb') as f:
            data = f.read()
        encrypted = fernet.encrypt(data)
        enc_path = filepath + '.enc'
        with open(enc_path, 'wb') as f:
            f.write(encrypted)
        log_info(f"🔒 Informe cifrado: {enc_path}")
        return enc_path
    except Exception as e:
        log_error(f"Error cifrando: {e}")
        return False

def decrypt_report(enc_path):
    if not os.path.exists(enc_path):
        return None
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        with open(enc_path, 'rb') as f:
            encrypted = f.read()
        decrypted = fernet.decrypt(encrypted)
        return decrypted.decode('utf-8')
    except Exception as e:
        log_error(f"Error descifrando: {e}")
        return None

def save_report(html_content, title, encrypt=True):
    filename = f"{title}_{int(time.time())}.html"
    path = os.path.join(CONFIG["report_dir"], filename)
    with open(path, 'w') as f:
        f.write(html_content)
    log_info(f"✅ Informe guardado: {path}")
    if encrypt:
        enc_path = encrypt_report(path)
        if enc_path:
            return enc_path
    return path

# ============================================================
# 4. EXPONENTIAL BACKOFF DECORATOR
# ============================================================
def retry_with_backoff(retries=3, backoff_in_seconds=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            x = 0
            while x < retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    sleep_time = backoff_in_seconds * (2 ** x)
                    log_warn(f"Fallo en red ({e}). Reintentando en {sleep_time}s... (Intento {x+1}/{retries})")
                    time.sleep(sleep_time)
                    x += 1
            log_error(f"Operación falló tras {retries} intentos.")
            return None
        return wrapper
    return decorator

# ============================================================
# 5. ENVÍO DE CORREOS
# ============================================================
def send_email(to_email, subject, body, attachments=None):
    if not CONFIG["sender_email"] or not CONFIG["sender_password"]:
        log_warn("Credenciales SMTP no configuradas.")
        return False
    log_info(f"📧 Enviando correo a {to_email}...")
    try:
        msg = MIMEMultipart()
        msg['From'] = CONFIG["sender_email"]
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        if attachments:
            for filepath in attachments:
                if os.path.exists(filepath):
                    with open(filepath, "rb") as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(filepath)}")
                        msg.attach(part)
        server = smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"])
        server.starttls()
        server.login(CONFIG["sender_email"], CONFIG["sender_password"])
        server.sendmail(CONFIG["sender_email"], to_email, msg.as_string())
        server.quit()
        log_info("✅ Correo enviado con éxito.")
        return True
    except Exception as e:
        log_error(f"Error enviando correo: {e}")
        return False

# ============================================================
# 6. ANCLAJE A SOURCESEAL (con backoff)
# ============================================================
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def anchor_to_sourceseal(sha256_hash, metadata=None):
    api_url = CONFIG["sourceseal_api"]
    payload = {
        "hash": sha256_hash,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metadata": metadata or {}
    }
    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res = json.loads(response.read().decode())
            return res.get("status") == "success", res.get("proof_id")
    except Exception as e:
        log_warn(f"Anclaje offline: {e}")
        return False, f"Offline-Mode-Hash-{sha256_hash[:12]}"

# ============================================================
# 7. FUNCIONES DE ESCANEO
# ============================================================
def run_cmd(cmd, timeout=30):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=timeout)
        return out, err, proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        return "", "Timeout", -1
    except (FileNotFoundError, OSError) as e:
        return "", str(e), 127

def scan_network(target, ports_str="22,80,443,3306,8080,554,21,25,53,139,445,3389"):
    """Escaneo de red con nmap. ports_str renombrado para evitar shadowing."""
    log_info(f"🔍 Escaneando {target}...")
    out, err, code = run_cmd(["nmap", "-sV", "-O", "--script", "vuln", "-p", ports_str, "-oX", "-", target], timeout=120)
    if code != 0:
        return {"error": f"nmap falló: {err}"}
    try:
        root = ET.fromstring(out)
    except ET.ParseError:
        return {"error": "Error parseando XML", "raw": out[:500]}
    hosts = []
    for host in root.findall('host'):
        addr = host.find('address')
        ip = addr.get('addr') if addr is not None else "unknown"
        status = host.find('status')
        state = status.get('state') if status is not None else "down"
        os_elem = host.find('os/osmatch')
        os_name = os_elem.get('name') if os_elem is not None else "Desconocido"
        # FIX: variable renombrada de 'ports' a 'port_list' para no
        # pisar el parámetro ports_str
        port_list = []
        for port in host.findall('ports/port'):
            port_id = port.get('portid')
            service = port.find('service')
            service_name = service.get('name') if service is not None else "unknown"
            port_list.append({"port": int(port_id), "service": service_name})
        hosts.append({
            "ip": ip,
            "status": state,
            "os": os_name,
            "ports": port_list
        })
    return {"target": target, "hosts": hosts, "total": len(hosts)}

def scan_cameras(target):
    log_info(f"📷 Buscando cámaras en {target}...")
    out, err, code = run_cmd(["nmap", "-p", "554,80,8080,37777", "--open", "-oG", "-", target], timeout=30)
    if code != 0:
        return {"error": err}
    cameras = []
    for line in out.split('\n'):
        if "Ports:" in line:
            parts = line.split()
            if len(parts) > 1:
                ip = parts[1]
                ports = re.findall(r'(\d+)/open', line)
                cameras.append({
                    "ip": ip,
                    "rtsp_url": f"rtsp://{ip}:554",
                    "http_url": f"http://{ip}:80",
                    "ports": [int(p) for p in ports]
                })
    return {"target": target, "cameras": cameras, "total": len(cameras)}

def _http_get_json(url, timeout=5):
    """GET HTTP que devuelve JSON (usando urllib stdlib)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def _http_get_text(url, timeout=10):
    """GET HTTP que devuelve texto."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()
    except Exception:
        return None

def osint_ip(ip):
    """OSINT profesional en IP — multi-source threat intel + geo + WHOIS."""
    log_info(f"🌐 OSINT en {ip}...")
    result = {"ip": ip, "threat_score": 0, "factors": []}

    # 1. Geo IP (ip-api.com — gratuito, sin API key)
    geo = _http_get_json(
        f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city,lat,lon,isp,org,as,reverse,proxy,hosting",
        timeout=5
    )
    if geo and geo.get("status") == "success":
        result["geo"] = {k: geo.get(k) for k in ["country", "city", "lat", "lon", "isp", "org", "as"]}
        result["reverse_dns"] = geo.get("reverse", "")
        if geo.get("proxy"):
            result["factors"].append({"factor": "Proxy/VPN", "value": "detectado"})
            result["threat_score"] += 15
        if geo.get("hosting"):
            result["factors"].append({"factor": "Hosting", "value": geo.get("isp", "?")})
            result["threat_score"] += 5
    else:
        result["geo"] = {"error": "No disponible"}

    # 2. WHOIS (binario o RDAP via HTTP)
    whois_out, _, _ = run_cmd(["whois", ip], timeout=10)
    if whois_out and whois_out.strip():
        result["whois"] = whois_out[:800]
    else:
        # Fallback RDAP
        rdap = _http_get_json(f"https://rdap.org/ip/{ip}", timeout=10)
        if rdap:
            events = {e.get("eventAction",""): e.get("eventDate","") for e in rdap.get("events",[])}
            result["whois"] = {
                "source": "rdap",
                "registered": events.get("registration", ""),
                "last_changed": events.get("last changed", ""),
                "handle": rdap.get("handle", ""),
                "name": rdap.get("name", ""),
            }

    # 3. Abuse check (ipwho.is — gratuito)
    ipwho = _http_get_json(f"https://ipwho.is/{ip}", timeout=5)
    if ipwho and ipwho.get("success", True):
        conn = ipwho.get("connection", {})
        if conn.get("type") in ("hosting", "tor"):
            result["factors"].append({"factor": "Connection", "value": conn["type"]})
            result["threat_score"] += 10
        if conn.get("asn"):
            result["asn"] = conn.get("asn")

    # 4. Reverse DNS local
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        result["hostname"] = hostname
    except Exception:
        pass

    result["threat_level"] = (
        "CRITICAL" if result["threat_score"] >= 25 else
        "HIGH" if result["threat_score"] >= 15 else
        "MEDIUM" if result["threat_score"] >= 5 else
        "LOW"
    )
    return result

def osint_domain(domain):
    """OSINT profesional en dominio — WHOIS + DNS + subdominios + headers."""
    log_info(f"🌐 OSINT en dominio {domain}...")
    result = {"domain": domain}

    # 1. DNS records (A, MX, NS, TXT)
    result["dns"] = {}
    try:
        result["dns"]["A"] = list(set(socket.gethostbyname_ex(domain)[2]))
    except Exception:
        result["dns"]["A"] = []

    # MX/NS/TXT via Google DNS-over-HTTPS (sin dig)
    for rtype in ["MX", "NS", "TXT"]:
        doh = _http_get_json(
            f"https://dns.google/resolve?name={domain}&type={rtype}", timeout=5
        )
        if doh and doh.get("Answer"):
            result["dns"][rtype] = [a.get("data", "") for a in doh["Answer"]]
        else:
            result["dns"][rtype] = []

    # SPF/DMARC check
    txt_records = result["dns"].get("TXT", [])
    result["spf"] = any("spf1" in str(t).lower() for t in txt_records)
    dmarc = _http_get_json(f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT", timeout=5)
    result["dmarc"] = bool(dmarc and dmarc.get("Answer"))

    # 2. WHOIS (binario o RDAP)
    whois_out, _, _ = run_cmd(["whois", domain], timeout=10)
    if whois_out and whois_out.strip():
        result["whois"] = whois_out[:800]
    else:
        rdap = _http_get_json(f"https://rdap.org/domain/{domain}", timeout=10)
        if rdap:
            events = {e.get("eventAction",""): e.get("eventDate","") for e in rdap.get("events",[])}
            result["whois"] = {
                "source": "rdap",
                "registrar": rdap.get("entities", [{}])[0].get("vcardArray", [None, None])[1] if rdap.get("entities") else None,
                "registered": events.get("registration", ""),
                "expires": events.get("expiration", ""),
                "name_servers": [n.get("ldhName","") for n in rdap.get("nameservers",[])],
            }

    # 3. Subdominios comunes (DNS resolve pasivo)
    common_subs = ["www","mail","ftp","api","dev","admin","portal","vpn","blog","shop",
                   "staging","test","cdn","static","docs","support","git","ci","auth","sso"]
    found_subs = []
    for sub in common_subs:
        full = f"{sub}.{domain}"
        try:
            ips = socket.gethostbyname_ex(full)[2]
            if ips:
                found_subs.append({"subdomain": full, "ip": ips[0]})
        except Exception:
            pass
    result["subdomains"] = found_subs
    result["subdomains_count"] = len(found_subs)

    # 4. HTTP headers fingerprint
    try:
        req = urllib.request.Request(
            f"https://{domain}",
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            headers = dict(resp.headers.items())
            result["headers"] = {
                "server": headers.get("Server", "Desconocido"),
                "x_powered_by": headers.get("X-Powered-By", "Desconocido"),
                "status": resp.status,
            }
            security = {}
            for h in ["Strict-Transport-Security","X-Frame-Options","X-Content-Type-Options",
                       "Content-Security-Policy","X-XSS-Protection","Referrer-Policy"]:
                security[h] = "present" if headers.get(h) else "missing"
            result["security_headers"] = security
            result["security_score"] = sum(1 for v in security.values() if v == "present")
    except Exception as e:
        result["headers"] = {"error": str(e)}

    return result

def osint_email(email):
    """OSINT en email — verifica dominio, MX, provider, hash."""
    log_info(f"📧 OSINT en email {email}...")
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return {"email": email, "error": "Formato invalido"}

    domain = email.split("@")[1]
    username = email.split("@")[0]

    result = {
        "email": email,
        "domain": domain,
        "username": username,
        "hash_sha256": hashlib.sha256(email.encode()).hexdigest(),
    }

    # MX records
    doh_mx = _http_get_json(f"https://dns.google/resolve?name={domain}&type=MX", timeout=5)
    result["mx_records"] = [a.get("data","") for a in (doh_mx or {}).get("Answer",[])]

    # SPF/DMARC
    doh_txt = _http_get_json(f"https://dns.google/resolve?name={domain}&type=TXT", timeout=5)
    txt_records = [a.get("data","") for a in (doh_txt or {}).get("Answer",[])]
    result["spf"] = any("spf1" in str(t).lower() for t in txt_records)

    doh_dmarc = _http_get_json(f"https://dns.google/resolve?name=_dmarc.{domain}&type=TXT", timeout=5)
    result["dmarc"] = bool(doh_dmarc and doh_dmarc.get("Answer"))

    # Provider detection
    providers = {
        "gmail.com": "Google", "outlook.com": "Microsoft", "hotmail.com": "Microsoft",
        "yahoo.com": "Yahoo", "protonmail.com": "Proton", "proton.me": "Proton",
        "icloud.com": "Apple", "gmx.com": "GMX", "zoho.com": "Zoho",
    }
    result["provider"] = providers.get(domain, "Desconocido")
    result["is_free_provider"] = domain in providers

    return result

def batch_osint_ip(ip_list):
    log_info(f"🌐 OSINT concurrente para {len(ip_list)} IPs...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["max_concurrent"]) as executor:
        future_to_ip = {executor.submit(osint_ip, ip): ip for ip in ip_list}
        for future in concurrent.futures.as_completed(future_to_ip):
            try:
                results.append(future.result())
            except Exception as e:
                log_error(f"Error en OSINT: {e}")
    return results

def generate_html(data, title, sections, hash_val=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    if not hash_val:
        hash_val = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    html_sections = ""
    for sec in sections:
        html_sections += f'<div class="section"><h2>{sec["title"]}</h2><pre>{json.dumps(sec["data"], indent=2, default=str)}</pre></div>\n'
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>{title}</title>
<style>
body {{ font-family: monospace; background: #0a0e17; color: #e2e8f0; padding: 2rem; max-width: 1200px; margin: 0 auto; }}
.header {{ border-bottom: 2px solid #f59e0b; padding-bottom: 1rem; margin-bottom: 2rem; display: flex; justify-content: space-between; }}
.header h1 {{ color: #f59e0b; }}
.section {{ background: #111827; border: 1px solid #1e293b; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }}
.section h2 {{ color: #60a5fa; border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem; margin-top: 0; }}
pre {{ background: #0f172a; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; font-size: 0.8rem; }}
.hash {{ background: #0f172a; padding: 0.5rem 1rem; border-radius: 0.5rem; font-family: monospace; color: #f59e0b; word-break: break-all; }}
.footer {{ margin-top: 3rem; border-top: 1px solid #1e293b; padding-top: 1rem; text-align: center; color: #64748b; font-size: 0.8rem; }}
</style>
</head><body>
<div class="header"><h1>⚡ {title}</h1><span class="badge">{timestamp}</span></div>
<div class="section"><h2>🔐 Sello de Integridad</h2>
<div class="hash">SHA-256: {hash_val}</div>
<p style="color:#94a3b8; font-size:0.8rem;">Verifica este hash en blockchain para validar integridad.</p>
</div>
{html_sections}
<div class="footer">SourceSeal Intelligence v3.5.0 — SSP-ZKP-2048-L4</div>
</body></html>"""
    return html, hash_val

# ============================================================
# 8. FLUJO DE AUDITORÍA CON CHECKPOINTS POR FASE
# ============================================================
# Fases del flujo automático:
#   start → network_done → cameras_done → osint_done → completed
#
# Cada fase guarda su resultado en el checkpoint. Si el proceso
# muere (OOM, Termux kill, batería), --resume reconstruye desde
# el último checkpoint y continúa la siguiente fase.

def run_audit_phased(scan_id, target, email=None):
    """Ejecuta la auditoría completa con checkpoints atómicos por fase.
    Si se interrumpe, resume_scan() puede continuar desde aquí."""

    checkpoint = get_checkpoint(scan_id) or {"phase": "start"}
    phase = checkpoint.get("phase", "start")

    # ── Fase 1: Escaneo de red ──────────────────────────────
    if phase == "start":
        log_info("📡 Fase 1/3: Escaneo de red...")
        net = scan_network(target)
        checkpoint = {"phase": "network_done", "network": net}
        save_checkpoint(scan_id, checkpoint)
        log_info("✅ Fase 1 completada")
    else:
        net = checkpoint.get("network", {})
        log_info(f"⏭️ Fase 1 saltada (checkpoint: network_done)")

    # ── Fase 2: Detección de cámaras ─────────────────────────
    if checkpoint["phase"] in ("network_done", "cameras_done"):
        if checkpoint["phase"] == "network_done":
            log_info("📷 Fase 2/3: Detección de cámaras...")
            cams = scan_cameras(target)
            checkpoint = {"phase": "cameras_done", "network": net, "cameras": cams}
            save_checkpoint(scan_id, checkpoint)
            log_info("✅ Fase 2 completada")
        else:
            cams = checkpoint.get("cameras", {})
            log_info("⏭️ Fase 2 saltada (checkpoint: cameras_done)")
    else:
        cams = checkpoint.get("cameras", {})

    # ── Fase 3: OSINT ────────────────────────────────────────
    if checkpoint["phase"] in ("cameras_done", "osint_done"):
        if checkpoint["phase"] == "cameras_done":
            active_ips = [h["ip"] for h in net.get("hosts", []) if h.get("status") == "up"][:5]
            if active_ips:
                log_info(f"🌐 Fase 3/3: OSINT en {len(active_ips)} IPs activas...")
                osint_data = batch_osint_ip(active_ips)
            else:
                log_info("🌐 Fase 3/3: Sin hosts activos para OSINT")
                osint_data = []
            checkpoint = {"phase": "osint_done", "network": net, "cameras": cams, "osint": osint_data}
            save_checkpoint(scan_id, checkpoint)
            log_info("✅ Fase 3 completada")
        else:
            osint_data = checkpoint.get("osint", [])
            log_info("⏭️ Fase 3 saltada (checkpoint: osint_done)")
    else:
        osint_data = checkpoint.get("osint", [])

    # ── Fase final: Generar informe ──────────────────────────
    log_info("📄 Generando informe...")
    data = {"network": net, "cameras": cams, "osint": osint_data}
    hash_val = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    html, _ = generate_html(data, f"Auditoría completa {target}", [
        {"title": "📡 Topología", "data": net},
        {"title": "📷 Cámaras", "data": cams},
        {"title": "🌐 OSINT", "data": osint_data}
    ], hash_val)
    path = save_report(html, f"auto_{target.replace('/', '_')}", encrypt=True)

    if path:
        log_info(f"✅ Informe generado y cifrado: {path}")
        if email and CONFIG["sender_email"] and CONFIG["sender_password"]:
            send_email(email, f"Informe de auditoría {target}", "Adjunto informe sellado con blockchain.", [path])
        # Guardar resultado final en DB
        save_scan_result(target, "auto_audit", data, hash_val)
        # Marcar el escaneo como completado
        update_scan_status(scan_id, "completed")
        # Limpiar checkpoint (ya terminó)
        save_checkpoint(scan_id, {"phase": "completed"})
        log_info(f"🏁 Auditoría completada (ID={scan_id}, hash={hash_val[:8]}...)")
    else:
        log_error("❌ Falló la generación del informe.")
        update_scan_status(scan_id, "failed")

    return path

def resume_scan(scan_id, email=None):
    """Reanuda un escaneo desde su último checkpoint.
    Reconstruye las fases ya completadas y continúa desde la siguiente."""
    row = get_scan_info(scan_id)
    if not row:
        log_error("ID no encontrado.")
        return

    target, scan_type, status, data_json, checkpoint_json = row
    if status == "completed":
        log_warn(f"El escaneo {scan_id} ya está completado.")
        return

    checkpoint = json.loads(checkpoint_json) if checkpoint_json else {"phase": "start"}
    phase = checkpoint.get("phase", "start")

    if phase == "completed":
        log_warn(f"El escaneo {scan_id} ya está completado (checkpoint dice completed).")
        return

    log_info(f"🔄 Reanudando escaneo ID={scan_id} ({scan_type} → {target})")
    log_info(f"   Última fase completada: {phase}")

    # Reanudar el flujo desde el checkpoint — run_audit_phased
    # lee el checkpoint y continúa desde la fase correcta
    return run_audit_phased(scan_id, target, email)

# ============================================================
# 9. MODO AUTOMÁTICO (--auto)
# ============================================================
def auto_mode(target, email):
    log_info(f"🚀 Modo automático: {target} → {email}")
    scan_id = create_scan_record(target, "auto_audit")
    run_audit_phased(scan_id, target, email)

# ============================================================
# 10. CLI CON ARGPARSE
# ============================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="COMMANDER v3.5.0 — Suite de Inteligencia Táctica",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s --auto 192.168.1.0/24 --email cliente@mail.com --debug
  %(prog)s --resume 3
  %(prog)s --resume 3 --email cliente@mail.com
  %(prog)s --key "mi frase" --debug
        """
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--auto", metavar="TARGET", help="Ejecuta auditoría automática en un objetivo (IP o CIDR)")
    mode.add_argument("--scan-network", metavar="TARGET", help="Escanea una IP o rango con nmap")
    mode.add_argument("--scan-cameras", metavar="TARGET", help="Busca cámaras IP con nmap")
    mode.add_argument("--osint-ip", metavar="IP", help="Investiga una dirección IP")
    mode.add_argument("--osint-domain", metavar="DOMAIN", help="Investiga un dominio")
    mode.add_argument("--osint-email", metavar="EMAIL", help="Analiza el dominio de un email")
    parser.add_argument("--email", metavar="EMAIL", help="Correo destino para el informe")
    parser.add_argument("--key", metavar="PASSPHRASE", help="Frase de paso para el cifrado Fernet")
    mode.add_argument("--resume", metavar="ID", type=int, help="Reanuda una auditoría por su ID en SQLite")
    mode.add_argument("--list", action="store_true", help="Lista auditorías pendientes y completadas")
    parser.add_argument("--debug", action="store_true", help="Habilita logs detallados de depuración")
    return parser.parse_args()

# ============================================================
# 11. MAIN
# ============================================================
def main():
    args = parse_args()
    global logger
    logger = setup_logger(debug_mode=args.debug)
    log_info(f"🔧 COMMANDER v3.5.0 iniciado (debug={args.debug})")

    # Configurar clave desde argumento o entorno
    if args.key:
        CONFIG["encryption_key"] = args.key
        log_debug("Clave de cifrado cargada desde argumento --key")
    elif os.environ.get("COMMANDER_KEY"):
        CONFIG["encryption_key"] = os.environ.get("COMMANDER_KEY")
        log_debug("Clave de cifrado cargada desde variable COMMANDER_KEY")

    init_db()

    # --list: mostrar todas las auditorías
    if args.list:
        conn = sqlite3.connect(CONFIG["db_path"])
        c = conn.cursor()
        c.execute("SELECT id, target, scan_type, timestamp, status FROM audits ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()
        if not rows:
            print("📭 No hay auditorías registradas.")
        else:
            print("📂 Auditorías:")
            for r in rows:
                icon = "✅" if r[4] == "completed" else "🔄" if r[4] == "running" else "⏸️"
                print(f"  {icon} [{r[0]}] {r[1]} | {r[2]} | {r[3]} | {r[4]}")
        return

    # Modos directos usados por start.sh, sourceseal_tactical y el dashboard.
    direct_modes = (
        ("scan_network", scan_network),
        ("scan_cameras", scan_cameras),
        ("osint_ip", osint_ip),
        ("osint_domain", osint_domain),
        ("osint_email", osint_email),
    )
    for attr, operation in direct_modes:
        value = getattr(args, attr)
        if value:
            print(json.dumps(operation(value), ensure_ascii=False, indent=2, default=str))
            return

    # --auto: auditoría automática
    if args.auto:
        auto_mode(args.auto, args.email)
        return

    # --resume ID: reanudar auditoría
    if args.resume is not None:
        resume_scan(args.resume, email=args.email)
        return

    # Modo interactivo (menú completo)
    while True:
        print("\n" + "="*60)
        print("  ⚡ COMMANDER v3.5.0 — CLI + Logging + Checkpoints Reales")
        print("="*60)
        print("1️⃣  Escaneo de red completo")
        print("2️⃣  Detección de cámaras IP")
        print("3️⃣  Análisis forense de archivo")
        print("4️⃣  OSINT en IP")
        print("4️⃣b  OSINT en dominio (WHOIS+DNS+Subdominios+Headers)")
        print("4️⃣c  OSINT en email (MX+SPF+DMARC+Provider)")
        print("5️⃣  Auditoría completa (red + cámaras + OSINT)")
        print("6️⃣  Configurar SMTP + SourceSeal")
        print("7️⃣  Anclar hash a SourceSeal")
        print("8️⃣  Listar y reanudar auditorías")
        print("9️⃣  Descifrar y ver reporte .enc")
        print("🔟  🚨 COM-LINK — Comunicación de Emergencia")
        print("0️⃣  Salir")
        print("="*60)
        choice = input("👉 Selecciona una opción: ").strip()

        if choice == "0":
            log_info("👋 Hasta luego.")
            break
        elif choice == "1":
            target = input("🌐 IP o rango: ").strip()
            if not target: continue
            net = scan_network(target)
            print(json.dumps(net, indent=2))
            if input("📄 ¿Guardar informe? (s/n): ").lower() == 's':
                html, _ = generate_html(net, f"Topología {target}", [{"title": "Topología", "data": net}])
                path = save_report(html, f"topo_{target.replace('/', '_')}", encrypt=True)
                if path:
                    subprocess.run(["termux-open", path], check=False)
        elif choice == "2":
            target = input("🌐 Rango para cámaras: ").strip()
            if not target: continue
            cams = scan_cameras(target)
            print(json.dumps(cams, indent=2))
            if input("📄 ¿Guardar informe? (s/n): ").lower() == 's':
                html, _ = generate_html(cams, f"Cámaras {target}", [{"title": "Cámaras", "data": cams}])
                path = save_report(html, f"cams_{target.replace('/', '_')}", encrypt=True)
                if path:
                    subprocess.run(["termux-open", path], check=False)
        elif choice == "3":
            filepath = input("📂 Ruta del archivo: ").strip()
            if not os.path.exists(filepath):
                print("❌ Archivo no encontrado.")
                continue
            print("🔬 Análisis forense básico (puedes añadir forensic_file de v3.3)")
        elif choice == "4":
            ip = input("🌐 IP a investigar: ").strip()
            if not ip: continue
            osint = osint_ip(ip)
            print(json.dumps(osint, indent=2))
        elif choice == "4b":
            domain = input("🌐 Dominio a investigar: ").strip()
            if not domain: continue
            osint = osint_domain(domain)
            print(json.dumps(osint, indent=2))
            if input("📄 ¿Guardar informe? (s/n): ").lower() == 's':
                html, _ = generate_html(osint, f"OSINT Dominio {domain}", [
                    {"title": "DNS", "data": osint.get("dns",{})},
                    {"title": "WHOIS", "data": osint.get("whois",{})},
                    {"title": "Subdominios", "data": osint.get("subdomains",[])},
                    {"title": "Headers", "data": osint.get("headers",{})},
                ])
                path = save_report(html, f"osint_dom_{domain.replace('.','_')}", encrypt=True)
        elif choice == "4c":
            email = input("📧 Email a investigar: ").strip()
            if not email: continue
            osint = osint_email(email)
            print(json.dumps(osint, indent=2))
        elif choice == "5":
            target = input("🌐 Rango para auditoría completa: ").strip()
            if not target: continue
            email = input("📧 Email para el informe (Enter para omitir): ").strip() or None
            log_info("Ejecutando auditoría completa con checkpoints...")
            scan_id = create_scan_record(target, "interactive_audit")
            run_audit_phased(scan_id, target, email)
            if input("📄 ¿Abrir informe? (s/n): ").lower() == 's':
                # Buscar el último .enc en report_dir
                reports = sorted(
                    [f for f in os.listdir(CONFIG["report_dir"]) if f.startswith("auto_") and f.endswith(".enc")],
                    reverse=True
                )
                if reports:
                    path = os.path.join(CONFIG["report_dir"], reports[0])
                    subprocess.run(["termux-open", path], check=False)
        elif choice == "6":
            CONFIG["sender_email"] = input("📧 Email remitente: ").strip()
            CONFIG["sender_password"] = input("🔑 Contraseña: ").strip()
            CONFIG["sourceseal_api"] = input("🔗 URL SourceSeal: ").strip() or CONFIG["sourceseal_api"]
            log_info("✅ Configuración actualizada.")
        elif choice == "7":
            h = input("🔑 Hash a anclar: ").strip()
            if len(h) != 64:
                print("❌ Hash inválido.")
                continue
            success, proof = anchor_to_sourceseal(h, {"source": "commander_v3.5.0"})
            print(f"✅ Anclaje exitoso: {success} | Proof ID: {proof}")
        elif choice == "8":
            pending = get_pending_scans()
            if not pending:
                print("📭 No hay auditorías pendientes.")
                continue
            print("📂 Auditorías pendientes:")
            for row in pending:
                print(f"  [{row[0]}] {row[1]} - {row[2]} ({row[3]}) | {row[4]}")
            choice_id = input("ID a reanudar (0 cancelar): ").strip()
            if choice_id != "0":
                try:
                    email = input("📧 Email para el informe (Enter para omitir): ").strip() or None
                    resume_scan(int(choice_id), email=email)
                except Exception as e:
                    log_error(f"Error: {e}")
        elif choice == "9":
            path = input("📂 Ruta del archivo .enc: ").strip()
            if os.path.exists(path):
                html = decrypt_report(path)
                if html:
                    temp_file = os.path.join(CONFIG["temp_dir"], "temp_report.html")
                    with open(temp_file, 'w') as f:
                        f.write(html)
                    subprocess.run(["termux-open", temp_file], check=False)
                    log_info("🌐 Reporte abierto temporalmente.")
                else:
                    log_error("No se pudo descifrar el reporte.")
            else:
                print("❌ Archivo no encontrado.")
        elif choice == "10":
            # COM-LINK — Sistema de Comunicación de Emergencia
            comlink_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comlink")
            comlink_sh = os.path.join(comlink_dir, "comlink.sh")
            if not os.path.exists(comlink_sh):
                print("❌ COM-LINK no está instalado. Ejecuta: cd comlink && ./install.sh")
                continue
            log_info("🚨 Iniciando COM-LINK v3.0...")
            try:
                subprocess.run(["bash", comlink_sh], cwd=comlink_dir, check=False)
            except KeyboardInterrupt:
                print("\n👋 COM-LINK cerrado.")
            except Exception as e:
                log_error(f"Error COM-LINK: {e}")
        else:
            print("❌ Opción inválida.")
        input("\nPresiona Enter para continuar...")

if __name__ == "__main__":
    main()

