# 🛡 SourceSeal Red Team - Manual de Despliegue Completo
# Red-team-tauri v3.0

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

### Termux (Android)
```bash
pkg update && pkg upgrade -y
pkg install python python-pip git nodejs-lts openssl -y
pip install fastapi uvicorn aiohttp cryptography pydantic
```

### Replit
- Crear Repl tipo Python
- Importar desde GitHub: `sourceseal-star/Red-team-tauri`
- El `.replit` y `replit.nix` ya están configurados

---

## <a name="termux"></a>2. Instalación en Termux

```bash
# 1. Clonar repositorio
cd ~
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri

# 2. Sincronizar con main
git fetch origin && git reset --hard origin/main

# 3. Instalar dependencias Python
pip install fastapi uvicorn aiohttp cryptography pydantic pymupdf

# 4. Crear directorios necesarios
mkdir -p ~/storage/downloads/seal_reports
mkdir -p ~/storage/templates

# 5. Limpiar caché de Python (importante si hubo errores antes)
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# 6. Arrancar backend unificado
python3 source_seal_backend_v3.py
```

El servidor arranca en `http://localhost:8001`.

---

## <a name="replit"></a>3. Despliegue en Replit

```bash
# En la consola de Replit:
git fetch origin && git reset --hard origin/main

# Limpiar build cache
rm -rf artifacts/api-server/dist 2>/dev/null

# Instalar dependencias
pip install fastapi uvicorn aiohttp cryptography pydantic

# Arrancar (el .replit ya está configurado)
# O manualmente:
python3 source_seal_backend_v3.py
```

**URLs en Replit:**
- API: `https://<tu-repl>.repl.co`
- Docs: `https://<tu-repl>.repl.co/docs`
- WebSocket: `wss://<tu-repl>.repl.co/ws/alerts`

---

## <a name="estructura"></a>4. Estructura del Proyecto

```
Red-team-tauri/
├── source_seal_backend_v3.py    # ← ORQUESTADOR PRINCIPAL v3.0
├── backend/
│   └── dashboard_server.py      # Backend alternativo (redteam/scripts)
├── redteam/
│   └── scripts/
│       └── dashboard_server.py  # Backend con OSINT + Interceptor + ARTO + SEAL
├── arto/                        # Sistema ARTO (AI autónomo)
│   ├── __init__.py
│   ├── api/
│   │   └── arto_router.py       # 16 endpoints + 6 de traffic
│   ├── core/
│   │   ├── decision_engine.py
│   │   ├── learning_engine.py
│   │   ├── prediction_engine.py
│   │   └── action_engine.py
│   ├── memory/
│   │   └── memory_store.py      # SQLite persistence
│   ├── models/
│   └── modules/
│       ├── attack_simulator.py
│       ├── defense_orchestrator.py
│       ├── report_generator.py
│       ├── vpn_interceptor.py  # Captura tráfico VpnService
│       └── anomaly_detector.py
├── seal/                        # SEAL SUPER PACK
│   ├── __init__.py
│   ├── api/
│   │   └── seal_api_router.py   # /devices, /scan, /alerts, /hikvision, /onvif
│   ├── scanners/
│   │   ├── network_sweep_ultimate.py
│   │   ├── fingerprint_engine.py
│   │   └── onvif_scanner.py
│   ├── attackers/
│   │   └── hikvision_killer.py
│   └── utils/
│       └── vendor_dicts.py
├── tauri-frontend/              # Frontend React + Tauri
│   └── src/
│       ├── App.tsx              # Router principal (18+ módulos)
│       ├── components/
│       │   ├── AppShell.tsx     # Sidebar con todos los módulos
│       │   ├── ARTOPanel.tsx    # Panel ARTO (7 pestañas)
│       │   ├── SealPanel.tsx    # Panel SEAL (7 tabs)
│       │   ├── TrafficCapturePanel.tsx
│       │   └── ... (15+ paneles)
│       └── api/
│           ├── sealApi.ts       # Cliente SEAL
│           └── artoApi.ts       # Cliente ARTO
└── android/                     # Tauri Android
    └── app/src/main/java/com/redteam/tauri/vpn/
        ├── ARTOVpnService.java  # VpnService de Android
        └── VpnManager.java      # Gestor VPN
```

---

## <a name="arranque"></a>5. Arranque del Backend

