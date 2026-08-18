# ============================================================================
# Red-Team-Tauri v4.0 — Módulos OSINT e Interceptor Avanzados
# ============================================================================

## Instalación

```bash
# 1. Descomprimir el ZIP en la raíz del proyecto
unzip redteam-modules-v4.0.zip -d /path/to/Red-team-tauri/

# 2. Instalar dependencias
pip install httpx pydantic fastapi uvicorn python-whois dnspython beautifulsoup4

# 3. Configurar API keys (opcional — los módulos funcionan sin ellas con fallbacks)
export SHODAN_API_KEY="tu-key"
export VIRUSTOTAL_API_KEY="tu-key"
export ABUSEIPDB_API_KEY="tu-key"
export CENSYS_API_ID="tu-id"
export CENSYS_API_SECRET="tu-secret"
export GOOGLE_API_KEY="tu-key"
export GOOGLE_CSE_ID="tu-cse-id"
export GITHUB_TOKEN="tu-token"

# 4. Reiniciar el backend
python3 backend/dashboard_server.py
```

## Endpoints nuevos

### OSINT Advanced (`/api/osint/*`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/osint/whois/{domain}` | WHOIS lookup |
| GET | `/api/osint/dns/{domain}` | DNS recon (A, MX, TXT, NS, SPF, DMARC) |
| POST | `/api/osint/subdomains` | Enumeración de subdominios |
| GET | `/api/osint/threat-intel/{ip}` | Threat intelligence (AbuseIPDB, geo) |
| POST | `/api/osint/email` | Email OSINT (MX, SPF, DMARC, hash) |
| GET | `/api/osint/headers?url=` | HTTP header fingerprinting |
| GET | `/api/osint/full/{domain}` | OSINT completo (WHOIS + DNS + subdominios) |
| GET | `/api/osint/results` | Resultados guardados en BD |
| GET | `/api/osint/google?q=` | Google Custom Search |
| GET | `/api/osint/shodan/{ip}` | Shodan host lookup |
| GET | `/api/osint/virustotal/{indicator}` | VirusTotal lookup |
| POST | `/api/osint/social` | Social media username search |

### Interceptor Advanced (`/api/interceptor/*`)
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
- NIST SP 800-92 (Guide to Computer Security Log Management)
- MITRE ATT&CK T1190 (Exploit Public-Facing Application)
- MITRE ATT&CK T1592 (Gather Victim Host Info)

## Arquitectura Zero-PII
Todos los emails se hashean con SHA-256 antes de almacenarse.
No se guarda contenido de payloads, solo metadatos y alertas.
