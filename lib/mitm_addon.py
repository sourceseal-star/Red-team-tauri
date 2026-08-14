# Addon de mitmproxy con CERCO defensivo.
# Carga: mitmdump -s lib/mitm_addon.py -q -w evidence/traffic.flow
# SCOPE: solo registra credenciales/banners cuando el destino está en tus rangos.
# Fuera de scope => evento OUT_OF_SCOPE sin user, sin path sensible, sin snippet.
# Eso convierte "DEFENSIVE USE ONLY" en código, no en cartel.
import os, re, json, time, base64, threading, hashlib, ipaddress
from mitmproxy import http

OUT          = os.environ.get("SEALCTL_INTERCEPT", "evidence/intercept.jsonl")
LOG_CREDS    = os.environ.get("SEALCTL_LOG_CREDS", "0") == "1"   # OFF: nunca escribir contraseñas
MY_NETS_RAW  = os.environ.get("SEALCTL_MY_NETS", "")             # ej "192.168.1.0/24,10.0.0.0/8"
_lock = threading.Lock()

def _parse_nets(s):
    nets = []
    for chunk in [c.strip() for c in s.split(",") if c.strip()]:
        try: nets.append(ipaddress.ip_network(chunk, strict=False))
        except ValueError: pass
    return nets
MY_NETS = _parse_nets(MY_NETS_RAW)

def _dst_ip(flow):
    try:
        a = flow.server_conn and flow.server_conn.address
        return a[0] if a else None
    except Exception:
        return None

def in_scope(flow):
    """Dentro de cerco: RFC1918/loopback/link-local O en SEALCTL_MY_NETS."""
    ip = _dst_ip(flow)
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return True
    return any(addr in n for n in MY_NETS)

CAM_RE   = re.compile(r'/(ISAPI|cgi-bin/magicBox|axis-cgi|onvif|snapshot\.cgi|doc/page|videostream|tmpfs/autojpg)', re.I)
CAM_VEND = [('isapi','Hikvision'),('magicbox','Dahua'),('axis-cgi','Axis'),('onvif','ONVIF'),('videostream','cam-IP'),('uniview','Uniview')]
RADIO_RE = re.compile(r'/(stream|live|radio|\.mp3|\.aac|\.opus|status\.xsl|stats\.xml)', re.I)
TOKEN_Q  = re.compile(r'(token|key|auth|pass|pwd|secret|api[_-]?key)=([^&\s]+)', re.I)

def _emit(rec):
    rec["ts"] = time.time()
    rec["id"] = hashlib.sha1(f"{rec['ts']}{rec.get('host')}{rec.get('kind')}".encode()).hexdigest()[:12]
    with _lock, open(OUT, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _vendor(path):
    for k, v in CAM_VEND:
        if k in (path or "").lower(): return v
    return None

def request(flow: http.HTTPFlow):
    h = flow.request
    host, path, method, scheme = h.pretty_host, h.path, h.method, h.scheme
    scoped = in_scope(flow)
    base = {"dir": "req", "host": host, "port": h.port, "method": method,
            "scheme": scheme, "tls": scheme == "https", "in_scope": scoped}

    # ---- CREDENCIALES: solo se registran DENTRO de cerco ----
    auth = h.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        if not scoped:
            _emit({**base, "kind": "OUT_OF_SCOPE", "note": "credencial básica hacia destino fuera de cerco: NO registrada"}); return
        try:
            raw = base64.b64decode(auth.split()[1]).decode("latin-1"); user = raw.split(":", 1)[0]
        except Exception:
            user, raw = "?", ""
        rec = {**base, "kind": "CRED_CLEARTEXT", "user": user, "cleartext": scheme != "https", "path": path.split('?')[0]}
        if LOG_CREDS: rec["raw"] = raw
        _emit(rec); return
    q = TOKEN_Q.search(h.query or "")
    if q:
        if not scoped:
            _emit({**base, "kind": "OUT_OF_SCOPE", "note": "token en query hacia destino fuera de cerco: NO registrado"}); return
        _emit({**base, "kind": "TOKEN_IN_QUERY", "param": q.group(1), "cleartext": scheme != "https", "path": path.split('?')[0]}); return

    # ---- HUELLA cámara/radio: dentro de cerco registra vendor+path; fuera, solo host ----
    v = _vendor(path)
    if v or CAM_RE.search(path):
        if scoped: _emit({**base, "kind": "CAMERA", "vendor": v or "cam-IP", "path": path.split('?')[0]})
        else:      _emit({**base, "kind": "OUT_OF_SCOPE", "note": "huella de cámara en destino público: no es tuya, no registrada"})
        return
    if RADIO_RE.search(path) or h.headers.get("icy-metadata"):
        if scoped: _emit({**base, "kind": "RADIO", "path": path.split('?')[0]})
        else:      _emit({**base, "kind": "OUT_OF_SCOPE", "note": "huella de radio en destino público: no registrada"})
        return

def response(flow: http.HTTPFlow):
    h, r = flow.request, flow.response
    if not r: return
    scoped = in_scope(flow)
    if not scoped: return   # fuera de cerco no inspeccionamos respuestas
    host, path, scheme = h.pretty_host, h.path, h.scheme
    if r.status_code == 401 and scheme != "https" and r.headers.get("www-authenticate"):
        _emit({"dir": "resp", "kind": "AUTH_OVER_HTTP", "host": host, "path": path.split('?')[0],
               "scheme": scheme, "tls": False, "in_scope": True,
               "challenge": r.headers.get("www-authenticate", "")[:60],
               "note": "el dispositivo pide credenciales por HTTP en claro"})
    if CAM_RE.search(path) and r.raw_content:
        body = r.raw_content[:600].decode("latin-1", "ignore")
        v = _vendor(path) or _vendor(body)
        if v or "<deviceinfo" in body.lower() or '"serialnumber"' in body.lower():
            _emit({"dir": "resp", "kind": "CAMERA_BANNER", "host": host, "path": path.split('?')[0],
                   "vendor": v, "tls": scheme == "https", "in_scope": True, "snippet": body[:200]})
