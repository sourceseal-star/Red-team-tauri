# 🦑 LEVIATHAN — Guía de Inicio y Ejecución
**Versión:** 3.0.0 — Edición Industrial
**Autor:** Harold Paredes / SourceSeal Red Team
**Última actualización:** 30 de Agosto 2026

---

## ¿Qué es LEVIATHAN?

LEVIATHAN es el módulo de Red Team automatizado del ecosistema SourceSeal.
Está compuesto por **4 categorías de módulos** con **20+ herramientas especializadas:

| Categoría | Módulos | Función |
|-----------|---------|---------|
| **Scanners** | 6 | Detección de dispositivos, servicios, cámaras IP |
| **Exploiters** | 5 | Explotación ética de vulnerabilidades (Hikvision, Dahua, brute, chain) |
| **AI Analyzers** | 4 | Análisis con IA: objetos, anomalías, comportamiento, threat scoring |
| **Reporters** | 3 | Generación de informes en JSON, HTML y PDF |

---

## ¿Dónde está integrado?

LEVIATHAN **NO es un sistema separado**. Está integrado directamente en el
backend principal (`redteam/scripts/dashboard_server.py`) como router FastAPI:

- **Router 1:** `/api/leviathan/*` — API original de LEVIATHAN
- **Router 2:** `/api/v1/*` — API unificada (scanners, exploiters, AI, reporters)

Ambos routers se montan automáticamente al iniciar el backend. Si los módulos
fallan (dependencias faltantes), el dashboard principal sigue funcionando sin
problema — LEVIATHAN es opcional y degradable.

---

## Inicio Rápido (Termux)

```bash
# 1. Clonar y entrar al repo
cd ~/Red-team-tauri

# 2. Preparar/sincronizar de forma segura
bash termux_recover.sh

# Si ya tienes la copia preparada, arranca sin tocar Git:
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

El backend arranca en `http://localhost:8001`.
LEVIATHAN se monta automáticamente si las dependencias están disponibles.

### Verificar que LEVIATHAN está activo

```bash
curl http://localhost:8001/api/leviathan/status
```

Respuesta esperada:
```json
{
  "scanners": 6,
  "exploiters": 5,
  "analyzers": 4,
  "reporters": 3,
  "status": "operational"
}
```

Si devuelve `null` o error, los módulos no cargaron — ver sección
"Solución de Problemas" abajo.

---

## Frontend — Panel LEVIATHAN

LEVIATHAN tiene su propio panel en el frontend principal (`tauri-frontend`):

1. Abrir el dashboard: `http://localhost:8001` (o el build de Vite)
2. En el sidebar izquierdo, buscar **"LEVIATHAN"** (icono escudo, badge v3.0)
3. El panel tiene 7 secciones expandibles:
   - **Estado del Sistema** — contadores de módulos
   - **Módulos** — lista completa con descripción
   - **Escaneo de Red** — escanear cualquier CIDR (/24, /22, /20, /16)
   - **Explotación Dirigida** — ejecutar exploit contra IP específica
   - **Cámaras Detectadas** — tabla con IP, vendor, vulnerabilidades
   - **Historial** — escaneos anteriores con estado
   - **Informes** — generar JSON, HTML o PDF

### Frontend separado (opcional)

Existe también un frontend React dedicado en `leviathan-frontend/`:

```bash
cd leviathan-frontend
npm install && npm run dev
# Abre http://localhost:3000 (proxy a :8001)
```

> ⚠️ El frontend principal (`tauri-frontend`) ya tiene el panel integrado.
> El frontend separado es para desarrollo standalone o Docker.

---

## Endpoints API

### Scanners (`/api/leviathan/scan` o `/api/v1/scan/*`)

```bash
# Escaneo completo de red
curl -X POST http://localhost:8001/api/leviathan/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24"}'

# Escaneo con módulos específicos
curl -X POST http://localhost:8001/api/leviathan/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24", "modules": ["rtsp_scanner", "camera_detector"]}'

# Scanners individuales via API unificada
curl -X POST http://localhost:8001/api/v1/scan/network \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24"}'

curl -X POST http://localhost:8001/api/v1/scan/cameras \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24"}'

curl -X POST http://localhost:8001/api/v1/scan/rtsp \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.100"}'

curl -X POST http://localhost:8001/api/v1/scan/onvif \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24"}'
```

### Exploiters (`/api/leviathan/exploit` o `/api/v1/exploit/*`)

```bash
# Explotación dirigida
curl -X POST http://localhost:8001/api/leviathan/exploit \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.100", "module": "hikvision_rce"}'

# Módulos disponibles:
# - hikvision_rce     — CVE-2021-36260 (RCE Hikvision)
# - dahua_backdoor    — CVE-2021-31956 (Backdoor Dahua)
# - generic_brute     — Fuerza bruta con diccionarios
# - exploit_chain     — Encadenamiento de exploits
# - kraken_integration — Integración con KRAKEN v3.0
```

