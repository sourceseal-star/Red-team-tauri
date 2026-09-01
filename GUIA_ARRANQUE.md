# Guía de Arranque — SourceSeal Red-team-tauri v7.0

**Actualizada:** 2026-09-01
**Versión:** 7.0-TACTICAL-HOTRELOAD

---

## 🚀 ARRANQUE COMPLETO — 3 COMANDOS

```bash
cd ~/Red-team-tauri && git pull origin main && bash arrancar.sh
```

Eso es todo. El script hace:
1. ✅ Instala deps Python si faltan
2. ✅ Build frontend (no-fatal: si falla, usa dist/ existente)
3. ✅ Copia build a public/
4. ✅ Arranca FastAPI en :8001
5. ✅ Dashboard disponible en http://localhost:8001

---

## 🔄 ACTUALIZAR DESDE GITHUB

```bash
cd ~/Red-team-tauri

# Si tienes cambios locales:
git stash
git pull origin main
git stash pop

# Si no tienes cambios locales:
git pull origin main

# Reiniciar:
bash arrancar.sh
```

---

## 🔥 HOT-RELOAD — DESARROLLO EN VIVO

```bash
# Terminal 1: Dashboard
bash arrancar.sh

# Terminal 2: Watcher
python3 watcher.py &
```

Ahora edita cualquier módulo en `redteam/modules/`:
- El watcher detecta el cambio en 2 segundos
- Sella el cambio en el ledger SourceSeal
- Envía SIGUSR1 al dashboard
- El dashboard recarga el módulo en caliente

**Sin reiniciar nada.**

---

## 📋 ARRANQUE EN REPLIT

```bash
bash replit_start.sh
```

El script de Replit:
1. Instala deps Nix (Python 3.12, Node 18, nmap, onnxruntime)
2. Build frontend con npm
3. Arranca FastAPI en :8001
4. Replit proxy expone el dashboard

---

## 🎯 AUDITORÍA TÁCTICA — PASO A PASO

### Desde el dashboard
1. Abre `http://localhost:8001`
2. En el sidebar, busca **"Auditoría Táctica"** (icono 🎯 rojo, badge "LIVE")
3. Ingresa la subnet (ej: `192.168.1.0/24`) o déjalo vacío para auto-detectar
4. Clic en **"Ejecutar Auditoría"** (botón rojo-naranja)
5. Observa el log en vivo:
   - 📦 Descubrimiento de hosts
   - 🔌 Escaneo de puertos
   - 📷 Identificación de cámaras
   - 🔑 Prueba de credenciales
   - 🛡️ Búsqueda de CVEs
   - 📄 Generación de reporte sellado
6. Al finalizar:
   - Stats cards con conteos
   - Tabla de hallazgos
   - Botón de descarga del reporte HTML sellado

### Desde la terminal
```bash
# Auto-detectar
curl -X POST http://localhost:8001/api/tactical/scan

# Subnet específica
curl -X POST http://localhost:8001/api/tactical/scan \
  -H "Content-Type: application/json" \
  -d '{"subnet": "192.168.1.0/24"}'
```

---

## 🔧 COMANDOS DE GESTIÓN

### Estado del sistema
```bash
# ¿Está el dashboard arriba?
curl http://localhost:8001/api/health

# ¿Qué módulos hay?
ls redteam/modules/*.py

# ¿Qué playbooks hay?
ls playbooks/*.json

# ¿El watcher está corriendo?
ps aux | grep watcher
```

### Parar servicios
```bash
# Parar dashboard
pkill -f dashboard_server

# Parar watcher
pkill -f watcher.py

# Parar todo
pkill -f dashboard_server; pkill -f watcher.py
```

### Reiniciar limpio
```bash
pkill -f dashboard_server; pkill -f watcher.py
sleep 1
bash arrancar.sh
python3 watcher.py &
```

---

## ⚙️ CONFIGURACIÓN INICIAL

### .env
```bash
# Crear archivo .env con API keys (opcional)
cat > ~/Red-team-tauri/.env << 'EOF'
SHODAN_API_KEY=tu_key_aqui
ABUSEIPDB_KEY=tu_key_aqui
TELEGRAM_BOT_TOKEN=tu_token_aqui
TELEGRAM_CHAT_ID=tu_chat_id
EOF
```

### Engagement autorizado
Editar `config/engagements.json` y poner `authorization_signed: true` con el scope del cliente.

### Operators
Editar `config/operators.json` con los operadores autorizados.

---

## 🐛 PROBLEMAS COMUNES

| Problema | Solución |
|----------|----------|
| Frontend en blanco | `cd tauri-frontend && npm run build && cp -r dist/. ../public/` |
| Puerto 8001 ocupado | `pkill -f dashboard_server && bash arrancar.sh` |
| Git pull fallido | `git stash && git pull origin main && git stash pop` |
| Watcher no detecta | Verificar que `redteam/modules/` existe y hay `.py` files |
| Dashboard no recarga | `kill -USR1 $(cat ~/.c2/pids/dashboard.pid)` |
| psutil no instala | Ya tiene fallback con clang/CFLAGS (commit 3fad1be) |
