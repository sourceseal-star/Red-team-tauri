# SourceSeal Console — Estado del Proyecto

**Ultima actualizacion:** 2026-08-19
**Version:** 5.0-ARTO
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main
**Ultimo commit:** 73f3b89 (fix: ARTO auth headers + User-Agent field mismatch + WS endpoint)

---

## ✅ FIXES APLICADOS (19-ago-2026)

### Bug 1: ARTO 401 Unauthorized desde el frontend
- `artoApi.ts` NO enviaba `Authorization: Bearer` header
- **Fix:** Ahora importa `getApiKey()` y envía Bearer token en cada request
- También usa `getBaseUrl()` dinámico en vez de URL hardcodeada

### Bug 2: Interceptor "User-Agent" error 422
- Frontend enviaba `{"user_agent": "..."}` pero backend exigía `{"ua": "..."}`
- **Fix:** `UserAgentModel` ahora acepta ambos campos (opcionales) con `get_ua()`

### Bug 3: ARTO WebSocket nunca conectaba
- Conectaba a `/api/arto/ws` (no existe) — el WS real está en `/ws`
- **Fix:** `artoWebsocket.ts` ahora usa `/ws` con resolución dinámica de host

---

## 📦 NUEVOS ARCHIVOS (19-ago-2026)

1. **`quickstart.sh`** — Script de arranque + smoke tests automáticos
   - `bash quickstart.sh` → Instala deps, compila frontend, levanta backend, testea
   - `bash quickstart.sh --test-only` → Solo ejecuta smoke tests

2. **`README.md`** — Documentación completa actualizada con:
   - Arquitectura v5.0
   - 80+ endpoints documentados
   - Guías de arranque (Replit/Termux/Manual)
   - Solución de problemas
   - Smoke tests manuales con curl

---

## 🏗️ ARQUITECTURA ACTUAL (v5.0-ARTO)

```
Red-team-tauri/
├── redteam/scripts/dashboard_server.py  # Backend ÚNICO — FastAPI :8001
├── tauri-frontend/                        # Frontend ÚNICO — React/Vite/TS
│   ├── src/components/                    #   30+ componentes
│   ├── src/api/                           #   artoApi, interceptorApi, osintApi
│   └── dist/                             #   Build output
├── arto/                                  # ARTO AI (23 endpoints)
│   ├── api/arto_router.py
│   ├── core/ (5 motores AI)
│   ├── modules/ (attack_simulator, vpn, defense)
│   └── memory/ (SQLite + knowledge_base)
├── redteam/tlsproxy/                      # Interceptor MITM
│   ├── interceptor_advanced.py (12 endpoints)
│   └── interceptor_bridge.py (bridge v2)
├── redteam/osint/                         # OSINT advanced
├── backend/modules/enhanced_recon.py      # Reconocimiento de red
├── replit_start.sh                        # Arranque Replit
├── arrancar.sh                            # Arranque Termux
├── quickstart.sh                          # Arranque + tests (NUEVO)
└── replit.nix                             # Deps Nix (Replit)
```

---

## ⚡ ARRANQUE RÁPIDO

### Opción 1: Quickstart (recomendado)
```bash
bash quickstart.sh
```

### Opción 2: Replit
```bash
bash replit_start.sh
```

### Opción 3: Termux
```bash
bash arrancar.sh
```

### Opción 4: Manual
```bash
cd tauri-frontend && npm install --legacy-peer-deps && npm run build && cd ..
cd redteam/scripts && PORT=8001 python3 dashboard_server.py
```

→ http://localhost:8001

---

## ⏳ PENDIENTES

1. **Push a GitHub** — El commit 73f3b89 está hecho localmente pero el token expiró. Hacer `git push origin main` desde Replit.
2. **Rediseño de NetworkTopology.tsx** — Estilo mapa global (siguiente tarea)
3. **Test del proxy MITM con payloads reales** — Verificar captura + análisis
4. **Integración osint_advanced.py con backend** — Confirmar endpoints OSINT
5. **Verificar despliegue final en producción** — Replit autoscale

## 🔑 PENDIENTES MANUALES (no urgentes)

1. Configurar keystore en GitHub Secrets (APK build)
2. Probar Integrity Check en producción
3. Probar flujo de autodestrucción de sellos
4. Verificar build de APK después de reducir permisos

---

## 🚫 LEGACY (NO USAR)

- `server.js.deprecated` — viejo backend Node.js v1
- `backend/main.py.deprecated` — viejo backend Python v2
- `tauri-app-src/` — versión anterior del frontend
- `src/` — viejo Termux bridge Node.js

---

## 📝 CHANGELOG

- **v5.0** ARTO + VPN (2026-08-19) — fixes de auth + WS + docs
- **v4.1** Topología + Traffic Analyzer (2026-08-18)
- **v4.0** OSINT Advanced + Interceptor Advanced (2026-08-14)
- **v3.0** Backend unificado Python/FastAPI (2026-08-10)