### AI Analyzers (`/api/leviathan/analyze` o `/api/v1/ai/*`)

```bash
# Threat scoring
curl -X POST http://localhost:8001/api/leviathan/analyze \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.100", "module": "threat_scoring", "data": {"severity": "high"}}'

# Detección de anomalías
curl -X POST http://localhost:8001/api/v1/ai/anomalies \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.100"}'
```

### Reporters (`/api/leviathan/report` o `/api/v1/report/*`)

```bash
# JSON
curl -X POST http://localhost:8001/api/leviathan/report \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24", "format": "json"}'

# HTML
curl -X POST http://localhost:8001/api/leviathan/report \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24", "format": "html"}'

# PDF (requiere weasyprint)
curl -X POST http://localhost:8001/api/leviathan/report \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.0/24", "format": "pdf"}'
```

### Consultas

```bash
# Cámaras detectadas (persistentes en SQLite)
curl http://localhost:8001/api/leviathan/cameras

# Historial de escaneos
curl http://localhost:8001/api/leviathan/scans

# Alertas activas
curl http://localhost:8001/api/leviathan/alerts

# Perfiles de escaneo
curl http://localhost:8001/api/v1/profiles

# Health check
curl http://localhost:8001/api/v1/health
```

---

## Perfiles de Escaneo

Definidos en `leviathan_core/config/profiles.json`:

| Perfil | Concurrencia | Timeout | Uso |
|--------|-------------|---------|-----|
| **stealth** | 5 | 5s | Escaneo sigiloso (bajo riesgo de detección) |
| **aggressive** | 50 | 2s | Escaneo agresivo (alto rendimiento) |
| **massive** | 200 | 1s | Escaneo masivo (miles de IPs) |
| **camera_detection** | 20 | 3s | Optimizado para cámaras IP |

> ⚠️ En Termux/celular usar `stealth` o `camera_detection`. Los perfiles
> `aggressive` y `massive` son para desktop o servidores con más recursos.

---

## Dependencias por Módulo

### Funciona en Termux sin extra (✅)
- network_scanner, rtsp_scanner, onvif_scanner, http_fingerprint
- camera_detector, service_scanner
- threat_scoring, behavior_analyzer
- json_reporter, html_reporter

### Requiere pip install (⚠️)
- object_detection → `pip install opencv-python-headless numpy ultralytics`
- anomaly_detector → `pip install numpy`
- pdf_reporter → `pip install weasyprint`

### Instalar todo de una vez
```bash
pip install opencv-python-headless numpy aiohttp requests beautifulsoup4
```

> **Nota:** `ultralytics` (YOLO) es pesado (~200MB). Si solo necesitas
> scanners y exploiters, no lo instales — los AI analyzers son opcionales.

---

## Solución de Problemas

### LEVIATHAN no aparece en el status

```bash
# Verificar import
python3 -c "from leviathan_core.api.leviathan_router import router; print('OK')"

# Si falla, verificar dependencias
python3 -c "from leviathan_core.modules.scanners import register_all; print('Scanners OK')"
python3 -c "from leviathan_core.modules.exploiters import register_all; print('Exploiters OK')"
```

### Error: module 'cv2' not found
```bash
pip install opencv-python-headless
```

### Error: module 'aiohttp' not found
```bash
pip install aiohttp
```

### El panel dice "No hay módulos cargados"
Los routers no se montaron. Revisar el log del backend:
```bash
# Si dice "[WARN] LEVIATHAN import falló: ..."
# es que falta una dependencia. Instalarla y reiniciar.
```

---

## Persistencia

LEVIATHAN usa la misma base de datos SQLite (`redteam.db`) que el dashboard
principal. Las tablas se crean automáticamente al primer request:

- `leviathan_cameras` — cámaras IP detectadas
- `leviathan_scans` — historial de escaneos
- `leviathan_alerts` — alertas activas

No interfiere con las tablas existentes del dashboard.

---

## Docker (Frontend standalone)

```bash
cd leviathan-frontend
docker build -t leviathan-frontend .
docker run -p 80:80 --network host leviathan-frontend
# nginx hace proxy de /api → localhost:8001
```

---

## Referencias

- **MANUAL_OPERATIVO.md** (leviathan_core/docs/) — referencia completa de API
- **profiles.json** — configuración de perfiles de escaneo
- **dashboard_server.py** — backend principal donde se montan los routers
- **AppShell.tsx** — sidebar del frontend con el botón LEVIATHAN
- **LeviathanPanel.tsx** — componente React del panel

---

*LEVIATHAN v3.0 — Edición Industrial. SourceSeal Red Team.*
