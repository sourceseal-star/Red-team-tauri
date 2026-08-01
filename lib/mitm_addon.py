# Addon de mitmproxy: clasifica el tráfico interceptado y lo saca a evidence/intercept.jsonl
# Carga: mitmdump -s lib/mitm_addon.py -q -w evidence/traffic.flow
# Scope DEFENSIVO: solo ve lo que TÚ enrutas por el proxy (tu dispositivo / tu LAN).
import os, re, json, time, base64, threading, hashlib
from mitmproxy import http

OUT = os.environ.get("SEALCTL_INTERCEPT", "evidence/intercept.jsonl")
LOG_CREDS = os.environ.get("SEALCTL_LOG_CREDS", "0") == "1"  # OFF por defecto: no escribir contraseñas
_lock = threading.Lock()

CAM_RE   = re.compile(r'/(ISAPI|cgi-bin/magicBox|axis-cgi|onvif|snapshot\.cgi|doc/page|videostream|tmpfs/autojpg)', re.I)
CAM_VEND = [('isapi','Hikvision'),('magicbox','Dahua'),('axis-cgi','Axis'),('onvif','ONVIF'),('videostream','cam-IP'),('uniview','Uniview')]
RADIO_RE = re.compile(r'/(stream|live|radio|\.mp3|\.aac|\.opus|status\.xsl|stats\.xml)', re.I)
TOKEN_Q  = re.compile(r'(token|key|auth|pass|pwd|secret|api[_-]?key)=([^&\s]+)', re.I)

def _emit(rec):
    rec["ts"] = time.time()
    rec["id"] = hashlib.sha1(f"{rec['ts']}{rec.get('host')}{rec.get('path')}".encode()).hexdigest()[:12]
    with _lock, open(OUT, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def _vendor(path):
    for k, v in CAM_VEND:
        if k in path.lower(): return v
    return None

def request(flow: http.HTTPFlow):
    h = flow.request
    host, path, method = h.pretty_host, h.path, h.method
    rec = {"dir": "req", "host": host, "port": h.port, "method": method, "path": path.split('?')[0],
           "scheme": h.scheme, "tls": h.scheme == "https"}

    # 1) credencial en claro (Basic / Digest / token en query)
    auth = h.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            raw = base64.b64decode(auth.split()[1]).decode("latin-1")
            user = raw.split(":", 1)[0]
        except Exception:
            user, raw = "?", ""
        rec["kind"] = "CRED_CLEARTEXT"; rec["user"] = user; rec["cleartext"] = (h.scheme != "https")
        if LOG_CREDS: rec["raw"] = raw  # solo si TÚ lo activas a propósito
        _emit(rec); return
    q = TOKEN_Q.search(h.query or "")
    if q:
        rec["kind"] = "TOKEN_IN_QUERY"; rec["param"] = q.group(1); rec["cleartext"] = (h.scheme != "https")
        _emit(rec); return

    # 2) huella de cámara / radio (aunque vaya cifrada, registramos el path: es TU dispositivo)
    v = _vendor(path)
    if v or CAM_RE.search(path):
        rec["kind"] = "CAMERA"; rec["vendor"] = v or "cam-IP"; _emit(rec); return
    if RADIO_RE.search(path) or h.headers.get("icy-metadata"):
        rec["kind"] = "RADIO"; _emit(rec); return

def response(flow: http.HTTPFlow):
    h, r = flow.request, flow.response
    if not r: return
    host, path = h.pretty_host, h.path
    # credenciales que el SERVIDOR pide sin TLS (401 + WWW-Authenticate sobre http)
    if r.status_code == 401 and h.scheme != "https" and r.headers.get("www-authenticate"):
        _emit({"dir": "resp", "kind": "AUTH_OVER_HTTP", "host": host, "path": path.split('?')[0],
               "scheme": h.scheme, "tls": False, "challenge": r.headers.get("www-authenticate","")[:60],
               "note": "el dispositivo pide credenciales por HTTP en claro"})
    # banner de cámara en el body (deviceInfo XML/JSON)
    if CAM_RE.search(path) and r.raw_content:
        body = r.raw_content[:600].decode("latin-1", "ignore")
        v = _vendor(path) or _vendor(body)
        if v or "<deviceinfo" in body.lower() or '"serialnumber"' in body.lower():
            _emit({"dir": "resp", "kind": "CAMERA_BANNER", "host": host, "path": path.split('?')[0],
                   "vendor": v, "tls": h.scheme == "https", "snippet": body[:200]})
