"""
Escenario: Biometría con Hash Criptográfico Único
---------------------------------------------------
Tu app usa hash criptográfico único para biometría (recuperable vía panel).
Esto es un modelo de cifrado reversible, NO un hash puro. Ataques a probar:

- Colisiones: si el algoritmo es débil, dos biometrías distintas pueden producir
  el mismo "hash" → acceso cruzado
- Fuerza bruta offline: si la base de hashes se filtra, ¿se puede revertir?
- Página de recuperación: ¿está protegida con MFA? ¿La respuesta se loggea?
- Plantillas biométricas: ¿se almacenan en claro o cifradas en reposo?
- Bypass del check local: el flag "biometric OK" no debe ser decisión del cliente
"""
import re
import subprocess
import pathlib
import hashlib
from typing import List, Dict


# Patrones típicos de templates biométricos que NO deberían aparecer en strings
BIOMETRIC_RAW_MARKERS = [
    r"finger[_-]?print[_-]?template",
    r"face[_-]?id[_-]?template",
    r"iris[_-]?template",
    r"biometric[_-]?raw",
]

# Algoritmos de hash criptográfico aceptables para hash "recuperable" (en realidad cifrado)
ACCEPTABLE_KDF = ["bcrypt", "argon2", "scrypt", "pbkdf2", "hkdf"]
WEAK_KDF = ["md5", "sha1", "sha256", "crc32"]  # SHA-256 NO es recuperable, es señal de confusion


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "biometric",
            "severity": "info",
            "title": "Target no disponible",
            "description": f"{target} no existe; saltando análisis biométrico.",
            "evidence_path": "",
            "remediation": "Proporcionar artefacto.",
        }]

    try:
        out = pathlib.Path(output_dir) / "biometric-strings.txt"
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=3)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{8,}", raw))

    # 1) Templates biométricos en claro
    raw_hits = [p for p in BIOMETRIC_RAW_MARKERS if re.search(p, text, re.IGNORECASE)]
    if raw_hits:
        findings.append({
            "scenario": "biometric",
            "severity": "critical",
            "title": "Posible almacenamiento de templates biométricos sin cifrar",
            "description": f"Marcadores: {', '.join(raw_hits)}",
            "evidence_path": str(out),
            "remediation": "Templates SIEMPRE cifrados en reposo. Usar TEE/StrongBox (Android) o Secure Enclave (iOS).",
        })

    # 2) Hash/derivación criptográfica
    found_kdf = [k for k in ACCEPTABLE_KDF if k in text.lower()]
    found_weak = [k for k in WEAK_KDF if k in text.lower()]

    if "sha256" in text.lower() and "argon2" not in text.lower() and "bcrypt" not in text.lower():
        findings.append({
            "scenario": "biometric",
            "severity": "high",
            "title": "Uso de SHA-256 (no recuperable) para biometría — ¿modelo de cifrado claro?",
            "description": "SHA-256 detectado pero no es reversible. Si el modelo es 'hash único recuperable', "
                           "debería ser cifrado simétrico (AES) + KDF, no SHA.",
            "evidence_path": str(out),
            "remediation": "Confirmar arquitectura: si es cifrado AES, separar clave maestra por usuario. "
                           "Si es hash, NO es recuperable — el modelo necesita re-diseño.",
        })

    if found_weak and not found_kdf:
        findings.append({
            "scenario": "biometric",
            "severity": "medium",
            "title": "Solo algoritmos débiles de derivación detectados",
            "description": f"Detectados: {', '.join(found_weak)}. Sin KDF fuerte (argon2/bcrypt).",
            "evidence_path": str(out),
            "remediation": "Usar Argon2id o HKDF con sal por usuario y work factor ajustado al dispositivo.",
        })

    # 3) Página de recuperación — buscar endpoints típicos
    recovery_endpoints = re.findall(r"https?://[^\s'\"]*(recover|reset|biometric|hash)[^\s'\"]*",
                                     text, re.IGNORECASE)
    if recovery_endpoints:
        findings.append({
            "scenario": "biometric",
            "severity": "info",
            "title": f"Endpoints de recuperación biométrica detectados ({len(recovery_endpoints)})",
            "description": "Endpoints: " + ", ".join(set(recovery_endpoints[:5])),
            "evidence_path": str(out),
            "remediation": "Validar: requiere MFA? rate limit? audit log? quien tiene acceso al panel?",
        })

    # 4) Verificación de integridad — el "flag" biométrico NO debe ser decisión del cliente
    flag_patterns = [r"isBiometricValid\s*=\s*true", r"biometricOk\s*=\s*1", r"skipBiometricCheck"]
    if any(re.search(p, text, re.IGNORECASE) for p in flag_patterns):
        findings.append({
            "scenario": "biometric",
            "severity": "critical",
            "title": "Bypass potencial del check biométrico en cliente",
            "description": "Patrones de override de flag biométrico detectados. Un atacante con acceso al "
                           "dispositivo podría saltarse la verificación.",
            "evidence_path": str(out),
            "remediation": "Verificación biométrica SIEMPRE server-side. Cliente solo captura y envía template cifrado.",
        })

    return findings
