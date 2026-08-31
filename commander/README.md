# 🔱 COMMANDER — Tactical Intelligence Suite

**Auditoría de seguridad para Termux (Android) | v4.0.0**

Suite CLI de auditoría de seguridad que combina escaneo de red (nmap), detección de cámaras IP, OSINT, cifrado Fernet y anclaje blockchain SourceSeal. Diseñada para condiciones reales de campo.

> ⚠️ **Repositorio independiente de Red-team-tauri.** Este repo NO depende ni se conecta al backend FastAPI de Red-team-tauri. Es una herramienta CLI standalone.

---

## 🚀 ARRANQUE RÁPIDO

### Prerrequisitos (Termux)

```bash
# 1. Instalar Termux desde F-Droid (NO Play Store)
# https://f-droid.org/packages/com.termux/

# 2. Dependencias del sistema
pkg update -y && pkg upgrade -y
pkg install python nmap whois

# 3. Dependencias Python
pip install cryptography

# 4. Permisos de almacenamiento (para informes)
termux-setup-storage

# 5. Clonar
git clone https://github.com/sourceseal-star/commander.git
cd commander
```

### Primera ejecución

```bash
# Modo interactivo (menú completo)
python3 commander.py

# Auditoría automática
python3 commander.py --auto 192.168.1.0/24 --email cliente@mail.com --debug

# Si se cayó a mitad, reanudar
python3 commander.py --resume 1 --email cliente@mail.com

# Listar todas las auditorías
python3 commander.py --list
```

---

## 📋 REQUISITOS

| Componente | Versión | Nota |
|---|---|---|
| Python | 3.10+ | CLI + SQLite + cifrado |
| nmap | cualquiera | Escaneo de red + cámaras |
| whois | opcional | OSINT IPs (fallback RDAP si no está) |
| Termux | desde F-Droid | NO desde Play Store |
| cryptography | >=41.0.0 | Cifrado Fernet de informes |

### Opcional

| Componente | Instalación | Activa |
|---|---|---|
| `termux-api` | `pkg install termux-api` | Abrir informes con `termux-open` |
| SMTP (Gmail) | Configurar en menú interactivo | Envío de informes por email |

---

## 📡 CLI — ARGUMENTOS

```
commander.py [OPTIONS]

Opciones:
  --auto TARGET     Ejecuta auditoría automática (IP o CIDR)
  --resume ID       Reanuda auditoría por ID de SQLite
  --list            Lista auditorías pendientes y completadas
  --email EMAIL     Correo destino para el informe
  --key PASSPHRASE  Frase de paso para cifrado Fernet
  --debug           Habilita logs detallados de depuración
  -h, --help        Muestra ayuda
```

### Ejemplos

```bash
# Auditoría automática completa con debug
python3 commander.py --auto 192.168.1.0/24 --email cliente@mail.com --debug

# Auditoría con frase de paso personalizada
export COMMANDER_KEY="mi_clave_secreta"
python3 commander.py --auto 10.0.0.0/24 --email jefe@corp.com

# Reanudar auditoría interrumpida (ID=3)
python3 commander.py --resume 3 --email cliente@mail.com

# Listar auditorías
python3 commander.py --list

# Modo interactivo (menú con 9 opciones)
python3 commander.py
```

---

## 🔄 FLUJO DE AUDITORÍA — CHECKPOINTS POR FASE

```
┌─────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐     ┌───────────┐
│  start  │ ──→ │ network_done │ ──→ │ cameras_done │ ──→ │ osint_done │ ──→ │ completed │
└─────────┘     └──────────────┘     └──────────────┘     └────────────┘     └───────────┘
                  (save cp)             (save cp)            (save cp)          (mark done)
```

