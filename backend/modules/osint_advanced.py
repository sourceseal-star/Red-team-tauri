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
    target: str = Field(None, description="Dominio, IP o email a investigar")
    domain: str = Field(None, description="Alias de target (compatibilidad)")

    def __init__(self, **data):
        # Aceptar tanto "target" como "domain"
        if "domain" in data and "target" not in data:
            data["target"] = data["domain"]
        if "target" not in data and "domain" not in data:
            raise ValueError("Falta 'target' o 'domain'")
        super().__init__(**data)


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def _dns_resolve(domain: str, record_type: str = "A") -> List[str]:
    """Resuelve registros DNS. Intenta dig, fallback a Google DNS-over-HTTPS."""
    try:
        if record_type == "A":
            return list(set(socket.gethostbyname_ex(domain)[2]))
        
        # Intentar dig primero
        import subprocess
        try:
            result = subprocess.run(
                ["dig", "+short", record_type, domain],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Fallback: Google DNS-over-HTTPS (sin binarios externos)
        import urllib.request
        import json as _json
        url = f"https://dns.google/resolve?name={domain}&type={record_type}"
        req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read().decode())
        answers = data.get("Answer", [])
        return [a.get("data", "") for a in answers if a.get("type") == _record_type_num(record_type)]
    except Exception:
        return []

def _record_type_num(rtype: str) -> int:
    """Convierte tipo DNS string a número (para Google DoH)."""
    return {"A": 1, "MX": 15, "TXT": 16, "NS": 2, "CNAME": 5}.get(rtype, 1)


async def whois_lookup(domain: str) -> Dict[str, Any]:
    """
    WHOIS lookup — NIST SP 800-115 §A.1 (OSINT from public registers).
    Estrategia: RDAP (HTTPS) primero → python-whois → whois CLI.
    """
    result: Dict[str, Any] = {"domain": domain, "raw": {}}

    # 1) RDAP via HTTPS (siempre disponible, sin puerto 43)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
            r = await c.get(f"https://rdap.org/domain/{domain}")
            if r.status_code == 200:
                d = r.json()
                events = {e.get("eventAction", ""): e.get("eventDate", "")
                          for e in d.get("events", [])}
                ns = [n.get("ldhName", "") for n in d.get("nameservers", [])]
                # Buscar registrar en entities
                registrar = None
                for ent in d.get("entities", []):
                    if ent.get("roles") and "registrar" in ent.get("roles", []):
                        registrar = ent.get("vcardArray", [None, None])[1].get("fn", {}).get("value") if len(ent.get("vcardArray", [])) > 1 else None
                        if not registrar:
                            registrar = str(ent.get("handle", ""))
                        break
                result["raw"] = {
                    "source": "rdap",
                    "registrar": registrar,
                    "creation_date": events.get("registration", ""),
                    "expiration_date": events.get("expiration", ""),
                    "name_servers": ns,
                    "status": d.get("status", []),
                }
                return result
    except Exception:
        pass

    # 2) python-whois (puerto 43, puede timeout en sandboxes sin red abierta)
    try:
        import whois as python_whois
        w = await asyncio.to_thread(python_whois.whois, domain)
        result["raw"] = {
            "source": "python-whois",
            "registrar": w.registrar,
            "creation_date": str(w.creation_date) if w.creation_date else None,
            "expiration_date": str(w.expiration_date) if w.expiration_date else None,
            "name_servers": w.name_servers,
            "status": w.status,
            "emails": w.emails,
            "org": w.org,
            "country": w.country,
        }
        return result
    except Exception:
        pass

    # 3) whois CLI
    try:
        import subprocess
        proc = await asyncio.to_thread(
            subprocess.run, ["whois", domain],
            capture_output=True, text=True, timeout=8
        )
        if proc.stdout and proc.stdout.strip():
            result["raw"] = {"source": "cli", "cli_output": proc.stdout[:2000]}
            return result
    except Exception:
        pass

    # 4) urllib fallback (RDAP)
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://rdap.org/domain/{domain}",
            headers={"Accept": "application/rdap+json"}
        )
        resp = await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=8))
        d = json.loads(resp.read().decode())
        events = {e.get("eventAction", ""): e.get("eventDate", "")
                  for e in d.get("events", [])}
        ns = [n.get("ldhName", "") for n in d.get("nameservers", [])]
        result["raw"] = {
            "source": "rdap-urllib",
            "registrar": None,
            "creation_date": events.get("registration", ""),
            "expiration_date": events.get("expiration", ""),
            "name_servers": ns,
            "status": d.get("status", []),
        }
        return result
    except Exception as e3:
        result["raw"] = {"error": f"Todos los metodos WHOIS fallaron: {e3}"}

    return result


