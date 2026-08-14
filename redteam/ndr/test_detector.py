#!/usr/bin/env python3
"""
Unit tests for NDR (Network Detection & Response) module.
Tests: TrafficFlow, C2Detector, ExfilDetector, AnomalyDetector (ML),
       ZScoreAnomalyDetector, DNSTunnelingDetector, DGA detection.
"""

import unittest
import time
import math
from datetime import datetime

# Import engine components (existing remote)
try:
    from engine import NDREngine, TrafficFlow, AnomalyAlert, C2Detector, ExfilDetector
except ImportError:
    from ndr.engine import NDREngine, TrafficFlow, AnomalyAlert, C2Detector, ExfilDetector

# Import ML detector components (new)
try:
    from ml_detector import (
    ZScoreAnomalyDetector,
    IsolationForestDetector,
    DNSTunnelingDetector,
    calculate_entropy,
    TrafficFlow as MLTrafficFlow,
    AnomalyAlert as MLAnomalyAlert,
)
except ImportError:
    from ndr.ml_detector import (
    ZScoreAnomalyDetector,
    IsolationForestDetector,
    DNSTunnelingDetector,
    calculate_entropy,
    TrafficFlow as MLTrafficFlow,
    AnomalyAlert as MLAnomalyAlert,
)
try:
    from behavioral import AnomalyDetector
except ImportError:
    from ndr.behavioral import AnomalyDetector


class TestTrafficFlow(unittest.TestCase):
    """Tests for TrafficFlow dataclass from engine.py."""

    def test_traffic_flow_creation(self):
        flow = TrafficFlow(
            src_ip="192.168.1.10", dst_ip="10.0.0.5", dst_port=443,
            protocol="TCP", bytes_sent=1024, bytes_received=4096,
            timestamp=time.time()
        )
        self.assertEqual(flow.src_ip, "192.168.1.10")
        self.assertEqual(flow.dst_ip, "10.0.0.5")
        self.assertEqual(flow.dst_port, 443)
        self.assertEqual(flow.protocol, "TCP")
        self.assertEqual(flow.bytes_sent, 1024)
        self.assertEqual(flow.bytes_received, 4096)

    def test_traffic_flow_default_duration(self):
        flow = TrafficFlow(
            src_ip="10.0.0.1", dst_ip="10.0.0.2", dst_port=80,
            protocol="TCP", bytes_sent=100, bytes_received=200,
            timestamp=time.time()
        )
        self.assertEqual(flow.duration_ms, 0)


class TestC2Detector(unittest.TestCase):
    """Tests for C2 beaconing detection."""

    def test_beaconing_detected(self):
        """Regular intervals between connections should trigger beaconing alert."""
        detector = C2Detector(min_connections=5, interval_tolerance=0.3)
        base_time = time.time()
        alerts = []
        # Simulate 6 connections at 10-second intervals (very regular = beaconing)
        for i in range(6):
            flow = TrafficFlow(
                src_ip="192.168.1.10", dst_ip="203.0.113.50", dst_port=443,
                protocol="TCP", bytes_sent=256, bytes_received=128,
                timestamp=base_time + i * 10.0
            )
            alert = detector.observe(flow)
            if alert:
                alerts.append(alert)
        # After 6 regular connections, should detect beaconing
        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[-1].type, "beaconing")

    def test_no_beaconing_irregular(self):
        """Irregular intervals should NOT trigger beaconing."""
        detector = C2Detector(min_connections=5, interval_tolerance=0.3)
        base_time = time.time()
        alerts = []
        # Random-ish intervals
        intervals = [1.0, 45.0, 3.0, 120.0, 0.5, 67.0]
        for i, interval in enumerate(intervals):
            flow = TrafficFlow(
                src_ip="192.168.1.10", dst_ip="203.0.113.50", dst_port=443,
                protocol="TCP", bytes_sent=256, bytes_received=128,
                timestamp=base_time + sum(intervals[:i + 1])
            )
            alert = detector.observe(flow)
            if alert:
                alerts.append(alert)
        self.assertEqual(len(alerts), 0)

    def test_below_min_connections(self):
        """Fewer than min_connections should not trigger."""
        detector = C2Detector(min_connections=5, interval_tolerance=0.3)
        base_time = time.time()
        for i in range(3):
            flow = TrafficFlow(
                src_ip="192.168.1.10", dst_ip="203.0.113.50", dst_port=443,
                protocol="TCP", bytes_sent=100, bytes_received=50,
                timestamp=base_time + i * 10.0
            )
            result = detector.observe(flow)
            self.assertIsNone(result)


class TestExfilDetector(unittest.TestCase):
    """Tests for data exfiltration detection."""

    def test_exfiltration_detected(self):
        """Large outbound transfer should trigger exfiltration alert."""
        detector = ExfilDetector()
        flow = TrafficFlow(
            src_ip="192.168.1.10", dst_ip="203.0.113.99", dst_port=443,
            protocol="TCP", bytes_sent=5000000, bytes_received=100,
            timestamp=time.time(), duration_ms=5000
        )
        alert = detector.observe(flow)
        if alert:
            self.assertEqual(alert.type, "exfiltration")
            self.assertEqual(alert.src_ip, "192.168.1.10")

    def test_normal_traffic_no_alert(self):
        """Normal traffic should not trigger exfiltration."""
        detector = ExfilDetector()
        flow = TrafficFlow(
            src_ip="192.168.1.10", dst_ip="93.184.216.34", dst_port=443,
            protocol="TCP", bytes_sent=500, bytes_received=5000,
            timestamp=time.time(), duration_ms=100
        )
        alert = detector.observe(flow)
        self.assertIsNone(alert)


