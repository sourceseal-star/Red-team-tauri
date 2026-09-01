# 🔐 Sistema de Credenciales — Red-Team-Tauri v6.0

> **Regla de oro:** `.env` es la ÚNICA fuente de verdad. El código NUNCA regenera ni sobrescribe un valor que ya existe. Si un valor falta, se genera uno nuevo automáticamente y se guarda en `.env`.

---

## Tabla de Credenciales del Sistema

| # | Variable | Servicio | Puerto | Obligatoria | Cómo se genera |
|---|----------|----------|--------|-------------|----------------|
| 1 | `ADMIN_EMAIL` | Dashboard login | 8001 | Sí | Valor fijo: `admin@redteam.local` |
| 2 | `ADMIN_PASSWORD` | Dashboard login | 8001 | Sí | `control_claves.sh set` (tú la defines o se genera fuerte) |
| 3 | `REDTEAM_API_KEY` | Bearer token API | 8001 | Sí | Auto-generada (48 chars) si está vacía |
| 4 | `NEXUS_USER` | Nexus Omni HTTP Basic | 8004 | Sí | Default: `admin` |
| 5 | `NEXUS_PASS` | Nexus Omni HTTP Basic | 8004 | Sí | Auto-generada (48 chars) si está vacía |
| 6 | `TELEGRAM_BOT_TOKEN` | Alertas Telegram | — | Opcional | Desde @BotFather en Telegram |
| 7 | `TELEGRAM_CHAT_ID` | Destino alertas TG | — | Opcional | Tu chat ID (desde @userinfobot) |
| 8 | `ABUSEIPDB_KEY` | OSINT IP reputation | — | Opcional | https://www.abuseipdb.com/account/api |
| 9 | `SHODAN_API_KEY` | OSINT dispositivos | — | Opcional | https://www.shodan.io/dashboard |
| 10 | `HUNTER_API_KEY` | OSINT emails | — | Opcional | https://hunter.io/api-keys |
| 11 | `VIRUSTOTAL_API_KEY` | OSINT malware | — | Opcional | https://www.virustotal.com/api |
| 12 | `CENSYS_API_ID` | OSINT certs | — | Opcional | https://search.censys.io/account/api |
| 13 | `CENSYS_API_SECRET` | OSINT certs | — | Opcional | Junto con CENSYS_API_ID |
| 14 | `GOOGLE_API_KEY` | Google Custom Search | — | Opcional | https://console.cloud.google.com |
| 15 | `GOOGLE_CSE_ID` | Google Custom Search | — | Opcional | Junto con GOOGLE_API_KEY |
| 16 | `GITHUB_TOKEN` | GitHub recon | — | Opcional | https://github.com/settings/tokens |
| 17 | `SEAL_ENCRYPTION_KEY` | Commander encryption | — | Opcional | Definida por el operador |
| 18 | `SEAL_MASTER_KEY` | COM-LINK encryption | — | Opcional | Definida por el operador |
| 19 | `SOURCESEAL_API` | SourceSeal anchoring | — | Opcional | https://source.coal/api/v1/anchor |
| 20 | `SOURCESEAL_KEY` | SourceSeal HMAC | — | Opcional | Desde sourcesealcorp |

---

## Archivos de Credenciales

### 1. `.env` (raíz del proyecto) — Fuente de verdad
- **Permisos:** `600` (solo el dueño puede leer)
- **Backup cifrado:** `~/.c2/env_respaldo.aes` (AES-256-CBC)
- **NUNCA se sube a git** (está en `.gitignore`)
- **Template:** `.env.example` (con valores vacíos)

### 2. `redteam/scripts/.auth/password.json` — Hash de password
- Generado por `auth_bootstrap.py` desde `ADMIN_PASSWORD` de `.env`
- Algoritmo: PBKDF2-SHA256, 310,000 iteraciones, salt aleatorio
- **No es la password** — es el hash. La password vive en `.env`.
- Si se borra, el backend lo re-crea desde `.env` automáticamente.

### 3. `commander/comlink/data/config.json` — Config COM-LINK
- Contiene `telegram.bot_token` y `telegram.default_chat_id`
- Cifrado de mensajes COM-LINK con `SEAL_MASTER_KEY`
- Permisos recomendados: `600`

---

## Cómo Generar / Cambiar Cada Credencial

### 🔑 Credenciales del Dashboard (ADMIN_PASSWORD, REDTEAM_API_KEY)

**Definir por primera vez o cambiar:**
```bash
cd ~/Red-team-tauri
bash control_claves.sh set
```
- Te pedirá `ADMIN_PASSWORD` (Enter = genera una fuerte de 24 chars)
- Te pedirá `NEXUS_PASS` (Enter = genera una fuerte de 24 chars)
- `REDTEAM_API_KEY` se genera automáticamente (48 chars) si está vacía
- Crea respaldo cifrado en `~/.c2/env_respaldo.aes`
- Elimina `password.json` viejo para que se regenere el hash

