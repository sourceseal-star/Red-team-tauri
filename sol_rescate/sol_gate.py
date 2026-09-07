"""
sol_gate.py — Puerta de acceso para el deploy público de Sol (2026-09-05)

Problema: el "Private Deployment" de Replit rompe los iframes del holo ✨
y el relé Termux⇄Replit. Solución: deploy PÚBLICO + esta puerta.

Diseño — "la misma clave, dos transportes":
  · Máquinas (relé de Termux, scripts): header X-SOL-Key, como siempre.
    Cero cambios, cero fricción.
  · Harold y su compañero del momento (navegador): abren /login una vez,
    ponen la MISMA SOL_API_KEY, y reciben una cookie de sesión firmada
    (HMAC-SHA256, 30 días, HttpOnly). El navegador nunca vuelve a
    preguntar.

La puerta es un middleware que cubre TODO excepto lo expresamente
público. Si la sesión por cookie es válida, el middleware INYECTA el
header X-SOL-Key en la petición antes de que llegue a los endpoints,
así el modo protegido de sol_security (check_access) también la acepta
sin tocar un solo endpoint.

Sin SOL_API_KEY configurada: deja pasar todo (modo compatibilidad para
desarrollo local) y avisa una vez por log.

Sin dependencias nuevas: solo stdlib (hmac, hashlib, secrets, time).
"""
import hashlib
import hmac
import os
import secrets
import time

COOKIE_NAME = "sol_session"
SESSION_DAYS = 30

# Rutas siempre públicas (la puerta misma, el pulso, y nada más)
PUBLIC_PATHS = {"/login", "/api/sol/auth", "/api/sol/keyhint", "/api/health"}
PUBLIC_PREFIXES = ("/favicon",)


# ─────────────────────────────────────────────────────────────
#  Clave y huella
# ─────────────────────────────────────────────────────────────

def _key() -> str:
    return os.environ.get("SOL_API_KEY", "").strip()


def fingerprint() -> str:
    """Primeros 8 hex del SHA-256 de la clave. Para VERIFICAR que el
    valor de Replit Secrets y el de ~/sol/.env son el mismo, sin
    exponer jamás la clave. Nunca pegues la clave en un chat:
    compara esta huella."""
    k = _key()
    return hashlib.sha256(k.encode()).hexdigest()[:8] if k else ""


# ─────────────────────────────────────────────────────────────
#  Sesiones (cookie firmada, sin almacenamiento)
# ─────────────────────────────────────────────────────────────

