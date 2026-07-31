#!/usr/bin/env python3
"""Tests de los escenarios del agente Red Team.

v2.1 (2026-07-27): Agrega tests para el fix bug "Skipped vs Failed":
  - test_sourcesealcorp_offline
  - test_orchestrator_aggregates_skipped
  - test_orchestrator_mixed_status
"""
import sys
import os
import pathlib
import json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def test_luhn():
    from scenarios.imei import luhn_check, is_blacklisted
    def make(prefix):
        digits = [int(d) for d in prefix[:14]]
        total = 0
        for i, d in enumerate(digits):
            if i % 2 == 0:
                d *= 2
                if d > 9: d -= 9
            total += d
        check = (10 - (total % 10)) % 10
        return prefix[:14] + str(check)
    h = make("35693803564380")
    assert luhn_check(h), f"{h} debe pasar"
    assert not luhn_check("123456789012345")
    assert is_blacklisted("356938035643800")
    print("✓ test_luhn")


def test_sourcesealcorp_dry_run(tmp_path):
    """El escenario SOURCESEALCORP debe correr en dry-run sin lanzar excepciones
    y todos los findings deben ser info o skipped (NUNCA high/critical por offline)."""
    os.environ["SOURCESEAL_API"] = "https://invalid.example.local"
    os.environ["SOURCESEAL_KEY"] = ""
    os.environ["RECOVERY_PAGE"] = ""
    # Forzar reimport para que tome el nuevo env
    if "scenarios.sourcesealcorp" in sys.modules:
        del sys.modules["scenarios.sourcesealcorp"]
    from scenarios.sourcesealcorp import run
    findings = run("dummy", "https://invalid.example.local", str(tmp_path))
    assert isinstance(findings, list), "run() debe devolver lista"
    assert len(findings) > 0, "run() debe devolver al menos un finding"
    # FIX verificado: ningún finding puede ser high/critical cuando el backend no responde
    for f in findings:
        assert f.get("severity") not in ("high", "critical"), (
            f"Finding '{f.get('title')}' tiene severity={f.get('severity')} "
            f"con backend offline — esto es un falso positivo"
        )
    # Debe haber al menos un finding info (el agregado de skipped)
    assert any(f.get("severity") == "info" for f in findings), (
        "Debe haber al menos un finding info cuando el backend no responde"
    )
    print(f"✓ test_sourcesealcorp_dry_run ({len(findings)} findings, todos info/skipped)")


# ── TESTS NUEVOS — Bug "Skipped vs Failed" ────────────────────────────────────

