"""
Dashboard unificado — SOURCESEAL RedTeam + Site Monitor + Editor

Sirve el directorio `dashboard/` y expone:
  GET  /api/latest                    -> último reporte del RedTeam Agent
  GET  /api/history                   -> historial compacto de reportes
  POST /api/scan                      -> dispara un escaneo (largo, puede timeout)
  GET  /api/site/state                -> snapshot del monitor del sitio
  GET  /api/site/events               -> Server-Sent Events del monitor
  POST /api/site/configure            -> {url, interval} reinicia el monitor
  GET  /api/site/fetch?url=...        -> descarga el sitio para edición
  POST /api/site/publish              -> {owner, slug, files:[{path,content}]}
                                        requiere REPLIT_TOKEN en env

Variables de entorno relevantes:
  PORT (default 8000)
  REPLIT_TOKEN (opcional, habilita /api/site/publish)
  SITE_MONITOR_URL (opcional, auto-configura al arrancar)
  SITE_MONITOR_INTERVAL (default 15s)
  SOURCESEAL_API, SOURCESEAL_KEY, RECOVERY_PAGE (las del agente original)
"""
import json
import os
import pathlib
import queue
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from site_monitor.monitor import EventBus, SiteMonitor  # noqa: E402
from redteam.threat_intel import (  # noqa: E402
    fetch_all_iocs, get_iocs, add_ioc, delete_ioc, import_stix,
)
from site_monitor.edit import (  # noqa: E402
    ReplitPublisher, fetch_site, parse_repl_url,
)

DASHBOARD = ROOT / "dashboard"
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence"
PORT = int(os.environ.get("PORT", "8000"))

# Estado global: monitor activo + bus de eventos
_MONITORS: dict = {}   # key=url -> SiteMonitor
_MONITORS_LOCK = threading.Lock()
_DEFAULT_BUS = EventBus()


def _ensure_monitor(url: str, interval: float) -> SiteMonitor:
    with _MONITORS_LOCK:
        m = _MONITORS.get(url)
        if m:
            m.state.interval = interval
            return m
        m = SiteMonitor(url=url, interval=interval, bus=_DEFAULT_BUS)
        _MONITORS[url] = m
        m.start()
        return m


