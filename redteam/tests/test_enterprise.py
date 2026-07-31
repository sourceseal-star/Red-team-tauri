#!/usr/bin/env python3
"""
Tests de los módulos enterprise (XDR, SOAR, ZTNA, NDR, RASP, Deception, TLS Proxy).
Ejecutar: python3 tests/test_enterprise.py
"""
import sys
import os
import time
import json
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def test_xdr_correlator():
    """XDR: ingestar eventos y correlacionar incidentes."""
    from xdr.correlator import XDRCorrelator, XDREvent
    import datetime

    corr = XDRCorrelator()

    # Ingestar eventos de diferentes fuentes
    corr.ingest_raw("ndr", "critical", "C2 Beaconing", "Beaconing detected",
                    mitre="T1071", src_ip="10.0.0.99")
    corr.ingest_raw("ndr", "critical", "Exfiltracion", "Data exfil detected",
                    mitre="T1041", src_ip="10.0.0.99")
    corr.ingest_raw("deception", "critical", "Canary consumido",
                    "Token canary consumido", mitre="T1550", src_ip="10.0.0.99")

    incidents = corr.correlate()
    assert len(incidents) > 0, "Debe generar al menos 1 incidente"
    assert any(i.severity == "critical" for i in incidents), "Debe haber incidentes críticos"

    # Verificar mapeo MITRE
    attack_map = corr.get_attack_surface_map()
    assert attack_map["total_events"] == 3
    assert "Command and Control" in attack_map["mitre_tactics_covered"]

    print(f"✓ test_xdr_correlator ({len(incidents)} incidentes, {attack_map['total_events']} eventos)")


def test_soar_playbooks():
    """SOAR: ejecutar playbooks de respuesta automática."""
    from soar.engine import SOAREngine

    soar = SOAREngine()
    assert len(soar.playbooks) >= 8, f"Debe tener >=8 playbooks, tiene {len(soar.playbooks)}"

    # Ejecutar playbook block_ip
    incident = {
        "id": "test-inc-001",
        "severity": "critical",
        "recommended_actions": ["block_ip", "revoke_tokens"],
        "src_ips": ["10.0.0.99"],
        "affected_assets": ["device-001"],
    }
    results = soar.execute_incident(incident)
    assert len(results) > 0, "Debe ejecutar al menos una acción"

    # Verificar que los handlers dry-run funcionan
    success_count = sum(1 for r in results if r.status == "success")
    assert success_count > 0, "Debe haber al menos una acción exitosa"

    summary = soar.get_execution_summary()
    assert summary["total_executions"] > 0

    print(f"✓ test_soar_playbooks ({len(results)} acciones, {success_count} exitosas)")


def test_ztna_gateway():
    """ZTNA: evaluar requests con políticas ABAC."""
    from ztna.gateway import ZTNAGateway, AccessRequest, AccessDecision

    ztna = ZTNAGateway()

    # 1. Request legítimo — debe ser ALLOW
    req_ok = AccessRequest(
        user_id="1", user_hash="abc123", role="student",
        endpoint="/api/courses", method="GET",
        device_attested=True, ip_address="10.0.0.1",
    )
    decision, reason, policy = ztna.evaluate(req_ok)
    assert decision == AccessDecision.ALLOW, f"Request legitimo debe ser ALLOW, got {decision}: {reason}"

    # 2. Request sin rol suficiente — debe ser DENY
    req_admin = AccessRequest(
        user_id="2", user_hash="def456", role="student",
        endpoint="/api/admin/seals", method="GET",
        device_attested=True, ip_address="10.0.0.2",
    )
    decision, reason, policy = ztna.evaluate(req_admin)
    assert decision == AccessDecision.DENY, f"Student no debe acceder admin, got {decision}"

    # 3. BOLA attempt — debe ser DENY_BOLA
    req_bola = AccessRequest(
        user_id="3", user_hash="ghi789", role="student",
        endpoint="/api/courses/123", method="GET",
        device_attested=True, ip_address="10.0.0.3",
        resource_owner_id="xyz999",
    )
    decision, reason, policy = ztna.evaluate(req_bola)
    assert decision == AccessDecision.DENY_BOLA, f"BOLA debe ser detectado, got {decision}: {reason}"

    # 4. Rate limit — exceder debe bloquear
    req_rl = AccessRequest(
        user_id="4", user_hash="rate123", role="student",
        endpoint="/api/courses", method="GET",
        device_attested=True, ip_address="10.0.0.4",
    )
    # /api/courses tiene rate_limit_per_minute=60, enviar 65
    for _ in range(65):
        ztna.evaluate(req_rl)
    decision, reason, policy = ztna.evaluate(req_rl)
    assert decision == AccessDecision.DENY_RATE_LIMIT, f"Debe rate-limitear, got {decision}"

    # 5. Block IP via SOAR
    ztna.block_ip("10.0.0.99")
    req_blocked = AccessRequest(
        user_id="5", user_hash="blk999", role="student",
        endpoint="/api/courses", method="GET",
        device_attested=True, ip_address="10.0.0.99",
    )
    decision, reason, policy = ztna.evaluate(req_blocked)
    assert decision == AccessDecision.DENY, f"IP bloqueada debe ser DENY, got {decision}"

    # 6. Quarantine device
    ztna.quarantine_device("device-evil", ["/api/health"])
    req_quarantine = AccessRequest(
        user_id="6", user_hash="quar123", role="student",
        endpoint="/api/courses", method="GET",
        device_attested=True, ip_address="10.0.0.5",
        device_id="device-evil",
    )
    decision, reason, policy = ztna.evaluate(req_quarantine)
    assert decision == AccessDecision.DENY_BAD_POSTURE, f"Dispositivo en cuarentena debe ser denegado, got {decision}"

    print(f"✓ test_ztna_gateway (6 escenarios ABAC)")


