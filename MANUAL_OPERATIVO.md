# 🛡️ MANUAL OPERATIVO — Red-Team-Tauri / SourceSeal
## Sala de Guerra Unificada v3.0

> **Consola de operaciones de seguridad ofensiva y defensiva.**  
> Topología + Cámaras + Comunicaciones Ultrasónicas + Threat Intel + Exploits + Captura de tráfico — todo en un dashboard.

---

## 📋 TABLA DE CONTENIDOS

1. [Requisitos del Sistema](#1-requisitos-del-sistema)
2. [Instalación — Termux (Android)](#2-instalación--termux-android)
3. [Instalación — Replit](#3-instalación--replit)
4. [Instalación — Local (Linux/Mac)](#4-instalación--local-linuxmac)
5. [Arranque y Operación](#5-arranque-y-operación)
6. [Variables de Entorno](#6-variables-de-entorno)
7. [Arquitectura del Sistema](#7-arquitectura-del-sistema)
8. [Endpoints de la API (60+)](#8-endpoints-de-la-api)
9. [Sala de Guerra — Panel Principal](#9-sala-de-guerra--panel-principal)
10. [Protocolo MURCIÉLAGO (Ultrasonidos)](#10-protocolo-murciélago-ultrasonidos)
11. [Threat Intelligence](#11-threat-intelligence)
12. [Exploit Matcher](#12-exploit-matcher)
13. [Packet Analyzer](#13-packet-analyzer)
14. [Evidencia Blindada](#14-evidencia-blindada)
15. [Comandos de Sincronización](#15-comandos-de-sincronización)
16. [Solución de Problemas](#16-solución-de-problemas)
17. [Identidad Visual SourceSeal](#17-identidad-visual-sourceseal)

---

## 1. REQUISITOS DEL SISTEMA

### Mínimos

| Componente | Requisito |
|---|---|
| **Python** | 3.10+ |
| **Node.js** | 18+ (LTS recomendado) |
| **Git** | Cualquiera |
| **RAM** | 512 MB libre |
| **Disco** | 200 MB (sin ExploitDB) / 500 MB (con ExploitDB) |

### Herramientas opcionales (activan funciones extra)

| Herramienta | Instalación | Función que activa |
|---|---|---|
| `nmap` | `pkg install nmap` / `apt install nmap` | Escaneo de topología, puertos, OS fingerprint |
| `traceroute` | `pkg install traceroute` / `apt install traceroute` | Traceroute desde el dashboard |
| `tcpdump` | `pkg install tcpdump` / `apt install tcpdump` | Captura de paquetes + detección de anomalías |
| `ffmpeg` | `pkg install ffmpeg` / `apt install ffmpeg` | RTSP→HLS, snapshots de cámaras, detección de movimiento |
| `ffplay` | Incluido con ffmpeg | Reproducción de ultrasonidos (MURCIÉLAGO) |
| `termux-microphone-record` | `pkg install termux-api` | Recepción de ultrasonidos (solo Termux) |
| `qrencode` | `pkg install qrencode` | Códigos QR en evidencia |

### Dependencias Python

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.0
httpx
qrcode[pil]==7.4.2
reportlab==4.2.5
numpy
```

---

## 2. INSTALACIÓN — TERMUX (Android)

### Paso 1: Instalar Termux

Descargar desde F-Droid (NO desde Play Store — versión desactualizada):
```
https://f-droid.org/packages/com.termux/
```

### Paso 2: Configurar permisos

```bash
termux-setup-storage
```
Aceptar permisos de almacenamiento. Para el micrófono (MURCIÉLAGO):
- Ir a Ajustes → Apps → Termux → Permisos → Micrófono → Permitir

### Paso 3: Instalación automática (recomendada)

```bash
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri
bash termux_setup.sh
```

Esto ejecuta automáticamente:
1. `pkg update && pkg upgrade`
2. Instala Python, Node.js, Git, OpenSSL, jq, curl, termux-api
3. Instala nmap, whois (opcionales)
4. `pip install fastapi uvicorn pydantic httpx qrcode reportlab numpy`
5. `npm install` en `tauri-frontend/`
6. `npm run build` (genera `dist/`)

### Paso 4: Instalación manual (si el script falla)

```bash
# Paquetes del sistema
pkg update -y && pkg upgrade -y
pkg install -y python python-pip nodejs-lts git openssl-tool jq curl wget termux-api
pkg install -y nmap whois ffmpeg tcpdump

# Python deps
pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" pydantic==2.9.0 httpx
pip install "qrcode[pil]==7.4.2" reportlab==4.2.5 numpy

# Frontend
cd tauri-frontend
npm install
npm run build
cd ..
```

---

## 3. INSTALACIÓN — REPLIT

### Paso 1: Importar desde GitHub

1. Ir a https://replit.com
2. Crear nuevo Repl → "Import from GitHub"
3. Seleccionar `sourceseal-star/Red-team-tauri`

### Paso 2: Configurar Secrets

En la pestaña **Secrets** del Repl:

| Key | Valor | Obligatorio |
|---|---|---|
| `REDTEAM_API_KEY` | Tu clave de API (cualquier string) | Sí |
| `ABUSEIPDB_KEY` | Key de abuseipdb.com (gratis) | Opcional |
| `SHODAN_API_KEY` | Key de shodan.io | Opcional |
| `CANARY_CALLBACK_HOST` | URL pública del Repl | Opcional |

### Paso 3: Ejecutar

El Repl arranca automáticamente con `replit_start.sh`. Si no:

```bash
bash replit_start.sh
```

Servidor disponible en el puerto **8001**.

---

## 4. INSTALACIÓN — LOCAL (Linux/Mac)

```bash
# 1. Clonar
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri

# 2. Python
python3 -m venv venv
source venv/bin/activate
pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" pydantic==2.9.0 httpx
pip install "qrcode[pil]==7.4.2" reportlab==4.2.5 numpy

# 3. Frontend
cd tauri-frontend
npm install
npm run build
cd ..

# 4. Arrancar
PORT=8001 python3 redteam/scripts/dashboard_server.py
# Abrir http://localhost:8001
```

---

## 5. ARRANQUE Y OPERACIÓN

### Comando principal

```bash
bash replit_start.sh    # Replit o Local — solo backend :8001 (sirve dist/)
bash start-termux.sh    # Termux — backend :8001 + Vite dev :5173
```

### Sincronizar con GitHub (traer cambios)

```bash
bash sync.sh
```

`sync.sh` hace automáticamente:
1. `git fetch origin`
2. Si hay cambios: `git reset --hard origin/main`
3. `pip install` (dependencias Python)
4. `npm install && npm run build` (frontend)
5. Mata procesos zombie en el puerto 8001
6. Reinicia el backend

### Verificar que está corriendo

```bash
curl http://localhost:8001/health
# Respuesta: {"status":"ok","backend":"red-team-tauri-unified","version":"3.0",...}
```

### Puertos

| Puerto | Servicio | Entorno |
|---|---|---|
| **8001** | Backend FastAPI (API + WebSocket + estáticos) | Todos |
| **5173** | Frontend Vite dev server (proxy a :8001) | Solo Termux |
| **554** | Streams RTSP de cámaras | Externo |

---

## 6. VARIABLES DE ENTORNO

### Obligatorias

| Variable | Default | Descripción |
|---|---|---|
| `REDTEAM_API_KEY` | (vacío) | Clave de API. Si está vacía, no se valida. |

### Opcionales — Intel y OSINT

| Variable | Default | Descripción |
|---|---|---|
| `ABUSEIPDB_KEY` | (vacío) | Key de AbuseIPDB (gratis, 1000/día) |
| `SHODAN_API_KEY` | (vacío) | Key de Shodan para OSINT |
| `SOURCESEAL_API` | `https://source.coal/api/v1/seal` | Anclaje blockchain |
| `SOURCESEAL_VERIFY` | `https://source.coal/api/v1/verify` | Verificación blockchain |

### Opcionales — Configuración

| Variable | Default | Descripción |
|---|---|---|
| `PORT` | `8001` | Puerto del backend |
| `HOST` | `0.0.0.0` | Bind address |
| `ALLOWED_ORIGINS` | `localhost:5173,127.0.0.1:5173` | CORS (separados por coma) |
| `RATE_LIMIT` | `60` | Requests/min por IP |
| `CANARY_CALLBACK_HOST` | (vacío) | URL pública para canary tokens |

### Cómo configurarlas

```bash
# Termux / Linux — exportar antes de arrancar
export ABUSEIPDB_KEY=tu_key_aqui
export SHODAN_API_KEY=tu_key_aqui
bash start-termux.sh

# Replit — pestaña Secrets
# Name: ABUSEIPDB_KEY  Value: tu_key_aqui
```

---

## 7. ARQUITECTURA DEL SISTEMA

```
Red-Team-Tauri/
├── replit_start.sh              # Arranque Replit/Local
├── start-termux.sh              # Arranque Termux
├── sync.sh                      # Sincronización con GitHub
├── termux_setup.sh              # Instalación completa Termux
│
├── redteam/
│   ├── scripts/
│   │   ├── dashboard_server.py  # BACKEND — FastAPI (60+ endpoints)
│   │   ├── requirements.txt     # Dependencias Python
│   │   └── ...                  # Scripts auxiliares
│   ├── murcielago/
│   │   ├── murcielago_sender.py     # Emisor ultrasonido (standalone)
│   │   ├── murcielago_receiver.py   # Receptor ultrasonido (standalone)
│   │   └── README.md
│   ├── dashboard/               # Frontend legacy (PWA)
│   ├── reports/                 # Reportes JSON generados
│   └── data/                    # Datos persistentes
│       ├── intel_cache.db       # Cache SQLite Threat Intel
│       ├── exploitdb/           # CSV ExploitDB (descargable)
│       ├── captures/            # Capturas pcap
│       └── murcielago_wav/      # WAVs generados
│
├── tauri-frontend/              # FRONTEND — React + Vite + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   │   ├── WarRoom.tsx       # SALA DE GUERRA (vista principal)
│   │   │   │   ├── TopologyMap.tsx    # Grafo interactivo (vis-network)
│   │   │   │   ├── RiskPanel.tsx      # Riesgo semafórico
│   │   │   │   └── CommandPalette.tsx # Paleta ⌘K
│   │   │   ├── IntelPanel.tsx         # Threat Intel (AbuseIPDB)
│   │   │   ├── ExploitMatrix.tsx      # Exploit Matcher
│   │   │   ├── TrafficMonitor.tsx     # Packet Analyzer
│   │   │   ├── CameraGrid.tsx         # Grid de cámaras
│   │   │   ├── EvidenceExporter.tsx   # Evidencia blindada
│   │   │   ├── MurcielagoPanel.tsx    # Ultrasonidos (panel standalone)
│   │   │   └── LeafletMap.tsx         # Geolocalización
│   │   ├── hooks/
│   │   │   └── useScanStore.ts        # Zustand — estado global
│   │   └── styles/
│   │       └── source-seal.css       # Identidad visual (CSS vars)
│   ├── package.json
│   └── vite.config.ts
│
└── docs/
    └── CAMERA_ENDPOINTS.md
```

### Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Backend** | FastAPI + Uvicorn + httpx + WebSocket |
| **Frontend** | React 18 + TypeScript + Vite |
| **Estado** | Zustand (store global) |
| **Grafo de red** | vis-network (topología interactiva) |
| **Geolocalización** | Leaflet |
| **Iconos** | lucide-react |
| **Cache** | SQLite (Threat Intel) |
| **Audio** | Web Audio API (emisor) + numpy FFT (receptor) |
| **Seguridad** | API Key + Rate Limiting + CORS |

---

## 8. ENDPOINTS DE LA API

### Escaneo y Topología

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/scan/topology` | Escaneo de topología de red (nmap) |
| `POST` | `/api/scan/cameras` | Detección de cámaras IP |
| `POST` | `/api/scan/routers` | Detección de routers |
| `POST` | `/api/scan/iot` | Detección de dispositivos IoT |
| `POST` | `/api/scan/wifi` | Escaneo WiFi |
| `GET` | `/api/topology/traceroute` | Traceroute real (o nmap fallback) |

### Cámaras y Video

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/iot/snapshot` | Snapshot de cámara (JPEG) |
| `GET` | `/api/iot/video-urls` | URLs de video detectadas |
| `GET` | `/api/iot/mjpeg-proxy` | Proxy MJPEG |
| `POST` | `/api/iot/rtsp-to-hls` | Convertir RTSP a HLS |
| `DELETE` | `/api/iot/rtsp-stop/{id}` | Detener conversión HLS |
| `GET` | `/api/iot/rtsp-active` | Conversiones HLS activas |
| `GET` | `/api/vision/motion-detect` | Detección de movimiento (ffmpeg + hash) |

### Protocolo MURCIÉLAGO (Ultrasonidos)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/murcielago/send` | Generar y reproducir ultrasonido |
| `GET` | `/api/murcielago/generate-wav` | Generar WAV descargable |
| `GET` | `/api/murcielago/download/{file}` | Descargar WAV cacheado |
| `GET` | `/api/murcielago/status` | Estado del protocolo |
| `POST` | `/api/comms/ultrasonic-send` | Enviar con offset de frecuencia |
| `POST` | `/api/comms/ultrasonic-receive` | Grabar y decodificar |

### Threat Intelligence

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/intel/ip/{ip}` | Reputación de IP (AbuseIPDB + cache) |
| `POST` | `/api/intel/bulk-check` | Consulta masiva (5 concurrentes) |

### Exploit Matcher

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/exploits/match` | Match de fingerprints a exploits |
| `GET` | `/api/exploits/search` | Búsqueda libre |
| `POST` | `/api/exploits/init-db` | Descargar ExploitDB (offline) |
| `GET` | `/api/exploits/list` | Listar exploits conocidos |

### Packet Analyzer

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/capture/start` | Iniciar captura (tcpdump) |
| `POST` | `/api/capture/stop/{id}` | Detener y analizar |
| `GET` | `/api/capture/active` | Capturas activas |

### Evidencia Blindada

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/export/sealed-json` | Topología + hash SHA-256 + blockchain |
| `GET` | `/api/export/paper-evidence` | PDF imprimible con código QR |
| `GET` | `/api/export/sealed-csv` | CSV con hash en headers |
| `POST` | `/api/export/process-pending` | Procesar sellos offline |
| `GET` | `/api/export/verify/{hash}` | Verificar hash en blockchain |

### Honeypot y Canary

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/honeypot/start` | Iniciar honeypot |
| `POST` | `/api/honeypot/stop` | Detener honeypot |
| `POST` | `/api/canary/generate` | Generar canary token |
| `POST` | `/api/canary/svg/generate` | Generar canary SVG |
| `GET` | `/api/canary/callback` | Callback de canary token |

### OSINT y Geo

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/osint/shodan` | Lookup en Shodan |
| `POST` | `/api/osint/extract` | Extracción OSINT |
| `GET` | `/api/geo` | Geolocalización de IP |

### Sistema

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/network/stats` | Estadísticas de red |
| `WS` | `/ws` | WebSocket (alertas en tiempo real) |
| `GET/POST` | `/api/settings` | Configuración del sistema |
| `POST` | `/api/auth/login` | Autenticación |

---

## 9. SALA DE GUERRA — PANEL PRINCIPAL

La **Sala de Guerra** (`WarRoom.tsx`) es el dashboard unificado:

```
+------------------------+------------------------+
|  TOPOLOGIA             |  CAMARAS               |
|  - Grafo interactivo   |  - Grid de feeds       |
|  - Click host ->       |  - Snapshots           |
|    Traceroute overlay  |  - Deteccion movimiento|
|  - Hosts seleccionables|  - Hash de capturas    |
+------------------------+------------------------+
|  TABS: Murcielago  |  Threat Intel             |
+-------------------------------------------------+
|  Murcielago:                                    |
|  - Slider de frecuencia (16-22 kHz)             |
|  - Envio via Web Audio API (sin backend)       |
|  - Recepcion via backend (microfono + FFT)    |
|  - Historial de mensajes                        |
+-------------------------------------------------+
|  Threat Intel (3 columnas):                     |
|  IntelPanel - ExploitMatrix - TrafficMonitor   |
+-------------------------------------------------+
```

### Operacion desde el dashboard

1. **Topologia**: Click en "Escanear" -> grafo interactivo. Click en un host -> traceroute.
2. **Cameras**: Click en "Escanear" -> grid de feeds. Botones Snap y Mov.
3. **Ultrasonidos**: Escribir mensaje -> ajustar slider de frecuencia -> "Enviar".
4. **Threat Intel**: Click en "Verificar Reputacion" -> consulta AbuseIPDB.
5. **Exploit Matrix**: Click en "Buscar Exploits" -> match contra ExploitDB.
6. **Traffic Analyzer**: Seleccionar interfaz -> "Capturar" -> 15s + analisis.

---

## 10. PROTOCOLO MURCIÉLAGO (Ultrasonidos)

### Concepto

Comunicacion por ultrasonidos (18-20 kHz) sin internet, WiFi, Bluetooth ni red. Solo altavoz y microfono.

### Scripts standalone (sin dashboard)

```bash
# Emisor (reproduce por el altavoz)
python3 redteam/murcielago/murcielago_sender.py "SOS 192.168.1.10"
python3 redteam/murcielago/murcielago_sender.py "MENSAJE" --farol  # Repite 3x

# Receptor (graba y decodifica)
python3 redteam/murcielago/murcielago_receiver.py
python3 redteam/murcielago/murcielago_receiver.py --duration 20
```

### Desde el dashboard

- **Enviar**: Escribir mensaje -> ajustar slider -> "Enviar" (Web Audio API, sin backend)
- **Recibir**: Click en "Escuchar" -> graba 6s -> decodifica via backend
  - Requiere `numpy` y `termux-microphone-record` (Termux) o `ffmpeg` (Linux)

### Configuracion

| Parametro | Default | Notas |
|---|---|---|
| Frecuencia base | 18,000 Hz | Slider: -2000 a +2000 Hz |
| Frecuencia de sync | 19,500 Hz | Tono fijo al inicio y final |
| Duracion por simbolo | 80 ms | 120 ms en Web Audio API |
| Sample rate | 48,000 Hz | |
| Modo Farol | 3 repeticiones | Para entornos ruidosos |

### Instalacion para MURCIÉLAGO

```bash
# Termux
pkg install ffmpeg termux-api
pip install numpy

# Linux
sudo apt install ffmpeg
pip install numpy
```

---

## 11. THREAT INTELLIGENCE

### Activacion

1. Registrarse gratis en https://www.abuseipdb.com (1000 consultas/dia gratis)
2. Obtener API key
3. Configurar:
```bash
export ABUSEIPDB_KEY=tu_key_aqui
```

### Uso desde el dashboard

1. Escanear la red (topologia) -> detecta hosts
2. Ir al tab "Threat Intel"
3. Click en "Verificar Reputacion" -> consulta las IPs publicas encontradas
4. Resultados con verdict semaforico:
   - MALICIOUS (score > 75) — rojo
   - SUSPICIOUS (score > 25) — ambar
   - CLEAN (score <= 25) — verde

### Cache

- Los resultados se cachean en SQLite (`data/intel_cache.db`)
- TTL: 24 horas
- Consultas en cache no consumen API quota

### API directa

```bash
# Una IP
curl http://localhost:8001/api/intel/ip/8.8.8.8

# Masivo
curl -X POST http://localhost:8001/api/intel/bulk-check \
  -H "Content-Type: application/json" \
  -d '["8.8.8.8", "1.1.1.1", "8.8.4.4"]'
```

---

## 12. EXPLOIT MATCHER

### Primera vez — descargar ExploitDB

```bash
curl -X POST http://localhost:8001/api/exploits/init-db
```

Descarga `files_exploits.csv` desde GitHub (~50 MB). Una vez descargado, funciona 100% offline.

### Uso desde el dashboard

1. Escanear la red -> detecta servicios (nmap fingerprint)
2. Ir al tab "Threat Intel"
3. Click en "Buscar Exploits" -> match automatico
4. Resultados con confianza:
   - **HIGH** — service + version coinciden
   - **MEDIUM** — service coincide
   - **LOW** — keywords coinciden
5. Links directos a ExploitDB

### API directa

```bash
# Match por fingerprints
curl -X POST http://localhost:8001/api/exploits/match \
  -H "Content-Type: application/json" \
  -d '[{"name":"apache","version":"2.4.49"},{"name":"openssh"}]'

# Busqueda libre
curl "http://localhost:8001/api/exploits/search?query=eternalblue"
```

---

## 13. PACKET ANALYZER

### Requisitos

```bash
# Termux
pkg install tcpdump

# Linux
sudo apt install tcpdump
```

En Linux requiere root o capacidades CAP_NET_RAW:
```bash
sudo setcap cap_net_raw=eip $(which tcpdump)
```

### Uso desde el dashboard

1. Ir al tab "Threat Intel"
2. Seleccionar interfaz (any / wlan0 / eth0)
3. Click en "Capturar" -> captura 15 segundos
4. Analisis automatico:
   - Total de paquetes
   - Distribucion de protocolos (ARP, TCP SYN, otros)
   - Deteccion de anomalias:
     - **ARP_STORM** (>50 ARP -> posible ARP Spoofing)
     - **PORT_SCAN** (>20 SYN de una IP -> posible escaneo)

### API directa

```bash
# Iniciar captura
curl -X POST "http://localhost:8001/api/capture/start?interface=any&duration=15"

# Detener y analizar
curl -X POST http://localhost:8001/api/capture/stop/SESSION_ID

# Ver capturas activas
curl http://localhost:8001/api/capture/active
```

---

## 14. EVIDENCIA BLINDADA

### Que hace

Exporta la topologia escaneada con integridad criptografica:
- Hash SHA-256 de los datos
- Anclaje en blockchain (SourceSeal)
- PDF imprimible con codigo QR de verificacion
- CSV con hash en los headers
- Modo offline: guarda sellos pendientes y los procesa cuando hay internet

### Uso

Desde el dashboard -> boton "Evidencia" -> 3 opciones:
1. **JSON Sellado** — descarga JSON con hash + anclaje blockchain
2. **CSV + Hash** — CSV con hash en headers
3. **PDF con QR** — PDF imprimible con codigo QR

Boton "Procesar Pendientes" -> procesa sellos guardados offline.

### API directa

```bash
curl http://localhost:8001/api/export/sealed-json
curl http://localhost:8001/api/export/paper-evidence
curl http://localhost:8001/api/export/verify/HASH_AQUI
```

---

## 15. COMANDOS DE SINCRONIZACIÓN

### `sync.sh` — Traer cambios de GitHub

```bash
bash sync.sh
```

Hace: `git fetch` -> `git reset --hard` (si hay cambios) -> `pip install` -> `npm install && npm run build` -> reinicia backend.

### `replit_start.sh` — Arrancar en Replit/Local

```bash
bash replit_start.sh
```

Mata zombies en puerto 8001 -> arranca backend -> sirve `dist/` como estaticos.

### `start-termux.sh` — Arrancar en Termux

```bash
bash start-termux.sh
```

Arranca backend en :8001 + Vite dev server en :5173 (con proxy a :8001).

### `termux_setup.sh` — Instalacion completa

```bash
bash termux_setup.sh
```

Instala todo desde cero en Termux.

### Comandos utiles

```bash
# Ver si el backend esta corriendo
curl http://localhost:8001/health

# Ver logs del backend (Termux)
tail -f logs/backend.log

# Matar proceso en puerto 8001
fuser -k 8001/tcp          # Linux
lsof -ti:8001 | xargs kill  # Mac/Termux

# Rebuild del frontend
cd tauri-frontend && npm run build

# Descargar ExploitDB
curl -X POST http://localhost:8001/api/exploits/init-db

# Ver estado de MURCIÉLAGO
curl http://localhost:8001/api/murcielago/status
```

---

## 16. SOLUCIÓN DE PROBLEMAS

### El backend no arranca

```bash
# Verificar que el puerto esta libre
lsof -i:8001

# Matar zombies
fuser -k 8001/tcp

# Reintentar
bash replit_start.sh
```

### El frontend no carga

```bash
# Verificar que dist/ existe
ls tauri-frontend/dist/

# Si no existe, rebuild
cd tauri-frontend && npm install && npm run build
```

### "traceroute: command not found"

```bash
pkg install traceroute    # Termux
sudo apt install traceroute  # Linux
```

### "tcpdump: command not found"

```bash
pkg install tcpdump       # Termux
sudo apt install tcpdump  # Linux
```

### MURCIÉLAGO no reproduce sonido

```bash
# Verificar ffplay
which ffplay

# Si no esta
pkg install ffmpeg        # Termux
sudo apt install ffmpeg   # Linux
```

### MURCIÉLAGO no graba (receptor)

```bash
# Termux: instalar termux-api
pkg install termux-api

# Dar permisos de microfono a Termux en Android
# Ajustes -> Apps -> Termux -> Permisos -> Microfono
```

### AbuseIPDB devuelve error 503

- Verificar que `ABUSEIPDB_KEY` esta configurada
- Verificar que no se excedieron las 1000 consultas/dia
- Los resultados en cache (24h) no consumen quota

### ExploitDB no encuentra exploits

```bash
# Descargar la base de datos
curl -X POST http://localhost:8001/api/exploits/init-db

# Verificar que se descargo
ls -la redteam/data/exploitdb/files_exploits.csv
```

### Git pull falla en Termux

```bash
# Si dist/ esta causando conflictos
git checkout -- .
git clean -fd
git pull origin main

# O usar sync.sh que maneja esto automaticamente
bash sync.sh
```

### WebSocket no conecta

- Verificar que el backend esta corriendo en :8001
- En Termux, usar `http://localhost:5173` (Vite proxy)
- En Replit, usar la URL publica del Repl

---

## 17. IDENTIDAD VISUAL SOURCEESEAL

### Paleta de colores

| Variable CSS | Color | Uso |
|---|---|---|
| `--ss-bg` | `#08090d` | Fondo principal |
| `--ss-bg-2` | `#0d1117` | Paneles |
| `--ss-bg-3` | `#161b22` | Inputs / subpaneles |
| `--ss-border` | `#1f2937` | Bordes |
| `--ss-cyan` | `#00e5ff` | Acento principal / topologia |
| `--ss-amber` | `#fbbf24` | Camaras / advertencias |
| `--ss-red` | `#ff3b5c` | Critico / exploits |
| `--ss-green` | `#00ff88` | OK / trafico |

### Archivo de estilos

```
tauri-frontend/src/styles/source-seal.css
```

### Convenciones

- **Cyan** -> Topologia, comunicaciones, acciones primarias
- **Ambar** -> Camaras, advertencias, evidencia
- **Red** -> Critico, exploits, anomalias
- **Green** -> OK, trafico limpio, capturas
- Fuente: `font-mono` (monospace)
- Estilo: minimalista, tactico, sin gradientes innecesarios

---

## NOTAS FINALES

- **Sin internet**: MURCIÉLAGO y captura de paquetes funcionan 100% offline. Threat Intel y ExploitDB necesitan conexion para descarga inicial (luego cache/offline).
- **Seguridad**: La API key (`REDTEAM_API_KEY`) protege los endpoints. Sin ella, el backend no valida acceso — configurar en produccion.
- **Rate limiting**: 60 requests/minuto por IP por defecto. Ajustable via `RATE_LIMIT`.
- **Persistencia**: Datos en `redteam/data/`. SQLite para cache Intel, pcap en `captures/`, WAVs en `murcielago_wav/`.
- **Version**: 3.0-unified. Health check: `GET /health` -> `{"version":"3.0"}`.

---

*Documentado: 2026-08-13 · SourceSeal / Red-Team-Tauri v3.0*
