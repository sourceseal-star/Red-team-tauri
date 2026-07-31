#!/usr/bin/env python3
"""
Termux Runner — Red Team Enterprise Agent con integridad sellada.

Verifica integridad antes de ejecutar cualquier módulo defensivo.
Si alguien modifica un JSON o config, la ejecución se BLOQUEA.

Uso:
    python3 scripts/termux_run.py seal                     # Sellar archivos críticos
    python3 scripts/termux_run.py verify                   # Verificar integridad
    python3 scripts/termux_run.py scan --target <apk>      # Scan enterprise (verifica primero)
    python3 scripts/termux_run.py tests                    # Tests enterprise
    python3 scripts/termux_run.py dashboard                # Dashboard web
    python3 scripts/termux_run.py rasp --target <apk>      # Solo RASP
    python3 scripts/termux_run.py ndr                      # Solo NDR
    python3 scripts/termux_run.py deception                # Solo Deception
    python3 scripts/termux_run.py ztna                     # Test ZTNA
    python3 scripts/termux_run.py status                   # Estado completo del sistema
"""
import os
import sys
import json
import pathlib
import subprocess
import platform

IS_TERMUX = os.path.exists("/data/data/com.termux/files/usr")
ROOT = pathlib.Path(__file__).resolve().parent.parent

if IS_TERMUX:
    os.environ.setdefault("TERMUX", "1")
    os.environ.setdefault("PORT", "8000")
    os.environ.setdefault("PYTHONPATH", str(ROOT))

sys.path.insert(0, str(ROOT))

from integrity.seal_manager import SealManager

seal_mgr = SealManager(root=str(ROOT))


def require_integrity():
    """Verifica integridad antes de ejecutar defensas. Bloquea si hay manipulación."""
    result = seal_mgr.verify_all()
    if result["status"] == "NOT_SEALED":
        print("[integrity] ⚠️  Sistema no sellado. Ejecuta 'seal' primero.")
        print("[integrity] Sellando ahora automáticamente...")
        seal_mgr.seal_all()
        print("[integrity] ✅ Sellado completo.\n")
        return True
    elif result["status"] != "VERIFIED":
        print("\n" + "=" * 60)
        print("🚨 INTEGRIDAD COMPROMETIDA — EJECUCIÓN BLOQUEADA")
        print("=" * 60)
        print(f"\n{result['message']}")
        for t in result.get("tampered", []):
            print(f"  ❌ {t['file']}: {t['reason']}")
        print("\nRestaurar:  git checkout -- .")
        print("Re-sellar:  python3 scripts/termux_run.py seal")
        print("=" * 60 + "\n")
        return False
    else:
        print(f"[integrity] ✅ {result['message']}\n")
        return True


def cmd_seal(args):
    """Sellado criptográfico de todos los archivos críticos."""
    print("[seal] Generando sellos SHA-256 + HMAC...")
    manifest = seal_mgr.seal_all()
    print(f"[seal] ✅ {manifest['total_files']} archivos sellados")
    print(f"[seal] Manifiesto: integrity/seals.json")
    print(f"[seal] Firma HMAC: {manifest['manifest_hmac'][:32]}...")
    print(f"[seal] Timestamp: {manifest['sealed_at']}")
    print()
    print("Archivos protegidos:")
    for path, info in manifest["seals"].items():
        print(f"  🔒 {path}  ({info['size']} bytes)")


def cmd_verify(args):
    """Verificar integridad de archivos sellados."""
    result = seal_mgr.verify_all()
    print("=" * 60)
    if result["status"] == "VERIFIED":
        print("✅ INTEGRIDAD VERIFICADA")
        print(f"   {result['message']}")
    elif result["status"] == "NOT_SEALED":
        print("⚠️  SISTEMA NO SELLADO")
        print(f"   {result['message']}")
    elif result["status"] == "MANIFEST_TAMPERED":
        print("🚨 MANIFIESTO DE SELLOS MANIPULADO")
        print(f"   {result['message']}")
    else:
        print("🚨 INTEGRIDAD COMPROMETIDA")
        print(f"   {result['message']}")
        print("\n   Archivos manipulados:")
        for t in result.get("tampered", []):
            print(f"     ❌ {t['file']}: {t['reason']}")
    print("=" * 60)