def test_sourcesealcorp_offline(tmp_path):
    """
    NUEVO v2.1: Verifica que cuando SOURCESEAL_API no responde,
    TODOS los ataques devuelven status='skipped' (no 'fail').
    Esto previene falsos positivos HIGH en el reporte.
    """
    os.environ["SOURCESEAL_API"] = "http://hostname-invalido-que-no-existe-redteam.local:5000"
    os.environ["SOURCESEAL_KEY"] = ""
    os.environ["RECOVERY_PAGE"] = ""
    os.environ["SOURCESEAL_NODE"] = ""
    if "scenarios.sourcesealcorp" in sys.modules:
        del sys.modules["scenarios.sourcesealcorp"]
    from scenarios.sourcesealcorp import (
        attack_A1_hash_reuse, attack_A2_timelock_bypass,
        attack_A4_rate_limit, attack_A5_signature, attack_A6_replay,
    )
    import pathlib as _p

    evidence = _p.Path(str(tmp_path))

    # Testear cada ataque individualmente
    attacks_to_test = [
        ("A1", attack_A1_hash_reuse("http://hostname-invalido-que-no-existe-redteam.local:5000",
                                     "", "x" * 64, evidence)),
        ("A2", attack_A2_timelock_bypass("http://hostname-invalido-que-no-existe-redteam.local:5000",
                                          "", "x" * 64, evidence)),
        ("A4", attack_A4_rate_limit("http://hostname-invalido-que-no-existe-redteam.local:5000",
                                     "", evidence)),
        ("A5", attack_A5_signature("http://hostname-invalido-que-no-existe-redteam.local:5000",
                                    evidence)),
        ("A6", attack_A6_replay("http://hostname-invalido-que-no-existe-redteam.local:5000",
                                 "", "x" * 64, evidence)),
    ]

    for attack_id, result in attacks_to_test:
        # Cada ataque con backend offline debe ser skipped
        assert result.get("status") == "skipped", (
            f"{attack_id}: esperaba status='skipped', got status='{result.get('status')}' "
            f"(passed={result.get('passed')}) — esto es el bug AV-skipped-vs-failed"
        )
        assert result.get("actual") is None, (
            f"{attack_id}: actual debe ser None en skipped, got {result.get('actual')}"
        )
        assert result.get("passed") is None, (
            f"{attack_id}: passed debe ser None en skipped, got {result.get('passed')} "
            f"— passed=False causa falsos positivos HIGH"
        )
        assert result.get("reason") is not None, (
            f"{attack_id}: debe tener campo 'reason' explicando por qué fue skipped"
        )
        reason_lower = result["reason"].lower()
        assert any(kw in reason_lower for kw in ("no accesible", "dns", "timeout", "refused")), (
            f"{attack_id}: reason debe mencionar conectividad, got: '{result['reason']}'"
        )

    # Verificar también que el run() completo no genera findings HIGH
    if "scenarios.sourcesealcorp" in sys.modules:
        del sys.modules["scenarios.sourcesealcorp"]
    from scenarios.sourcesealcorp import run
    all_findings = run("dummy", "http://hostname-invalido-que-no-existe-redteam.local:5000", str(tmp_path))

    high_or_critical = [f for f in all_findings if f.get("severity") in ("high", "critical")]
    assert len(high_or_critical) == 0, (
        f"Con backend offline no debe haber findings HIGH/CRITICAL, "
        f"pero se encontraron: {[f['title'] for f in high_or_critical]}"
    )

    print(f"✓ test_sourcesealcorp_offline — {len(attacks_to_test)} ataques todos skipped, "
          f"0 falsos HIGH en run()")


def test_orchestrator_aggregates_skipped():
    """
    NUEVO v2.1: Verifica que cuando TODOS los ataques de sourcesealcorp están skipped,
    run() emite 1 solo hallazgo info (no N hallazgos HIGH falsos).
    """
    import tempfile
    if "scenarios.sourcesealcorp" in sys.modules:
        del sys.modules["scenarios.sourcesealcorp"]

    os.environ["SOURCESEAL_API"] = "http://hostname-invalido-que-no-existe-redteam.local:5000"
    os.environ["SOURCESEAL_KEY"] = ""
    os.environ["RECOVERY_PAGE"] = ""
    os.environ["SOURCESEAL_NODE"] = ""

    from scenarios.sourcesealcorp import run

    with tempfile.TemporaryDirectory() as tmp:
        findings = run("dummy", "http://offline.local:5000", tmp)

    # Debe haber exactamente 1 finding info
    assert len(findings) == 1, (
        f"Con todos skipped debe haber 1 finding agregado, got {len(findings)}: "
        f"{[f['title'] for f in findings]}"
    )
    f = findings[0]
    assert f["severity"] == "info", (
        f"El finding agregado debe ser 'info', got '{f['severity']}'"
    )
    title_lower = f["title"].lower()
    assert "no evaluado" in title_lower or "no accesible" in title_lower, (
        f"El título debe indicar que no fue evaluado, got: '{f['title']}'"
    )
    desc_lower = f["description"].lower()
    assert "no responde" in desc_lower or "no accesible" in desc_lower or "backend" in desc_lower, (
        f"La descripción debe mencionar el backend, got: '{f['description']}'"
    )
    print(f"✓ test_orchestrator_aggregates_skipped — 1 finding info, sin HIGH falsos")


