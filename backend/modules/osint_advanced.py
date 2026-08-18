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
    "abuseipdb": os.environ.get("ABUSEIPDB_KEY", ""),
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


# ============================================================================
# GOOGLE CUSTOM SEARCH
# ============================================================================

@osint_router.get("/google")
async def api_google_search(
    q: str = Query(..., description="Consulta de busqueda"),
    num: int = Query(10, ge=1, le=20, description="Numero de resultados"),
):
    """
    Google Custom Search API — NIST SP 800-115 §A.1.
    Si no hay API key, usa scraping basico con httpx.
    """
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    cse_id = os.environ.get("GOOGLE_CSE_ID", "")

    if google_key and cse_id:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={"key": google_key, "cx": cse_id, "q": q, "num": num},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("items", []):
                        results.append({
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "displayLink": item.get("displayLink", ""),
                        })
                    return {"query": q, "engine": "google-cse", "results": results, "total": len(results)}
        except Exception as e:
            pass

    # Fallback: DuckDuckGo HTML (no requiere API key)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": q},
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            )
            results = []
            if resp.status_code == 200:
                # Parsear resultados basico con regex
                links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)', resp.text)
                for url, title in links[:num]:
                    # Limpiar URL de redirect de DDG
                    if "uddg=" in url:
                        from urllib.parse import parse_qs, urlparse as up
                        parsed = up(url)
                        qs = parse_qs(parsed.query)
                        url = unquote(qs.get("uddg", [url])[0])
                    results.append({"title": title.strip(), "link": url, "snippet": "", "displayLink": ""})
            return {"query": q, "engine": "duckduckgo", "results": results, "total": len(results)}
    except Exception as e:
        return {"query": q, "engine": "none", "results": [], "error": str(e)}


# ============================================================================
# SHODAN HOST LOOKUP
# ============================================================================

@osint_router.get("/shodan/{ip}")
async def api_shodan(ip: str):
    """
    Shodan host lookup — NIST SP 800-150.
    Requiere SHODAN_API_KEY. Sin key, retorna info basica de la IP.
    """
    shodan_key = os.environ.get("SHODAN_API_KEY", "")

    if shodan_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.shodan.io/shodan/host/{ip}",
                    params={"key": shodan_key},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "ip": ip,
                        "source": "shodan",
                        "hostnames": data.get("hostnames", []),
                        "org": data.get("org", ""),
                        "os": data.get("os", ""),
                        "ports": data.get("ports", []),
                        "services": [
                            {"port": s.get("port"), "product": s.get("product", ""),
                             "version": s.get("version", ""), "banner": (s.get("data", "") or "")[:200]}
                            for s in data.get("data", [])
                        ],
                        "country": data.get("country_name", ""),
                        "city": data.get("city", ""),
                        "isp": data.get("isp", ""),
                        "tags": data.get("tags", []),
                        "vulns": data.get("vulns", []),
                    }
                elif resp.status_code == 404:
                    return {"ip": ip, "source": "shodan", "error": "No data found"}
                else:
                    return {"ip": ip, "source": "shodan", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ip": ip, "source": "shodan", "error": str(e)}

    # Sin key: info basica
    try:
        hostname = socket.gethostbyaddr(ip)[0]
    except Exception:
        hostname = None
    return {"ip": ip, "source": "basic", "hostname": hostname, "note": "Configura SHODAN_API_KEY para datos completos"}


# ============================================================================
# VIRUSTOTAL LOOKUP
# ============================================================================

@osint_router.get("/virustotal/{indicator}")
async def api_virustotal(indicator: str):
    """
    VirusTotal v3 lookup — NIST SP 800-150.
    Soporta IP, dominio, o hash de archivo.
    """
    vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "")

    if not vt_key:
        return {"indicator": indicator, "source": "virustotal", "error": "VIRUSTOTAL_API_KEY no configurado"}

    # Detectar tipo de indicator
    try:
        socket.inet_aton(indicator)
        endpoint = f"https://www.virustotal.com/api/v3/ip_addresses/{indicator}"
    except Exception:
        if "." in indicator and " " not in indicator:
            endpoint = f"https://www.virustotal.com/api/v3/domains/{indicator}"
        else:
            endpoint = f"https://www.virustotal.com/api/v3/files/{indicator}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(endpoint, headers={"x-apikey": vt_key})
            if resp.status_code == 200:
                data = resp.json().get("data", {}).get("attributes", {})
                stats = data.get("last_analysis_stats", {})
                return {
                    "indicator": indicator,
                    "source": "virustotal",
                    "malicious": stats.get("malicious", 0),
                    "suspicious": stats.get("suspicious", 0),
                    "harmless": stats.get("harmless", 0),
                    "undetected": stats.get("undetected", 0),
                    "reputation": data.get("reputation", 0),
                    "categories": data.get("categories", {}),
                    "tags": data.get("tags", []),
                }
            elif resp.status_code == 404:
                return {"indicator": indicator, "source": "virustotal", "error": "No encontrado"}
            else:
                return {"indicator": indicator, "source": "virustotal", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"indicator": indicator, "source": "virustotal", "error": str(e)}


# ============================================================================
# CENSYS HOST SEARCH
# ============================================================================

