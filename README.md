# 🛡️ Red-Team-Tauri — SourceSeal Console v6.0

Sistema de operaciones de red team con **ARTO** (AI autónomo) + **SEAL SUPER PACK** (inteligencia de red y cámaras) + **KRAKEN v3.0** (motor de explotación) + **VPN interceptor** + **OSINT advanced** + **Honeypot**.

Backend Python/FastAPI · Frontend React/Vite/TypeScript · Sin mocks · Sin dummy data.

---
## 🦑 LEVIATHAN v3.0 — Sistema de Módulos

Sistema modular de red team con 22 módulos: scanners, exploiters, AI analyzers y reporters.

- **Backend:** `leviathan_core/` — módulos Python + FastAPI router (`/api/leviathan/*`)
- **Frontend:** `leviathan-frontend/` — React 18 + Redux + Vite + Chart.js + Leaflet
- **Aislamiento:** No modifica ni importa kraken/, seal/, o redteam/
- **Persistencia:** Tablas `leviathan_*` en redteam.db (no interfiere con existentes)

### Activar router en dashboard_server.py
```python
from leviathan_core.api.leviathan_router import router as leviathan_router
app.include_router(leviathan_router)
```

### Documentación
- `leviathan_core/README.md` — Arquitectura, endpoints, instalación
- `leviathan_core/docs/MANUAL_OPERATIVO.md` — Flujo operativo, dependencias, Termux

### Frontend
```bash
cd leviathan-frontend && npm install && npm run dev
# Docker: docker build -t leviathan-frontend . && docker run -p 80:80 leviathan-frontend
```

---



## 🚀 ARRANQUE RÁPIDO — UN SOLO COMANDO

### Replit

```bash
bash replit_start.sh
```

### Termux (Android)

```bash
bash arrancar.sh
```

Este comando inicia el dashboard unificado y PHANTOM en el dispositivo. Para
incluir Commander desde su repositorio hermano:

```bash
bash termux_recover.sh
```

Commander se expone en `http://localhost:8001/api/commander/*`; no se inicia un
segundo servidor en el puerto 8003. Si el repositorio privado no está disponible,
el dashboard principal sigue funcionando y muestra Commander como no disponible.

COM-LINK queda disponible dentro de Commander:

```bash
curl -H "Authorization: Bearer TU_TOKEN" \
  http://localhost:8001/api/commander/comlink/status
```

El endpoint de envío es `POST /api/commander/comlink/send` y requiere `channel`
y `message` en JSON. No se ejecuta ningún canal externo durante el arranque;
SMS, Telegram, radio, satélite y mesh solo se activan mediante una llamada
explícita y con su configuración correspondiente.

### Manual (cualquier Linux/Mac)

```bash
# 1. Clonar
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri

# 2. Instalar deps Python
pip install -r backend/requirements.txt

# 3. Compilar frontend
cd tauri-frontend
npm install --legacy-peer-deps
npm run build
cd ..

# 4. Levantar backend (sirve API + frontend estático)
cd redteam/scripts
export PORT=8001 HOST=0.0.0.0
python3 dashboard_server.py
```

→ Abrir `http://localhost:8001` en el navegador.

---

## ⚡ ARRANQUE + TEST AUTOMÁTICO

```bash
bash quickstart.sh
```

Este script hace todo: instala deps, compila frontend, levanta backend, y ejecuta **smoke tests** contra todos los módulos para verificar que todo responde correctamente.

---

## 📋 REQUISITOS

| Componente | Versión | Nota |
|---|---|---|
| Python | 3.10+ | Backend FastAPI |
| Node.js | 18+ LTS | Compilar frontend |
| Git | cualquiera | Clonar/actualizar |

### Opcionales (activan funciones extra)

| Herramienta | Instalación | Activa |
|---|---|---|
| `nmap` | `pkg install nmap` / `apt install nmap` | Escaneo de puertos y topología |
| `whois` | `pkg install whois` / `apt install whois` | OSINT WHOIS |
| `dig` | `pkg install bind-utils` / `apt install dnsutils` | DNS recon |
| `tcpdump` | `pkg install tcpdump` / `apt install tcpdump` | Captura de paquetes |
| `iproute2` | `pkg install iproute2` / `apt install iproute2` | ARP discovery (SEAL tactical engine) |
| `ffmpeg` | `pkg install ffmpeg` / `apt install ffmpeg` | Transcodificación RTSP→HLS (cámaras) |
| `termux-api` | `pkg install termux-api` | Wake-lock + WiFi scan (Termux) |