| Fase | Qué hace | Herramienta | Timeout |
|---|---|---|---|
| 1. Network | Escaneo de red completo (-sV -O --script vuln) | nmap | 120s |
| 2. Cameras | Detección de cámaras IP (puertos 554,80,8080,37777) | nmap | 30s |
| 3. OSINT | WHOIS + Geo-IP + Threat score de hasta 5 hosts | whois + ip-api + ipwho.is | 10s/IP |
| Final | Genera informe HTML cifrado + hash SHA-256 | Fernet | - |

**Si el proceso muere** (OOM, batería, Termux kill), `--resume <ID>` reconstruye las fases completadas desde SQLite y continúa desde la siguiente.

---

## 🗂️ ESTRUCTURA DE ARCHIVOS

```
commander/
├── commander.py          # 🔱 Script principal (751 líneas)
├── requirements.txt       # 📦 Dependencias Python (cryptography)
├── README.md             # 📖 Este archivo
└── .replit               # ▶️ Config Replit (Python 3.12)

# Generados en runtime:
~/commander.db             # SQLite — auditorías + checkpoints
~/commander.log            # Log dual (consola + archivo)
~/.commander_tmp/          # Directorio temporal (NO usa /tmp)
~/storage/downloads/commander_reports/  # Informes HTML cifrados (.enc)
```

### ¿Por qué `~/.commander_tmp` y no `/tmp`?

En Termux, `/tmp` NO es escribible (PermissionError). El commit `a22a680` fixeó esto usando `~/.commander_tmp` como directorio temporal. **Nunca** cambiar a `/tmp` en este repo.

---

## 🔐 CIFRADO Y BLOCKCHAIN

### Cifrado Fernet

- Los informes HTML se cifran con Fernet (symmetric encryption)
- La clave se genera desde `COMMANDER_KEY` (env var) o `--key` (CLI arg)
- Sin clave → se genera una aleatoria (se muestra en el log)
- Los archivos se guardan como `.enc` (no legibles sin descifrar)

### Anclaje SourceSeal

- Cada auditoría genera un hash SHA-256 del resultado completo
- El hash se ancla a la API de SourceSeal (`sourceseal_api` en CONFIG)
- Si la API no responde → modo offline (guarda el hash localmente)
- Backoff exponencial: 3 reintentos con 2s, 4s, 8s

```python
# El hash se calcula así:
hash_val = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
```

---

## 📧 ENVÍO DE INFORMES POR EMAIL

Configuración SMTP (Gmail):

```bash
# Opción 1: Desde el menú interactivo (opción 6)
python3 commander.py
# → seleccionar opción 6
# → ingresar email remitente + contraseña

# Opción 2: Variables de entorno
export COMMANDER_SMTP_EMAIL=tu@gmail.com
export COMMANDER_SMTP_PASSWORD=tu-app-password
```

> ⚠️ Gmail requiere **App Password** (no la contraseña normal). Generar en: https://myaccount.google.com/apppasswords

---

## 🧪 TESTEO — SMOKE TESTS

### Verificación rápida

```bash
# 1. Verificar que Python y deps funcionan
python3 -c "from cryptography.fernet import Fernet; print('✅ cryptography OK')"
python3 -c "import sqlite3; print('✅ sqlite3 OK')"

# 2. Verificar nmap y whois
nmap --version | head -1
whois --version

# 3. Help del CLI
python3 commander.py --help

# 4. Listar auditorías (debe mostrar vacío o DB existente)
python3 commander.py --list

# 5. Test de cifrado (genera y descifra un reporte de prueba)
python3 -c "
from cryptography.fernet import Fernet
key = Fernet.generate_key()
f = Fernet(key)
encrypted = f.encrypt(b'test')
decrypted = f.decrypt(encrypted)
assert decrypted == b'test'
print('✅ Cifrado/descifrado OK')
"

# 6. Test de SQLite (checkpoints)
python3 -c "
import sqlite3, json
conn = sqlite3.connect('test_commander.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT, scan_type TEXT, timestamp TEXT,
    data_json TEXT, hash TEXT, status TEXT, checkpoint_data TEXT
)''')
c.execute('INSERT INTO audits VALUES (NULL,?,?,?,?,?,?,?)',
    ('192.168.1.0/24', 'test', '2026-01-01T00:00:00Z', '{}', 'abc123', 'running', json.dumps({'phase':'start'}))
)
conn.commit()
row = c.execute('SELECT * FROM audits').fetchone()
print(f'✅ SQLite OK — ID={row[0]}, target={row[1]}, phase={json.loads(row[7])[\"phase\"]}')
conn.close()
import os; os.remove('test_commander.db')
"
```

