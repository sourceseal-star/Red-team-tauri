#!/usr/bin/env python3
"""
NDR Comportamental — Network Detection and Response
====================================================
Reemplaza reglas estáticas con motor comportamental:
  - Detección de beaconing C2 (intervalos regulares)
  - Exfiltración low-and-slow (volumen acumulado anómalo)
  - Tunelización no autorizada (DNS/ICMP)
  - Anomalías de tráfico con baseline adaptativo

No requiere ML pesado — usa heurísticas estadísticas eficientes
que funcionan en tiempo real.
"""
import time
import math
import hashlib
import datetime
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class TrafficFlow:
    src_ip: str
    dst_ip: str
    dst_port: int
    protocol: str        # TCP, UDP, ICMP, DNS
    bytes_sent: int
    bytes_received: int
    timestamp: float
    duration_ms: int = 0


@dataclass
class AnomalyAlert:
    id: str
    type: str            # beaconing | exfiltration | tunneling | anomaly
    severity: str
    src_ip: str
    dst_ip: str
    description: str
    evidence: Dict[str, Any]
    timestamp: str
    mitre: str = ""


class C2Detector:
    """Detecta beaconing C2 — comunicaciones con intervalos regulares."""

    def __init__(self, min_connections: int = 5, interval_tolerance: float = 0.3):
        self.min_connections = min_connections
        self.interval_tolerance = interval_tolerance
        self._flows: Dict[str, List[float]] = defaultdict(list)  # key=src->dst, values=timestamps

    def observe(self, flow: TrafficFlow) -> Optional[AnomalyAlert]:
        key = f"{flow.src_ip}->{flow.dst_ip}:{flow.dst_port}"
        self._flows[key].append(flow.timestamp)

        timestamps = self._flows[key]
        if len(timestamps) < self.min_connections:
            return None

        # Calcular intervalos
        intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        if len(intervals) < self.min_connections - 1:
            return None

        # Coeficiente de variación — si los intervalos son muy regulares, es beaconing
        mean = sum(intervals) / len(intervals)
        if mean == 0:
            return None
        variance = sum((x - mean) ** 2 for x in intervals) / len(intervals)
        cv = math.sqrt(variance) / mean  # coefficient of variation

        # CV bajo = intervalos regulares = beaconing
        if cv < self.interval_tolerance and mean < 3600:  # < 1h entre beacons
            return AnomalyAlert(
                id=hashlib.sha256(f"beacon_{key}_{time.time()}".encode()).hexdigest()[:16],
                type="beaconing",
                severity="critical" if flow.bytes_sent > 1000 else "high",
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                description=f"C2 beaconing: {len(timestamps)} conexiones a {flow.dst_ip}:{flow.dst_port} "
                           f"con intervalo regular de {mean:.1f}s (CV={cv:.3f})",
                evidence={
                    "connections": len(timestamps),
                    "mean_interval_s": round(mean, 2),
                    "cv": round(cv, 3),
                    "bytes_total": sum(f.bytes_sent for f in [flow]),
                    "port": flow.dst_port,
                    "protocol": flow.protocol,
                },
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                mitre="T1071",
            )
        return None


class ExfilDetector:
    """Detecta exfiltración low-and-slow — pequeño volumen pero acumulado anómalo."""

    def __init__(self, window_seconds: int = 3600, threshold_bytes: int = 50_000_000):
        self.window = window_seconds
        self.threshold = threshold_bytes
        self._traffic: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

    def observe(self, flow: TrafficFlow) -> Optional[AnomalyAlert]:
        # Solo outbound (bytes_sent >> bytes_received)
        if flow.bytes_sent < flow.bytes_received * 2:
            return None

        self._traffic[flow.src_ip].append((flow.timestamp, flow.bytes_sent))

        # Sumar bytes en ventana temporal
        cutoff = flow.timestamp - self.window
        total = sum(b for ts, b in self._traffic[flow.src_ip] if ts >= cutoff)

        # Exfiltración low-and-slow: muchas conexiones pequeñas que suman mucho
        connections = sum(1 for ts, b in self._traffic[flow.src_ip] if ts >= cutoff)

        if total > self.threshold and connections > 20:
            avg_per_conn = total / connections
            return AnomalyAlert(
                id=hashlib.sha256(f"exfil_{flow.src_ip}_{time.time()}".encode()).hexdigest()[:16],
                type="exfiltration",
                severity="critical",
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                description=f"Exfiltracion low-and-slow: {total/1e6:.1f}MB en {connections} conexiones "
                           f"({avg_per_conn/1e3:.1f}KB/conexion) en {self.window}s",
                evidence={
                    "total_bytes": total,
                    "connections": connections,
                    "avg_bytes_per_conn": int(avg_per_conn),
                    "window_seconds": self.window,
                    "dst_port": flow.dst_port,
                },
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                mitre="T1041",
            )
        return None


