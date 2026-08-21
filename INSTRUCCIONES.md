# ============================================================================
# Red-Team-Tauri v6.0 — Módulos OSINT e Interceptor Avanzados
# ACTUALIZADO: 2026-08-21
# ============================================================================

> **Backend único:** `redteam/scripts/dashboard_server.py` (:8001)
> **Arranque:** `bash arrancar.sh` (Termux) / `bash replit_start.sh` (Replit)

## Instalación

```bash
# 1. Clonar (si no existe)
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri

# 2. Sincronizar con main
git fetch origin && git reset --hard origin/main

# 3. Arrancar (instala todo automáticamente)
bash arrancar.sh
```

## Configurar API Keys (opcional — todo funciona sin ellas con fallbacks)

Editar `.env` en la raíz del repo:

```bash
nano .env
```

```bash
ABUSEIPDB_KEY=tu-key       # https://www.abuseipdb.com/account/api (1000 checks/día gratis)
SHODAN_API_KEY=tu-key      # https://www.shodan.io/dashboard (cuenta gratis)
HUNTER_API_KEY=tu-key      # https://hunter.io/api-keys (opcional, emails OSINT)
```

> ⚠️ La variable es `ABUSEIPDB_KEY` (sin `_API`).

## Endpoints OSINT Advanced (`/api/osint/*`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/osint/whois/{domain}` | WHOIS lookup |
| GET | `/api/osint/dns/{domain}` | DNS recon (A, MX, TXT, NS, SPF, DMARC) |
| POST | `/api/osint/subdomains` | Enumeración de subdominios |
| GET | `/api/osint/threat-intel/{ip}` | Threat intelligence (AbuseIPDB, geo) |
| POST | `/api/osint/email` | Email OSINT (MX, SPF, DMARC, hash SHA-256) |
| GET | `/api/osint/headers?url=` | HTTP header fingerprinting |
| GET | `/api/osint/full/{domain}` | OSINT completo (WHOIS + DNS + subdominios) |
| GET | `/api/osint/results` | Resultados guardados en BD |
| GET | `/api/osint/google?q=` | Google Custom Search |
| GET | `/api/osint/shodan/{ip}` | Shodan host lookup |
| GET | `/api/osint/virustotal/{indicator}` | VirusTotal lookup |
| POST | `/api/osint/social` | Social media username search |

## Endpoints Interceptor Advanced (`/api/interceptor/*`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/interceptor/analyze/request` | Analizar request HTTP |
| POST | `/api/interceptor/analyze/response` | Analizar response HTTP |
| GET | `/api/interceptor/flows` | Flujos interceptados |
| GET | `/api/interceptor/alerts` | Alertas de inyección |
| GET | `/api/interceptor/stats` | Estadísticas SIEM |
| DELETE | `/api/interceptor/flows` | Limpiar BD |

## Detecciones del Interceptor
- SQL Injection (CWE-89)
- XSS (CWE-79)
- Command Injection (CWE-78)
- Path Traversal (CWE-22)
- SSRF (CWE-918)
- XXE (CWE-611)
- LFI/RFI (CWE-98)
- LDAP Injection (CWE-90)
- NoSQL Injection (CWE-943)

## Referencias
- NIST SP 800-115 (Technical Guide to Information Security Testing)
- NIST SP 800-150 (Guide to Cyber Threat Information Sharing)
- NIST SP 800-94 (Guide to Intrusion Detection and Prevention Systems)
- MITRE ATT&CK T1190 (Exploit Public-Facing Application)
- MITRE ATT&CK T1592 (Gather Victim Host Info)

## Arquitectura Zero-PII
Todos los emails se hashean con SHA-256 antes de almacenarse.
No se guarda contenido de payloads, solo metadatos y alertas.

---

*Ver también: `MANUAL_OPERATIVO.md` (referencia completa 995 líneas), `GUIA_ARRANQUE.md` (arranque rápido)*