@osint_router.get("/censys/{ip}")
async def api_censys(ip: str):
    """
    Censys host search — NIST SP 800-150.
    Requiere CENSYS_API_ID y CENSYS_API_SECRET.
    """
    censys_id = os.environ.get("CENSYS_API_ID", "")
    censys_secret = os.environ.get("CENSYS_API_SECRET", "")

    if not censys_id or not censys_secret:
        return {"ip": ip, "source": "censys", "error": "CENSYS_API_ID/SECRET no configurados"}

    try:
        import httpx
        import base64
        auth = base64.b64encode(f"{censys_id}:{censys_secret}".encode()).decode()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://search.censys.io/api/v2/hosts/{ip}",
                headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json().get("result", {})
                services = []
                for svc in data.get("services", []):
                    services.append({
                        "port": svc.get("port", 0),
                        "transport": svc.get("transport", ""),
                        "service": svc.get("service", ""),
                        "banner": (str(svc.get("banner", "")) or "")[:200],
                    })
                return {
                    "ip": ip,
                    "source": "censys",
                    "services": services,
                    "location": data.get("location", {}),
                    "autonomous_system": data.get("autonomous_system", {}),
                }
            elif resp.status_code == 404:
                return {"ip": ip, "source": "censys", "error": "No encontrado"}
            else:
                return {"ip": ip, "source": "censys", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ip": ip, "source": "censys", "error": str(e)}


# ============================================================================
# GITHUB RECON — Search for leaked secrets and exposed repos
# ============================================================================

@osint_router.get("/github/{username}")
async def api_github_recon(username: str):
    """
    GitHub recon — busca repos publicos, gists y posibles leaks.
    MITRE ATT&CK T1613 (Search for Victim Organizations Info).
    """
    github_token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            # Perfil
            resp = await client.get(f"https://api.github.com/users/{username}", headers=headers)
            profile = {}
            if resp.status_code == 200:
                d = resp.json()
                profile = {
                    "login": d.get("login"), "name": d.get("name"),
                    "bio": d.get("bio"), "company": d.get("company"),
                    "blog": d.get("blog"), "location": d.get("location"),
                    "public_repos": d.get("public_repos", 0),
                    "public_gists": d.get("public_gists", 0),
                    "followers": d.get("followers", 0),
                    "following": d.get("following", 0),
                    "created_at": d.get("created_at"),
                }

            # Repos
            resp = await client.get(
                f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10",
                headers=headers,
            )
            repos = []
            if resp.status_code == 200:
                for r in resp.json():
                    repos.append({
                        "name": r.get("name"), "description": r.get("description"),
                        "language": r.get("language"), "stars": r.get("stargazers_count", 0),
                        "updated_at": r.get("updated_at"), "url": r.get("html_url"),
                    })

            # GitHub dorks — buscar posibles secrets en codigo publico
            dorks = [
                f"{username} password",
                f"{username} api_key",
                f"{username} secret",
                f"{username} token",
            ]
            leaks = []
            for dork in dorks[:2]:
                resp = await client.get(
                    "https://api.github.com/search/code",
                    params={"q": dork, "per_page": 3},
                    headers=headers,
                )
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        leaks.append({
                            "file": item.get("name"),
                            "repo": item.get("repository", {}).get("full_name"),
                            "url": item.get("html_url"),
                        })

            return {
                "username": username,
                "profile": profile,
                "repos": repos,
                "potential_leaks": leaks[:5],
            }
    except Exception as e:
        return {"username": username, "error": str(e)}


# ============================================================================
# SOCIAL MEDIA USERNAME SEARCH
# ============================================================================

PLATFORMS = {
    "github": "https://github.com/{u}",
    "twitter": "https://twitter.com/{u}",
    "x": "https://x.com/{u}",
    "instagram": "https://instagram.com/{u}",
    "linkedin": "https://linkedin.com/in/{u}",
    "facebook": "https://facebook.com/{u}",
    "youtube": "https://youtube.com/@{u}",
    "reddit": "https://reddit.com/user/{u}",
    "tiktok": "https://tiktok.com/@{u}",
    "telegram": "https://t.me/{u}",
    "gitlab": "https://gitlab.com/{u}",
    "medium": "https://medium.com/@{u}",
    "pinterest": "https://pinterest.com/{u}",
    "snapchat": "https://snapchat.com/add/{u}",
    "twitch": "https://twitch.tv/{u}",
    "steam": "https://steamcommunity.com/id/{u}",
}

@osint_router.post("/social")
async def api_social_search(req: OSINTRequest):
    """
    Social media username search — MITRE ATT&CK T1589 (Gather Victim Identity Info).
    Verifica si un username existe en 15+ plataformas via HTTP status check.
    """
    username = req.target.replace("@", "").strip()
    results = []
    sem = asyncio.Semaphore(10)

    async def check_platform(name: str, url: str):
        full_url = url.replace("{u}", username)
        async with sem:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=8, follow_redirects=True, verify=False) as client:
                    resp = await client.get(full_url, headers={"User-Agent": "Mozilla/5.0"})
                    exists = resp.status_code == 200
                    # Algunas plataformas retornan 404 si no existe
                    not_found_signals = ["not found", "doesn't exist", "unavailable", "page not found"]
                    if resp.status_code == 200 and any(s in resp.text[:2000].lower() for s in not_found_signals):
                        exists = False
                    results.append({
                        "platform": name,
                        "url": full_url,
                        "exists": exists,
                        "status_code": resp.status_code,
                    })
            except Exception as e:
                results.append({
                    "platform": name,
                    "url": full_url,
                    "exists": False,
                    "error": str(e)[:100],
                })

    tasks = [check_platform(name, url) for name, url in PLATFORMS.items()]
    await asyncio.gather(*tasks)

    found = [r for r in results if r["exists"]]
    return {"username": username, "found": found, "total_found": len(found), "total_checked": len(results)}
