# SourceSeal Console Pro — Estado del Proyecto

**Ultima actualizacion:** 2026-08-01
**Version:** 2.0.0+20 (Pro)
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main

---

## Lo que YA esta hecho (v2.0.0 Pro)

### Backend Python (backend/main.py — 41KB)
- [x] FastAPI server con 17 endpoints REST + WebSocket
- [x] Port Scanner (TCP SYN/Connect, UDP, banner, service detection)
- [x] WiFi Scanner (network discovery, security, signal, WPS)
- [x] Camera Scanner (Hikvision, Dahua, Axis, Foscam, Avigilon)
- [x] Radio Scanner (FM/AM/Digital)
- [x] IoT Scanner (MQTT, CoAP, ZigBEE, BLE, WiFi)
- [x] Network Topology Mapper
- [x] C2 Manager (sessions, commands, WebSocket)
- [x] Exploit Framework (8 CVEs: EternalBlue, Log4Shell, Hikvision, etc.)
- [x] OSINT (Shodan, WHOIS)
- [x] Report Generator (executive, technical, compliance)
- [x] CORS habilitado para Flutter
- [x] ThreadPoolExecutor (50 workers)
- [x] Requirements: fastapi, uvicorn, python-nmap, python-whois, websockets

### Flutter App (lib/ — 30 archivos Dart)
- [x] main.dart — entry point con theme + router
- [x] core/ — constants, theme (dark cyber), router (go_router), errors, extensions
- [x] features/dashboard/ — dashboard screen + cards + stats + recent activity
- [x] features/wifi/ — WiFi scan screen + security card + signal chart (fl_chart)
- [x] features/topology/ — topology screen + host detail sheet + graph (graphview)
- [x] features/scanner/ — scanner, camera scan, IoT scan, radio scan screens
- [x] features/c2/ — C2 session management screen
- [x] features/recon/ — reconnaissance screen
- [x] features/report/ — report list + detail screens
- [x] services/ — api_service (Dio), secure_storage, websocket
- [x] pubspec.yaml — 50+ dependencias (flutter_bloc, dio, go_router, fl_chart, etc.)

### Assets
- [x] assets/config/config.json
- [x] assets/images/ (splash_logo, app_icon — placeholders)
- [x] assets/fonts/ (.gitkeep — necesita fuentes reales JetBrainsMono + Inter)

### Scripts
- [x] scripts/install_replit.sh — auto-deteccion de URL, sed de config, start backend
- [x] scripts/install_termux.sh — full setup: pkg update, flutter, clone, build APK

### Infraestructura existente (Tauri — version anterior)
- [x] src-tauri/ — Cargo.toml, tauri.conf.json (desktop app Rust)
- [x] tauri-frontend/ — Vite + TypeScript + Tailwind (frontend anterior)
- [x] lib/ — archivos .js del Tauri anterior (coexisten con .dart)
- [x] server.js — backend Node.js anterior (65KB)
- [x] redteam/ — Python Red Team toolkit completo (XDR, RASP, NDR, SOAR, etc.)

---

## Lo que FALTA

### Flutter
- [ ] **Fuentes reales** — Descargar JetBrainsMono y Inter TTF, subir a assets/fonts/
- [ ] **flutter pub get** — Instalar dependencias (requiere Flutter SDK)
- [ ] **flutter build apk** — Compilar APK (requiere Android SDK o Termux)
- [ ] **flutter build web** — Compilar web (para Replit)
- [ ] **Splash screen real** — Reemplazar placeholder con logo real
- [ ] **App icon real** — Reemplazar placeholder con icono real

### Backend
- [ ] **WHOIS** — Funciona con python-whois pero requiere acceso a puerto 43 (bloqueado en algunos sandboxes)
- [ ] **Nmap** — Requiere nmap instalado en el sistema (no solo la lib Python)
- [ ] **Persistencia** — Los resultados de scan estan en memoria (se pierden al reiniciar)

### Deploy
- [ ] **Replit** — Ejecutar `bash scripts/install_replit.sh` (detecta URL automatica)
- [ ] **Termux** — Ejecutar `bash scripts/install_termux.sh` (instala Flutter + build APK)
- [ ] **Docker** — No hay Dockerfile para el backend (podria agregarse)

---

## Como continuar

### 1. Backend local (ya funcionando)
```bash
cd backend
pip install -r requirements.txt
python main.py
# API: http://localhost:8000
# Swagger: http://localhost:8000/docs
```

### 2. Flutter app
```bash
flutter pub get
flutter run  # debug
flutter build apk --release  # APK
flutter build web  # web
```

### 3. Replit
```bash
bash scripts/install_replit.sh
```

### 4. Termux
```bash
bash scripts/install_termux.sh   # instalación completa (una sola vez)
bash start-termux.sh             # arrancar backend actual (Python FastAPI, puerto 8000)
```

⚠️ **IMPORTANTE — 3 generaciones de código coexisten en este repo:**
- `backend/main.py` + `lib/` (Flutter) → **ACTUAL**, v2.0.0 Pro. Arranca con `start-termux.sh`.
- `server.js` + `tauri-frontend/` → LEGACY (v1, Node.js). Arranca con `start-termux-legacy-nodejs.sh`. NO es el backend que debes usar salvo que sepas específicamente que lo necesitas.
- `redteam/` → toolkit paralelo (XDR/NDR/RASP/SOAR), proyecto distinto, incluso referencia otro repo de GitHub (`Red-team`, sin `-tauri`). No confundir con este proyecto.

Si algo "dejó de funcionar" después de que antes funcionaba, lo primero a verificar es cuál de los 3 backends se está ejecutando. El correcto siempre es `backend/main.py` en el puerto 8000 (Swagger en `/docs`).

---

## Arquitectura

```
Red-team-tauri/
├── lib/                    # Flutter app (Dart) — v2.0.0 Pro
│   ├── main.dart
│   ├── core/               # constants, theme, router
│   ├── features/           # 7 feature modules
│   │   ├── dashboard/
│   │   ├── wifi/
│   │   ├── topology/
│   │   ├── scanner/        # port, camera, iot, radio
│   │   ├── c2/
│   │   ├── recon/
│   │   └── report/
│   └── services/           # api, storage, websocket
├── backend/                # Python FastAPI backend
│   ├── main.py             # 41KB — 17 endpoints
│   └── requirements.txt
├── assets/                 # Flutter assets
├── scripts/                # install scripts (replit, termux)
├── pubspec.yaml            # Flutter config v2.0.0
├── src-tauri/              # Tauri desktop (Rust) — version anterior
├── tauri-frontend/         # Vite frontend — version anterior
├── redteam/                # Python Red Team toolkit
└── server.js               # Node.js backend — version anterior
```
