# -*- coding: utf-8 -*-
"""
SourceSeal Red Team - XDR Unit Tests
Pruebas unitarias para validar el motor de correlación, Cyber Kill Chain,
visualizaciones y evaluación de la superficie de ataque.
"""

import unittest
from datetime import datetime, timedelta
import json

from xdr.correlator import XDREvent, Incident, MITRE_TECHNIQUES, XDRCorrelator
from xdr.kill_chain import KillChainPhase, AttackPath, KillChainAnalyzer, KillChainVisualizer
from xdr.attack_surface import AttackSurface, AttackSurfaceMapper


class TestXDRCorrelatorAndKillChain(unittest.TestCase):

    def setUp(self):
        self.analyzer = KillChainAnalyzer()
        self.now = datetime.now()

    def test_event_and_incident_creation(self):
        """Prueba que los eventos e incidentes se creen e inicialicen con datos correctos."""
        event = XDREvent(
            event_id="EV-TEST-01",
            timestamp=self.now,
            source="test_source",
            event_type="test_event",
            description="Test Description",
            mitre_techniques=["T1595"]
        )
        self.assertEqual(event.event_id, "EV-TEST-01")
        self.assertEqual(event.mitre_techniques, ["T1595"])

        incident = Incident(
            incident_id="INC-TEST-01",
            title="Test Incident",
            description="Test Incident Description",
            severity="MEDIUM",
            timestamp=self.now,
            events=[event],
            mitre_techniques=["T1595"]
        )
        self.assertEqual(incident.incident_id, "INC-TEST-01")
        self.assertEqual(len(incident.events), 1)
        self.assertEqual(incident.severity, "MEDIUM")

    def test_kill_chain_analyzer(self):
        """Valida que el analizador reconstruya correctamente las fases a partir de técnicas MITRE."""
        # Creamos una cadena de eventos cronológica que avanza por varias fases
        ev1 = XDREvent("EV1", self.now - timedelta(minutes=10), "firewall", "recon", "Scan", ["T1595"]) # RECONNAISSANCE
        ev2 = XDREvent("EV2", self.now - timedelta(minutes=5), "email", "phish", "Phishing", ["T1566"])   # DELIVERY
        ev3 = XDREvent("EV3", self.now, "endpoint", "powershell", "Script", ["T1059"])                  # EXPLOITATION

        incident = Incident(
            incident_id="INC-CKC",
            title="Ataque secuencial detectado",
            description="Intrusión en progreso",
            severity="HIGH",
            timestamp=self.now,
            events=[ev1, ev2, ev3],
            mitre_techniques=["T1595", "T1566", "T1059"]
        )

        path = self.analyzer.analyze([incident])

        # Verificar que se detectaron las fases correspondientes
        self.assertIn(KillChainPhase.RECONNAISSANCE, path.phases)
        self.assertIn(KillChainPhase.DELIVERY, path.phases)
        self.assertIn(KillChainPhase.EXPLOITATION, path.phases)

        # Verificar madurez del ataque (la fase más avanzada es EXPLOITATION, índice 3 de 7)
        maturity = self.analyzer.calculate_attack_maturity(path)
        self.assertTrue(maturity > 0)
        self.assertEqual(maturity, 57.14)  # 4/7 * 100

        # Verificar predicciones (debe sugerir fases posteriores a la máxima alcanzada)
        predictions = self.analyzer.predict_next_phase(path)
        self.assertTrue(len(predictions) > 0)

        # Verificar contramedidas recomendadas
        countermeasures = self.analyzer.get_recommended_countermeasures(path)
        self.assertTrue(len(countermeasures) > 0)

    def test_kill_chain_visualizer(self):
        """Prueba que los visualizadores de la Kill Chain no arrojen errores y serialicen bien."""
        ev = XDREvent("EV1", self.now, "endpoint", "powershell", "Script", ["T1059"])
        incident = Incident("INC-VIS", "Visualizer Test", "Desc", "LOW", self.now, [ev], ["T1059"])
        path = self.analyzer.analyze([incident])

        # ASCII Art
        ascii_out = KillChainVisualizer.to_ascii(path)
        self.assertIsInstance(ascii_out, str)
        self.assertTrue(len(ascii_out) > 0)

        # Mermaid
        mermaid_out = KillChainVisualizer.to_mermaid(path)
        self.assertIsInstance(mermaid_out, str)
        self.assertIn("graph TD", mermaid_out)

        # JSON
        json_out = KillChainVisualizer.to_json(path)
        self.assertIsInstance(json_out, str)
        data = json.loads(json_out)
        self.assertEqual(data["confidence_score"], path.confidence_score)
        self.assertEqual(data["maturity_percentage"], self.analyzer.calculate_attack_maturity(path))

    def test_attack_surface_mapper(self):
        """Valida las funciones de evaluación y comparación de la superficie de ataque."""
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

        self.assertEqual(surface.endpoints_count, 2)
        self.assertEqual(surface.exposed_ports_count, 3)
        self.assertEqual(len(surface.technologies), 2)
        self.assertEqual(len(surface.vulnerabilities), 2)

        risk_score = mapper.calculate_risk_score(surface)
        self.assertTrue(0.0 <= risk_score <= 10.0)

        matrix = mapper.get_exposure_matrix(surface)
        self.assertIn("Apache", matrix)
        self.assertEqual(matrix["Apache"]["cvss_max"], 9.8)

        # Comparación histórica
        past_scan = {
            "endpoints": ["10.0.0.5"],
            "ports": [22],
            "technologies": ["OpenSSH"],
            "vulnerabilities": []
        }
        past_surface = mapper.map_from_scan_results(past_scan)

        diff = mapper.compare_surfaces(past_surface, surface)
        self.assertTrue(diff["risk_metrics"]["current_risk"] > diff["risk_metrics"]["previous_risk"])
        self.assertEqual(diff["vulnerabilities_delta"]["added_count"], 2)


if __name__ == "__main__":
    unittest.main()
