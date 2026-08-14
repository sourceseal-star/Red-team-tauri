#!/usr/bin/env python3
"""
NDR Behavioral Detection Module
================================
Advanced behavioral analytics including:
- BeaconingDetector (C2 callback pattern detection via Coefficient of Variation)
- SlowExfiltrationDetector (Low & slow exfiltration + DNS tunneling)
- AnomalyDetector (Statistical baseline & Z-score analysis)
"""
import time
import math
import hashlib
import datetime
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

try:
    from ndr.engine import TrafficFlow, AnomalyAlert
except ImportError:
    from .engine import TrafficFlow, AnomalyAlert


class BeaconingDetector:
    """Detects C2 beaconing pattern based on connection interval regularity (low jitter/CV)."""

    def __init__(self, min_connections: int = 5, window_seconds: int = 600, interval_tolerance: float = 0.3):
        self.min_connections = min_connections
        self.window_seconds = window_seconds
        self.interval_tolerance = interval_tolerance
        # key: (src_ip, dst_ip), value: list of timestamps
        self._history: Dict[Tuple[str, str], List[float]] = defaultdict(list)

    def observe(self, flow: TrafficFlow) -> Optional[AnomalyAlert]:
        key = (flow.src_ip, flow.dst_ip)
        self._history[key].append(flow.timestamp)

        # Slide window: keep only timestamps within the last `window_seconds` (10 mins)
        cutoff = flow.timestamp - self.window_seconds
        self._history[key] = sorted([t for t in self._history[key] if t >= cutoff])

        timestamps = self._history[key]
        if len(timestamps) < self.min_connections:
            return None

        # Compute intervals
        intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
        if len(intervals) < self.min_connections - 1:
            return None

        # Interval statistics
        n = len(intervals)
        mean = sum(intervals) / n
        if mean == 0:
            return None

        variance = sum((x - mean) ** 2 for x in intervals) / n
        std = math.sqrt(variance)
        cv = std / mean  # Coefficient of Variation

        # Jitter: Average absolute difference of consecutive intervals
        if len(intervals) > 1:
            jitter = sum(abs(intervals[i] - intervals[i-1]) for i in range(1, len(intervals))) / (len(intervals) - 1)
        else:
            jitter = 0.0

        # CV < 0.3 indicates beaconing
        if cv < self.interval_tolerance:
            # Determine severity: critical if CV < 0.1, high if < 0.2, medium if < 0.3
            if cv < 0.1:
                severity = "critical"
            elif cv < 0.2:
                severity = "high"
            else:
                severity = "medium"

            alert_id = hashlib.sha256(f"beacon_{flow.src_ip}_{flow.dst_ip}_{flow.timestamp}".encode()).hexdigest()[:16]
            description = (
                f"C2 beaconing detected: {len(timestamps)} connections to {flow.dst_ip} "
                f"within {self.window_seconds/60:.1f} minutes with low jitter (CV={cv:.3f}, mean={mean:.1f}s)"
            )

            return AnomalyAlert(
                id=alert_id,
                type="beaconing",
                severity=severity,
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                description=description,
                evidence={
                    "connection_count": len(timestamps),
                    "mean_interval_s": round(mean, 3),
                    "std_interval_s": round(std, 3),
                    "cv": round(cv, 3),
                    "jitter": round(jitter, 3),
                    "dst_port": flow.dst_port,
                    "protocol": flow.protocol,
                    "mitre_techniques": ["T1071.001", "T1573.001"]
                },
                timestamp=datetime.datetime.fromtimestamp(flow.timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                mitre="T1071.001"
            )

        return None


class SlowExfiltrationDetector:
    """Detects low and slow data exfiltration and DNS tunneling."""

    def __init__(self, window_seconds: int = 3600, threshold_bytes: int = 10_000_000, dns_window_seconds: int = 300):
        self.window_seconds = window_seconds
        self.threshold_bytes = threshold_bytes
        self.dns_window_seconds = dns_window_seconds
        
        # Track flows for exfiltration: key=(src_ip, dst_ip), val=list of (timestamp, bytes_sent, bytes_received)
        self._history: Dict[Tuple[str, str], List[Tuple[float, int, int]]] = defaultdict(list)
        
        # Track DNS queries: key=(src_ip, domain), val=list of timestamps
        self._dns_history: Dict[Tuple[str, str], List[float]] = defaultdict(list)

    def observe(self, flow: TrafficFlow) -> Optional[AnomalyAlert]:
        key = (flow.src_ip, flow.dst_ip)
        
        # --- 1. Cumulative Bytes Exfiltration ---
        self._history[key].append((flow.timestamp, flow.bytes_sent, flow.bytes_received))
        
        # Prune older than 1 hour (window_seconds)
        cutoff = flow.timestamp - self.window_seconds
        self._history[key] = [item for item in self._history[key] if item[0] >= cutoff]
        
        total_sent = sum(item[1] for item in self._history[key])
        total_received = sum(item[2] for item in self._history[key])
        
        # Check if ratio sent:received > 10:1
        ratio = total_sent / total_received if total_received > 0 else float("inf")
        
        is_exfil = False
        evidence = {}
        description = ""
        
        # Trigger conditions:
        # - total bytes sent > 10MB to a single destination over 1 hour
        # - OR ratio sent:received > 10:1 (with a minimum of 1MB sent to prevent trivial noise)
        if total_sent > self.threshold_bytes:
            is_exfil = True
            description = (
                f"Slow exfiltration detected: sent {total_sent / (1024*1024):.2f}MB to {flow.dst_ip} "
                f"over {self.window_seconds/3600:.1f} hour(s)."
            )
            evidence = {
                "metric": "cumulative_bytes_sent",
                "total_bytes_sent": total_sent,
                "total_bytes_received": total_received,
                "ratio_sent_received": round(ratio, 2) if ratio != float("inf") else "inf",
                "time_window_seconds": self.window_seconds,
            }
        elif ratio > 10.0 and total_sent > 1_000_000:  # Minimum 1MB sent for ratio triggers to ensure high confidence
            is_exfil = True
            description = (
                f"Slow exfiltration detected: high sent-to-received ratio ({ratio:.1f}:1, "
                f"sent {total_sent / (1024*1024):.2f}MB) to {flow.dst_ip} within 1 hour."
            )
            evidence = {
                "metric": "high_ratio_sent_received",
                "total_bytes_sent": total_sent,
                "total_bytes_received": total_received,
                "ratio_sent_received": round(ratio, 2),
                "time_window_seconds": self.window_seconds,
            }

        if is_exfil:
            alert_id = hashlib.sha256(f"exfil_{flow.src_ip}_{flow.dst_ip}_{flow.timestamp}".encode()).hexdigest()[:16]
            return AnomalyAlert(
                id=alert_id,
                type="exfiltration",
                severity="critical" if total_sent > 50_000_000 else "high",
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                description=description,
                evidence={
                    **evidence,
                    "dst_port": flow.dst_port,
                    "protocol": flow.protocol,
                    "mitre_techniques": ["T1041", "T1048.003"]
                },
                timestamp=datetime.datetime.fromtimestamp(flow.timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                mitre="T1041"
            )

        # --- 2. DNS Tunneling Detection ---
        if flow.protocol == "DNS" or flow.dst_port == 53:
            domain = getattr(flow, "domain", None) or getattr(flow, "query", None)
            
            if domain:
                parts = domain.split(".")
                has_long_subdomain = False
                long_part = ""
                
                # Check first part (e.g. extremelylonglabel.example.com)
                if len(parts) > 1 and len(parts[0]) > 50:
                    has_long_subdomain = True
                    long_part = parts[0]
                # Check other subdomains
                elif len(parts) >= 3:
                    subdomains = parts[:-2]
                    for sub in subdomains:
                        if len(sub) > 50:
                            has_long_subdomain = True
                            long_part = sub
                            break
                
                if has_long_subdomain:
                    alert_id = hashlib.sha256(f"dns_tunnel_long_{flow.src_ip}_{flow.dst_ip}_{flow.timestamp}".encode()).hexdigest()[:16]
                    return AnomalyAlert(
                        id=alert_id,
                        type="tunneling",
                        severity="high",
                        src_ip=flow.src_ip,
                        dst_ip=flow.dst_ip,
                        description=f"DNS tunneling detected: query with long subdomain (>50 chars) '{long_part[:20]}...' to {domain}",
                        evidence={
                            "domain": domain,
                            "subdomain_part": long_part,
                            "subdomain_length": len(long_part),
                            "dst_port": flow.dst_port,
                            "protocol": "DNS",
                            "mitre_techniques": ["T1048.003"]
                        },
                        timestamp=datetime.datetime.fromtimestamp(flow.timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        mitre="T1048.003"
                    )

                # Track query counts for same domain in 5 minutes
                dns_key = (flow.src_ip, domain)
                self._dns_history[dns_key].append(flow.timestamp)
                
                # Prune older than 5 minutes
                dns_cutoff = flow.timestamp - self.dns_window_seconds
                self._dns_history[dns_key] = [t for t in self._dns_history[dns_key] if t >= dns_cutoff]
                
                query_count = len(self._dns_history[dns_key])
                if query_count > 50:
                    alert_id = hashlib.sha256(f"dns_tunnel_count_{flow.src_ip}_{domain}_{flow.timestamp}".encode()).hexdigest()[:16]
                    return AnomalyAlert(
                        id=alert_id,
                        type="tunneling",
                        severity="high",
                        src_ip=flow.src_ip,
                        dst_ip=flow.dst_ip,
                        description=f"DNS tunneling detected: >50 DNS queries ({query_count}) to domain '{domain}' in 5 minutes.",
                        evidence={
                            "domain": domain,
                            "query_count_5m": query_count,
                            "dst_port": flow.dst_port,
                            "protocol": "DNS",
                            "mitre_techniques": ["T1048.003"]
                        },
                        timestamp=datetime.datetime.fromtimestamp(flow.timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        mitre="T1048.003"
                    )

        return None


class AnomalyDetector:
    """Learns normal traffic baseline patterns and uses Z-score to spot packet/frequency/ratio anomalies."""

    def __init__(self, min_baseline_size: int = 15, max_history_size: int = 1000):
        self.min_baseline_size = min_baseline_size
        self.max_history_size = max_history_size
        
        # Track baseline parameters per src_ip
        # Metrics: packet_sizes, byte_ratios, connection_intervals
        self._history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: {
            "packet_sizes": [],
            "byte_ratios": [],
            "connection_intervals": []
        })
        self._last_timestamp: Dict[str, float] = {}

    def observe(self, flow: TrafficFlow) -> Optional[AnomalyAlert]:
        src = flow.src_ip
        
        # Current flow metrics
        packet_size = float(flow.bytes_sent + flow.bytes_received)
        byte_ratio = float(flow.bytes_sent) / (float(flow.bytes_received) + 1.0)
        
        interval = 0.0
        if src in self._last_timestamp:
            interval = flow.timestamp - self._last_timestamp[src]
        self._last_timestamp[src] = flow.timestamp
        
        hist = self._history[src]
        alerts_triggered = []
        
        def check_and_update(metric_name: str, current_value: float) -> Optional[Tuple[float, float, float]]:
            values = hist[metric_name]
            
            # If not enough baseline data, just learn
            if len(values) < self.min_baseline_size:
                values.append(current_value)
                return None
                
            # Calculate baseline statistics
            n = len(values)
            mean = sum(values) / n
            variance = sum((x - mean) ** 2 for x in values) / n
            std = math.sqrt(variance)
            
            # Update baseline sliding window
            values.append(current_value)
            if len(values) > self.max_history_size:
                values.pop(0)
                
            if std > 0:
                z = abs(current_value - mean) / std
                return z, mean, std
            return None

        # Check packet size
        res_size = check_and_update("packet_sizes", packet_size)
        if res_size and res_size[0] > 3.0:
            alerts_triggered.append(("packet_size", packet_size, res_size[1], res_size[2], res_size[0]))
            
        # Check byte ratio
        res_ratio = check_and_update("byte_ratios", byte_ratio)
        if res_ratio and res_ratio[0] > 3.0:
            alerts_triggered.append(("byte_ratio", byte_ratio, res_ratio[1], res_ratio[2], res_ratio[0]))
            
        # Check connection intervals
        if interval > 0.0:
            res_interval = check_and_update("connection_intervals", interval)
            if res_interval and res_interval[0] > 3.0:
                alerts_triggered.append(("connection_interval", interval, res_interval[1], res_interval[2], res_interval[0]))
        else:
            # Record interval but don't check for first connection
            hist["connection_intervals"].append(0.0)
            if len(hist["connection_intervals"]) > self.max_history_size:
                hist["connection_intervals"].pop(0)

        if alerts_triggered:
            # Select the anomaly with the highest Z-score
            alerts_triggered.sort(key=lambda x: x[4], reverse=True)
            name, current, mean, std, z_score = alerts_triggered[0]
            
            alert_id = hashlib.sha256(f"anomaly_{src}_{flow.timestamp}".encode()).hexdigest()[:16]
            description = (
                f"Statistical anomaly on host '{src}' for metric '{name}': "
                f"value={current:.2f}, baseline mean={mean:.2f}, std={std:.2f} (Z-score={z_score:.2f} > 3)"
            )
            
            evidence = {
                "anomalous_metric": name,
                "current_value": round(current, 3),
                "baseline_mean": round(mean, 3),
                "baseline_std": round(std, 3),
                "z_score": round(z_score, 3),
                "all_alerts": {
                    n: {"current": round(c, 3), "mean": round(m, 3), "std": round(s, 3), "z": round(z, 3)}
                    for n, c, m, s, z in alerts_triggered
                },
                "mitre_techniques": ["T1071", "T1041"]
            }
            
            return AnomalyAlert(
                id=alert_id,
                type="anomaly",
                severity="high" if z_score > 5.0 else "medium",
                src_ip=flow.src_ip,
                dst_ip=flow.dst_ip,
                description=description,
                evidence=evidence,
                timestamp=datetime.datetime.fromtimestamp(flow.timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                mitre="T1071"
            )

        return None


try:
    from ndr.engine import NDREngine
except ImportError:
    from .engine import NDREngine

class BehavioralNDREngine(NDREngine):
    """Enhanced NDR Engine integrating advanced behavioral detectors."""

    def __init__(self):
        super().__init__()
        self.beaconing_detector = BeaconingDetector()
        self.slow_exfil_detector = SlowExfiltrationDetector()
        self.anomaly_detector = AnomalyDetector()

    def ingest_flow(self, flow: TrafficFlow) -> List[AnomalyAlert]:
        # Process flow through default parent engine detectors
        alerts = super().ingest_flow(flow)

        # Process flow through advanced behavioral detectors
        for detector in [self.beaconing_detector, self.slow_exfil_detector, self.anomaly_detector]:
            try:
                alert = detector.observe(flow)
                if alert:
                    self.alerts.append(alert)
                    alerts.append(alert)
            except Exception:
                # Proper error handling to avoid engine crash on bad data
                pass
        return alerts
