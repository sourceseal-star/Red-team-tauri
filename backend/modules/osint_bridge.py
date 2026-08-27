"""
OSINT Bridge v2 - Integracion profunda con frontend
===================================================
Envuelve las funciones reales de osint_advanced.py en un formato
estructurado para el panel OSINT Advanced del frontend.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import asyncio
from datetime import datetime

from .osint_advanced import (
    whois_lookup, dns_recon, subdomain_enumeration,
    threat_intel_lookup, email_osint, header_fingerprint
)

router = APIRouter(prefix="/api/osint/v2", tags=["osint-bridge-v2"])


class FullScanRequest(BaseModel):
    target: str
    scan_type: str = "auto"  # ip, domain, email, url


class SearchRequest(BaseModel):
    query: str
    engine: str = "google"
    limit: int = 10


def _detect_type(target: str) -> str:
    """Detecta automaticamente el tipo de objetivo."""
    import re
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target):
        return "ip"
    if "@" in target and "." in target:
        return "email"
    if target.startswith("http://") or target.startswith("https://"):
        return "url"
    return "domain"


@router.post("/full-scan")
async def full_scan(request: FullScanRequest):
    """
    Escaneo OSINT completo con resultados estructurados.
    Combina WHOIS + DNS + Subdominios + Threat Intel en una sola llamada.
    """
    target = request.target.strip()
    scan_type = request.scan_type if request.scan_type != "auto" else _detect_type(target)

    results = {}
    errors = []

    # WHOIS y DNS para dominios
    if scan_type in ("domain", "url"):
        domain = target.replace("http://", "").replace("https://", "").split("/")[0]
        try:
            results["whois"] = await whois_lookup(domain)
        except Exception as e:
            errors.append(f"WHOIS: {e}")
            results["whois"] = None

        try:
            results["dns"] = await dns_recon(domain)
        except Exception as e:
            errors.append(f"DNS: {e}")
            results["dns"] = None

        try:
            sub_result = await subdomain_enumeration(domain, max_results=30)
            results["subdomains"] = sub_result.get("subdomains", []) if sub_result else []
        except Exception as e:
            errors.append(f"Subdomains: {e}")
            results["subdomains"] = []

    # Threat Intel para IPs
    if scan_type == "ip":
        try:
            results["threat_intel"] = await threat_intel_lookup(target)
        except Exception as e:
            errors.append(f"Threat Intel: {e}")
            results["threat_intel"] = None

    # Email OSINT para emails
    if scan_type == "email":
        try:
            results["email"] = await email_osint(target)
        except Exception as e:
            errors.append(f"Email: {e}")
            results["email"] = None

    # Headers fingerprint para URLs
    if scan_type == "url":
        try:
            results["headers"] = await header_fingerprint(target)
        except Exception as e:
            errors.append(f"Headers: {e}")
            results["headers"] = None

    # Calcular nivel de amenaza
    malicious_indicators = 0
    if results.get("threat_intel"):
        ti = results["threat_intel"]
        if isinstance(ti, dict):
            if ti.get("is_malicious"):
                malicious_indicators += 3
            if ti.get("abuse_score", 0) > 50:
                malicious_indicators += 1
    if results.get("email"):
        em = results["email"]
        if isinstance(em, dict):
            if em.get("breaches"):
                malicious_indicators += len(em.get("breaches", []))

    threat_level = "CRITICAL" if malicious_indicators > 3 else \
                   "HIGH" if malicious_indicators > 0 else "LOW"

    return {
        "target": target,
        "type": scan_type,
        "is_malicious": malicious_indicators > 0,
        "threat_level": threat_level,
        "malicious_indicators": malicious_indicators,
        "results": results,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/quick-scan/{target}")
async def quick_scan(target: str, scan_type: str = "auto"):
    """Escaneo rapido - solo hallazgos clave."""
    st = scan_type if scan_type != "auto" else _detect_type(target)
    domain = target.replace("http://", "").replace("https://", "").split("/")[0]

    key_findings = {
        "open_ports": 0,
        "vulnerabilities": 0,
        "subdomains": 0,
        "breaches": 0,
    }

    if st in ("domain", "url"):
        try:
            sub_result = await subdomain_enumeration(domain, max_results=10)
            key_findings["subdomains"] = len(sub_result.get("subdomains", [])) if sub_result else 0
        except Exception:
            pass

    if st == "email":
        try:
            em = await email_osint(target)
            if em and isinstance(em, dict):
                key_findings["breaches"] = len(em.get("breaches", []))
        except Exception:
            pass

    if st == "ip":
        try:
            ti = await threat_intel_lookup(target)
            if ti and isinstance(ti, dict):
                key_findings["open_ports"] = len(ti.get("ports", []))
                key_findings["vulnerabilities"] = len(ti.get("vulns", []))
        except Exception:
            pass

    return {
        "target": target,
        "type": st,
        "is_malicious": key_findings["vulnerabilities"] > 0 or key_findings["breaches"] > 0,
        "threat_level": "HIGH" if (key_findings["vulnerabilities"] > 0 or key_findings["breaches"] > 0) else "LOW",
        "key_findings": key_findings
    }


@router.get("/whois/{target}")
async def get_whois(target: str):
    """WHOIS lookup."""
    return await whois_lookup(target)


@router.get("/dns/{domain}")
async def get_dns(domain: str):
    """Registros DNS."""
    return await dns_recon(domain)


@router.get("/subdomains/{domain}")
async def get_subdomains(domain: str):
    """Enumeracion de subdominios."""
    result = await subdomain_enumeration(domain, max_results=50)
    return result if result else {"subdomains": []}


@router.get("/threat/{entity}")
async def get_threat_intel(entity: str, entity_type: str = "auto"):
    """Inteligencia de amenazas."""
    return await threat_intel_lookup(entity)


@router.post("/search")
async def search(request: SearchRequest):
    """Busqueda en motores - delega al endpoint /google existente."""
    # El modulo osint_advanced ya tiene /api/osint/google
    # Este endpoint es un alias para el frontend v2
    from .osint_advanced import api_google_search
    # Reusar la funcion existente
    return await api_google_search(q=request.query, num=min(request.limit, 20))
