# 🦑 LEVIATHAN v3.1 — Sistema de Módulos de Red Team

**Versión:** 3.1.0 | **Autor:** Harold Paredes / SourceSeal Red Team  
**Estado:** ✅ Integrado en Red-team-tauri via `include_router`

## Arquitectura

```
leviathan_core/
├── __init__.py
├── banner.py                  # Banner ASCII art
├── core/
│   ├── __init__.py
│   └── engine.py              # ModuleManager + LeviathanEngine
├── modules/
│   ├── scanners/              # 6 módulos de detección
│   ├── exploiters/            # 5 módulos de explotación
│   ├── ai_analyzers/          # 4 módulos de análisis IA
│   └── reporters/             # 3 generadores de informes
├── api/
│   ├── leviathan_router.py    # Router básico (/api/leviathan/*)
│   └── integration_router.py # Router unificado (/api/v1/*) — NUEVO
├── config/
│   ├── __init__.py
│   └── profiles.json          # Perfiles de escaneo + OPSEC + camera defaults
├── tools/
│   ├── __init__.py
│   ├── convert_yolo_onnx.py   # Conversión YOLOv8 a ONNX (PC)
│   └── verify_modules.py      # Verificador de módulos para Termux
└── docs/
    └── MANUAL_OPERATIVO.md

leviathan-frontend/
├── package.json               # React 18 + Redux + Vite
├── src/
│   ├── components/            # Dashboard, LiveGrid, CameraViewer, etc.
│   ├── api/                   # Axios client + WebSocket
│   └── store/                 # Redux (ui, cameras, scans, alerts)
```

## API Endpoints

### Router básico (/api/leviathan/*)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/leviathan/status` | Estado del sistema |
| GET | `/api/leviathan/modules` | Lista todos los módulos |
| POST | `/api/leviathan/scan` | Ejecuta scanners |
| POST | `/api/leviathan/exploit` | Ejecuta un exploiter |
| POST | `/api/leviathan/analyze` | Ejecuta un AI analyzer |
| POST | `/api/leviathan/report` | Genera informe |
| GET | `/api/leviathan/cameras` | Cámaras detectadas |
| GET | `/api/leviathan/scans` | Historial de escaneos |
| GET | `/api/leviathan/alerts` | Alertas activas |

### Router unificado (/api/v1/*) — NUEVO v3.1

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/status` | Estado completo del sistema |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/profiles` | Perfiles de escaneo disponibles |
| POST | `/api/v1/scan/network` | Escaneo de red completo |
| POST | `/api/v1/scan/cameras` | Detección de cámaras IP |
| POST | `/api/v1/scan/rtsp` | Detección RTSP |
| POST | `/api/v1/scan/onvif` | Detección ONVIF |
| POST | `/api/v1/scan/services` | Escaneo de servicios |
| POST | `/api/v1/exploit/camera` | Explotación por vendor (auto-detect) |
| POST | `/api/v1/exploit/chain` | Cadena de exploits |
| POST | `/api/v1/ai/threat-scoring` | Puntuación de amenazas |
| POST | `/api/v1/ai/anomalies` | Detección de anomalías |
| POST | `/api/v1/ai/behavior` | Análisis de comportamiento |
| POST | `/api/v1/report/json` | Informe JSON |
| POST | `/api/v1/report/html` | Informe HTML |

## Detección de Objetos con ONNX (Termux)

El módulo `object_detection` v3.1 usa **onnxruntime** en vez de ultralytics/PyTorch.
PyTorch no compila en Termux/Android, pero onnxruntime sí.

### Setup (2 pasos)

**Paso 1 — En PC (convertir modelo):**
```bash
pip install ultralytics onnx
python3 leviathan_core/tools/convert_yolo_onnx.py
# Genera yolov8n.onnx (~12MB)
```

**Paso 2 — En Termux:**
```bash
pip install onnxruntime numpy pillow
# Copiar yolov8n.onnx a redteam/models/
scp yolov8n.onnx termux:~/Red-team-tauri/redteam/models/
```

El módulo detecta automáticamente si hay un `.onnx` disponible y lo usa.
Si estás en PC con ultralytics, usa el `.pt` directamente.

## Verificación de Módulos

```bash
python3 leviathan_core/tools/verify_modules.py
```

Verifica deps base, core, scanners, exploiters, AI, reporters.
Reporta: `TOTAL: 28/30 módulos OK`.

## Módulos Disponibles

### Scanners (6)
- `network_scanner` — Escaneo de red con detección de dispositivos
- `rtsp_scanner` — Detección de streams RTSP
- `onvif_scanner` — Detección de dispositivos ONVIF
- `http_fingerprint` — Identificación de servicios HTTP
- `camera_detector` — Detección de cámaras IP (Hikvision, Dahua, etc.)
- `service_scanner` — Escaneo de puertos y servicios

### Exploiters (5)
- `hikvision_rce` — Explotación de Hikvision (CVE-2021-36260)
- `dahua_backdoor` — Explotación de Dahua (CVE-2021-31956)
- `generic_brute` — Fuerza bruta genérica
- `kraken_integration` — Integración con KRAKEN
- `exploit_chain` — Encadenamiento de exploits

### AI Analyzers (4) — compatibles con Termux
- `object_detection` — Detección de objetos (ONNX/ultralytics dual)
- `anomaly_detector` — Detección de anomalías (Python puro, numpy opcional)
- `behavior_analyzer` — Análisis de comportamiento (Python puro)
- `threat_scoring` — Puntuación de amenazas (Python puro)

### Reporters (3)
- `json_reporter` — Informes JSON
- `html_reporter` — Informes HTML visuales
- `pdf_reporter` — Informes PDF

## Perfiles de Escaneo (profiles.json)

| Perfil | Concurrencia | Jitter | Descripción |
|--------|-------------|--------|-------------|
| stealth | 5 | 2-5s | Escaneo sigiloso |
| aggressive | 50 | 0.1-0.5s | Alto rendimiento |
| massive | 200 | 0.05-0.2s | Miles de IPs |
| camera_detection | 20 | 0.5-1.5s | Optimizado para cámaras IP |

## Instalación Termux

```bash
# Deps base (livianas, funcionan en Termux)
pip install aiohttp requests beautifulsoup4 pydantic

# Detección de objetos (ONNX — liviano)
pip install onnxruntime numpy pillow

# Verificar que todo carga
python3 leviathan_core/tools/verify_modules.py
```

## Aislamiento

LEVIATHAN es completamente independiente:
- No modifica kraken/, seal/, arto/, o dashboard_server.py core
- Se monta via `include_router` — si falla, el dashboard sigue funcionando
- El router de integración (/api/v1/*) carga módulos bajo demanda