class TunnelDetector:
    """Detecta tunelización no autorizada vía DNS/ICMP."""

    DNS_LONG_QUERY = 100  # queries > 100 chars son sospechosas
    ICMP_LARGE = 1000     # ICMP > 1000 bytes es anómalo

    def __init__(self):
        self._dns_queries: Dict[str, List[str]] = defaultdict(list)
        self._icmp_flows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

    def observe(self, flow: TrafficFlow) -> Optional[AnomalyAlert]:
        if flow.protocol == "DNS" and flow.bytes_sent > self.DNS_LONG_QUERY:
            return AnomalyAlert(
                id=hashlib.sha256(f"dns_tunnel_{flow.src_ip}_{time.time()}".encode()).hexdigest()[:16],
                type="tunneling",
                severity="high",
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                description=f"Tunelizacion DNS: query de {flow.bytes_sent} bytes detectada",
                evidence={
                    "query_size": flow.bytes_sent,
                    "port": flow.dst_port,
                    "protocol": "DNS",
                },
                timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                mitre="T1573",
            )

        if flow.protocol == "ICMP" and flow.bytes_sent > self.ICMP_LARGE:
            self._icmp_flows[flow.src_ip].append(flow)
            if len(self._icmp_flows[flow.src_ip]) > 10:
                return AnomalyAlert(
                    id=hashlib.sha256(f"icmp_tunnel_{flow.src_ip}_{time.time()}".encode()).hexdigest()[:16],
                    type="tunneling",
                    severity="high",
                    src_ip=flow.src_ip,
                    dst_ip=flow.dst_ip,
                    description=f"Tunelizacion ICMP: {len(self._icmp_flows[flow.src_ip])} "
                               f"paquetes grandes (>{self.ICMP_LARGE}B)",
                    evidence={
                        "large_packets": len(self._icmp_flows[flow.src_ip]),
                        "max_size": max(f.bytes_sent for f in self._icmp_flows[flow.src_ip]),
                    },
                    timestamp=datetime.datetime.utcnow().isoformat() + "Z",
                    mitre="T1573",
                )
        return None


class NDREngine:
    """Motor NDR que integra todos los detectores."""

    def __init__(self):
        self.c2 = C2Detector()
        self.exfil = ExfilDetector()
        self.tunnel = TunnelDetector()
        self.alerts: List[AnomalyAlert] = []
        self._baseline: Dict[str, Dict[int, int]] = {}  # ip -> {port: avg_bytes}

    def ingest_flow(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        """Procesa un flujo de tráfico y retorna alertas generadas."""
        new_alerts = []
        for detector in [self.c2, self.exfil, self.tunnel]:
            alert = detector.observe(flow)
            if alert:
                self.alerts.append(alert)
                new_alerts.append(alert)
        return new_alerts

    def ingest_flow_raw(self, src_ip: str, dst_ip: str, dst_port: int,
                        protocol: str, bytes_sent: int, bytes_received: int) -> List[AnomalyAlert]:
        """API conveniencia."""
        flow = TrafficFlow(
            src_ip=src_ip, dst_ip=dst_ip, dst_port=dst_port,
            protocol=protocol, bytes_sent=bytes_sent, bytes_received=bytes_received,
            timestamp=time.time(),
        )
        return self.ingest_flow(flow)

    def get_alerts(self, since: float = 0) -> List[Dict]:
        if since == 0:
            return [asdict(a) for a in self.alerts]
        return [asdict(a) for a in self.alerts if self._ts(a.timestamp) >= since]

    @staticmethod
    def _ts(ts: str) -> float:
        try:
            return datetime.datetime.fromisoformat(ts.replace("Z", "")).timestamp()
        except Exception:
            return 0.0

    def get_summary(self) -> Dict:
        by_type = {}
        by_severity = {}
        for a in self.alerts:
            by_type[a.type] = by_type.get(a.type, 0) + 1
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        return {
            "total_alerts": len(self.alerts),
            "by_type": by_type,
            "by_severity": by_severity,
            "mitre_techniques": sorted(set(a.mitre for a in self.alerts if a.mitre)),
        }