**Verificar sin revelar valores:**
```bash
bash control_claves.sh status
```

**Recuperar desde respaldo cifrado:**
```bash
bash control_claves.sh restore
# Te pide la passphrase que usaste en "set"
```

### 🔑 Credencial de Nexus Omni (NEXUS_PASS)

**Cómo funciona:**
- `nexus_credentials.py` lee `NEXUS_USER` y `NEXUS_PASS` de `.env`
- Si `NEXUS_PASS` está vacío, genera una automáticamente y la guarda en `.env`
- Si ya existe, la usa tal cual — **nunca la sobrescribe**
- Permisos del `.env` se fuerzan a `600` automáticamente

**Para regenerar (forzar nueva clave):**
```python
# Desde Python, dentro del proyecto:
from nexus_credentials import ensure_nexus_credentials
creds = ensure_nexus_credentials(reset=True)
# La nueva clave se guarda en .env automáticamente
```

**O desde bash:**
```bash
# Editar .env directamente y cambiar NEXUS_PASS=valor_nuevo
nano ~/Red-team-tauri/.env
# Buscar la línea NEXUS_PASS= y poner el nuevo valor
# Guardar con Ctrl+X, Y
chmod 600 ~/Red-team-tauri/.env
```

### 🔑 Telegram Bot

**Obtener credenciales:**
1. Abre Telegram, busca `@BotFather`
2. Envía `/newbot` — sigue los pasos
3. Guarda el token que te da (formato: `123456789:ABCdefGhi...`)
4. Busca `@userinfobot` y envía cualquier mensaje — te da tu Chat ID

**Configurar en Termux:**
```bash
# Opción A — en .env del proyecto:
echo 'TELEGRAM_BOT_TOKEN=tu_token_aqui' >> ~/Red-team-tauri/.env
echo 'TELEGRAM_CHAT_ID=tu_chat_id_aqui' >> ~/Red-team-tauri/.env
chmod 600 ~/Red-team-tauri/.env

# Opción B — en bashrc (para que iniciar_todo.sh las detecte):
echo 'export TELEGRAM_BOT_TOKEN="tu_token_aqui"' >> ~/.bashrc
echo 'export TELEGRAM_CHAT_ID="tu_chat_id_aqui"' >> ~/.bashrc
source ~/.bashrc
```

**Configurar en COM-LINK (commander):**
```bash
cd ~/Red-team-tauri/commander/comlink/data
jq '.telegram.bot_token = "TU_TOKEN" | .telegram.default_chat_id = "TU_CHAT_ID"' \
  config.json > config.tmp && mv config.tmp config.json
```

**Probar Telegram:**
```bash
curl -X POST http://127.0.0.1:8001/api/telegram/test
```

### 🔑 API Keys OSINT (AbuseIPDB, Shodan, etc.)

Todas van en `.env`:
```bash
nano ~/Red-team-tauri/.env
# Completar las líneas que están vacías:
# ABUSEIPDB_KEY=tu_key
# SHODAN_API_KEY=tu_key
# etc.
chmod 600 ~/Red-team-tauri/.env
```

### 🔑 SEAL Encryption Keys (Commander / COM-LINK)

```bash
echo "SEAL_ENCRYPTION_KEY=$(head -c 32 /dev/urandom | base64)" >> ~/Red-team-tauri/.env
echo "SEAL_MASTER_KEY=$(head -c 32 /dev/urandom | base64)" >> ~/Red-team-tauri/.env
chmod 600 ~/Red-team-tauri/.env
```

### 🔑 Clave del Manual Cifrado (manual_operaciones.enc)

```bash
bash cambiar_clave.sh
# Pide clave actual, clave nueva (2 veces), y verifica
```

---

## Auto-Detección de Credenciales

El sistema detecta credenciales automáticamente en este orden:

1. **Variable de entorno** del proceso (`os.environ.get()`)
2. **Archivo `.env`** del proyecto (leído por `nexus_credentials.py` y `auth_bootstrap.py`)
3. **`.bashrc`** de Termux (para Telegram, leído por `iniciar_todo.sh`)
4. **config.json** de COM-LINK (para Telegram del commander)

Si una credencial no existe en ningún lado:
- `REDTEAM_API_KEY` → se genera automáticamente (48 chars) y se guarda en `.env`
- `NEXUS_PASS` → se genera automáticamente (48 chars) y se guarda en `.env`
- `ADMIN_PASSWORD` → NO se genera automáticamente. Debes definirla con `control_claves.sh set`
- Telegram, API keys OSINT → quedan vacías (servicios opcionales desactivados)

---

## Flujo Completo: Desde Cero hasta Sistema Operativo

### Paso 1: Clonar repo (si no existe)
```bash
cd ~
git clone https://github.com/sourceseal-star/Red-team-tauri.git
cd Red-team-tauri
```

