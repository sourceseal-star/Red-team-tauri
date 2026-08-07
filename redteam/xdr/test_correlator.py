# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - XDR Unit Tests
Pruebas unitarias para validar el motor de correlacion, Cyber Kill Chain,
visualizaciones y evaluacion de la superficie de ataque.
"""

import unittest
from datetime import datetime, timedelta
import json

from xdr.correlator import XDREvent, Incident, MITRE_TECHNIQUES, XDRCorrelator
from xdr.kill_chain import KillChainPhase, AttackPath, KillChainAnalyzer, KillChainVisualizer
from xdr.attack_surface import AttackSurface, AttackSurfaceMapper


def _ev(eid, source, severity, title, ts, technique):
    """Helper: crea un XDREvent con la firma correcta del dataclass."""
    return XDREvent(
        id=eid,
        source=source,
        severity=severity,
        title=title,
        description=f"{title} detectado desde {source}",
        timestamp=ts.isoformat() if isinstance(ts, datetime) else str(ts),
        mitre_technique=technique,
    )


def _inc(iid, title, severity, events, techniques, created_at):
    """Helper: crea un Incident con la firma correcta del dataclass."""
    return Incident(
        id=iid,
        title=title,
        severity=severity,
        status="OPEN",
        events=[{"id": e.id, "title": e.title, "source": e.source, "mitre_technique": e.mitre_technique} for e in events],
        mitre_techniques=techniques,
        mitre_tactics=[],
        src_ips=[],
        affected_assets=[],
        recommended_actions=[],
        created_at=created_at if isinstance(created_at, str) else str(created_at),
    )


class TestXDRCorrelatorAndKillChain(unittest.TestCase):

    def setUp(self):
        self.analyzer = KillChainAnalyzer()
        self.now = datetime.now()

    def test_event_and_incident_creation(self):
        """Prueba que los eventos e incidentes se creen e inicialicen con datos correctos."""
        event = _ev("EV-TEST-01", "test_source", "HIGH", "test_event", self.now, "T1595")
        self.assertEqual(event.id, "EV-TEST-01")
        self.assertEqual(event.mitre_technique, "T1595")

        incident = _inc(
            "INC-TEST-01", "Test Incident", "MEDIUM",
            [event], ["T1595"], self.now.isoformat()
        )
        self.assertEqual(incident.id, "INC-TEST-01")
        self.assertEqual(len(incident.events), 1)
        self.assertEqual(incident.severity, "MEDIUM")

    def test_kill_chain_analyzer(self):
        """Valida que el analizador reconstruya correctamente las fases a partir de tecnicas MITRE."""
        ev1 = _ev("EV1", "firewall", "MEDIUM", "recon", self.now - timedelta(minutes=10), "T1595")
        ev2 = _ev("EV2", "email", "HIGH", "phish", self.now - timedelta(minutes=5), "T1566")
        ev3 = _ev("EV3", "endpoint", "CRITICAL", "powershell", self.now, "T1059")

        incident = _inc(
            "INC-CKC", "Ataque secuencial detectado", "HIGH",
            [ev1, ev2, ev3], ["T1595", "T1566", "T1059"],
            self.now.isoformat()
        )

        path = self.analyzer.analyze([incident])

        self.assertIn(KillChainPhase.RECONNAISSANCE, path.phases)
        self.assertIn(KillChainPhase.DELIVERY, path.phases)
        self.assertIn(KillChainPhase.EXPLOITATION, path.phases)

        maturity = self.analyzer.calculate_attack_maturity(path)
        self.assertTrue(maturity > 0)

        predictions = self.analyzer.predict_next_phase(path)
        self.assertTrue(len(predictions) > 0)

        countermeasures = self.analyzer.get_recommended_countermeasures(path)
        self.assertTrue(len(countermeasures) > 0)

    def test_kill_chain_visualizer(self):
        """Prueba que los visualizadores de la Kill Chain no arrojen errores y serialicen bien."""
        ev = _ev("EV1", "endpoint", "LOW", "powershell", self.now, "T1059")
        incident = _inc(
            "INC-VIS", "Visualizer Test", "LOW",
            [ev], ["T1059"], self.now.isoformat()
        )
        path = self.analyzer.analyze([incident])

        ascii_out = KillChainVisualizer.to_ascii(path)
        self.assertIsInstance(ascii_out, str)
        self.assertTrue(len(ascii_out) > 0)

        mermaid_out = KillChainVisualizer.to_mermaid(path)
        self.assertIsInstance(mermaid_out, str)
        self.assertIn("graph TD", mermaid_out)

        json_out = KillChainVisualizer.to_json(path)
        self.assertIsInstance(json_out, str)
        data = json.loads(json_out)
        self.assertAlmostEqual(data["metrics"]["confidence_score"], path.confidence_score, places=1)

    def test_attack_surface_mapper(self):
        """Valida las funciones de evaluacion y comparacion de la superficie de ataque."""
        scan_data = {
            "endpoints": ["10.0.0.5", "10.0.0.6"],
            "ports": [22, 80, 443],
            "technologies": ["Apache", "OpenSSH"],
            "vulnerabilities": [
                {
                    "cve": "CVE-2023-0001",
                    "cvss": 9.8,
                    "component": "Apache",
                    "description": "Critical RCE"
                },
                {
                    "cve": "CVE-2023-0002",
                    "cvss": 5.4,
                    "component": "OpenSSH",
                    "description": "Medium Information Disclosure"
                }
            ]
        }

        mapper = AttackSurfaceMapper()
        surface = mapper.map_from_scan_results(scan_data)

        self.assertEqual(len(surface.endpoints), 2)
        self.assertEqual(len(surface.ports), 3)
        self.assertEqual(len(surface.technologies), 2)
        self.assertEqual(len(surface.vulnerabilities), 2)

        risk_score = mapper.calculate_risk_score(surface)
        self.assertTrue(0.0 <= risk_score <= 10.0)

        matrix = mapper.get_exposure_matrix(surface)
        self.assertIn("Apache", matrix)
        self.assertEqual(matrix["Apache"]["max_cvss"], 9.8)

        past_scan = {
            "endpoints": ["10.0.0.5"],
            "ports": [22],
            "technologies": ["OpenSSH"],
            "vulnerabilities": []
        }
        past_surface = mapper.map_from_scan_results(past_scan)

        diff = mapper.compare_surfaces(past_surface, surface)
        self.assertTrue(diff["risk_metrics"]["risk_after"] > diff["risk_metrics"]["risk_before"])
        self.assertEqual(diff["vulnerabilities"]["added_count"], 2)


if __name__ == "__main__":
    unittest.main()