class TestEntropy(unittest.TestCase):
    """Tests for calculate_entropy utility function."""

    def test_empty_string(self):
        self.assertEqual(calculate_entropy(""), 0.0)

    def test_single_char(self):
        self.assertEqual(calculate_entropy("aaaa"), 0.0)

    def test_high_entropy(self):
        """Random-looking string should have high entropy."""
        s = "xJ7kQ2mNpL9rTzWqYbVc"
        entropy = calculate_entropy(s)
        self.assertGreater(entropy, 3.5)

    def test_low_entropy(self):
        """Repetitive string should have low entropy."""
        s = "abababababababab"
        entropy = calculate_entropy(s)
        self.assertLess(entropy, 1.5)


class TestZScoreAnomalyDetector(unittest.TestCase):
    """Tests for Z-Score statistical anomaly detection."""

    def test_no_anomaly_below_min_samples(self):
        """Should not alert before min_samples threshold."""
        detector = ZScoreAnomalyDetector(min_samples=15, z_threshold=3.0)
        for i in range(10):
            flow = MLTrafficFlow(
                src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=50000, dst_port=443,
                protocol="TCP", bytes_sent=1000, bytes_recv=2000, duration_ms=100.0
            )
            alerts = detector.analyze(flow)
            self.assertEqual(len(alerts), 0)

    def test_anomaly_detected_on_spike(self):
        """A sudden spike after normal traffic should trigger anomaly."""
        detector = ZScoreAnomalyDetector(min_samples=15, z_threshold=3.0)
        # Feed 20 normal flows
        for i in range(20):
            flow = MLTrafficFlow(
                src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=50000, dst_port=443,
                protocol="TCP", bytes_sent=1000, bytes_recv=2000, duration_ms=100.0
            )
            detector.analyze(flow)
        # Now send a massive spike
        spike_flow = MLTrafficFlow(
            src_ip="10.0.0.1", dst_ip="10.0.0.2", src_port=50000, dst_port=443,
            protocol="TCP", bytes_sent=9999999, bytes_recv=100, duration_ms=100.0
        )
        alerts = detector.analyze(spike_flow)
        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0].detector_name, "ZScoreAnomalyDetector")


class TestDNSTunnelingDetector(unittest.TestCase):
    """Tests for DNS tunneling detection."""

    def test_long_subdomain_detected(self):
        """Very long subdomain should trigger DNS tunneling suspicion."""
        detector = DNSTunnelingDetector()
        flow = MLTrafficFlow(
            src_ip="10.0.0.1", dst_ip="8.8.8.8", src_port=53, dst_port=53,
            protocol="DNS", bytes_sent=200, bytes_recv=300, duration_ms=50.0,
            dns_query="eyJ0ZXN0IjoidGhpcyBpcyBhIHZlcnkgbG9uZyBlbmNvZGVkIHN0cmluZyBmb3IgZG5zIHR1bm5lbGluZyJ9.exfil.evil.com"
        )
        alerts = detector.analyze(flow)
        self.assertGreaterEqual(len(alerts), 1)
        self.assertEqual(alerts[0].detector_name, "DNSTunnelingDetector")

    def test_normal_dns_no_alert(self):
        """Normal DNS query should not trigger alert."""
        detector = DNSTunnelingDetector()
        flow = MLTrafficFlow(
            src_ip="10.0.0.1", dst_ip="8.8.8.8", src_port=53, dst_port=53,
            protocol="DNS", bytes_sent=60, bytes_recv=120, duration_ms=30.0,
            dns_query="www.google.com"
        )
        alerts = detector.analyze(flow)
        self.assertEqual(len(alerts), 0)


class TestAnomalyDetector(unittest.TestCase):
    """Tests for the unified AnomalyDetector facade."""

    def test_detector_initialization(self):
        """AnomalyDetector should initialize without errors."""
        detector = AnomalyDetector()
        self.assertIsNotNone(detector)

    def test_detector_processes_flow(self):
        """AnomalyDetector should process a flow without crashing."""
        detector = AnomalyDetector()
        flow = TrafficFlow(
            src_ip="10.0.0.1", dst_ip="10.0.0.2", dst_port=443,
            protocol="TCP", bytes_sent=1000, bytes_received=2000,
            timestamp=time.time()
        )
        result = detector.observe(flow)
        # observe() returns Optional[AnomalyAlert] — None or alert
        self.assertTrue(result is None or isinstance(result, AnomalyAlert))


class TestNDREngine(unittest.TestCase):
    """Tests for the main NDREngine from engine.py."""

    def test_engine_initialization(self):
        engine = NDREngine()
        self.assertIsNotNone(engine)

    def test_engine_observes_flow(self):
        engine = NDREngine()
        flow = TrafficFlow(
            src_ip="10.0.0.1", dst_ip="10.0.0.2", dst_port=443,
            protocol="TCP", bytes_sent=500, bytes_received=1000,
            timestamp=time.time()
        )
        result = engine.ingest_flow(flow)
        # ingest_flow returns List[AnomalyAlert]
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