### Paso 2: Definir credenciales
```bash
cd ~/Red-team-tauri
cp .env.example .env
chmod 600 .env

# Definir ADMIN_PASSWORD, NEXUS_PASS, REDTEAM_API_KEY
bash control_claves.sh set
# Enter = genera clave fuerte automática

# Verificar
bash control_claves.sh status
```

### Paso 3: Configurar API keys y Telegram (opcional)
```bash
nano ~/Red-team-tauri/.env
# Completar: ABUSEIPDB_KEY, SHODAN_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
chmod 600 ~/Red-team-tauri/.env
```

### Paso 4: Actualizar desde git
```bash
cd ~/Red-team-tauri
git pull origin main
```

### Paso 5: Levantar el sistema completo
```bash
cd ~/Red-team-tauri

# Opción A — Sistema unificado (recomendado):
bash iniciar_unificado.sh
# Arranca: Dashboard 8001 + Commander (in-process) + PHANTOM 8002
#         + Nexus 8004 + Controller 8005 (si existen)

# Opción B — Con Telegram + PDF + Monitor:
bash iniciar_todo.sh --full

# Opción C — Solo dashboard (arranque mínimo):
bash arrancar_termux.sh
```

### Paso 6: Verificar que todo está vivo
```bash
cd ~/Red-team-tauri
bash scripts/healthcheck_all.sh
# Debe mostrar OK en: 8001, 8001/commander, 8002, 8003, 8004, 8005, .env 600, ledger
```

### Paso 7: Probar módulos
```bash
# Login:
curl -X POST http://127.0.0.1:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@redteam.local","password":"TU_PASSWORD"}'

# Telegram:
curl -X POST http://127.0.0.1:8001/api/telegram/test

# Commander:
curl http://127.0.0.1:8001/api/commander/health

# Nexus:
curl -u admin:TU_NEXUS_PASS http://127.0.0.1:8004/
```

---

## Cuentas y Dónde Obtener Cada API Key

| Servicio | URL | Tier | Dónde verla |
|----------|-----|------|-------------|
| AbuseIPDB | https://www.abuseipdb.com/account/api | Gratis (1000/día) | "API Key" en tu cuenta |
| Shodan | https://www.shodan.io/dashboard | Gratis (básico) | "Show API Key" |
| Hunter.io | https://hunter.io/api-keys | Gratis (50/mes) | Dashboard principal |
| VirusTotal | https://www.virustotal.com/api | Gratis (4/min) | "API key" en settings |
| Censys | https://search.censys.io/account/api | Gratis (25/día) | "API ID" + "Secret" |
| Google CSE | https://console.cloud.google.com | Gratis (100/día) | "API Key" + "Search Engine ID" |
| GitHub | https://github.com/settings/tokens | Gratis | Crear token (scope: read:user) |
| Telegram | @BotFather en Telegram | Gratis | `/newbot` → token |
| SourceSeal | https://source.coal/api/v1/anchor | — | Desde sourcesealcorp |

---

## Resumen de Scripts de Credenciales

| Script | Función |
|--------|---------|
| `control_claves.sh set` | Definir todas las claves del operador + respaldo cifrado |
| `control_claves.sh status` | Verificar qué claves están configuradas (sin mostrar valores) |
| `control_claves.sh restore` | Recuperar .env desde respaldo cifrado |
| `cambiar_clave.sh` | Cambiar la clave del manual cifrado |
| `auth_bootstrap.py` | Sincroniza hash de password desde .env → password.json |
| `nexus_credentials.py` | Gestiona credenciales de Nexus (genera si falta, nunca sobrescribe) |
| `guardian_custodian.sh` | Protege archivos críticos con SHA-256 + backup cifrado |

---

## Puertos y Servicios

| Puerto | Servicio | Script |
|--------|----------|--------|
| 8001 | Dashboard + Commander (in-process) | `redteam/scripts/dashboard_server.py` |
| 8002 | GHOST PHANTOM Master | `ghost_hunter_phantom/master.py` |
| 8003 | Commander Dashboard (standalone, opcional) | `commander/commander_server.py` |
| 8004 | Nexus Omni-Sentient | `nexus_omni_v9.py` |
| 8005 | SourceSeal Controller | `~/sourceseal_controller.py` |
| 8000 | Motor de Cierre / Termux Bridge | `motor_cierre/backend/` |

---

## Para la cuenta sealclient2@gmail.com

Si las API keys y credenciales de Telegram están en la cuenta `sealclient2@gmail.com`:

1. Inicia sesión en cada servicio con esa cuenta (AbuseIPDB, Shodan, etc.)
2. Copia cada API key al `.env` correspondiente
3. Para Telegram: el bot fue creado desde esa cuenta — el token está en @BotFather
4. Ejecuta `bash control_claves.sh set` para cargar todo en `.env`
5. Reinicia el sistema con `bash iniciar_unificado.sh`

El sistema detecta automáticamente los valores cuando están en `.env` o como variables de entorno. No necesita configuración adicional una vez que las claves están en `.env`.
