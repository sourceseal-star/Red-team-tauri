# 📖 MANUAL OPERATIVO — LEVIATHAN v3.0

## 1. Activación del Router

El router de LEVIATHAN está diseñado como import opcional en `dashboard_server.py`.
Si los módulos no están instalados o fallan, el dashboard principal sigue funcionando.

### Activar:

Agregar antes del bloque de includes de routers en `redteam/scripts/dashboard_server.py`:

```python
# ── LEVIATHAN ──────────────────────────────────────────────────────────────
try:
    from leviathan_core.api.leviathan_router import router as leviathan_router
    app.include_router(leviathan_router)
    print("[LEVIATHAN] Router montado en /api/leviathan/*")
except Exception as _lev_err:
    print(f"[WARN] LEVIATHAN no disponible: {_lev_err}", flush=True)
```

## 2. Flujo Operativo

### Escaneo de Red

```bash
# API
curl -X POST http://localhost:8001/api/leviathan/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24"}'

# Python directo
python3 -c "
from leviathan_core.modules.scanners import register_all
scanners = register_all()
for s in scanners:
    print(f'{s.name}: {s.description}')
"
```

### Explotación Dirigida

```bash
curl -X POST http://localhost:8001/api/leviathan/exploit \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.100", "module": "hikvision_rce"}'
```

### Análisis IA

```bash
curl -X POST http://localhost:8001/api/leviathan/analyze \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.100", "module": "threat_scoring", "data": {"severity": "high"}}'
```

### Generar Informe

```bash
curl -X POST http://localhost:8001/api/leviathan/report \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24", "format": "json"}'
```

## 3. Frontend

```bash
cd leviathan-frontend
npm install && npm run dev
# Abre http://localhost:5173
# El dashboard carga datos desde /api/leviathan/* del backend
```

### Docker

```bash
cd leviathan-frontend
docker build -t leviathan-frontend .
docker run -p 80:80 --network host leviathan-frontend
# El nginx.conf hace proxy de /api → localhost:8001
```

## 4. Dependencias por Módulo

| Módulo | Requiere | Termux compatible |
|--------|----------|-------------------|
| network_scanner | asyncio, ipaddress, socket | ✅ Sí |
| rtsp_scanner | asyncio, socket | ✅ Sí |
| onvif_scanner | requests | ✅ Sí |
| http_fingerprint | aiohttp, beautifulsoup4 | ✅ Sí |
| camera_detector | asyncio, socket | ✅ Sí |
| service_scanner | socket | ✅ Sí |
| object_detection | cv2, numpy, PIL | ⚠️ Pesado |
| anomaly_detector | numpy | ⚠️ Pesado |
| threat_scoring | — | ✅ Sí |
| behavior_analyzer | — | ✅ Sí |
| pdf_reporter | weasyprint | ⚠️ Pesado |

## 5. Persistencia

Las tablas `leviathan_cameras`, `leviathan_scans`, `leviathan_alerts` se crean
automáticamente en `redteam.db` al primer request. No interfiere con las tablas
existentes del dashboard.
