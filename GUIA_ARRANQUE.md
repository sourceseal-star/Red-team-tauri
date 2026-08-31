# SourceSeal Console — Guía de Arranque Rápido
# Moto Edge 50 Fusion + Termux

**Última actualización:** 2026-08-30

## ━━━━ PASO 1: Configurar API Keys (una sola vez) ━━━━

### AbuseIPDB (gratis — reputación de IPs)
1. Ve a https://www.abuseipdb.com/account/api
2. Regístrate (gratis) o inicia sesión
3. Copia tu API key
4. En Termux:
   ```bash
   cd ~/Red-team-tauri
   echo 'ABUSEIPDB_KEY=tu-key-aqui' >> .env
   ```

### Shodan (gratis — puertos, servicios, vulnerabilidades)
1. Ve a https://www.shodan.io/dashboard
2. Crea cuenta gratis
3. Copia tu API key
4. En Termux:
   ```bash
   echo 'SHODAN_API_KEY=tu-key-aqui' >> .env
   ```

## ━━━━ PASO 2: Arrancar todo (un comando) ━━━━

```bash
cd ~/Red-team-tauri
bash arrancar_termux.sh
```

Este es el arranque local seguro: no hace `pull`, `reset`, `stash` ni instala
paquetes. Levanta el dashboard, Commander integrado y PHANTOM usando la copia
que ya tienes en el teléfono.

Para la primera instalación o una actualización completa, usa el recuperador:

```bash
bash termux_recover.sh
```

El recuperador instala dependencias, sincroniza ambos repositorios si están
limpios, compila el frontend y arranca todo. `arrancar.sh` es un alias
compatible del recuperador, no el arranque local.

## ━━━━ PASO 2b: (Opcional) Detección de Objetos con IA ━━━━

### En PC (convertir modelo YOLOv8 a ONNX):
```bash
pip install ultralytics onnx
python3 leviathan_core/tools/convert_yolo_onnx.py
# Genera yolov8n.onnx (~12MB)
scp yolov8n.onnx termux:~/Red-team-tauri/redteam/models/
```

### En Termux (instalar runtime):
```bash
pip install onnxruntime numpy pillow
```

El módulo detecta automáticamente el modelo .onnx y lo usa.

## ━━━━ PASO 2c: Verificar módulos ━━━━

Antes de arrancar, verifica que todo carga:
```bash
python3 leviathan_core/tools/verify_modules.py
```
Reporta: `TOTAL: 28/30 módulos OK` y marca cuáles faltan.

## ━━━━ PASO 3: Abrir el dashboard ━━━━

En Chrome del celular:
```
http://localhost:8001
```

Desde otro dispositivo en la misma WiFi:
```
http://TU_IP_LOCAL:8001
```

## ━━━━ ENDPOINTS PRINCIPALES ━━━━

### Sistema
```bash
curl http://localhost:8001/api/health
curl http://localhost:8001/api/v1/status          # LEVIATHAN unificado
curl http://localhost:8001/api/v1/health           # LEVIATHAN health
curl http://localhost:8001/api/integrated/health   # ARTO + SEAL + LEVIATHAN
```

### LEVIATHAN — Escaneo y Explotación (/api/v1/*)
```bash
# Escaneo de red completo
curl -X POST "http://localhost:8001/api/v1/scan/network" \
  -H "Content-Type: application/json" \
  -d '{"network": "192.168.0.0/24", "profile": "camera_detection"}'

# Detección de cámaras IP
curl -X POST "http://localhost:8001/api/v1/scan/cameras?network=192.168.0.0/24"

# Detección RTSP
curl -X POST "http://localhost:8001/api/v1/scan/rtsp?target=192.168.0.7&port=554"

# Explotación de cámara (auto-detect vendor)
curl -X POST "http://localhost:8001/api/v1/exploit/camera" \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.0.7", "vendor": "hikvision"}'

# Puntuación de amenazas con IA
curl -X POST "http://localhost:8001/api/v1/ai/threat-scoring?target=192.168.0.7" \
  -H "Content-Type: application/json" \
  -d '{"vulnerabilities": [{"severity": "critical"}]}'

# Perfiles de escaneo disponibles
curl http://localhost:8001/api/v1/profiles

# Informe HTML
curl -X POST "http://localhost:8001/api/v1/report/html?target=192.168.0.0/24" \
  -H "Content-Type: application/json" \
  -d '{"scan_type": "comprehensive"}' --output report.html
```

