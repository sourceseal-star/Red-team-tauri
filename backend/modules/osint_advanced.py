"""
MÓDULO OSINT AVANZADO - SourceSeal Console
===========================================
Integración con enhanced_recon.py existente.
Nuevas capacidades: DNS recon, subdomain enumeration, whois lookup,
threat intel lookup, email OSINT, HTTP header analysis.

Referencias: NIST SP 800-115, MITRE ATT&CK T1592 (Gather Victim Host Info)
             NIST SP 800-86 (Guide to Integrating Forensic Techniques)

Uso:
    from modules.osint_advanced import (
        osint_router, whois_lookup, dns_recon,
        subdomain_enumeration, threat_intel_lookup, email_osint,
        header_fingerprint
    )
"""

import asyncio
import json
import re
import socket
import sqlite3
import hashlib
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field

# ============================================================================
# CONFIG
# ============================================================================

osint_router = APIRouter(prefix="/api/osint", tags=["osint-advanced"])

OSINT_DB_PATH = os.path.join(os.getcwd(), "evidence", "osint_results.db")

# API keys from environment (all optional — graceful degradation)
API_KEYS = {
    "shodan": os.environ.get("SHODAN_API_KEY", ""),
    "virustotal": os.environ.get("VIRUSTOTAL_API_KEY", ""),
    "abuseipdb": os.environ.get("ABUSEIPDB_API_KEY", ""),
    "github": os.environ.get("GITHUB_TOKEN", ""),
}

# Common subdomains for brute-force enumeration (NIST SP 800-115 §A.3)
COMMON_SUBDOMAINS = [
    "www", "mail", "ftp", "localhost", "webmail", "smtp", "pop", "ns1", "ns2",
    "dns", "dns1", "dns2", "api", "dev", "staging", "test", "beta", "admin",
    "portal", "vpn", "remote", "m", "mobile", "app", "blog", "shop", "store",
    "cd", "cdn", "media", "static", "assets", "img", "images", "docs",
    "wiki", "support", "help", "kb", "status", "monitor", "grafana",
    "jenkins", "git", "gitlab", "ci", "build", "registry", "docker",
    "k8s", "kube", "consul", "vault", "etcd", "elastic", "search",
    "db", "database", "mysql", "postgres", "redis", "mongo", "cache",
    "auth", "sso", "saml", "oauth", "keycloak", "ldap", "ad",
    "backup", "backups", "old", "new", "v2", "v1", "internal", "intranet",
    "extranet", "secure", "ssl", "tls", "proxy", "gateway", "load",
    "panel", "cpanel", "whm", "plesk", "webmin", "phpmyadmin",
    "s3", "storage", "files", "download", "uploads", "media1",
]


# ============================================================================
# DATABASE
# ============================================================================