### API Keys OSINT (gratis, opcionales)

```bash
# .env en la raíz del repo
ABUSEIPDB_KEY=tu-key    # https://www.abuseipdb.com/account/api (1000 checks/día gratis)
SHODAN_API_KEY=tu-key   # https://www.shodan.io/dashboard (cuenta gratis)
HUNTER_API_KEY=tu-key   # https://hunter.io/api-keys (opcional, emails OSINT)
```

---

## 🏗️ ARQUITECTURA

```
Red-team-tauri/
├── redteam/scripts/
│   └── dashboard_server.py          # Backend ÚNICO — FastAPI :8001
│                                     #    Sirve API + dist/ estático
│                                     #    80+ endpoints unificados
│
├── tauri-frontend/                   # Frontend ÚNICO — React/Vite/TS
│   ├── src/
│   │   ├── components/               #    30+ componentes (incluye SealPanel)
│   │   ├── api/                      #    Clients: artoApi, interceptorApi, osintApi
│   │   ├── lib/                      #    auth, fetch interceptor, sourceseal utils
│   │   └── App.tsx                   #    Router principal
│   ├── vite.config.ts                #    proxy /api → :8001, /ws → :8001
│   └── dist/                         #    Build output (servido por backend)
│
├── arto/                             # Sistema ARTO (AI autónomo)
│   ├── api/arto_router.py             #    23 endpoints FastAPI
│   ├── core/                         #    5 motores AI
│   ├── modules/                      #    attack_simulator, vpn_interceptor, defense
│   ├── memory/                       #    SQLite + knowledge_base
│   └── utils/                        #    threat_intel, risk, anomaly
│
├── seal/                             # 🔱 SEAL SUPER PACK v2.1 (independiente)
│   ├── scanners/                    #    network_sweep, onvif, fingerprint_engine
│   ├── attackers/                    #    hikvision_killer (CVE-2021-36260)
│   ├── utils/                       #    vendor_dicts (600+ credenciales)
│   ├── orchestrator/                 #    monitoreo 24/7
│   ├── ai/                           #    arto_integration bridge
│   ├── core/                         #    tactical_engine (reportes cifrados)
│   ├── api/                          #    seal_api_router (20+ endpoints)
│   └── docs/README.md                #    Guía completa de SEAL
│
├── kraken/                           # 🐙 KRAKEN v3.0 (independiente)
│   ├── src/kraken/                   #    core, plugins, services, api, cli
│   ├── termux_install.sh             #    Instalación ligera para Termux
│   └── docs/README.md                #    Documentación de KRAKEN
│
├── redteam/
│   ├── tlsproxy/
│   │   ├── interceptor_advanced.py   # Interceptor MITM (12 endpoints)
│   │   └── interceptor_bridge.py      #    Bridge v2 (control + analyze)
│   ├── osint/
│   │   └── osint_advanced.py          # OSINT (Shodan, AbuseIPDB, WHOIS, emails)
│   └── data/                         #    ops_config.json, iocs.json, etc.
│
├── backend/modules/
│   └── enhanced_recon.py             # Reconocimiento de red optimizado
│
├── gateway/                          # Federación mesh (orchestrator + satellite)
├── honeypot/                         # Honeypot + canary tokens
├── src-tauri/                        # Tauri desktop (Rust) — wrapper nativo
├── android/                          # VpnService Java (captura sin root)
├── replit_start.sh                   # Arranque Replit
├── arrancar.sh                       # Arranque Termux (dashboard + PHANTOM)
├── termux_recover.sh                  # Termux + sincronización de Commander
├── quickstart.sh                     # Arranque + test automático
└── replit.nix                        # Dependencias Nix (Replit)
```

### Principio de aislamiento