async def dns_recon(domain: str) -> Dict[str, Any]:
    """
    DNS reconnaissance — NIST SP 800-115 §A.3.
    Recopila A, MX, TXT, NS, CNAME records.
    """
    result: Dict[str, Any] = {"domain": domain, "records": {}}
    result["records"]["A"] = await asyncio.to_thread(_dns_resolve, domain, "A")
    result["records"]["MX"] = await asyncio.to_thread(_dns_resolve, domain, "MX")
    result["records"]["TXT"] = await asyncio.to_thread(_dns_resolve, domain, "TXT")
    result["records"]["NS"] = await asyncio.to_thread(_dns_resolve, domain, "NS")

    txt_records = result["records"].get("TXT", [])
    result["spf"] = any("spf1" in t.lower() for t in txt_records)
    result["dmarc"] = any("dmarc" in t.lower() for t in txt_records)

    dkim = await asyncio.to_thread(_dns_resolve, f"_dmarc.{domain}", "TXT")
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



def _apply_geo(geo_data: dict, result: dict):
    """Aplica datos de geolocalización al resultado de threat intel."""
    result["factors"].append({
        "factor": "Country",
        "value": geo_data.get("country", "?"),
    })
    conn_type = geo_data.get("connection", {}).get("type")
    if conn_type in ("hosting", "tor"):
        result["factors"].append({
            "factor": "Hosting/Tor",
            "value": conn_type,
        })
        result["score"] += 10

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

    # Geo IP lookup — intentar httpx, fallback a urllib
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                _apply_geo(geo_data=resp.json(), result=result)
    except ImportError:
        # Fallback: urllib (stdlib)
        try:
            import urllib.request
            req = urllib.request.Request(f"https://ipwho.is/{ip}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                _apply_geo(geo_data=json.loads(resp.read().decode()), result=result)
        except Exception:
            pass
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

    domain = email.split("@")[1]   # despues del @
    username = email.split("@")[0]  # antes del @

    result: Dict[str, Any] = {
        "email": email,
        "domain": domain,
        "username": username,
        "hash_sha256": hashlib.sha256(email.encode()).hexdigest(),
        "mx_records": await asyncio.to_thread(_dns_resolve, domain, "MX"),
        "spf": False,
        "dmarc": False,
    }

    txt = await asyncio.to_thread(_dns_resolve, domain, "TXT")
    result["spf"] = any("spf1" in t.lower() for t in txt)

    dmarc = await asyncio.to_thread(_dns_resolve, f"_dmarc.{domain}", "TXT")
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



def _apply_headers(headers: dict, status_code: int, result: dict):
    """Aplica headers HTTP al resultado de fingerprinting."""
    result["headers"] = {
        "server": headers.get("server", headers.get("Server", "Desconocido")),
        "x_powered_by": headers.get("x-powered-by", headers.get("X-Powered-By", "Desconocido")),
        "content_type": headers.get("content-type", headers.get("Content-Type", "Desconocido")),
        "status_code": status_code,
    }
    security = {}
    for h in ["strict-transport-security", "x-frame-options",
               "x-content-type-options", "content-security-policy",
               "x-xss-protection", "referrer-policy",
               "permissions-policy"]:
        val = headers.get(h) or headers.get(h.title())
        security[h] = "present" if val else "missing"
    result["security_headers"] = security
    result["security_score"] = sum(1 for v in security.values() if v == "present")
    result["security_total"] = len(security)

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
            _apply_headers(resp.headers, resp.status_code, result)
    except ImportError:
        # Fallback: urllib
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            _apply_headers(dict(resp.headers.items()), resp.status, result)

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
            return _parse_ddg_results(resp.text, q, num)
    except ImportError:
        # Fallback: urllib (stdlib)
        try:
            import urllib.request
            import urllib.parse as _up
            url = f"https://html.duckduckgo.com/html/?q={_up.quote(q)}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return _parse_ddg_results(resp.read().decode(), q, num)
        except Exception as e:
            return {"query": q, "engine": "none", "results": [], "error": str(e)}
    except Exception as e:
        return {"query": q, "engine": "none", "results": [], "error": str(e)}

def _parse_ddg_results(html: str, q: str, num: int) -> dict:
    """Parsea resultados de DuckDuckGo HTML."""
    results = []
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)', html)
    for url, title in links[:num]:
        if "uddg=" in url:
            from urllib.parse import parse_qs, urlparse as up, unquote
            parsed = up(url)
            qs = parse_qs(parsed.query)
            url = unquote(qs.get("uddg", [url])[0])
        results.append({"title": title.strip(), "link": url, "snippet": "", "displayLink": ""})
    return {"query": q, "engine": "duckduckgo", "results": results, "total": len(results)}


