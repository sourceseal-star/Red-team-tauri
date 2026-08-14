# SourceSeal Console — Estado del Proyecto

**Ultima actualizacion:** 2026-08-07
**Version:** 3.0-unified
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main

---

## Arquitectura actual (v3.0-unified)

```
Red-team-tauri/
├── redteam/scripts/dashboard_server.py  # Backend UNICO — FastAPI :8001 (1155+ lineas)
├── tauri-frontend/                        # Frontend UNICO — Vite + React + TypeScript
│   ├── src/                              # 37 archivos .tsx/.ts
│   ├── package.json                      # dev: vite --port 5000, build: tsc && vite build
│   └── vite.config.ts                    # proxy /api → :8001
├── redteam/                              # Python Red Team toolkit (XDR, RASP, NDR, SOAR, etc.)
│   ├── runner/orchestrator.py            # Orchestrator de escenarios
│   ├── scenarios/                        # 13 escenarios de ataque
│   ├── honeypot/                         # Honeypot + fake-api + c2-sinkhole + network-ids
│   ├── xdr/                              # XDR correlator
│   ├── ndr/                              # NDR engine
│   ├── rasp/                             # RASP attestation
│   ├── soar/                             # SOAR engine + playbooks
│   ├── deception/                        # Deception mesh + canary
│   ├── monitor/                          # Canary monitor
│   ├── ztna/                             # ZTNA gateway
│   ├── tip/                             # Threat Intel Platform
│   └── geo_intel.py                      # Geo/Intel lookup
├── src-tauri/                            # Tauri desktop (Rust) — wrapper nativo
├── replit_start.sh                       # Arranque Replit (backend + frontend build)
├── start-termux.sh                       # Arranque Termux (backend + vite dev)
└── .replit                               # Config Replit (puerto 8001 → 3001)
```

## Backend: redteam/scripts/dashboard_server.py (v3.0-unified)

- FastAPI en puerto 8001 — sirve API + WebSocket + dist/ estatico
- 73+ endpoints: scan, services, honeypot, canary, SOAR, TIP, RASP, terminal, etc.
- Sin mocks. Sin dummy data. Solo datos reales.
- 11 servicios gestionables (xdr, ndr, rasp, soar, ztna, deception, fake-api, c2-sinkhole, canary-monitor, network-ids)
- Orchestrator ejecuta 13 escenarios de ataque
- Health check: GET /api/health → version=3.0-unified

## Frontend: tauri-frontend/ (React + TypeScript)

- Vite + React 18 + TypeScript + Tailwind + Zustand + Recharts
- 12 rutas: Dashboard, Config, Reports, Honeypot, SOAR, TIP, Geo, RASP, Terminal, Settings, About
- Build: `cd tauri-frontend && npm run build` → dist/ (servido por backend)
- Dev: `npm run dev` → :5000 con proxy a :8001

## Como arrancar

### Replit
```bash
bash replit_start.sh
```

### Termux
```bash
bash start-termux.sh
```

### Manual
```bash
# Frontend build
cd tauri-frontend && npm install && npm run build
# Backend
cd redteam/scripts && PORT=8001 python3 dashboard_server.py
# → http://localhost:8001
```

## Codigo legacy (NO usar)

- `server.js.deprecated` — viejo backend Node.js v1 (80KB)
- `backend/main.py.deprecated` — viejo backend Python v2 (41KB)
- `tauri-app-src/` — version anterior del frontend (7 archivos)
- `src/` — viejo Termux bridge Node.js
- `build/` — copia de build antigua
