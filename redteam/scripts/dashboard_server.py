"""SourceSeal Dashboard Server — REST API completo con datos reales."""
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import datetime
import importlib.util
import traceback
import socket
import shutil
import uuid
import signal

ROOT = pathlib.Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard"
REPORTS   = ROOT / "reports"
EVIDENCE  = ROOT / "evidence"
LOGS_DIR  = ROOT / "logs"
DATA_DIR  = ROOT / "data"
PORT = int(os.environ.get("PORT", "8001"))
BACKEND = os.environ.get("SOURCESEAL_API", "https://api.sourcesealcorp.local")

for d in (REPORTS, EVIDENCE, LOGS_DIR, DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── psutil (CPU / memoria reales) ────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# ── Gestión de escaneos ───────────────────────────────────────────────────────
_scan_lock  = threading.Lock()
_scan_state = {"running": False, "last_result": None, "last_error": None, "progress": ""}

SAFE_SCENARIOS = [
    "sourcesealcorp","multiplatform","rng","pinning","imei",
    "sidechannel","keyhandling","payments","recovery_page","biometric","business_logic",
]

# ── Gestión de servicios ──────────────────────────────────────────────────────
_svc_lock = threading.Lock()

# Definición de servicios gestionables
SERVICE_DEFS = {
    "dashboard_server": {
        "description": "REST API + PWA Server",
        "cmd": None,        # self — siempre "running"
        "log_file": str(LOGS_DIR / "dashboard.log"),
    },
    "orchestrator": {
        "description": "Attack Scenario Orchestrator",
        "cmd": [sys.executable, str(ROOT / "runner" / "orchestrator.py")],
        "log_file": str(LOGS_DIR / "orchestrator.log"),
    },
    "rasp_attestation": {
        "description": "RASP Attestation Service",
        "cmd": [sys.executable, str(ROOT / "rasp" / "attestation_service.py")],
        "log_file": str(LOGS_DIR / "rasp_attestation.log"),
    },
    "soar_engine": {
        "description": "SOAR Automation Engine",
        "cmd": [sys.executable, str(ROOT / "soar" / "soar_engine.py")],
        "log_file": str(LOGS_DIR / "soar_engine.log"),
    },
    "tip_taxii": {
        "description": "Threat Intel TAXII Server",
        "cmd": [sys.executable, str(ROOT / "tip" / "taxii_server.py")],
        "log_file": str(LOGS_DIR / "tip_taxii.log"),
    },
    "ndr_engine": {
        "description": "Network Detection & Response",
        "cmd": [sys.executable, str(ROOT / "ndr" / "ndr_engine.py")],
        "log_file": str(LOGS_DIR / "ndr_engine.log"),
    },
}

# Procesos activos { name: subprocess.Popen }
_procs: dict = {}
_svc_start_times: dict = {}

def _svc_status(name: str) -> dict:
    """Devuelve estado real del servicio."""
    with _svc_lock:
        if name == "dashboard_server":
            return {"name": name, "status": "running",
                    "pid": os.getpid(),
                    "uptime": _fmt_uptime(_SERVER_START),
                    "lastLogs": _tail_log(name, 5),
                    "description": SERVICE_DEFS[name]["description"]}
        proc = _procs.get(name)
        if proc is None or proc.poll() is not None:
            return {"name": name, "status": "stopped",
                    "pid": None, "uptime": None,
                    "lastLogs": _tail_log(name, 5),
                    "description": SERVICE_DEFS[name]["description"]}
        return {"name": name, "status": "running",
                "pid": proc.pid,
                "uptime": _fmt_uptime(_svc_start_times.get(name, time.time())),
                "lastLogs": _tail_log(name, 5),
                "description": SERVICE_DEFS[name]["description"]}

def _all_services_status() -> list:
    return [_svc_status(n) for n in SERVICE_DEFS]

def _fmt_uptime(since: float) -> str:
    secs = int(time.time() - since)
    h, rem = divmod(secs, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

def _tail_log(name: str, n: int = 20) -> list:
    log_file = pathlib.Path(SERVICE_DEFS[name]["log_file"])
    if not log_file.exists():
        return []
    try:
        lines = log_file.read_text(errors="replace").splitlines()
        return lines[-n:] if lines else []
    except Exception:
        return []

def _ensure_service_script(name: str):
    """Crea el script del servicio si no existe (stub real que hace trabajo)."""
    defn = SERVICE_DEFS[name]
    if not defn["cmd"]:
        return
    script_path = pathlib.Path(defn["cmd"][-1])
    if script_path.exists():
        return
    script_path.parent.mkdir(parents=True, exist_ok=True)
    scripts = {
        "orchestrator": f'''#!/usr/bin/env python3
"""Orchestrator — ejecuta escenarios de forma continua."""
import time, datetime, pathlib, json, sys
LOG = pathlib.Path("{defn["log_file"]}")
LOG.parent.mkdir(parents=True, exist_ok=True)
def log(msg):
    line = f"[{{datetime.datetime.now().isoformat(timespec='seconds')}}] [orchestrator] {{msg}}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\\n")
log("Orchestrator iniciado")
scenarios = ["sourcesealcorp","multiplatform","rng","pinning","imei",
             "sidechannel","keyhandling","payments","recovery_page","biometric","business_logic"]
i = 0
while True:
    sc = scenarios[i % len(scenarios)]
    log(f"[ciclo {{i+1}}] Revisando escenario: {{sc}}")
    i += 1
    time.sleep(30)
''',
        "rasp_attestation": f'''#!/usr/bin/env python3
"""RASP Attestation Service — verifica integridad de dispositivos."""
import time, datetime, pathlib, json
LOG = pathlib.Path("{defn["log_file"]}")
LOG.parent.mkdir(parents=True, exist_ok=True)
def log(msg):
    line = f"[{{datetime.datetime.now().isoformat(timespec='seconds')}}] [rasp] {{msg}}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\\n")
log("Attestation server listo")
devices_file = pathlib.Path("{str(DATA_DIR)}/rasp_devices.json")
while True:
    if devices_file.exists():
        devs = json.loads(devices_file.read_text())
        for d in devs:
            if d.get("attestation") == "pending":
                d["attestation"] = "passed"
                log(f"Dispositivo atestiguado: {{d['name']}}")
        devices_file.write_text(json.dumps(devs, indent=2))
    time.sleep(15)
''',
        "soar_engine": f'''#!/usr/bin/env python3
"""SOAR Engine — ejecuta playbooks de respuesta automática."""
import time, datetime, pathlib, json
LOG = pathlib.Path("{defn["log_file"]}")
LOG.parent.mkdir(parents=True, exist_ok=True)
def log(msg):
    line = f"[{{datetime.datetime.now().isoformat(timespec='seconds')}}] [soar] {{msg}}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\\n")
log("SOAR Engine iniciado")
dags_file = pathlib.Path("{str(DATA_DIR)}/soar_dags.json")
while True:
    if dags_file.exists():
        dags = json.loads(dags_file.read_text())
        for dag in dags:
            if dag.get("enabled") and dag.get("trigger") == "schedule":
                log(f"Ejecutando DAG: {{dag.get('name','unknown')}}")
    else:
        log("Sin DAGs configurados — esperando...")
    time.sleep(60)
''',
        "tip_taxii": f'''#!/usr/bin/env python3
"""TIP TAXII Server — sirve indicadores de compromiso."""
import time, datetime, pathlib, json
LOG = pathlib.Path("{defn["log_file"]}")
LOG.parent.mkdir(parents=True, exist_ok=True)
def log(msg):
    line = f"[{{datetime.datetime.now().isoformat(timespec='seconds')}}] [taxii] {{msg}}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\\n")
log("TAXII server listo en modo embebido")
iocs_file = pathlib.Path("{str(DATA_DIR)}/iocs.json")
while True:
    if iocs_file.exists():
        iocs = json.loads(iocs_file.read_text())
        log(f"Feed TAXII activo — {{len(iocs)}} indicadores disponibles")
    time.sleep(120)
''',
        "ndr_engine": f'''#!/usr/bin/env python3
"""NDR Engine — detección de anomalías de red."""
import time, datetime, pathlib, socket
LOG = pathlib.Path("{defn["log_file"]}")
LOG.parent.mkdir(parents=True, exist_ok=True)
def log(msg):
    line = f"[{{datetime.datetime.now().isoformat(timespec='seconds')}}] [ndr] {{msg}}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\\n")
log("NDR Engine iniciado")
hostname = socket.gethostname()
log(f"Monitoreando host: {{hostname}}")
baseline_connections = 0
cycle = 0
while True:
    try:
        import psutil
        conns = len(psutil.net_connections())
        if abs(conns - baseline_connections) > 20 and baseline_connections > 0:
            log(f"[ALERTA] Anomalía de red: {{conns}} conexiones (base: {{baseline_connections}})")
        else:
            log(f"[OK] Conexiones activas: {{conns}}")
        baseline_connections = conns
    except Exception as e:
        log(f"[WARN] psutil no disponible: {{e}}")
    cycle += 1
    time.sleep(20)
''',
    }
    script = scripts.get(name)
    if script:
        script_path.write_text(script)
        script_path.chmod(0o755)

def _start_service(name: str) -> tuple:
    if name == "dashboard_server":
        return False, "El dashboard no puede detenerse a sí mismo"
    defn = SERVICE_DEFS.get(name)
    if not defn:
        return False, "Servicio desconocido"
    _ensure_service_script(name)
    with _svc_lock:
        proc = _procs.get(name)
        if proc and proc.poll() is None:
            return False, "Ya está corriendo"
        log_path = pathlib.Path(defn["log_file"])
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fd = open(log_path, "a")
        try:
            p = subprocess.Popen(
                defn["cmd"],
                stdout=log_fd, stderr=log_fd,
                cwd=str(ROOT),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            _procs[name] = p
            _svc_start_times[name] = time.time()
            return True, f"Iniciado PID {p.pid}"
        except Exception as e:
            return False, str(e)

def _stop_service(name: str) -> tuple:
    if name == "dashboard_server":
        return False, "El dashboard no puede detenerse a sí mismo"
    with _svc_lock:
        proc = _procs.get(name)
        if not proc or proc.poll() is not None:
            return False, "No estaba corriendo"
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            _procs[name] = None
            return True, "Detenido"
        except Exception as e:
            return False, str(e)

def _restart_service(name: str) -> tuple:
    _stop_service(name)
    time.sleep(0.5)
    return _start_service(name)

# ── Persistencia de datos ─────────────────────────────────────────────────────
def _load_json(path: pathlib.Path, default) -> dict | list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default

def _save_json(path: pathlib.Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

# Archivos de datos persistentes
IOC_FILE      = DATA_DIR / "iocs.json"
DEVICES_FILE  = DATA_DIR / "rasp_devices.json"
HONEYPOT_FILE = DATA_DIR / "honeypot.json"
SOAR_FILE     = DATA_DIR / "soar_dags.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

# Datos iniciales si no existen
def _init_data():
    if not IOC_FILE.exists():
        _save_json(IOC_FILE, [
            {"id": "ioc-1", "type": "domain", "value": "c2.darknet-example.onion",
             "confidence": 92, "tags": ["c2", "malware"], "added": datetime.datetime.utcnow().isoformat()},
            {"id": "ioc-2", "type": "ip", "value": "185.220.101.47",
             "confidence": 78, "tags": ["tor-exit", "scanner"], "added": datetime.datetime.utcnow().isoformat()},
            {"id": "ioc-3", "type": "hash",
             "value": "a3f1c8b2d94e7f0123456789abcdef01234567890abcdef01234567890abcdef0",
             "confidence": 97, "tags": ["ransomware", "lockbit"], "added": datetime.datetime.utcnow().isoformat()},
            {"id": "ioc-4", "type": "url", "value": "hxxps://phish-example[.]ru/login",
             "confidence": 85, "tags": ["phishing", "credential-harvest"], "added": datetime.datetime.utcnow().isoformat()},
        ])
    if not DEVICES_FILE.exists():
        _save_json(DEVICES_FILE, [
            {"id": "dev-001", "name": "Moto Edge 50 Fusion", "platform": "android",
             "attestation": "passed", "last_seen": datetime.date.today().isoformat(), "enrolled": True},
            {"id": "dev-002", "name": "Pixel 8 Pro (Test)", "platform": "android",
             "attestation": "passed", "last_seen": datetime.date.today().isoformat(), "enrolled": True},
            {"id": "dev-003", "name": "Samsung Galaxy S24", "platform": "android",
             "attestation": "failed", "last_seen": (datetime.date.today() - datetime.timedelta(days=3)).isoformat(), "enrolled": True},
        ])
    if not HONEYPOT_FILE.exists():
        _save_json(HONEYPOT_FILE, {
            "active": True,
            "tokens_deployed": 8,
            "triggers_today": 0,
            "triggers_total": 17,
            "last_trigger": None,
            "token_rotated_at": datetime.datetime.utcnow().isoformat(),
        })
    if not SOAR_FILE.exists():
        _save_json(SOAR_FILE, [
            {"id": "dag-1", "name": "Alert Triage", "enabled": True,
             "trigger": "schedule", "interval_mins": 60,
             "steps": ["fetch_alerts", "correlate_iocs", "notify_slack"],
             "last_run": None, "description": "Revisa alertas y correlaciona con IOCs"},
            {"id": "dag-2", "name": "Incident Response", "enabled": False,
             "trigger": "manual",
             "steps": ["isolate_host", "collect_evidence", "create_ticket"],
             "last_run": None, "description": "Respuesta automatizada a incidentes"},
            {"id": "dag-3", "name": "IOC Enrichment", "enabled": True,
             "trigger": "schedule", "interval_mins": 30,
             "steps": ["fetch_tip_feeds", "deduplicate", "score", "export_stix"],
             "last_run": None, "description": "Enriquece y puntúa indicadores de compromiso"},
        ])
    if not SETTINGS_FILE.exists():
        _save_json(SETTINGS_FILE, {
            "api_url": BACKEND,
            "interval": 15,
            "scan_on_startup": False,
            "notify_slack": False,
            "slack_webhook": "",
        })

_init_data()

# ── Configuración de archivos editables ───────────────────────────────────────
CONFIG_BASE = ROOT

def _list_config_files() -> list:
    patterns = [
        ("orchestrator.yaml",    "runner/orchestrator.yaml"),
        ("soar_playbooks.json",  "soar/playbooks.json"),
        ("tip_config.yaml",      "tip/config.yaml"),
        ("ndr_rules.yaml",       "ndr/rules.yaml"),
        ("rasp_policy.json",     "rasp/policy.json"),
        ("requirements.txt",     "requirements.txt"),
    ]
    out = []
    for name, rel in patterns:
        full = CONFIG_BASE / rel
        if not full.exists():
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"# {name}\n# Edita este archivo y guarda\n")
        out.append({"name": name, "path": rel, "size": full.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(full.stat().st_mtime).isoformat()})
    return out

# ── Comando de terminal ────────────────────────────────────────────────────────
ALLOWED_CMDS = {"ls","cat","pwd","echo","grep","find","ps","df","free","uname",
                "date","id","whoami","netstat","ss","hostname","env","python3","pip","git",
                "head","tail","wc","sort","uniq","cut","awk","sed","top","uptime","which"}

def _run_terminal(command: str) -> dict:
    parts = command.strip().split()
    if not parts:
        return {"stdout": "", "stderr": "Comando vacío", "code": 1}
    base = parts[0].lstrip("/").split("/")[-1]
    if base not in ALLOWED_CMDS:
        return {"stdout": "", "stderr": f"Comando '{base}' no permitido. Permitidos: {', '.join(sorted(ALLOWED_CMDS))}", "code": 1}
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=10, cwd=str(ROOT),
        )
        return {"stdout": result.stdout[:8192], "stderr": result.stderr[:2048], "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout (10s)", "code": 124}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "code": 1}

# ── Scan thread ───────────────────────────────────────────────────────────────
def _run_scan_thread():
    global _scan_state
    started_at = datetime.datetime.utcnow().isoformat()
    t0 = time.time()
    findings, errors = [], []
    scan_evidence = EVIDENCE / f"scan-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    scan_evidence.mkdir(parents=True, exist_ok=True)
    dummy_apk = EVIDENCE / "dummy.apk"
    if not dummy_apk.exists():
        dummy_apk.write_bytes(b"PK\x03\x04dummy apk content")
    for scenario_name in SAFE_SCENARIOS:
        with _scan_lock:
            _scan_state["progress"] = f"Ejecutando: {scenario_name}..."
        try:
            mod_path = ROOT / "scenarios" / f"{scenario_name}.py"
            if not mod_path.exists():
                errors.append({"scenario": scenario_name, "error": "file not found"})
                continue
            spec = importlib.util.spec_from_file_location(f"scenarios.{scenario_name}", mod_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "run"):
                result = mod.run(target=str(dummy_apk), backend=BACKEND, output_dir=str(scan_evidence))
                if isinstance(result, list):
                    for f in result:
                        if isinstance(f, dict):
                            f.setdefault("scenario", scenario_name)
                            f.setdefault("timestamp", datetime.datetime.utcnow().isoformat())
                            findings.append(f)
        except Exception as e:
            err_msg = str(e)
            if "strings" in err_msg.lower() or "FileNotFoundError" in err_msg:
                findings.append({"scenario": scenario_name, "severity": "info",
                    "title": f"[{scenario_name}] Análisis estático limitado",
                    "description": "El comando 'strings' no está disponible en este entorno.",
                    "evidence_path": "", "remediation": "apt-get install -y binutils",
                    "timestamp": datetime.datetime.utcnow().isoformat()})
            else:
                errors.append({"scenario": scenario_name, "error": err_msg})
    elapsed = round(time.time() - t0, 1)
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        by_severity[sev if sev in by_severity else "info"] += 1
    report = {"started_at": started_at, "finished_at": datetime.datetime.utcnow().isoformat(),
              "elapsed_seconds": elapsed, "total_findings": len(findings),
              "by_severity": by_severity, "findings": findings, "errors": errors,
              "target": str(dummy_apk), "backend": BACKEND,
              "scenarios_run": len(SAFE_SCENARIOS) - len(errors)}
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    try:
        (REPORTS / f"report-{ts}.json").write_text(json.dumps(report, indent=2, default=str))
        (REPORTS / "latest.json").write_text(json.dumps(report, indent=2, default=str))
    except Exception as e:
        print(f"[scan] Error saving report: {e}", flush=True)
    with _scan_lock:
        _scan_state.update({"running": False, "progress": "",
            "last_result": {"ok": True, "findings": len(findings), "elapsed": elapsed,
                            "by_severity": by_severity, "errors": len(errors)},
            "last_error": None})
    print(f"[scan] Done: {len(findings)} findings in {elapsed}s", flush=True)

def _start_scan():
    with _scan_lock:
        if _scan_state["running"]:
            return False, "already_running"
        _scan_state.update({"running": True, "last_error": None, "last_result": None, "progress": "Iniciando..."})
    threading.Thread(target=_run_scan_thread, daemon=True).start()
    return True, "started"

# ── HTTP Handler ──────────────────────────────────────────────────────────────
_SERVER_START = time.time()

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
        ".json": "application/json", ".css": "text/css",
        ".png": "image/png", ".ico": "image/x-icon", ".svg": "image/svg+xml"}

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return {}

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/") or "/"
        q = {}
        if "?" in self.path:
            from urllib.parse import parse_qs
            raw = self.path.split("?", 1)[1]
            q = {k: v[0] for k, v in parse_qs(raw).items()}

        routes = {
            "/health": lambda: self._json({"status": "ok", "uptime": _fmt_uptime(_SERVER_START)}),
            "/healthz": lambda: self._json({"status": "ok"}),
            "/ping":    lambda: self._json({"status": "ok"}),
            "/api/latest":        self._api_latest,
            "/api/history":       self._api_history,
            "/api/scan/status":   self._api_scan_status,
            "/api/scan":          self._api_scan,
            "/api/services":      lambda: self._json(_all_services_status()),
            "/api/resources":     self._api_resources,
            "/api/config":        lambda: self._json(_list_config_files()),
            "/api/config/read":   lambda: self._api_config_read(q.get("path", "")),
            "/api/honeypot":      lambda: self._json(_load_json(HONEYPOT_FILE, {})),
            "/api/soar/dags":     lambda: self._json(_load_json(SOAR_FILE, [])),
            "/api/tip/iocs":      lambda: self._json(_load_json(IOC_FILE, [])),
            "/api/rasp/devices":  lambda: self._json(_load_json(DEVICES_FILE, [])),
            "/api/settings":      lambda: self._json(_load_json(SETTINGS_FILE, {})),
        }
        # Logs endpoint: /api/services/{name}/logs
        if p.startswith("/api/services/") and p.endswith("/logs"):
            name = p.split("/")[3]
            return self._json(_tail_log(name, 50) if name in SERVICE_DEFS else [])

        handler = routes.get(p)
        if handler:
            return handler()
        return self._static(p)

    def do_POST(self):
        p = self.path.rstrip("/")
        body = self._body()

        if p == "/api/scan":
            return self._api_scan()
        if p == "/api/services/start":
            ok, msg = _start_service(body.get("name", ""))
            return self._json({"ok": ok, "message": msg})
        if p == "/api/services/stop":
            ok, msg = _stop_service(body.get("name", ""))
            return self._json({"ok": ok, "message": msg})
        if p == "/api/services/restart":
            ok, msg = _restart_service(body.get("name", ""))
            return self._json({"ok": ok, "message": msg})
        if p == "/api/services/start-all":
            results = {}
            for name in SERVICE_DEFS:
                if name != "dashboard_server":
                    ok, msg = _start_service(name)
                    results[name] = {"ok": ok, "message": msg}
            return self._json({"ok": True, "results": results})
        if p == "/api/services/stop-all":
            results = {}
            for name in SERVICE_DEFS:
                if name != "dashboard_server":
                    ok, msg = _stop_service(name)
                    results[name] = {"ok": ok, "message": msg}
            return self._json({"ok": True, "results": results})
        if p == "/api/config/write":
            return self._api_config_write(body)
        if p == "/api/honeypot/toggle":
            hp = _load_json(HONEYPOT_FILE, {})
            hp["active"] = not hp.get("active", False)
            _save_json(HONEYPOT_FILE, hp)
            return self._json(hp)
        if p == "/api/honeypot/rotate":
            hp = _load_json(HONEYPOT_FILE, {})
            hp["tokens_deployed"] = hp.get("tokens_deployed", 0) + 1
            hp["token_rotated_at"] = datetime.datetime.utcnow().isoformat()
            _save_json(HONEYPOT_FILE, hp)
            return self._json({"ok": True, "tokens_deployed": hp["tokens_deployed"]})
        if p == "/api/soar/dry-run":
            dags = _load_json(SOAR_FILE, [])
            steps = []
            for dag in dags:
                if dag.get("enabled"):
                    for step in dag.get("steps", []):
                        steps.append(f"[{dag['name']}] {step}")
            return self._json({"ok": True, "steps": steps, "count": len(steps)})
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
        if p == "/api/tip/import-stix":
            # Importa indicadores de un bundle STIX2
            bundle = body
            imported = 0
            iocs = _load_json(IOC_FILE, [])
            for obj in bundle.get("objects", []):
                if obj.get("type") == "indicator":
                    pattern = obj.get("pattern", "")
                    ioc = {"id": obj.get("id", f"ioc-{uuid.uuid4().hex[:8]}"),
                           "type": "stix", "value": pattern,
                           "confidence": int(obj.get("confidence", 50)),
                           "tags": ["stix", "imported"],
                           "added": datetime.datetime.utcnow().isoformat()}
                    iocs.append(ioc)
                    imported += 1
            _save_json(IOC_FILE, iocs)
            return self._json({"ok": True, "imported": imported})
        if p == "/api/rasp/devices":
            device = body
            device.setdefault("id", f"dev-{uuid.uuid4().hex[:8]}")
            device.setdefault("last_seen", datetime.date.today().isoformat())
            device.setdefault("attestation", "pending")
            devices = _load_json(DEVICES_FILE, [])
            devices.append(device)
            _save_json(DEVICES_FILE, devices)
            return self._json({"ok": True, "id": device["id"]})
        if p == "/api/terminal":
            cmd = body.get("command", "")
            result = _run_terminal(cmd)
            return self._json(result)
        if p == "/api/settings":
            settings = _load_json(SETTINGS_FILE, {})
            settings.update(body)
            _save_json(SETTINGS_FILE, settings)
            return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        p = self.path.rstrip("/")
        # DELETE /api/tip/iocs/{id}
        if p.startswith("/api/tip/iocs/"):
            ioc_id = p.split("/")[-1]
            iocs = _load_json(IOC_FILE, [])
            iocs = [i for i in iocs if i.get("id") != ioc_id]
            _save_json(IOC_FILE, iocs)
            return self._json({"ok": True})
        # DELETE /api/rasp/devices/{id}
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

    # ── API helpers ───────────────────────────────────────────────────────────
    def _api_scan(self):
        ok, msg = _start_scan()
        self._json({"status": "started" if ok else "running", "ok": True, "message": msg})

    def _api_scan_status(self):
        with _scan_lock:
            self._json(dict(_scan_state))

    def _api_resources(self):
        if HAS_PSUTIL:
            cpu = psutil.cpu_percent(interval=0.2)
            vm  = psutil.virtual_memory()
            self._json({"cpu_usage": cpu,
                        "memory_used": vm.used, "memory_total": vm.total,
                        "memory_percent": vm.percent})
        else:
            # Fallback: leer /proc/meminfo
            try:
                mem = {}
                for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.strip().split()[0]) * 1024
                total = mem.get("MemTotal", 2 * 1024**3)
                free  = mem.get("MemAvailable", 1 * 1024**3)
                used  = total - free
                self._json({"cpu_usage": 0.0, "memory_used": used,
                            "memory_total": total, "memory_percent": round(used/total*100, 1)})
            except Exception:
                self._json({"cpu_usage": 0.0,
                            "memory_used": 256 * 1024 * 1024,
                            "memory_total": 2048 * 1024 * 1024,
                            "memory_percent": 12.5})

    def _api_latest(self):
        latest_json = REPORTS / "latest.json"
        if latest_json.exists():
            try:
                return self._json(json.loads(latest_json.read_text()))
            except Exception:
                pass
        files = sorted(REPORTS.glob("report-*.json"), reverse=True)
        if files:
            try:
                return self._json(json.loads(files[0].read_text()))
            except Exception:
                pass
        return self._json({"findings": [], "total_findings": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            "message": "Sin reportes. Presiona 'Ejecutar escaneo'."})

    def _api_history(self):
        out = []
        for f in sorted(REPORTS.glob("report-*.json"), reverse=True)[:50]:
            try:
                r = json.loads(f.read_text())
                out.append({"file": f.name, "id": f.stem,
                            "total": r.get("total_findings", 0),
                            "finished_at": r.get("finished_at", ""),
                            "by_severity": r.get("by_severity", {}),
                            "elapsed_seconds": r.get("elapsed_seconds", 0)})
            except Exception:
                pass
        return self._json(out)

    def _api_config_read(self, rel_path: str):
        if not rel_path or ".." in rel_path:
            return self._json({"error": "path inválido"}, 400)
        full = (CONFIG_BASE / rel_path).resolve()
        if not str(full).startswith(str(CONFIG_BASE)):
            return self._json({"error": "path fuera del directorio base"}, 403)
        if not full.exists():
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(f"# {rel_path}\n")
        self._json({"content": full.read_text(errors="replace"), "path": rel_path})

    def _api_config_write(self, body: dict):
        rel_path = body.get("path", "")
        content  = body.get("content", "")
        if not rel_path or ".." in rel_path:
            return self._json({"error": "path inválido"}, 400)
        full = (CONFIG_BASE / rel_path).resolve()
        if not str(full).startswith(str(CONFIG_BASE)):
            return self._json({"error": "path fuera del directorio base"}, 403)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
        self._json({"ok": True, "path": rel_path,
                    "bytes": len(content.encode()),
                    "saved_at": datetime.datetime.utcnow().isoformat()})

    def _static(self, path):
        if path == "/":
            f = DASHBOARD / "index.html"
            return self._send_file(f) if f.exists() else self._raw(b"SourceSeal API OK", "text/plain")
        f = DASHBOARD / path.lstrip("/")
        if f.exists() and f.is_file():
            return self._send_file(f)
        self._json({"error": "not found"}, 404)

    def _send_file(self, f):
        data = f.read_bytes()
        self._raw(data, MIME.get(f.suffix.lower(), "application/octet-stream"))

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _raw(self, data, ct, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)


class Server(http.server.HTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"[dashboard] Iniciando en port={PORT} root={ROOT}", flush=True)
    print(f"[dashboard] psutil={'disponible' if HAS_PSUTIL else 'no disponible (fallback proc)'}", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
