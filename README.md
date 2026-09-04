# SourceSeal — Ecosistema Red-team + Commander

Sistema de Seguridad ofensiva y defensiva para Termux (Android).

## Arquitectura

```
Red-team-tauri/
├── backend/dashboard_server.py   # FastAPI :8001 — Dashboard + AI Orchestrator + PHANTOM
├── nexus_omni_v9.py              # FastAPI :8004 — Nexus OSINT (red local, MAC, OUI)
├── ghost_hunter_phantom/         # :8002 — GHOST HUNTER distribuido (master + nodos)
├── commander/                     # AI Orchestrator + Seal IA Knowledge
│   ├── ai_orchestrator.py         # Motor de evolución autónoma
│   └── seal_ia_knowledge.py      # Ética, anti-extracción, identidad Seal IA
├── start_all.sh                   # Arranque completo (Dashboard + Nexus + PHANTOM + AI)
├── setup.sh                        # Instalación y sincronización (Termux)
└── arrancar.sh                    # Launcher seguro (delega a termux_recover.sh)
```

## Puertos

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| Dashboard | 8001 | FastAPI principal con Swagger en /docs |
| PHANTOM | 8002 | GHOST HUNTER master (orquestador de nodos) |
| Nexus | 8004 | OSINT de red local (MAC, OUI, hostname, geo) |

## Arranque rápido (Termux) — desde CERO

```bash
# En una Termux recién instalada, TRES comandos levantan la Torre completa:
pkg install git -y
git clone https://github.com/sourceseal-star/Red-team-tauri
bash Red-team-tauri/instalar_torre.sh
```

El instalador hace todo: herramientas base, clona los 3 repos (sol,
Red-team-tauri, commander), crea el .env SOLO si no existe (nunca
sobrescribe), sincroniza dependencias, levanta todo y verifica la cadena
completa con ~/sol/verificar_torre.sh.

## Gestión diaria — TODO pasa por omni.sh

```bash
cd ~/Red-team-tauri

bash omni.sh start        # Levanta TODO: Dashboard :8001, GHOST :8002, Nexus :8004,
                          # Sol ☀️ (daemon + puente Telegram + relé Termux⇄Replit) + watchdog
bash omni.sh stop         # Detiene todo limpio
bash omni.sh restart      # Stop + Start
bash omni.sh status       # Estado de todos los servicios
bash omni.sh sync         # git pull + deps + build (SIN tocar .env jamás)
bash omni.sh logs [serv]  # dash|ghost|tg|nexus|seal|all
bash omni.sh verify       # Verifica integridad de credenciales
```

Blindaje incluido: lock global (nunca dos omni.sh a la vez — evita puentes
Telegram duplicados), preflight de credenciales ANTES de arrancar, y
verificación de las llaves de Sol (SOL_PUBLIC_URL, SOL_API_KEY, LLM_API_KEY,
TELEGRAM_BOT_TOKEN) con aviso claro si falta alguna.

Los scripts legacy (setup.sh, start_all.sh, arrancar.sh) quedaron
reemplazados por omni.sh — no usarlos.

Verificación de punta a punta en un solo comando:
```bash
bash ~/sol/verificar_torre.sh
```

## AI Orchestrator

El AI Orchestrator (en `commander/ai_orchestrator.py`) ejecuta ciclos autónomos:

1. **Escanea** la red (nmap o fallback con socket)
2. **Piensa** — consulta al LLM (Claude/OpenAI) con el conocimiento de Seal IA
3. **Valida** — verifica confianza mínima y bloquea intentos de extracción
4. **Actúa** — ejecuta exploits, escaneos profundos, o genera reportes

### Configurar IA

```bash
export LLM_API_KEY="tu_clave"
export LLM_MODEL="claude-sonnet-4-20250514"
# Opcional:
export TARGET_NETWORK="192.168.1.0/24"
export MIN_CONFIDENCE="50"
```

### Endpoints del AI Orchestrator

```
GET  /api/commander/ai/status    # Estado: memoria, conocimiento, config
POST /api/commander/ai/cycle     # Ejecuta un ciclo (IA o modo offline)
POST /api/commander/ai/generate  # Genera código de explotación
GET  /api/commander/ai/history   # Historial de eventos
```

Todos requieren `X-Api-Key` con el valor de `REDTEAM_API_KEY`.

## GHOST HUNTER PHANTOM

Sistema distribuido de caza de dispositivos IoT y cámaras.

```bash
# Lanzar caza
curl -X POST http://localhost:8002/api/hunt/start \
  -H "Content-Type: application/json" \
  -d '{"query":"Hikvision port:554","playbook":"hikvision","max_results":50}'
```

Ver hallazgos: `GET /api/phantom/alerts` en el Dashboard.

## Sol — Cerebro accesible desde el dashboard

Sol tiene 3 endpoints en el backend para que el SolWidget (War Room) y FloatingSol funcionen:

| Método | Path | Descripción |
|---|---|---|
| POST | `/api/sol/think` | Procesar mensaje con Sol (body: `{"message": "..."}`) |
| GET | `/api/sol/last-message` | Último mensaje de Sol |
| GET | `/api/sol/status` | Estado del cerebro (online/offline) |

El cerebro de Sol (`sol_core.py`) funciona offline sin internet y responde en español.

## Telegram

```bash
export TELEGRAM_BOT_TOKEN="tu_token"
export TELEGRAM_CHAT_ID="tu_chat_id"
```

Notifica al iniciar `start_all.sh`.

## Auth

El backend requiere `REDTEAM_API_KEY` en todas las rutas de escaneo.

```bash
export REDTEAM_API_KEY="tu-clave-secreta"
```

Sin esta variable, el backend bloquea las rutas protegidas.

## Sync de repos

```bash
bash setup.sh              # Sincroniza Red-team + Commander via SSH
bash setup.sh --unified    # Sync + inicia stack unificado
bash setup.sh --watch      # Sync + watcher en segundo plano
```
