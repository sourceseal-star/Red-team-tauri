# SourceSeal Console — Centro de Control

Dashboard de operaciones de seguridad ofensiva y defensiva. El flujo activo en Replit
es el dashboard unificado de `Red-team-tauri` con LEVIATHAN v3.1 integrado.

## Cómo ejecutar

```bash
bash replit_start.sh
```

El workflow **SourceSeal Dashboard** arranca automáticamente el backend y sirve el
frontend compilado en el puerto **8001**.

En Termux, `bash arrancar.sh` inicia todo + detecta entorno Android.

### Despliegue conjunto en Termux: Red-team-tauri + Commander

El arranque oficial para Android instala las dependencias, sincroniza ambos repositorios, compila el frontend y lanza el sistema unificado:

```bash
cd ~/Red-team-tauri
bash termux_recover.sh
```

El script usa por defecto `https://github.com/sourceseal-star/commander.git` y deja estos servicios locales:
- Dashboard Red-team-tauri: `http://localhost:8001`
- Dashboard Commander: `http://localhost:8003`
- GHOST HUNTER PHANTOM: `http://localhost:8002/api/status`

Como Commander es privado, Git debe estar autenticado en Termux antes de ejecutar el script. No pongas tokens en la URL ni los guardes en el repositorio. Si prefieres SSH:

```bash
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git bash termux_recover.sh
```

Health check:

```bash
curl http://localhost:8001/api/health
curl http://localhost:8001/api/v1/status       # LEVIATHAN unificado
curl http://localhost:8001/api/integrated/health  # ARTO + SEAL + LEVIATHAN
```

## Estructura principal

```
redteam/
└── scripts/dashboard_server.py    # Backend unificado FastAPI :8001
leviathan_core/                     # Módulos de Red Team (31+ archivos)
├── api/
│   ├── leviathan_router.py         # /api/leviathan/* (CRUD básico)
│   └── integration_router.py      # /api/v1/* (unificado — NUEVO)
├── config/profiles.json            # Perfiles de escaneo + OPSEC
├── modules/
│   ├── scanners/ (6)              # network, rtsp, onvif, http, camera, service
│   ├── exploiters/ (5)            # hikvision_rce, dahua, brute, kraken, chain
│   ├── ai_analyzers/ (4)          # object_detection, anomaly, behavior, threat
│   └── reporters/ (3)             # json, html, pdf
└── tools/
    ├── convert_yolo_onnx.py        # Convertir YOLOv8 a ONNX (PC)
    └── verify_modules.py           # Verificar módulos
tauri-frontend/
├── src/                            # React + TypeScript
└── dist/                           # Frontend compilado para el backend
```

## Endpoints LEVIATHAN (/api/v1/*)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/status` | Estado del sistema LEVIATHAN |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/profiles` | Perfiles de escaneo disponibles |
| POST | `/api/v1/scan/network` | Escaneo de red (con perfil) |
| POST | `/api/v1/scan/cameras` | Detección de cámaras IP |
| POST | `/api/v1/scan/rtsp` | Detección RTSP |
| POST | `/api/v1/scan/onvif` | Detección ONVIF |
| POST | `/api/v1/exploit/camera` | Explotación (auto-detect vendor) |
| POST | `/api/v1/ai/threat-scoring` | Puntuación de amenazas |
| POST | `/api/v1/ai/anomalies` | Detección de anomalías |
| POST | `/api/v1/report/json` | Informe JSON |
| POST | `/api/v1/report/html` | Informe HTML |

## Detección de Objetos con IA (ONNX)

### En Replit/PC:
```bash
pip install onnxruntime numpy pillow
# Convertir modelo YOLOv8:
pip install ultralytics onnx
python3 leviathan_core/tools/convert_yolo_onnx.py
```

### En Termux:
onnxruntime no tiene wheels para aarch64/Android. El módulo degrada gracefully
(sin romper el dashboard). Para activarlo:
1. Convertir modelo en PC → `yolov8n.onnx`
2. Copiar a `redteam/models/yolov8n.onnx`
3. `pip install numpy pillow` en Termux

## Verificación de Módulos

```bash
python3 leviathan_core/tools/verify_modules.py
```


## Endpoints IoT y Cámaras (/api/iot/*)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/iot/vulns?ip=X&port=Y` | Vendor + CVEs + creds + URLs |
| GET | `/api/iot/auto-access?ip=X&port=Y` | Orquestación completa en 1 llamado |
| POST | `/api/iot/auto-access-batch` | Escanea red CIDR, procesa todas las cámaras |
| GET | `/api/iot/snapshot?ip=X&port=Y&user=U&pwd=P` | Snapshot con 11 paths + auth |
| GET | `/api/iot/stream?ip=X&port=Y&path=P&user=U&pwd=P` | Proxy MJPEG en vivo |

## Vendors de cámaras detectados
Hikvision, Dahua, Xiongmai, D-Link, Netgear, GoAhead, Ubiquiti, ONVIF

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `8001` | Puerto HTTP del dashboard |
| `HOST` | `0.0.0.0` | Host de escucha |
| `REDTEAM_API_KEY` | local-dev-token | Clave para endpoints protegidos |
| `CORSET_SCOPE_B64` | — | Alcance autorizado de escaneo |
| `SHODAN_API_KEY` | — | Intel Shodan |
| `ABUSEIPDB_KEY` | — | Reputación de IPs |
| `START_GATEWAY` | `1` en Termux | Inicia el Gateway Mesh en 8080 |

El backend no rellena resultados con datos simulados. Para operar escaneos reales,
define un alcance autorizado mediante `CORSET_SCOPE_B64`.

## Solución de problemas

### git pull falla con "unstaged changes"
```bash
git stash && git pull origin main && git stash pop
# Si conflicto: git checkout . && git pull origin main
```

### Verificar que todo carga
```bash
python3 leviathan_core/tools/verify_modules.py
```

### Puerto 8001 ocupado
```bash
pkill -9 -f dashboard_server.py
bash arrancar.sh   # o bash replit_start.sh
```

### LEVIATHAN no carga
El router es opcional — si falla, el dashboard sigue funcionando.
Revisar el output de arranque: `[LEVIATHAN] Router montado: /api/leviathan/* + /api/v1/*`
Si dice `[WARN] LEVIATHAN import falló`, revisar dependencias con verify_modules.py.

## User preferences

- Idioma de comunicación: español