def _get_default_monitor() -> Optional[SiteMonitor]:
    with _MONITORS_LOCK:
        for m in _MONITORS.values():
            return m
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD), **kwargs)

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        p = parsed.path
        q = urllib.parse.parse_qs(parsed.query)

        if p == "/api/latest":
            return self._serve_latest_report()
        if p == "/api/history":
            return self._serve_report_history()
        if p == "/api/site/state":
            return self._serve_site_state()
        if p == "/api/site/events":
            return self._serve_sse()
        if p == "/api/site/fetch":
            return self._serve_site_fetch(q.get("url", [""])[0])
        if p == "/api/site/publish_check":
            return self._json({"publish_enabled": bool(os.environ.get("REPLIT_TOKEN"))})

        # ── Threat Intelligence ──────────────────────────────────
        if p == "/tip/iocs":
            return self._json(get_iocs())

        return super().do_GET()

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        p = parsed.path
        length = int(self.headers.get("Content-Length", "0") or 0)
        body_raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(body_raw.decode("utf-8")) if body_raw else {}
        except Exception:
            body = {}

        if p == "/api/scan":
            return self._run_scan()
        if p == "/api/site/configure":
            return self._configure_site(body)
        if p == "/api/site/publish":
            return self._publish_to_replit(body)

        # ── Threat Intelligence ──────────────────────────────────
        if p == "/tip/iocs":
            return self._json(add_ioc(body))
        if p.startswith("/tip/iocs/"):
            ioc_id = p.split("/tip/iocs/")[1]
            return self._json(delete_ioc(ioc_id))
        if p == "/tip/import-stix":
            return self._json(import_stix(body))
        if p == "/tip/update":
            iocs = fetch_all_iocs()
            return self._json({"iocs_loaded": len(iocs)})

        self._json({"error": "not found"}, 404)

    # ----------------------------------------------------------------- SSE
    def _serve_sse(self):
        sub = _DEFAULT_BUS.subscribe()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # enviar snapshot inicial
        m = _get_default_monitor()
        if m:
            snap = m.snapshot()
            self._write_sse("snapshot", snap)
        else:
            self._write_sse("info", {"message": "monitor no configurado"})

        try:
            while True:
                try:
                    ev = sub.get(timeout=15)
                except queue.Empty:
                    self._write_sse("ping", {"ts": time.time()})
                    self.wfile.flush()
                    continue
                kind = ev.get("type", "event")
                self._write_sse(kind, ev)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _DEFAULT_BUS.unsubscribe(sub)

    def _write_sse(self, event: str, data) -> None:
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(msg.encode("utf-8"))
        self.wfile.flush()

    # ------------------------------------------------------------- helpers
    def _json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------- reports
    def _serve_latest_report(self):
        REPORTS.mkdir(exist_ok=True)
        files = sorted(REPORTS.glob("report-*.json"), reverse=True)
        if not files:
            return self._json({"findings": [], "by_severity": {},
                               "total_findings": 0, "agent": "no-data"})
        try:
            data = json.loads(files[0].read_text())
            data["agent"] = data.get("agent") or "redteam-agent"
            return self._json(data)
        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def _serve_report_history(self):
        REPORTS.mkdir(exist_ok=True)
        files = sorted(REPORTS.glob("report-*.json"), reverse=True)[:50]
        out = []
        for f in files:
            try:
                r = json.loads(f.read_text())
                out.append({"finished_at": r.get("finished_at"),
                            "by_severity": r.get("by_severity", {}),
                            "total_findings": r.get("total_findings", 0)})
            except Exception:
                pass
        return self._json(list(reversed(out)))

    def _run_scan(self):
        EVIDENCE.mkdir(exist_ok=True)
        target = EVIDENCE / "dummy.apk"
        if not target.exists():
            target.write_bytes(b"")
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "runner" / "orchestrator.py"),
                 "--target", str(target),
                 "--backend", os.environ.get("SOURCESEAL_API",
                                             "https://api.sourcesealcorp.local"),
                 "--output", str(REPORTS)],
                check=True, timeout=180, cwd=str(ROOT),
            )
            return self._json({"ok": True})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)

    # ------------------------------------------------------------- monitor
    def _configure_site(self, body):
        url = (body.get("url") or "").strip()
        interval = float(body.get("interval") or 15)
        if not url.startswith(("http://", "https://")):
            return self._json({"ok": False, "error": "URL inválida"}, 400)
        m = _ensure_monitor(url, interval)
        return self._json({"ok": True, "url": url, "interval": interval,
                           "snapshot": m.snapshot()})

    def _serve_site_state(self):
        m = _get_default_monitor()
        if not m:
            return self._json({"ok": False, "error": "monitor no configurado"}, 404)
        return self._json({"ok": True, "snapshot": m.snapshot()})

    def _serve_site_fetch(self, url: str):
        if not url:
            return self._json({"ok": False, "error": "url requerida"}, 400)
        if not url.startswith(("http://", "https://")):
            return self._json({"ok": False, "error": "URL inválida"}, 400)
        result = fetch_site(url)
        if not result.get("ok"):
            return self._json(result, 502)
        return self._json(result)

    # ----------------------------------------------------------- replit
    def _publish_to_replit(self, body):
        token = os.environ.get("REPLIT_TOKEN")
        if not token:
            return self._json({"ok": False,
                               "error": "REPLIT_TOKEN no configurado"}, 403)
        site_url = (body.get("site_url") or "").strip()
        files = body.get("files") or []
        if not site_url or not files:
            return self._json({"ok": False, "error": "site_url y files son requeridos"}, 400)
        parsed = parse_repl_url(site_url)
        if not parsed:
            return self._json({"ok": False,
                               "error": "URL no parece un Repl replit.com/@owner/slug"}, 400)
        owner, slug = parsed
        publisher = ReplitPublisher(token)
        result = publisher.write_files(owner, slug, files)
        return self._json({"ok": result.get("ok"), **result})

    # ------------------------------------------------------------ logging
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[dashboard] {fmt % args}\n")


def main():
    REPORTS.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)

    # auto-arranque del monitor si hay URL por env
    site_url = os.environ.get("SITE_MONITOR_URL")
    if site_url:
        interval = float(os.environ.get("SITE_MONITOR_INTERVAL", "15"))
        _ensure_monitor(site_url, interval)
        print(f"🛰  Site Monitor activo: {site_url} cada {interval}s")

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as srv:
        print(f"🛡   Dashboard en http://0.0.0.0:{PORT}")
        print(f"    API: /api/latest /api/history /api/scan")
        print(f"    Monitor: /api/site/state /api/site/events (SSE)")
        print(f"    Editor: /api/site/fetch /api/site/publish")
        if not os.environ.get("REPLIT_TOKEN"):
            print("    ⚠  REPLIT_TOKEN no configurado: editor en modo 'patches'")
        else:
            print("    ✅ REPLIT_TOKEN detectado: editor puede publicar al Repl")
        srv.serve_forever()


if __name__ == "__main__":
    main()
