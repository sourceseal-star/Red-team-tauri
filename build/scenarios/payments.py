"""
Escenario: Pasarelas de Pago (PayPal, Stripe, Binance, MercadoPago)
--------------------------------------------------------------------
Detecta malas prácticas en la integración de pagos:
- Secret keys hardcodeadas (PayPal, Stripe, Binance) en binarios
- Webhook signature verification ausente o rota
- PCI scope: almacenamiento de PAN/CVV
- Race conditions en captura de pagos
"""
import re
import subprocess
import pathlib
from typing import List, Dict


PROVIDER_MARKERS = {
    "stripe": [r"sk_live_[A-Za-z0-9]{24,}", r"pk_live_[A-Za-z0-9]{24,}", r"whsec_[A-Za-z0-9]{24,}"],
    "paypal": [r"access_token\$production", r"client_id.*paypal", r"PAYPAL_CLIENT_SECRET"],
    "binance": [r"BINANCE_API_KEY", r"BINANCE_API_SECRET", r"x-mbx-apikey"],
    "mercadopago": [r"APP_USR-\d+-\d+-\d+-\d+", r"MERCADO_PAGO_ACCESS_TOKEN"],
}

# Patrones que indican almacenamiento de datos sensibles (PCI-DSS red flag)
PCI_SENSITIVE = [
    r"cvv\s*=\s*['\"]?\d{3,4}['\"]?",
    r"cardNumber\s*[:=]\s*['\"]?\d{13,19}",
    r"track[12]?\s*[:=]\s*['\"]?[%A-Z]",
    r"magnetic\s*stripe",
]

WEBHOOK_VERIFICATION_OK = [
    "constructEvent",                # Stripe
    "verifyWebhookSignature",        # PayPal
    "HMAC_SHA256",                   # Binance
    "x-signature",                   # MercadoPago
    "validateWebhook",
]


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "payments",
            "severity": "info",
            "title": "Target no disponible",
            "description": f"{target} no existe; saltando análisis de pagos.",
            "evidence_path": "",
            "remediation": "Proporcionar artefacto.",
        }]

    # Extraer strings
    try:
        out = pathlib.Path(output_dir) / "payments-strings.txt"
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=60)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{8,}", raw))

    # 1) Secret keys de proveedores
    leaks = {}
    for provider, patterns in PROVIDER_MARKERS.items():
        for pat in patterns:
            hits = re.findall(pat, text)
            if hits:
                leaks.setdefault(provider, []).extend(hits[:3])

    if leaks:
        findings.append({
            "scenario": "payments",
            "severity": "critical",
            "title": f"Secret keys de pasarela de pago hardcodeadas ({len(leaks)} proveedores)",
            "description": "Proveedores afectados: " + ", ".join(leaks.keys()),
            "evidence_path": str(out),
            "remediation": "Rotar INMEDIATAMENTE todas las keys, mover a variables de entorno o vault, "
                           "separar keys live/test.",
        })

    # 2) Verificación de webhooks
    has_verif = any(m in text for m in WEBHOOK_VERIFICATION_OK)
    if not has_verif:
        findings.append({
            "scenario": "payments",
            "severity": "high",
            "title": "Sin evidencia de verificación de firma en webhooks",
            "description": "No se detectaron constructEvent/verifyWebhookSignature/validateWebhook. "
                           "Riesgo de webhook spoofing → pagos falsos confirmados.",
            "evidence_path": str(out),
            "remediation": "Implementar verificación criptográfica de TODOS los webhooks antes de marcar como pagado.",
        })

    # 3) PCI scope — almacenamiento de PAN/CVV
    pci_hits = []
    for pat in PCI_SENSITIVE:
        pci_hits.extend(re.findall(pat, text, re.IGNORECASE))
    if pci_hits:
        findings.append({
            "scenario": "payments",
            "severity": "critical",
            "title": f"Almacenamiento de datos sensibles de tarjeta (PCI-DSS violación)",
            "description": f"{len(pci_hits)} coincidencias de CVV/PAN/track. PCI-DSS prohíbe almacenar CVV. "
                           "PAN solo permitido si la infra cumple SAQ-D completo.",
            "evidence_path": str(out),
            "remediation": "Eliminar TODO dato de tarjeta. Tokenizar con proveedor (Stripe.js, PayPal SDK, "
                           "Binance Pay hosted). Nunca tocar PAN/CVV desde tu backend.",
        })

    # 4) Detección de race condition en captura (heurística)
    race_patterns = [r"update\s+.*\s+set\s+status\s*=\s*['\"]paid['\"]", r"capturePayment"]
    if any(re.search(p, text, re.IGNORECASE) for p in race_patterns):
        findings.append({
            "scenario": "payments",
            "severity": "medium",
            "title": "Posible race condition en captura de pagos",
            "description": "Patrones de update de status a 'paid' encontrados. Sin transacciones atómicas, "
                           "un atacante puede capturar el mismo pago N veces.",
            "evidence_path": str(out),
            "remediation": "Usar idempotency keys, transacciones atómicas, y webhook reconciliation.",
        })

    return findings