def test_orchestrator_mixed_status(tmp_path):
    """
    NUEVO v2.1: Verifica que cuando hay mezcla (algunos skipped, otros pass/fail),
    run() emite hallazgos individuales (no el finding agregado de 'todos skipped').
    También verifica que los skipped individuales son INFO, no HIGH.
    """
    # Simular escenario donde A1 pasa, A2 falla, A3 es skipped
    # Esto se logra mockeando _request en el módulo
    import unittest.mock as mock
    if "scenarios.sourcesealcorp" in sys.modules:
        del sys.modules["scenarios.sourcesealcorp"]

    import scenarios.sourcesealcorp as ssc

    call_count = [0]

    def mock_request(method, url, body=None, key="", extra_headers=None, timeout=3):
        call_count[0] += 1
        # Primera llamada (A1): devolver 409 → pass
        if call_count[0] <= 2:
            return {"ok": False, "status": 409, "error": "Conflict"}
        # Segunda llamada (A2): devolver 200 → fail
        elif call_count[0] == 3:
            return {"ok": True, "status": 200, "response": "ok"}
        # Resto: backend offline → skipped
        else:
            return {"ok": None, "status": 0, "error": "Connection refused", "dry_run": True}

    with mock.patch.object(ssc, "_request", mock_request):
        findings = ssc.run("dummy", "http://mixed.test:5000", str(tmp_path))

    # No debe ser el finding único de "todos skipped"
    assert not (len(findings) == 1 and "no evaluado" in findings[0]["title"].lower()), (
        "Con mezcla de estados no debe emitir el finding agregado de 'todos skipped'"
    )

    # Ningún finding de un ataque skipped debe ser HIGH
    for f in findings:
        if "no ejecutado" in f["title"].lower() or "no evaluado" in f["title"].lower():
            assert f["severity"] == "info", (
                f"Finding skipped '{f['title']}' tiene severity='{f['severity']}', "
                f"debe ser 'info'"
            )

    print(f"✓ test_orchestrator_mixed_status — {len(findings)} hallazgos individuales, "
          f"skipped son info")


def test_recovery_page_unconfigured(tmp_path):
    os.environ["RECOVERY_PAGE"] = ""
    from scenarios.recovery_page import run
    findings = run("dummy", "https://x", str(tmp_path))
    assert any("RECOVERY_PAGE" in f.get("title", "") or f.get("severity") == "info"
               for f in findings)
    print("✓ test_recovery_page_unconfigured")


def test_orchestrator_loads_all():
    """El orquestador debe poder importar correctamente."""
    from runner.orchestrator import Orchestrator
    o = Orchestrator("dummy", "https://x", "/tmp")
    assert hasattr(o, "run_all")
    assert hasattr(o, "write_report")
    # v2.1: verificar que Finding tiene campo status
    from runner.orchestrator import Finding
    import inspect
    fields = [f.name for f in Finding.__dataclass_fields__.values()]
    assert "status" in fields, "Finding debe tener campo 'status' en v2.1"
    print("✓ test_orchestrator_loads_all (incluyendo campo status en Finding)")


def test_payments_patterns():
    """Validar que los patrones de payments detectan keys conocidas."""
    from scenarios.payments import PROVIDER_MARKERS
    import re
    fake = "sk_live_XXXX_PLACEHOLDER_TEST_KEY"
    hits = re.findall(PROVIDER_MARKERS["stripe"][0], fake)
    assert len(hits) == 1
    print("✓ test_payments_patterns")


if __name__ == "__main__":
    import tempfile
    test_luhn()
    test_payments_patterns()
    test_orchestrator_loads_all()
    test_orchestrator_aggregates_skipped()
    with tempfile.TemporaryDirectory() as tmp:
        test_sourcesealcorp_dry_run(tmp)
        test_sourcesealcorp_offline(tmp)
        test_orchestrator_mixed_status(tmp)
        test_recovery_page_unconfigured(tmp)
    print("\n✓✓✓ Todos los tests pasaron")
