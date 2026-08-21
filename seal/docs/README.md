# SEAL SUPER PACK v2.1 — Guía de Instalación, Ejecución y Sync

Sistema de inteligencia de red, cámaras y OSINT para Red-team-tauri.
**Independiente del dashboard principal** — ver sección de aislamiento.

## Estructura del repo (resumen)

```
Red-team-tauri/
├── redteam/scripts/dashboard_server.py   ← BACKEND PRINCIPAL (puerto 8001)
├── kraken/                                ← KRAKEN v3.0 (motor de explotación, standalone)
├── seal/                                  ← SEAL SUPER PACK (este módulo)
│   ├── scanners/
│   │   ├── network_sweep_ultimate.py     Escaneo ARP+Ping, vendor fingerprint
│   │   ├── onvif_scanner.py              WS-Discovery + HTTP ONVIF
│   │   └── fingerprint_engine.py         CVE matching + risk scoring
│   ├── attackers/
│   │   └── hikvision_killer.py           CVE-2021-36260 + brute force + RTSP
│   ├── utils/
│   │   └── vendor_dicts.py               600+ credenciales, 20+ fabricantes
│   ├── orchestrator/
│   │   └── seal_orchestrator.py          Monitoreo 24/7, change detection
│   ├── ai/
│   │   └── arto_integration.py           Bridge con ARTO
│   ├── core/
│   │   └── tactical_engine.py            Motor de auditoría rápida + reportes cifrados (NUEVO v2.1)
│   └── api/
│       └── seal_api_router.py            20+ endpoints FastAPI (montaje opcional)
└── frontend/src/components/SealPanel.tsx  Panel React (6 pestañas)
```

## Principio de aislamiento

- `redteam/scripts/dashboard_server.py` es y sigue siendo el **backend principal y único que arranca por defecto** (Replit + `arrancar.sh` en Termux).
- `kraken/` y `seal/` son módulos **independientes**: no se importan automáticamente en el dashboard. Cero riesgo de romper nada existente al actualizarlos.
- Para activar los endpoints de SEAL dentro del dashboard (opcional), hay que añadir manualmente 1-2 líneas en `dashboard_server.py` (ver sección "Activar SEAL en el dashboard").
- Cada módulo de `seal/` también funciona **suelto por CLI** sin necesidad del dashboard — ideal para Termux en campo.

## Puertos usados

| Puerto | Servicio | Dónde |
|--------|----------|-------|
| 8001 | Dashboard principal (`dashboard_server.py`) | Replit + Termux, siempre activo |
| 8011 | `tactical_engine.py --serve` (opcional, standalone) | Solo si se corre manualmente, NUNCA junto al dashboard en el mismo puerto |

## Instalación

### Replit (sync)

```bash
git pull origin main
bash replit_start.sh        # levanta el dashboard en :8001, sin cambios
```

Los módulos `kraken/` y `seal/` llegan con el `git pull` pero no se ejecutan solos en Replit — están disponibles para usarlos vía Termux o para montarlos manualmente en el dashboard si se decide.

### Termux — dashboard (sin cambios)

```bash
cd ~/Red-team-tauri
git pull origin main
bash arrancar.sh             # dashboard en :8001, igual que siempre
```

### Termux — SEAL (opcional, independiente)

```bash
cd ~/Red-team-tauri
pip install aiohttp fastapi uvicorn cryptography

# Módulos que necesitan paquete de sistema para ARP:
pkg install iproute2          # da el comando `ip` (usado por network_sweep_ultimate y tactical_engine)
```

### Termux — KRAKEN (opcional, independiente, ya documentado)

```bash
cd ~/Red-team-tauri/kraken
bash termux_install.sh
```

## Ejecución — uso directo (CLI, sin dashboard)

```bash
# Escaneo de red completo (ARP + Ping + vendor fingerprint)
python3 seal/scanners/network_sweep_ultimate.py --network 192.168.0.0/24

# Detección ONVIF
python3 seal/scanners/onvif_scanner.py --network 192.168.0.0/24

# Ataque a cámara Hikvision (CVE-2021-36260 + brute force)
python3 seal/attackers/hikvision_killer.py 192.168.0.7 --brute

# Motor táctico — auditoría rápida con reporte cifrado (NUEVO)
python3 -m seal.core.tactical_engine --network 192.168.0.0/24

# Orquestador continuo (monitoreo 24/7)
python3 seal/orchestrator/seal_orchestrator.py --start
```

Los reportes cifrados del motor táctico quedan en:
- `~/storage/downloads/seal_reports/` si corriste `termux-setup-storage`
- `~/seal_reports/` si no (fallback automático, sin errores de permisos)

La base de datos SQLite del motor táctico vive en `~/seal_tactical.db`.
La llave de cifrado se genera una sola vez y se persiste en `~/.seal/tactical.key` (permisos 600) — así los reportes viejos siguen siendo legibles entre reinicios. Para usar una llave propia, exporta `SEAL_MASTER_KEY` antes de correr el script.

## Activar SEAL en el dashboard (opcional)

Si quieres que los endpoints de SEAL respondan desde el backend principal (puerto 8001, mismo proceso que el resto del dashboard), añade en `redteam/scripts/dashboard_server.py`, después de crear la instancia `app = FastAPI(...)`:

```python
from seal.api.seal_api_router import include_seal_routes
include_seal_routes(app)          # monta /api/devices, /api/scan, /api/alerts, etc.

from seal.core.tactical_engine import include_tactical_routes
include_tactical_routes(app)      # monta /api/seal/tactical/scan, /results, /health
```

Esto es **opcional y no se hace automáticamente** — así el dashboard nunca cambia de comportamiento sin que tú lo decidas explícitamente.

## Endpoints del motor táctico (`tactical_engine.py`)

| Método | Ruta | Función |
|--------|------|---------|
| POST | `/api/seal/tactical/scan?network=192.168.0.0/24` | Lanza auditoría completa en background |
| GET | `/api/seal/tactical/results` | Últimos 50 escaneos guardados |
| GET | `/api/seal/tactical/health` | Estado del motor (cifrado, DB) |

Namespaced bajo `/api/seal/tactical/*` para no chocar con `/api/scan`, `/api/health` ya usados por `seal_api_router.py`.

## Cambios de esta actualización (v2.1) respecto al documento original

1. **Eliminado el servidor FastAPI standalone en `port=8001`** — el documento original levantaba su propio `uvicorn.run(app, port=8001)`, que habría chocado directamente con `dashboard_server.py`. Ahora es un `APIRouter` que se monta opcionalmente, y el modo `--serve` standalone usa el puerto `8011` por defecto.
2. **Llave de cifrado persistente** — el original generaba una llave Fernet nueva en cada arranque si no había variable de entorno, lo que volvía ilegibles los reportes cifrados anteriores. Ahora se persiste en `~/.seal/tactical.key`.
3. **Fallback de directorio de reportes** — `~/storage/downloads/seal_reports` solo existe en Termux tras `termux-setup-storage`. Se agregó detección automática con fallback a `~/seal_reports` (mismo patrón usado para el fix de COMMANDER con `/tmp`).
4. **`datetime.utcnow()` → `datetime.now(timezone.utc)`** — la forma antigua está deprecada en Python 3.12+ (el que trae Termux/Replit actual).
5. **Namespacing de rutas** (`/api/seal/tactical/*`) para evitar colisión con las rutas ya existentes de `seal_api_router.py`.
6. **Modo CLI añadido** (`python3 -m seal.core.tactical_engine --network ...`) para uso directo en campo sin necesidad de FastAPI corriendo.