- **`dashboard_server.py` es y sigue siendo el único backend que arranca por defecto** (Replit + Termux).
- **KRAKEN** y **SEAL** son módulos **independientes**: no se importan automáticamente en el dashboard. Cero imports cruzados. Actualizarlos nunca rompe el dashboard.
- Para activar los endpoints de SEAL dentro del dashboard (opcional), ver [`seal/docs/README.md`](seal/docs/README.md).
- Para instalar KRAKEN en Termux: `cd kraken && bash termux_install.sh`.

### Flujo de datos

```
Navegador (React SPA)
    ↓ HTTP/WS
dashboard_server.py (FastAPI :8001)
    ├── /api/arto/*        → arto/api/arto_router.py
    ├── /api/interceptor/* → redteam/tlsproxy/interceptor_advanced.py
    ├── /api/interceptor/v2/* → redteam/tlsproxy/interceptor_bridge.py
    ├── /api/osint/*       → redteam/osint/osint_advanced.py
    ├── /api/scan/*        → backend/modules/enhanced_recon.py
    ├── /api/network/*     → escaneo local (nmap, arp, ss)
    ├── /api/seal/*        → seal/api/seal_api_router.py (opcional, manual)
    ├── /ws                → WebSocket hub (tiempo real)
    └── /*                 → dist/index.html (SPA fallback)
```

---

## 🔱 SEAL SUPER PACK v2.1 — Inteligencia de Red y Cámaras

Sistema de descubrimiento, fingerprinting y explotación de cámaras IP y dispositivos de red.

**Uso directo (CLI, sin dashboard):**

```bash
# Escaneo de red (ARP + Ping + vendor fingerprint)
python3 seal/scanners/network_sweep_ultimate.py --network 192.168.0.0/24

# Detección ONVIF
python3 seal/scanners/onvif_scanner.py --network 192.168.0.0/24

# Ataque a cámara Hikvision (CVE-2021-36260 + brute force)
python3 seal/attackers/hikvision_killer.py 192.168.0.7 --brute

# Motor táctico — auditoría rápida con reporte cifrado
python3 -m seal.core.tactical_engine --network 192.168.0.0/24

# Orquestador continuo (monitoreo 24/7)
python3 seal/orchestrator/seal_orchestrator.py --start
```

**Activar en el dashboard (opcional):**

```python
# En dashboard_server.py, después de crear app = FastAPI(...):
from seal.api.seal_api_router import include_seal_routes
include_seal_routes(app)              # /api/devices, /api/scan, /api/alerts, etc.

from seal.core.tactical_engine import include_tactical_routes
include_tactical_routes(app)          # /api/seal/tactical/scan, /results, /health
```

📖 Documentación completa: [`seal/docs/README.md`](seal/docs/README.md)

---

## 🐙 KRAKEN v3.0 — Motor de Explotación Autónomo

Framework modular de explotación con plugins SSH, SMB, EternalBlue, inteligencia de amenazas y reportes.

**Instalación (Termux, modo ligero):**

```bash
cd kraken
bash termux_install.sh
python3 -m kraken.cli.commands --help
```

📖 Documentación completa: [`kraken/docs/README.md`](kraken/docs/README.md)

---

## 🔑 AUTENTICACIÓN

El backend usa API Key via header `Authorization: Bearer <key>`.

- La key se genera automáticamente en `.env` al primer arranque (`REDTEAM_API_KEY`)
- El frontend la guarda en `localStorage` tras login
- Paths públicos (sin auth): `/api/health`, `/health`, `/healthz`, `/canary/callback`, `/api/auth/*`

**Login desde el frontend:**
```
POST /api/auth/login
Body: { "password": "tu-password" }
→ Devuelve: { "token": "xxx", "expires": 3600 }
```

**Verificar token manualmente:**
```bash
curl -H "Authorization: Bearer TU_TOKEN" http://localhost:8001/api/health
```

---

## 📡 ENDPOINTS PRINCIPALES

### Salud
| Método | Path | Descripción |
|---|---|---|
| GET | `/api/health` | Health check del backend |