# ============================================================================
# SHODAN HOST LOOKUP
# ============================================================================

# ── Enriquecimiento local para IPs privadas ──────────────────────────
import ipaddress as _ipaddr
import re as _re

_LOCAL_PORTS = [22, 23, 53, 80, 443, 554, 1883, 37777, 5000, 8000, 8080, 8443, 8554, 9000]
_SVC_NAMES = {22:"ssh", 23:"telnet", 53:"dns", 80:"http", 443:"https", 554:"rtsp",
              1883:"mqtt", 37777:"dahua-dvr", 5000:"http", 8000:"http-alt",
              8080:"http-proxy", 8443:"https-alt", 8554:"rtsp-alt", 9000:"http"}

def _is_private_ip(ip: str) -> bool:
    try:
        return _ipaddr.ip_address(ip).is_private
    except ValueError:
        return False

def _get_mac(ip: str):
    try:
        import subprocess as _sp
        out = _sp.check_output(["ip", "neigh", "show", ip],
                               stderr=_sp.DEVNULL, timeout=3).decode()
        for tok in out.split():
            if _re.fullmatch(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", tok):
                return tok.lower()
    except Exception:
        pass
    return None

async def _ping_latency(ip: str):
    try:
        import subprocess as _sp
        out = _sp.check_output(["ping", "-c", "1", "-W", "1", ip],
                               stderr=_sp.DEVNULL, timeout=3).decode()
        m = _re.search(r"time[=<]([\d.]+)", out)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None

def _guess_type(ports):
    ps = {p["port"] for p in ports}
    if ps & {554, 8554, 37777, 8000}:
        return "camera"
    if ps & {23, 80, 443} and len(ps) >= 2:
        return "router"
    if ps & {1883}:
        return "iot"
    return "unknown"

async def _local_enrich(ip: str) -> dict:
    """Escaneo local real: puertos TCP, MAC, latencia, tipo inferido."""
    import asyncio as _aio
    ports = []
    for p in _LOCAL_PORTS:
        try:
            fut = _aio.open_connection(ip, p, limit=1)
            reader, writer = await _aio.wait_for(fut, timeout=1.0)
            banner = ""
            try:
                data = await _aio.wait_for(reader.read(256), timeout=0.5)
                banner = data.decode(errors="replace").strip()[:80]
            except _aio.TimeoutError:
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            ports.append({"port": p, "service": _SVC_NAMES.get(p, "unknown"),
                          "state": "open", "banner": banner})
        except (_aio.TimeoutError, ConnectionRefusedError, OSError):
            continue
    from datetime import datetime as _dt
    return {
        "ip": ip, "mac": _get_mac(ip), "vendor": None, "hostname": None,
        "latency_ms": await _ping_latency(ip), "ports": ports,
        "type": _guess_type(ports), "first_seen": _dt.now().isoformat(),
    }


@osint_router.get("/shodan/{ip}")
async def api_shodan(ip: str):
    """
    Shodan host lookup — NIST SP 800-150.
    Para IPs privadas: enriquecimiento local real (puertos, MAC, latencia).
    Para IPs publicas: Shodan real (requiere SHODAN_API_KEY).
    """

    # Validacion estricta
    try:
        _ipaddr.ip_address(ip)
    except ValueError:
        from fastapi.responses import JSONResponse as _JR
        return _JR({"status": "error", "error": f"IP invalida: {ip}"}, status_code=422)

    # IP PRIVADA -> enriquecimiento local real + advertencia
    if _is_private_ip(ip):
        host = await _local_enrich(ip)
        return {
            "ip": ip,
            "status": "local",
            "warning": "IP privada: Shodan solo indexa internet publico. "
                       "Estos datos son REALES, obtenidos por escaneo local de tu red.",
            "source": "escaneo-local",
            "hostnames": [],
            "org": None, "os": None,
            "ports": [p["port"] for p in host["ports"]],
            "services": host["ports"],
            "mac": host["mac"],
            "latency_ms": host["latency_ms"],
            "type": host["type"],
            "country": "Local Network",
            "city": None, "isp": None,
            "tags": [], "vulns": [],
        }

    # IP PUBLICA -> Shodan real
    shodan_key = os.environ.get("SHODAN_API_KEY", "")
    if not shodan_key:
        from fastapi.responses import JSONResponse as _JR
        return _JR({"ip": ip, "status": "error",
                     "error": "SHODAN_API_KEY no configurada. "
                              "Usa una IP privada (192.168.x.x) para escaneo local."},
                    status_code=503)
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
                    "ip": ip, "status": "shodan", "source": "shodan",
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
                return {"ip": ip, "status": "error", "source": "shodan", "error": f"Shodan no tiene datos publicos para {ip}"}
            else:
                return {"ip": ip, "status": "error", "source": "shodan", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ip": ip, "status": "error", "source": "shodan", "error": str(e)}


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

# ============================================================================
# PLATFORM DETECTION CONFIG — datos de verificación reales por sitio
# Metodología del proyecto Sherlock (sherlock-project/sherlock,
# sherlock_project/resources/data.json), adaptada a httpx async y
# VALIDADA EN VIVO contra cuentas reales y username inventados antes
# de subir esto a producción (2026-08-20).
#
# Por qué el checker anterior era pura alucinación: marcaba
# "exists": true con solo status_code == 200. La mayoría de estas
# plataformas devuelven 200 para CUALQUIER ruta — son SPAs que
# renderizan "usuario no encontrado" con JavaScript, invisible para
# un scraper — así que cualquier username, real o inventado, salía
# "true". Cada plataforma tiene su propia forma real de indicar
# "no existe": un string específico en el HTML/JSON, un endpoint de
# API separado, o (raramente) un status_code que sí es confiable.
#
# Plataformas retiradas de la lista por bloqueo anti-bot verificado en
# vivo (Instagram, LinkedIn, Facebook, Reddit, Twitter/X vía nitter):
# devuelven la MISMA respuesta exista o no la cuenta desde este tipo
# de origen (IP de datacenter) — cualquier resultado sería inventado.
# Se marcan como "unreliable" en vez de adivinar.
# ============================================================================

PLATFORMS = {
    "github": {
        "url": "https://www.github.com/{u}",
        "check": "status_code",
        "regex": r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$",
    },
    "gitlab": {
        "url": "https://gitlab.com/{u}",
        "probe": "https://gitlab.com/api/v4/users?username={u}",
        "check": "message_means_missing",
        "error_msgs": ["[]"],
        "note": "vía API oficial de GitLab",
    },
    "youtube": {
        "url": "https://www.youtube.com/@{u}",
        "check": "status_code",
    },
    "tiktok": {
        "url": "https://www.tiktok.com/@{u}",
        "check": "message_means_missing",
        "error_msgs": ['"statusCode":10221', "Govt. of India decided to block 59 apps"],
    },
    "telegram": {
        "url": "https://t.me/{u}",
        "check": "message_means_missing",
        "error_msgs": [
            '<div class="tgme_page_context_link_icon">',
            'tgme_username_link" href="tg://resolve?domain=',
        ],
        "regex": r"^[a-zA-Z0-9_]{3,32}[^_]$",
        "note": "solo detecta usernames públicos indexables, no canales privados",
    },
    "medium": {
        "url": "https://medium.com/@{u}",
        "probe": "https://medium.com/feed/@{u}",
        "check": "message_means_missing",
        "error_msgs": ["<body"],
        "note": "vía feed RSS",
    },
    "pinterest": {
        "url": "https://www.pinterest.com/{u}/",
        "probe": "https://www.pinterest.com/oembed.json?url=https://www.pinterest.com/{u}/",
        "check": "status_code",
    },
    "snapchat": {
        "url": "https://www.snapchat.com/add/{u}",
        "check": "status_code",
        "regex": r"^[a-z][a-z0-9-_.]{2,14}$",
    },
    "twitch": {
        "url": "https://www.twitch.tv/{u}",
        "check": "message_means_missing",
        "error_msgs": [
            "content='Twitch is the world&#39;s leading video platform and community for gamers.'"
        ],
    },
    "steam": {
        "url": "https://steamcommunity.com/id/{u}/",
        "check": "message_means_missing",
        "error_msgs": ["The specified profile could not be found"],
    },
    # --- Sin verificación confiable sin autenticación (bloqueo anti-bot
    #     confirmado en vivo — misma respuesta exista o no la cuenta) ---
    "instagram": {
        "url": "https://instagram.com/{u}",
        "check": "unreliable",
        "note": "Instagram devuelve 200 (shell SPA) o 403 (anti-bot) igual exista o no la cuenta",
    },
    "linkedin": {
        "url": "https://linkedin.com/in/{u}",
        "check": "unreliable",
        "note": "LinkedIn bloquea scraping no autenticado — misma respuesta exista o no la cuenta",
    },
    "facebook": {
        "url": "https://facebook.com/{u}",
        "check": "unreliable",
        "note": "Facebook redirige a login para cualquier perfil, exista o no",
    },
    "reddit": {
        "url": "https://www.reddit.com/user/{u}",
        "check": "unreliable",
        "note": "Reddit bloquea con 403/challenge anti-bot igual exista o no la cuenta",
    },
    "twitter": {
        "url": "https://x.com/{u}",
        "check": "unreliable",
        "note": "x.com requiere JavaScript; los espejos públicos (nitter) están caídos",
    },
}


@osint_router.post("/social")
async def api_social_search(req: OSINTRequest):
    """
    Social media username search — MITRE ATT&CK T1589 (Gather Victim Identity Info).

    Verificación real por plataforma (no solo status_code == 200), usando la
    metodología de Sherlock: mensajes de error específicos, endpoints de API
    cuando existen, y validación de formato de username antes de gastar
    requests en rutas que ninguna plataforma real aceptaría.

    Plataformas sin forma confiable de verificar sin autenticación
    (Instagram, LinkedIn, Facebook, Reddit, Twitter/X) se marcan
    "exists": null en vez de adivinar — ver campo "note".
    """
    raw_username = req.target.replace("@", "").strip()
    results = []
    sem = asyncio.Semaphore(10)

    warnings = []
    if " " in raw_username:
        warnings.append(
            "El input contiene espacios — parece un nombre completo, no un "
            "username. Ningún username real de estas plataformas admite "
            "espacios; los resultados de las plataformas con validación de "
            "formato saldrán como 'formato inválido'. Prueba variantes sin "
            "espacios (ej: nombreapellido, nombre.apellido, nombre_apellido)."
        )

    async def check_platform(name: str, cfg: dict):
        from urllib.parse import quote
        username = quote(raw_username, safe="")

        # 1. Validar formato ANTES de gastar un request — si el username no
        #    cumple el patrón que la plataforma exige, no puede existir.
        regex = cfg.get("regex")
        if regex and not re.match(regex, raw_username):
            results.append({
                "platform": name,
                "url": cfg["url"].replace("{u}", username),
                "exists": False,
                "status_code": None,
                "note": "Formato de username inválido para esta plataforma — no se hizo la solicitud",
            })
            return

        # 2. Plataformas sin verificación confiable sin autenticación
        if cfg.get("check") == "unreliable":
            results.append({
                "platform": name,
                "url": cfg["url"].replace("{u}", username),
                "exists": None,
                "status_code": None,
                "note": cfg.get("note", "No hay forma confiable de verificar sin autenticación"),
            })
            return

        target_url = cfg.get("probe", cfg["url"]).replace("{u}", username)
        display_url = cfg["url"].replace("{u}", username)

        async with sem:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10, follow_redirects=True, verify=False) as client:
                    resp = await client.get(
                        target_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        },
                    )
                    check_type = cfg.get("check", "status_code")

                    if check_type == "status_code":
                        exists = resp.status_code == 200
                    elif check_type == "message_means_missing":
                        # OJO: no truncar el body — algunos marcadores de "no
                        # existe" aparecen bien adentro de la página (ej. Steam
                        # a los ~26KB). Truncar a 2000 chars fue justo el bug
                        # original que causaba falsos positivos.
                        found_error = any(msg in resp.text for msg in cfg.get("error_msgs", []))
                        exists = resp.status_code == 200 and not found_error
                    else:
                        exists = resp.status_code == 200

                    entry = {
                        "platform": name,
                        "url": display_url,
                        "exists": exists,
                        "status_code": resp.status_code,
                    }
                    if cfg.get("note"):
                        entry["note"] = cfg["note"]
                    results.append(entry)
            except Exception as e:
                results.append({
                    "platform": name,
                    "url": display_url,
                    "exists": False,
                    "error": str(e)[:100],
                    "note": "Fallo de conexión — no confirmado ni descartado",
                })

    tasks = [check_platform(name, cfg) for name, cfg in PLATFORMS.items()]
    await asyncio.gather(*tasks)

    found = [r for r in results if r["exists"] is True]
    unreliable = [r for r in results if r["exists"] is None]

    return {
        "username": raw_username,
        "found": found,
        "unreliable": unreliable,
        "total_found": len(found),
        "total_checked": len(results),
        "warnings": warnings,
    }