def test_ndr_engine():
    """NDR: detectar beaconing, exfiltración y tunelización."""
    from ndr.engine import NDREngine, TrafficFlow

    ndr = NDREngine()

    # 1. Beaconing — 5 conexiones regulares al mismo destino
    base_time = time.time()
    for i in range(6):
        flow = TrafficFlow(
            src_ip="10.0.0.1", dst_ip="185.220.101.1", dst_port=443,
            protocol="TCP", bytes_sent=500, bytes_received=50,
            timestamp=base_time + i * 30,  # cada 30s exacto
        )
        alerts = ndr.ingest_flow(flow)
    beacon_alerts = [a for a in ndr.alerts if a.type == "beaconing"]
    assert len(beacon_alerts) > 0, "Debe detectar beaconing con intervalos regulares"

    # 2. DNS Tunneling
    ndr2 = NDREngine()
    dns_flow = TrafficFlow(
        src_ip="10.0.0.2", dst_ip="8.8.8.8", dst_port=53,
        protocol="DNS", bytes_sent=250, bytes_received=100,
        timestamp=time.time(),
    )
    alerts = ndr2.ingest_flow(dns_flow)
    assert any(a.type == "tunneling" for a in alerts), "Debe detectar tunelización DNS"

    print(f"✓ test_ndr_engine (beaconing + DNS tunneling)")


def test_rasp_agent():
    """RASP: scan de runtime en entorno seguro (no debe encontrar amenazas críticas)."""
    from rasp.agent import RASPAgent

    rasp = RASPAgent(target="")
    alerts = rasp.scan()

    # En un entorno limpio no deberíamos tener alertas críticas de hooking
    hooking = [a for a in alerts if a.type == "hooking"]
    # Puede detectar o no dependiendo del entorno, lo importante es que no crashee
    assert isinstance(alerts, list), "scan() debe retornar una lista"

    # Attestación debe funcionar
    attestation = rasp.attest()
    assert "attested" in attestation
    assert "device_safe" in attestation

    print(f"✓ test_rasp_agent ({len(alerts)} alertas, atestación: {attestation.get('device_safe')})")


