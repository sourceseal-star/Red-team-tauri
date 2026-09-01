# SourceSeal Console — Estado del Proyecto

**Última actualización:** 2026-09-01
**Versión:** 7.0-TACTICAL-HOTRELOAD
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main
**Último commit:** feat(infra): motor táctico profesional con hot-reload + módulos + playbooks

---

## ✅ NOVEDADES (01-sep-2026)

### Motor Táctico Profesional con Hot-Reload
- **watcher.py** — Monitorea `redteam/modules/` cada 2s, sella cambios en ledger SourceSeal con chain hash SHA-256, envía SIGUSR1 al dashboard para recargar módulos sin reiniciar
- **hot_loader.py** — Carga módulos en caliente con handler SIGUSR1, detecta cambios por mtime

### 6 Módulos Nuevos
- `recon.py` — nmap, masscan, subfinder (red + host + subdominios + TCP connect fallback)
- `enumeration.py` — SMB, RPC, LDAP, NetBIOS (enum4linux, smbclient, rpcclient, nmblookup, ldapsearch)
- `vulnerability.py` — nikto, nuclei, sslscan con extracción automática de CVEs
- `exploitation.py` — PLANTILLA para validación de vulns (tú la llenas)
- `post.py` — PLANTILLA para post-explotación con evidencia
- `reporting.py` — Informes HTML sellados con SHA-256, badges de severidad, tabla de hallazgos

### Configuración Profesional
- `config/engagements.json` — Alcance autorizado por cliente
- `config/policies.json` — Acciones permitidas por rol y política
- `config/operators.json` — Roles: admin / reviewer / operator

### Playbooks
- `playbooks/external_pentest.json` — recon → enum → vuln → report
- `playbooks/internal_audit.json` — recon → enum → tactical → vuln → report
- `playbooks/webapp_test.json` — recon → nikto+nuclei → report

### Frontend
- **TacticalPanel.tsx** — Panel de auditoría táctica con botón "Ejecutar Auditoría"
  - Input de subnet (auto-detectar si vacío)
  - Log en vivo con timestamps
  - Stats cards: hosts, puertos, cámaras, creds, CVEs
  - Tabla de hallazgos con vendor, credenciales y CVEs
  - Descarga de reporte sellado HTML/JSON

---

## 🏗️ ARQUITECTURA ACTUAL (v7.0-TACTICAL-HOTRELOAD)

```
Red-team-tauri/
├── watcher.py                            # HOT-RELOAD: monitorea módulos, señaliza dashboard
├── config/
│   ├── engagements.json                  # Alcances autorizados por cliente
│   ├── policies.json                     # Políticas de acciones permitidas
│   └── operators.json                     # Roles: admin / reviewer / operator
├── redteam/
│   ├── runner/
│   │   ├── orchestrator.py                # Orquestador de playbooks
│   │   ├── hot_loader.py                  # HOT LOADER: SIGUSR1 recarga en caliente
│   │   └── engagement_guard.py           # Validación fail-closed de alcance
│   └── modules/
│       ├── __init__.py
│       ├── base.py                        # Clase base: sellado SHA-256 automático
│       ├── recon.py                       # nmap, masscan, subfinder
│       ├── enumeration.py                 # SMB, RPC, LDAP, NetBIOS
│       ├── vulnerability.py               # nikto, nuclei, sslscan + CVEs
│       ├── exploitation.py                # PLANTILLA (tú la llenas)
│       ├── post.py                        # PLANTILLA (tú la llenas)
│       ├── reporting.py                   # Informes HTML sellados
│       └── tactical_executor.py           # Ejecutor táctico integral
├── tauri-frontend/
│   └── src/components/TacticalPanel.tsx   # Panel de auditoría táctica
├── playbooks/
│   ├── external_pentest.json
│   ├── internal_audit.json
│   └── webapp_test.json
├── evidence/
│   ├── findings/                          # JSON de hallazgos sellados
│   └── sealed/                            # Informes sellados
├── reports/
│   └── templates/                         # Plantillas de reportes
├── redteam/scripts/dashboard_server.py    # Backend FastAPI :8001
├── arrancar.sh                            # Arranque Termux
├── replit_start.sh                        # Arranque Replit
└── replit.nix                             # Deps Nix
```

---

## ⚡ ARRANQUE RÁPIDO

### Opción 1: Termux (recomendado)
```bash
cd ~/Red-team-tauri
git stash && git pull origin main && git stash pop
bash arrancar.sh
```

### Opción 2: Replit
```bash
bash replit_start.sh
```

### Opción 3: Manual
```bash
cd ~/Red-team-tauri
git pull origin main
cd tauri-frontend && npm install && npm run build && cp -r dist/. ../public/
cd .. && python3 redteam/scripts/dashboard_server.py
```

→ http://localhost:8001

---

## 🔄 HOT-RELOAD (NUEVO)

El watcher monitorea módulos y recarga en caliente:

```bash
# Terminal 1: Dashboard
bash arrancar.sh

# Terminal 2: Watcher (background)
python3 watcher.py &

# Editar un módulo, ej:
nano redteam/modules/recon.py

# El watcher detecta el cambio automáticamente:
# 🔄 MODIFIED: recon.py (a1b2c3d4...)
# 🔗 Sellado en ledger SourceSeal
# 📡 Señal reload enviada al dashboard
# [HOT-LOADER] Recargando módulos...
# [HOT-LOADER] Cargado: recon.py
```

---

## 📡 ENDPOINTS TÁCTICOS

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/tactical/scan` | Ejecuta auditoría táctica completa |
| GET | `/api/tactical/report/{filename}` | Descarga informe sellado |
| GET | `/api/tactical/credentials` | Ver diccionario (conteo por vendor) |
| GET | `/api/tactical/ports` | Puertos por defecto escaneados |

---

## ⏳ PENDIENTES

1. **Probar en Termux** — `git pull && bash arrancar.sh`
2. **Probar hot-reload** — `python3 watcher.py &` y editar un módulo
3. **Probar TacticalPanel** — sidebar → "Auditoría Táctica" → "Ejecutar Auditoría"
4. **Configurar API Keys** — SHODAN_API_KEY y ABUSEIPDB_KEY en .env
5. **Implementar exploitation.py** — Llenar la plantilla con técnicas autorizadas
6. **Implementar post.py** — Llenar la plantilla con recolección de evidencia

## 🔑 PENDIENTES MANUALES (no urgentes)

1. Configurar keystore en GitHub Secrets (APK build)
2. Probar Integrity Check en producción
3. Migrar a Railway (siguiente fase)
4. Configurar dominio en Cloudflare

---

## 🚫 LEGACY (NO USAR)

- `server.js.deprecated` — viejo backend Node.js v1
- `backend/main.py.deprecated` — viejo backend Python v2
- `tauri-app-src/` — versión anterior del frontend
- `redteam-dashboard/` — versión paralela vieja del frontend
- `leviathan-frontend/` — versión paralela vieja del frontend LEVIATHAN

---

## 📝 CHANGELOG

- **v7.0** TACTICAL HOT-RELOAD (2026-09-01) — watcher, hot_loader, 6 módulos, configs, playbooks, TacticalPanel frontend
- **v6.0** LEVIATHAN IoT + Camera Batch (2026-08-25) — vendor detection, CVE DB, auto-access batch, grilla de cámaras
- **v5.0** ARTO + VPN (2026-08-19) — fixes de auth + WS + docs
- **v4.1** Topología + Traffic Analyzer (2026-08-18)
- **v4.0** OSINT Advanced + Interceptor Advanced (2026-08-14)
- **v3.0** Backend unificado Python/FastAPI (2026-08-10)