# ============================================================================
# MULTI-ENGINE SEARCH — DuckDuckGo, Bing, Yahoo, Brave, Yandex, Tor
# ============================================================================

SUPPORTED_ENGINES = [
    "duckduckgo", "bing", "yahoo", "brave", "yandex", "google", "tor", "all"
]

# User-Agent rotatorio para evitar bloqueos
_UAS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


async def _search_duckduckgo(client, query: str, num: int) -> List[Dict]:
    """DuckDuckGo HTML — sin API key, scraping ligero."""
    resp = await client.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"User-Agent": _UAS[0]},
    )
    results = []
    if resp.status_code == 200:
        # DDG usa result__a para links y result__snippet
        blocks = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</(?:a|span)',
            resp.text, re.DOTALL
        )
        for url, title, snippet in blocks[:num]:
            if "uddg=" in url:
                from urllib.parse import parse_qs, urlparse as up, unquote
                parsed = up(url)
                qs = parse_qs(parsed.query)
                url = unquote(qs.get("uddg", [url])[0])
            results.append({
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "link": url.strip(),
                "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
                "engine": "duckduckgo",
            })
    return results


async def _search_bing(client, query: str, num: int) -> List[Dict]:
    """Bing — scraping HTML, sin API key."""
    resp = await client.get(
        "https://www.bing.com/search",
        params={"q": query, "count": str(num)},
        headers={"User-Agent": _UAS[1]},
    )
    results = []
    if resp.status_code == 200:
        blocks = re.findall(
            r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>',
            resp.text, re.DOTALL
        )
        for url, title, snippet in blocks[:num]:
            if url.startswith("/"):
                url = "https://www.bing.com" + url
            results.append({
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "link": url.strip(),
                "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
                "engine": "bing",
            })
    return results