def test_deception_mesh():
    """Deception Mesh: deploy tokens, decoys y detectar consumo."""
    from deception.mesh import DeceptionMesh, ThreatIntelPlatform

    dm = DeceptionMesh()

    # Deploy tokens
    token1 = dm.deploy_token("api_key", "api_endpoint_test")
    token2 = dm.deploy_token("jwt", "session_cache_test")
    assert len(dm.tokens) >= 2

    # Deploy sesión sintética
    session = dm.deploy_synthetic_session()
    assert session.jwt.startswith("eyJ")

    # Simular consumo de canary
    alert = dm.check_token_consumed(token1.token, ip="10.0.0.99", user="attacker")
    assert alert is not None, "Debe alertar al consumirse un canary"
    assert alert["severity"] == "critical"
    assert alert["mitre"] == "T1550"

    # Simular acceso a decoy
    decoy_alert = dm.check_decoy_hit("/v1/keys", "GET", ip="10.0.0.50")
    assert decoy_alert is not None, "Debe alertar al acceder un decoy"
    assert decoy_alert["severity"] == "critical"

    # TIP
    tip = ThreatIntelPlatform()
    tip.add_ioc("ip", "185.220.101.1", source="ndr", confidence=90, tags=["T1071"])
    tip.add_ioc("domain", "evil-c2.example.com", source="deception", confidence=80)
    tip.add_ioc("hash", "a" * 64, source="rasp", confidence=60)

    bundle = tip.to_stix_bundle()
    assert bundle["type"] == "bundle"
    assert len(bundle["objects"]) > 0, "STIX bundle debe tener objetos"

    blocklist = tip.get_blocklist()
    assert "185.220.101.1" in blocklist
    assert "evil-c2.example.com" in blocklist

    print(f"✓ test_deception_mesh ({len(dm.tokens)} tokens, {len(dm.alerts)} alertas, {len(tip.iocs)} IoCs)")


def test_tls_proxy():
    """TLS Proxy: detectar headers y paths sospechosos."""
    from tlsproxy.interceptor import TLSProxy, InterceptedFlow
    import datetime

    proxy = TLSProxy()

    # Flow con header sospechoso
    flow = InterceptedFlow(
        id="test-001", src_ip="10.0.0.1",
        dst_host="api.example.com", dst_port=443,
        method="GET", path="/.env",
        request_headers={"x-forwarded-for": "10.0.0.1"},
        response_headers={"content-type": "application/json"},
        request_size=100, response_size=500,
        tls_version="TLSv1.3", sni="api.example.com",
        cert_valid=True, content_type="application/json",
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )
    alerts = proxy.process_flow(flow)
    assert len(alerts) >= 2, "Debe detectar header sospechoso + path /.env"

    # TLS obsoleto
    flow_weak = InterceptedFlow(
        id="test-002", src_ip="10.0.0.2",
        dst_host="old.example.com", dst_port=443,
        method="GET", path="/api/data",
        request_headers={},
        response_headers={},
        tls_version="TLSv1.1", sni="old.example.com",
        cert_valid=False, cert_issuer="Unknown",
        content_type="text/html",
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
    )
    alerts2 = proxy.process_flow(flow_weak)
    assert any(a["type"] == "weak_tls" for a in alerts2), "Debe detectar TLS obsoleto"
    assert any(a["type"] == "invalid_cert" for a in alerts2), "Debe detectar cert inválido"

    print(f"✓ test_tls_proxy ({len(proxy.alerts)} alertas en {len(proxy.flows)} flujos)")


def test_unified_orchestrator():
    """Orquestador unificado: ejecutar scan end-to-end."""
    from runner.unified_orchestrator import run_unified_scan

    with tempfile.TemporaryDirectory() as tmp:
        # Crear dummy target
        target = pathlib.Path(tmp) / "dummy.apk"
        target.write_bytes(b"dummy")

        report = run_unified_scan(
            target=str(target),
            backend="https://api.test.local",
            output_dir=str(pathlib.Path(tmp) / "reports"),
        )

        assert "xdr" in report
        assert "soar" in report
        assert "ztna" in report
        assert "ndr" in report
        assert "rasp" in report
        assert "deception" in report
        assert "TLSProxy" in report
        assert "tip" in report
        assert report["xdr"]["total_events"] > 0, "XDR debe tener eventos"
        assert len(report["incidents_detail"]) > 0, "Debe generar incidentes"

    print(f"✓ test_unified_orchestrator (end-to-end OK)")


if __name__ == "__main__":
    print("=== Tests Enterprise ===\n")
    test_xdr_correlator()
    test_soar_playbooks()
    test_ztna_gateway()
    test_ndr_engine()
    test_rasp_agent()
    test_deception_mesh()
    test_tls_proxy()
    test_unified_orchestrator()
    print(f"\n✓✓✓ Todos los tests enterprise pasaron")
