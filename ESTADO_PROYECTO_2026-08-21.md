# Estado del Proyecto — Red-Team-Tauri / SourceSeal Console
**Fecha:** 2026-08-21
**Versión:** v6.0 — ARTO + LEVIATHAN UNIFIED
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main
**Backend único:** `redteam/scripts/dashboard_server.py` (FastAPI :8001)

---

## ✅ SISTEMA ACTUAL

### Backend (FastAPI)
- **Archivo:** `redteam/scripts/dashboard_server.py` (5600+ líneas, 154+ endpoints)
- **Puerto:** 8001
- **Sin bloqueos:** middleware de 20s previene congelamiento
- **Sin mocks:** solo datos reales
- **Incluye:** OSINT + ARTO + SEAL + LEVIATHAN + ThreatIntel + WebSocket + Reports

> ⚠️ `backend/dashboard_server.py` es una versión anterior/paralela — NO usar.
> `source_seal_backend_v3.py` es legacy — NO usar.

### Frontend (React + Vite + TypeScript)
- **Build:** `cd tauri-frontend && npm run build` → dist/
- **Dev:** `npm run dev` → :5000 con proxy a :8001
- **30+ componentes:** NetworkTopology, TrafficMonitor, ARTOPanel, SealPanel, WarRoom, etc.

### Sistemas integrados
- **ARTO** — AI autónomo (23 endpoints, 5 motores AI, VPN interceptor)
- **SEAL** — Super Pack v2.1 (network sweep, hikvision, ONVIF, fingerprint)
- **LEVIATHAN** — v3.1 módulos Red Team (scanners, exploiters, AI, reporters)
- **KRAKEN** — v3.0 motor de explotación (independiente)
- **OSINT** — Advanced (Shodan, AbuseIPDB, WHOIS, DNS, Google, VirusTotal)
- **Interceptor** — MITM (SQLi, XSS, XXE, LFI, SSRF, LDAP, NoSQL detection)
- **Honeypot** + canary tokens
- **Gateway Mesh** — federación entre dispositivos (opcional)

---

## ⚡ ARRANQUE RÁPIDO

### Termux (Android) — recomendado
```bash
bash arrancar.sh
```

### Replit
```bash
bash replit_start.sh
```

### Con smoke tests
```bash
bash quickstart.sh
```

### Manual
```bash
cd tauri-frontend && npm install --legacy-peer-deps && npm run build && cd ..
cd redteam/scripts
export PORT=8001 HOST=0.0.0.0
python3 dashboard_server.py
```

→ http://localhost:8001

---

## 🔑 API KEYS (.env)

```bash
ABUSEIPDB_KEY=tu-key       # https://www.abuseipdb.com/account/api (gratis)
SHODAN_API_KEY=tu-key      # https://www.shodan.io/dashboard (gratis)
HUNTER_API_KEY=tu-key      # https://hunter.io/api-keys (opcional)
```

> ⚠️ La variable es `ABUSEIPDB_KEY` (sin `_API`).

---

## ❌ Google Play Protect bloquea la APK

### Causa raíz
1. Permisos peligrosos (`shell:allow-spawn`, `shell:allow-execute`)
2. Firma de debug o auto-firmada (no keystore real)
3. `com.sourceseal.console` no registrado en Play Store
4. Tauri WebView + shell permissions = patrón de malware
5. CSP null en `tauri.conf.json`
6. Código de escaneo de red y exploits dispara detectores

### Soluciones (por prioridad)
1. **Firmar con keystore consistente** — ver `SETUP_FIRMA_APK.md`
2. **Reducir permisos shell** en `src-tauri/capabilities/default.json`
3. **Habilitar CSP** en `src-tauri/tauri.conf.json`
4. **Cambiar identifier** a algo menos sospechoso
5. **Subir a Play Store como Internal Testing**
6. **Pedir revisión manual** a Google Play Protect

---

## 📋 PENDIENTES

1. Configurar keystore en GitHub Secrets (APK build)
2. Reducir permisos shell en `src-tauri/capabilities/default.json`
3. Habilitar CSP en `tauri.conf.json`
4. Probar Integrity Check en producción
5. Probar flujo de autodestrucción de sellos
6. Verificar build de APK con permisos reducidos

---

## 🚫 LEGACY (NO USAR)

- `source_seal_backend_v3.py` — viejo orquestador v3.0
- `server.js.deprecated` — viejo backend Node.js v1
- `backend/main.py.deprecated` — viejo backend Python v2
- `tauri-app-src/` — versión anterior del frontend
- `src/` — viejo Termux bridge Node.js

---

## 📝 CHANGELOG RECIENTE

- **v6.0** LEVIATHAN UNIFIED (2026-08-21) — router /api/v1/* + ONNX + profiles.json
- **v5.0** ARTO + VPN (2026-08-19) — fixes de auth + WS + docs
- **v4.1** Topología + Traffic Analyzer (2026-08-18)
- **v4.0** OSINT Advanced + Interceptor Advanced (2026-08-14)
- **v3.0** Backend unificado Python/FastAPI (2026-08-10)

---

*Manuales relacionados: `MANUAL_OPERATIVO.md` (completo), `GUIA_ARRANQUE.md` (rápido), `MANUAL_DESPLIEGUE.md` (despliegue)*