async def _search_yahoo(client, query: str, num: int) -> List[Dict]:
    """Yahoo Search — scraping HTML."""
    resp = await client.get(
        "https://search.yahoo.com/search",
        params={"p": query, "n": str(num)},
        headers={"User-Agent": _UAS[2]},
    )
    results = []
    if resp.status_code == 200:
        blocks = re.findall(
            r'<a[^>]*class="[^"]*ac-algo[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<span[^>]*>(.*?)</span>',
            resp.text, re.DOTALL
        )
        for url, title, snippet in blocks[:num]:
            results.append({
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "link": url.strip(),
                "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
                "engine": "yahoo",
            })
    return results


async def _search_brave(client, query: str, num: int) -> List[Dict]:
    """Brave Search — scraping HTML (sin API key).
    Brave también tiene API oficial en api.search.brave.com si hay key."""
    brave_key = os.environ.get("BRAVE_API_KEY", "")
    if brave_key:
        try:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": num},
                headers={
                    "X-Subscription-Token": brave_key,
                    "Accept": "application/json",
                },
            )
            results = []
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("web", {}).get("results", [])[:num]:
                    results.append({
                        "title": item.get("title", ""),
                        "link": item.get("url", ""),
                        "snippet": item.get("description", ""),
                        "engine": "brave",
                    })
            return results
        except Exception:
            pass
    # Fallback: scraping HTML
    resp = await client.get(
        "https://search.brave.com/search",
        params={"q": query},
        headers={"User-Agent": _UAS[3]},
    )
    results = []
    if resp.status_code == 200:
        blocks = re.findall(
            r'<a[^>]*class="[^"]*result-header[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<span[^>]*>(.*?)</span>',
            resp.text, re.DOTALL
        )
        for url, title in blocks[:num]:
            results.append({
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "link": url.strip(),
                "snippet": "",
                "engine": "brave",
            })
    return results


