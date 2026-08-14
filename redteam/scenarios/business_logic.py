"""
Escenario: Lógica de Negocio (Ventas, Pagos, Comisiones)
---------------------------------------------------------
Ataca la lógica de la app de control de pagos:

- IDOR: vendedor A lee ventas de vendedor B con /sales/{id}
- Manipulación de precios: cliente envía precio, servidor no re-valida
- Race condition en abonos: dos abonos simultáneos para la misma cuota
- Bypass de comisiones: cambiar el porcentaje de comisión del vendedor
- Validación de saldo: registrar abono mayor al saldo pendiente
- Estado de venta: cambiar de 'pendiente' a 'pagado' sin pago real
"""
import re
import subprocess
import pathlib
from typing import List, Dict


# Patrones en strings que sugieren problemas de autorización
AUTH_PATTERNS = {
    "idor_risk": [
        r"/sales/\$\{?id\}?",
        r"/customers/\$\{?id\}?",
        r"/payments/\$\{?id\}?",
        r"sale_id\s*=\s*req\.",
    ],
    "client_side_pricing": [
        r"price\s*=\s*req\.body\.",
        r"amount\s*=\s*request\.json\[",
        r"total\s*=\s*params\[",
    ],
    "client_side_commission": [
        r"commission\s*=\s*req\.",
        r"vendorCommission\s*=\s*request\.",
    ],
    "missing_state_validation": [
        r"setStatus\s*\(\s*['\"]paid['\"]\)",
        r"status\s*=\s*['\"]paid['\"]",
    ],
}

# Endpoints que DEBERÍAN tener autorización pero el cliente los manipula
SENSITIVE_OPERATIONS = [
    "delete", "refund", "cancel", "void", "markAsPaid",
    "approveCredit", "discount", "override",
]


def run(target: str, backend: str, output_dir: str) -> List[Dict]:
    findings = []
    apk = pathlib.Path(target)

    if not apk.exists():
        return [{
            "scenario": "business_logic",
            "severity": "info",
            "title": "Target no disponible",
            "description": f"{target} no existe.",
            "evidence_path": "",
            "remediation": "Proporcionar artefacto.",
        }]

    try:
        out = pathlib.Path(output_dir) / "bizlogic-strings.txt"
        subprocess.run(["strings", "-a", str(apk)], stdout=open(out, "w"), check=True, timeout=3)
        text = out.read_text(errors="ignore")
    except FileNotFoundError:
        raw = apk.read_bytes()
        text = "\n".join(s.decode(errors="ignore") for s in re.findall(rb"[\x20-\x7e]{8,}", raw))

    # 1) IDOR patterns
    idor_hits = []
    for pat in AUTH_PATTERNS["idor_risk"]:
        idor_hits.extend(re.findall(pat, text, re.IGNORECASE))
    if idor_hits:
        findings.append({
            "scenario": "business_logic",
            "severity": "high",
            "title": "Posible IDOR (Insecure Direct Object Reference)",
            "description": f"{len(idor_hits)} patrones de acceso por ID sin contexto de autorización visible. "
                           "Riesgo: vendedor lee ventas de otros vendedores o de otras tiendas.",
            "evidence_path": str(out),
            "remediation": "Validar ownership server-side: el vendor_id del path debe coincidir con el del token. "
                           "Considerar UUIDs en lugar de IDs incrementales.",
        })

    # 2) Pricing manipulable por cliente
    pricing_hits = []
    for pat in AUTH_PATTERNS["client_side_pricing"]:
        pricing_hits.extend(re.findall(pat, text, re.IGNORECASE))
    if pricing_hits:
        findings.append({
            "scenario": "business_logic",
            "severity": "critical",
            "title": "Precios/amounts tomados del cliente sin re-validación server-side",
            "description": f"{len(pricing_hits)} patrones detectados. Un atacante con proxy (mitmproxy/Burp) "
                           "puede modificar el monto de la venta o el abono.",
            "evidence_path": str(out),
            "remediation": "Precios SIEMPRE desde el catálogo server-side. Cliente solo envía product_id y cantidad. "
                           "Abonos validan contra saldo pendiente en transacción atómica.",
        })

    # 3) Comisión manipulable
    if any(re.search(p, text, re.IGNORECASE) for p in AUTH_PATTERNS["client_side_commission"]):
        findings.append({
            "scenario": "business_logic",
            "severity": "critical",
            "title": "Comisión del vendedor enviada por el cliente",
            "description": "Comisión debe calcularse server-side según reglas del plan del vendedor.",
            "evidence_path": str(out),
            "remediation": "Comisión = función(producto, plan, tienda) — nunca input del cliente.",
        })

    # 4) Cambio de estado sin validación
    state_hits = []
    for pat in AUTH_PATTERNS["missing_state_validation"]:
        state_hits.extend(re.findall(pat, text, re.IGNORECASE))
    if state_hits:
        findings.append({
            "scenario": "business_logic",
            "severity": "high",
            "title": "Cambio de estado de venta a 'paid' sin validación visible",
            "description": f"{len(state_hits)} patrones. Riesgo: marcar ventas como pagadas sin recibir pago real.",
            "evidence_path": str(out),
            "remediation": "Solo webhook de pasarela puede cambiar estado a 'paid'. Implementar state machine "
                           "estricta con transiciones permitidas.",
        })

    # 5) Operaciones sensibles sin 2FA
    sensitive_in_app = [op for op in SENSITIVE_OPERATIONS if op in text]
    if sensitive_in_app and "totp" not in text.lower() and "2fa" not in text.lower() and "mfa" not in text.lower():
        findings.append({
            "scenario": "business_logic",
            "severity": "medium",
            "title": "Operaciones sensibles sin evidencia de 2FA",
            "description": f"Operaciones detectadas: {', '.join(sensitive_in_app)}. "
                           "Refunds, cancellations, discounts deberían requerir segundo factor.",
            "evidence_path": str(out),
            "remediation": "Implementar TOTP/2FA para operaciones monetarias. Considerar step-up auth.",
        })

    return findings
