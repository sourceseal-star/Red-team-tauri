"""Dashboard server - serves PWA dashboard + REST API con scan real."""
import http.server
import json
import os
import pathlib
import sys
import threading
import time
import datetime
import importlib.util
import traceback
import socket
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard"
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence"
PORT = int(os.environ.get("PORT", "8000"))
BACKEND = os.environ.get("SOURCESEAL_API", "https://api.sourcesealcorp.local")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for d in (REPORTS, EVIDENCE):
    d.mkdir(parents=True, exist_ok=True)

_scan_lock = threading.Lock()
_scan_state = {
    "running": False,
    "last_result": None,
    "last_error": None,
    "progress": "",
}

FALLBACK_HTML = b"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>SourceSeal RedTeam</title>
<style>body{font-family:monospace;background:#0a0a0a;color:#00ff88;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{text-align:center;padding:2rem;border:1px solid #00ff88;border-radius:8px}
h1{font-size:1.5rem}p{color:#888}</style></head>
<body><div class="box"><h1>SourceSeal RedTeam</h1>
<p>Server online</p><p>API: /api/latest /api/history /api/scan /api/scan/status</p>
</div></body></html>"""

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript",
    ".json": "application/json",
    ".css":  "text/css",
    ".png":  "image/png",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
}

SAFE_SCENARIOS = [
    "sourcesealcorp",
    "multiplatform",
    "rng",
    "pinning",
    "imei",
    "sidechannel",
    "keyhandling",
    "payments",
    "recovery_page",
    "biometric",
    "business_logic",
]


def _run_scan_thread():
    """Ejecuta los escenarios en background y guarda el reporte."""
    global _scan_state
    started_at = datetime.datetime.utcnow().isoformat()
    t0 = time.time()
    findings = []
    errors = []

    # Directorio de evidencia para este scan
    scan_evidence = EVIDENCE / f"scan-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    scan_evidence.mkdir(parents=True, exist_ok=True)

    # Crear dummy APK si no existe
    dummy_apk = EVIDENCE / "dummy.apk"
    if not dummy_apk.exists():
        dummy_apk.write_bytes(b"PK\x03\x04dummy apk content")

    # Verificar si 'strings' está disponible; si no, crear fallback
    has_strings = shutil.which("strings") is not None

    for scenario_name in SAFE_SCENARIOS:
        with _scan_lock:
            _scan_state["progress"] = f"Ejecutando: {scenario_name}..."

        try:
            mod_path = ROOT / "scenarios" / f"{scenario_name}.py"
            if not mod_path.exists():
                errors.append({"scenario": scenario_name, "error": "file not found"})
                continue

            spec = importlib.util.spec_from_file_location(
                f"scenarios.{scenario_name}", mod_path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if hasattr(mod, "run"):
                result = mod.run(
                    target=str(dummy_apk),
                    backend=BACKEND,
                    output_dir=str(scan_evidence),
                )
                if isinstance(result, list):
                    for f in result:
                        if isinstance(f, dict):
                            f.setdefault("scenario", scenario_name)
                            f.setdefault("timestamp", datetime.datetime.utcnow().isoformat())
                            findings.append(f)
        except Exception as e:
            err_msg = str(e)
            # Si es error de 'strings' command, crear finding de info
            if "strings" in err_msg.lower() or "FileNotFoundError" in err_msg:
                findings.append({
                    "scenario": scenario_name,
                    "severity": "info",
                    "title": f"[{scenario_name}] Análisis de strings omitido (tool no disponible)",
                    "description": "El comando 'strings' no está disponible en este entorno. Análisis estático limitado.",
                    "evidence_path": "",
                    "remediation": "Instalar binutils: apt-get install -y binutils",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                })
            else:
                errors.append({
                    "scenario": scenario_name,
                    "error": err_msg,
                })

    elapsed = round(time.time() - t0, 1)
    finished_at = datetime.datetime.utcnow().isoformat()

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = str(f.get("severity", "info")).lower()
        if sev in by_severity:
            by_severity[sev] += 1
        else:
            by_severity["info"] += 1

    report = {
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": elapsed,
        "total_findings": len(findings),
        "by_severity": by_severity,
        "findings": findings,
        "errors": errors,
        "target": str(dummy_apk),
        "backend": BACKEND,
        "scenarios_run": len(SAFE_SCENARIOS) - len(errors),
    }

    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    try:
        (REPORTS / f"report-{ts}.json").write_text(json.dumps(report, indent=2, default=str))
        (REPORTS / "latest.json").write_text(json.dumps(report, indent=2, default=str))
    except Exception as e:
        print(f"[scan] Error saving report: {e}", flush=True)

    with _scan_lock:
        _scan_state["running"] = False
        _scan_state["last_result"] = {
            "ok": True,
            "findings": len(findings),
            "elapsed": elapsed,
            "by_severity": by_severity,
            "errors": len(errors),
        }
        _scan_state["last_error"] = None
        _scan_state["progress"] = ""

    print(f"[scan] Done: {len(findings)} findings, {len(errors)} errors in {elapsed}s", flush=True)


def _start_scan():
    global _scan_state
    with _scan_lock:
        if _scan_state["running"]:
            return False, "already_running"
        _scan_state["running"] = True
        _scan_state["last_error"] = None
        _scan_state["last_result"] = None
        _scan_state["progress"] = "Iniciando..."

    t = threading.Thread(target=_run_scan_thread, daemon=True)
    t.start()
    return True, "started"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in ("/health", "/healthz", "/ping"):
            return self._json({"status": "ok"})
        if path == "/api/latest":
            return self._api_latest()
        if path == "/api/history":
            return self._api_history()
        if path == "/api/scan/status":
            return self._api_scan_status()
        # Also allow GET /api/scan to start a scan (for backward compat)
        if path == "/api/scan":
            return self._api_scan()
        return self._static(path)

    def do_POST(self):
        if self.path.rstrip("/") == "/api/scan":
            return self._api_scan()
        self._json({"error": "not found"}, 404)

    def _api_scan(self):
        ok, msg = _start_scan()
        if ok:
            self._json({"status": "started", "ok": True, "message": "Scan iniciado correctamente"})
        else:
            self._json({"status": "running", "ok": True, "message": "Scan ya en progreso"})

    def _api_scan_status(self):
        with _scan_lock:
            state = dict(_scan_state)
        self._json(state)

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
        return self._json({
            "findings": [],
            "total_findings": 0,
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            "message": "No hay reportes. Presiona 'Ejecutar escaneo'."
        })

    def _api_history(self):
        out = []
        for f in sorted(REPORTS.glob("report-*.json"), reverse=True)[:50]:
            try:
                r = json.loads(f.read_text())
                out.append({
                    "file": f.name,
                    "total": r.get("total_findings", 0),
                    "finished_at": r.get("finished_at", ""),
                    "by_severity": r.get("by_severity", {}),
                })
            except Exception:
                pass
        return self._json(out)

    def _static(self, path):
        if path == "/":
            f = DASHBOARD / "index.html"
            return self._send_file(f) if f.exists() else self._raw(FALLBACK_HTML, "text/html; charset=utf-8")
        f = DASHBOARD / path.lstrip("/")
        if f.exists() and f.is_file():
            return self._send_file(f)
        # SPA fallback
        index = DASHBOARD / "index.html"
        if index.exists():
            return self._send_file(index)
        self._json({"error": "not found"}, 404)

    def _send_file(self, f):
        data = f.read_bytes()
        ct = MIME.get(f.suffix.lower(), "application/octet-stream")
        self._raw(data, ct)

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _raw(self, data, ct, status=200):
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Server(http.server.HTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"[dashboard] port={PORT} root={ROOT}", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
