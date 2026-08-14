#!/usr/bin/env python3
"""
Unit tests for TIP (Threat Intelligence Platform) module.
Tests: IoC management, ThreatIntelPlatform blocklists, StixExporter STIX 2.1
       serialization, MISP event export, TAXII client local fallback.
"""

import unittest
import json
import os
import tempfile
from datetime import datetime

# Import TIP platform
from tip.platform import IoC, ThreatIntelPlatform

# Import STIX exporter (builds JSON manually — no stix2 dependency needed)
from tip.stix_exporter import StixExporter

# Import TAXII client
from tip.taxii_client import TaxiiClient


class TestIoC(unittest.TestCase):
    """Tests for IoC dataclass."""

    def test_ioc_creation(self):
        ioc = IoC(
            type="ip", value="203.0.113.50", source="ndr",
            confidence=0.95, tags=["c2", "beaconing"]
        )
        self.assertEqual(ioc.type, "ip")
        self.assertEqual(ioc.value, "203.0.113.50")
        self.assertEqual(ioc.confidence, 0.95)
        self.assertIn("c2", ioc.tags)

    def test_ioc_defaults(self):
        ioc = IoC(type="domain", value="evil.com", source="deception", confidence=0.8)
        self.assertIsInstance(ioc.first_seen, datetime)
        self.assertEqual(ioc.tags, [])


class TestThreatIntelPlatform(unittest.TestCase):
    """Tests for ThreatIntelPlatform IoC management."""

    def test_initialization(self):
        tip = ThreatIntelPlatform()
        self.assertEqual(len(tip.iocs), 0)
        self.assertEqual(len(tip.blocklist), 0)

    def test_add_ioc(self):
        tip = ThreatIntelPlatform()
        ioc = IoC(type="ip", value="198.51.100.1", source="ndr", confidence=0.9)
        tip.add_ioc(ioc)
        self.assertEqual(len(tip.iocs), 1)
        # High confidence should be added to blocklist
        self.assertIn("198.51.100.1", tip.blocklist)

    def test_low_confidence_not_blocked(self):
        tip = ThreatIntelPlatform()
        ioc = IoC(type="ip", value="198.51.100.2", source="ndr", confidence=0.3)
        tip.add_ioc(ioc)
        self.assertNotIn("198.51.100.2", tip.blocklist)

    def test_blocklist_threshold(self):
        """Confidence >= 0.7 should go to blocklist."""
        tip = ThreatIntelPlatform()
        ioc = IoC(type="domain", value="suspicious.com", source="probe", confidence=0.7)
        tip.add_ioc(ioc)
        self.assertIn("suspicious.com", tip.get_blocklist())

    def test_get_blocklist_sorted(self):
        tip = ThreatIntelPlatform()
        tip.add_ioc(IoC(type="ip", value="10.0.0.2", source="xdr", confidence=0.9))
        tip.add_ioc(IoC(type="ip", value="10.0.0.1", source="xdr", confidence=0.9))
        blocklist = tip.get_blocklist()
        self.assertEqual(blocklist, sorted(blocklist))

    def test_get_summary(self):
        tip = ThreatIntelPlatform()
        tip.add_ioc(IoC(type="ip", value="1.1.1.1", source="ndr", confidence=0.9))
        tip.add_ioc(IoC(type="domain", value="evil.com", source="deception", confidence=0.8))
        tip.add_ioc(IoC(type="ip", value="2.2.2.2", source="ndr", confidence=0.5))
        summary = tip.get_summary()
        self.assertEqual(summary["total_iocs"], 3)
        self.assertEqual(summary["blocklist_size"], 2)
        self.assertEqual(summary["by_type"]["ip"], 2)
        self.assertEqual(summary["by_type"]["domain"], 1)
        self.assertEqual(summary["by_source"]["ndr"], 2)
        self.assertEqual(summary["by_source"]["deception"], 1)


