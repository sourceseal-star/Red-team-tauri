# 🛡️ MANUAL OPERATIVO — Red-Team-Tauri / SourceSeal
## SourceSeal Console v6.0 — ARTO + LEVIATHAN UNIFIED

> **Última actualización:** 2026-08-30
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
6. [ARTO — Sistema AI Autónomo](#6-arto--sistema-ai-autónomo)
7. [VPN — Captura de Tráfico](#7-vpn--captura-de-tráfico)
8. [Solución de Problemas](#8-solución-de-problemas)
9. [Changelog](#9-changelog)

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

### Ejecutar la copia local — recomendado

```bash
bash arrancar_termux.sh
```

`arrancar_termux.sh` ejecuta la copia local sin `git pull`, `reset`, `stash` ni
instalación de paquetes. Levanta el dashboard, Commander integrado y PHANTOM.

### Preparar o actualizar todo

```bash
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

Este recuperador sincroniza ambos repositorios solo después de comprobar que no
hay cambios locales sin guardar; después instala dependencias, compila el
frontend y arranca el sistema unificado. `arrancar.sh` queda como alias
compatible de este recuperador.

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

### Actualizar desde GitHub sin perder cambios

```bash
# 1. Detener con Ctrl+C y revisar cambios
git status --short

# 2. Guardar cambios explícitamente (commit o stash)
git add -A && git commit -m "Cambios locales de Termux"

# 3. Sincronizar y volver a arrancar
bash termux_recover.sh
```

Si no quieres guardar todavía los cambios, ejecuta `bash arrancar_termux.sh`.
No uses `git reset --hard` para resolver un arranque fallido.

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
# Respuesta: {"status":"ok","version":"4.0-unified",...}
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
2. **Escribir manual** — `192.168.1.0/24` (o /22, /20, /16 — soporta cualquier CIDR)
3. **"Escanear Red"** — empieza el escaneo SSE en vivo

> **Redes grandes (/22, /20, /16):** El sistema ahora usa chunking automático
> (lotes de 64 hosts) para no saturar la memoria del celular. Los resultados
> aparecen en vivo a medida que encuentra hosts. El escaneo de 1022 IPs (/22)
> tarda ~2-3 minutos pero NO colapsa el backend.
>
> Endpoint SSE directo: `GET /api/scan/network/stream?subnet=192.168.0.0/22`
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

## 6. ARTO — SISTEMA AI AUTÓNOMO

### 6.1 ¿Qué es ARTO?

ARTO (Automated Red Team Operations) es un sistema de operaciones autónomas
de red team con inteligencia artificial. Se ejecuta como parte del backend
FastAPI y se inicia automáticamente al arrancar el servidor.

### 6.2 Arquitectura

```
arto/
├── __init__.py              # Clase ARTO principal + start/stop
├── core/
│   ├── decision_engine.py   # Toma de decisiones autónomas
│   ├── learning_engine.py   # Aprendizaje adaptativo
│   ├── prediction_engine.py # Predicción de amenazas
│   ├── action_engine.py     # Ejecución de acciones autónomas
│   └── behavior_analyzer.py# Análisis de comportamiento
├── modules/
│   ├── attack_simulator.py  # Simulación de ataques (integra enhanced_recon + interceptor)
│   ├── vpn_interceptor.py   # Captura de tráfico real via VpnService
│   ├── defense_orchestrator.py # Orquestación de defensa
│   └── report_generator.py  # Generación de informes
├── memory/
│   ├── memory_storage.py    # Persistencia en SQLite
│   └── knowledge_base.py    # Base de conocimiento
├── utils/
│   ├── threat_intelligence.py # Feeds de amenazas
│   ├── risk_assessor.py     # Evaluación de riesgos
│   ├── pattern_recognizer.py # Reconocimiento de patrones
│   ├── anomaly_detector.py  # Detección de anomalías
│   └── temporal_analyzer.py # Análisis temporal
├── api/
│   └── arto_router.py       # Router FastAPI con 23 endpoints
└── models/
    ├── action.py            # Modelo de acción
    ├── decision.py          # Modelo de decisión
    ├── knowledge.py         # Modelo de conocimiento
    ├── prediction.py        # Modelo de predicción
    ├── report.py            # Modelo de informe
    └── threat.py            # Modelo de amenaza
```

### 6.3 Arranque automático

ARTO se inicializa automáticamente cuando `dashboard_server.py` arranca,
mediante eventos de FastAPI:

- **Startup**: inicializa memoria SQLite, knowledge_base, threat_intel,
  learning_engine, prediction_engine, attack_simulator (con enhanced_recon +
  interceptor), defense_orchestrator y vpn_interceptor.
- **Shutdown**: guarda memoria y knowledge_base en SQLite.

**No requiere llamada manual a `/api/arto/start`** — ARTO ya está corriendo
cuando el health check pasa.

### 6.4 Endpoints ARTO

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/arto/status` | Estado del sistema ARTO |
| POST | `/api/arto/start` | Iniciar ARTO (manual) |
| POST | `/api/arto/stop` | Detener ARTO |
| POST | `/api/arto/operation/{type}` | Ejecutar operación (scan, simulate, monitor, investigate, defend) |
| GET | `/api/arto/operations` | Listar operaciones |
| GET | `/api/arto/operations/{id}` | Detalle de operación |
| GET | `/api/arto/predictions` | Predicciones de amenazas |
| POST | `/api/arto/predict` | Generar predicción |
| POST | `/api/arto/defend` | Ejecutar defensa autónoma |
| POST | `/api/arto/simulate` | Simular ataque |
| GET | `/api/arto/threats` | Lista de amenazas |
| GET | `/api/arto/templates` | Plantillas de ataque disponibles |
| POST | `/api/arto/analyze/behavior` | Analizar comportamiento |
| GET | `/api/arto/memory/stats` | Estadísticas de memoria SQLite |
| GET | `/api/arto/knowledge/stats` | Estadísticas de knowledge base |
| GET | `/api/arto/stats` | Estadísticas generales |
| WS | `/api/arto/ws` | WebSocket para eventos en tiempo real |

### 6.5 Frontend ARTO

El panel de ARTO se encuentra en el sidebar con el ícono Cpu y badge "AI".
Tiene 5 pestañas:

1. **🎯 Operaciones** — Escaneo, simulación, monitoreo, investigación, defensa
2. **🔮 Predicciones** — Predicciones de amenazas con 24h de anticipación
3. **🛡️ Amenazas** — Lista de amenazas activas
4. **🎭 Simulaciones** — Plantillas de ataque (Web, Red, API, Auth, Social)
5. **🔌 Tráfico** — Captura de tráfico en tiempo real (VPN)

### 6.6 Persistencia

ARTO usa SQLite (`arto/data/arto_memory.db`) para almacenar:
- Decisiones tomadas
- Resultados de operaciones
- Patrones aprendidos
- Predicciones generadas
- Base de conocimiento

Los datos persisten entre reinicios. Al detener el servidor, el evento
`shutdown` guarda todo correctamente.

### 6.7 Integración con módulos existentes

ARTO se conecta automáticamente con:
- **enhanced_recon.py** — OSINT local (ONVIF, SSDP, SNMP, NetBIOS, mDNS)
- **osint_bridge.py** — OSINT v2 (WHOIS + DNS + Subdominios + Threat Intel) via `_recon_module_wrapper`
- **interceptor.py** — Interceptor TLS (MITM, SQLi, XSS, SSRF, LFI/RFI)
- **vpn_interceptor.py** — Captura de tráfico via Android VpnService

Si un módulo no está disponible, ARTO funciona en modo degradado sin errores.

> **FIX (2026-08-20):** El `_recon_module_wrapper` ahora reordena `sys.path` antes
> de importar `modules.osint_bridge`, resolviendo el conflicto de paquetes
> `modules` entre `arto/modules/` y `backend/modules/`. Antes de este fix,
> ARTO caía silenciosamente en modo degradado y nunca ejecutaba OSINT real.

---

## 7. VPN — CAPTURA DE TRÁFICO

### 7.1 ¿Qué hace?

La captura de tráfico usa Android VpnService para interceptar TODO el tráfico
del dispositivo (TCP, UDP, ICMP, HTTP, HTTPS, DNS) **sin root**. Los paquetes
se envían al backend Python donde ARTO los analiza con 6 reglas:

| Regla | Severidad | Descripción |
|-------|-----------|-------------|
| Port Scanning | HIGH | Múltiples conexiones a puertos diferentes en poco tiempo |
| Brute Force | CRITICAL | Múltiples intentos de conexión fallidos |
| Data Exfiltration | HIGH | Transferencia de grandes cantidades de datos |
| C2 Communication | CRITICAL | Comunicación con servidores C2 conocidos |
| DNS Tunneling | HIGH | Tráfico DNS sospechoso |
| Beaconing | MEDIUM | Comunicación periódica con servidor externo |

### 7.2 Endpoints de tráfico

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/arto/traffic/start` | Iniciar captura de tráfico |
| POST | `/api/arto/traffic/stop` | Detener captura |
| GET | `/api/arto/traffic/stats` | Estadísticas de tráfico |
| GET | `/api/arto/traffic/packets` | Paquetes capturados (?limit=100) |
| GET | `/api/arto/traffic/analysis` | Análisis completo |
| POST | `/api/arto/traffic/clear` | Limpiar estadísticas |

### 7.3 Android VpnService

Los archivos Java van en el proyecto Tauri (NO en el backend Python):

```
android/app/src/main/java/com/redteam/tauri/vpn/
├── ARTOVpnService.java  # Servicio VPN que intercepta tráfico
├── VpnManager.java      # Gestor de VPN (start/stop/envío)
```

Permisos necesarios en `AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.BIND_VPN_SERVICE" />
<service android:name=".vpn.ARTOVpnService"
         android:permission="android.permission.BIND_VPN_SERVICE"
         android:foregroundServiceType="vpn">
    <intent-filter>
        <action android:name="android.net.VpnService" />
    </intent-filter>
</service>
```

### 7.4 Requisitos VPN

- Android 5.0+ (API 21)
- Solo una VPN activa a la vez
- El usuario debe aprobar la conexión VPN manualmente
- El servicio muestra una notificación permanente

---

## 8. SOLUCIÓN DE PROBLEMAS

### Problemas con ARTO

**ARTO no arranca:**
```bash
# Verificar si ARTO está activo
curl localhost:8001/api/arto/status

# Si responde error, revisar logs del backend:
# En Termux:
python3 redteam/scripts/dashboard_server.py 2>&1 | grep ARTO

# En Replit:
# Revisar la consola de Replit, buscar líneas con [ARTO]
```

**ARTO no inicializa (modo degradado):**
- ARTO funciona en modo degradado si enhanced_recon o interceptor no están disponibles
- **FIX (2026-08-20):** Si ARTO aparece como "degradado" pero los módulos SÍ están
  presentes, el problema era un conflicto de paquetes Python `modules` entre
  `arto/modules/` y `backend/modules/`. Ya está resuelto — al hacer `git pull`
  y reiniciar, ARTO debería conectar OSINT correctamente.
- Para verificar: `GET /api/arto/status` debería mostrar `"running": true`
  y las operaciones de scan deberían devolver datos reales (no vacíos).
- No es un error fatal — ARTO sigue operando con capacidades reducidas
- Para integración completa, asegurar que `backend/modules/enhanced_recon.py` existe

**Error en memoria SQLite:**
```bash
# La base de datos está en arto/data/arto_memory.db
# Si se corrompe, eliminarla y se recrea automáticamente:
rm -f arto/data/arto_memory.db
# Reiniciar el servidor
```

**VpnInterceptor no recibe paquetes:**
- El VpnService (Java) debe estar activo en Android
- Verificar que no haya otra VPN activa
- El usuario debe aprobar el diálogo de VPN
- Verificar que el backend Python esté corriendo en el puerto 8001

### Problemas generales

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

## 9. LEVIATHAN UNIFIED — MÓDULOS DE RED TEAM
## 10. DETECCIÓN DE OBJETOS CON IA (ONNX)
## 11. VERIFICACIÓN DE MÓDULOS

## 9. LEVIATHAN UNIFIED — MÓDULOS DE RED TEAM

### 9.1 ¿Qué es LEVIATHAN?

LEVIATHAN v3.1 es el sistema de módulos de Red Team integrado en el dashboard.
Se monta via `include_router` en `dashboard_server.py` — si falla, el dashboard sigue funcionando.

**Dos routers activos:**
- `/api/leviathan/*` — Router básico (CRUD de cameras/scans/alerts)
- `/api/v1/*` — Router unificado (scanners, exploiters, AI, reporters)

### 9.2 Arquitectura

```
leviathan_core/
├── core/engine.py              # Motor de ejecución
├── modules/
│   ├── scanners/ (6)           # network, rtsp, onvif, http_fingerprint, camera, service
│   ├── exploiters/ (5)         # hikvision_rce, dahua_backdoor, generic_brute, kraken, chain
│   ├── ai_analyzers/ (4)       # object_detection, anomaly, behavior, threat_scoring
│   └── reporters/ (3)          # json, html, pdf
├── api/
│   ├── leviathan_router.py     # /api/leviathan/*
│   └── integration_router.py  # /api/v1/* (unificado)
├── config/profiles.json        # Perfiles de escaneo + OPSEC + camera defaults
└── tools/
    ├── convert_yolo_onnx.py   # Conversión YOLOv8 a ONNX (para PC)
    └── verify_modules.py      # Verificador de módulos
```

### 9.3 Endpoints LEVIATHAN (/api/v1/*)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/status` | Estado completo del sistema |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/profiles` | Perfiles de escaneo disponibles |
| POST | `/api/v1/scan/network` | Escaneo de red (con perfil) |
| POST | `/api/v1/scan/cameras` | Detección de cámaras IP |
| POST | `/api/v1/scan/rtsp` | Detección RTSP |
| POST | `/api/v1/scan/onvif` | Detección ONVIF |
| POST | `/api/v1/scan/services` | Escaneo de servicios |
| POST | `/api/v1/exploit/camera` | Explotación (auto-detect vendor) |
| POST | `/api/v1/exploit/chain` | Cadena de exploits |
| POST | `/api/v1/ai/threat-scoring` | Puntuación de amenazas |
| POST | `/api/v1/ai/anomalies` | Detección de anomalías |
| POST | `/api/v1/ai/behavior` | Análisis de comportamiento |
| POST | `/api/v1/report/json` | Informe JSON |
| POST | `/api/v1/report/html` | Informe HTML |

### 9.4 Perfiles de Escaneo (profiles.json)

| Perfil | Concurrencia | Jitter | Uso |
|--------|-------------|--------|-----|
| stealth | 5 | 2-5s | Bajo riesgo de detección |
| aggressive | 50 | 0.1-0.5s | Alto rendimiento |
| massive | 200 | 0.05-0.2s | Miles de IPs |
| camera_detection | 20 | 0.5-1.5s | Cámaras IP (puertos 80,443,554,8000,8080,37777) |

### 9.5 Estado en el banner de arranque

Al arrancar verás:
```
[LEVIATHAN] Router montado: /api/leviathan/* + /api/v1/* (unified)
→ LEVIATHAN: OK
```

Si LEVIATHAN falla, el dashboard sigue funcionando y muestra `→ LEVIATHAN: NOT AVAILABLE`.

## 10. DETECCIÓN DE OBJETOS CON IA (ONNX)

### 10.1 ¿Por qué ONNX y no ultralytics?

PyTorch (dependencia de ultralytics/YOLOv8) no compila en Termux/Android.
`onnxruntime` sí tiene soporte ARM64 y es mucho más liviano (~50MB vs ~500MB).

### 10.2 Setup (2 pasos)

**Paso 1 — En PC (convertir modelo):**
```bash
pip install ultralytics onnx
python3 leviathan_core/tools/convert_yolo_onnx.py
# Genera yolov8n.onnx (~12MB)
scp yolov8n.onnx termux:~/Red-team-tauri/redteam/models/
```

**Paso 2 — En Termux:**
```bash
pip install onnxruntime numpy pillow
```

El módulo `object_detection` detecta automáticamente:
- Si hay `.onnx` → usa onnxruntime (Termux)
- Si hay `ultralytics` → usa PyTorch (PC)
- Si no hay nada → devuelve error con instrucciones

### 10.3 Verificar

```bash
curl -X POST "http://localhost:8001/api/v1/ai/threat-scoring?target=test"   -H "Content-Type: application/json"   -d '{"image_path": "/sdcard/foto.jpg"}'
```

## 11. VERIFICACIÓN DE MÓDULOS

Antes de arrancar el dashboard, verifica que todos los módulos cargan:

```bash
python3 leviathan_core/tools/verify_modules.py
```

Output esperado:
```
[1] DEPENDENCIAS BASE
  ✅ fastapi                Web framework
  ✅ uvicorn                 ASGI server
  ✅ onnxruntime             ONNX inference (YOLOv8)
  ...
[5] AI ANALYZERS
  ✅ object_detection        Detección de objetos (ONNX/ultralytics)
  ✅ anomaly_detector        Detección de anomalías
  ...
TOTAL: 28/30 módulos OK
✅ SISTEMA COMPLETO — LISTO PARA OPERAR
```

## 12. CHANGELOG

### v6.0 LEVIATHAN UNIFIED (2026-08-21)

**Commits: 7d7e356, 25e88e3, 497e0eb, 2af83d6**

- LEVIATHAN integration router `/api/v1/*` montado en dashboard_server.py
- `leviathan_core/api/integration_router.py` — APIRouter unificado (15.8KB)
  - 5 scanners: network, cameras, rtsp, onvif, services
  - 2 exploiters: camera (auto-detect vendor), chain
  - 3 AI: threat-scoring, anomalies, behavior
  - 2 reporters: json, html
  - 3 system: status, health, profiles
- `leviathan_core/config/profiles.json` — 4 perfiles de escaneo + OPSEC + camera defaults
- `object_detection.py` v3.1 con backend ONNX (onnxruntime) para Termux
- `convert_yolo_onnx.py` — script para convertir YOLOv8 a ONNX en PC
- `verify_modules.py` — verificador de módulos para Termux
- `anomaly_detector.py` — numpy hecho opcional (import muerto eliminado)
- `arrancar.sh` fixes: tail-2 → tail -2, exec removido, wait agregado, deps LEVIATHAN
- `dashboard_server.py`: integrated_health ahora incluye LEVIATHAN status
- `leviathan_core/README.md` actualizado con /api/v1/* y ONNX

**Adaptaciones del blueprint original:**
- No crea `main_unified.py` (dashboard_server.py sigue como primario)
- No usa uvloop (no compila en Termux/Android)
- No usa ultralytics en Termux (ONNX en su lugar)
- Imports apuntan a `leviathan_core.modules.*` (no `leviathan_modules.*`)
- profiles.json sin secrets hardcodeados


### v1.1.0 ARTO VPN (2026-08-19) — commit d63dba2

**VPN Interceptor:**
- `vpn_interceptor.py` — captura de tráfico real via VpnService (sin root)
- 6 reglas de detección: port scan, brute force, data exfiltration, C2, DNS tunneling, beaconing
- `TrafficCapturePanel.tsx` — panel con stats en vivo, filtros, amenazas, conexiones
- `ARTOVpnService.java` + `VpnManager.java` — VpnService nativo de Android
- 6 nuevos endpoints: `/api/arto/traffic/*`
- Nueva pestaña "🔌 Tráfico" en ARTOPanel
- Integración con attack_simulator

### v1.0.0 ARTO (2026-08-19) — commits d0f7251, 9a63de4

**Sistema ARTO completo:**
- 29 archivos Python (core, modules, memory, utils, api, models)
- 5 motores AI: decisiones, aprendizaje, predicción, acciones, comportamiento
- Attack simulator integrado con enhanced_recon + interceptor
- Defense orchestrator + report generator
- Memoria SQLite persistente + knowledge base
- Threat intelligence, risk assessor, anomaly detector
- Router FastAPI con 17 endpoints + WebSocket en `/api/arto/*`
- Frontend: ARTOPanel (5 pestañas), ARTOProvider, artoApi, artoWebsocket
- Integrado en sidebar (ícono Cpu, badge "AI")
- Auto-start en dashboard_server.py (startup/shutdown events)
- Auto-start en arrancar.sh (Termux) y replit_start.sh (Replit)

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


### v4.1 (2026-08-19) — commit 4b3a540 — Verificación de integración

**Aclaración importante sobre el backend en uso:**

> ⚠️ `arrancar.sh` ejecuta `redteam/scripts/dashboard_server.py` (5600 líneas, 154 endpoints).
> NO usa `backend/dashboard_server.py` (130KB, 85 endpoints, sin v2).
>
> El archivo `backend/dashboard_server.py` es una versión anterior/paralela que NO tiene los endpoints `/api/v2/*`.
> Toda la funcionalidad v4 (SQLite, topology, IoT, alertas SSE, SOAR, export, settings) está integrada en `redteam/scripts/dashboard_server.py`.
>
> El zip original `redteam-dashboard-v4.zip` contenía `dashboard_server_v2.py` (749 líneas) como backend independiente con solo los 20 endpoints v2. Ese archivo fue **fusionado** dentro del dashboard_server.py existente en lugar de reemplazarlo, conservando los 60+ endpoints originales (MURCIÉLAGO, OSINT, Enhanced Recon, AbuseIPDB, Shodan, honeypot, C2, forensics, etc.).
>
> Los componentes del frontend en el repo (`tauri-frontend/src/components/`) están adaptados respecto al zip original:
> - Usan URLs relativas `/api/` en lugar de `window.__API__`
> - Incluyen `authHeaders()` con `getApiKey()` para autenticación
> - Esto los hace compatibles con el proxy de Vite y el backend unificado

**Endpoints `/api/v2/*` confirmados en `redteam/scripts/dashboard_server.py`:**

| Método | Endpoint | Función |
|--------|----------|---------|
| GET | `/api/v2/topology/hosts` | Lista de hosts con filtros |
| GET | `/api/v2/topology/graph` | Grafo de red (nodos + aristas) |
| POST | `/api/v2/topology/hosts` | Agregar host manual |
| GET | `/api/v2/iot/cameras` | Cámaras descubiertas |
| POST | `/api/v2/iot/cameras` | Agregar cámara |
| GET | `/api/v2/iot/snapshot/{camera_id}` | Snapshot JPEG de cámara |
| POST | `/api/v2/iot/brute/{camera_id}` | Test credenciales por defecto |
| GET | `/api/v2/alerts` | Alertas recientes |
| POST | `/api/v2/alerts` | Crear alerta |
| GET | `/api/v2/alerts/stream` | SSE stream en tiempo real |
| POST | `/api/v2/alerts/{alert_id}/ack` | Acknowledge alerta |
| GET | `/api/v2/threatintel/iocs` | IOCs persistentes |
| POST | `/api/v2/threatintel/iocs` | Agregar IOC |
| GET | `/api/v2/soar/playbooks` | Playbooks guardados |
| POST | `/api/v2/soar/playbooks` | Guardar playbook |
| POST | `/api/v2/soar/execute/{playbook_id}` | Ejecutar playbook |
| GET | `/api/v2/settings` | Configuración persistente |
| POST | `/api/v2/settings` | Guardar configuración |
| GET | `/api/v2/export/{fmt}` | Exportar JSON/CSV |
| POST | `/api/v2/reports/generate` | Generar reporte |

**Componentes frontend confirmados:**

| Archivo | Tamaño | Estado |
|---------|--------|--------|
| `TopologyPanel.tsx` | 16KB | ✅ Importado en App.tsx, reemplaza NetworkTopology |
| `IoTCameras.tsx` | 8KB | ✅ Importado en App.tsx, URLs relativas + auth |
| `AlertsPanel.tsx` | 7.5KB | ✅ Importado en App.tsx, SSE con token |
| `ExportPanel.tsx` | 4.7KB | ✅ Importado en App.tsx, exports con token |
| `AppShell.tsx` | 17KB | ✅ 3 módulos nuevos en menú (Topología, IoT, Alertas, Exportar) |