### Opción A: Orquestador v3.0 (Recomendado)
```bash
python3 source_seal_backend_v3.py
```
- Puerto: 8001
- Docs Swagger: `http://localhost:8001/docs`
- Incluye: OSINT + ARTO + SEAL + ThreatIntel + WebSocket + Reports

### Opción B: Backend dashboard_server (redteam/scripts)
```bash
python3 redteam/scripts/dashboard_server.py
```
- Puerto: 8001
- Incluye: OSINT Advanced + Interceptor + ARTO + SEAL

### Opción C: Backend dashboard_server (backend/)
```bash
python3 backend/dashboard_server.py
```
- Puerto: 8001
- Incluye: OSINT Advanced + Interceptor + ARTO + SEAL

**⚠️ Solo ejecutar UN backend a la vez (todos usan el puerto 8001).**

---

## <a name="config"></a>6. Configuración

### Variables de Entorno
```bash
# Clave de cifrado (auto-generada si no se establece)
export SEAL_MASTER_KEY="tu-clave-base64-aqui"

# Threat Intelligence (opcional)
export SHODAN_API_KEY="tu-shodan-key"
export VIRUSTOTAL_API_KEY="tu-vt-key"
export ABUSEIPDB_API_KEY="tu-abuseipdb-key"

# Red por defecto para escaneos
# Se puede cambiar desde la API o UI
```

### Configuración de Red
El target de pentesting se configura desde:
- La UI (Settings → API URL)
- El campo de texto en Reports antes de scan
- El backend lee el target desde `settings.json` en runtime
- **Ya NO está hardcoded a sourceseal.co**

---

## <a name="endpoints"></a>7. API Endpoints

### Escaneo
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/scan` | Escaneo completo de red |
| GET | `/api/v1/scan/quick` | Escaneo rápido (solo hosts activos) |
| GET | `/api/v1/scan/{ip}` | Escaneo de IP específica |

### OSINT
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/osint?username=X` | Verificar username en 14 plataformas |
| POST | `/api/v1/osint/batch` | Verificar múltiples usernames |

### ARTO
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/arto/analyze?target=X` | Análisis autónomo |
| GET | `/api/v1/arto/decision?target=X` | Decisión de ARTO |
| GET | `/api/v1/arto/predictions?timeframe=24` | Predicciones de ataques |
| POST | `/api/v1/arto/simulate` | Simular ataque |

### SEAL
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/seal/network-sweep` | Network sweep completo |
| GET | `/api/v1/seal/hikvision-attack?ip=X` | Ataque Hikvision |
| GET | `/api/v1/seal/onvif-scan` | Escaneo ONVIF |
| GET | `/api/v1/seal/fingerprint/{ip}` | Fingerprint de dispositivo |

### Threat Intelligence
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/threat/shodan/{ip}` | Shodan lookup |
| GET | `/api/v1/threat/virustotal/{ip}` | VirusTotal lookup |
| GET | `/api/v1/threat/abuseipdb/{ip}` | AbuseIPDB lookup |
| GET | `/api/v1/threat/all/{ip}` | Todas las fuentes |

### Alertas
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/alerts` | Listar alertas activas |
| POST | `/api/v1/alerts/{id}/resolve` | Resolver alerta |

### Informes
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/reports` | Listar informes |
| GET | `/api/v1/reports/{filename}` | Descargar informe |

### Estado
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/health` | Estado del sistema |
| WS | `/ws/alerts` | WebSocket de alertas en tiempo real |

### ARTO Router (separado)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/arto/health` | Estado de ARTO |
| POST | `/api/arto/start` | Iniciar ARTO |
| POST | `/api/arto/stop` | Detener ARTO |
| GET | `/api/arto/operations` | Listar operaciones |
| POST | `/api/arto/analyze` | Análisis autónomo |
| POST | `/api/arto/traffic/start` | Iniciar captura VPN |
| POST | `/api/arto/traffic/stop` | Detener captura |
| GET | `/api/arto/traffic/stats` | Stats de tráfico |
| GET | `/api/arto/traffic/packets` | Paquetes capturados |
| GET | `/api/arto/traffic/analysis` | Análisis de tráfico |

### SEAL Router (separado)
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/devices` | Dispositivos detectados |
| GET | `/api/scan` | Escaneo de red |
| GET | `/api/alerts` | Alertas SEAL |
| GET | `/api/status` | Estado SEAL |
| GET | `/api/hikvision/scan` | Scan Hikvision |
| GET | `/api/onvif/scan` | Scan ONVIF |

### Integración
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/integrated/health` | Estado ARTO+SEAL |
| GET | `/api/integrated/scan` | Scan integrado |
| POST | `/api/integrated/attack/{ip}` | Ataque integrado |

