"""
Escenario: Side-Channel
-----------------------
Detecta:
- Mensajes de error con tiempos distinguibles (timing attack a comparar/validar)
- Uso de comparación no constante (==, memcmp) en lugar de constant-time
- Logs que filtran material criptográfico
"""
import re
import pathlib
from typing import List, Dict


# Patrones de funciones de comparación constante-tiempo (bueno)
CONST_TIME_OK = [
    r"\bCRYPTO_memcmp\b",
    r"\bsodium_memcmp\b",
    r"\bcrypto_verify\b",
    r"\bhmac\.compare_digest\b",
    r"\bMessageDigest\.isEqual\b",
    r"\bCT\.mem_equal\b",
]

# Patrones de comparación naive (malo en contexto cripto)
CONST_TIME_BAD = [
    r"==\s*[A-Za-z_][A-Za-z0-9_]*\s*==\s*['\"]?expected",
    r"\.equals\s*\(\s*expected",
    r"memcmp\s*\(",
]


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "sidechannel",
            "severity": "info",
            "title": "Target no accesible para análisis estático",
            "description": f"{target} no existe; saltando side-channel estático.",
            "evidence_path": "",
            "remediation": "Proporcionar APK/IPA o código fuente.",
        }]

    # Strings: usar 'strings' o fallback
    try:
        import subprocess
        out = pathlib.Path(output_dir) / "sidechannel-strings.txt"
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=3)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{6,}", raw))

    bad_hits = []
    for pat in CONST_TIME_BAD:
        bad_hits.extend(re.findall(pat, text))

    if bad_hits:
        findings.append({
            "scenario": "sidechannel",
            "severity": "high",
            "title": "Posible comparación NO constante de material criptográfico",
            "description": f"{len(bad_hits)} matches de patrones de comparación naive. Riesgo de timing attack.",
            "evidence_path": str(out),
            "remediation": "Sustituir por hmac.compare_digest / MessageDigest.isEqual / CRYPTO_memcmp según lenguaje.",
        })
    else:
        findings.append({
            "scenario": "sidechannel",
            "severity": "info",
            "title": "Sin comparación naive evidente",
            "description": "No se detectaron patrones sospechosos en el análisis estático.",
            "evidence_path": str(out),
            "remediation": "Validar con microbenchmarks (medir tiempo en comparaciones válidas vs inválidas).",
        })

    # Detección de logs que filtran keys/tokens
    leak_patterns = [
        r"private[_-]?key", r"secret[_-]?key", r"api[_-]?token",
        r"password\s*=\s*['\"]", r"BEGIN PRIVATE KEY", r"BEGIN RSA",
    ]
    leaks = [p for p in leak_patterns if re.search(p, text, re.IGNORECASE)]
    if leaks:
        findings.append({
            "scenario": "sidechannel",
            "severity": "critical",
            "title": "Posible filtración de material criptográfico en strings",
            "description": f"Patrones detectados: {', '.join(leaks)}",
            "evidence_path": str(out),
            "remediation": "Eliminar logs en producción, cifrar material en reposo, usar KeyStore/Keychain.",
        })

    return findings