async def _search_yandex(client, query: str, num: int) -> List[Dict]:
    """Yandex Search — scraping HTML."""
    resp = await client.get(
        "https://yandex.com/search",
        params={"text": query},
        headers={"User-Agent": _UAS[0], "Accept-Language": "en-US,en;q=0.9"},
    )
    results = []
    if resp.status_code == 200:
        # Yandex usa organic__url para links
        blocks = re.findall(
            r'class="organic__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        )
        for url, title in blocks[:num]:
            results.append({
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "link": url.strip(),
                "snippet": "",
                "engine": "yandex",
            })
    return results


async def _search_google(client, query: str, num: int) -> List[Dict]:
    """Google Custom Search API (si hay key) o fallback a DuckDuckGo."""
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    cse_id = os.environ.get("GOOGLE_CSE_ID", "")
    if google_key and cse_id:
        try:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": google_key, "cx": cse_id, "q": query, "num": num},
            )
            results = []
            if resp.status_code == 200:
                for item in resp.json().get("items", [])[:num]:
                    results.append({
                        "title": item.get("title", ""),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "engine": "google",
                    })
            return results
        except Exception:
            pass
    # Sin key -> no devolver nada, el caller con "all" usará DDG
    return []


async def _search_tor(client, query: str, num: int) -> List[Dict]:
    """Tor search via Ahmia (onion search) — sin proxy Tor requerido.
    Ahmia expone resultados en clearnet."""
    try:
        resp = await client.get(
            "https://ahmia.fi/search/",
            params={"q": query},
            headers={"User-Agent": _UAS[0]},
        )
        results = []
        if resp.status_code == 200:
            # Ahmia usa li con clase resultado
            blocks = re.findall(
                r'<h4[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h4>.*?<p[^>]*>(.*?)</p>',
                resp.text, re.DOTALL
            )
            for url, title, snippet in blocks[:num]:
                # Ahima puede devolver links .onion o links a ahmia
                if "ahmia.fi" in url and "onion" not in url:
                    # extraer el onion real del redirect
                    onion_match = re.search(r'([a-z0-9]{16,56}\.onion)', resp.text)
                    if onion_match:
                        url = "http://" + onion_match.group(1)
                results.append({
                    "title": re.sub(r"<[^>]+>", "", title).strip(),
                    "link": url.strip(),
                    "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
                    "engine": "tor",
                })
        return results
    except Exception:
        return []