### ARTO — AI Autónomo (23 endpoints)
| Método | Path | Descripción |
|---|---|---|
| GET | `/api/arto/status` | Estado del motor ARTO |
| POST | `/api/arto/start` | Iniciar ARTO |
| POST | `/api/arto/stop` | Detener ARTO |
| POST | `/api/arto/operation/{type}` | Ejecutar operación (scan, sniff, attack) |
| GET | `/api/arto/operations` | Listar operaciones |
| GET | `/api/arto/predictions` | Predicciones de amenazas |
| POST | `/api/arto/defend` | Activar defensa autónoma |
| POST | `/api/arto/simulate` | Simular ataque |
| POST | `/api/arto/analyze/behavior` | Analizar comportamiento |
| POST | `/api/arto/traffic/start` | Iniciar captura de tráfico |
| GET | `/api/arto/traffic/stats` | Stats de tráfico |

### Interceptor MITM (12 + 5 bridge v2)
| Método | Path | Descripción |
|---|---|---|
| POST | `/api/interceptor/analyze/request` | Analizar request HTTP |
| POST | `/api/interceptor/analyze/response` | Analizar response HTTP |
| GET | `/api/interceptor/flows` | Flujos capturados |
| GET | `/api/interceptor/alerts` | Alertas de seguridad |
| GET | `/api/interceptor/stats` | Estadísticas |
| POST | `/api/interceptor/decode` | Decodificar payload |
| GET | `/api/interceptor/cert/{host}` | Analizar certificado TLS |
| POST | `/api/interceptor/analyze/user-agent` | Analizar User-Agent |
| POST | `/api/interceptor/capture/start` | Iniciar captura MITM |
| POST | `/api/interceptor/v2/control` | Control del proxy v2 |
| POST | `/api/interceptor/v2/analyze/{id}` | Análisis profundo de flujo |

### OSINT
| Método | Path | Descripción |
|---|---|---|
| GET | `/api/osint/shodan?ip=X` | Lookup Shodan |
| GET | `/api/osint/whois/{domain}` | WHOIS de dominio |
| GET | `/api/osint/subdomains/{domain}` | Subdominios |
| GET | `/api/osint/emails/{domain}` | Emails públicos |
| GET | `/api/investigate/ip/{ip}` | Investigación completa de IP |
| GET | `/api/investigate/camera/{ip}` | Investigación de cámara |
| GET | `/api/geo?ip=X` | Geo-localización |

### Red y Escaneo
| Método | Path | Descripción |
|---|---|---|
| GET | `/api/network/info` | Info de red local |
| POST | `/api/scan/topology` | Topología de red |
| POST | `/api/scan/cameras` | Escanear cámaras IP |
| POST | `/api/scan/routers` | Escanear routers |
| POST | `/api/scan/iot` | Escanear IoT |
| GET | `/api/services` | Lista de servicios |
| GET | `/api/resources` | Recursos del sistema |
| GET | `/api/ops/config` | Config de operaciones |

### SEAL (opcional, requiere activación manual)
| Método | Path | Descripción |
|---|---|---|
| GET | `/api/devices` | Lista todos los dispositivos descubiertos |
| POST | `/api/scan` | Ejecuta un escaneo de red |
| GET | `/api/alerts` | Lista alertas del orquestador |
| GET | `/api/status` | Estado del orquestador SEAL |
| POST | `/api/hikvision/attack/{ip}` | Atacar cámara Hikvision |
| POST | `/api/seal/tactical/scan?network=CIDR` | Auditoría táctica con reporte cifrado |
| GET | `/api/seal/tactical/results` | Resultados de auditorías tácticas |

### WebSocket
| Path | Descripción |
|---|---|
| `/ws` | Hub WebSocket tiempo real |

---

## 🧪 TESTEO — SMOKE TESTS

### Smoke test automático

```bash
bash quickstart.sh --test-only
```

### Tests manuales con curl

