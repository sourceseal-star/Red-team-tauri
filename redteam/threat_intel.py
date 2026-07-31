"""
Threat Intelligence Module — SourceSeal Red Team

Descarga IOCs reales de feeds gratuitos y los sirve via API.
Fuentes: AlienVault OTX, abuse.ch URLhaus, Tor Exit Nodes, AbuseIPDB
"""
import json
import os
import time
import threading
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

# ── Storage ──────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
IOC_FILE = DATA_DIR / "iocs.json"

# Cache en memoria
_iocs_cache: list[dict] = []
_iocs_lock = threading.Lock()

# ── Feeds gratuitos ──────────────────────────────────────────────
FEEDS = {
    "alienvault": {
        "url": "https://otx.alienvault.com/api/v1/indicators/export",
        "type": "ip",
        "label": "AlienVault OTX",
    },
    "abusech_urlhaus": {
        "url": "https://urlhaus.abuse.ch/downloads/text/",
        "type": "url",
        "label": "abuse.ch URLhaus",
    },
    "tor_exit": {
        "url": "https://check.torproject.org/exit-addresses",
        "type": "ip",
        "label": "Tor Exit Nodes",
    },
    "abuseipdb": {
        "url": "https://raw.githubusercontent.com/stamparm/ipsum/master/levels/3.txt",
        "type": "ip",
        "label": "IPsum (GitHub)",
    },
}


def _load_iocs() -> list[dict]:
    """Carga IOCs desde el archivo JSON local"""
    global _iocs_cache
    with _iocs_lock:
        if _iocs_cache:
            return _iocs_cache
        if IOC_FILE.exists():
            try:
                _iocs_cache = json.loads(IOC_FILE.read_text("utf-8"))
            except Exception:
                _iocs_cache = []
        else:
            _iocs_cache = []
        return _iocs_cache


def _save_iocs(iocs: list[dict]):
    """Guarda IOCs al archivo JSON local"""
    global _iocs_cache
    with _iocs_lock:
        _iocs_cache = iocs
        IOC_FILE.write_text(json.dumps(iocs, indent=2), "utf-8")


def _fetch_alienvault() -> list[dict]:
    """AlienVault OTX — IPs maliciosas"""
    if not requests:
        return []
    try:
        r = requests.get(FEEDS["alienvault"]["url"], timeout=10)
        if r.status_code != 200:
            return []
        results = []
        lines = r.text.strip().split("\n")
        for line in lines[1:100]:  # skip header, first 100
            parts = line.split(",")
            if parts and parts[0].strip():
                results.append({
                    "id": f"otx-{len(results)}",
                    "type": "ip",
                    "value": parts[0].strip(),
                    "confidence": 70,
                    "tags": ["alienvault", "otx"],
                    "source": "AlienVault OTX",
                    "added": datetime.now().isoformat(),
                })
        return results
    except Exception:
        return []


def _fetch_urlhaus() -> list[dict]:
    """abuse.ch URLhaus — URLs maliciosas"""
    if not requests:
        return []
    try:
        r = requests.get(FEEDS["abusech_urlhaus"]["url"], timeout=10)
        if r.status_code != 200:
            return []
        results = []
        lines = r.text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            results.append({
                "id": f"urlhaus-{len(results)}",
                "type": "url",
                "value": line,
                "confidence": 85,
                "tags": ["malware", "urlhaus"],
                "source": "abuse.ch URLhaus",
                "added": datetime.now().isoformat(),
            })
            if len(results) >= 100:
                break
        return results
    except Exception:
        return []


def _fetch_tor_exits() -> list[dict]:
    """Tor Exit Nodes — nodos de salida"""
    if not requests:
        return []
    try:
        r = requests.get(FEEDS["tor_exit"]["url"], timeout=10)
        if r.status_code != 200:
            return []
        results = []
        for line in r.text.split("\n"):
            if line.startswith("ExitAddress"):
                parts = line.split()
                if len(parts) >= 2:
                    results.append({
                        "id": f"tor-{len(results)}",
                        "type": "ip",
                        "value": parts[1],
                        "confidence": 50,
                        "tags": ["tor", "exit-node", "anonymizer"],
                        "source": "Tor Project",
                        "added": datetime.now().isoformat(),
                    })
        return results[:100]
    except Exception:
        return []


def _fetch_ipsum() -> list[dict]:
    """IPsum — IPs con score 3+ (múltiples fuentes confirman maliciosas)"""
    if not requests:
        return []
    try:
        r = requests.get(FEEDS["abuseipdb"]["url"], timeout=10)
        if r.status_code != 200:
            return []
        results = []
        for line in r.text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            results.append({
                "id": f"ipsum-{len(results)}",
                "type": "ip",
                "value": line,
                "confidence": 75,
                "tags": ["ipsum", "malicious"],
                "source": "IPsum (GitHub)",
                "added": datetime.now().isoformat(),
            })
            if len(results) >= 50:
                break
        return results
    except Exception:
        return []


def fetch_all_iocs() -> list[dict]:
    """Descarga IOCs de todos los feeds y los combina"""
    all_iocs = []
    all_iocs.extend(_fetch_alienvault())
    all_iocs.extend(_fetch_urlhaus())
    all_iocs.extend(_fetch_tor_exits())
    all_iocs.extend(_fetch_ipsum())

    # Merge con IOCs existentes (no duplicar)
    existing = _load_iocs()
    existing_values = {i["value"] for i in existing}

    new_iocs = [i for i in all_iocs if i["value"] not in existing_values]
    merged = existing + new_iocs

    _save_iocs(merged)
    return merged


def get_iocs() -> list[dict]:
    """Retorna todos los IOCs cacheados"""
    return _load_iocs()


def add_ioc(ioc: dict) -> dict:
    """Agrega un IOC manualmente"""
    iocs = _load_iocs()
    ioc["id"] = ioc.get("id") or f"manual-{int(time.time())}"
    ioc["added"] = ioc.get("added") or datetime.now().isoformat()
    ioc.setdefault("confidence", 50)
    ioc.setdefault("tags", [])
    ioc.setdefault("type", "ip")
    ioc.setdefault("source", "manual")
    iocs.append(ioc)
    _save_iocs(iocs)
    return {"ok": True, "id": ioc["id"]}


def delete_ioc(ioc_id: str) -> dict:
    """Elimina un IOC por ID"""
    iocs = _load_iocs()
    filtered = [i for i in iocs if i.get("id") != ioc_id]
    _save_iocs(filtered)
    return {"ok": True}


def import_stix(bundle: dict) -> dict:
    """Importa un bundle STIX 2.1"""
    count = 0
    iocs = _load_iocs()
    objects = bundle.get("objects", []) if isinstance(bundle, dict) else []

    for obj in objects:
        if obj.get("type") == "indicator":
            pattern = obj.get("pattern", "")
            # Extraer valor del patron STIX (ej: "[ipv4-addr:value = '1.2.3.4']")
            value = ""
            if "=" in pattern:
                value = pattern.split("=", 1)[1].strip().strip("'\"]")
            if value:
                iocs.append({
                    "id": obj.get("id", f"stix-{count}"),
                    "type": "indicator",
                    "value": value,
                    "confidence": 60,
                    "tags": ["stix"],
                    "source": "STIX import",
                    "added": datetime.now().isoformat(),
                })
                count += 1

    _save_iocs(iocs)
    return {"ok": True, "imported": count}
