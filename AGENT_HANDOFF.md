# AGENT_HANDOFF — Libro de Obras del Ecosistema SourceSeal

> Registro cronológico de obras realizadas por el agente en el repositorio.
> Cada entrada: fecha, commit, descripción, archivos afectados.

---

## 2026-09-01 — Seal IA en Telegram v2 (async, custodia, reporte entregable)

**Commit:** `feat: Seal IA en Telegram v2 — async, custodia y reporte entregable`

**Descripción:**
Implementación del poller de Telegram que expone Seal IA como interfaz conversacional
y operativa. Escaneos asíncronos con candado global, entrega de reportes HTML con hash
SHA-256 en el caption, cadena de custodia (ledger), memoria conversacional, cambio de
alcance con confirmación de 30s, y texto listo para reenviar al cliente.

**Archivos creados:**
- `sol_telegram_bridge.py` — poller completo con todos los comandos
- `AGENT_HANDOFF.md` — este libro de obras

**Archivos modificados:**
- `.env.example` — añadida `TELEGRAM_ALLOWED_USERS`
- `MANUAL_OPERACIONES.md` — sección 10 "Telegram = Interfaz de Seal IA"

**Arquitectura:**
- Poller de long-polling de Telegram (getUpdates, offset incremental)
- Whitelist de user_ids (`TELEGRAM_ALLOWED_USERS` o chat_id default)
- `SCAN_LOCK` (threading.Lock) — un solo escaneo a la vez
- Escaneos en thread daemon → Telegram no se bloquea
- Ledger local en `~/.sourceseal/seal_ledger.json` (cadena SHA-256)
- Memoria en `~/.sourceseal/seal_chat.json` (últimos 16 mensajes)
- Reportes HTML en `reports/reporte_*.html` con stats y tabla de dispositivos
- Modo offline (reflejos tácticos) y modo LLM (Anthropic con seal_ia_knowledge.py)

**Comandos implementados:**
`/seal`, `/seal status`, `/seal scan`, `/seal ultimo`, `/reporte`,
`/engagement`, `/engagement set`, `/chain`, `/cliente`, texto libre.

---

## 2026-09-01 — Seal IA integrada al ecosistema (healthcheck + Telegram + manual)

**Commit:** `feat: Seal IA integrada al ecosistema (healthcheck+Telegram+manual)`

**Descripción:**
Integración de Seal IA al ecosistema existente: healthcheck, script puente de Telegram,
manual de operaciones y variables de entorno documentadas.

**Archivos creados:**
- `scripts/seal_telegram_cmd.sh` — puente /seal (ejecuta --status, máx 500 chars)

**Archivos modificados:**
- `.env.example` — `SEAL_NETWORK`, `SEAL_ENABLED`, `LLM_API_KEY`
- `iniciar_unificado.sh` — sección 7 Seal IA (arranca si SEAL_ENABLED=1)
- `scripts/healthcheck_all.sh` — check SEAL IA via --status
- `MANUAL_OPERACIONES.md` — sección 9 completa + mapa de puertos actualizado

---

## 2026-08-31 — NEXUS autoscan + Commander alineado + Frontend servido

**Commit:** `feat: nexus autoscan+mapa, commander alineado, frontend servido por backend completo`

**Descripción:**
NEXUS autoscan con nmap, rutas API para mapa de hosts, alineación de 24 rutas
frontend↔backend, y verificación de build del frontend servido por el backend.

**Archivos creados:**
- `nexus_autoscan.py` — módulo de escaneo automático

**Archivos modificados:**
- `nexus_omni_v9.py` — 2 rutas nuevas (GET /api/nexus/hosts, POST /api/nexus/scan/now)
- `.env.example` — `NEXUS_SCAN_TARGET`