```bash
BASE="http://localhost:8001"
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" -H "Content-Type: application/json" -d '{"password":"tu-password"}' | jq -r .token)
AUTH="Authorization: Bearer $TOKEN"

# Health
curl -s "$BASE/api/health" | jq .

# ARTO
curl -s -H "$AUTH" "$BASE/api/arto/status" | jq .

# Interceptor
curl -s -H "$AUTH" "$BASE/api/interceptor/stats" | jq .

# User-Agent analysis
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  "$BASE/api/interceptor/analyze/user-agent" \
  -d '{"user_agent":"sqlmap/1.6.5"}' | jq .

# OSINT WHOIS
curl -s -H "$AUTH" "$BASE/api/osint/whois/example.com" | jq .

# Geo IP
curl -s -H "$AUTH" "$BASE/api/geo?ip=8.8.8.8" | jq .

# SEAL Tactical (si está activado)
curl -s -H "$AUTH" "$BASE/api/seal/tactical/health" | jq .

# Services
curl -s -H "$AUTH" "$BASE/api/services" | jq .
```

---

## 🔧 SOLUCIÓN DE PROBLEMAS

### Puerto 8001 ocupado
```bash
pkill -9 -f "dashboard_server.py"
# o
lsof -ti:8001 | xargs kill -9    # Linux/Mac
fuser -k 8001/tcp                # Termux
```

### Frontend no carga (404 en assets)
El frontend necesita compilarse:
```bash
cd tauri-frontend && npm install --legacy-peer-deps && npm run build
```

### Error 401 Unauthorized
- Token expirado → volver a hacer login
- Verificar `localStorage.getItem('api_key')` en el navegador
- Verificar `REDTEAM_API_KEY` en `.env`

### pydantic_core error en Replit
No usar `pip install pydantic` — las deps vienen de `replit.nix`:
```bash
find ~/.local/lib/python3.12/site-packages -maxdepth 1 -iname "pydantic*" -exec rm -rf {} +
```

### ARTO en modo degradado (OSINT no funciona)
Si ARTO aparece corriendo pero las operaciones de scan devuelven vacío:
- **Causa (resuelta 2026-08-20):** Conflicto de paquetes Python `modules` entre
  `arto/modules/` y `backend/modules/` — Python solo podía resolver uno.
- **Fix:** Ya aplicado en el repo. Hacer `git pull` y reiniciar.
- **Verificar:** `GET /api/arto/status` -> `"running": true`
- **Probar:** `POST /api/arto/operation/scan` con body `{"target": "example.com"}`

### SEAL/KRAKEN no aparecen en el dashboard
- **Es esperado:** son módulos independientes. No se montan automáticamente.
- Para activar SEAL: ver [`seal/docs/README.md`](seal/docs/README.md)
- Para activar KRAKEN: ver [`kraken/docs/README.md`](kraken/docs/README.md)

---

## 📦 DESPLIEGUE

| Plataforma | Comando | Nota |
|---|---|---|
| Replit | `bash replit_start.sh` | Auto-deploy, deps via Nix |
| Termux | `bash arrancar.sh` | Instala todo automáticamente |
| Manual | ver arriba | Linux/Mac/Windows |

### Módulos opcionales (Termux)

| Módulo | Instalación | Uso |
|---|---|---|
| SEAL | `pip install aiohttp cryptography` | `python3 seal/scanners/network_sweep_ultimate.py --network CIDR` |
| KRAKEN | `cd kraken && bash termux_install.sh` | `python3 -m kraken.cli.commands --help` |

---

## 🔒 SEGURIDAD

- Auth: API Key via Bearer token
- CORS: configurable via `ALLOWED_ORIGINS`
- Sin mocks: todos los escaneos son reales
- Path traversal: protección en endpoints de config
- Rate limiting: via interceptor
- SEAL tactical: reportes cifrados con Fernet (AES-256), llave persistente

> ⚠️ Los escaneos deben ejecutarse únicamente dentro de un alcance autorizado.

---

## 📝 CHANGELOG

- **v6.0** SEAL SUPER PACK v2.1 + KRAKEN v3.0 integrados (2026-08-21)
- **v5.0** ARTO + VPN (2026-08-19)
- **v4.1** Topología + Traffic Analyzer (2026-08-18)
- **v4.0** OSINT Advanced + Interceptor Advanced (2026-08-14)
- **v3.0** Backend unificado Python/FastAPI (2026-08-10)

---

## 🔗 LINKS

- Repo: https://github.com/sourceseal-star/Red-team-tauri
- Dominio: https://sourceseal.co

---

© 2026 SourceSeal Corp. Uso autorizado únicamente.
