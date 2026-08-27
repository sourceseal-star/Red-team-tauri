# 🦑 LEVIATHAN Dashboard v3.0 — Rediseño Completo

## Estructura

```
leviathan-frontend/
├── index.html                    # Entry point Vite
├── package.json                   # Dependencias (React 18, Vite 5, axios)
├── vite.config.js                 # Proxy → localhost:8001 (backend)
├── public/
│   └── index.html
└── src/
    ├── index.jsx                  # ReactDOM root
    ├── App.jsx                    # Router + Providers
    ├── components/
    │   ├── layout/
    │   │   ├── Layout.jsx          # Layout principal
    │   │   ├── SidebarCompact.jsx  # Sidebar plegable (70px ↔ 260px)
    │   │   ├── Topbar.jsx          # Barra superior con pestañas
    │   │   └── layout.css
    │   ├── widgets/
    │   │   ├── CameraDetection.jsx # Detección de cámaras IP
    │   │   ├── QuickScan.jsx       # Escaneo rápido de objetivos
    │   │   ├── ExploitWidget.jsx   # Explotación (KRAKEN/Cámara/Cadena)
    │   │   ├── AIAnalysis.jsx      # Análisis con IA
    │   │   ├── ThreatMap.jsx       # Mapa de amenazas
    │   │   ├── StatsWidget.jsx     # Estadísticas del sistema
    │   │   └── AlertCenter.jsx     # Centro de alertas
    │   ├── common/
    │   │   ├── Button.jsx, Card.jsx, Input.jsx, Modal.jsx, Badge.jsx
    │   └── icons/
    │       └── index.jsx
    ├── hooks/
    │   ├── useLeviathan.js         # Cliente API (22 endpoints)
    │   ├── useWebSocket.js         # WebSocket con reconexión auto
    │   └── useTheme.js             # 3 temas (leviathan/light/dark)
    ├── pages/
    │   ├── Dashboard.jsx           # Vista principal con widgets
    │   ├── DetectionPage.jsx       # Detección dedicada
    │   ├── AnalysisPage.jsx        # Análisis con IA
    │   ├── ExploitPage.jsx         # Explotación
    │   └── ReportsPage.jsx         # Reportes e historial
    └── styles/
        ├── index.css               # Estilos globales
        ├── theme.css               # Variables de tema
        └── widgets.css             # Estilos de widgets
```

## Instalación y Ejecución

### Opción A — Desarrollo (Termux/Local)

```bash
# 1. Entrar al directorio
cd leviathan-frontend

# 2. Instalar dependencias
npm install

# 3. Iniciar en modo desarrollo (puerto 3000)
npm run dev
```

El frontend se conecta automáticamente al backend en `localhost:8001`.

### Opción B — Build de producción

```bash
cd leviathan-frontend
npm install
npm run build    # Genera dist/
npm run preview   # Sirve el build en puerto 4173
```

### Backend requerido

El backend debe estar corriendo en el puerto **8001**:

```bash
# Desde la raíz del repo
python redteam/scripts/dashboard_server.py
# o
./replit_start.sh
```

El router de LEVIATHAN se monta automáticamente en `/api/leviathan/*` con 22 endpoints.

## Endpoints del Backend

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | /api/leviathan/status | Estado del sistema |
| GET | /api/leviathan/modules | Lista de módulos |
| POST | /api/leviathan/scan | Escaneo general |
| POST | /api/leviathan/scan/network | Escaneo de red |
| POST | /api/leviathan/scan/cameras | Escaneo de cámaras |
| POST | /api/leviathan/scan/quick | Escaneo rápido |
| POST | /api/leviathan/exploit | Explotación general |
| POST | /api/leviathan/exploit/camera | Explotar cámara |
| POST | /api/leviathan/exploit/chain | Explotación en cadena |
| POST | /api/leviathan/exploit/kraken | KRAKEN force |
| POST | /api/leviathan/analyze | Análisis IA general |
| POST | /api/leviathan/ai/analyze | Análisis comportamiento |
| POST | /api/leviathan/ai/detect | Detección de objetos |
| POST | /api/leviathan/report | Generar informe |
| POST | /api/leviathan/report/generate | Generar informe (alias) |
| GET | /api/leviathan/cameras | Cámaras detectadas |
| GET | /api/leviathan/scans | Historial de escaneos |
| GET | /api/leviathan/alerts | Alertas activas |
| GET | /api/leviathan/stats | Estadísticas agregadas |
| GET | /api/leviathan/threat-map | Datos del mapa de amenazas |
| GET | /api/leviathan/services | Servicios disponibles |
| GET | /api/leviathan/history | Historial completo |

WebSocket: `ws://localhost:8001/ws`

## Temas

Tres temas disponibles (cambiables desde el Topbar):
- **leviathan** — Oscuro con acentos púrpura (default)
- **dark** — Oscuro estándar
- **light** — Claro

## Notas

- El sistema degrada gracefully si faltan dependencias de IA (ultralytics/onnxruntime)
- Responsive: optimizado para pantallas de móvil/Termux
- El sidebar se pliega a 70px en pantallas pequeñas