---

## <a name="frontend"></a>8. Frontend (Tauri)

### Build del frontend
```bash
cd tauri-frontend
npm install
npm run build
```

### Build Android APK (Tauri)
```bash
# Requiere Android SDK + NDK
cd tauri-frontend
npm run tauri android build
```

### Módulos del Sidebar
1. **War Room** - Dashboard principal
2. **Cámaras** - Camera Command Center
3. **Threat Intel** - Intel + Exploit + Traffic
4. **KRAKEN** - OSINT v4.0
5. **WiFi** - WiFi tools
6. **Ultrasonidos** - Radio
7. **Black Mirror** - Surveillance
8. **Servicios** - Service Control
9. **Terminal** - Terminal remoto
10. **Control Tower** - Tower
11. **Topología** - Network topology
12. **IoT Cámaras** - IoT cameras
13. **Alertas** - Alertas en tiempo real
14. **Exportar** - Export panel
15. **Config** - System settings
16. **OSINT Avanzado** - v4.0
17. **Interceptor Avanzado** - v4.0
18. **ARTO AI** - Panel de operaciones autónomas (badge: AI)
19. **SEAL Pack** - Escaneo y ataque (badge: NEW)

---

## <a name="troubleshooting"></a>9. Troubleshooting

### Error: DecisionType.ANALYZE no existe
```bash
# Limpiar caché de bytecode
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
# Reset a main limpio
git fetch origin && git reset --hard origin/main
```

### Error: 405 Method Not Allowed
```bash
# Los endpoints /api/arto/* requieren que ARTO esté iniciado
# Verificar: curl http://localhost:8001/api/arto/health
# Si no responde, iniciar ARTO: curl -X POST http://localhost:8001/api/arto/start
```

### Error: Redis connection refused
El sistema usa Map en memoria por defecto. Redis NO es necesario.
Si aparece el error, verificar que `sharedStore.ts` use `Map()` y no Redis.

### Error: Port 8001 already in use
```bash
# Verificar qué usa el puerto
lsof -i :8001  # Linux/Mac
ss -tlnp | grep 8001  # Termux
# Matar el proceso
kill -9 <PID>
```

### Error: module 'arto' has no attribute 'start'
```bash
# Verificar que arto/__init__.py existe y tiene la función start
cat arto/__init__.py | grep "async def start"
```

### Error: module 'seal' not found
```bash
# Verificar estructura
ls -la seal/__init__.py
ls -la seal/api/seal_api_router.py
```

### Frontend no compila
```bash
cd tauri-frontend
rm -rf node_modules package-lock.json
npm install
npm run build
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

### Commits recientes (v3.0)
- `faab425` - SourceSeal Backend v3.0 orquestador completo
- `a81699f` - SealPanel + sealApi frontend
- `b43129b` - SEAL integrado en dashboard_server + endpoints
- `d0f7251` - ARTO 28 archivos Python + frontend
- `fe6e351` - Desancleado de sourceseal.co (targets configurables)
- `c52f9d9c` - Seguridad: keystore removido de repo público

---

## 📌 Notas Importantes

1. **SOLO un backend a la vez** - Todos usan puerto 8001
2. **El orquestador v3.0 es el recomendado** - Incluye todo
3. **SQLite se crea automáticamente** en `~/seal_tactical.db`
4. **Los informes se guardan** en `~/storage/downloads/seal_reports/`
5. **WebSocket requiere cliente** - Conectar a `ws://localhost:8001/ws/alerts`
6. **Threat Intelligence necesita API keys** - Sin keys, devuelve error pero no falla
7. **OSINT** - 9 plataformas verificables + 5 marcadas como no verificables (Instagram, LinkedIn, X, Facebook, Reddit)

---

## 🔐 Seguridad

- Cifrado AES-256 Fernet para informes sensibles
- Keystore removido del repositorio público (commit c52f9d9c)
- Targets NO hardcoded - configurables desde UI/API
- Token Bearer para autenticación de API
- Rate limiting en frontend (api.ts interceptor)

---

*Última actualización: v3.0 - SourceSeal Red Team*
*Autor: Harold Paredes / SourceSeal*
