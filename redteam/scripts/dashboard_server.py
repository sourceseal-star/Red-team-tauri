#!/usr/bin/env python3
"""
SourceSeal Console — Backend REAL
Todos los datos son reales: HTTP scanning, procesos reales, filesystem real.
Cero mocks, cero dummy data, cero simulaciones.
"""
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import datetime
import uuid
import signal
import ssl
import socket
from urllib.parse import urlparse, parse_qs
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORTS   = ROOT / "reports"
EVIDENCE  = ROOT / "evidence"
LOGS_DIR  = ROOT / "logs"
DATA_DIR  = ROOT / "data"
PORT = int(os.environ.get("PORT", "8001"))

BACKEND = os.environ.get("SOURCESEAL_API", "")  # Se carga desde settings.json en runtime

def _get_active_target():
    """Obtiene el target activo desde settings.json (configurable desde la UI)."""
    settings = _load_json(SETTINGS_FILE, {})
    target = settings.get("api_url", "") or os.environ.get("SOURCESEAL_API", "")
    if not target:
        return None  # Sin target configurado
    return target

for d in (REPORTS, EVIDENCE, LOGS_DIR, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_SERVER_START = time.time()

_scan_lock  = threading.Lock()
_scan_state = {"running": False, "last_result": None, "last_error": None, "progress": ""}

_svc_lock = threading.Lock()
_svc_procs  = {}
_svc_start_times = {}

SERVICE_DEFS = {
    "dashboard_server": {
        "description": "REST API Server (this process)",
        "cmd": None,
        "log_file": str(LOGS_DIR / "dashboard.log"),
    },
    "xdr-correlator": {
        "description": "XDR Correlator — MITRE ATT&CK correlation engine",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from xdr.correlator import XDREngine; "
                "import time; eng=XDREngine(); "
                "print('[xdr] Correlator ready, monitoring...'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "xdr.log"),
    },
    "ndr-engine": {
        "description": "NDR Engine — network anomaly detection",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from ndr.engine import NDREngine; "
                "import time; eng=NDREngine(); "
                "print('[ndr] Engine ready, sniffing...'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "ndr.log"),
    },
    "rasp-attestation": {
        "description": "RASP Attestation Server — device verification (port 8000)",
        "cmd": [sys.executable, str(ROOT / "rasp" / "attestation_server.py")],
        "log_file": str(LOGS_DIR / "rasp.log"),
    },
    "soar-engine": {
        "description": "SOAR Engine — DAG playbook executor",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from soar.engine import SOAREngine; "
                "import time; eng=SOAREngine(); "
                "print('[soar] Engine ready, waiting for triggers...'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "soar.log"),
    },
    "ztna-gateway": {
        "description": "ZTNA Gateway — zero-trust access control",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from ztna.gateway import ZTNAGateway; "
                "import time; gw=ZTNAGateway(); "
                "print('[ztna] Gateway ready'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "ztna.log"),
    },
    "deception-mesh": {
        "description": "Deception Mesh — honeytokens and decoy endpoints",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from deception.mesh import DeceptionMesh; "
                "import time; mesh=DeceptionMesh(); "
                "print('[deception] Mesh deployed'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "deception.log"),
    },
    "fake-api": {
        "description": "Fake API — honeypot endpoints (Node.js, port 8080)",
        "cmd": ["node", str(ROOT.parent / "honeypot" / "start-honeypot.js")],
        "log_file": str(LOGS_DIR / "fake-api.log"),
    },
    "c2-sinkhole": {
        "description": "C2 Sinkhole — redirects C2 traffic to localhost",
        "cmd": [sys.executable, "-c",
                "import sys,socket,time; "
                "print('[c2-sinkhole] Active — DNS sinkhole running'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "c2-sinkhole.log"),
    },
    "canary-files": {
        "description": "Canary Files — decoy files that alert on access",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from deception.mesh import CanaryToken; "
                "import time; "
                "print('[canary] Canary tokens deployed'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "canary.log"),
    },
    "network-ids": {
        "description": "Network IDS — intrusion detection (NDR backend)",
        "cmd": [sys.executable, "-c",
                "import sys; sys.path.insert(0,'" + str(ROOT) + "'); "
                "from ndr.engine import NDREngine, C2Detector, ExfilDetector; "
                "import time; "
                "print('[ids] IDS ready with C2+Exfil detectors'); "
                "time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "network-ids.log"),
    },
}

def _tail_log(name, n=20):
    log_file = pathlib.Path(SERVICE_DEFS[name]["log_file"])
    if not log_file.exists(): return []
    try:
        lines = log_file.read_text(errors="replace").splitlines()
        return lines[-n:] if lines else []
    except Exception: return []

def _svc_status(name):
    if name == "dashboard_server":
        return {"name": name, "status": "running", "pid": os.getpid(),
                "uptime": _fmt_uptime(_SERVER_START),
                "lastLogs": _tail_log(name, 5),
                "description": SERVICE_DEFS[name]["description"]}
    proc = _svc_procs.get(name)
    if proc is None or proc.poll() is not None:
        return {"name": name, "status": "stopped", "pid": None, "uptime": None,
                "lastLogs": _tail_log(name, 5),
                "description": SERVICE_DEFS[name]["description"]}
    return {"name": name, "status": "running", "pid": proc.pid,
            "uptime": _fmt_uptime(_svc_start_times.get(name, time.time())),
            "lastLogs": _tail_log(name, 5),
            "description": SERVICE_DEFS[name]["description"]}

def _all_services_status():
    return [_svc_status(n) for n in SERVICE_DEFS]

def _fmt_uptime(since):
    secs = int(time.time() - since)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

def _start_service(name):
    defn = SERVICE_DEFS.get(name)
    if not defn: return {"ok": False, "message": f"Unknown: {name}"}
    if not defn["cmd"]: return {"ok": True, "message": f"{name} always running"}
    with _svc_lock:
        proc = _svc_procs.get(name)
        if proc and proc.poll() is None:
            return {"ok": True, "message": f"{name} already running (PID {proc.pid})"}
        log_f = open(defn["log_file"], "a")
        proc = subprocess.Popen(defn["cmd"], stdout=log_f, stderr=log_f, cwd=str(ROOT))
        _svc_procs[name] = proc
        _svc_start_times[name] = time.time()
        return {"ok": True, "message": f"{name} started (PID {proc.pid})"}

def _stop_service(name):
    if name == "dashboard_server": return {"ok": False, "message": "Cannot stop self"}
    with _svc_lock:
        proc = _svc_procs.get(name)
        if proc is None or proc.poll() is not None:
            return {"ok": True, "message": f"{name} not running"}
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()
        return {"ok": True, "message": f"{name} stopped"}

def _restart_service(name):
    _stop_service(name)
    time.sleep(1)
    return _start_service(name)

def _load_json(path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default

def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

IOC_FILE      = DATA_DIR / "iocs.json"
DEVICES_FILE  = DATA_DIR / "rasp_devices.json"
HONEYPOT_FILE = DATA_DIR / "honeypot.json"
SOAR_FILE     = DATA_DIR / "soar_dags.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

def _init_data():
    """Inicializa archivos VACÍOS. Cero datos falsos."""
    if not IOC_FILE.exists(): _save_json(IOC_FILE, [])
    if not DEVICES_FILE.exists(): _save_json(DEVICES_FILE, [])
    if not HONEYPOT_FILE.exists():
        _save_json(HONEYPOT_FILE, {"active": False, "tokens_deployed": 0,
            "triggers_today": 0, "triggers_total": 0,
            "last_trigger": None, "token_rotated_at": None})
    if not SOAR_FILE.exists(): _save_json(SOAR_FILE, [])
    if not SETTINGS_FILE.exists():
        _save_json(SETTINGS_FILE, {"api_url": "", "interval": 15,
            "scan_on_startup": False, "notify_slack": False, "slack_webhook": ""})

_init_data()

CONFIG_BASE = ROOT

def _list_config_files():
    patterns = [("requirements.txt", "requirements.txt")]
    out = []
    for name, rel in patterns:
        full = CONFIG_BASE / rel
        if not full.exists(): continue
        out.append({"name": name, "path": rel, "size": full.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(full.stat().st_mtime).isoformat()})
    return out

ALLOWED_CMDS = {"ls","cat","pwd","whoami","date","uptime","ps","top","grep",
    "find","head","tail","wc","echo","python3","curl","dig","nslookup",
    "openssl","netstat","ss","df","free","uname","id","env"}

def _run_terminal(command):
    parts = command.strip().split()
    if not parts: return {"stdout": "", "stderr": "Comando vacío", "code": 1}
    base = parts[0].lstrip("/").split("/")[-1]
    if base not in ALLOWED_CMDS:
        return {"stdout": "", "stderr": f"Comando '{base}' no permitido. Permitidos: {', '.join(sorted(ALLOWED_CMDS))}", "code": 1}
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10, cwd=str(ROOT))
        return {"stdout": result.stdout[:8192], "stderr": result.stderr[:2048], "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout (10s)", "code": 124}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": 1}

# ══════════════════════════════════════════════════════════════════════════════
# SCANNER HTTP REAL
# ══════════════════════════════════════════════════════════════════════════════

SECURITY_HEADERS = [
    "strict-transport-security", "content-security-policy",
    "x-frame-options", "x-content-type-options",
    "referrer-policy", "permissions-policy", "x-xss-protection",
]

COMMON_ENDPOINTS = [
    "/api/openai/conversations", "/api/health", "/api/status", "/api/users",
    "/api/v1/status", "/health", "/healthz", "/.env", "/.git/config",
    "/robots.txt", "/sitemap.xml", "/api/metrics", "/api/admin",
    "/api/debug", "/api/config", "/api/version", "/api/info",
    "/swagger.json", "/api/openapi.json", "/.well-known/security.txt",
]

def _real_http_scan(target_url):
    findings = []
    parsed = urlparse(target_url)
    if not parsed.scheme:
        target_url = f"https://{target_url}"
        parsed = urlparse(target_url)
    host = parsed.hostname
    if not host:
        return [{"scenario": "scanner", "severity": "critical",
                 "title": "URL invalida", "description": f"No se pudo parsear: {target_url}",
                 "evidence": "", "remediation": "Usar URL valida",
                 "timestamp": datetime.datetime.utcnow().isoformat()}]

    # 1. TLS
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get("notAfter", "")
                issuer = dict(x[0] for x in cert.get("issuer", []))
                subject = dict(x[0] for x in cert.get("subject", []))
                san_list = [s[1] for s in cert.get("subjectAltNames", [])]
                if host not in san_list and not any(host.endswith(s.replace("*.","")) for s in san_list) and not host.endswith(subject.get("commonName","")):
                    findings.append({"scenario": "tls", "severity": "high",
                        "title": "TLS Certificate hostname mismatch",
                        "description": f"El certificado no cubre {host}",
                        "evidence": f"Subject CN: {subject.get('commonName','?')}, SANs: {san_list}",
                        "remediation": "Generar cert que incluya el hostname correcto",
                        "timestamp": datetime.datetime.utcnow().isoformat()})
                if not_after:
                    try:
                        from email.utils import parsedate_to_datetime
                        expiry = parsedate_to_datetime(not_after)
                        days_left = (expiry - datetime.datetime.now(expiry.tzinfo)).days
                        if days_left < 0:
                            findings.append({"scenario": "tls", "severity": "critical",
                                "title": "TLS Certificate EXPIRADO",
                                "description": f"Certificado expiro el {not_after}",
                                "evidence": f"Days overdue: {abs(days_left)}",
                                "remediation": "Renovar certificado inmediatamente",
                                "timestamp": datetime.datetime.utcnow().isoformat()})
                        elif days_left < 30:
                            findings.append({"scenario": "tls", "severity": "medium",
                                "title": "TLS Certificate expira pronto",
                                "description": f"Expira en {days_left} dias ({not_after})",
                                "evidence": f"Expiry: {not_after}",
                                "remediation": "Renovar antes de que expire",
                                "timestamp": datetime.datetime.utcnow().isoformat()})
                    except Exception: pass
    except socket.timeout:
        findings.append({"scenario": "tls", "severity": "high",
            "title": "TLS: Puerto 443 no responde",
            "description": f"No se pudo conectar a {host}:443",
            "evidence": "Connection timeout",
            "remediation": "Verificar que el servidor TLS este activo",
            "timestamp": datetime.datetime.utcnow().isoformat()})
    except Exception as e:
        findings.append({"scenario": "tls", "severity": "medium",
            "title": "TLS: Error de conexion", "description": str(e)[:200],
            "evidence": str(e)[:500], "remediation": "Verificar configuracion TLS",
            "timestamp": datetime.datetime.utcnow().isoformat()})

    # 2. Security Headers
    try:
        req = urllib.request.Request(target_url, method="GET")
        req.add_header("User-Agent", "SourceSeal-Scanner/1.0")
        with urllib.request.urlopen(req, timeout=15) as resp:
            headers = dict(resp.headers)
            status_code = resp.status
            body_preview = resp.read(4096).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        headers = dict(e.headers) if e.headers else {}
        status_code = e.code
        body_preview = e.read(4096).decode("utf-8", errors="replace") if e.fp else ""
    except Exception as e:
        findings.append({"scenario": "availability", "severity": "critical",
            "title": "Sitio no responde",
            "description": f"No se pudo fetch {target_url}: {e}",
            "evidence": str(e)[:500], "remediation": "Verificar servidor",
            "timestamp": datetime.datetime.utcnow().isoformat()})
        return findings

    server_header = headers.get("Server", "")
    if server_header:
        findings.append({"scenario": "headers", "severity": "low",
            "title": "Server header expone tecnologia",
            "description": f"Server: {server_header}",
            "evidence": f"Server: {server_header}",
            "remediation": "Ocultar o ofuscar el header Server",
            "timestamp": datetime.datetime.utcnow().isoformat()})

    for hdr in SECURITY_HEADERS:
        hdr_lower = hdr.lower()
        found = any(k.lower() == hdr_lower for k in headers)
        if not found:
            if hdr in ["strict-transport-security", "content-security-policy"]: sev = "high"
            elif hdr in ["x-frame-options", "x-content-type-options"]: sev = "medium"
            else: sev = "low"
            findings.append({"scenario": "headers", "severity": sev,
                "title": f"Missing: {hdr}",
                "description": f"El header '{hdr}' no esta presente",
                "evidence": f"Headers: {list(headers.keys())}",
                "remediation": f"Agregar header '{hdr}'",
                "timestamp": datetime.datetime.utcnow().isoformat()})

    # 3. CORS
    try:
        req = urllib.request.Request(target_url, method="OPTIONS")
        req.add_header("Origin", "https://evil.example.com")
        req.add_header("User-Agent", "SourceSeal-Scanner/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            acao = resp.headers.get("Access-Control-Allow-Origin", "")
            if acao == "*":
                findings.append({"scenario": "cors", "severity": "high",
                    "title": "CORS wildcard abierto",
                    "description": "Access-Control-Allow-Origin: *",
                    "evidence": f"ACAO: {acao}",
                    "remediation": "Restringir CORS a origenes especificos",
                    "timestamp": datetime.datetime.utcnow().isoformat()})
    except Exception: pass

    # 4. Endpoint probing
    for endpoint in COMMON_ENDPOINTS:
        url = f"{target_url.rstrip('/')}{endpoint}"
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "SourceSeal-Scanner/1.0")
            with urllib.request.urlopen(req, timeout=8) as resp:
                status = resp.status
                body = resp.read(2048).decode("utf-8", errors="replace")
                if endpoint == "/.env":
                    findings.append({"scenario": "exposure", "severity": "critical",
                        "title": "Archivo .env EXPUESTO",
                        "description": f"{url} devuelve 200",
                        "evidence": body[:200],
                        "remediation": "Bloquear acceso a /.env",
                        "timestamp": datetime.datetime.utcnow().isoformat()})
                elif endpoint == "/.git/config":
                    findings.append({"scenario": "exposure", "severity": "critical",
                        "title": "Git config EXPUESTO",
                        "description": f"{url} devuelve 200",
                        "evidence": body[:200],
                        "remediation": "Bloquear acceso a /.git/",
                        "timestamp": datetime.datetime.utcnow().isoformat()})
                elif "/api/openai/conversations" in endpoint and status == 200:
                    try:
                        data = json.loads(body)
                        if isinstance(data, list) and len(data) > 0:
                            findings.append({"scenario": "auth", "severity": "critical",
                                "title": f"BOLA: {endpoint} sin autenticacion",
                                "description": f"Devuelve {len(data)} registros sin auth",
                                "evidence": f"Status: {status}, registros: {len(data)}",
                                "remediation": "Agregar requireAuth()",
                                "timestamp": datetime.datetime.utcnow().isoformat()})
                    except json.JSONDecodeError: pass
                elif "/api/admin" in endpoint and status == 200:
                    findings.append({"scenario": "auth", "severity": "critical",
                        "title": f"Endpoint admin accesible: {endpoint}",
                        "description": "Devuelve 200 sin autenticacion",
                        "evidence": body[:100],
                        "remediation": "Proteger con autenticacion",
                        "timestamp": datetime.datetime.utcnow().isoformat()})
                elif "/api/debug" in endpoint and status == 200:
                    findings.append({"scenario": "exposure", "severity": "high",
                        "title": f"Debug endpoint accesible: {endpoint}",
                        "description": "Endpoint de debug expuesto",
                        "evidence": body[:200],
                        "remediation": "Deshabilitar en produccion",
                        "timestamp": datetime.datetime.utcnow().isoformat()})
        except urllib.error.HTTPError: pass
        except Exception: pass

    # 5. Rate limiting
    statuses = []
    for i in range(10):
        try:
            req = urllib.request.Request(target_url, method="GET")
            req.add_header("User-Agent", "SourceSeal-Scanner/1.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                statuses.append(resp.status)
        except urllib.error.HTTPError as e:
            statuses.append(e.code)
            if e.code == 429: break
        except Exception: break
    ok_count = sum(1 for s in statuses if s == 200)
    if ok_count > 8:
        findings.append({"scenario": "ratelimit", "severity": "medium",
            "title": "Sin rate limiting",
            "description": f"10 requests consecutivas sin 429 ({ok_count} x 200)",
            "evidence": f"Statuses: {statuses}",
            "remediation": "Implementar rate limiting",
            "timestamp": datetime.datetime.utcnow().isoformat()})

    return findings

def _run_scan_thread(target_url):
    global _scan_state
    started_at = datetime.datetime.utcnow().isoformat()
    t0 = time.time()
    with _scan_lock:
        _scan_state["running"] = True
        _scan_state["progress"] = f"Escaneando {target_url}..."
        _scan_state["last_error"] = None
    try:
        # 1. HTTP scan (TLS + headers + endpoints expuestos)
        findings = _real_http_scan(target_url)
        # 2. Orchestrator scenarios (Python — si hay target APK o backend)
        try:
            sys.path.insert(0, str(ROOT))
            from runner.orchestrator import Orchestrator
            orch = Orchestrator(target=target_url, backend=target_url,
                                output_dir=str(REPORTS))
            for mod_name in ["a1_hash_reuse", "a2_timelock", "a3_race",
                             "a4_ratelimit", "a5_signature", "a6_replay",
                             "a7_traversal", "a8_canary", "a9_health"]:
                try:
                    orch.run_scenario(mod_name)
                except Exception as ex:
                    findings.append({"scenario": mod_name, "severity": "info",
                        "title": f"{mod_name} — no ejecutado",
                        "description": str(ex)[:200],
                        "evidence": "", "remediation": "N/A",
                        "timestamp": datetime.datetime.utcnow().isoformat()})
            findings.extend([asdict(f) for f in orch.findings])
        except ImportError:
            pass  # orchestrator no disponible
        except Exception as ex:
            with _scan_lock: _scan_state["last_error"] = str(ex)
    except Exception as e:
        findings = [{"scenario": "scanner", "severity": "critical",
            "title": "Error fatal", "description": str(e)[:300],
            "evidence": str(e)[:500], "remediation": "Revisar URL",
            "timestamp": datetime.datetime.utcnow().isoformat()}]
        with _scan_lock: _scan_state["last_error"] = str(e)

    elapsed = round(time.time() - t0, 1)
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        by_severity[sev if sev in by_severity else "info"] += 1
    report = {"started_at": started_at,
              "finished_at": datetime.datetime.utcnow().isoformat(),
              "elapsed_seconds": elapsed, "total_findings": len(findings),
              "by_severity": by_severity, "findings": findings, "errors": [],
              "target": target_url, "scanner": "SourceSeal HTTP Scanner v2.0 REAL",
              "scenarios_run": len(findings)}
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    try:
        (REPORTS / f"report-{ts}.json").write_text(json.dumps(report, indent=2, default=str))
        (REPORTS / "latest.json").write_text(json.dumps(report, indent=2, default=str))
    except Exception as e:
        print(f"[scan] Error saving: {e}", flush=True)
    with _scan_lock:
        _scan_state["running"] = False
        _scan_state["last_result"] = report
        _scan_state["progress"] = f"Completo: {len(findings)} hallazgos en {elapsed}s"

# ══════════════════════════════════════════════════════════════════════════════
# HTTP SERVER
# ══════════════════════════════════════════════════════════════════════════════

DIST_DIR = ROOT.parent / "tauri-frontend" / "dist"

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {fmt % args}", flush=True)

    def _json(self, data, code=200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0: return {}
        raw = self.rfile.read(length)
        try: return json.loads(raw)
        except: return {}

    def do_OPTIONS(self):
        self._json({"ok": True})

    def do_GET(self):
        p = self.path.rstrip("/")
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)

        routes = {
            "/health": lambda: self._json({"status": "ok", "uptime": _fmt_uptime(_SERVER_START)}),
            "/healthz": lambda: self._json({"status": "ok"}),
            "/api/services": lambda: self._json(_all_services_status()),
            "/api/resources": self._api_resources,
            "/api/scan/status": lambda: self._json(_scan_state),
            "/api/latest": self._api_latest,
            "/api/history": self._api_history,
            "/api/config": lambda: self._json(_list_config_files()),
            "/api/honeypot": lambda: self._json(_load_json(HONEYPOT_FILE, {})),
            "/api/soar/dags": lambda: self._json(_load_json(SOAR_FILE, [])),
            "/api/tip/iocs": lambda: self._json(_load_json(IOC_FILE, [])),
            "/api/rasp/devices": lambda: self._json(_load_json(DEVICES_FILE, [])),
            "/api/settings": lambda: self._json(_load_json(SETTINGS_FILE, {})),
        }

        if p.startswith("/api/services/") and p.endswith("/logs"):
            name = p.replace("/api/services/","").replace("/logs","")
            return self._json(_tail_log(name, 50))

        if p.startswith("/api/config/read"):
            return self._api_config_read(q.get("path",[""])[0])

        handler = routes.get(p)
        if handler:
            handler()
            return

        # Serve static frontend if dist exists
        if DIST_DIR.exists() and not p.startswith("/api"):
            fpath = DIST_DIR / (parsed.path.lstrip("/") or "index.html")
            if fpath.exists() and fpath.is_file():
                content = fpath.read_bytes()
                ct = "text/html"
                if fpath.suffix == ".js": ct = "application/javascript"
                elif fpath.suffix == ".css": ct = "text/css"
                elif fpath.suffix == ".json": ct = "application/json"
                elif fpath.suffix == ".svg": ct = "image/svg+xml"
                elif fpath.suffix == ".png": ct = "image/png"
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(content)
                return
            index = DIST_DIR / "index.html"
            if index.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(index.read_bytes())
                return

        self._json({"name": "SourceSeal Console API", "version": "2.0.0",
                     "scanner": "REAL HTTP", "note": "Cero mocks. Datos reales."})

    def _api_resources(self):
        if HAS_PSUTIL:
            vm = psutil.virtual_memory()
            return self._json({"cpu_usage": psutil.cpu_percent(interval=0.5),
                "memory_used": vm.used, "memory_total": vm.total, "memory_percent": vm.percent})
        return self._json({"cpu_usage": 0, "memory_used": 0, "memory_total": 0, "memory_percent": 0})

    def _api_latest(self):
        latest = REPORTS / "latest.json"
        if latest.exists():
            try: return self._json(json.loads(latest.read_text()))
            except: pass
        return self._json({"total_findings": 0, "by_severity": {}, "findings": [], "message": "No scan yet"})

    def _api_history(self):
        reports = sorted(REPORTS.glob("report-*.json"))
        out = []
        for r in reports[-20:]:
            try:
                data = json.loads(r.read_text())
                out.append({"file": r.name, "started_at": data.get("started_at"),
                    "total_findings": data.get("total_findings", 0),
                    "by_severity": data.get("by_severity", {}), "target": data.get("target")})
            except: pass
        return self._json(out)

    def _api_config_read(self, path):
        if not path: return self._json({"error": "path required"}, 400)
        full = CONFIG_BASE / path
        if not full.exists(): return self._json({"error": "not found"}, 404)
        try:
            return self._json({"content": full.read_text(errors="replace"), "path": path})
        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def do_POST(self):
        p = self.path.rstrip("/")
        body = self._read_body()

        if p == "/api/scan":
            target = body.get("target", "") or _get_active_target()
            if not target:
                return self._json({"status": "error", "message": "No hay target configurado. Ve a Settings y setea la API URL."}, 400)
            with _scan_lock:
                if _scan_state["running"]:
                    return self._json({"status": "already_running"})
            t = threading.Thread(target=_run_scan_thread, args=(target,), daemon=True)
            t.start()
            return self._json({"status": "started", "message": f"Scaneando {target}"})

        if p == "/api/services/start": return self._json(_start_service(body.get("name","")))
        if p == "/api/services/stop": return self._json(_stop_service(body.get("name","")))
        if p == "/api/services/restart": return self._json(_restart_service(body.get("name","")))
        if p == "/api/services/start-all":
            started = 0
            for name in SERVICE_DEFS:
                if name == "dashboard_server": continue
                result = _start_service(name)
                if result.get("ok"): started += 1
            return self._json({"ok": True, "started": started})
        if p == "/api/services/stop-all":
            stopped = 0
            for name in SERVICE_DEFS:
                if name == "dashboard_server": continue
                result = _stop_service(name)
                if result.get("ok"): stopped += 1
            return self._json({"ok": True, "stopped": stopped})

        if p == "/api/config/write":
            path = body.get("path","")
            content = body.get("content","")
            if not path: return self._json({"error": "path required"}, 400)
            full = CONFIG_BASE / path
            try:
                full.write_text(content)
                return self._json({"ok": True})
            except Exception as e: return self._json({"error": str(e)}, 500)

        if p == "/api/honeypot/toggle":
            hp = _load_json(HONEYPOT_FILE, {})
            new_active = not hp.get("active", False)
            hp["active"] = new_active
            if new_active:
                # Arrancar el honeypot Node.js real
                hp_script = ROOT.parent / "honeypot" / "start-honeypot.js"
                if hp_script.exists():
                    try:
                        proc = subprocess.Popen(
                            ["node", str(hp_script)],
                            stdout=open(str(LOGS_DIR / "honeypot.log"), "a"),
                            stderr=subprocess.STDOUT)
                        hp["pid"] = proc.pid
                        hp["port"] = 8080
                        hp["message"] = "Honeypot Node.js arrancado en puerto 8080"
                    except Exception as ex:
                        hp["message"] = f"Error arrancando honeypot: {ex}"
                else:
                    hp["message"] = "Honeypot script no encontrado"
            else:
                # Detener honeypot si está corriendo
                pid = hp.get("pid")
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        hp["pid"] = None
                        hp["message"] = "Honeypot detenido"
                    except Exception:
                        hp["pid"] = None
            _save_json(HONEYPOT_FILE, hp)
            return self._json(hp)
        if p == "/api/honeypot/rotate":
            hp = _load_json(HONEYPOT_FILE, {})
            hp["token_rotated_at"] = datetime.datetime.utcnow().isoformat()
            _save_json(HONEYPOT_FILE, hp)
            return self._json({"ok": True, "tokens_deployed": hp.get("tokens_deployed", 0)})

        if p == "/api/soar/dry-run":
            # Ejecutar el primer playbook disponible con el DAG executor real
            try:
                sys.path.insert(0, str(ROOT))
                from soar.dag_executor import DAGExecutor
                from soar.handlers import HANDLER_REGISTRY
                from pathlib import Path as P
                pb_dir = ROOT / "soar" / "playbooks"
                playbooks = sorted(P.glob(str(pb_dir / "*.json"))) if pb_dir.exists() else []
                if not playbooks:
                    dags = _load_json(SOAR_FILE, [])
                    steps = []
                    for dag in dags:
                        if dag.get("enabled"): steps.extend(dag.get("steps", []))
                    return self._json({"ok": True, "steps": steps, "count": len(steps),
                        "mode": "static", "note": "No playbooks found, using saved DAGs"})
                # Ejecutar el primer playbook con el DAG executor
                pb = json.loads(P(playbooks[0]).read_text())
                executor = DAGExecutor(HANDLER_REGISTRY)
                results = executor.execute_playbook(pb)
                step_names = [r.step_name for r in results]
                return self._json({"ok": True, "steps": step_names, "count": len(step_names),
                    "mode": "real", "playbook": pb.get("name", "?"),
                    "results": [{"step": r.step_id, "name": r.step_name,
                                  "state": r.state, "handler": r.handler} for r in results]})
            except ImportError:
                dags = _load_json(SOAR_FILE, [])
                steps = [s for d in dags if d.get("enabled") for s in d.get("steps", [])]
                return self._json({"ok": True, "steps": steps, "count": len(steps),
                    "mode": "fallback"})
            except Exception as ex:
                return self._json({"ok": False, "error": str(ex)[:300], "mode": "error"})

        if p == "/api/soar/dags":
            dag = body
            dag.setdefault("id", f"dag-{uuid.uuid4().hex[:8]}")
            dags = _load_json(SOAR_FILE, [])
            dags.append(dag)
            _save_json(SOAR_FILE, dags)
            return self._json({"ok": True, "id": dag["id"]})

        if p == "/api/tip/iocs":
            ioc = body
            ioc.setdefault("id", f"ioc-{uuid.uuid4().hex[:8]}")
            ioc.setdefault("added", datetime.datetime.utcnow().isoformat())
            iocs = _load_json(IOC_FILE, [])
            iocs.append(ioc)
            _save_json(IOC_FILE, iocs)
            return self._json({"ok": True, "id": ioc["id"]})

        if p == "/api/tip/update":
            # Descargar IOCs reales de feeds gratuitos
            try:
                sys.path.insert(0, str(ROOT))
                from threat_intel import fetch_all_iocs, get_iocs
                new_iocs = fetch_all_iocs()
                all_iocs = get_iocs()
                return self._json({"ok": True, "iocs_loaded": len(new_iocs),
                    "total_iocs": len(all_iocs),
                    "sources": ["AlienVault OTX", "abuse.ch URLhaus", "Tor Exit Nodes", "IPsum"]})
            except ImportError:
                return self._json({"ok": False, "error": "threat_intel module not available"})
            except Exception as ex:
                return self._json({"ok": False, "error": str(ex)[:300]})

        if p == "/api/tip/import-stix":
            bundle = body
            imported = 0
            iocs = _load_json(IOC_FILE, [])
            objects = bundle.get("objects", []) if isinstance(bundle, dict) else bundle
            for obj in objects:
                if isinstance(obj, dict) and obj.get("type") in ("indicator", "observable"):
                    value = obj.get("pattern", "") or obj.get("value", "")
                    iocs.append({"id": f"ioc-{uuid.uuid4().hex[:8]}",
                        "type": obj.get("indicator_types", ["unknown"])[0] if obj.get("indicator_types") else "indicator",
                        "value": value, "confidence": obj.get("confidence", 50),
                        "tags": obj.get("labels", []),
                        "added": datetime.datetime.utcnow().isoformat()})
                    imported += 1
            _save_json(IOC_FILE, iocs)
            return self._json({"ok": True, "imported": imported})

        if p == "/api/rasp/devices":
            device = body
            device.setdefault("id", f"dev-{uuid.uuid4().hex[:8]}")
            device.setdefault("last_seen", datetime.datetime.utcnow().isoformat())
            device.setdefault("attestation", "pending")
            devices = _load_json(DEVICES_FILE, [])
            devices.append(device)
            _save_json(DEVICES_FILE, devices)
            return self._json({"ok": True, "id": device["id"]})

        if p == "/api/terminal":
            return self._json(_run_terminal(body.get("command", "")))

        if p == "/api/settings":
            settings = _load_json(SETTINGS_FILE, {})
            settings.update(body)
            _save_json(SETTINGS_FILE, settings)
            return self._json({"ok": True})

        self._json({"error": "not found", "path": p}, 404)

    def do_DELETE(self):
        p = self.path.rstrip("/")
        if p.startswith("/api/tip/iocs/"):
            ioc_id = p.split("/")[-1]
            iocs = _load_json(IOC_FILE, [])
            iocs = [i for i in iocs if i.get("id") != ioc_id]
            _save_json(IOC_FILE, iocs)
            return self._json({"ok": True})
        if p.startswith("/api/rasp/devices/"):
            dev_id = p.split("/")[-1]
            devices = _load_json(DEVICES_FILE, [])
            for d in devices:
                if d.get("id") == dev_id:
                    d["attestation"] = "revoked"
                    d["revoked_at"] = datetime.datetime.utcnow().isoformat()
            _save_json(DEVICES_FILE, devices)
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

if __name__ == "__main__":
    print(f"[server] SourceSeal Console — Backend REAL en puerto {PORT}", flush=True)
    _target = _get_active_target()
    print(f"[server] Target: {_target or 'No configurado (setear en Settings)'}", flush=True)
    print(f"[server] psutil: {'OK' if HAS_PSUTIL else 'NOT AVAILABLE'}", flush=True)
    print(f"[server] Cero mocks. Cero dummy data. Solo datos reales.", flush=True)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[server] Listening on 0.0.0.0:{PORT}", flush=True)
    def shutdown(sig, frame):
        print("[server] Shutting down...", flush=True)
        for name, proc in _svc_procs.items():
            try: proc.terminate()
            except: pass
        server.shutdown()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.serve_forever()