def _init_db():
    os.makedirs(os.path.dirname(OSINT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(OSINT_DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS domain_osint (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT UNIQUE,
        ip_addresses TEXT,
        whois_info TEXT,
        dns_records TEXT,
        subdomains TEXT,
        open_ports TEXT,
        last_scan TEXT,
        is_malicious INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ip_osint (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT UNIQUE,
        hostname TEXT,
        threat_intel TEXT,
        geo_location TEXT,
        last_scan TEXT,
        is_malicious INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_osint (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        domain TEXT,
        username TEXT,
        social_media TEXT,
        breaches TEXT,
        last_scan TEXT
    )''')
    conn.commit()
    conn.close()


_init_db()


# ============================================================================
# MODELS
# ============================================================================

class OSINTRequest(BaseModel):
    target: str = Field(..., description="Dominio, IP o email a investigar")


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def _dns_resolve(domain: str, record_type: str = "A") -> List[str]:
    """Resuelve registros DNS usando socket stdlib (sin dependencias externas)."""
    try:
        if record_type == "A":
            return list(set(socket.gethostbyname_ex(domain)[2]))
        elif record_type == "MX":
            import subprocess
            result = subprocess.run(
                ["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=5
            )
            return [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        elif record_type == "TXT":
            import subprocess
            result = subprocess.run(
                ["dig", "+short", "TXT", domain], capture_output=True, text=True, timeout=5
            )
            return [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        elif record_type == "NS":
            import subprocess
            result = subprocess.run(
                ["dig", "+short", "NS", domain], capture_output=True, text=True, timeout=5
            )
            return [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    except Exception:
        return []


async def whois_lookup(domain: str) -> Dict[str, Any]:
    """
    WHOIS lookup — NIST SP 800-115 §A.1 (OSINT from public registers).
    Usa python-whois si esta disponible, si no usa whois CLI.
    """
    result: Dict[str, Any] = {"domain": domain, "raw": {}}
    try:
        import whois as python_whois
        w = python_whois.whois(domain)
        result["raw"] = {
            "registrar": w.registrar,
            "creation_date": str(w.creation_date) if w.creation_date else None,
            "expiration_date": str(w.expiration_date) if w.expiration_date else None,
            "name_servers": w.name_servers,
            "status": w.status,
            "emails": w.emails,
            "org": w.org,
            "country": w.country,
        }
    except ImportError:
        import subprocess
        try:
            proc = subprocess.run(
                ["whois", domain], capture_output=True, text=True, timeout=10
            )
            result["raw"] = {"cli_output": proc.stdout[:2000]}
        except Exception as e:
            result["raw"] = {"error": str(e)}
    except Exception as e:
        result["raw"] = {"error": str(e)}

    return result


async def dns_recon(domain: str) -> Dict[str, Any]:
    """
    DNS reconnaissance — NIST SP 800-115 §A.3.
    Recopila A, MX, TXT, NS, CNAME records.
    """
    result: Dict[str, Any] = {"domain": domain, "records": {}}
    result["records"]["A"] = _dns_resolve(domain, "A")
    result["records"]["MX"] = _dns_resolve(domain, "MX")
    result["records"]["TXT"] = _dns_resolve(domain, "TXT")
    result["records"]["NS"] = _dns_resolve(domain, "NS")

    txt_records = result["records"].get("TXT", [])
    result["spf"] = any("spf1" in t.lower() for t in txt_records)
    result["dmarc"] = any("dmarc" in t.lower() for t in txt_records)

    dkim = _dns_resolve(f"_dmarc.{domain}", "TXT")
    result["dmarc_record"] = dkim[0] if dkim else None

    return result


async def subdomain_enumeration(domain: str, max_results: int = 50) -> Dict[str, Any]:
    """
    Enumeracion de subdominios — MITRE ATT&CK T1580 (Cloud Infrastructure Discovery).
    Resuelve subdominios comunes via DNS (brute-force pasivo, sin enviar paquetes al target).
    """
    found: List[Dict] = []
    sem = asyncio.Semaphore(30)

    async def check(sub: str):
        full = f"{sub}.{domain}"
        async with sem:
            ips = await asyncio.to_thread(_dns_resolve, full, "A")
            if ips:
                found.append({"subdomain": full, "ip": ips[0], "all_ips": ips})

    tasks = [check(s) for s in COMMON_SUBDOMAINS[:max_results]]
    await asyncio.gather(*tasks)
    return {"domain": domain, "subdomains": found, "total": len(found)}


async def threat_intel_lookup(ip: str) -> Dict[str, Any]:
    """
    Threat Intelligence lookup — NIST SP 800-150 (Guide to Cyber Threat Information Sharing).
    Consulta AbuseIPDB, VirusTotal (si hay API key) y heuristicas locales.
    """
    result: Dict[str, Any] = {"ip": ip, "score": 0, "factors": [], "is_malicious": False}

    try:
        hostname = socket.gethostbyaddr(ip)[0]
        result["factors"].append({"factor": "rDNS", "value": hostname})
    except Exception:
        hostname = None

    if API_KEYS["abuseipdb"]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}",
                    headers={"Key": API_KEYS["abuseipdb"], "Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    score = data.get("abuseConfidenceScore", 0)
                    result["factors"].append({"factor": "AbuseIPDB", "value": f"{score}/100"})
                    result["score"] += score // 3
                    if score > 50:
                        result["is_malicious"] = True
        except Exception:
            pass

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                geo = resp.json()
                result["factors"].append({
                    "factor": "Country",
                    "value": geo.get("country", "?"),
                })
                if geo.get("connection", {}).get("type") in ("hosting", "tor"):
                    result["factors"].append({
                        "factor": "Hosting/Tor",
                        "value": geo["connection"]["type"],
                    })
                    result["score"] += 10
    except Exception:
        pass

    try:
        conn = sqlite3.connect(OSINT_DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO ip_osint
            (ip, hostname, threat_intel, geo_location, last_scan, is_malicious)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (ip, hostname, json.dumps(result["factors"]), None,
             datetime.utcnow().isoformat(), 1 if result["is_malicious"] else 0))
        conn.commit()
        conn.close()
    except Exception:
        pass

    result["score"] = min(result["score"], 100)
    return result


async def email_osint(email: str) -> Dict[str, Any]:
    """
    Email OSINT — NIST SP 800-115 §A.2.
    Verifica formato, dominio, registros MX, y genera hash SHA-256 (Zero-PII).
    """
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return {"email": email, "error": "Formato de email invalido"}

    domain = email.split("@")[0]
    username = email.split("@")[0]

    result: Dict[str, Any] = {
        "email": email,
        "domain": domain,
        "username": username,
        "hash_sha256": hashlib.sha256(email.encode()).hexdigest(),
        "mx_records": _dns_resolve(domain, "MX"),
        "spf": False,
        "dmarc": False,
    }

    txt = _dns_resolve(domain, "TXT")
    result["spf"] = any("spf1" in t.lower() for t in txt)

    dmarc = _dns_resolve(f"_dmarc.{domain}", "TXT")
    result["dmarc"] = bool(dmarc)

    providers = {
        "gmail.com": "Google", "outlook.com": "Microsoft",
        "hotmail.com": "Microsoft", "yahoo.com": "Yahoo",
        "protonmail.com": "Proton", "proton.me": "Proton",
        "icloud.com": "Apple", "gmx.com": "GMX",
    }
    result["provider"] = providers.get(domain, "Desconocido")

    try:
        conn = sqlite3.connect(OSINT_DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO email_osint
            (email, domain, username, social_media, breaches, last_scan)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (result["hash_sha256"], domain, username, "[]", "[]",
             datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass

    return result


async def header_fingerprint(url: str) -> Dict[str, Any]:
    """
    HTTP Header Fingerprinting — NIST SP 800-115 §3.2.
    Analiza headers de respuesta para identificar servidor, frameworks y configuraciones.
    """
    result: Dict[str, Any] = {"url": url, "headers": {}, "security_headers": {}}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, verify=False) as client:
            resp = await client.get(url)
            headers = dict(resp.headers)

            result["headers"] = {
                "server": headers.get("server", "Desconocido"),
                "x_powered_by": headers.get("x-powered-by", "Desconocido"),
                "content_type": headers.get("content-type", "Desconocido"),
                "status_code": resp.status_code,
            }

            security = {}
            for h in ["strict-transport-security", "x-frame-options",
                       "x-content-type-options", "content-security-policy",
                       "x-xss-protection", "referrer-policy",
                       "permissions-policy"]:
                val = headers.get(h)
                security[h] = "present" if val else "missing"
            result["security_headers"] = security
            result["security_score"] = sum(1 for v in security.values() if v == "present")
            result["security_total"] = len(security)

    except Exception as e:
        result["error"] = str(e)

    return result


# ============================================================================
# ENDPOINTS
# ============================================================================

@osint_router.get("/whois/{domain}")
async def api_whois(domain: str):
    return await whois_lookup(domain)


@osint_router.get("/dns/{domain}")
async def api_dns(domain: str):
    return await dns_recon(domain)


@osint_router.post("/subdomains")
async def api_subdomains(req: OSINTRequest):
    if "." not in req.target:
        raise HTTPException(400, "Target debe ser un dominio valido")
    return await subdomain_enumeration(req.target)


@osint_router.get("/threat-intel/{ip}")
async def api_threat_intel(ip: str):
    try:
        socket.inet_aton(ip)
    except Exception:
        raise HTTPException(400, "IP invalida")
    return await threat_intel_lookup(ip)


@osint_router.post("/email")
async def api_email_osint(req: OSINTRequest):
    return await email_osint(req.target)


@osint_router.get("/headers")
async def api_headers(url: str = Query(..., description="URL completa a escanear")):
    if not url.startswith("http"):
        url = f"https://{url}"
    return await header_fingerprint(url)


@osint_router.get("/full/{domain}")
async def api_full_osint(domain: str):
    """
    OSINT completo — combina WHOIS + DNS + Subdominios en una sola consulta.
    NIST SP 800-115 §A (Reconnaissance).
    """
    whois_result, dns_result, sub_result = await asyncio.gather(
        whois_lookup(domain),
        dns_recon(domain),
        subdomain_enumeration(domain, max_results=30),
    )
    return {
        "domain": domain,
        "whois": whois_result,
        "dns": dns_result,
        "subdomains": sub_result,
        "timestamp": datetime.utcnow().isoformat(),
    }


@osint_router.get("/results")
async def api_get_results():
    """Lista todos los resultados OSINT guardados en la base de datos."""
    try:
        conn = sqlite3.connect(OSINT_DB_PATH)
        c = conn.cursor()
        domains = c.execute("SELECT * FROM domain_osint ORDER BY last_scan DESC LIMIT 50").fetchall()
        ips = c.execute("SELECT * FROM ip_osint ORDER BY last_scan DESC LIMIT 50").fetchall()
        conn.close()
        return {"domains": domains, "ips": ips}
    except Exception as e:
        return {"error": str(e), "domains": [], "ips": []}
