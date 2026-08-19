# Red-Team-Tauri / SourceSeal Console v5.0

Sistema de operaciones de red team con ARTO (AI autónomo) + VPN interceptor.

## Arranque rápido

### Termux (Android)
```bash
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri
bash arrancar.sh
```

### Replit
```bash
bash replit_start.sh
```

## Componentes

- **Backend**: FastAPI en puerto 8001 (unificado)
- **Frontend**: React/Vite compilado a `dist/`
- **ARTO**: Sistema AI autónomo (29 archivos Python)
- **VPN**: Captura de tráfico via Android VpnService (sin root)
- **Módulos**: enhanced_recon, interceptor, OSINT advanced, honeypot

## Estructura

```
Red-team-tauri/
├── redteam/scripts/     # Backend FastAPI (dashboard_server.py)
├── backend/modules/     # enhanced_recon, OSINT, interceptor
├── arto/                # Sistema ARTO (AI autónomo)
│   ├── core/            # 5 motores AI
│   ├── modules/         # attack_simulator, vpn_interceptor, defense
│   ├── memory/          # SQLite + knowledge_base
│   ├── utils/           # threat_intel, risk, anomaly
│   ├── api/             # Router FastAPI (23 endpoints)
│   └── models/          # Modelos de datos
├── tauri-frontend/      # Frontend React/Vite
├── android/             # VpnService Java (Tauri)
└── scripts/             # Deploy scripts
```

## Documentación

- [MANUAL_OPERATIVO.md](MANUAL_OPERATIVO.md) — Manual completo
- Endpoints ARTO: `/api/arto/*`
- Health check: `/api/health`

## Changelog

- **v5.0** ARTO + VPN (2026-08-19) — commits d0f7251, 9a63de4, d63dba2
- **v4.1** Topología + Traffic Analyzer (2026-08-18)
- **v4.0** OSINT Advanced + Interceptor Advanced (2026-08-14)
