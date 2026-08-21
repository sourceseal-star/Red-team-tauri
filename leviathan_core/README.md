# 🦑 LEVIATHAN v3.0 — Sistema de Módulos de Red Team

**Versión:** 3.0.0 | **Autor:** Harold Paredes / SourceSeal Red Team  
**Estado:** ✅ Integrado en Red-team-tauri

## Arquitectura

```
leviathan_core/
├── __init__.py
├── core/
│   ├── __init__.py
│   └── engine.py              # ModuleManager + LeviathanEngine
├── modules/
│   ├── scanners/              # 6 módulos de detección
│   ├── exploiters/            # 5 módulos de explotación
│   ├── ai_analyzers/          # 4 módulos de análisis IA
│   └── reporters/             # 3 generadores de informes
├── api/
│   └── leviathan_router.py    # FastAPI router (/api/leviathan/*)
└── requirements.txt

leviathan-frontend/
├── package.json               # React 18 + Redux + Vite
├── Dockerfile                 # Build con Node + serve con nginx
├── nginx.conf                 # Proxy /api → backend, /ws → WebSocket
├── src/
│   ├── main.tsx               # Entry point
│   ├── App.tsx                # Router + layout
│   ├── store/                 # Redux (ui, cameras, scans, alerts)
│   ├── api/                   # Axios client + WebSocket
│   ├── hooks/                 # useWebSocket
│   └── components/            # Dashboard, LiveGrid, CameraViewer, etc.
```

## API Endpoints

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

## Backend — Activar en dashboard_server.py

El router es un import opcional. Para activarlo, agregar en `redteam/scripts/dashboard_server.py`:

```python
# ── LEVIATHAN modules router ───────────────────────────────────────────────
try:
    from leviathan_core.api.leviathan_router import router as leviathan_router
    app.include_router(leviathan_router)
    print("[LEVIATHAN] Router montado en /api/leviathan/*")
except Exception as _lev_err:
    print(f"[WARN] LEVIATHAN no disponible: {_lev_err}", flush=True)
```

## Frontend — Desarrollo

```bash
cd leviathan-frontend
npm install
npm run dev          # Dev server en :5173
npm run build        # Build producción → dist/
```

### Docker

```bash
cd leviathan-frontend
docker build -t leviathan-frontend .
docker run -p 80:80 leviathan-frontend
```

## Módulos Disponibles

### Scanners (6)
- `network_scanner` — Escaneo de red con detección de dispositivos
- `rtsp_scanner` — Detección de streams RTSP
- `onvif_scanner` — Detección de dispositivos ONVIF
- `http_fingerprint` — Identificación de servicios HTTP
- `camera_detector` — Detección de cámaras IP (Hikvision, Dahua, etc.)
- `service_scanner` — Escaneo de puertos y servicios

### Exploiters (5)
- `hikvision_rce` — Explotación de Hikvision
- `dahua_backdoor` — Explotación de Dahua
- `generic_brute` — Fuerza bruta genérica
- `kraken_integration` — Integración con KRAKEN
- `exploit_chain` — Encadenamiento de exploits

### AI Analyzers (4)
- `object_detection` — Detección de objetos en video
- `anomaly_detector` — Detección de anomalías
- `behavior_analyzer` — Análisis de comportamiento
- `threat_scoring` — Puntuación de amenazas

### Reporters (3)
- `json_reporter` — Informes JSON
- `html_reporter` — Informes HTML visuales
- `pdf_reporter` — Informes PDF

## Instalación Termux (ligera)

```bash
pip install aiohttp requests beautifulsoup4
# Para AI analyzers (opcional, pesado):
# pip install opencv-python-headless numpy pillow
# Para PDF reporter (opcional):
# pip install weasyprint
```

## Aislamiento

LEVIATHAN es completamente independiente:
- No importa ni modifica kraken/, seal/, redteam/, o dashboard_server.py
- Sus tablas SQLite (`leviathan_*`) son propias
- El router se monta opcionalmente — si falla, el dashboard sigue funcionando