_SEARCH_FUNCS = {
    "duckduckgo": _search_duckduckgo,
    "bing": _search_bing,
    "yahoo": _search_yahoo,
    "brave": _search_brave,
    "yandex": _search_yandex,
    "google": _search_google,
    "tor": _search_tor,
}


@osint_router.get("/search")
async def multi_engine_search(
    q: str = Query(..., description="Consulta de busqueda"),
    engine: str = Query("duckduckgo", description=f"Motor: {', '.join(SUPPORTED_ENGINES)}"),
    num: int = Query(10, ge=1, le=30, description="Resultados por motor"),
):
    """
    Multi-Engine Search OSINT — NIST SP 800-115 §A.1.
    
    Motores soportados:
    - duckduckgo: HTML scraping (sin API key)
    - bing: HTML scraping (sin API key)
    - yahoo: HTML scraping (sin API key)
    - brave: API oficial (si BRAVE_API_KEY) o HTML scraping
    - yandex: HTML scraping (sin API key)
    - google: Custom Search API (si GOOGLE_API_KEY + GOOGLE_CSE_ID)
    - tor: Ahmia.fi onion search (sin Tor browser requerido)
    - all: Ejecuta TODOS los motores en paralelo, deduplica resultados
    """
    import httpx
    import random

    ua = random.choice(_UAS)
    timeout = httpx.Timeout(15.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
        if engine == "all":
            tasks = []
            for eng, func in _SEARCH_FUNCS.items():
                tasks.append(func(client, q, num))
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            all_results = []
            errors = []
            engines_used = []
            for eng, res in zip(_SEARCH_FUNCS.keys(), raw_results):
                if isinstance(res, Exception):
                    errors.append(f"{eng}: {str(res)[:80]}")
                else:
                    all_results.extend(res)
                    if res:
                        engines_used.append(eng)

            # Deduplicar por URL
            seen = set()
            deduped = []
            for r in all_results:
                key = r.get("link", "").rstrip("/").lower()
                if key and key not in seen:
                    seen.add(key)
                    deduped.append(r)

            return {
                "query": q,
                "engine": "all",
                "engines_used": engines_used,
                "results": deduped[:num * len(engines_used)],
                "total": len(deduped),
                "errors": errors,
            }
        elif engine in _SEARCH_FUNCS:
            try:
                results = await _SEARCH_FUNCS[engine](client, q, num)
                return {
                    "query": q,
                    "engine": engine,
                    "results": results,
                    "total": len(results),
                }
            except Exception as e:
                return {
                    "query": q,
                    "engine": engine,
                    "results": [],
                    "total": 0,
                    "error": str(e),
                }
        else:
            return {
                "query": q,
                "engine": engine,
                "results": [],
                "total": 0,
                "error": f"Motor no soportado. Usa: {', '.join(SUPPORTED_ENGINES)}",
            }


@osint_router.get("/search/engines")
async def list_search_engines():
    """Lista los motores de búsqueda disponibles y su estado."""
    engines = []
    for eng in SUPPORTED_ENGINES:
        info = {
            "engine": eng,
            "requires_key": False,
            "has_key": True,
            "description": "",
        }
        if eng == "google":
            info["requires_key"] = True
            info["has_key"] = bool(os.environ.get("GOOGLE_API_KEY"))
            info["description"] = "Google Custom Search API (requiere GOOGLE_API_KEY + GOOGLE_CSE_ID)"
        elif eng == "brave":
            info["requires_key"] = False
            info["has_key"] = bool(os.environ.get("BRAVE_API_KEY"))
            info["description"] = "Brave Search — API oficial (opcional BRAVE_API_KEY) o HTML scraping"
        elif eng == "duckduckgo":
            info["description"] = "DuckDuckGo HTML — sin API key, scraping"
        elif eng == "bing":
            info["description"] = "Bing Search — sin API key, scraping"
        elif eng == "yahoo":
            info["description"] = "Yahoo Search — sin API key, scraping"
        elif eng == "yandex":
            info["description"] = "Yandex Search — sin API key, scraping"
        elif eng == "tor":
            info["description"] = "Tor onion search via Ahmia.fi — sin Tor browser requerido"
        elif eng == "all":
            info["description"] = "Ejecuta TODOS los motores en paralelo, deduplica resultados"
        engines.append(info)
    return {"engines": engines, "total": len(engines)}