### Test completo de auditoría (requiere red local)

```bash
# Auditar localhost (rápido, sin danger)
python3 commander.py --auto 127.0.0.1 --debug

# Verificar que se generó el informe
ls -la ~/storage/downloads/commander_reports/

# Verificar el log
tail -20 ~/commander.log

# Listar la auditoría
python3 commander.py --list
```

---

## 🍱 MENÚ INTERACTIVO (9 opciones)

```
╔══════════════════════════════════════════╗
║        🔱 COMMANDER v4.0.0               ║
║        Tactical Intelligence Suite       ║
╠══════════════════════════════════════════╣
║  1) Escaneo de red (nmap)               ║
║  2) Detección de cámaras IP              ║
║  3) Análisis forense básico              ║
║  4) OSINT de IP                          ║
║  4b) OSINT de dominio (WHOIS+DNS+Subs)  ║
║  4c) OSINT de email (MX+SPF+DMARC)      ║
║  5) Auditoría completa (con checkpoints) ║
║  6) Configuración (SMTP + SourceSeal)    ║
║  7) Anclar hash a SourceSeal            ║
║  8) Reanudar auditoría pendiente        ║
║  9) Descifrar informe (.enc)            ║
║  0) Salir                                ║
╚══════════════════════════════════════════╝
```

---

## 🏗️ ARQUITECTURA INTERNA

```
commander.py (751 líneas, un solo archivo)
│
├── Configuración global (CONFIG dict)
│   ├── report_dir    → ~/storage/downloads/commander_reports/
│   ├── temp_dir      → ~/.commander_tmp/ (NO /tmp)
│   ├── db_path       → ~/commander.db (SQLite)
│   ├── log_path      → ~/commander.log
│   └── smtp_server   → smtp.gmail.com:587
│
├── Logging dual (consola + archivo)
│
├── SQLite thread-safe (con db_lock)
│   ├── create_scan_record()  → INSERT inicial
│   ├── save_checkpoint()     → UPDATE checkpoint por fase
│   ├── get_checkpoint()      → SELECT checkpoint para resume
│   └── update_scan_status() → UPDATE status (completed/failed)
│
├── Cifrado Fernet
│   ├── encrypt_report()  → cifra HTML con clave
│   └── decrypt_report()  → descifra .enc
│
├── Anclaje SourceSeal (con backoff exponencial)
│   └── anchor_to_sourceseal() → POST hash a API
│
├── Escaneo
│   ├── scan_network()  → nmap -sV -O --script vuln
│   ├── scan_cameras()  → nmap -p 554,80,8080,37777
│   └── osint_ip()      → whois + ip-api.com
│
├── Auditoría con checkpoints
│   ├── run_audit_phased()  → ejecuta 3 fases + guarda cp
│   └── resume_scan()       → lee cp + continúa
│
├── Informes
│   ├── generate_html()     → genera HTML con datos
│   └── save_report()      → cifra + guarda .enc
│
├── Email
│   └── send_email()       → SMTP Gmail con adjuntos
│
└── CLI (argparse)
    ├── --auto       → auto_mode()
    ├── --resume ID  → resume_scan()
    ├── --list       → lista auditorías
    └── (sin args)   → menú interactivo
```

---

## 🔧 SOLUCIÓN DE PROBLEMAS

### PermissionError en /tmp

```
❌ No se pudo crear /tmp/xxx: [Errno 13] Permission denied
```

