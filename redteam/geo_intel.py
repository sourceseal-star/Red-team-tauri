"""
Geo + Threat Intel — módulo Python puro (stdlib only).
Usado por dashboard_server.py para /api/geo e /api/intel.
"""
import urllib.request
import urllib.error
import json
import socket
import threading
import time
import re
from pathlib import Path

_cache: dict = {}
_cache_lock = threading.Lock()
TTL = 30 * 60  # 30 min

PRIVATE_RE = re.compile(
    r'^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|0\.0\.0\.0|169\.254\.|::1|fd)'
)

HOSTING_ISP = re.compile(
    r'digitalocean|amazon|google|microsoft|azure|ovh|hetzner|vultr|linode|cloudflare|'
    r'contabo|scaleway|upcloud|kamatera|hostinger|godaddy|m247|psychz|leaseweb|akamai|'
    r'fastly|cloudfront|rackspace|softlayer|ionos|1&1|internap|cogent|hurricane electric',
    re.I
)

BULLETPROOF = re.compile(
    r'marosnet|king servers|hostkey|firstheberg|neterra|abeloost|m247|psychz', re.I
)

# ── Geo ──────────────────────────────────────────────────────────────────────
def lookup(ip: str) -> dict:
    ip = ip.strip()
    if not ip:
        return {'error': 'ip requerida'}
    if PRIVATE_RE.match(ip):
        return {'ip': ip, 'private': True, 'lat': None, 'lon': None,
                'country': '—', 'city': '—', 'isp': 'red privada / LAN',
                'as': '—', 'proxy': False, 'hosting': False, 'mobile': False,
                'note': 'IP privada: sin geolocalización pública (esperado, no un error).'}
    with _cache_lock:
        c = _cache.get('geo:' + ip)
        if c and time.time() - c['t'] < TTL:
            return c['v']
    try:
        url = f'https://ipwho.is/{ip}?fields=success,country,city,latitude,longitude,connection,flag'
        req = urllib.request.Request(url, headers={'User-Agent': 'SourceSeal-RedTeam/2.0'})
        with urllib.request.urlopen(req, timeout=12) as r:
            j = json.loads(r.read().decode())
        if not j.get('success'):
            return {'ip': ip, 'error': j.get('message', 'geo falló'), 'lat': None, 'lon': None}
        conn = j.get('connection') or {}
        v = {
            'ip': ip,
            'country': j.get('country', '—'),
            'city': j.get('city', '—'),
            'lat': j.get('latitude'),
            'lon': j.get('longitude'),
            'isp': conn.get('isp') or conn.get('org') or '—',
            'as': conn.get('asn', '—'),
            'proxy': bool(conn.get('type') and re.search(r'proxy|vpn', conn.get('type', ''), re.I)),
            'hosting': bool(
                (conn.get('type') and re.search(r'hosting|cloud|datacenter', conn.get('type', ''), re.I)) or
                (conn.get('isp') and HOSTING_ISP.search(conn.get('isp', '')))
            ),
            'mobile': bool(conn.get('type') and re.search(r'mobile|cellular', conn.get('type', ''), re.I)),
        }
        with _cache_lock:
            _cache['geo:' + ip] = {'t': time.time(), 'v': v}
        return v
    except Exception as e:
        return {'ip': ip, 'error': str(e), 'lat': None, 'lon': None}

# ── rDNS ─────────────────────────────────────────────────────────────────────
def rdns(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None

# ── Blocklist (abuse.ch feodotracker) ────────────────────────────────────────
_bl: dict = {'set': set(), 'ok': False, 'at': 0}
_bl_lock = threading.Lock()

def _load_blocklist() -> dict:
    with _bl_lock:
        if _bl['ok'] and time.time() - _bl['at'] < 6 * 3600:
            return _bl
    try:
        url = 'https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt'
        req = urllib.request.Request(url, headers={'User-Agent': 'SourceSeal-RedTeam/2.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            text = r.read().decode()
        ips = {l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')}
        with _bl_lock:
            _bl.update({'set': ips, 'ok': bool(ips), 'at': time.time()})
    except Exception:
        pass
    return _bl

# ── Intel ────────────────────────────────────────────────────────────────────
def assess(ip: str) -> dict:
    ip = ip.strip()
    if not ip:
        return {'error': 'ip requerida'}
    g = lookup(ip)
    if g.get('private'):
        return {'ip': ip, 'private': True, 'score': 0, 'label': 'LAN', 'rdns': None,
                'breakdown': [{'f': 'red privada', 'w': 0}], 'flags': g,
                'blocklist': False, 'note': 'IP interna — confianza N/A'}
    rev = rdns(ip)
    bl = _load_blocklist()
    breakdown = []
    score = 0
    if g.get('hosting'):
        score += 25; breakdown.append({'f': 'hosting / cloud', 'w': 25})
    if g.get('proxy'):
        score += 30; breakdown.append({'f': 'proxy / vpn', 'w': 30})
    if g.get('mobile'):
        score -= 10; breakdown.append({'f': 'móvil / CGN (residencial)', 'w': -10})
    if rev and re.search(r'tor|exit|relay', rev, re.I):
        score += 40; breakdown.append({'f': 'posible nodo tor', 'w': 40})
    if bl['ok'] and ip in bl['set']:
        score += 45; breakdown.append({'f': 'en blocklist (abuse.ch)', 'w': 45})
    if rev and BULLETPROOF.search(rev):
        score += 20; breakdown.append({'f': 'ASN bulletproof (rDNS)', 'w': 20})
    isp_str = str(g.get('isp', ''))
    if BULLETPROOF.search(isp_str):
        score += 20; breakdown.append({'f': 'ASN bulletproof (ISP)', 'w': 20})
    score = max(0, min(100, score))
    label = 'ALTA (limpia)' if score <= 20 else 'MEDIA' if score <= 50 else 'BAJA' if score <= 80 else 'CRÍTICA'
    return {
        'ip': ip, 'score': score, 'label': label, 'rdns': rev,
        'breakdown': breakdown, 'flags': g, 'blocklist': bl['ok'],
        'note': 'score completo' if bl['ok'] else 'score PARCIAL: blocklist no disponible'
    }
