# -*- coding: utf-8 -*-
"""
Script de verificación para validar que todas las clases y módulos del Red Team
se importan y funcionan correctamente.
"""

from datetime import datetime
import json

# Importar nuestros módulos creados
from xdr.correlator import XDREvent, Incident, MITRE_TECHNIQUES
from xdr.kill_chain import KillChainPhase, AttackPath, KillChainAnalyzer, KillChainVisualizer
from xdr.attack_surface import AttackSurface, AttackSurfaceMapper
from tip.stix_taxii import STIXBundle, TAXIIPublisher, TAXIISubscriber, MITREAttackMapper


def test_kill_chain():
    print("--- Test de Kill Chain ---")
    
    # Crear eventos de ejemplo
    event1 = XDREvent(
        event_id="EV-001",
        timestamp=datetime.now(),
        source="firewall",
        event_type="network_scan",
        description="Escaneo de puertos activo desde IP externa",
        mitre_techniques=["T1595"]
    )
    
    event2 = XDREvent(
        event_id="EV-002",
        timestamp=datetime.now(),
        source="email_gateway",
        event_type="phishing",
        description="Correo de phishing con adjunto detectado",
        mitre_techniques=["T1566", "T1204"]
    )
    
    event3 = XDREvent(
        event_id="EV-003",
        timestamp=datetime.now(),
        source="endpoint_agent",
        event_type="process_creation",
        description="Ejecución de PowerShell sospechosa",
        mitre_techniques=["T1059"]
    )

    # Crear incidente
    incident = Incident(
        incident_id="INC-100",
        title="Intrusión en fase temprana detectada",
        description="Se detectó una secuencia de escaneo de puertos seguido de phishing y ejecución de PowerShell",
        severity="HIGH",
        timestamp=datetime.now(),
        events=[event1, event2, event3],
        mitre_techniques=["T1595", "T1566", "T1204", "T1059"]
    )

    # Ejecutar análisis
    analyzer = KillChainAnalyzer()
    path = analyzer.analyze([incident])
    
    print(f"Fases detectadas: {[p.value for p in path.phases]}")
    print(f"Confianza de análisis: {path.confidence_score}%")
    
    maturity = analyzer.calculate_attack_maturity(path)
    print(f"Madurez del ataque: {maturity}%")
    
    predictions = analyzer.predict_next_phase(path)
    print(f"Predicciones de siguiente fase: {predictions}")
    
    countermeasures = analyzer.get_recommended_countermeasures(path)
    print(f"Contramedidas sugeridas (top 3): {countermeasures[:3]}")

    # Visualizar
    ascii_art = KillChainVisualizer.to_ascii(path)
    print("\nVisualización ASCII:")
    print(ascii_art)
    
    mermaid_diag = KillChainVisualizer.to_mermaid(path)
    print("\nDiagrama Mermaid:")
    print(mermaid_diag)
    
    json_data = KillChainVisualizer.to_json(path)
    print("\nDashboard JSON:")
    print(json_data)


def test_attack_surface():
    print("\n--- Test de Superficie de Ataque ---")
    scan_results = {
        "endpoints": ["192.168.1.10", "192.168.1.20"],
        "ports": [22, 80, 443, 3306],
        "technologies": ["OpenSSH", "Nginx", "MySQL"],
        "vulnerabilities": [
            {
                "cve": "CVE-2023-4567",
                "cvss": 9.8,
                "component": "Nginx",
                "description": "RCE en cabecera HTTP"
            },
            {
                "cve": "CVE-2023-1111",
                "cvss": 7.2,
                "component": "MySQL",
                "description": "Inyección SQL de privilegios"
            }
        ]
    }
    
    mapper = AttackSurfaceMapper()
    surface = mapper.map_from_scan_results(scan_results)
    
    risk = mapper.calculate_risk_score(surface)
    print(f"Puntaje de riesgo de superficie: {risk}/10")
    
    matrix = mapper.get_exposure_matrix(surface)
    print(f"Matriz de exposición (Nginx): {json.dumps(matrix.get('Nginx'), indent=2)}")

    # Comparación histórica
    older_scan = {
        "endpoints": ["192.168.1.10"],
        "ports": [22, 80],
        "technologies": ["OpenSSH", "Nginx"],
        "vulnerabilities": []
    }
    old_surface = mapper.map_from_scan_results(older_scan)
    
    diff = mapper.compare_surfaces(old_surface, surface)
    print(f"Delta de riesgo histórico: {diff['risk_metrics']}")


def test_stix_taxii():
    print("\n--- Test de STIX & TAXII ---")
    bundle = STIXBundle()
    
    # Añadir IoC
    bundle.add_indicator("185.220.101.1", name="Tor Exit Node", description="Nodo de salida TOR identificado en campaña C2")
    # Añadir malware
    malware_ref = bundle.add_malware("ShadowStealer", "infostealer", aliases=["ShadowSpy"])
    # Añadir relación
    bundle.add_relationship(malware_ref.id, "indicator--abcdef", "indicates")
    
    print("Bundle STIX generado con éxito!")
    print(f"Longitud de objetos: {len(bundle.objects)}")
    
    # Test MITRE mapper
    tech = MITREAttackMapper.get_technique("T1003")
    print(f"Detalles de técnica T1003: {tech['name']} | Táctica: {tech['tactic']}")
    
    by_tactic = MITREAttackMapper.get_by_tactic("Impact")
    print(f"Técnicas de Impacto (Total): {len(by_tactic)}")
    
    by_alert = MITREAttackMapper.techniques_for_alert("ransomware_encryption")
    print(f"Técnicas mapeadas a alerta 'ransomware_encryption': {by_alert}")


if __name__ == "__main__":
    test_kill_chain()
    test_attack_surface()
    test_stix_taxii()
    print("\n[OK] ¡TODAS LAS PRUEBAS PY PASARON CORRECTAMENTE!")
