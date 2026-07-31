"""
Escenario: Multiplataforma (Android, iOS, Windows, Linux, Ubuntu Server)
------------------------------------------------------------------------
Verifica que la lógica criptográfica sea consistente entre plataformas
y que no haya debilidades introducidas por portabilidad.

- Longitud de clave consistente (AES-256 en todas, no AES-128 en iOS)
- RNG uniforme entre plataformas
- Almacenamiento seguro: KeyStore Android vs Keychain iOS vs DPAPI Windows
- Cifrado en disco: ¿la misma clave maestra para todas las plataformas?
- Logs multiplataforma que filtran material cripto
"""
import re
import subprocess
import pathlib
import platform
from typing import List, Dict


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "multiplatform",
            "severity": "info",
            "title": "Target no disponible",
            "description": f"{target} no existe.",
            "evidence_path": "",
            "remediation": "Proporcionar artefacto.",
        }]

    try:
        out = pathlib.Path(output_dir) / "multiplatform-strings.txt"
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=60)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{8,}", raw))

    # 1) Identificar plataforma del artefacto
    if apk.suffix.lower() == ".apk":
        platform_name = "Android"
    elif apk.suffix.lower() in (".ipa", ".app"):
        platform_name = "iOS"
    elif apk.suffix.lower() in (".exe", ".msi"):
        platform_name = "Windows"
    elif apk.suffix.lower() in (".deb", ".rpm", ".appimage"):
        platform_name = "Linux"
    else:
        platform_name = "Desconocida"

    findings.append({
        "scenario": "multiplatform",
        "severity": "info",
        "title": f"Plataforma detectada: {platform_name}",
        "description": f"Archivo: {apk.name}, extensión: {apk.suffix}",
        "evidence_path": str(target),
        "remediation": "N/A",
    })

    # 2) Almacenamiento seguro por plataforma
    keystore_indicators = {
        "Android": "AndroidKeyStore",
        "iOS": "Keychain",
        "Windows": "DPAPI|CNG|BCrypt",
        "Linux": "libsecret|secret-service",
    }
    expected = keystore_indicators.get(platform_name)
    if expected and not re.search(expected, text):
        findings.append({
            "scenario": "multiplatform",
            "severity": "high",
            "title": f"Sin uso del almacén seguro nativo de {platform_name}",
            "description": f"Esperado alguno de: {expected}",
            "evidence_path": str(out),
            "remediation": f"Usar el mecanismo nativo: {expected}. Nunca cifrar claves con contraseña hardcodeada.",
        })

    # 3) Longitud de clave inconsistente
    aes_128 = len(re.findall(r"AES[^A-Za-z0-9_]+128", text, re.IGNORECASE))
    aes_256 = len(re.findall(r"AES[^A-Za-z0-9_]+256", text, re.IGNORECASE))
    if aes_128 > 0 and aes_256 == 0:
        findings.append({
            "scenario": "multiplatform",
            "severity": "medium",
            "title": "Solo AES-128 detectado — migrar a AES-256 para consistencia multiplatform",
            "description": f"AES-128: {aes_128} referencias, AES-256: 0.",
            "evidence_path": str(out),
            "remediation": "AES-256 en TODAS las plataformas. Eliminar fallback a 128.",
        })

    # 4) RNG nativo por plataforma
    native_rng = {
        "Android": "SecureRandom|getRandom",
        "iOS": "SecRandomCopyBytes|kSecRandomDefault",
        "Windows": "BCryptGenRandom|CryptGenRandom",
        "Linux": "getrandom|/dev/urandom",
    }
    rng_expected = native_rng.get(platform_name)
    if rng_expected and not re.search(rng_expected, text):
        findings.append({
            "scenario": "multiplatform",
            "severity": "high",
            "title": f"Sin uso del CSPRNG nativo de {platform_name}",
            "description": f"Esperado: {rng_expected}",
            "evidence_path": str(out),
            "remediation": "Usar SIEMPRE el CSPRNG del SO. Nunca implementar RNG propio.",
        })

    # 5) Consistencia: misma clave maestra en todas las plataformas?
    master_key_markers = re.findall(r"MASTER_KEY\s*[:=]\s*['\"][A-Fa-f0-9]{16,}['\"]", text)
    if master_key_markers:
        findings.append({
            "scenario": "multiplatform",
            "severity": "critical",
            "title": "Master key hardcodeada detectada",
            "description": f"Encontradas {len(master_key_markers)} referencias a MASTER_KEY en claro.",
            "evidence_path": str(out),
            "remediation": "Master key NUNCA en binario. Usar HSM o KMS. Cada plataforma debe derivar su clave "
                           "del almacén seguro con autenticación de usuario.",
        })

    # 6) Verificar soporte offline (servidor Ubuntu)
    findings.append({
        "scenario": "multiplatform",
        "severity": "info",
        "title": "Check de servidor backend",
        "description": f"Backend actual: {backend}. Verificar manualmente que el servidor Ubuntu tenga: "
                       "ufw activo, fail2ban, TLS 1.2+ only, AppArmor/SELinux, logrotate, backups cifrados.",
        "evidence_path": backend,
        "remediation": "Auditar hardening del servidor con lynis / oscap. Rotar claves SSH. "
                       "Desactivar login con password.",
    })

    return findings
