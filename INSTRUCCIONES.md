# ============================================================================
# Red-Team-Tauri v6.1 — Dashboard + IoT + OSINT + LEVIATHAN
# ACTUALIZADO: 2026-08-30
# ============================================================================

> **Backend unico:** `redteam/scripts/dashboard_server.py` (:8001)
> **Arranque:** `bash arrancar_termux.sh` (Termux) / `bash replit_start.sh` (Replit)

## Instalacion

```bash
# 1. Clonar (si no existe)
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri

# 2. Preparar y sincronizar de forma segura
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

> `termux_recover.sh` se detiene si detecta cambios locales sin guardar. No
> ejecuta `git reset --hard` ni borra trabajo local.

## Comandos principales

```bash
# Ejecutar la copia local sin pull, reset, stash ni instalación
bash arrancar_termux.sh

# Alias compatible: prepara/sincroniza y luego arranca
bash arrancar.sh

# Solo Replit
bash replit_start.sh
```

Commander queda integrado bajo `/api/commander/*`; no arranques
`commander_server.py` ni un servidor adicional en `8003`.

## Configurar API Keys (opcional — todo funciona sin ellas con fallbacks)

Editar `.env` en la raiz del repo:

```bash
nano .env
```

```bash
ABUSEIPDB_KEY=tu-key       # https://www.abuseipdb.com/account/api (1000 checks/dia gratis)
SHODAN_API_KEY=tu-key      # https://www.shodan.io/dashboard (cuenta gratis)
HUNTER_API_KEY=tu-key      # https://hunter.io/api-keys (opcional, emails OSINT)
```

> La variable es `ABUSEIPDB_KEY` (sin `_API`).

## Endpoints OSINT (`/api/osint/*`)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/api/osint/whois/{domain}` | WHOIS lookup |
| GET | `/api/osint/subdomains/{domain}` | Enumeracion de subdominios |
| GET | `/api/osint/emails/{domain}` | Email OSINT |
| GET | `/api/osint/full/{target}` | OSINT completo (WHOIS + DNS + geo + threat) |
| GET | `/api/osint/social/{username}` | Social media username search |
| GET | `/api/osint/cert/{domain}` | Certificado SSL |
| GET | `/api/osint/history/{target}` | Historial |
| GET | `/api/osint/shodan?ip=X` | Shodan host lookup |
| GET | `/api/osint/export/{target}` | Exportar resultados |

## Endpoints IoT y Camaras (`/api/iot/*`)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/api/iot/vulns?ip=X&port=Y` | Vendor + CVEs + creds + URLs |
| GET | `/api/iot/auto-access?ip=X&port=Y` | Orquestacion completa en 1 llamado |
| POST | `/api/iot/auto-access-batch` | Escanea red CIDR, procesa todas las camaras |
| GET | `/api/iot/snapshot?ip=X&port=Y&user=U&pwd=P` | Snapshot con 11 paths + auth |
| GET | `/api/iot/stream?ip=X&port=Y&path=P` | Proxy MJPEG en vivo |
| GET | `/api/iot/video-urls?ip=X&port=Y` | Detectar URLs de video |
| POST | `/api/iot/scan-network` | Escaneo de red CIDR |

## Endpoints LEVIATHAN (`/api/v1/*`)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | `/api/v1/status` | Estado del sistema LEVIATHAN |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/profiles` | Perfiles de escaneo |
| POST | `/api/v1/scan/network` | Escaneo de red |
| POST | `/api/v1/scan/cameras` | Deteccion de camaras IP |
| POST | `/api/v1/scan/rtsp` | Deteccion RTSP |
| POST | `/api/v1/exploit/camera` | Explotacion de camara |
| POST | `/api/v1/ai/threat-scoring` | Puntuacion de amenazas |
| POST | `/api/v1/report/json` | Informe JSON |

## Endpoints Interceptor (`/api/interceptor/*`)

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/api/interceptor/analyze/request` | Analizar request HTTP |
| POST | `/api/interceptor/analyze/response` | Analizar response HTTP |
| GET | `/api/interceptor/flows` | Flujos interceptados |
| GET | `/api/interceptor/alerts` | Alertas de inyeccion |
| GET | `/api/interceptor/stats` | Estadisticas SIEM |

## Uso de camaras

```bash
# Escanear toda la red y ver todas las camaras
curl -X POST http://localhost:8001/api/iot/auto-access-batch \
  -H "Content-Type: application/json" \
  -d '{"cidr": "192.168.1.0/24"}' | python3 -m json.tool

# Ver una camara especifica
curl "http://localhost:8001/api/iot/auto-access?ip=192.168.1.7&port=80" | python3 -m json.tool

# Ver snapshot en el navegador
# http://localhost:8001/api/iot/snapshot?ip=192.168.1.7&port=80&user=admin&pwd=12345

# Ver stream MJPEG en el navegador
# http://localhost:8001/api/iot/stream?ip=192.168.1.7&port=80&path=/Streaming/Channels/101&user=admin&pwd=12345
```

## Vendors de camaras detectados

Hikvision, Dahua, Xiongmai, D-Link, Netgear, GoAhead, Ubiquiti, ONVIF (generico)

## CVEs conocidos por vendor

- **Hikvision**: CVE-2021-36260 (RCE), CVE-2021-33044 (auth bypass), CVE-2017-7921 (backdoor)
- **Dahua**: CVE-2021-33045 (RCE), CVE-2020-25078 (auth bypass), CVE-2022-30560
- **Xiongmai**: CVE-2017-17215 (RCE sin auth), CVE-2017-8225 (auth bypass)
- **D-Link**: CVE-2019-16920 (RCE), CVE-2020-25078
- **Netgear**: CVE-2016-6277 (RCE)
- **GoAhead**: CVE-2017-8225 (auth bypass)
- **Ubiquiti**: CVE-2021-35064

---

*Ver tambien: `MANUAL_OPERATIVO.md`, `GUIA_ARRANQUE.md`, `CONTINUAR_AQUI.md`*
