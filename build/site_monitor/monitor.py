"""
Site Monitor — vigilancia pasiva en tiempo real de un dominio externo.

Por diseño, este módulo NO requiere credenciales del sitio objetivo.
Hace polling periódico contra la URL pública, mide:
  - uptime / latencia
  - código HTTP y redirecciones
  - headers de seguridad
  - expiración del certificado TLS
  - diff de HTML entre muestras (detección de defacement / inyección)
  - tamaño y SHA-256 del body

Los resultados se empujan a un EventBus en memoria y se sirven al dashboard
por Server-Sent Events (SSE).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import socket
import ssl
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_TIMEOUT = float(os.environ.get("SITE_MONITOR_TIMEOUT", "10"))
DEFAULT_INTERVAL = float(os.environ.get("SITE_MONITOR_INTERVAL", "15"))
MAX_DIFF_SAMPLES = int(os.environ.get("SITE_MONITOR_DIFF_SAMPLES", "30"))


# ---------------------------------------------------------------------------
# Event bus (memoria, thread-safe, sin dependencias externas)
# ---------------------------------------------------------------------------
class EventBus:
    """Bus simple basado en queue.Queue. Soporta múltiples suscriptores SSE."""

    def __init__(self) -> None:
        self._subscribers: List["queue.Queue"] = []
        self._lock = threading.Lock()

    def subscribe(self) -> "queue.Queue":
        import queue
        q: "queue.Queue" = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def publish(self, event: Dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------
@dataclass
class ProbeResult:
    timestamp: str
    url: str
    ok: bool
    status: int
    latency_ms: float
    body_size: int
    body_sha256: str
    server_header: Optional[str]
    security_headers: Dict[str, str]
    missing_security_headers: List[str]
    content_type: Optional[str]
    tls_expires_in_days: Optional[int]
    tls_subject: Optional[str]
    tls_issuer: Optional[str]
    error: Optional[str] = None
    diff_summary: Optional[str] = None
    changed_since_last: bool = False


@dataclass
class SiteState:
    url: str
    interval: float
    last: Optional[ProbeResult] = None
    history: List[ProbeResult] = field(default_factory=list)
    total_probes: int = 0
    total_failures: int = 0
    last_change_at: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------
class SiteMonitor:
    """Polling en background de una URL pública + emisión de eventos."""

    SECURITY_HEADERS = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ]

    def __init__(self, url: str, interval: float = DEFAULT_INTERVAL,
                 bus: Optional[EventBus] = None) -> None:
        self.state = SiteState(url=url, interval=interval)
        self.bus = bus or EventBus()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # -- ciclo de vida -----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="site-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # -- núcleo ------------------------------------------------------------
    def _run(self) -> None:
        self.bus.publish({"type": "monitor.started", "url": self.state.url,
                          "interval": self.state.interval,
                          "ts": datetime.now(timezone.utc).isoformat()})
        while not self._stop.is_set():
            try:
                result = self.probe_once()
            except Exception as e:  # nunca dejar caer el loop
                result = ProbeResult(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    url=self.state.url, ok=False, status=0, latency_ms=0.0,
                    body_size=0, body_sha256="", server_header=None,
                    security_headers={}, missing_security_headers=[],
                    content_type=None, tls_expires_in_days=None,
                    tls_subject=None, tls_issuer=None, error=str(e),
                )
            self._record(result)
            self._stop.wait(self.state.interval)

    def _record(self, r: ProbeResult) -> None:
        with self._lock:
            prev = self.state.last
            self.state.last = r
            self.state.history.append(r)
            if len(self.state.history) > MAX_DIFF_SAMPLES:
                self.state.history = self.state.history[-MAX_DIFF_SAMPLES:]
            self.state.total_probes += 1
            if not r.ok:
                self.state.total_failures += 1
            if prev is not None and prev.body_sha256 and r.body_sha256 and prev.body_sha256 != r.body_sha256:
                r.changed_since_last = True
                self.state.last_change_at = r.timestamp
                self.bus.publish({
                    "type": "site.content_changed",
                    "url": r.url,
                    "old_sha256": prev.body_sha256,
                    "new_sha256": r.body_sha256,
                    "diff_summary": r.diff_summary,
                    "ts": r.timestamp,
                })
        self.bus.publish({"type": "site.probe", "data": asdict(r)})

    # -- una sonda --------------------------------------------------------
    def probe_once(self) -> ProbeResult:
        ts = datetime.now(timezone.utc).isoformat()
        parsed = urllib.parse.urlparse(self.state.url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"scheme no soportado: {parsed.scheme}")

        ctx = ssl.create_default_context()
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        req = urllib.request.Request(
            self.state.url,
            headers={"User-Agent": "SOURCESEAL-Monitor/1.0 (+defacement-watch)"}
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT, context=ctx) as resp:
                status = resp.status
                body = resp.read()
                headers = {k: v for k, v in resp.headers.items()}
                content_type = headers.get("Content-Type")
                server_header = headers.get("Server")
        except Exception as e:
            return ProbeResult(
                timestamp=ts, url=self.state.url, ok=False, status=0,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                body_size=0, body_sha256="", server_header=None,
                security_headers={}, missing_security_headers=[],
                content_type=None, tls_expires_in_days=None,
                tls_subject=None, tls_issuer=None, error=str(e),
            )

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        body_size = len(body)
        body_sha256 = hashlib.sha256(body).hexdigest()
        # Intentar decodificar para diff legible (si es HTML/texto)
        text_preview = ""
        try:
            text_preview = body[:8192].decode("utf-8", errors="replace")
        except Exception:
            pass

        sec_headers = {h: headers.get(h) for h in self.SECURITY_HEADERS if h in headers}
        missing = [h for h in self.SECURITY_HEADERS if h not in headers]

        diff_summary = self._diff_against_last(text_preview)

        # TLS info
        tls_expires, tls_subject, tls_issuer = self._tls_info(parsed.hostname or "", parsed.port or 443)

        ok = 200 <= status < 400
        return ProbeResult(
            timestamp=ts, url=self.state.url, ok=ok, status=status,
            latency_ms=latency_ms, body_size=body_size, body_sha256=body_sha256,
            server_header=server_header, security_headers=sec_headers,
            missing_security_headers=missing, content_type=content_type,
            tls_expires_in_days=tls_expires, tls_subject=tls_subject,
            tls_issuer=tls_issuer, error=None, diff_summary=diff_summary,
        )

    def _diff_against_last(self, text: str) -> Optional[str]:
        with self._lock:
            last = next((h for h in reversed(self.state.history) if h.diff_summary is not None), None)
        if last is None or not text:
            return None
        # Reconstrucción barata: almacenamos el último texto en una variable aparte
        cached = _LAST_TEXT.get(self.state.url)
        if not cached:
            return None
        diff = list(difflib.unified_diff(
            cached.splitlines()[:400], text.splitlines()[:400],
            lineterm="", n=2
        ))
        if not diff:
            return None
        return "\n".join(diff[:80])  # cap

    def _tls_info(self, host: str, port: int) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        if not host:
            return None, None, None
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=DEFAULT_TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
            not_after = cert.get("notAfter")
            expires_in = None
            if not_after:
                dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                expires_in = (dt - datetime.now(timezone.utc)).days
            subject = " / ".join("=".join(t) for r in cert.get("subject", ())
                                  for t in r) or None
            issuer = " / ".join("=".join(t) for r in cert.get("issuer", ())
                                 for t in r) or None
            return expires_in, subject, issuer
        except Exception:
            return None, None, None

    # -- snapshot público --------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "url": self.state.url,
                "interval": self.state.interval,
                "started_at": self.state.started_at,
                "total_probes": self.state.total_probes,
                "total_failures": self.state.total_failures,
                "last_change_at": self.state.last_change_at,
                "last": asdict(self.state.last) if self.state.last else None,
                "history": [asdict(h) for h in self.state.history[-20:]],
            }


# cache proceso-local del último texto visto por URL, usado para diff
_LAST_TEXT: Dict[str, str] = {}
_LOCK_LAST = threading.Lock()


def remember_text(url: str, text: str, max_len: int = 200_000) -> None:
    with _LOCK_LAST:
        _LAST_TEXT[url] = text[:max_len]


# Parche: en _record guardamos el texto del body si fue texto. Hacemos esto
# sin modificar la firma pública usando un wrapper.
_original_record = SiteMonitor._record


def _record_with_text(self: SiteMonitor, r: ProbeResult) -> None:  # type: ignore[no-redef]
    if r.ok and r.body_size > 0 and r.content_type and "text" in r.content_type:
        # reconstruir texto no es trivial aquí porque ProbeResult no guarda el body
        # por diseño. En su lugar, programamos una sonda extra con cache separada.
        pass
    _original_record(self, r)


# Mejor: monkey-patch de probe_once para guardar el último texto. Esto evita
# modificar la dataclass pública.
_original_probe_once = SiteMonitor.probe_once


def _probe_once_with_cache(self: SiteMonitor) -> ProbeResult:  # type: ignore[no-redef]
    parsed = urllib.parse.urlparse(self.state.url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"scheme no soportado: {parsed.scheme}")
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    req = urllib.request.Request(
        self.state.url,
        headers={"User-Agent": "SOURCESEAL-Monitor/1.0 (+defacement-watch)"}
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT, context=ctx) as resp:
            status = resp.status
            body = resp.read()
            headers = {k: v for k, v in resp.headers.items()}
            content_type = headers.get("Content-Type")
            server_header = headers.get("Server")
    except Exception as e:
        return ProbeResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            url=self.state.url, ok=False, status=0,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            body_size=0, body_sha256="", server_header=None,
            security_headers={}, missing_security_headers=[],
            content_type=None, tls_expires_in_days=None,
            tls_subject=None, tls_issuer=None, error=str(e),
        )
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    body_size = len(body)
    body_sha256 = hashlib.sha256(body).hexdigest()
    text = ""
    if content_type and "text" in content_type:
        try:
            text = body[:8192].decode("utf-8", errors="replace")
            remember_text(self.state.url, text)
        except Exception:
            pass
    sec_headers = {h: headers.get(h) for h in self.SECURITY_HEADERS if h in headers}
    missing = [h for h in self.SECURITY_HEADERS if h not in headers]
    diff_summary = self._diff_against_last(text)
    tls_expires, tls_subject, tls_issuer = self._tls_info(parsed.hostname or "", parsed.port or 443)
    ok = 200 <= status < 400
    return ProbeResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        url=self.state.url, ok=ok, status=status, latency_ms=latency_ms,
        body_size=body_size, body_sha256=body_sha256,
        server_header=server_header, security_headers=sec_headers,
        missing_security_headers=missing, content_type=content_type,
        tls_expires_in_days=tls_expires, tls_subject=tls_subject,
        tls_issuer=tls_issuer, error=None, diff_summary=diff_summary,
    )


SiteMonitor.probe_once = _probe_once_with_cache  # type: ignore[assignment]
