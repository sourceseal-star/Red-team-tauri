# 🛡️ MANUAL OPERATIVO — Red-Team-Tauri / SourceSeal
## SourceSeal Console v4.1

> **Backend Python/FastAPI + frontend React/Vite.**
> El arranque unificado sirve API y frontend real en el puerto 8001.
> Los escaneos deben ejecutarse únicamente dentro de un alcance autorizado.

---

## 📋 TABLA DE CONTENIDOS

1. [Requisitos](#1-requisitos)
2. [Instalación — Termux](#2-instalación--termux)
3. [Arranque](#3-arranque)
4. [Dashboard — Pestañas](#4-dashboard--pestañas)
5. [API — Endpoints](#5-api--endpoints)
6. [Solución de Problemas](#6-solución-de-problemas)
7. [Changelog](#7-changelog)

---

## 1. REQUISITOS

| Componente | Requisito | Nota |
|---|---|---|
| **Python** | 3.10+ | Backend FastAPI |
| **Node.js** | 18+ (LTS) | Necesario para compilar el frontend |
| **Git** | Cualquiera | Para clonar/actualizar |
| **Termux** | Desde F-Droid | NO desde Play Store |
| **RAM** | 512 MB libre | Recomendado para reconocimiento de red |

**Opcionales** (activan funciones extra):

| Herramienta | Instalación | Activa |
|---|---|---|
| `termux-api` | `pkg install termux-api` | Wake-lock + WiFi scan |
| `nmap` | `pkg install nmap` | Escaneo avanzado de puertos y topología |
| `tcpdump` | `pkg install tcpdump` | Traffic Analyzer (captura de paquetes) |
| `whois` | `pkg install whois` | OSINT WHOIS lookup |
| `bind-utils` | `pkg install bind-utils` | DNS recon (dig) |

El script instala las dependencias Python que falten y compila el frontend
únicamente si todavía no existe `tauri-frontend/dist/`.

---

## 2. INSTALACIÓN — TERMUX

### Paso 1: Termux + permisos

```bash
# Descargar de F-Droid (NO Play Store)
# https://f-droid.org/packages/com.termux/

# Permisos de almacenamiento
termux-setup-storage

# Sin restricciones de bateria:
# Ajustes → Apps → Termux → Bateria → Sin restricciones
```

### Paso 2: Instalar Python y Node.js

```bash
pkg update -y && pkg upgrade -y
pkg install -y python nodejs-lts git openssl curl
```

### Paso 3: Clonar el repo

```bash
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri
```

### Paso 4: (Opcional) termux-api para wake-lock

```bash
pkg install -y termux-api
```

La primera ejecución puede instalar dependencias Python y compilar el frontend.

---

## 3. ARRANQUE

### Comando único — recomendado

```bash
bash arrancar.sh
```

`arrancar.sh` hace todo en 7 pasos:
1. Activa wake-lock (Android no mata el proceso)
2. `git pull` para sincronizar código
3. Verifica e instala dependencias del sistema (python, nodejs, nmap, tcpdump, etc.)
4. Verifica dependencias Python (fastapi, uvicorn, httpx, pydantic, psutil)
5. Crea `.env` con API key local + espacios para API keys OSINT (preserva .env existente)
6. Compila `tauri-frontend` si falta `dist/`
7. Mata procesos anteriores y arranca el backend en `:8001`

### Alternativa: start-termux.sh

```bash
bash start-termux.sh
```

Similar a `arrancar.sh` pero además:
- Inicia el gateway mesh en `:8080` (opcional)
- Útil si necesitas federación entre dispositivos

Para omitir el gateway:
```bash
START_GATEWAY=0 bash start-termux.sh
```

### Actualizar desde GitHub

```bash
# Opción 1: arrancar.sh ya hace git pull automáticamente
bash arrancar.sh

# Opción 2: sync.sh (más agresivo — reset --hard)
bash sync.sh

# Opción 3: manual
git pull origin main
bash arrancar.sh
```

### Abrir el dashboard

En tu celular, abre el navegador:
```
http://localhost:8001
```

El gateway mesh, cuando está activo, se comprueba en:

```bash
curl http://localhost:8080/health
```

Desde otro dispositivo en la misma WiFi:
```
http://TU_IP_LOCAL:8001
```

Para saber tu IP local en Termux:
```bash
ip addr show wlan0 | grep inet
# o
ifconfig wlan0
```

### Verificar que está corriendo

```bash
curl http://localhost:8001/api/health
# Respuesta: {"status":"ok","version":"3.0-unified",...}
```

### Configurar API Keys OSINT

Las API keys se configuran en el archivo `.env` (creado automáticamente).
Edítalo con tu editor preferido:

```bash
nano .env
```

```bash
# === API KEYS OSINT (todas tienen tier gratis) ===

# AbuseIPDB: https://www.abuseipdb.com/account/api — gratis, 1000 checks/día
ABUSEIPDB_KEY=tu-key-aqui

# Shodan: https://www.shodan.io/dashboard — cuenta gratis
SHODAN_API_KEY=tu-key-aqui

# Hunter.io (emails): https://hunter.io/api-keys — opcional
HUNTER_API_KEY=tu-key-aqui
```

**Importante:** Todos los módulos usan `ABUSEIPDB_KEY` (sin `_API`).
Si una clave no funciona, verifica el nombre de la variable en `.env`.

Los módulos funcionan sin keys con fallbacks graceful.

---

## 4. DASHBOARD — PESTAÑAS

### 🌐 Topología de Red (escaneo de red /24)

La pestaña principal. Escanea los 254 hosts de tu subred en tiempo real.

**Nodo central:** Muestra tu dispositivo real con ícono de servidor,
hostname del sistema e IP local detectada automáticamente (no un
placeholder genérico). Anillo de pulso animado durante el escaneo.

1. **Botón "Auto"** — detecta tu subred automáticamente
2. **Escribir manual** — `192.168.1.0/24`
3. **"Escanear Red"** — empieza el escaneo SSE en vivo
4. Cada host aparece al instante con su tipo:
   - 📷 Cámara (puerto 554 detectado)
   - 🔧 Router (puertos 22 + 80)
   - 📡 IoT (puerto 1883)
   - 🌐 Web (puerto 80/8080)
   - 🖥️ Windows (puerto 3389)
   - ☎️ VoIP (puerto 5060)
5. **Click en cualquier host** → va a Overview y lo analiza completo

### Overview

Vista combinada de Geo + Intel + IoT para una IP específica.
- Escribe la IP → "Analizar" → resultados en 3 columnas.

### 📍 Geo

Geolocalización real via ipwho.is (HTTPS, sin API key):
- País, ciudad, coordenadas, ISP, AS
- Detección de proxy/VPN/hosting/móvil
- Link a OpenStreetMap

### 🛡️ Intel

Score de riesgo 0-100:
- Blocklist abuse.ch
- rDNS lookup
- Detección de hosting/proxy/Tor/bulletproof ASN
- Desglose del score por factor
- AbuseIPDB si la API key está configurada

### 📡 IoT

Detección de cámaras IP, radio streaming y VoIP:
- TCP probe a 10 puertos IoT
- RTSP OPTIONS handshake
- SIP/UDP probe
- HTTP path probing (ISAPI, ONVIF, magicBox, etc.)
- Fingerprinting de vendor (Hikvision, Dahua, Axis, Uniview)
- Botón "Cámara" para escaneo profundo

### 📊 Traffic Analyzer

Captura y análisis de tráfico de red en tiempo real:
- Selector de interfaz (any, wlan0, eth0, wlan1)
- Selector de duración (10s, 15s, 30s, 60s)
- Stats grid: paquetes totales, protocolos detectados, anomalías
- Distribución de protocolos con barras de color por tipo:
  - HTTPS/TLS, HTTP, DNS, ARP, ICMP, TCP, UDP
- Top Talkers (IPs origen más activas)
- Top Destinos (IPs destino más activas)
- Top Servicios (puertos con nombre real del servicio)
- Detección de anomalías: ARP Storm, Port Scan

**Requiere:** `tcpdump` instalado (`pkg install tcpdump`)

### 🔬 Forense

Análisis de archivos (drag & drop o tap):
- Hash SHA-256 + MD5
- Entropía de Shannon con gauge de color (verde/amarillo/rojo)
- 10 patrones IOC: emails, URLs, IPv4, JWT, AWS keys, GitHub PATs, OpenAI keys, BTC wallets, Base64, Windows paths
- Cadena de custodia SSP-ZKP-2048-L4
- Máximo 50MB

### 📄 JSON

Respuesta JSON cruda del último análisis.

---

## 5. API — ENDPOINTS

### 5.0 Core

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard HTML |
| GET | `/api/health` | Estado del servidor |
| GET | `/api/geo?ip=X` | Geolocalización (ipwho.is) |
| GET | `/api/intel?ip=X` | Threat score (abuse.ch + DNS + AbuseIPDB) |
| GET | `/api/iot?ip=X` | Scan IoT de un host |
| GET | `/api/full?ip=X` | Geo + Intel + IoT combinado |
| POST | `/api/scan-batch` | Escaneo batch `{ips:[...]}` |
| POST | `/api/scan/network` | Scan red /24 (254 hosts) |
| GET | `/api/scan/network/stream?subnet=X` | Scan red SSE en vivo |
| GET | `/api/scan/cameras?ip=X` | Escaneo profundo cámara |
| POST | `/api/forensics/analyze` | Análisis forense (multipart) |
| GET | `/api/forensics/tools` | Estado de herramientas |
| GET | `/api/forensics/patterns` | Lista de patrones IOC |
| GET | `/api/stream?ip=X` | SSE streaming single IP |

### 5.1 Topología y Captura de Tráfico

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/scan/topology` | Escaneo topológico de red (nmap -sn) — devuelve `local_ip`, `local_hostname` |
| POST | `/api/scan/cameras` | Detección de cámaras ONVIF/RTSP |
| GET | `/api/enhanced/cameras` | Listado de cámaras detectadas |
| POST | `/api/enhanced/discover/all` | Descubrimiento completo de red |
| GET | `/api/scan/video-urls?ip=X` | URLs de video streaming detectadas |
| POST | `/api/capture/start` | Iniciar captura de tráfico (tcpdump) |
| POST | `/api/capture/stop/{session_id}` | Detener captura y obtener análisis |
| GET | `/api/capture/active` | Capturas activas |

**Análisis de captura incluye:**
- `total_packets`: conteo total
- `protocols`: distribución por protocolo (HTTPS/TLS, HTTP, DNS, ARP, ICMP, TCP, UDP)
- `top_talkers`: IPs origen más activas (top 6)
- `top_destinations`: IPs destino más activas (top 6)
- `top_services`: puertos/servicios más frecuentes con nombre real (top 6)
- `anomalies`: ARP Storm, Port Scan detectados automáticamente

### 5.2 OSINT Avanzado

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/osint/whois/{domain}` | WHOIS lookup |
| GET | `/api/osint/dns/{domain}` | DNS recon (A, MX, TXT, NS, SPF, DMARC) |
| POST | `/api/osint/subdomains` | Enumeración de subdominios |
| GET | `/api/osint/threat-intel/{ip}` | Threat intelligence IP |
| POST | `/api/osint/email` | Email OSINT (MX, SPF, DMARC, hash SHA-256) |
| GET | `/api/osint/emails/{domain}` | Búsqueda de emails por dominio (Hunter.io + pattern guess) |
| GET | `/api/osint/headers?url=` | HTTP header fingerprinting |
| GET | `/api/osint/full/{domain}` | OSINT completo |
| GET | `/api/osint/results` | Resultados guardados BD |
| GET | `/api/osint/google?q=` | Google Custom Search |
| GET | `/api/osint/shodan/{ip}` | Shodan host lookup |
| GET | `/api/osint/virustotal/{indicator}` | VirusTotal lookup |
| GET | `/api/osint/censys/{ip}` | Censys lookup |
| GET | `/api/osint/github/{username}` | GitHub user recon |
| POST | `/api/osint/social` | Social media username search |

### 5.3 Interceptor Avanzado

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/interceptor/analyze/request` | Analizar request HTTP |
| POST | `/api/interceptor/analyze/response` | Analizar response HTTP |
| GET | `/api/interceptor/flows` | Flujos interceptados |
| GET | `/api/interceptor/alerts` | Alertas de inyección |
| GET | `/api/interceptor/stats` | Estadísticas SIEM |
| DELETE | `/api/interceptor/flows` | Limpiar BD |
| POST | `/api/interceptor/decode` | Decodificar payload |
| GET | `/api/interceptor/cert/{host}` | Análisis certificado SSL |
| POST | `/api/interceptor/analyze/user-agent` | Analizar User-Agent |
| GET | `/api/interceptor/rate-check/{ip}` | Rate limit check |

### Detecciones del Interceptor (CWE)
- SQL Injection (CWE-89)
- XSS (CWE-79)
- Command Injection (CWE-78)
- Path Traversal (CWE-22)
- SSRF (CWE-918)
- XXE (CWE-611)
- LFI/RFI (CWE-98)
- LDAP Injection (CWE-90)
- NoSQL Injection (CWE-943)

### API Keys OSINT

```bash
# Variables de entorno (.env)
ABUSEIPDB_KEY=tu-key           # AbuseIPDB (todos los módulos usan este nombre)
SHODAN_API_KEY=tu-key           # Shodan
HUNTER_API_KEY=tu-key           # Hunter.io (emails)
VIRUSTOTAL_API_KEY=tu-key       # VirusTotal
CENSYS_API_ID=tu-id             # Censys (ID + Secret)
CENSYS_API_SECRET=tu-secret
GOOGLE_API_KEY=tu-key           # Google Custom Search
GOOGLE_CSE_ID=tu-cse-id
GITHUB_TOKEN=tu-token           # GitHub recon
```

Los módulos funcionan sin keys con fallbacks graceful.

---

## 6. SOLUCIÓN DE PROBLEMAS

### Página vacía / blanco

```bash
# Verificar que el servidor está corriendo
curl http://localhost:8001/api/health

# Si no responde, matar y reiniciar
pkill -f "dashboard_server.py"
bash arrancar.sh

# Verificar que el HTML existe
ls tauri-frontend/dist/index.html
```

### "python3: not found"

```bash
pkg install -y python
```

### El frontend no compila

```bash
cd tauri-frontend
npm install --legacy-peer-deps
npm run build
```

### Puerto 8001 ocupado

```bash
# arrancar.sh ya mata procesos anteriores automáticamente,
# pero si persiste:
fuser -k 8001/tcp
# o
ps aux | grep dashboard_server.py | grep -v grep
kill <PID>
```

### Traffic Analyzer muestra error "tcpdump no instalado"

```bash
pkg install tcpdump
```

### AbuseIPDB no devuelve datos

Verifica que en tu `.env` la variable se llama `ABUSEIPDB_KEY` (no `ABUSEIPDB_API_KEY`).

```bash
grep ABUSEIPDB .env
# Debe mostrar: ABUSEIPDB_KEY=tu-key
```

### Gateway Mesh no responde en 8080

```bash
curl http://localhost:8080/health
tail -f sourceseal-gateway.log
```

Si no necesitas federación, arranca solo el dashboard:

```bash
START_GATEWAY=0 bash start-termux.sh
```

### Termux se cierra solo

```bash
# Instalar wake-lock
pkg install -y termux-api
termux-wake-lock

# Y en Android:
# Ajustes → Apps → Termux → Bateria → Sin restricciones
```

### No encuentra hosts en el escaneo

- Verifica que estás en la red WiFi correcta
- La subred debe ser correcta: `192.168.1.0/24` (no `192.168.0.0/24`)
- Usa el botón "Auto" para detectar tu subred
- El escaneo tarda ~30 segundos (254 hosts × 15 puertos)
- Si hay 0 hosts, prueba: `curl http://localhost:8001/api/iot?ip=192.168.1.1`

### El escaneo de red es lento

Es normal — 254 hosts × 15 puertos = 3,810 probes TCP.
El SSE streaming muestra resultados en vivo, no esperes al final.

---

### 🌐 Internacionalización (i18n)

El dashboard soporta 3 idiomas: Español, 简体中文, English.
- Selector de idioma en la barra superior
- Los módulos v4.0 usan nombres en chino simplificado
- Datos y elementos de la interfaz son traducibles
- Preferencia guardada en localStorage

## ARQUITECTURA

```
Red-team-tauri/
├── arrancar.sh                ← Arranque completo (7 pasos, recomendado)
├── start-termux.sh            ← Arranque Termux con gateway mesh opcional
├── sync.sh                    ← Sincronización forzada + rebuild
├── .env.example               ← Template de API keys
├── gateway/
│   └── mesh_server.py         ← Gateway Mesh :8080
├── redteam/scripts/
│   └── dashboard_server.py    ← Backend FastAPI unificado :8001
├── backend/
│   ├── dashboard_server.py    ← Backend alternativo (FastAPI)
│   └── modules/
│       └── osint_advanced.py   ← Módulos OSINT avanzados
├── tauri-frontend/
│   ├── src/components/
│   │   ├── NetworkTopology.tsx ← Topología de red con hostname/IP real
│   │   ├── TrafficMonitor.tsx  ← Traffic Analyzer con protocolos reales
│   │   ├── WarRoom.tsx         ← War Room (Comms/Intel/Exploits/Traffic)
│   │   └── ...
│   └── dist/                   ← Build de producción (servido por el backend)
└── docs/
```

## 7. CHANGELOG

### v4.1 (2026-08-18) — commits 259f28c, dd59d0d

**Topología de Red:**
- Nodo central reemplazado: texto "YO" → ícono Server profesional
- Muestra hostname real del dispositivo + IP local detectada
- Anillo de pulso animado durante escaneo
- Backend `/api/scan/topology` ahora devuelve `local_ip` y `local_hostname`

**Traffic Analyzer:**
- Parser de tcpdump reescrito: clasifica HTTPS/TLS, HTTP, DNS, ARP, ICMP, TCP, UDP
- Nuevos paneles: Top Talkers, Top Destinos, Top Servicios
- Selector de duración de captura (10/15/30/60s)
- Barras de protocolo con color por tipo
- Manejo de errores visible en UI (no más alert())

**Fix de consistencia:**
- `osint_advanced.py`: `ABUSEIPDB_API_KEY` → `ABUSEIPDB_KEY` (alineado con .env, arrancar.sh, y los demás backends)

### v4.0 (2026-08-14) — commit ab107d9

- Integración OSINT Advanced: Google, Shodan, VirusTotal, Censys, GitHub, Social
- Interceptor Advanced: XXE, LFI/RFI, LDAP, NoSQL, cert, UA, decoder
- i18n: Español, 简体中文, English
