"""
Escenario: Validación de IMEI
-----------------------------
Para una app de ventas de celulares, el IMEI es un dato central.

Ataques:
- Luhn check ausente: aceptar IMEIs malformados → fraude de inventario
- Duplicación: mismo IMEI vendido dos veces (robo)
- IMEI inválido/tachado: terminados en 00 son inválidos
- Predicción: si el IMEI se genera, ¿es predecible?
- TAC lookup: el IMEI revela fabricante/modelo → no se debe confiar
"""
import re
import pathlib
from typing import List, Dict


def luhn_check(imei: str) -> bool:
    """Implementa Luhn estándar. IMEI tiene 15 dígitos, último es check."""
    if not re.fullmatch(r"\d{15}", imei):
        return False
    digits = [int(d) for d in imei]
    # Luhn: doblar cada 2do desde la derecha, excepto el check
    total = 0
    for i, d in enumerate(digits[:-1]):
        if i % 2 == 0:  # posiciones pares desde la derecha
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (total + digits[-1]) % 10 == 0


def is_blacklisted(imei: str) -> bool:
    """IMEI inválido por convención (últimos dos dígitos 00)."""
    return imei.endswith("00")


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "imei",
            "severity": "info",
            "title": "Target no disponible",
            "description": f"{target} no existe.",
            "evidence_path": "",
            "remediation": "Proporcionar artefacto.",
        }]

    # 1) Búsqueda de IMEIs en el binario (puede haber fixtures, ejemplos, leaks)
    try:
        out = pathlib.Path(output_dir) / "imei-strings.txt"
        import subprocess
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=3)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{8,}", raw))

    imei_candidates = re.findall(r"\b\d{15}\b", text)
    if imei_candidates:
        valid = sum(1 for i in imei_candidates if luhn_check(i))
        invalid = len(imei_candidates) - valid
        findings.append({
            "scenario": "imei",
            "severity": "high" if invalid > valid else "medium",
            "title": f"IMEIs encontrados en binario ({len(imei_candidates)} candidatos)",
            "description": f"Válidos (Luhn): {valid}, Inválidos: {invalid}. "
                           "Si hay inválidos aceptados, se pueden inyectar IMEIs malformados en inventario.",
            "evidence_path": str(out),
            "remediation": "Validar Luhn server-side. Si son fixtures, usar placeholders explícitos (no reales).",
        })

    # 2) ¿La app valida Luhn? Buscamos la implementación
    has_luhn = any(m in text for m in [
        "luhn", "Luhn", "LUHN", "checkDigit", "imei_check",
    ])
    if not has_luhn:
        findings.append({
            "scenario": "imei",
            "severity": "medium",
            "title": "Sin evidencia de validación Luhn de IMEI",
            "description": "No se encontraron marcadores de algoritmo Luhn. Riesgo: aceptar IMEIs malformados.",
            "evidence_path": str(out),
            "remediation": "Implementar Luhn check antes de aceptar IMEI. Validar también TAC (primeros 8 dígitos) "
                           "contra base de GSMA.",
        })

    # 3) IMEI blacklist check
    if "blacklist" not in text.lower() and "stolen" not in text.lower() and "gsma" not in text.lower():
        findings.append({
            "scenario": "imei",
            "severity": "medium",
            "title": "Sin evidencia de consulta a blacklist (IMEI robado/perdido)",
            "description": "No se detectan referencias a GSMA blacklist. Riesgo: vender celular reportado como robado.",
            "evidence_path": str(out),
            "remediation": "Integrar API de blacklist (GSMA, Stolen Phone Check, etc.) antes de aceptar IMEI.",
        })

    return findings
