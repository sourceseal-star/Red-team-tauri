# 🛡 SourceSeal Red Team — Manual de Despliegue Completo
# Red-team-tauri v6.0 — ARTO + LEVIATHAN UNIFIED

> **Última actualización:** 2026-08-30
> **Backend único:** `redteam/scripts/dashboard_server.py` (FastAPI :8001)
> **Frontend único:** `tauri-frontend/` (React/Vite/TypeScript)
> **Arranque recomendado:** `COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh` (Termux) / `bash replit_start.sh` (Replit)

---

## 📋 Tabla de Contenidos
1. [Requisitos Previos](#requisitos)
2. [Instalación en Termux](#termux)
3. [Despliegue en Replit](#replit)
4. [Estructura del Proyecto](#estructura)
5. [Arranque del Backend](#arranque)
6. [Configuración](#config)
7. [API Endpoints](#endpoints)
8. [Frontend (Tauri)](#frontend)
9. [Troubleshooting](#troubleshooting)
10. [Comandos Git](#git)

---

## <a name="requisitos"></a>1. Requisitos Previos

| Componente | Versión | Nota |
|---|---|---|
| **Python** | 3.10+ | Backend FastAPI |
| **Node.js** | 18+ LTS | Compilar frontend |
| **Git** | cualquiera | Clonar/actualizar |
| **Termux** | Desde F-Droid | NO desde Play Store |

### Opcionales (activan funciones extra)

| Herramienta | Instalación | Activa |
|---|---|---|
| `nmap` | `pkg install nmap` | Escaneo de puertos y topología |
| `tcpdump` | `pkg install tcpdump` | Traffic Analyzer (captura de paquetes) |
| `whois` | `pkg install whois` | OSINT WHOIS lookup |
| `dig` | `pkg install bind-utils` | DNS recon |
| `termux-api` | `pkg install termux-api` | Wake-lock + WiFi scan |
| `iproute2` | `pkg install iproute2` | ARP discovery (SEAL tactical) |
| `ffmpeg` | `pkg install ffmpeg` | Transcodificación RTSP→HLS |

---

## <a name="termux"></a>2. Instalación en Termux

```bash
# 1. Descargar Termux de F-Droid (NO Play Store)
#    https://f-droid.org/packages/com.termux/

# 2. Permisos de almacenamiento
termux-setup-storage

# 3. Sin restricciones de batería:
#    Ajustes → Apps → Termux → Batería → Sin restricciones

# 4. Instalar Python, Node.js y herramientas
pkg update -y && pkg upgrade -y
pkg install -y python nodejs-lts git openssl curl

# 5. Clonar repositorio principal
cd ~
git clone git@github.com:sourceseal-star/Red-team-tauri.git
cd Red-team-tauri

# 6. (Opcional) termux-api para wake-lock
pkg install -y termux-api

# 7. Preparar/sincronizar Red-team-tauri + Commander y arrancar
bash termux_recover.sh
```

Para ejecutar la copia local sin modificarla ni sincronizar Git:

```bash
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

`termux_recover.sh` conserva `.env` y se detiene ante cambios locales sin
guardar. `arrancar.sh` es solo un alias compatible del recuperador; no es el
comando de arranque local.

### COM-LINK y hardware Android

COM-LINK no es un servicio remoto adicional. Sus comandos se ejecutan donde
corre `dashboard_server.py`. En Replit el archivo puede estar instalado, pero
no hay Termux:API ni hardware del teléfono. En Termux, verifica la preparación
sin enviar mensajes:

```bash
bash commander/comlink/comlink.sh status-json | jq
```

No asumas que los siete canales están activos. Revisa `ready_count` y
`channels[].reason`; radio AX.25 y satélite permanecen no implementados hasta
contar con un driver probado. Consulta [`COMLINK_OPERATIVO.md`](COMLINK_OPERATIVO.md).

Si se necesita usar un checkout independiente de Commander:

```bash
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

---

## <a name="replit"></a>3. Despliegue en Replit

```bash
# Importar desde GitHub: sourceseal-star/Red-team-tauri
# El .replit y replit.nix ya están configurados

# Sincronizar con main
git fetch origin && git reset --hard origin/main

# Arrancar
bash replit_start.sh
```

**URLs en Replit:**
- Dashboard: `https://<tu-repl>.repl.co`
- API: `https://<tu-repl>.repl.co/api/health`
- Docs Swagger: `https://<tu-repl>.repl.co/docs`
- WebSocket: `wss://<tu-repl>.repl.co/ws/alerts`

---

## <a name="estructura"></a>4. Estructura del Proyecto

```
Red-team-tauri/
├── termux_recover.sh          ← Preparar/sincronizar Termux de forma segura
├── iniciar_unificado.sh       ← Arranque local unificado sin tocar Git
├── arrancar.sh                ← Alias compatible del recuperador
├── start-termux.sh            ← Arranque Termux con gateway mesh opcional
├── replit_start.sh            ← Arranque Replit
├── quickstart.sh              ← Arranque + smoke tests automáticos
├── sync.sh                    ← Sincronización forzada + rebuild
├── .env.example               ← Template de API keys
│
├── redteam/scripts/
│   └── dashboard_server.py    ← BACKEND ÚNICO — FastAPI :8001
│                               ← Sirve API + frontend estático
│                               ← 80+ endpoints unificados
│
├── tauri-frontend/            ← FRONTEND ÚNICO — React/Vite/TS
│   ├── src/components/        ← 30+ componentes
│   ├── src/api/               ← artoApi, interceptorApi, osintApi
│   └── dist/                  ← Build output (servido por backend)
│
├── arto/                      ← Sistema ARTO (AI autónomo)
│   ├── api/arto_router.py     ← 23 endpoints FastAPI
│   ├── core/                  ← 5 motores AI
│   ├── modules/               ← attack_simulator, vpn, defense
│   └── memory/                ← SQLite + knowledge_base
│
├── seal/                      ← SEAL SUPER PACK v2.1 (independiente)
│   ├── scanners/             ← network_sweep, onvif, fingerprint
│   ├── attackers/             ← hikvision_killer
│   └── api/                   ← seal_api_router (20+ endpoints)
│
├── leviathan_core/            ← LEVIATHAN v3.1 (módulos Red Team)
│   ├── modules/               ← scanners(6), exploiters(5), ai(4), reporters(3)
│   ├── api/                   ← leviathan_router + integration_router
│   └── config/profiles.json   ← Perfiles de escaneo
│
├── kraken/                    ← KRAKEN v3.0 (independiente)
├── gateway/                   ← Federación mesh (orchestrator + satellite)
├── honeypot/                  ← Honeypot + canary tokens
├── backend/modules/
│   └── enhanced_recon.py      ← Reconocimiento de red optimizado
└── android/                   ← VpnService Java (captura sin root)
```

> ⚠️ **Backend en uso:** `redteam/scripts/dashboard_server.py` es el ÚNICO backend.
> `backend/dashboard_server.py` es una versión anterior/paralela sin endpoints v2.
> `source_seal_backend_v3.py` es legacy — NO usar.

---

## <a name="arranque"></a>5. Arranque del Backend

### Opción A: iniciar_unificado.sh (Termux, sin sincronizar)
```bash
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```
Levanta la copia local sin `git pull`, `reset`, `stash` ni instalación de
paquetes. Inicia el dashboard unificado, Commander integrado y PHANTOM.

### Opción B: replit_start.sh (Replit)
```bash
bash replit_start.sh
```

### Opción C: quickstart.sh (Arranque + tests)
```bash
bash quickstart.sh
```
Instala deps, compila frontend, levanta backend y ejecuta smoke tests.

### Preparar o actualizar Termux
```bash
bash termux_recover.sh
```
Sincroniza ambos repositorios solo cuando no hay cambios locales sin guardar,
prepara dependencias, compila el frontend y arranca todo.

### Opción D: Manual
```bash
cd tauri-frontend && npm install --legacy-peer-deps && npm run build && cd ..
cd redteam/scripts
export PORT=8001 HOST=0.0.0.0
python3 dashboard_server.py
```

→ Abrir `http://localhost:8001` en el navegador.

**⚠️ Solo ejecutar UN backend a la vez (todos usan el puerto 8001).**

---

## <a name="config"></a>6. Configuración

### Variables de Entorno (.env)

El archivo `.env` se crea automáticamente con `arrancar.sh`.
Edítalo con `nano .env`:

```bash
# === API KEYS OSINT (todas tienen tier gratis) ===

# AbuseIPDB: https://www.abuseipdb.com/account/api — gratis, 1000 checks/día
ABUSEIPDB_KEY=tu-key-aqui

# Shodan: https://www.shodan.io/dashboard — cuenta gratis
SHODAN_API_KEY=tu-key-aqui

# Hunter.io (emails): https://hunter.io/api-keys — opcional
HUNTER_API_KEY=tu-key-aqui
```

> ⚠️ **Importante:** La variable es `ABUSEIPDB_KEY` (sin `_API`).
> Si una clave no funciona, verifica el nombre exacto en `.env`.

Los módulos funcionan sin keys con fallbacks graceful.

### Configuración de Red
El target de pentesting se configura desde:
- La UI (Settings → API URL)
- El campo de texto en Reports antes de scan
- El backend lee el target desde `settings.json` en runtime
- **Ya NO está hardcoded a sourceseal.co**

---

## <a name="endpoints"></a>7. API Endpoints

### Core
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard HTML |
| GET | `/api/health` | Estado del servidor |
| GET | `/api/geo?ip=X` | Geolocalización (ipwho.is) |
| GET | `/api/intel?ip=X` | Threat score |
| GET | `/api/iot?ip=X` | Scan IoT de un host |
| GET | `/api/full?ip=X` | Geo + Intel + IoT combinado |
| POST | `/api/scan/network` | Scan red /24 (254 hosts) |
| GET | `/api/scan/network/stream?subnet=X` | Scan red SSE en vivo |
| POST | `/api/forensics/analyze` | Análisis forense (multipart) |

### LEVIATHAN (/api/v1/*)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/status` | Estado completo del sistema |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/profiles` | Perfiles de escaneo disponibles |
| POST | `/api/v1/scan/network` | Escaneo de red (con perfil) |
| POST | `/api/v1/scan/cameras` | Detección de cámaras IP |
| POST | `/api/v1/scan/rtsp` | Detección RTSP |
| POST | `/api/v1/exploit/camera` | Explotación (auto-detect vendor) |
| POST | `/api/v1/ai/threat-scoring` | Puntuación de amenazas |
| POST | `/api/v1/ai/anomalies` | Detección de anomalías |
| POST | `/api/v1/report/json` | Informe JSON |
| POST | `/api/v1/report/html` | Informe HTML |

### ARTO (/api/arto/*)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/arto/status` | Estado de ARTO |
| POST | `/api/arto/start` | Iniciar ARTO |
| POST | `/api/arto/stop` | Detener ARTO |
| POST | `/api/arto/traffic/start` | Iniciar captura VPN |
| POST | `/api/arto/traffic/stop` | Detener captura |
| GET | `/api/arto/traffic/stats` | Stats de tráfico |
| GET | `/api/arto/traffic/analysis` | Análisis de tráfico |

### OSINT (/api/osint/*)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/osint/whois/{domain}` | WHOIS lookup |
| GET | `/api/osint/dns/{domain}` | DNS recon (A, MX, TXT, NS, SPF, DMARC) |
| GET | `/api/osint/shodan/{ip}` | Shodan host lookup |
| GET | `/api/osint/full/{domain}` | OSINT completo |
| GET | `/api/osint/google?q=` | Google Custom Search |

### Alertas
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/alerts` | Listar alertas activas |
| WS | `/ws/alerts` | WebSocket de alertas en tiempo real |

---

## <a name="frontend"></a>8. Frontend (Tauri)

### Build del frontend
```bash
cd tauri-frontend
npm install --legacy-peer-deps
npm run build
```

### Módulos del Sidebar
1. **War Room** - Dashboard principal
2. **Cámaras** - Camera Command Center
3. **Threat Intel** - Intel + Exploit + Traffic
4. **KRAKEN** - OSINT v4.0
5. **WiFi** - WiFi tools
6. **Topología** - Network topology
7. **IoT Cámaras** - IoT cameras
8. **Alertas** - Alertas en tiempo real
9. **ARTO AI** - Panel de operaciones autónomas
10. **SEAL Pack** - Escaneo y ataque
11. **OSINT Avanzado** - v4.0
12. **Interceptor Avanzado** - v4.0

### Build Android APK (Tauri)
Requiere Android SDK + NDK + keystore configurado.
Ver `SETUP_FIRMA_APK.md` para instrucciones de firma.

---

## <a name="troubleshooting"></a>9. Troubleshooting

### Página vacía / blanco
```bash
curl http://localhost:8001/api/health
# Si no responde:
pkill -f "dashboard_server.py"
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

### "python3: not found"
```bash
pkg install -y python
```

### El frontend no compila
```bash
cd tauri-frontend
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npm run build
```

### Puerto 8001 ocupado
```bash
pkill -9 -f dashboard_server.py
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

### AbuseIPDB no devuelve datos
Verifica que en `.env` la variable se llama `ABUSEIPDB_KEY` (no `ABUSEIPDB_API_KEY`).
```bash
grep ABUSEIPDB .env
# Debe mostrar: ABUSEIPDB_KEY=tu-key
```

### ARTO no arranca / modo degradado
```bash
curl localhost:8001/api/arto/status
# Si responde error, reiniciar:
pkill -f dashboard_server.py
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

### Traffic Analyzer muestra error "tcpdump no instalado"
```bash
pkg install tcpdump
```

### Termux se cierra solo
```bash
pkg install -y termux-api
termux-wake-lock
# Ajustes → Apps → Termux → Batería → Sin restricciones
```

### git pull falla con conflictos
```bash
cd ~/Red-team-tauri
git status --short
# Ejecutar la versión local sin perder cambios:
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
# Para actualizar, guarda primero los cambios y luego:
bash termux_recover.sh
```

### Error en memoria SQLite de ARTO
```bash
rm -f arto/data/arto_memory.db
# Reiniciar — se recrea automáticamente
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

---

## <a name="git"></a>10. Comandos Git

### Sincronizar con main
```bash
git fetch origin && git reset --hard origin/main
```

### Limpiar todo y empezar fresco
```bash
git fetch origin
git reset --hard origin/main
git clean -fdx
find . -type d -name __pycache__ -exec rm -rf {} +
rm -rf tauri-frontend/node_modules tauri-frontend/dist
```

### Ver últimos commits
```bash
git log --oneline -10
```

---

## 📌 Notas Importantes

1. **SOLO un backend a la vez** — Todos usan puerto 8001
2. **`termux_recover.sh` prepara/actualiza; `iniciar_unificado.sh` ejecuta localmente**
3. **`redteam/scripts/dashboard_server.py` es el backend único** — No usar otros
4. **SQLite se crea automáticamente** — No requiere configuración manual
5. **WebSocket requiere cliente** — Conectar a `ws://localhost:8001/ws/alerts`
6. **Threat Intelligence necesita API keys** — Sin keys, devuelve error pero no falla
7. **OSINT funciona sin keys** — Con fallbacks graceful

---

## 🔐 Seguridad

- Cifrado AES-256 Fernet para informes sensibles
- Keystore removido del repositorio público
- Targets NO hardcoded — configurables desde UI/API
- Token Bearer para autenticación de API
- Zero-PII: emails se hashean con SHA-256 antes de almacenarse

---

*Última actualización: v6.0 — ARTO + LEVIATHAN UNIFIED (2026-08-30)*
*Ver también: `MANUAL_OPERATIVO.md` (referencia completa), `GUIA_ARRANQUE.md` (arranque rápido)*
