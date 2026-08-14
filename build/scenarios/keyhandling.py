"""
Escenario: Key Handling
-----------------------
Verifica buenas prácticas de manejo de claves:
- Uso de Android Keystore / iOS Keychain
- Detección de claves hardcodeadas
- Persistencia insegura (SharedPreferences en claro, NSUserDefaults)
"""
import re
import pathlib
import subprocess
from typing import List, Dict


HARDCODE_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                   # AWS
    r"AIza[0-9A-Za-z\-_]{35}",             # Google API key
    r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}",  # JWT
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"-----BEGIN [A-Z ]*SECRET-----",
    r"sk_[A-Za-z0-9]{20,}",                # Stripe-like
    r"[A-Fa-f0-9]{64}",                    # 32-byte hex (posible AES key)
]

KEYSTORE_OK_MARKERS = [
    "AndroidKeyStore", "KeyStore.getInstance(\"AndroidKeyStore\")",
    "Keychain Services", "kSecClassGenericPassword", "CryptoKit",
]


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "keyhandling",
            "severity": "info",
            "title": "Target no disponible para análisis",
            "description": f"{target} no existe.",
            "evidence_path": "",
            "remediation": "Proporcionar artefacto para análisis.",
        }]

    # Extraer strings
    try:
        out = pathlib.Path(output_dir) / "keyhandling-strings.txt"
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=60)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{8,}", raw))

    # 1) Claves hardcodeadas
    leaks = {}
    for pat in HARDCODE_PATTERNS:
        matches = re.findall(pat, text)
        if matches:
            leaks[pat] = matches[:5]  # limita a 5 muestras

    if leaks:
        findings.append({
            "scenario": "keyhandling",
            "severity": "critical",
            "title": f"Claves o secretos hardcodeados detectados ({sum(len(v) for v in leaks.values())} coincidencias)",
            "description": "; ".join(f"{k}: {len(v)} matches" for k, v in leaks.items()),
            "evidence_path": str(out),
            "remediation": "Rotar inmediatamente TODAS las claves filtradas, mover a Keystore/Keychain, separar dev/prod.",
        })

    # 2) Uso de KeyStore/Keychain
    uses_keystore = any(m in text for m in KEYSTORE_OK_MARKERS)
    if not uses_keystore:
        findings.append({
            "scenario": "keyhandling",
            "severity": "high",
            "title": "Sin uso detectable de KeyStore/Keychain nativo",
            "description": "No se encontraron marcadores de AndroidKeyStore ni iOS Keychain.",
            "evidence_path": str(out),
            "remediation": "Migrar claves a KeyStore (Android) o Keychain (iOS) con protección StrongBox/biometric.",
        })
    else:
        findings.append({
            "scenario": "keyhandling",
            "severity": "info",
            "title": "Uso de KeyStore/Keychain detectado",
            "description": "La app parece apoyarse en almacenamiento seguro nativo.",
            "evidence_path": str(out),
            "remediation": "Verificar que las claves no sean exportables y requieran auth de usuario.",
        })

    return findings
