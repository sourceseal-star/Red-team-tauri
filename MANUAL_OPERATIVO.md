# 🛡️ MANUAL OPERATIVO — Red-Team-Tauri / SourceSeal
## SourceSeal Console v4.0

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
| `nmap` | `pkg install nmap` | Escaneo avanzado de puertos |

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

### Comando único

```bash
bash start-termux.sh
```

Esto hace:
1. Activa wake-lock (Android no mata el proceso)
2. Verifica Python y dependencias FastAPI
3. Crea un `.env` local con una API key si no existe
4. Compila `tauri-frontend` si falta `dist/`
5. Arranca el gateway mesh en `:8080`
6. Arranca el backend unificado en `:8001`

Para ejecutar únicamente el backend y omitir la federación:

```bash
START_GATEWAY=0 bash start-termux.sh
```

### Actualizar desde GitHub

```bash
bash start-termux.sh --sync
# o manualmente:
git pull origin main
bash start-termux.sh
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
# Respuesta: {"status":"ok","version":"2.0.0",...}
```

---

## 4. DASHBOARD — PESTAÑAS

### 🌐 Red (escaneo de red /24)

La pestaña principal. Escanea los 254 hosts de tu subred en tiempo real.

1. **Botón "Auto"** — detecta tu subred automáticamente via WebRTC
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

### 📡 IoT

Detección de cámaras IP, radio streaming y VoIP:
- TCP probe a 10 puertos IoT
- RTSP OPTIONS handshake
- SIP/UDP probe
- HTTP path probing (ISAPI, ONVIF, magicBox, etc.)
- Fingerprinting de vendor (Hikvision, Dahua, Axis, Uniview)
- Botón "Cámara" para escaneo profundo

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

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Dashboard HTML |
| GET | `/api/health` | Estado del servidor |
| GET | `/api/geo?ip=X` | Geolocalización (ipwho.is) |
| GET | `/api/intel?ip=X` | Threat score (abuse.ch + DNS) |
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

---


## 5.1 API v4.0 — OSINT AVANZADO

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/osint/whois/{domain}` | WHOIS lookup |
| GET | `/api/osint/dns/{domain}` | DNS recon (A, MX, TXT, NS, SPF, DMARC) |
| POST | `/api/osint/subdomains` | Enumeración de subdominios |
| GET | `/api/osint/threat-intel/{ip}` | Threat intelligence IP |
| POST | `/api/osint/email` | Email OSINT |
| GET | `/api/osint/headers?url=` | HTTP header fingerprinting |
| GET | `/api/osint/full/{domain}` | OSINT completo |
| GET | `/api/osint/results` | Resultados guardados BD |
| GET | `/api/osint/google?q=` | Google Custom Search |
| GET | `/api/osint/shodan/{ip}` | Shodan host lookup |
| GET | `/api/osint/virustotal/{indicator}` | VirusTotal lookup |
| GET | `/api/osint/censys/{ip}` | Censys lookup |
| GET | `/api/osint/github/{username}` | GitHub user recon |
| POST | `/api/osint/social` | Social media username search |

## 5.2 API v4.0 — INTERCEPTOR AVANZADO

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

### API Keys opcionales (v4.0)
```bash
export SHODAN_API_KEY="tu-key"
export VIRUSTOTAL_API_KEY="tu-key"
export ABUSEIPDB_API_KEY="tu-key"
export CENSYS_API_ID="tu-id"
export CENSYS_API_SECRET="tu-secret"
export GOOGLE_API_KEY="tu-key"
export GOOGLE_CSE_ID="tu-cse-id"
export GITHUB_TOKEN="tu-token"
```
Los módulos funcionan sin keys con fallbacks graceful.

## 6. SOLUCIÓN DE PROBLEMAS

### Página vacía / blanco

```bash
# Verificar que el servidor está corriendo
curl http://localhost:8001/api/health

# Si no responde, matar y reiniciar
pkill -f "dashboard_server.py"
bash start-termux.sh

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
# El script de inicio mata el proceso anterior automáticamente,
# pero si persiste:
fuser -k 8001/tcp
# o
ps aux | grep dashboard_server.py | grep -v grep
kill <PID>
```

### Gateway Mesh no responde en 8080

```bash
curl http://localhost:8080/health
tail -f /tmp/sourceseal-gateway.log
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
├── start-termux.sh          ← Arranque Termux: gateway + dashboard
├── gateway/
│   └── mesh_server.py       ← Gateway Mesh :8080
├── redteam/scripts/
│   └── dashboard_server.py  ← Backend FastAPI unificado :8001
├── tauri-frontend/
│   ├── src/                 ← React + TypeScript
│   └── dist/                ← Frontend servido por FastAPI
└── backend/modules/         ← Reconocimiento complementario
```

**El sistema requiere:**
- ✅ Python 3.10+ y dependencias FastAPI
- ✅ Node.js 18+ para compilar el frontend
- ✅ Un alcance autorizado para escaneos reales
- ❌ Bases de datos
- ❌ Redis / Docker

**Solo necesita:**
- ✅ Node.js 18+
- ✅ `node sealctl/server.js`
