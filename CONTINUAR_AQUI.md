# SourceSeal Console — Estado del Proyecto

**Ultima actualizacion:** 2026-08-14
**Version:** 4.0-unified
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main
**Ultimo commit:** eebc43b (optimizacion endpoints + middleware anti-bloqueo)

---

## Ver documento completo de estado

**`ESTADO_PROYECTO_2026-08-14.md`** — Diagnostico Play Protect, cambios realizados, pendientes.

---

## Pendientes prioritarios (siguiente sesion)

### ✅ RESUELTOS (18-ago-2026)
1. ~~Configurar keystore en GitHub Secrets~~ — PENDIENTE MANUAL
2. ~~Reducir permisos shell~~ — HECHO (solo core:default + shell:allow-open)
3. ~~Habilitar CSP~~ — HECHO (CSP real configurado)
4. ~~Cambiar identifier~~ — HECHO (com.sourceseal.securityconsole)
5. ~~Integrar módulos v4.0~~ — HECHO (OSINT + Interceptor conectados a redteam/scripts/dashboard_server.py)
6. ~~Deps Python v4.0~~ — HECHO (dnspython, beautifulsoup4, python-whois en replit.nix + start-termux.sh)
7. ~~i18n dashboard~~ — HECHO (ES/ZH/EN con selector, módulos nuevos en chino simplificado)

### ⏳ PENDIENTES
1. **Configurar keystore en GitHub Secrets** — KEYSTORE_BASE64, KEY_ALIAS, STORE_PASSWORD, KEY_PASSWORD
2. **Probar Integrity Check en produccion**
3. **Probar flujo de autodestruccion de sellos**
4. **Verificar build de APK** despues de reducir permisos
5. **Probar en Termux** — bash start-termux.sh
6. **Probar en Replit** — bash replit_start.sh

## Cambios ya hechos (commit eebc43b, en GitHub)

- /api/network/radio: 2min → 4s (paralelizado)
- /api/enhanced/discover/all: bloqueo total → 13s con respuesta parcial
- Middleware: timeout 20s en todos los endpoints (504 si se cuelga, server sigue vivo)
- Todas las funciones bloqueantes movidas a thread pool

## Arquitectura actual (v4.0-unified)

```
Red-team-tauri/
├── redteam/scripts/dashboard_server.py  # Backend UNICO — FastAPI :8001
├── backend/modules/enhanced_recon.py    # Reconocimiento de red optimizado
├── tauri-frontend/                        # Frontend UNICO — Vite + React + TypeScript
│   ├── src/                              # 37 archivos .tsx/.ts
│   ├── package.json                      # dev: vite --port 5000, build: tsc && vite build
│   └── vite.config.ts                    # proxy /api → :8001
├── redteam/                              # Python Red Team toolkit
├── src-tauri/                            # Tauri desktop (Rust) — wrapper nativo
├── .github/workflows/build-android.yml  # Build APK automático
└── SETUP_FIRMA_APK.md                    # Instrucciones firma APK
```

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
cd tauri-frontend && npm install --legacy-peer-deps && npm run build
cd redteam/scripts && PORT=8001 python3 dashboard_server.py
# → http://localhost:8001
```

## Codigo legacy (NO usar)
- `server.js.deprecated` — viejo backend Node.js v1
- `backend/main.py.deprecated` — viejo backend Python v2
- `tauri-app-src/` — version anterior del frontend
- `src/` — viejo Termux bridge Node.js