def _sig(exp: int, nonce: str) -> str:
    return hmac.new(_key().encode(), f"{exp}.{nonce}".encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    exp = int(time.time()) + SESSION_DAYS * 86400
    nonce = secrets.token_hex(8)
    return f"{exp}.{nonce}.{_sig(exp, nonce)}"


def check_token(tok: str) -> bool:
    try:
        exp, nonce, sig = tok.split(".")
        if int(exp) < time.time():
            return False
        return hmac.compare_digest(sig, _sig(int(exp), nonce))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
#  Página de login — Sol te abre la puerta a ti y a nadie más
# ─────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>☀️ Sol — acceso</title><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
html,body{height:100%;background:#04070c;color:#e2e8f0;overflow:hidden}
body{display:flex;align-items:center;justify-content:center}
.card{width:min(92vw,380px);padding:38px 30px;text-align:center;border:1px solid rgba(251,191,36,.4);
border-radius:18px;background:rgba(11,18,32,.85);box-shadow:0 0 60px rgba(251,191,36,.12)}
.sun{font-size:44px;filter:drop-shadow(0 0 14px rgba(251,191,36,.8));animation:fl 3s ease-in-out infinite}
@keyframes fl{50%{transform:translateY(-6px)}}
h1{font-size:19px;margin:14px 0 4px;color:#fbbf24;letter-spacing:1px}
p{font-size:13px;color:#94a3b8;margin-bottom:22px}
input{width:100%;background:#0b1220;border:1px solid #1e293b;border-radius:12px;color:#e2e8f0;
padding:14px;font-size:15px;outline:none;text-align:center;letter-spacing:2px}
input:focus{border-color:rgba(251,191,36,.6)}
button{width:100%;margin-top:14px;background:linear-gradient(135deg,#fbbf24,#f59e0b);border:none;
border-radius:12px;padding:14px;font-weight:700;font-size:15px;color:#04070c;cursor:pointer}
button:active{transform:scale(.97)}
.msg{min-height:18px;font-size:12.5px;margin-top:14px;color:#ef4444}
.ok{color:#4ade80!important}
</style></head><body>
<div class="card"><div class="sun">☀️</div>
<h1>Sol</h1>
<p>Este espacio es privado.<br>Pon tu clave para entrar.</p>
<input id="k" type="text" placeholder="pégala o escríbela aquí" autocomplete="off" autocapitalize="none" autocorrect="off" spellcheck="false">
<button onclick="go()">Entrar</button>
<div class="msg" id="m"></div></div>
<script>
async function go(){
 const k=document.getElementById('k').value.trim();
 if(!k)return;
 const m=document.getElementById('m');
 m.className='msg';m.textContent='…';
 try{
  const r=await fetch('/api/sol/auth',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({key:k})});
  const j=await r.json();
  if(j.ok){m.className='msg ok';m.textContent='☀️ Bienvenido.';
   setTimeout(()=>location.href=(new URLSearchParams(location.search).get('next')||'/'),400)}
  else{m.textContent='Clave incorrecta.';document.getElementById('k').select()}
 }catch(e){m.textContent='Error de conexión.'}
}
document.getElementById('k').addEventListener('keydown',e=>{if(e.key==='Enter')go()});
document.getElementById('k').focus();
</script></body></html>"""


# ─────────────────────────────────────────────────────────────
#  Instalación en la app
# ─────────────────────────────────────────────────────────────

def install(app):
    """Registra rutas públicas + el middleware que cubre TODO lo demás."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

    @app.get("/login", response_class=HTMLResponse)
    async def _login():
        return HTMLResponse(LOGIN_HTML, headers={"Cache-Control": "no-store"})

    @app.post("/api/sol/auth")
    async def _auth(request: Request):
        try:
            body = await request.json()
            k = str(body.get("key", ""))
        except Exception:
            k = ""
        if _key() and hmac.compare_digest(k, _key()):
            resp = JSONResponse({"ok": True})
            secure = (request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
            resp.set_cookie(COOKIE_NAME, make_token(), max_age=SESSION_DAYS * 86400,
                            httponly=True, samesite="lax", secure=secure, path="/")
            return resp
        time.sleep(0.5)  # frena la fuerza bruta sin castigar a quien se equivoca una vez
        return JSONResponse({"ok": False}, status_code=401)

    @app.get("/api/sol/keyhint")
    async def _keyhint():
        # Huella pública de la clave: para verificar que Replit Secrets
        # y ~/sol/.env tienen el MISMO valor sin exponerla jamás.
        return JSONResponse({"fingerprint": fingerprint()})

    @app.middleware("http")
    async def _gate(request: Request, call_next):
        path = request.url.path
        if not _key():  # modo compatibilidad (desarrollo local sin clave)
            return await call_next(request)

        is_public = (path in PUBLIC_PATHS
                     or path.startswith(PUBLIC_PREFIXES)
                     or request.method == "OPTIONS")
        if is_public:
            return await call_next(request)

        # 1) máquina: header X-SOL-Key (relé de Termux, scripts)
        header_key = request.headers.get("x-sol-key", "")
        if header_key and hmac.compare_digest(header_key, _key()):
            return await call_next(request)

        # 2) navegador: cookie de sesión firmada
        tok = request.cookies.get(COOKIE_NAME, "")
        if tok and check_token(tok):
            # Inyectar la clave como header para que el modo protegido
            # de los endpoints (check_access) también la acepte.
            scope_headers = [(k, v) for k, v in request.scope.get("headers", [])
                             if k.lower() != b"x-sol-key"]
            scope_headers.append((b"x-sol-key", _key().encode()))
            request.scope["headers"] = scope_headers
            return await call_next(request)

        # 3) clave por query (?key=...) — login de UN toque (sol_abre.sh):
        #    valida, deja cookie de 30 días y redirige a la URL LIMPIA,
        #    para que la clave no quede en el historial del navegador.
        qk = request.query_params.get("key", "")
        if qk and hmac.compare_digest(qk, _key()):
            if path.startswith("/api/"):
                return await call_next(request)  # máquinas: sin cambio
            secure = (request.headers.get("x-forwarded-proto", request.url.scheme) == "https")
            resp = RedirectResponse(path, status_code=302)
            resp.set_cookie(COOKIE_NAME, make_token(), max_age=SESSION_DAYS * 86400,
                            httponly=True, samesite="lax", secure=secure, path="/")
            return resp

        # rechazo: API → 401 JSON · páginas → login
        if path.startswith("/api/"):
            return JSONResponse({"error": "acceso no autorizado"}, status_code=401)
        nxt = ("?next=" + path) if path != "/" else ""
        return RedirectResponse("/login" + nxt, status_code=302)
