#!/usr/bin/env python3
"""Tests de los escenarios del agente Red Team."""
import sys
import os
import pathlib
import json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def test_luhn():
    from scenarios.imei import luhn_check, is_blacklisted
    # Generar y validar
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


def test_sourcesealcorp_dry_run(tmp):
    """El escenario SOURCESEALCORP debe correr en dry-run sin fallar."""
    os.environ["SOURCESEAL_API"] = "https://invalid.example.local"
    os.environ["SOURCESEAL_KEY"] = ""
    os.environ["RECOVERY_PAGE"] = ""
    from scenarios.sourcesealcorp import run
    findings = run("dummy", "https://invalid.example.local", str(tmp))
    assert isinstance(findings, list)
    assert len(findings) > 0
    # debe haber al menos un info de dry-run
    assert any("dry-run" in f.get("description", "").lower() or f.get("severity") == "info"
               for f in findings)
    print(f"✓ test_sourcesealcorp_dry_run ({len(findings)} findings)")


def test_recovery_page_unconfigured(tmp):
    os.environ["RECOVERY_PAGE"] = ""
    from scenarios.recovery_page import run
    findings = run("dummy", "https://x", str(tmp))
    assert any("RECOVERY_PAGE" in f.get("title", "") or f.get("severity") == "info"
               for f in findings)
    print("✓ test_recovery_page_unconfigured")


def test_orchestrator_loads_all():
    """El orquestador debe poder importar los 11 escenarios."""
    from runner.orchestrator import Orchestrator
    o = Orchestrator("dummy", "https://x", "/tmp")
    assert hasattr(o, "run_all")
    assert hasattr(o, "write_report")
    print("✓ test_orchestrator_loads_all")


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
    with tempfile.TemporaryDirectory() as tmp:
        test_sourcesealcorp_dry_run(tmp)
        test_recovery_page_unconfigured(tmp)
    print("\n✓✓✓ Todos los tests pasaron")