### Investigación OSINT (existentes)
```bash
# Investigar una IP
curl http://localhost:8001/api/investigate/ip/190.1.2.3

# WHOIS de dominio
curl http://localhost:8001/api/osint/whois/dominio.com

# Subdominios
curl http://localhost:8001/api/osint/subdomains/dominio.com?brute=true

# Escanear red CCTV
curl -X POST http://localhost:8001/api/scan/topology
curl -X POST http://localhost:8001/api/scan/cameras
curl -X POST http://localhost:8001/api/enhanced/discover/all
```

### ARTO — AI Autónomo
```bash
curl http://localhost:8001/api/arto/status
curl -X POST http://localhost:8001/api/arto/start
```

## ━━━━ ANDROID / CAMPO ━━━━

En el Dashboard abre **Android / Campo**. Las funciones son bajo demanda:

1. **Leer ubicación** obtiene una posición puntual desde `termux-location`.
2. **Abrir en OsmAnd** envía esas coordenadas a la aplicación instalada.
3. **Estado Wi‑Fi** muestra la conexión y las interfaces visibles.
4. **Escaneo cercano** consulta redes Wi‑Fi mediante Termux:API.
5. **Escaneo automático de red** descubre la red local solo cuando pulsas el botón.
6. **Escaneo manual de puertos** requiere escribir el objetivo, elegir puertos y
   confirmar que tienes autorización.

Para Termux instala el paquete y la aplicación separada Termux:API:

```bash
pkg install termux-api iproute2 nmap
```

Pruebas equivalentes desde la terminal:

```bash
curl http://localhost:8001/api/android/status
curl http://localhost:8001/api/android/location
curl http://localhost:8001/api/android/wifi
curl http://localhost:8001/api/discover/network
curl -X POST http://localhost:8001/api/android/port-scan \
  -H "Content-Type: application/json" \
  -d '{"target":"192.168.1.1","ports":"22,80,443","confirm_manual":true}'
```

El último comando usa TCP connect, no explota servicios ni captura tráfico.
Utilízalo únicamente sobre objetivos propios o expresamente autorizados.

## ━━━━ SI ALGO FALLA ━━━━

### git pull falla con "unstaged changes"
```bash
cd ~/Red-team-tauri
git status --short
# Ejecutar la versión local sin modificarla:
bash arrancar_termux.sh
# Para actualizar, guarda los cambios y luego:
bash termux_recover.sh
```

### Verificar módulos
```bash
python3 leviathan_core/tools/verify_modules.py
```

### Verificar que el backend está vivo
```bash
curl http://localhost:8001/api/health
curl http://localhost:8001/api/v1/status
```

### Ver logs del backend
```bash
tail -50 backend.log
```

### Reinstalar dependencias
```bash
bash termux_setup.sh
```

> `termux_setup.sh` es un alias compatible del recuperador; úsalo solo para
> preparar/sincronizar, no para arrancar una copia local con cambios pendientes.

### Puerto 8001 ocupado
```bash
pkill -9 -f dashboard_server.py
bash arrancar_termux.sh
```

## ━━━━ EN REPLIT ━━━━

```bash
bash replit_start.sh
```

El backend se levanta en :8001 automáticamente.

## ━━━━ FLUJO DE TRABAJO CCTV ━━━━

1. MONTAR: Conectar cámaras a la red
2. ESCANEAR: `POST /api/v1/scan/network` con perfil `camera_detection`
3. DETECTAR: `POST /api/v1/scan/cameras` para cámaras IP específicas
4. INVESTIGAR: `GET /api/investigate/camera/{ip}` por cada cámara
5. ANALIZAR: `POST /api/v1/ai/threat-scoring` para scoring de amenazas
6. EXPLOTAR: `POST /api/v1/exploit/camera` (solo si autorizado)
7. REPORTAR: `POST /api/v1/report/html` para informe completo
8. EVIDENCIA: Documentar con WHOIS + threat intel de cada IP
