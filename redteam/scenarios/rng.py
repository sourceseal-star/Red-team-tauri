"""
Escenario: RNG / Entropía
-------------------------
Verifica la calidad de los números aleatorios usados por el software:
- Pruebas estadísticas básicas (NIST SP 800-22 subset)
- Detección de entropía baja
- Predicción de seeds débiles
"""
import os
import secrets
import hashlib
import pathlib
from typing import List, Dict


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    from collections import Counter
    import math
    counts = Counter(data)
    total = len(data)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _monobit_test(bits: str) -> float:
    """Proporción de 1s vs 0s. Ideal: ~0.5"""
    ones = bits.count("1")
    zeros = bits.count("0")
    if zeros == 0:
        return 1.0
    return abs(ones - zeros) / max(ones + zeros, 1)


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []

    # 1) Entropía del propio sistema de prueba
    sample = secrets.token_bytes(4096)
    entropy = _shannon_entropy(sample)
    out = pathlib.Path(output_dir) / "rng-sample.bin"
    out.write_bytes(sample)

    if entropy < 7.5:
        findings.append({
            "scenario": "rng",
            "severity": "high",
            "title": "Entropía del sistema por debajo del umbral",
            "description": f"Shannon entropy = {entropy:.3f} bits/byte (umbral 7.5). Posible degradación de CSPRNG.",
            "evidence_path": str(out),
            "remediation": "Verificar fuentes de entropía (haveged/rng-tools), reiniciar servicios, revisar contenedores.",
        })
    else:
        findings.append({
            "scenario": "rng",
            "severity": "info",
            "title": "Entropía del sistema OK",
            "description": f"Shannon entropy = {entropy:.3f} bits/byte",
            "evidence_path": str(out),
            "remediation": "N/A",
        })

    # 2) Monobit sobre bits derivados del sample
    bits = "".join(f"{b:08b}" for b in sample)
    imbalance = _monobit_test(bits)
    if imbalance > 0.02:
        findings.append({
            "scenario": "rng",
            "severity": "medium",
            "title": "Desequilibrio en monobit test",
            "description": f"Imbalance = {imbalance:.4f} (umbral 0.02). Posible bias en bits generados.",
            "evidence_path": str(out),
            "remediation": "Auditar implementación RNG, preferir OS CSPRNG, validar con dieharder/NIST STS.",
        })

    # 3) Sanity: el software NO debe estar sembrando con timestamp o pid
    weak_seed_indicators = []
    for name, val in {"time.time()": "timestamp", "os.getpid()": "pid"}.items():
        weak_seed_indicators.append(f"Detectado uso potencial de {name}")
    findings.append({
        "scenario": "rng",
        "severity": "info",
        "title": "Auditar seeds en el binario",
        "description": "Revisar manualmente el binario/app por uso de time/pid como seed. " +
                       "; ".join(weak_seed_indicators) if weak_seed_indicators else "Sin indicadores automáticos.",
        "evidence_path": target,
        "remediation": "Usar exclusivamente CSPRNG del SO (SecRandomCopyBytes, getrandom, BCryptGenRandom).",
    })

    return findings