class TestStixExporter(unittest.TestCase):
    """Tests for StixExporter — STIX 2.1 bundle creation."""

    def test_initialization(self):
        exporter = StixExporter()
        self.assertEqual(exporter.bundle["type"], "bundle")
        self.assertEqual(exporter.bundle["spec_version"], "2.1")
        self.assertEqual(exporter.bundle["objects"], [])

    def test_add_indicator(self):
        exporter = StixExporter()
        ioc = IoC(type="ip", value="203.0.113.50", source="ndr", confidence=0.9)
        indicator = exporter.add_indicator(ioc)
        self.assertEqual(indicator["type"], "indicator")
        self.assertIn("ipv4-addr:value", indicator["pattern"])
        self.assertIn("203.0.113.50", indicator["pattern"])
        self.assertEqual(indicator["confidence"], 90)

    def test_add_observable(self):
        exporter = StixExporter()
        ioc = IoC(type="domain", value="evil.example.com", source="deception", confidence=0.8)
        obs = exporter.add_observable(ioc)
        self.assertEqual(obs["type"], "domain-name")
        self.assertEqual(obs["value"], "evil.example.com")

    def test_export_iocs(self):
        exporter = StixExporter()
        iocs = [
            IoC(type="ip", value="198.51.100.1", source="ndr", confidence=0.9, tags=["c2"]),
            IoC(type="domain", value="malware.evil.com", source="soar", confidence=0.95),
            IoC(type="hash", value="a" * 64, source="probe", confidence=0.7),
            IoC(type="url", value="http://evil.com/payload", source="deception", confidence=0.85),
        ]
        bundle = exporter.export_iocs(iocs)
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["spec_version"], "2.1")
        # Should have indicators + observables + report
        self.assertGreater(len(bundle["objects"]), len(iocs))

    def test_validate_bundle(self):
        exporter = StixExporter()
        iocs = [
            IoC(type="ip", value="1.2.3.4", source="ndr", confidence=0.9),
        ]
        exporter.export_iocs(iocs)
        self.assertTrue(exporter.validate())

    def test_to_json(self):
        exporter = StixExporter()
        iocs = [IoC(type="ip", value="1.2.3.4", source="ndr", confidence=0.9)]
        exporter.export_iocs(iocs)
        json_str = exporter.to_json()
        data = json.loads(json_str)
        self.assertEqual(data["type"], "bundle")

    def test_save_to_file(self):
        exporter = StixExporter()
        iocs = [IoC(type="ip", value="1.2.3.4", source="ndr", confidence=0.9)]
        exporter.export_iocs(iocs)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        exporter.save(path)
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data["type"], "bundle")
        os.unlink(path)

    def test_labels_by_source(self):
        """Labels should vary by IoC source."""
        exporter = StixExporter()
        # SOAR source → malicious-activity
        ioc_soar = IoC(type="ip", value="1.1.1.1", source="soar", confidence=0.9)
        ind_soar = exporter.add_indicator(ioc_soar)
        self.assertIn("malicious-activity", ind_soar["labels"])

        # Probe source → anomalous-activity
        exporter2 = StixExporter()
        ioc_probe = IoC(type="ip", value="2.2.2.2", source="probe", confidence=0.9)
        ind_probe = exporter2.add_indicator(ioc_probe)
        self.assertIn("anomalous-activity", ind_probe["labels"])

    def test_threat_report(self):
        """Export should include a threat report object."""
        exporter = StixExporter()
        iocs = [
            IoC(type="ip", value="1.1.1.1", source="ndr", confidence=0.9),
            IoC(type="domain", value="evil.com", source="soar", confidence=0.95),
        ]
        bundle = exporter.export_iocs(iocs)
        reports = [o for o in bundle["objects"] if o["type"] == "report"]
        self.assertEqual(len(reports), 1)
        self.assertIn("SourceSeal", reports[0]["name"])


class TestStixExporterMISP(unittest.TestCase):
    """Tests for MISP event export."""

    def test_to_misp_event(self):
        exporter = StixExporter()
        iocs = [
            IoC(type="ip", value="203.0.113.1", source="ndr", confidence=0.95),
            IoC(type="domain", value="evil.com", source="soar", confidence=0.85),
        ]
        misp = exporter.to_misp_event(iocs, event_info="Red Team Findings")
        self.assertIn("Event", misp)
        self.assertEqual(misp["Event"]["info"], "Red Team Findings")
        self.assertGreater(len(misp["Event"]["Attribute"]), 0)
        self.assertEqual(misp["Event"]["Attribute"][0]["value"], "203.0.113.1")


class TestTaxiiClient(unittest.TestCase):
    """Tests for TAXII 2.1 client."""

    def test_initialization(self):
        client = TaxiiClient(server_url="https://taxii.example.com", api_key="test-key", collection_id="col-1")
        self.assertEqual(client.server_url, "https://taxii.example.com")
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.collection_id, "col-1")

    def test_initialization_empty(self):
        client = TaxiiClient()
        self.assertEqual(client.server_url, "")

    def test_local_fallback_export(self):
        """Without a server, push should fall back to local file export."""
        client = TaxiiClient()
        bundle = {"type": "bundle", "spec_version": "2.1", "objects": []}
        result = client.push_to_collection(bundle)
        self.assertEqual(result["status"], "exported_local")
        # Clean up exported file if it was created
        if "file" in result and os.path.exists(result["file"]):
            os.unlink(result["file"])

    def test_discover_collections_no_server(self):
        """Without server, discover should return empty list."""
        client = TaxiiClient()
        collections = client.discover_collections()
        self.assertEqual(collections, [])


if __name__ == "__main__":
    unittest.main()
