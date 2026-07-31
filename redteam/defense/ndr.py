"""
defense.ndr — Network Detection and Response
==============================================

Analiza flujos de red (HTTP, DNS, ICMP) con técnicas de detección
comportamental:

  * **Beaconing**: intervalos regulares <60s con jitter <20% → C2
  * **DNS tunneling**: alta entropía en subdominios → exfil
  * **Low-and-slow exfil**: volumen sostenido bajo umbral
  * **ICMP tunnel**: payloads anómalos en ICMP

Mantiene una ventana deslizante por endpoint (5 min) y produce
``NDRFinding`` mapeados a MITRE ATT&CK.
"""
from __future__ import annotations

import base64
import collections
import dataclasses
import hashlib
import json
import logging
import math
import re
import statistics
import threading
import time
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===================== Data types =====================


@dataclasses.dataclass
class FlowEvent:
    """Un evento de red normalizado (agnóstico del origen)."""
    endpoint_id: str
    timestamp: float
    proto: str            # http | dns | icmp | tcp | udp
    direction: str        # inbound | outbound
    size: int
    dst: str              # IP, dominio o '*'
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class NDRFinding:
    severity: str
    category: str
    mitre_id: str
    evidence: str
    endpoint_id: str
    timestamp: float = dataclasses.field(default_factory=time.time)
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ===================== TLS Interception Proxy (mock) =====================


class TLSInterceptionProxy:
    """Decodifica payloads HTTP/HTTPS que pasan por el proxy MITM interno.

    En este entorno, no hay TLS real; simulamos la *inspección* de payloads
    HTTP ya decodificados. La idea: cualquier petición que pase por el
    gateway queda registrada como ``FlowEvent`` y consumida por NDR.
    """

    def __init__(self, ndr_engine: "NDREngine"):
        self.ndr = ndr_engine
        self._lock = threading.Lock()
        self._intercepted: List[Dict[str, Any]] = []

    def intercept_http(self, endpoint_id: str, method: str, url: str,
                       headers: Optional[Dict[str, str]] = None,
                       body: Optional[bytes] = None) -> Dict[str, Any]:
        body = body or b""
        headers = headers or {}
        size = len(body) + len(url) + sum(len(k) + len(v) for k, v in headers.items())
        # Extraer dominio
        m = re.match(r"https?://([^/]+)", url)
        dst = m.group(1) if m else url
        # Detectar posible base64 en headers (C2 exfil)
        decoded = None
        for k, v in headers.items():
            if re.fullmatch(r"[A-Za-z0-9+/=]{32,}", v or ""):
                try:
                    decoded = base64.b64decode(v).decode("utf-8", errors="replace")[:200]
                except Exception:
                    pass
        evt = FlowEvent(
            endpoint_id=endpoint_id,
            timestamp=time.time(),
            proto="http",
            direction="outbound",
            size=size,
            dst=dst,
            extra={"method": method, "url": url,
                   "decoded_header": decoded, "headers": dict(list(headers.items())[:5])},
        )
        self.ndr.ingest(evt)
        record = {"url": url, "method": method, "size": size, "decoded_header": decoded}
        with self._lock:
            self._intercepted.append(record)
        return record

    def intercepted(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._intercepted)


# ===================== NDR Engine =====================