def cmd_status(args):
    """Estado completo del sistema."""
    print("=" * 60)
    print("RED TEAM ENTERPRISE — ESTADO DEL SISTEMA")
    print("=" * 60)
    
    # Integridad
    result = seal_mgr.verify_all()
    print(f"\n🔒 Integridad: {result['status']}")
    if result["status"] == "VERIFIED":
        print(f"   {result['message']}")
    
    # Entorno
    print(f"\n📱 Entorno: {'Termux/Android' if IS_TERMUX else platform.system()}")
    print(f"   Python: {platform.python_version()}")
    print(f"   Root: {ROOT}")
    
    # Módulos
    print("\n🛡️  Módulos defensivos:")
    modules = [
        ("RASP", "rasp.agent", "RASPAgent"),
        ("NDR", "ndr.engine", "NDREngine"),
        ("ZTNA", "ztna.gateway", "ZTNAGateway"),
        ("XDR", "xdr.correlator", "XDRCorrelator"),
        ("SOAR", "soar.engine", "SOAREngine"),
        ("SOAR DAG Engine", "soar.playbooks", "PlaybookExecutor"),
        ("Deception", "deception.mesh", "DeceptionMesh"),
        ("TLS Proxy", "tlsproxy.interceptor", "TLSProxy"),
        ("TIP", "tip.platform", "ThreatIntelPlatform"),
        ("STIX Exporter", "tip.stix_exporter", "StixExporter"),
        ("TAXII Client", "tip.taxii_client", "TaxiiClient"),
        ("NDR Behavioral", "ndr.behavioral", "BeaconingDetector"),
        ("Dyn. Deception", "deception.dynamic_mesh", "DynamicDeceptionMesh"),
        ("MITRE Correlator", "xdr.mitre_correlator", "EnhancedMITREMapper"),
        ("SOAR DAG", "soar.playbooks", "PlaybookDAG"),
        ("Attestation", "attestation.server", "AttestationServer"),
    ]
    for name, mod_path, cls_name in modules:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            getattr(mod, cls_name)
            print(f"   ✅ {name}")
        except Exception as e:
            print(f"   ❌ {name}: {e}")
    
    # Reportes
    reports_dir = ROOT / "reports"
    if reports_dir.exists():
        reports = list(reports_dir.glob("*.json")) + list(reports_dir.glob("*.md"))
        print(f"\n📊 Reportes: {len(reports)} archivos en reports/")
    
    print("\n" + "=" * 60)


def cmd_scan(args):
    """Scan enterprise unificado."""
    if not require_integrity():
        return
    
    target = args.get("--target") or str(ROOT / "evidence" / "dummy.apk")
    backend = args.get("--backend") or os.environ.get("SOURCESEAL_API", "")
    output = args.get("--output") or str(ROOT / "reports")

    from runner.unified_orchestrator import run_unified_scan
    report = run_unified_scan(target, backend, output)
    print(f"\n[termux] Reporte: {output}")
    return report


def cmd_tests(args):
    """Tests enterprise."""
    if not require_integrity():
        return
    test_file = ROOT / "tests" / "test_enterprise.py"
    result = subprocess.run([sys.executable, str(test_file)], cwd=str(ROOT))
    return result.returncode == 0


def cmd_dashboard(args):
    """Dashboard web."""
    if not require_integrity():
        return
    port = args.get("--port") or os.environ.get("PORT", "8000")
    os.environ["PORT"] = port
    print(f"[termux] Dashboard en http://localhost:{port}")
    dashboard = ROOT / "scripts" / "dashboard_server.py"
    subprocess.run([sys.executable, str(dashboard)], cwd=str(ROOT))


def cmd_rasp(args):
    """Solo RASP scan."""
    if not require_integrity():
        return
    from rasp.agent import RASPAgent
    target = args.get("--target") or str(ROOT / "evidence" / "dummy.apk")
    agent = RASPAgent(target=target)
    alerts = agent.scan()
    attestation = agent.attest()
    print(f"\n=== RASP Scan ===")
    print(f"Target: {target}")
    print(f"Alertas: {len(alerts)}")
    for a in alerts:
        print(f"  [{a.severity.upper()}] {a.type}: {a.detail}")
    print(f"\nAtestación: {attestation.get('attested', False)}")
    print(f"Dispositivo seguro: {attestation.get('device_safe', False)}")
    if not attestation.get("attested"):
        print(f"Issues: {attestation.get('issues', [])}")


