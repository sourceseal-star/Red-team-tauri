# 🛡️ MANUAL OPERATIVO — Red-Team-Tauri / SourceSeal
## SealCtl Console v2.0

> **Una sola pieza. Un solo comando. Sin dependencias.**
> Node.js stdlib only — sin Python, sin Vite, sin npm install.
> Escaneo de red /24, cámaras IP, geolocalización, threat intel, forense.

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
| **Node.js** | 18+ (LTS) | Único requisito obligatorio |
| **Git** | Cualquiera | Para clonar/actualizar |
| **Termux** | Desde F-Droid | NO desde Play Store |
| **RAM** | 256 MB libre | Suficiente — Node.js es ligero |

**Opcionales** (activan funciones extra):

| Herramienta | Instalación | Activa |
|---|---|---|
| `termux-api` | `pkg install termux-api` | Wake-lock + WiFi scan |
| `nmap` | `pkg install nmap` | Escaneo avanzado de puertos |

**Sin Python. Sin pip. Sin Vite. Sin npm install.**

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

### Paso 2: Instalar Node.js

```bash
pkg update -y && pkg upgrade -y
pkg install -y nodejs-lts git
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

**Eso es todo. No hay Paso 5. No hay pip install. No hay npm install.**

---

## 3. ARRANQUE

### Comando único

```bash
bash start-termux.sh
```

Esto hace:
1. Activa wake-lock (Android no mata el proceso)
2. Verifica Node.js
3. Mata procesos anteriores en el puerto 8001
4. Arranca `sealctl/server.js`

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

## 6. SOLUCIÓN DE PROBLEMAS

### Página vacía / blanco

```bash
# Verificar que el servidor está corriendo
curl http://localhost:8001/api/health

# Si no responde, matar y reiniciar
pkill -f "server.js"
bash start-termux.sh

# Verificar que el HTML existe
ls sealctl/public/index.html
```

### "node: not found"

```bash
pkg install -y nodejs-lts
```

### "Cannot find module './lib/geo'"

```bash
# Los archivos lib/ faltan — actualizar
git pull origin main
ls sealctl/lib/
# Debe mostrar: geo.js  intel.js  iot.js
```

### Puerto 8001 ocupado

```bash
# El script de inicio mata el proceso anterior automáticamente,
# pero si persiste:
fuser -k 8001/tcp
# o
ps aux | grep server.js | grep -v grep
kill <PID>
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

## ARQUITECTURA

```
Red-team-tauri/
├── start-termux.sh          ← Script de inicio (UN comando)
├── sealctl/
│   ├── server.js            ← Backend Node.js (stdlib only)
│   ├── public/
│   │   └── index.html       ← Dashboard (un solo HTML)
│   └── lib/
│       ├── geo.js           ← Geolocalización (ipwho.is)
│       ├── intel.js         ← Threat scoring (abuse.ch + DNS)
│       └── iot.js           ← TCP scan + RTSP + SIP + HTTP probe
├── evidence/                ← Reportes forenses (auto-generado)
└── backend/
    └── dashboard_server.py  ← Backend Python (referencia, NO necesario)
```

**No necesita:**
- ❌ Python / pip
- ❌ npm install / node_modules
- ❌ Vite / Webpack
- ❌ API keys
- ❌ Bases de datos
- ❌ Redis / Docker

**Solo necesita:**
- ✅ Node.js 18+
- ✅ `node sealctl/server.js`
