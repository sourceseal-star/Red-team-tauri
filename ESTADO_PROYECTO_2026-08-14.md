# Estado del Proyecto — Red-Team-Tauri / SourceSeal Console
**Fecha:** 2026-08-14
**Sesión:** Superagent Base44
**Repositorio:** https://github.com/sourceseal-star/Red-team-tauri
**Branch:** main
**Último commit:** `658c023` — fix: optimizar endpoints lentos y prevenir bloqueos del event loop

---

## ✅ Trabajo completado en esta sesión

### Optimización de endpoints (commit 658c023, SUBIDO A GITHUB)

| Endpoint | Antes | Después |
|---|---|---|
| `/api/network/radio` | ~2 min (secuencial) | ~4s (paralelo, semaphore 200) |
| `/api/enhanced/discover/all` | Bloqueo total del server | ~13s con respuesta parcial |
| Middleware global | Sin timeout | 20s timeout → 504 si algo se cuelga |

**Cambios técnicos:**
- `backend/modules/enhanced_recon.py`: 219 líneas modificadas
  - onvif_discover, ssdp_discover → `asyncio.to_thread` (socket bloqueante → thread pool)
  - snmp_probe, netbios_query, mdns_query → sync + `to_thread`
  - extract_ssl_info → sync + `to_thread` (socket.create_connection bloqueante)
  - scan_camera_full: RTSP check async, DB write con timeout
  - Cancelación activa de tareas pendientes en timeout del gather
  - Timeouts: ONVIF 4s, SSDP 4s, mDNS 2s, scan 8s, por puerto 0.2s

- `redteam/scripts/dashboard_server.py`: 34 líneas modificadas
  - Middleware anti-bloqueo: `asyncio.wait_for(call_next(request), timeout=20.0)`
  - Devuelve 504 si cualquier endpoint tarda más de 20s
  - Server sigue vivo después de timeout

### Verificación de endpoints (75 totales, todos responden)
- `/api/health` → ok
- `/api/network/radio` → 200 (4s)
- `/api/enhanced/discover/all` → 200 (13s, partial=true)
- `/api/resources` → 200
- `/api/services` → 200
- `/api/soar/dags` → 200
- `/api/tip/iocs` → 200
- `/api/honeypot/status` → 200
- Server sobrevive después de todos los endpoints

---

## ❌ Por qué Google Play Protect bloquea la APK

### Causa raíz identificada

Play Protect usa heurísticas automatizadas que marcan la APK por **múltiples signals combinados**:

1. **Permisos peligrosos sin justificación visible** — La app solicita `shell:allow-spawn`, `shell:allow-execute` y `process:allow-restart` que permiten ejecutar comandos del sistema. Play Protect marca cualquier app no-firmada por Google que pueda ejecutar shell commands.

2. **Firma de debug o auto-firmada** — Si el keystore no está configurado correctamente en los Secrets de GitHub, la APK se firma con clave de debug. Play Protect es mucho más agresivo con APKs auto-firmadas que no están en Play Store.

3. **Identifier sospechoso** — `com.sourceseal.console` no está registrado en Google Play Console. Play Protect cross-referencia el package name contra Play Store.

4. **Tauri WebView + shell permissions** — La combinación de WebView + permisos de shell + ejecución de procesos es un patrón común en malware (apps que inyectan código o ejecutan comandos remotos).

5. **CSP null** — `tauri.conf.json` tiene `"csp": null` lo que deshabilita Content Security Policy. Play Protect lo marca como riesgo.

6. **Código ofuscado/scanner de red** — El backend incluye escaneo de red, credenciales de cámaras, SNMP, exploits. Estas funcionalidades disparan detectores de "hacking tools".

### Soluciones (por prioridad)

#### 1. Firmar con keystore consistente (ALTO impacto)
Seguir `SETUP_FIRMA_APK.md`:
- Crear keystore real (no debug)
- Configurar los 4 Secrets en GitHub: `KEYSTORE_BASE64`, `KEY_ALIAS`, `STORE_PASSWORD`, `KEY_PASSWORD`
- El workflow ya hace zipalign + apksigner verify

#### 2. Reducir permisos de shell (ALTO impacto)
En `src-tauri/capabilities/default.json`, eliminar o restringir:
```json
// ELIMINAR si no son estrictamente necesarios:
"shell:allow-spawn",
"shell:allow-execute",
"process:allow-restart",
"process:allow-exit"
```
O reemplazar con permisos más específicos que solo permitan comandos concretos.

#### 3. Habilitar CSP (MEDIO impacto)
En `src-tauri/tauri.conf.json`:
```json
"security": {
  "csp": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' ws: wss: http: https:"
}
```

#### 4. Cambiar el identifier (MEDIO impacto)
Usar un package name más genérico y menos sospechoso:
```json
"identifier": "com.sourceseal.securityconsole"
```

#### 5. Subir a Play Store como Internal Testing (BAJO impacto pero efectivo)
- Crear app en Google Play Console
- Subir la APK como Internal Testing
- Play Protect no bloquea apps que están en Play Store (incluso en testing)

#### 6. Pedir revisión manual a Google
- https://support.google.com/googleplay/android-developer/contact/playprotect_appeals
- Explicar que es una herramienta de seguridad ofensiva/defensiva
- Proporcionar el código fuente (es open source)

---

## 📋 Estado actual del sistema

### Backend (FastAPI)
- **Puerto:** 8001 (Replit) / 8088 (local)
- **Endpoints:** 75 funcionales
- **Sin bloqueos:** middleware de 20s previene congelamiento
- **Sin mocks:** solo datos reales

### Frontend (React + Vite)
- **Build:** `cd tauri-frontend && npm run build` → dist/
- **Dev:** `npm run dev` → :5000 con proxy a :8001
- **12 rutas:** Dashboard, Config, Reports, Honeypot, SOAR, TIP, Geo, RASP, Terminal, Settings, About

### APK (Tauri Android)
- **Workflow:** `.github/workflows/build-android.yml`
- **Build:** push a main dispara build automático
- **Firma:** necesita keystore configurado en Secrets
- **Play Protect:** bloquea por permisos shell + firma + identifier (ver soluciones arriba)

---

## 🔄 Cómo retomar el trabajo

### Prerrequisitos
```bash
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri
```

### Arrancar el backend
```bash
# Replit
bash replit_start.sh

# Local
cd tauri-frontend && npm install --legacy-peer-deps && npm run build
cd redteam/scripts && PORT=8001 python3 dashboard_server.py
# → http://localhost:8001
```

### Arrancar en Termux (Android)
```bash
bash termux_setup.sh
bash start-termux.sh
```

### Pendientes prioritarios
1. **Configurar keystore en GitHub Secrets** para firma consistente del APK
2. **Reducir permisos shell** en `src-tauri/capabilities/default.json`
3. **Habilitar CSP** en `tauri.conf.json`
4. **Probar Integrity Check en producción** (siguiente paso del conversation_status)
5. **Probar flujo de autodestrucción de sellos**
6. **Verificar que el build de APK no falle** con los nuevos permisos reducidos

### Archivos clave modificados
- `backend/modules/enhanced_recon.py` — optimización de discover/all
- `redteam/scripts/dashboard_server.py` — middleware anti-bloqueo
- `src-tauri/capabilities/default.json` — permisos (PENDIENTE reducir)
- `src-tauri/tauri.conf.json` — config Android (PENDIENTE CSP)
- `.github/workflows/build-android.yml` — build + firma APK