**Fix:** Commander usa `~/.commander_tmp/` (no `/tmp`). Si ves este error, verifica que el commit `a22a680` esté aplicado:

```bash
git log --oneline | grep a22a680
```

### nmap no encontrado

```bash
pkg install nmap
# o en Linux: sudo apt install nmap
```

### cryptography no instala en Termux

```bash
pkg install rustc libopenssl
pip install cryptography --no-binary :all:
```

### El informe no se guarda

```bash
# Verificar permisos de almacenamiento
termux-setup-storage
ls ~/storage/downloads/
# Debe existir el directorio
```

### SQLite database locked

El acceso a SQLite es thread-safe con `db_lock`. Si ves "database is locked", puede ser otro proceso de commander corriendo:

```bash
ps aux | grep commander
# matar duplicados
pkill -f commander.py
```

### SourceSeal API no responde

Commander funciona en modo offline si la API no responde. El hash se guarda localmente:

```
⚠️ Anclaje offline: [Errno] Connection refused
```

No es un error — el informe se genera igual con el hash SHA-256.

---

## 📌 DIFERENCIAS CON RED-TEAM-TAURI

| Aspecto | Commander | Red-team-tauri |
|---|---|---|
| Tipo | CLI standalone | Backend FastAPI + Frontend React |
| Interfaz | Terminal (argparse) | Web dashboard (navegador) |
| Backend | Sin backend — un solo .py | FastAPI :8001 |
| Puerto | Ninguno | 8001 (API + frontend) |
| DB | SQLite (~/.commander.db) | JSON files + SQLite (ARTO) |
| Escaneo | nmap directo | nmap via API endpoint |
| OSINT | ip-api + ipwho.is + RDAP + WHOIS + Google DoH | Multi-source threat intel + domain + email OSINT |

### 🔍 OSINT Profesional (v3.5)

**OSINT IP** (`osint_ip`):
- Geo IP multi-source: ip-api.com + ipwho.is
- Threat scoring: proxy/VPN, hosting, Tor detection
- WHOIS (binario o RDAP HTTP fallback)
- Reverse DNS local
- Niveles: LOW / MEDIUM / HIGH / CRITICAL

**OSINT Dominio** (`osint_domain`):
- DNS records via Google DNS-over-HTTPS (A, MX, NS, TXT)
- SPF/DMARC verification
- WHOIS via binario o RDAP fallback
- Subdominio enumeration pasivo (20 comunes)
- HTTP header fingerprinting + security score

**OSINT Email** (`osint_email`):
- MX/SPF/DMARC verification via Google DoH
- Provider detection (Gmail, Outlook, Proton, etc.)
- SHA-256 hash (Zero-PII)
- Free provider detection

> Todas las funciones OSINT usan stdlib (urllib, socket) — sin dependencias extra más allá de `cryptography`.

| Cifrado | Fernet (informes .enc) | API Key (auth Bearer) |
| Blockchain | Anclaje SourceSeal directo | Sin anclaje directo |
| Deploy | Termux / Replit (Python) | Termux / Replit (Python + Node) |
| Deps | cryptography | fastapi, uvicorn, httpx, pydantic, etc. |

**Son repositorios independientes.** No comparten código ni configuración.

---

## 📝 CHANGELOG

- **v4.0.0** CLI argparse + logging dual + checkpoints reales por fase (commit f3a6090)
- **v3.4.0** fix: temp_dir escribible en Termux (commit a22a680)
- **v3.3.0** deps: requirements.txt (commit 1be71b0)
- **v3.0** README + instalación + uso + flujo de checkpoints (commit 3db7cd5)
- **v1.0** Initial commit (commit 61e07fa)

---

## 🔗 LINKS

- **Repo**: https://github.com/sourceseal-star/commander
- **Dominio**: https://sourceseal.co
- **Replit**: configurado via `.replit` (Python 3.12)

---

© 2026 SourceSeal Corp. Uso autorizado únicamente. Los escaneos deben ejecutarse dentro de un alcance autorizado.
