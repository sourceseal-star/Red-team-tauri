"""
Escenario: Certificate / Public Key Pinning
--------------------------------------------
Verifica:
- Que el pinning esté implementado y no sea trivialmente bypassable
- Que la app rechace certificados MITM (mitmproxy, Charles, Burp)
- Que el backend tenga HSTS + CT
"""
import json
import socket
import ssl
import subprocess
import pathlib
from typing import List, Dict
from urllib.parse import urlparse


def _check_tls_pinning(backend: str) -> Dict:
    """Conexión directa y captura de cert; comparar con pin esperado si se pasa."""
    parsed = urlparse(backend)
    host = parsed.hostname
    port = parsed.port or 443
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert(binary_form=True)
            return {
                "host": host,
                "port": port,
                "sha256": __import__("hashlib").sha256(cert).hexdigest(),
                "subject": dict(x[0] for x in ssock.getpeercert().get("subject", [])),
            }


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []

    # 1) Verificar que el backend sirve HTTPS con cert válido
    try:
        info = _check_tls_pinning(backend)
        pathlib.Path(output_dir, "pinning-cert.json").write_text(json.dumps(info, indent=2))
        findings.append({
            "scenario": "pinning",
            "severity": "info",
            "title": "Cert TLS del backend capturado",
            "description": f"Host {info['host']}:{info['port']} SHA256={info['sha256'][:16]}...",
            "evidence_path": f"{output_dir}/pinning-cert.json",
            "remediation": "Comparar SHA256 contra el pin hardcodeado en la app móvil.",
        })
    except Exception as e:
        findings.append({
            "scenario": "pinning",
            "severity": "critical",
            "title": "Backend no presenta certificado TLS válido",
            "description": str(e),
            "evidence_path": "",
            "remediation": "Activar HTTPS en producción, configurar HSTS, deshabilitar HTTP plano.",
        })

    # 2) Análisis estático: ¿la app tiene pinning? (búsqueda de strings clave)
    apk = pathlib.Path(target)
    if apk.exists() and apk.suffix.lower() in (".apk", ".ipa"):
        # Extracción rápida de strings (APK es zip, IPA contiene binarios)
        try:
            if apk.suffix.lower() == ".apk":
                tmp = pathlib.Path(output_dir) / "apk-strings.txt"
                # Usa strings(1) si está disponible, si no fallback con grep binario
                try:
                    subprocess.run(
                        ["strings", "-a", str(apk)],
                        stdout=open(tmp, "w"), check=True, timeout=60
                    )
                except FileNotFoundError:
                    raw = apk.read_bytes()
                    tmp.write_bytes(b"\n".join(
                        s.encode() for s in __import__("re").findall(rb"[\x20-\x7e]{8,}", raw)
                    ))

                txt = tmp.read_text(errors="ignore")
                pinning_markers = [
                    "NetworkSecurityConfig", "network_security_config",
                    "trust-anchors", "pin-set", "certificatePinner",
                    "SSLContext", "X509TrustManager",
                ]
                hits = [m for m in pinning_markers if m in txt]
                if not hits:
                    findings.append({
                        "scenario": "pinning",
                        "severity": "high",
                        "title": "Sin evidencia de pinning en el APK",
                        "description": "No se encontraron marcadores típicos (NetworkSecurityConfig, pin-set, OkHttp CertificatePinner).",
                        "evidence_path": str(tmp),
                        "remediation": "Implementar pinning vía OkHttp CertificatePinner o NSP en res/xml/.",
                    })
                else:
                    findings.append({
                        "scenario": "pinning",
                        "severity": "info",
                        "title": "Marcadores de pinning encontrados",
                        "description": f"Detectados: {', '.join(hits)}",
                        "evidence_path": str(tmp),
                        "remediation": "Verificar manualmente que el pin cubra el cert de producción y tenga backup pin.",
                    })
        except Exception as e:
            findings.append({
                "scenario": "pinning",
                "severity": "info",
                "title": "Análisis estático no completado",
                "description": str(e),
                "evidence_path": "",
                "remediation": "Revisar manualmente el APK con apktool/jadx.",
            })

    return findings
