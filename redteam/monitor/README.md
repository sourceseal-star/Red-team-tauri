# SourceSeal Operations Monitor

Monitor administrativo seguro integrado en el backend unificado de SourceSeal.

## Endpoints

Todos los endpoints están protegidos por la autenticación global del dashboard:

- `GET /api/operations/status` — estado del monitor, métricas y capacidades.
- `GET /api/operations/repos` — estado de lectura de `Red-team-tauri` y `commander`.
- `GET /api/operations/audit?limit=50` — eventos recientes y hash de la cadena.
- `POST /api/operations/audit` — registra un evento administrativo no operativo.

El módulo no recibe comandos de Telegram, no ejecuta shell arbitrario, no mata
procesos, no cambia interfaces de red y no hace `pull`, `push`, `deploy` ni
sincronizaciones automáticas. Los comandos Git usados internamente son de
lectura y se ejecutan con `shell=False`.

El ledger se guarda por defecto en `~/.sourceseal/operations_audit.jsonl`.
Puede cambiarse con `SOURCESEAL_OPERATIONS_AUDIT`.