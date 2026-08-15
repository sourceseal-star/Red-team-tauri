# SourceSeal Console Pro — Centro de Control

Dashboard de operaciones de seguridad ofensiva y defensiva. El flujo activo en Replit
es el dashboard unificado de `Red-team-tauri`; el APK y el Motor de Cierre quedan
fuera de este flujo por ahora.

## Cómo ejecutar

```bash
bash replit_start.sh
```

El workflow **SourceSeal Dashboard** arranca automáticamente el backend y sirve el
frontend compilado en el puerto **8001**.

Health check:

```bash
curl http://localhost:8001/api/health
```

## Estructura principal

```
redteam/
└── scripts/dashboard_server.py   # Backend unificado FastAPI :8001
tauri-frontend/
├── src/                          # React + TypeScript
└── dist/                         # Frontend generado para el backend
backend/modules/                  # Reconocimiento real complementario
```

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `8001` | Puerto HTTP del dashboard |
| `REDTEAM_API_KEY` | local-dev-token | Clave para endpoints protegidos |
| `CORSET_SCOPE_B64` | — | Alcance autorizado de escaneo; recomendado |
| `SHODAN_API_KEY` | — | Intel Shodan, si se desea habilitar |

El backend informa explícitamente cuando faltan servicios o claves opcionales; no
rellena resultados con datos simulados. Para operar escaneos reales, define un
alcance autorizado mediante `CORSET_SCOPE_B64` y configura únicamente las claves
de servicios externos que vayas a utilizar.

El flujo de APK no forma parte de la puesta en marcha actual.

## User preferences

- Idioma de comunicación: español