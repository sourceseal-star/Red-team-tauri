# 🔱 SOURCESEAL — Guía Completa de Termux

**Actualizado: 31 agosto 2026**

Guía definitiva para instalar, sincronizar y levantar todo el sistema SourceSeal en Android via Termux.

---

## 📋 ÍNDICE

1. [Prerrequisitos](#prerrequisitos)
2. [Instalación inicial](#instalación-inicial)
3. [Sincronizar y actualizar](#sincronizar-y-actualizar)
4. [Levantar el sistema](#levantar-el-sistema)
5. [Commander CLI (separado)](#commander-cli)
6. [Detener el sistema](#detener)
7. [Puertos y servicios](#puertos)
8. [Solución de problemas](#problemas)
9. [Seguridad](#seguridad)

---

## 📦 PREREQUISITOS

| Componente | Versión | Nota |
|---|---|---|
| Termux | Última | **Desde F-Droid** — NO Play Store |
| Android | 8+ | API 26+ |
| RAM | 3GB+ | Recomendado 4GB |
| Almacenamiento | 500MB libres | Para repos + node_modules |

**Instalar Termux desde F-Droid:**
```
https://f-droid.org/packages/com.termux/
```
> ⚠️ La versión de Play Store está desactualizada y causa errores.

---

## 🚀 INSTALACIÓN INICIAL

### Paso 1 — Paquetes del sistema

```bash
pkg update -y && pkg upgrade -y
pkg install python git nmap whois nodejs openssh termux-api curl jq
```

### Paso 2 — Permisos de almacenamiento

```bash
termux-setup-storage
```
Acepta el diálogo que aparece.

### Paso 3 — Clonar repositorios

```bash
cd ~

# Red-team-tauri (Dashboard web + backend)
git clone https://github.com/sourceseal-star/Red-team-tauri.git

# Commander (CLI de auditoría)
git clone https://github.com/sourceseal-star/commander.git
```

### Paso 4 — Dependencias Python

```bash
pip install fastapi uvicorn httpx pydantic psutil aiohttp \
    dnspython beautifulsoup4 python-whois pycryptodome \
    numpy scipy sounddevice
```

> ⚠️ **NO instales `cryptography`** — fue reemplazado por `pycryptodome` porque `cryptography` requiere compilar un core en Rust que se rompe en Termux.

### Paso 5 — Build del frontend (primera vez)

```bash
cd ~/Red-team-tauri/tauri-frontend
npm install --legacy-peer-deps
npm run build
cd ~
```

### Paso 6 — Configurar .env

```bash
cd ~/Red-team-tauri
# El script termux_start.sh crea el .env automáticamente la primera vez
# O manualmente:
cat > .env << EOF
REDTEAM_API_KEY=tu-clave-secreta-aqui
HOST=0.0.0.0
PORT=8001
ALLOWED_ORIGINS=http://localhost:8001,http://127.0.0.1:8001
EOF
chmod 600 .env
```

**Verificar instalación:**
```bash
cd ~/Red-team-tauri
bash termux_start.sh
```
Deberías ver el dashboard en `http://localhost:8001`.

---

## 🔄 SINCRONIZAR Y ACTUALIZAR

Cada vez que haya cambios en GitHub (nuevos commits, fixes, mejoras):

```bash
cd ~/Red-team-tauri
bash termux_sync.sh
```

Este script hace automáticamente:

1. ✅ Verifica que git esté instalado
2. ✅ Detecta cambios locales sin commitear y los stashea
3. ✅ `git pull` desde GitHub (branch actual)
4. ✅ Muestra los últimos 10 commits
5. ✅ Instala dependencias Python actualizadas
6. ✅ Verifica pycryptodome, fastapi, uvicorn, etc.
7. ✅ Verifica node_modules del frontend
8. ✅ Rebuild del frontend si el código fuente cambió
9. ✅ Restaura tus cambios locales del stash
10. ✅ Libera puertos en uso (8001-8005, 8080)

**Sincronización manual (sin el script):**
```bash
cd ~/Red-team-tauri
git stash
git pull origin main
pip install -r requirements.txt 2>/dev/null || pip install -r redteam/requirements.txt
cd tauri-frontend && npm install --legacy-peer-deps && npm run build && cd ..
```

---

## ▶️ LEVANTAR EL SISTEMA

### Opción A — Script unificado (recomendado)

```bash
cd ~/Red-team-tauri
bash termux_start.sh
```

Esto levanta:
- Dashboard FastAPI en **:8001** (sirve API + frontend compilado)
- Gateway Mesh en **:8080** (si está disponible)
- Wake-lock (mantiene Android activo)
- Logs en vivo en la terminal

### Opción B — Script original de Termux

```bash
cd ~/Red-team-tauri
bash start-termux.sh
```

### Opción C — Manual

```bash
cd ~/Red-team-tauri/redteam/scripts
python3 dashboard_server.py
```

### Acceder al dashboard

Desde el mismo teléfono:
```
http://localhost:8001
```

Desde otro dispositivo en la misma WiFi:
```
http://TU_IP_WIFI:8001
```

Para saber tu IP WiFi:
```bash
ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1
```

---

## ⚡ COMMANDER CLI

Commander es una herramienta CLI independiente de auditoría de seguridad.

### Instalación

```bash
cd ~/commander
pip install -r requirements.txt
```

### Uso

```bash
# Menú interactivo (9+ opciones)
python3 commander.py

# Auditoría automática
python3 commander.py --auto 192.168.1.0/24 --email tu@mail.com --debug

# Reanudar auditoría interrumpida
python3 commander.py --resume 1 --email tu@mail.com

# Listar auditorías
python3 commander.py --list

# Dashboard web (si se quiere interfaz gráfica)
python3 commander_server.py  # Puerto 8003
```

### Actualizar Commander

```bash
cd ~/commander
git pull origin main
```

---

## 🛑 DETENER

### Detener el dashboard
```
Ctrl+C
```
El script libera puertos y wake-lock automáticamente.

### Detener procesos huérfanos
```bash
# Si el script no cerró limpio
pkill -f dashboard_server.py
pkill -f mesh_server.py
pkill -f commander_server.py
termux-wake-release
```

### Script de parada total
```bash
cd ~/Red-team-tauri
bash scripts/termux/stop_all.sh
```

---

## 🔌 PUERTOS

| Puerto | Servicio | Estado |
|---|---|---|
| 8001 | Dashboard FastAPI (principal) | Activo |
| 8002 | Ghost Hunter Phantom (futuro) | Reservado |
| 8003 | Commander web | Opcional |
| 8004 | Nexus | Opcional |
| 8005 | Controller | Opcional |
| 8080 | Gateway Mesh | Opcional |

**Verificar qué puertos están en uso:**
```bash
for p in 8001 8002 8003 8004 8005 8080; do
    lsof -i :$p 2>/dev/null && echo "Puerto $p en uso" || echo "Puerto $p libre"
done
```

---

## 🔧 PROBLEMAS

### "command not found: python3"
```bash
pkg install python
```

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
pip install fastapi uvicorn httpx pydantic psutil aiohttp pycryptodome
```

### "cryptography fails to build"
```bash
# NO instales cryptography — usa pycryptodome
pip uninstall cryptography
pip install pycryptodome
```

### El backend arranca pero el dashboard se ve en blanco
```bash
# Rebuild del frontend
cd ~/Red-team-tauri/tauri-frontend
npm install --legacy-peer-deps
npm run build
```

### "Port 8001 already in use"
```bash
pkill -f dashboard_server.py
# O
lsof -t -i :8001 | xargs kill
```

### El script vuelve al prompt sin decir nada
Este era un bug con `set -Eeuo pipefail` y `free_port()`. Ya está arreglado (commit `9d0a0e2`). Actualiza:
```bash
cd ~/Red-team-tauri
git pull origin main
```

### nmap no funciona
```bash
pkg install nmap
# Verificar
nmap --version
```

### El receptor de ultrasonidos falla
```bash
pip install numpy scipy sounddevice
# Si sounddevice falla (sin micrófono), el receptor usa arecord como fallback
pkg install alsa-utils  # para arecord
```

---

## 🔒 SEGURIDAD

### .env — Archivo crítico
```bash
# NUNCA commitear .env
# Verificar que esté en .gitignore
grep ".env" ~/Red-team-tauri/.gitignore

# Permisos correctos
chmod 600 ~/Red-team-tauri/.env
```

### API Key
- La API Key se genera automáticamente la primera vez
- Se guarda en `.env` como `REDTEAM_API_KEY`
- El frontend la guarda en `localStorage` como `api_token`
- **NUNCA la compartas en capturas de pantalla**

### Antes de commitear cambios
```bash
# Verificar que no hay secrets en el diff
git diff --cached | grep -i -E "(key|token|password|secret)" && echo "⚠️ REVISAR" || echo "✅ Limpio"
```

### Red
- El backend escucha en `0.0.0.0` (accesible desde WiFi)
- Para acceso solo local: cambiar `HOST=127.0.0.1` en `.env`
- Usa la API Key para autenticación en todas las peticiones

---

## 📝 NOTAS

- **Termux desde F-Droid** — la versión de Play Store está desactualizada
- **pycryptodome** reemplazó a `cryptography` — no intentes instalar `cryptography`
- **wake-lock** mantiene el proceso vivo aunque la pantalla se apague
- El frontend compilado se sirve desde el backend en un solo puerto (8001)
- Commander funciona como CLI independiente o integrado en el dashboard
- Los logs se guardan en: `sourceseal-backend.log`, `sourceseal-gateway.log`

---

## 🆘 SOPORTE

```bash
# Diagnóstico completo
echo "=== Sistema ==="
uname -a
echo "=== Python ==="
python3 --version
echo "=== Paquetes ==="
python3 -c "import fastapi, uvicorn, httpx, psutil; print('OK')"
python3 -c "from Crypto.Cipher import AES; print('pycryptodome OK')"
echo "=== Git ==="
cd ~/Red-team-tauri && git log --oneline -3
echo "=== Puertos ==="
for p in 8001 8003 8080; do lsof -i :$p 2>/dev/null && echo ":$p en uso" || echo ":$p libre"; done
echo "=== .env ==="
[ -f ~/Red-team-tauri/.env ] && echo ".env existe" || echo ".env FALTA"
```

---

*SourceSeal Global Protocol — Built from a Moto Edge. No funding. No excuses.*