class NDREngine:
    """Motor NDR con ventana deslizante por endpoint.

    Diseñado para ser alimentado por ``TLSInterceptionProxy`` o
    directamente por un sniffer externo (vía ``ingest``).
    """

    def __init__(
        self,
        *,
        window_seconds: int = 300,
        beaconing_max_interval: int = 60,
        beaconing_max_jitter_pct: float = 20.0,
        beaconing_min_samples: int = 5,
        dns_entropy_threshold: float = 3.5,
        dns_min_label_length: int = 20,
        exfil_bpm_threshold: int = 1024,
        exfil_sustained_minutes: int = 3,
        icmp_max_payload: int = 64,
        icmp_entropy_threshold: float = 2.0,
    ):
        self.window_seconds = window_seconds
        self.beaconing_max_interval = beaconing_max_interval
        self.beaconing_max_jitter_pct = beaconing_max_jitter_pct
        self.beaconing_min_samples = beaconing_min_samples
        self.dns_entropy_threshold = dns_entropy_threshold
        self.dns_min_label_length = dns_min_label_length
        self.exfil_bpm_threshold = exfil_bpm_threshold
        self.exfil_sustained_minutes = exfil_sustained_minutes
        self.icmp_max_payload = icmp_max_payload
        self.icmp_entropy_threshold = icmp_entropy_threshold
        self._events: Dict[str, Deque[FlowEvent]] = collections.defaultdict(
            lambda: collections.deque(maxlen=10000)
        )
        self._lock = threading.Lock()
        self._findings: List[NDRFinding] = []
        self._blocklist: List[Dict[str, Any]] = []
        # Buffer para correlate (consumido por XDR)
        self._recent: Deque[Dict[str, Any]] = collections.deque(maxlen=5000)

    # ---------- Ingest ----------

    def ingest(self, event: FlowEvent) -> List[NDRFinding]:
        """Registra el evento, aplica sliding window y retorna findings nuevos."""
        with self._lock:
            self._events[event.endpoint_id].append(event)
            self._recent.append({"endpoint": event.endpoint_id, "dst": event.dst,
                                 "ts": event.timestamp, "proto": event.proto})
            # Poda ventana
            self._prune(event.endpoint_id, event.timestamp)
        return self.analyze(event.endpoint_id)

    def ingest_many(self, events: List[FlowEvent]) -> List[NDRFinding]:
        out: List[NDRFinding] = []
        for e in events:
            out.extend(self.ingest(e))
        return out

    def _prune(self, endpoint_id: str, now: float) -> None:
        window = self._events[endpoint_id]
        cutoff = now - self.window_seconds
        while window and window[0].timestamp < cutoff:
            window.popleft()

    # ---------- Analyzers ----------

    def analyze(self, endpoint_id: str) -> List[NDRFinding]:
        with self._lock:
            window = list(self._events.get(endpoint_id, []))
        findings: List[NDRFinding] = []
        findings.extend(self.detect_beaconing(endpoint_id, window))
        findings.extend(self.detect_dns_tunneling(endpoint_id, window))
        findings.extend(self.detect_low_and_slow_exfil(endpoint_id, window))
        findings.extend(self.detect_icmp_tunnel(endpoint_id, window))
        # Dedupe simple: evita findings idénticos duplicados en ventana.
        new: List[NDRFinding] = []
        for f in findings:
            if not self._has_recent(f):
                new.append(f)
                with self._lock:
                    self._findings.append(f)
        return new

    def _has_recent(self, finding: NDRFinding, window_s: int = 60) -> bool:
        cutoff = finding.timestamp - window_s
        for f in reversed(self._findings):
            if f.timestamp < cutoff:
                return False
            if (f.endpoint_id == finding.endpoint_id
                    and f.category == finding.category
                    and f.mitre_id == finding.mitre_id):
                return True
        return False

    def detect_beaconing(self, endpoint_id: str,
                         window: Optional[List[FlowEvent]] = None) -> List[NDRFinding]:
        window = window if window is not None else list(self._events.get(endpoint_id, []))
        # Agrupar por (dst, proto) y ordenar por timestamp
        groups: Dict[Tuple[str, str], List[float]] = collections.defaultdict(list)
        for e in window:
            if e.direction == "outbound":
                groups[(e.dst, e.proto)].append(e.timestamp)
        findings: List[NDRFinding] = []
        for (dst, proto), ts_list in groups.items():
            if len(ts_list) < self.beaconing_min_samples:
                continue
            ts_sorted = sorted(ts_list)
            intervals = [ts_sorted[i + 1] - ts_sorted[i] for i in range(len(ts_sorted) - 1)]
            if not intervals:
                continue
            mean = statistics.mean(intervals)
            if mean > self.beaconing_max_interval:
                continue
            if mean <= 0:
                continue
            # Jitter = desviación estándar / media * 100
            jitter = (statistics.pstdev(intervals) / mean) * 100.0
            if jitter > self.beaconing_max_jitter_pct:
                continue
            findings.append(NDRFinding(
                severity="high",
                category="beaconing",
                mitre_id="T1071.001",
                evidence=f"{dst} {proto} n={len(ts_list)} mean={mean:.1f}s jitter={jitter:.1f}%",
                endpoint_id=endpoint_id,
                extra={"dst": dst, "proto": proto, "samples": len(ts_list),
                       "mean_interval": mean, "jitter_pct": jitter},
            ))
        return findings

    def detect_dns_tunneling(self, endpoint_id: str,
                             window: Optional[List[FlowEvent]] = None) -> List[NDRFinding]:
        window = window if window is not None else list(self._events.get(endpoint_id, []))
        findings: List[NDRFinding] = []
        for e in window:
            if e.proto != "dns":
                continue
            qname = e.extra.get("qname", "")
            # Tomamos solo la primera etiqueta larga (subdominio)
            parts = qname.split(".")
            for label in parts:
                if len(label) >= self.dns_min_label_length:
                    ent = self._entropy(label)
                    if ent >= self.dns_entropy_threshold:
                        findings.append(NDRFinding(
                            severity="high",
                            category="dns_tunneling",
                            mitre_id="T1071.004",
                            evidence=f"qname={qname} entropy={ent:.2f} len={len(label)}",
                            endpoint_id=endpoint_id,
                            extra={"qname": qname, "entropy": ent},
                        ))
                        break
        return findings

    def detect_low_and_slow_exfil(self, endpoint_id: str,
                                   window: Optional[List[FlowEvent]] = None) -> List[NDRFinding]:
        window = window if window is not None else list(self._events.get(endpoint_id, []))
        # Calcular bytes/min en los últimos N minutos
        if not window:
            return []
        now = window[-1].timestamp
        cutoff = now - (self.exfil_sustained_minutes * 60)
        recent = [e for e in window if e.timestamp >= cutoff and e.direction == "outbound"]
        if not recent:
            return []
        total = sum(e.size for e in recent)
        minutes = max(1, self.exfil_sustained_minutes)
        bpm = total / minutes
        if bpm > self.exfil_bpm_threshold:
            return []
        return [NDRFinding(
            severity="medium",
            category="low_slow_exfil",
            mitre_id="T1048",
            evidence=f"endpoint {endpoint_id} sustained {bpm:.0f} B/min over {minutes}min",
            endpoint_id=endpoint_id,
            extra={"bpm": bpm, "samples": len(recent), "window_minutes": minutes},
        )]

    def detect_icmp_tunnel(self, endpoint_id: str,
                           window: Optional[List[FlowEvent]] = None) -> List[NDRFinding]:
        window = window if window is not None else list(self._events.get(endpoint_id, []))
        findings: List[NDRFinding] = []
        for e in window:
            if e.proto != "icmp":
                continue
            payload = e.extra.get("payload", b"")
            if not isinstance(payload, (bytes, bytearray)):
                payload = str(payload).encode()
            if len(payload) > self.icmp_max_payload:
                ent = self._entropy(payload)
                if ent >= self.icmp_entropy_threshold:
                    findings.append(NDRFinding(
                        severity="high",
                        category="icmp_tunnel",
                        mitre_id="T1095",
                        evidence=f"icmp payload {len(payload)}B entropy={ent:.2f}",
                        endpoint_id=endpoint_id,
                        extra={"payload_size": len(payload), "entropy": ent},
                    ))
        return findings

    # ---------- Blocklist / inspection ----------

    def blocklist_add(self, ioc_type: str, value: str, source: str) -> None:
        with self._lock:
            self._blocklist.append({"type": ioc_type, "value": value, "source": source, "ts": time.time()})

    def blocklist(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._blocklist)

    def is_blocked(self, ioc_type: str, value: str) -> bool:
        with self._lock:
            return any(b["type"] == ioc_type and b["value"] == value for b in self._blocklist)

    def all_findings(self) -> List[NDRFinding]:
        with self._lock:
            return list(self._findings)

    def recent(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._recent)

    # ---------- Helpers ----------

    @staticmethod
    def _entropy(s: Any) -> float:
        if isinstance(s, (bytes, bytearray)):
            data = bytes(s)
        else:
            data = str(s).encode()
        if not data:
            return 0.0
        freq: Dict[int, int] = collections.Counter(data)
        total = len(data)
        ent = 0.0
        for c in freq.values():
            p = c / total
            ent -= p * math.log2(p)
        return ent
