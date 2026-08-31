# SourceSeal Console — Estado del Proyecto

**Ultima actualizacion:** 2026-08-30
**Version:** 6.1-LEVIATHAN-IoT-PHANTOM
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main
**Ultimo commit:** 4433bf7 (fix phantom node endpoints + launcher unificado) (feat: grilla de camaras batch con thumbnails + CVEs + stream)

---

## ✅ FIXES APLICADOS (25-ago-2026)

### Build frontend no-fatal (commit 14a1242)
- `set -e` + `npm run build | tail -5` + `cp -r dist/.` mataba el script si el build fallaba
- Ahora: `FRONTEND_BUILD_OK` flag, si falla usa dist/ existente, el backend SIEMPRE arranca

### Camaras: proxy MJPEG real (commit 0f64ecd)
- `/api/iot/stream` devolvia 501 → ahora proxy MJPEG con StreamingResponse
- `/api/iot/snapshot` probaba 1 path sin auth → ahora 11 paths + auth basico
- Soporta credenciales via query params (user/pwd)

### Frontend: fallback MJPEG (commit 7fad54c)
- Si snapshot falla, carga stream MJPEG automaticamente

### OSINT: 0 POSTs, todos los endpoints correctos (commits 354ab20, d5b8588, 058505b, 4aefa7d)
- `osintApi.ts` llamaba `/api/osint/v2/*` (no existe) → `/api/osint/*`
- 8 endpoints del OSINTAdvancedPanel corregidos (email, subdomains, search, threat, shodan, headers, virustotal, censys, social, dns)
- 0 POSTs restantes en todo el panel

### IoT: vendor detection + CVE DB + default creds (commit 4c00156)
- 7 fabricantes con CVEs: Hikvision(3), Dahua(3), Xiongmai(2), D-Link(2), Netgear(1), GoAhead(1), Ubiquiti(1)
- 23 credenciales por defecto probadas automaticamente
- RTSP paths especificos por vendor
- `_identify_camera_vendor()` detecta por Server header + HTML paths

### IoT: auto-access orquestado (commit 7bd0096)
- `GET /api/iot/auto-access?ip=X&port=Y` — vendor → CVEs → creds → snapshot → stream en 1 llamado
- `POST /api/iot/auto-access-batch` — escanea red CIDR entera, procesa todas las camaras
- 8 camaras en paralelo, devuelve resumen con full/partial/no_access

### Frontend: grilla batch de camaras (commit 7e45001)
- Boton "Escanear Todo" morado en CameraCommandCenter
- Grilla responsiva (2-5 columnas) con thumbnails, badges LIVE/DATA/OFF
- CVEs mostrados, credenciales, link directo al stream

---

## 🏗️ ARQUITECTURA ACTUAL (v6.0-LEVIATHAN-IoT)

```
Red-team-tauri/
├── redteam/scripts/dashboard_server.py  # Backend UNICO — FastAPI :8001
├── tauri-frontend/                        # Frontend UNICO — React/Vite/TS
│   ├── src/components/                    #   51 componentes
│   ├── src/api/                           #   artoApi, interceptorApi, osintApi
│   └── dist/                             #   Build output
├── leviathan_core/                        # LEVIATHAN v3.0 (31+ archivos)
│   ├── api/
│   │   ├── leviathan_router.py            # /api/leviathan/*
│   │   └── integration_router.py          # /api/v1/* (unificado)
│   ├── config/profiles.json
│   ├── modules/scanners/ (6)
│   ├── modules/exploiters/ (5)
│   ├── modules/ai_analyzers/ (4)
│   └── modules/reporters/ (3)
├── arto/                                  # ARTO AI (23 endpoints)
├── seal/                                  # SEAL SUPER PACK v2.0
├── kraken/                                # KRAKEN v3.0 (56 archivos)
├── replit_start.sh                        # Arranque Replit
├── arrancar.sh                            # Arranque Termux (build no-fatal)
└── replit.nix                             # Deps Nix (onnxruntime, pillow, pyyaml)
```

---

## ⚡ ARRANQUE RAPIDO

### Termux (recomendado)
```bash
cd ~/Red-team-tauri
bash arrancar_termux.sh
```

Para preparar o actualizar ambos repositorios de forma segura:

```bash
bash termux_recover.sh
```

### Replit
```bash
bash replit_start.sh
```

→ http://localhost:8001

---

## 📡 ENDPOINTS IoT NUEVOS

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| GET | `/api/iot/vulns?ip=X&port=Y` | Vendor + CVEs + creds + URLs |
| GET | `/api/iot/auto-access?ip=X&port=Y` | Orquestacion completa en 1 llamado |
| POST | `/api/iot/auto-access-batch` | Escanea red CIDR, procesa todas las camaras |
| GET | `/api/iot/snapshot?ip=X&port=Y&user=U&pwd=P` | Snapshot con 11 paths + auth |
| GET | `/api/iot/stream?ip=X&port=Y&path=P&user=U&pwd=P` | Proxy MJPEG en vivo |

---

## ⏳ PENDIENTES

1. **Probar en Termux** — `bash arrancar_termux.sh` y verificar:
   - El frontend compila (revisar output de npm run build)
   - El sidebar muestra LEVIATHAN, ARTO, SEAL, IoT, OSINT
   - El boton "Escanear Todo" en Camaras funciona
   - GHOST PHANTOM arranca en :8002 (ver logs)
2. **Probar PHANTOM** — `curl http://localhost:8002/api/status` despues de arrancar
3. **Configurar API Keys** — SHODAN_API_KEY y ABUSEIPDB_KEY en .env
4. **Verificar camara** — Probar `/api/iot/auto-access?ip=IP&port=80` con la camara real
5. **Probar caza PHANTOM** — `POST :8002/api/hunt/start` con playbook hikvision

## 🔑 PENDIENTES MANUALES (no urgentes)

1. Configurar keystore en GitHub Secrets (APK build)
2. Probar Integrity Check en produccion
3. Migrar a Railway (siguiente fase)
4. Configurar dominio en Cloudflare

---

## 🚫 LEGACY (NO USAR)

- `server.js.deprecated` — viejo backend Node.js v1
- `backend/main.py.deprecated` — viejo backend Python v2
- `tauri-app-src/` — version anterior del frontend
- `redteam-dashboard/` — version paralela vieja del frontend
- `leviathan-frontend/` — version paralela vieja del frontend LEVIATHAN

---

## 📝 CHANGELOG

- **v6.1** PHANTOM + Launcher Unificado (2026-08-26) — node.py fix, start.sh sin set-e, iniciar_unificado.sh, arrancar.sh con phantom
- **v6.0** LEVIATHAN IoT + Camera Batch (2026-08-25) — vendor detection, CVE DB, auto-access batch, grilla de camaras — vendor detection, CVE DB, auto-access batch, grilla de camaras
- **v5.0** ARTO + VPN (2026-08-19) — fixes de auth + WS + docs
- **v4.1** Topologia + Traffic Analyzer (2026-08-18)
- **v4.0** OSINT Advanced + Interceptor Advanced (2026-08-14)
- **v3.0** Backend unificado Python/FastAPI (2026-08-10)