def cmd_ndr(args):
    """NDR test."""
    if not require_integrity():
        return
    from ndr.engine import NDREngine, TrafficFlow
    import time
    ndr = NDREngine()
    print("\n=== NDR Test ===")
    print("Simulando C2 beaconing...")
    base = time.time()
    for i in range(6):
        flow = TrafficFlow(
            src_ip="10.0.0.1", dst_ip="185.220.101.1", dst_port=443,
            protocol="TCP", bytes_sent=500, bytes_received=50,
            timestamp=base + i * 30,
        )
        ndr.ingest_flow(flow)
    ndr.ingest_flow(TrafficFlow(
        src_ip="10.0.0.2", dst_ip="8.8.8.8", dst_port=53,
        protocol="DNS", bytes_sent=250, bytes_received=100,
        timestamp=time.time(),
    ))
    summary = ndr.get_summary()
    print(f"\nAlertas: {summary['total_alerts']}")
    for t, c in summary["by_type"].items():
        print(f"  {t}: {c}")
    print(f"MITRE: {', '.join(summary['mitre_techniques'])}")


def cmd_deception(args):
    """Deception mesh."""
    if not require_integrity():
        return
    from deception.mesh import DeceptionMesh
    dm = DeceptionMesh()
    print("\n=== Deception Mesh ===")
    for t in ["api_key", "jwt", "dns"]:
        token = dm.deploy_token(t, f"termux_{t}")
        print(f"  Token {t}: {token.token[:30]}...")
    for _ in range(3):
        s = dm.deploy_synthetic_session()
        print(f"  Sesión: {s.jwt[:40]}...")
    print(f"\n  Decoys: {len(dm.decoys)}")
    print(f"  Resumen: {dm.get_summary()}")


def cmd_ztna(args):
    """Test ZTNA con casos reales."""
    if not require_integrity():
        return
    from ztna.gateway import ZTNAGateway, AccessRequest, AccessDecision
    ztna = ZTNAGateway()
    ztna.block_ip("10.0.0.99")
    tests = [
        ("Student → /api/courses", "1", "student", "/api/courses", "GET", True, "10.0.0.1", "1"),
        ("Student → /api/admin (denegado)", "2", "student", "/api/admin/seals", "GET", True, "10.0.0.2", "2"),
        ("CEO → /api/admin/seals", "5", "ceo", "/api/admin/seals", "GET", True, "10.0.0.5", "5"),
        ("BOLA: recurso ajeno", "3", "student", "/api/courses/123", "GET", True, "10.0.0.3", "otro"),
        ("IP bloqueada SOAR", "6", "student", "/api/courses", "GET", True, "10.0.0.99", "6"),
    ]
    print("\n=== ZTNA Gateway — Tests ABAC ===\n")
    for desc, uid, role, ep, method, attested, ip, owner in tests:
        req = AccessRequest(
            user_id=uid, user_hash=f"hash_{uid}", role=role,
            endpoint=ep, method=method, device_attested=attested,
            ip_address=ip, resource_owner_id=owner,
        )
        decision, reason, _ = ztna.evaluate(req)
        emoji = "✅" if decision == AccessDecision.ALLOW else "🚫"
        print(f"  {emoji} {desc}")
        print(f"     → {decision.value}: {reason}")


def main():
    args = {}
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return

    command = argv[0]
    i = 1
    while i < len(argv):
        if argv[i].startswith("--"):
            key = argv[i]
            val = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else ""
            args[key] = val
            i += 2
        else:
            i += 1

    commands = {
        "seal": cmd_seal,
        "verify": cmd_verify,
        "status": cmd_status,
        "scan": cmd_scan,
        "tests": cmd_tests,
        "dashboard": cmd_dashboard,
        "rasp": cmd_rasp,
        "ndr": cmd_ndr,
        "deception": cmd_deception,
        "ztna": cmd_ztna,
    }

    if command in commands:
        commands[command](args)
    else:
        print(f"Comando desconocido: {command}")
        print(f"Comandos: {', '.join(commands.keys())}")


if __name__ == "__main__":
    main()
