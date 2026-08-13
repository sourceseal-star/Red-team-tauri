# 🛡️ MANUAL OPERATIVO — Red-Team-Tauri / SourceSeal
## Sala de Guerra Unificada v3.2.1

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
14. [OSINT Engine](#14-osint-engine)
15. [WiFi Scanner](#15-wifi-scanner)
16. [Black Mirror](#16-black-mirror)
17. [Evidencia Blindada](#17-evidencia-blindada)
18. [Comandos de Sincronización](#18-comandos-de-sincronización)
19. [Solución de Problemas](#19-solución-de-problemas)
20. [Identidad Visual SourceSeal](#20-identidad-visual-sourceseal)

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
| `whois` | `pkg install whois` / `apt install whois` | OSINT — WHOIS lookup |
| `dig` | `pkg install bind-utils` / `apt install dnsutils` | OSINT — brute force de subdominios |
| `exiftool` | `pkg install exiftool` / `apt install libimage-exiftool-perl` | OSINT — extracción de metadatos |
| `aircrack-ng` | `pkg install aircrack-ng` / `apt install aircrack-ng` | WiFi — captura y crackeo de handshakes |
| `iw` | `apt install iw` | WiFi — escaneo de redes (Linux/Kali) |
| `termux-api` | `pkg install termux-api` | WiFi — escaneo sin root en Termux |
| `iptables` | `apt install iptables` | Black Mirror — Chaos Fingerprint |
| `netcat` | `pkg install netcat-openbsd` / `apt install netcat-openbsd` | Black Mirror — Shadow Twin + Chaos |
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

Esto ejecuta automáticamente 8 pasos en orden:
1. `pkg update && pkg upgrade` — actualizar paquetes base
2. Instalar core: Python, Node.js, Git, OpenSSL, jq, curl, wget
3. Instalar herramientas por módulo (ver tabla abajo)
4. Instalar dependencias Python (fastapi, uvicorn, httpx, reportlab, numpy, etc.)
5. Sincronizar con GitHub (git fetch + reset --hard origin/main)
6. Build frontend (`npm install` + `npm run build`)
7. Aplicar permisos de ejecución + crear `.env` con API key
8. Verificación final con checklist de cada herramienta

### Paso 4: Instalación manual (si el script falla)

```bash
# 1. Paquetes base (obligatorios)
pkg update -y && pkg upgrade -y
pkg install -y python python-pip nodejs-lts git openssl-tool jq curl wget

# 2. Paquetes por modulo (instalar los que necesites)
# ESCANEO
pkg install -y nmap traceroute tcpdump

# OSINT ENGINE
pkg install -y whois bind-utils exiftool

# WIFI SCANNER (sin root)
pkg install -y termux-api
# WIFI SCANNER (con root — avanzado)
pkg install -y aircrack-ng

# BLACK MIRROR
pkg install -y netcat-openbsd

# EVIDENCIA
pkg install -y qrencode ffmpeg

# MURCIELAGO
pkg install -y termux-api  # + permiso de microfono

# 3. Dependencias Python
# numpy: SIEMPRE via pkg primero (binario, sin compilar). pip compila desde
# fuente y falla en Termux/aarch64 (Python 3.13 no tiene wheels de numpy).
pkg install -y python-numpy

pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" pydantic==2.9.0
pip install httpx==0.27.0 psutil==6.1.0 requests==2.32.0
pip install aiofiles==24.1.0 python-multipart==0.0.17 websockets==13.1
pip install python-whois==0.9.5 python-nmap==0.7.1
pip install "qrcode[pil]==7.4.2" reportlab==4.2.5
# Solo si pkg no instalo numpy:
python3 -c "import numpy" || pip install numpy

# 4. Frontend
cd tauri-frontend
npm install
npm run build
cd ..
```

### Orden recomendado de instalacion por modulo

Si el script automatico falla o quieres instalar por partes, este es el orden
optimizado (de mas critico a opcional):

| Orden | Modulo | Paquete | Comando | Obligatorio? |
|---|---|---|---|---|
| 1 | **Core** | Python + Node + Git | `pkg install python python-pip nodejs-lts git` | SI |
| 2 | **Backend** | FastAPI + uvicorn | `pip install fastapi uvicorn httpx pydantic` | SI |
| 3 | **Frontend** | npm build | `cd tauri-frontend && npm install && npm run build` | SI |
| 4 | **Escaneo** | nmap + traceroute | `pkg install nmap traceroute` | Recomendado |
| 5 | **Murcielago** | termux-api + permiso micro | `pkg install termux-api` | Recomendado |
| 6 | **OSINT** | whois + dig + exiftool | `pkg install whois bind-utils exiftool` | Recomendado |
| 7 | **WiFi** | termux-api + aircrack-ng | `pkg install termux-api aircrack-ng` | Opcional |
| 8 | **Black Mirror** | netcat | `pkg install netcat-openbsd` | Opcional |
| 9 | **Captura** | tcpdump | `pkg install tcpdump` | Opcional |
| 10 | **Evidencia** | qrencode + ffmpeg | `pkg install qrencode ffmpeg` | Opcional |

### Permisos de Android (despues de instalar)

```bash
# Almacenamiento
termux-setup-storage

# Microfono (MURCIÉLAGO + grabacion de evidencia)
# Ajustes → Apps → Termux → Permisos → Microfono → Permitir

# Ubicacion (WiFi Scanner sin root)
# Ajustes → Apps → Termux → Permisos → Ubicacion → Permitir
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
| `HUNTER_API_KEY` | (vacío) | Key de Hunter.io para email OSINT (25 req/mes gratis) |

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
│   │   │   ├── OSINTPanel.tsx         # OSINT Engine (crt.sh + WHOIS + emails)
│   │   │   ├── WiFiPanel.tsx          # WiFi Scanner (scan + capture + crack)
│   │   │   ├── BlackMirrorPanel.tsx    # Black Mirror (Canary + Ghost + Chaos)
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

### OSINT Engine

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/osint/subdomains/{domain}` | Enumeración de subdominios (crt.sh + brute force) |
| `GET` | `/api/osint/emails/{domain}` | Búsqueda de emails (Hunter.io + pattern-guess) |
| `GET` | `/api/osint/whois/{domain}` | WHOIS lookup con parseo + cache |
| `POST` | `/api/osint/metadata` | Extracción de metadatos con exiftool |
| `GET` | `/api/osint/history/{target}` | Historial de consultas OSINT |
| `GET` | `/api/osint/shodan` | Lookup en Shodan |
| `POST` | `/api/osint/extract` | Extracción OSINT avanzada |

### WiFi Scanner

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/wifi/scan` | Escaneo de redes WiFi (termux-api / iw / airodump-ng) |
| `POST` | `/api/wifi/capture/{bssid}` | Captura handshake WPA/WPA2 |
| `POST` | `/api/wifi/crack/{bssid}` | Crackeo de handshake con aircrack-ng |
| `GET` | `/api/wifi/captures` | Lista de capturas .cap |
| `DELETE` | `/api/wifi/captures/{filename}` | Eliminar captura |

### Black Mirror — Canary Forge

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/blackmirror/canary/forge` | Generar documento canary (PDF o HTML) |
| `GET` | `/api/blackmirror/canary/ping/{token}` | Web bug (se activa al abrir el documento) |
| `GET` | `/api/blackmirror/canary/status` | Estado de todos los canaries |

### Black Mirror — Shadow Twin

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/blackmirror/shadow/twin` | Generar configs de honeypots desde escaneo |

### Black Mirror — Ghostprint

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/blackmirror/ghostprint/learn` | Alimentar patrón temporal de un host |
| `GET` | `/api/blackmirror/ghostprint/profile/{host}` | Perfil semanal + detección de anomalías |
| `GET` | `/api/blackmirror/ghostprint/window/{host}` | Ventanas óptimas para operar |

### Black Mirror — Chaos Fingerprint

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/blackmirror/chaos/apply` | Aplicar regla de envenenamiento de huella |
| `GET` | `/api/blackmirror/chaos/status` | Lista de reglas de chaos activas |

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
|  TABS: Murcielago | Threat Intel | Recon | Mirror |
+---------------------------------------------------+
|  Murcielago:                                      |
|  - Slider de frecuencia (16-22 kHz)              |
|  - Envio via Web Audio API (sin backend)         |
|  - Recepcion via backend (microfono + FFT)      |
|  - Historial de mensajes                          |
+---------------------------------------------------+
|  Threat Intel (3 columnas):                      |
|  IntelPanel - ExploitMatrix - TrafficMonitor     |
+---------------------------------------------------+
|  Recon OSINT (2 columnas):                       |
|  OSINTPanel - WiFiPanel                           |
+---------------------------------------------------+
|  Black Mirror (panel completo):                  |
|  Canary Forge | Ghostprint | Chaos Fingerprint   |
+---------------------------------------------------+
```

### Operacion desde el dashboard

1. **Topologia**: Click en "Escanear" -> grafo interactivo. Click en un host -> traceroute.
2. **Cameras**: Click en "Escanear" -> grid de feeds. Botones Snap y Mov.
3. **Ultrasonidos**: Escribir mensaje -> ajustar slider de frecuencia -> "Enviar".
4. **Threat Intel**: Click en "Verificar Reputacion" -> consulta AbuseIPDB.
5. **Exploit Matrix**: Click en "Buscar Exploits" -> match contra ExploitDB.
6. **Traffic Analyzer**: Seleccionar interfaz -> "Capturar" -> 15s + analisis.
7. **OSINT**: Ingresar dominio -> botones Subs/Emails/WHOIS -> resultados con fuente e historial.
8. **WiFi**: Click en "Escanear" -> redes con señal semaforica -> capturar handshake -> crackear.
9. **Black Mirror**: 3 sub-modulos en panel independiente:
   - **Canary Forge**: Forjar doc con destinatario -> si se filtra, el token delata al traidor.
   - **Ghostprint**: Analizar IP -> heatmap 7x24 -> ventanas optimas para operar sin deteccion.
   - **Chaos**: Aplicar envenenamiento -> puerto real responde como Windows/Cisco/Fortinet.

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

## 14. OSINT ENGINE

### Descripcion

Motor de inteligencia de fuentes abiertas (OSINT) con 4 capacidades:
- **Subdominios** via crt.sh (gratis, sin API key) + brute force con dig
- **Emails** via Hunter.io (si hay key) o pattern-guess
- **WHOIS** via comando whois + parseo a JSON
- **Metadatos** via exiftool con deteccion de campos sospechosos

Todas las consultas se cachean en SQLite (24h TTL).

### Activacion

```bash
# Herramientas del sistema
pkg install whois dig          # Termux
sudo apt install whois dnsutils # Linux

# Exiftool (opcional, para metadatos)
pkg install exiftool            # Termux
sudo apt install libimage-exiftool-perl  # Linux

# Hunter.io (opcional, para emails reales)
# Registrarse en hunter.io (25 req/mes gratis)
export HUNTER_API_KEY=tu_key_aqui

# Wordlist para brute force (opcional, se crea una basica automaticamente)
curl -o redteam/data/wordlists/subdomains.txt \
  https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/subdomains-top1million-5000.txt
```

### Uso desde el dashboard

1. Ir al tab "Recon OSINT"
2. Ingresar dominio (ej: `ejemplo.com`)
3. Click en **Subs** -> enumera subdominios (crt.sh + brute force)
4. Click en **Emails** -> busca emails del dominio
5. Click en **WHOIS** -> consulta WHOIS parseado

Resultados muestran:
- Subdominios: nombre + IP resuelta + fuente (crt.sh / brute-force)
- Emails: direccion + fuente (hunter.io / pattern-guess) + confidence
- WHOIS: campos parseados (registrar, creation date, etc.)
- Historial: ultimas consultas con timestamp

### API directa

```bash
# Subdominios (con brute force)
curl "http://localhost:8001/api/osint/subdomains/ejemplo.com?brute=true"

# Emails
curl http://localhost:8001/api/osint/emails/ejemplo.com

# WHOIS
curl http://localhost:8001/api/osint/whois/ejemplo.com

# Metadatos de archivo (requiere exiftool)
curl -X POST "http://localhost:8001/api/osint/metadata?file_path=/ruta/archivo.pdf"

# Historial
curl http://localhost:8001/api/osint/history/ejemplo.com
```

### Wordlist por defecto

Si no existe wordlist, se crea automaticamente con 55 palabras comunes:
`www, mail, ftp, admin, api, app, blog, dev, staging, test, vpn, ns1, ns2, portal, shop, cdn, media, static, assets, secure, login, dashboard, panel, cpanel, webmail, smtp, pop, imap, mx, support, help, docs, wiki, git, gitlab, github, jenkins, jira, confluence, grafana, prometheus, kibana, elastic, db, database, sql, mysql, postgres, redis, mongo, backup, old, beta, alpha, demo, internal, intranet, extranet, private`

Para mejor cobertura, descargar SecLists (5000 subdominios):
```bash
curl -o redteam/data/wordlists/subdomains.txt \
  https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/DNS/subdomains-top1million-5000.txt
```

---

## 15. WIFI SCANNER

### Descripcion

Escaneo de redes WiFi con 3 metodos progresivos (se intentan en orden):
1. `termux-wifi-scaninfo` — Termux sin root (requiere termux-api + permisos de ubicacion)
2. `iw dev wlan0 scan` — Linux/Kali (requiere root en Android)
3. `airodump-ng` — Kali con modo monitor (requiere root + interfaz monitor)

Captura de handshakes WPA/WPA2 y crackeo con aircrack-ng.

### Activacion

```bash
# Termux (sin root)
pkg install termux-api
# Dar permisos de ubicacion a Termux:
# Ajustes -> Apps -> Termux -> Permisos -> Ubicacion -> Permitir

# Kali / Linux (con root)
sudo apt install aircrack-ng iw
# Modo monitor:
sudo airmon-ng start wlan0
# Interface pasara a llamarse wlan0mon

# Wordlist para crackeo (rockyou.txt)
mkdir -p /usr/share/wordlists
curl -L -o /usr/share/wordlists/rockyou.txt \
  https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt
```

### Uso desde el dashboard

1. Ir al tab "Recon OSINT"
2. Click en "Escanear" -> detecta redes WiFi cercanas
3. Resultados muestran:
   - SSID, BSSID, canal, encriptacion
   - Señal semaforica: verde (>-50dBm), ambar (>-70dBm), rojo (<-70dBm)
4. Click en **Handshake** -> captura 30s de handshake WPA/WPA2
5. Click en **Crack** -> crackea con aircrack-ng + rockyou.txt

### Requisitos por plataforma

| Plataforma | Metodo | Requisito |
|---|---|---|
| Termux (sin root) | termux-wifi-scaninfo | termux-api + permisos ubicacion |
| Termux (con root) | iw / airodump-ng | root + modo monitor |
| Kali Linux | iw / airodump-ng | root + interfaz WiFi |
| Linux normal | iw | root (para scan) |

### API directa

```bash
# Escanear redes
curl http://localhost:8001/api/wifi/scan

# Capturar handshake
curl -X POST \
  "http://localhost:8001/api/wifi/capture/AA:BB:CC:DD:EE:FF?ssid=MiRed&channel=6&duration=30"

# Crackear handshake
curl -X POST http://localhost:8001/api/wifi/crack/AA:BB:CC:DD:EE:FF

# Listar capturas
curl http://localhost:8001/api/wifi/captures

# Eliminar captura
curl -X DELETE http://localhost:8001/api/wifi/captures/archivo.cap
```

### Notas de seguridad

- El crackeo de WiFi solo debe usarse en redes propias o con autorizacion explicita
- El modo monitor requiere root y una tarjeta WiFi compatible
- aircrack-ng es la herramienta estandar; para mayor velocidad usar hashcat con GPU

---

## 16. BLACK MIRROR

Modulo de operaciones de deception y contrainteligencia con 4 capacidades:

### 16.1 Canary Forge — Documentos marcados geneticamente

Genera documentos unicos con tokens invisibles por destinatario. Si el documento se filtra, el token identifica al responsable.

**Tipos de documento:**
- **HTML**: incluye un web bug (pixel 1x1) que reporta IP + User-Agent al abrirse
- **PDF**: watermark invisible (texto 1pt color casi blanco) + metadatos unicos (Author, Subject, Creator)

**Uso desde el dashboard:**
1. Ir al tab "Black Mirror" -> sub-tab "Canary"
2. Ingresar destinatario (ej: `juan.perez`)
3. Ingresar titulo del documento
4. Seleccionar tipo: HTML (web bug) o PDF (watermark)
5. Click en "Forjar Documento Canary"
6. Distribuir el documento como si fuera real

**Deteccion de compromiso:**
- El panel muestra todos los canaries con estado SEGURO o COMPROMETIDO
- Si alguien abre un HTML canary, se registra: IP, User-Agent, fecha/hora
- Los canaries comprometidos aparecen en rojo con animate-pulse

**API directa:**
```bash
# Forjar canary
curl -X POST "http://localhost:8001/api/blackmirror/canary/forge?recipient=juan.perez&doc_type=html&title=Informe+Q3"

# Ver estado
curl http://localhost:8001/api/blackmirror/canary/status

# Web bug (se activa automaticamente al abrir HTML)
curl http://localhost:8001/api/blackmirror/canary/ping/TOKEN_AQUI
```

### 16.2 Shadow Twin — Clonacion de topologia para honeypots

Recibe resultados de escaneo nmap y genera configuraciones de honeypots que imitan exactamente los servicios detectados.

**Traps generados:**
- **SSH/Telnet**: fake_shell (responde whoami=root, id=uid=0) + credentials_honeytrap
- **HTTP/HTTPS**: fake_admin_panel (paginas /admin, /login, /config) + sql_injection_honeytrap
- **FTP**: fake_ftp (archivos backup.zip, credentials.xlsx, secret.pdf) + file_exfil_honeytrap

**Uso:**
```bash
# Generar shadows desde un escaneo
curl -X POST http://localhost:8001/api/blackmirror/shadow/twin   -H "Content-Type: application/json"   -d '{"hosts":[{"ip":"192.168.1.10","ports":[{"port":22,"service":"ssh"},{"port":80,"service":"http"}]}]}'

# Desplegar honeypots (requiere root)
sudo bash redteam/data/shadow_configs/deploy_shadows.sh
```

Los honeypots usan puerto real + 10000 (offset configurable).

### 16.3 Ghostprint — Perfil temporal de comportamiento

Aprende cuando cada host esta activo y detecta anomalias temporales.

**Flujo:**
1. Alimentar con escaneos periodicos: `POST /api/blackmirror/ghostprint/learn`
2. Consultar perfil: muestra heatmap 7x24 (168 celdas) con probabilidad por franja
3. Detecta GHOST_ANOMALY: host activo fuera de su patron historico (prob < 5%)
4. Sugiere ventanas optimas: 3 franjas con menor actividad para operar

**Uso desde el dashboard:**
1. Ir al tab "Black Mirror" -> sub-tab "Ghost"
2. Ingresar IP del host
3. Click en "Analizar"
4. Heatmap muestra actividad por dia/hora (purple = alta, oscuro = baja)
5. Si hay anomalia, alerta roja con detalles
6. Ventanas optimas en verde

**API directa:**
```bash
# Alimentar (ejecutar periodicamente, ej: cron cada hora)
curl -X POST http://localhost:8001/api/blackmirror/ghostprint/learn   -H "Content-Type: application/json"   -d '{"host":"192.168.1.10","rtt":0.5}'

# Perfil
curl http://localhost:8001/api/blackmirror/ghostprint/profile/192.168.1.10

# Ventanas optimas
curl http://localhost:8001/api/blackmirror/ghostprint/window/192.168.1.10
```

**Requisito:** Minimo 7 dias de escaneos periodicos para datos utiles. Mas de 50 observaciones para deteccion de anomalias.

### 16.4 Chaos Fingerprint — Envenenamiento de huellas

Hace que tu servidor Linux responda como un Windows IIS, Cisco IOS, Fortinet, etc. durante escaneos.

**Uso desde el dashboard:**
1. Ir al tab "Black Mirror" -> sub-tab "Chaos"
2. Ingresar puerto real a envenenar (ej: 80)
3. Seleccionar OS falso: Windows Server 2019, Cisco IOS, Fortinet, JunOS, Windows XP
4. Click en "Aplicar Chaos Rule"
5. Ejecutar el script generado como root

**Efectos:**
- `nmap -O` reportara el OS falso
- Shodan/Censys/BinaryEdge clasificaran incorrectamente
- Atacantes perderan tiempo con exploits equivocados

**API directa:**
```bash
# Aplicar regla
curl -X POST "http://localhost:8001/api/blackmirror/chaos/apply?real_port=80&fake_os=Windows+Server+2019"

# Ver reglas
curl http://localhost:8001/api/blackmirror/chaos/status

# Ejecutar (requiere root)
sudo bash redteam/data/shadow_configs/chaos_*.sh
```

**Requisitos:** `iptables` + `netcat` + root. Usar solo en entornos controlados.

### 16.5 Base de datos

Black Mirror usa `data/blackmirror.db` (SQLite) con 3 tablas:
- `bm_canaries` — documentos canary con estado de compromiso
- `ghostprints` — patrones temporales (host, hora, dia, seen, avg_rtt)
- `chaos_rules` — reglas de envenenamiento activas

---

## 17. EVIDENCIA BLINDADA

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

## 18. COMANDOS DE SINCRONIZACIÓN

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

## 19. SOLUCIÓN DE PROBLEMAS

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

### OSINT: "whois: command not found"

```bash
pkg install whois    # Termux
sudo apt install whois  # Linux
```

### OSINT: "dig: command not found"

```bash
pkg install bind-utils   # Termux
sudo apt install dnsutils  # Linux
```

### OSINT: crt.sh no devuelve resultados

- crt.sh puede tardar 10-30s en responder
- Si el dominio no tiene certificados SSL, no habra resultados de crt.sh
- El brute force con dig funciona igual (requiere dig instalado)

### OSINT: exiftool no instalado

```bash
pkg install exiftool    # Termux
sudo apt install libimage-exiftool-perl  # Linux
```

### WiFi: "Ningun metodo funciono"

```bash
# Termux: instalar termux-api
pkg install termux-api

# Dar permisos de ubicacion:
# Ajustes -> Apps -> Termux -> Permisos -> Ubicacion -> Permitir

# Verificar:
termux-wifi-scaninfo
```

### WiFi: airodump-ng no encuentra wlan0mon

```bash
# Crear interfaz monitor (requiere root)
su -c 'airmon-ng start wlan0'

# Verificar
iwconfig
# Debe mostrar wlan0mon
```

### WiFi: "No se encontro captura para este BSSID"

- Primero capturar el handshake: `POST /api/wifi/capture/{bssid}`
- Si no se capturo handshake, no hay archivo .cap para crackear
- Verificar capturas existentes: `GET /api/wifi/captures`

### WiFi: crackeo fallido ("Key no encontrada en wordlist")

- La wordlist por defecto (rockyou.txt) no contiene todas las claves posibles
- Para redes con claves complejas, usar hashcat con GPU (miles de veces mas rapido)
- Descargar rockyou.txt:
```bash
curl -L -o /usr/share/wordlists/rockyou.txt \
  https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt
```

### Black Mirror: "reportlab no instalado" (Canary PDF)

```bash
pip install reportlab
```

### "numpy metadata-generation-failed" / "ninja: build stopped: subcommand failed"

**Causa:** `pip install numpy==2.1.0` intenta compilar numpy desde codigo fuente
en Termux (Python 3.13, aarch64) porque no existe wheel precompilado para esa
combinacion. La compilacion falla con decenas de errores de C++ template.

**Solucion — usar el paquete nativo de Termux (sin compilar):**
```bash
pkg install -y python-numpy
```

Esto instala numpy ya compilado para tu arquitectura, evitando el build desde
fuente por completo. Verificar que funciono:
```bash
python3 -c "import numpy; print(numpy.__version__)"
```

Si `pkg install python-numpy` no esta disponible o falla, como ultimo recurso:
```bash
pip install numpy   # SIN version fija — deja que pip elija un wheel compatible
```

`termux_setup.sh` ya aplica este orden automaticamente (pkg primero, pip como
fallback sin pin de version).

### "bash: cd: tauri-frontend: No such file or directory"

**Causa:** Estas ejecutando el comando desde un directorio que no es la raiz
del repositorio. `tauri-frontend/` solo existe dentro de `Red-team-tauri/`.

**Solucion:** Verificar donde estas y moverte a la raiz del repo:
```bash
pwd                              # ver directorio actual
ls                                # deberia mostrar: tauri-frontend, redteam, termux_setup.sh, etc.

# Si no estas en la raiz, moverte ahi (ajusta la ruta si clonaste en otro lugar):
cd ~/Red-team-tauri              # o donde hayas clonado el repo
cd tauri-frontend && npm install && npm run build && cd ..
```

### Black Mirror: Ghostprint dice "insufficient_data"

- Necesitas minimo 7 dias de escaneos periodicos
- Alimenta con: `POST /api/blackmirror/ghostprint/learn` (ej: cron cada hora)
- Mas de 50 observaciones para deteccion de anomalias

### Black Mirror: Chaos Fingerprint no funciona

- Requiere root + iptables + netcat
```bash
sudo apt install iptables netcat-openbsd
```
- Ejecutar el script generado como root:
```bash
sudo bash redteam/data/shadow_configs/chaos_*.sh
```
- Solo usar en entornos controlados (redirige trafico real)

### Black Mirror: Shadow Twin deploy falla

- El script usa `nc -l -p` que requiere netcat-openbsd
```bash
pkg install netcat-openbsd   # Termux
sudo apt install netcat-openbsd  # Linux
```
- Ejecutar como root si los puertos son < 1024

---

## 20. IDENTIDAD VISUAL SOURCEESEAL

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
| `--ss-purple` | `#a855f7` | OSINT / Recon |
| `--ss-pink` | `#ec4899` | Black Mirror / Deception |

### Archivo de estilos

```
tauri-frontend/src/styles/source-seal.css
```

### Convenciones

- **Cyan** -> Topologia, comunicaciones, acciones primarias
- **Ambar** -> Camaras, advertencias, evidencia
- **Red** -> Critico, exploits, anomalias
- **Green** -> OK, trafico limpio, capturas
- **Purple** -> OSINT, Recon, subdominios
- **Pink** -> Black Mirror, deception, canary, chaos
- Fuente: `font-mono` (monospace)
- Estilo: minimalista, tactico, sin gradientes innecesarios

---

## NOTAS FINALES

- **Sin internet**: MURCIÉLAGO, captura de paquetes, WiFi Scanner y Black Mirror funcionan 100% offline. Threat Intel, ExploitDB y OSINT (crt.sh) necesitan conexion para consulta inicial (luego cache/offline).
- **Seguridad**: La API key (`REDTEAM_API_KEY`) protege los endpoints. Sin ella, el backend no valida acceso — configurar en produccion.
- **Rate limiting**: 60 requests/minuto por IP por defecto. Ajustable via `RATE_LIMIT`.
- **Persistencia**: Datos en `redteam/data/`. SQLite para cache Intel, pcap en `captures/`, WAVs en `murcielago_wav/`.
- **Version**: 3.0-unified. Health check: `GET /health` -> `{"version":"3.0"}`.

---

*Documentado: 2026-08-13 · SourceSeal / Red-Team-Tauri v3.2*
