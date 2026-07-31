#!/usr/bin/env python3
"""
Integration & Orchestrator Updater
==================================
Updates unified_orchestrator.py, termux_run.py, and seal_manager.py
to fully integrate the new SOAR DAG Playbooks engine, behavioral NDR, MITRE enrichment, and STIX 2.1 export.
Regenerates cryptographic seals using the integrity seal manager afterwards.
"""

import os
import sys
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def update_seal_manager():
    """Add soar/playbooks.py to the list of critical files inside seal_manager.py"""
    seal_path = ROOT / "integrity" / "seal_manager.py"
    if not seal_path.exists():
        print(f"[ERROR] seal_manager.py not found at {seal_path}")
        return False

    with open(seal_path, "r", encoding="utf-8") as f:
        content = f.read()

    # If already updated, skip
    if "soar/playbooks.py" in content:
        print("[+] seal_manager.py already includes soar/playbooks.py")
        return True

    # Find the critical_files array
    target_pattern = 'self.critical_files = ['
    replacement = 'self.critical_files = [\n            "soar/playbooks.py",'
    
    if target_pattern in content:
        updated_content = content.replace(target_pattern, replacement, 1)
        with open(seal_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print("[+] Successfully updated seal_manager.py critical files list.")
        return True
    else:
        print("[ERROR] Could not find critical_files list in seal_manager.py")
        return False

def update_termux_run():
    """Add soar.playbooks check to termux_run.py status command"""
    run_path = ROOT / "scripts" / "termux_run.py"
    if not run_path.exists():
        print(f"[ERROR] termux_run.py not found at {run_path}")
        return False

    with open(run_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "soar.playbooks" in content:
        print("[+] termux_run.py already contains soar.playbooks check")
        return True

    target_pattern = '("SOAR", "soar.engine", "SOAREngine"),'
    replacement = '("SOAR", "soar.engine", "SOAREngine"),\n        ("SOAR DAG Engine", "soar.playbooks", "PlaybookExecutor"),'

    if target_pattern in content:
        updated_content = content.replace(target_pattern, replacement, 1)
        with open(run_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print("[+] Successfully updated termux_run.py modules check list.")
        return True
    else:
        print("[ERROR] Could not find modules list in termux_run.py")
        return False

def update_unified_orchestrator():
    """Rewrite/Update unified_orchestrator.py to fully feature our new capabilities"""
    orch_path = ROOT / "runner" / "unified_orchestrator.py"
    
    # Let's write the entire high-fidelity implementation of the new orchestrator!
    orchestrator_code = """#!/usr/bin/env python3
\"\"\"
Orquestador Unificado Enriquecido — Red Team Enterprise
Ejecuta un escaneo completo, correlaciona con MITRE ATT&CK,
evalúa políticas ZTNA, simula detección NDR comportamental,
activa la Malla de Engaño Dinámica, ejecuta Playbooks de Respuesta
con el Motor DAG de SOAR y genera reportes con exportación de IoCs en STIX 2.1.
\"\"\"
import json
import time
import datetime
import os
import sys
import pathlib
import hashlib

# Asegurar imports correctos
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from xdr.correlator import XDRCorrelator, MITRE_TECHNIQUES
from soar.playbooks import PlaybookExecutor, create_predefined_playbook
from ztna.gateway import ZTNAGateway, AccessRequest, AccessDecision
from ndr.engine import NDREngine, TrafficFlow
from rasp.agent import RASPAgent
from deception.mesh import DeceptionMesh
from tlsproxy.interceptor import TLSProxy, InterceptedFlow
from tip.platform import ThreatIntelPlatform, IoC
from probe.real_scanner import RealScanner


def run_unified_scan(target: str, backend: str, output_dir: str) -> dict:
    \"\"\"Ejecuta scan real + todos los módulos defensivos enriquecidos.\"\"\"
    started_at = datetime.datetime.utcnow().isoformat() + "Z"

    # Inicializar componentes
    xdr = XDRCorrelator()
    playbook_executor = PlaybookExecutor(dry_run=False)
    ztna = ZTNAGateway()
    ndr = NDREngine()
    rasp = RASPAgent(target=target)
    deception = DeceptionMesh()
    tip = ThreatIntelPlatform()
    tls_proxy = TLSProxy()

    # ════════════════════════════════════════════════════════════════
    # FASE 0: SCAN REAL CONTRA EL BACKEND
    # ════════════════════════════════════════════════════════════════
    print("[0/8] Scan REAL contra backend...")
    scanner = RealScanner(backend_url=backend)
    real_results = scanner.scan_all()

    if real_results.get("error"):
        print(f"  ⚠️  {real_results['error']}")
        print(f"  Continuando con módulos defensivos...\\n")
    else:
        print(f"  ✅ {real_results['endpoints_tested']} endpoints probados, "
              f"{real_results['total_findings']} hallazgos reales\\n")

        # Alimentar hallazgos reales al XDR
        for finding in real_results.get("findings", []):
            xdr.ingest_raw(
                source="probe",
                severity=finding["severity"],
                title=f"REAL: {finding['type']} en {finding['endpoint']}",
                description=finding["description"],
                mitre=finding.get("mitre", ""),
                endpoint=finding["endpoint"],
            )
            # Alimentar al TIP
            tip.add_ioc(IoC(
                type="endpoint", value=finding["endpoint"],
                source="probe", confidence=0.9 if finding["severity"] == "critical" else 0.7,
            ))

    # ════════════════════════════════════════════════════════════════
    # FASE 1: RASP (Runtime Application Self-Protection)
    # ════════════════════════════════════════════════════════════════
    print("[1/8] Ejecutando RASP scan (cliente)...")
    rasp_alerts = rasp.scan()
    for a in rasp_alerts:
        xdr.ingest_raw(
            source="rasp", severity=a.severity, title=f"RASP: {a.type}",
            description=a.detail, mitre=a.mitre, endpoint=target,
        )
    attestation = rasp.attest()
    print(f"  → {len(rasp_alerts)} alertas RASP, atestación: {attestation.get('device_safe', False)}")

    # ════════════════════════════════════════════════════════════════
    # FASE 2: NDR COMPORTAMENTAL (Beaconing & Tunneling Detection)
    # ════════════════════════════════════════════════════════════════
    print("[2/8] Ejecutando NDR scan comportamental (análisis de flujos de red)...")
    
    # 2a. Tráfico regular para simular beaconing C2 (6 conexiones con intervalo idéntico)
    base_ts = time.time()
    for i in range(6):
        flow = TrafficFlow(
            src_ip="10.0.0.1",
            dst_ip="185.220.101.1",
            dst_port=443,
            protocol="TCP",
            bytes_sent=500,
            bytes_received=100,
            timestamp=base_ts + i * 30  # Intervalo perfecto de 30s
        )
        alerts = ndr.ingest_flow(flow)
        for a in alerts:
            xdr.ingest_raw(
                source="ndr", severity=a.severity, title=f"NDR: {a.type}",
                description=a.description, mitre=a.mitre,
                src_ip=a.src_ip, dst_ip=a.dst_ip,
            )

    # 2b. Tráfico anómalo de gran query DNS para simular tunelización
    dns_tunnel_flow = TrafficFlow(
        src_ip="10.0.0.1",
        dst_ip="8.8.8.8",
        dst_port=53,
        protocol="DNS",
        bytes_sent=150,  # Query de tamaño grande
        bytes_received=300,
        timestamp=time.time()
    )
    alerts = ndr.ingest_flow(dns_tunnel_flow)
    for a in alerts:
        xdr.ingest_raw(
            source="ndr", severity=a.severity, title=f"NDR: {a.type}",
            description=a.description, mitre=a.mitre,
            src_ip=a.src_ip, dst_ip=a.dst_ip,
        )

    print(f"  → {len(ndr.alerts)} alertas NDR detectadas mediante análisis heurístico comportamental.")

    # ════════════════════════════════════════════════════════════════
    # FASE 3: MALLA DE ENGAÑO DINÁMICA (Deception Mesh)
    # ════════════════════════════════════════════════════════════════
    print("[3/8] Desplegando Deception Mesh (elementos trampa activos)...")
    for i in range(5):
        deception.deploy_token("api_key", f"api_endpoint_{i}")
    deception.deploy_token("dns", "dns_canary")
    deception.deploy_token("jwt", "session_cache")
    for i in range(3):
        deception.deploy_synthetic_session()
        
    # Simular que un atacante interactúa con un decoy endpoint no documentado
    decoy_alert = deception.check_decoy_hit("/v1/keys", "GET", ip="10.0.0.99")
    if decoy_alert:
        xdr.ingest_raw(
            source="deception", severity="critical",
            title="Decoy accedido", description=decoy_alert["description"],
            mitre=decoy_alert["mitre"], src_ip="10.0.0.99",
        )
    print(f"  → {len(deception.tokens)} tokens plantados, {deception.get_summary()['decoy_hits']} decoy hits")

    # ════════════════════════════════════════════════════════════════
    # FASE 4: TLS PROXY INTERCEPTOR
    # ════════════════════════════════════════════════════════════════
    print("[4/8] Procesando flujos TLS...")
    test_intercepted = InterceptedFlow(
        id="flow-001", src_ip="10.0.0.5",
        dst_host=backend.split("//")[-1].split("/")[0] if backend else "unknown",
        dst_port=443, method="GET", path="/api/courses",
        request_headers={"host": backend}, response_headers={},
        request_size=200, response_size=5000, duration_ms=45,
        tls_version="TLSv1.3", sni=backend, cert_valid=True,
        content_type="application/json",
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )
    tls_alerts = tls_proxy.process_flow(test_intercepted)
    for a in tls_alerts:
        xdr.ingest_raw(
            source="tls", severity=a["severity"], title=f"TLS Proxy: {a['type']}",
            description=a["description"], mitre=a.get("mitre", ""),
        )
    print(f"  → {len(tls_proxy.alerts)} alertas TLS")

    # ════════════════════════════════════════════════════════════════
    # FASE 5: ZTNA GATEWAY (Zero Trust Network Access)
    # ════════════════════════════════════════════════════════════════
    print("[5/8] Evaluando ZTNA Gateway...")
    test_requests = [
        AccessRequest(user_id="1", user_hash="abc123", role="student",
                      endpoint="/api/courses", method="GET",
                      device_attested=True, ip_address="10.0.0.1"),
        AccessRequest(user_id="2", user_hash="def456", role="student",
                      endpoint="/api/admin/seals", method="GET",
                      device_attested=False, ip_address="10.0.0.2"),
        AccessRequest(user_id="3", user_hash="ghi789", role="student",
                      endpoint="/api/courses/123", method="GET",
                      device_attested=True, ip_address="10.0.0.3",
                      resource_owner_id="xyz999"),
    ]
    for req in test_requests:
        decision, reason, policy = ztna.evaluate(req)
        if decision != AccessDecision.ALLOW:
            xdr.ingest_raw(
                source="ztna",
                severity="high" if decision.value.startswith("deny") else "info",
                title=f"ZTNA: {decision.value}", description=reason,
                mitre="T1190" if "BOLA" in reason else "",
                src_ip=req.ip_address, user_hash=req.user_hash, endpoint=req.endpoint,
            )
    print(f"  → {len(ztna.audit_log)} evaluaciones ZTNA registradas.")

    # ════════════════════════════════════════════════════════════════
    # FASE 6: XDR CORRELATOR & ENRIQUECIMIENTO MITRE ATT&CK
    # ════════════════════════════════════════════════════════════════
    print("[6/8] Correlacionando eventos XDR con Enriquecimiento MITRE...")
    incidents = xdr.correlate()
    print(f"  → {len(incidents)} incidentes correlacionados.")
    
    enriched_incidents = []
    for inc in incidents:
        mitre_details = []
        print(f"  → Incidente Detectado: [{inc.severity.upper()}] '{inc.title}'")
        for tech_id in inc.mitre_techniques:
            tech_info = MITRE_TECHNIQUES.get(tech_id, {"name": "Technique", "tactic": "Unknown"})
            detail_str = f"{tech_id}: {tech_info['name']} (Táctica: {tech_info['tactic']})"
            mitre_details.append(detail_str)
            print(f"    - Mapeo MITRE: {detail_str}")
        
        inc_dict = {
            "id": inc.id,
            "title": inc.title,
            "severity": inc.severity,
            "status": inc.status,
            "mitre_techniques": inc.mitre_techniques,
            "mitre_details": mitre_details,
            "src_ips": inc.src_ips,
            "affected_assets": inc.affected_assets,
            "recommended_actions": inc.recommended_actions,
            "confidence": inc.confidence
        }
        enriched_incidents.append(inc_dict)

    # ════════════════════════════════════════════════════════════════
    # FASE 7: SOAR PLAYBOOK DAG ENGINE EXECUTION
    # ════════════════════════════════════════════════════════════════
    print("[7/8] Ejecutando Playbooks SOAR con Motor DAG...")
    soar_audit_logs = []
    blocked_ips = []
    isolated_devices = []

    for inc in incidents:
        # Determine appropriate predefined playbook based on recommended actions or incident title
        playbook_name = "credential_stuffing_response"  # Default fallback
        
        if "beacon" in inc.title.lower() or "exfil" in inc.title.lower():
            playbook_name = "c2_beaconing_response"
        elif "deception" in inc.title.lower() or "movimiento lateral" in inc.title.lower():
            playbook_name = "data_exfiltration_response"
        elif "credential" in inc.title.lower() or "brute" in inc.title.lower():
            playbook_name = "credential_stuffing_response"
        elif "api" in inc.title.lower() or "abuse" in inc.title.lower() or "rate" in inc.title.lower():
            playbook_name = "api_abuse_response"
        elif "malware" in inc.title.lower():
            playbook_name = "malware_detection_response"
            
        target_ip = inc.src_ips[0] if inc.src_ips else "10.0.0.99"
        
        print(f"  → Iniciando DAG Playbook '{playbook_name}' para target: {target_ip}")
        dag = create_predefined_playbook(playbook_name, target=target_ip)
        
        # Build Context
        context = {
            "id": inc.id,
            "title": inc.title,
            "severity": inc.severity,
            "src_ip": target_ip,
            "mitre_techniques": inc.mitre_techniques
        }
        
        # Execute Playbook
        execution_summary = playbook_executor.execute(dag, context)
        print(f"    - Resultado del Playbook: {execution_summary['status']}")
        print(f"    - Nodos completados: {', '.join(execution_summary['completed_nodes'])}")
        
        # Feed back blocks into live state
        for node_name, node in dag.nodes.items():
            if node.state == "completed":
                if node.action_type == "block_ip":
                    blocked_ips.append(node.target)
                elif node.action_type == "isolate_endpoint":
                    isolated_devices.append(node.target)

    # Collect full audit trail from SOAR
    soar_audit_logs = list(playbook_executor.audit_trail)
    print(f"  → {len(soar_audit_logs)} acciones de playbook registradas en la auditoría SOAR.")

    # ════════════════════════════════════════════════════════════════
    # FASE 8: TIP (Threat Intelligence Platform) & EXPORTACIÓN STIX 2.1
    # ════════════════════════════════════════════════════════════════
    print("[8/8] Actualizando TIP (Threat Intel Platform) & Exportando STIX 2.1...")
    
    # Alimentar TIP con IoCs resultantes de las acciones del SOAR
    for ip in blocked_ips:
        tip.add_ioc(IoC(type="ip", value=str(ip), source="soar", confidence=0.9))
    for device in isolated_devices:
        tip.add_ioc(IoC(type="domain", value=f"device-{device}.sourceseal.local", source="soar", confidence=0.85))

    tip_summary = tip.get_summary()
    print(f"  → {tip_summary['total_iocs']} IoCs consolidados en el TIP.")

    # Exportar IoCs recolectados a un paquete formal compatible con STIX 2.1
    stix_objects = []
    for ioc in tip.iocs:
        stix_id_base = hashlib.sha256(f"{ioc.type}:{ioc.value}".encode()).hexdigest()[:16]
        
        if ioc.type == "ip":
            addr_obj = {
                "type": "ipv4-addr",
                "spec_version": "2.1",
                "id": f"ipv4-addr--{stix_id_base}",
                "value": ioc.value
            }
            indicator_obj = {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{stix_id_base}",
                "created": ioc.first_seen.isoformat() + "Z",
                "modified": ioc.first_seen.isoformat() + "Z",
                "pattern": f"[ipv4-addr:value = '{ioc.value}']",
                "pattern_type": "stix",
                "valid_from": ioc.first_seen.isoformat() + "Z",
                "labels": ["malicious-activity"],
                "confidence": int(ioc.confidence * 100)
            }
            stix_objects.extend([addr_obj, indicator_obj])
            
        elif ioc.type == "endpoint" or ioc.type == "domain":
            domain_obj = {
                "type": "domain-name",
                "spec_version": "2.1",
                "id": f"domain-name--{stix_id_base}",
                "value": ioc.value
            }
            stix_objects.append(domain_obj)

    stix_bundle = {
        "type": "bundle",
        "id": f"bundle--{hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]}",
        "spec_version": "2.1",
        "objects": stix_objects
    }

    stix_filename = "stix-threat-bundle.json"
    stix_path = os.path.join(output_dir, stix_filename)
    with open(stix_path, "w") as sf:
        json.dump(stix_bundle, sf, indent=2)
    print(f"  → ✅ Exportación STIX 2.1 exitosa: {len(stix_objects)} objetos guardados en {stix_path}")

    # ════════════════════════════════════════════════════════════════
    # REPORTE FINAL DE AUDITORÍA
    # ════════════════════════════════════════════════════════════════
    finished_at = datetime.datetime.utcnow().isoformat() + "Z"
    
    report = {
        "scan_metadata": {
            "target": target, "backend": backend,
            "started_at": started_at, "finished_at": finished_at,
        },
        "real_scan": real_results,
        "rasp": {
            "alerts": len(rasp_alerts),
            "attestation": attestation.get("device_safe", False),
        },
        "ndr": {
            "alerts": len(ndr.alerts),
            "detections": ndr.get_summary()
        },
        "ztna": {"evaluations": len(ztna.audit_log)},
        "deception": {"tokens": len(deception.tokens), "decoy_hits": deception.get_summary()["decoy_hits"]},
        "tls_proxy": {"alerts": len(tls_proxy.alerts)},
        "xdr_correlator": {
            "incidents": len(incidents),
            "enriched_incidents": enriched_incidents
        },
        "soar_dag": {
            "executed_actions": len(soar_audit_logs),
            "audit_trail": soar_audit_logs,
            "blocked_ips": blocked_ips,
            "isolated_devices": isolated_devices
        },
        "tip": tip_summary,
        "stix_bundle_file": stix_filename
    }

    # Guardar reporte JSON
    os.makedirs(output_dir, exist_ok=True)
    filename = f"unified-report-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    report_path = os.path.join(output_dir, filename)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\\n[OK] Reporte unificado completo guardado en {report_path}")

    # Guardar reporte resumido Markdown
    md_path = os.path.join(output_dir, "latest-unified.md")
    with open(md_path, "w") as f:
        f.write(f"# Reporte Unificado Enriquecido — {started_at}\\n\\n")
        f.write(f"- **Target**: `{target}`\\n")
        f.write(f"- **Backend**: `{backend}`\\n\\n")
        f.write("## 🛡️ Resumen de Defensa Activa\\n")
        f.write(f"- Alertas RASP: `{len(rasp_alerts)}`\\n")
        f.write(f"- Alertas NDR Comportamentales: `{len(ndr.alerts)}`\\n")
        f.write(f"- Incidentes Correlacionados (XDR): `{len(incidents)}`\\n")
        f.write(f"- Acciones de Respuesta DAG Ejecutadas (SOAR): `{len(soar_audit_logs)}`\\n")
        f.write(f"- IoCs Registrados en TIP: `{tip_summary['total_iocs']}`\\n\\n")
        
        f.write("## 🧬 Enriquecimiento MITRE ATT&CK\\n")
        for inc in enriched_incidents:
            f.write(f"### {inc['title']} (Severidad: {inc['severity']})\\n")
            f.write(f"- **Confianza de Detección**: `{inc['confidence']:.2f}`\\n")
            f.write("- **Tácticas y Técnicas MITRE Map**:\\n")
            for det in inc['mitre_details']:
                f.write(f"  - `{det}`\\n")
            f.write("\\n")
            
        f.write("## 🤖 Auditoría de Ejecución de Playbooks SOAR (DAG)\\n")
        f.write("| Nodo | Acción | Target | Estado | Duración (ms) | Reintentos |\\n")
        f.write("|---|---|---|---|---|---|\\n")
        for entry in soar_audit_logs:
            f.write(f"| {entry['node_name']} | {entry['action_type']} | `{entry['target']}` | **{entry['status']}** | {entry['duration_ms']:.1f} | {entry['retries']} |\\n")

    print(f"[OK] Reporte Markdown guardado en {md_path}")
    return report
"""
    
    with open(orch_path, "w", encoding="utf-8") as f:
        f.write(orchestrator_code)
    
    print("[+] Successfully wrote updated unified_orchestrator.py.")
    return True

def run_cryptographic_seal():
    """Execute the termux_run.py seal command to regenerate the signatures for all changed critical files"""
    seal_cmd = [sys.executable, str(ROOT / "scripts" / "termux_run.py"), "seal"]
    print(f"Running: {' '.join(seal_cmd)}")
    
    result = subprocess.run(seal_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("[+] Cryptographic sealing completed successfully.")
        print(result.stdout)
        return True
    else:
        print("[ERROR] Cryptographic sealing failed.")
        print(result.stderr)
        return False

def main():
    print("==================================================")
    print("INTEGRATION SCRIPT: UPDATING REDTEAM ENTERPRISE")
    print("==================================================")
    
    if not update_seal_manager():
        sys.exit(1)
        
    if not update_termux_run():
        sys.exit(1)
        
    if not update_unified_orchestrator():
        sys.exit(1)
        
    print("\nRe-sealing changed assets for dynamic integrity verification...")
    if not run_cryptographic_seal():
        sys.exit(1)
        
    print("\n==================================================")
    print("[SUCCESS] All systems updated and re-sealed.")
    print("==================================================")

if __name__ == "__main__":
    main()
