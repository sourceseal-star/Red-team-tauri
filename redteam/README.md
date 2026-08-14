# Red Team — App de Ventas + SOURCESEALCORP

Agente Red Team **independiente** y autocontenido. Audita:
- App móvil de control de pagos/ventas de celulares (Android/iOS)
- Backend web (panel admin + API REST)
- Plataforma **SOURCESEALCORP** (hash blockchain + time-lock + regeneración)
- **Página de recuperación de hashes** (target crítico)

> ⚠️ El agente **no comparte credenciales, ni procesos, ni red** con el software
> de producción del cliente. Solo opera contra builds propias, la subred de
> honeypots, y la API/página de SOURCESEALCORP autorizada.

## Estructura

```
redteam/
├── runner/orchestrator.py         # corre los 11 escenarios
├── scenarios/                     # 11 escenarios de ataque
│   ├── rng.py                     #   1. CSPRNG / entropía
│   ├── pinning.py                 #   2. Cert/Key pinning
│   ├── sidechannel.py             #   3. Timing / constant-time
│   ├── keyhandling.py             #   4. Claves hardcodeadas
│   ├── payments.py                #   5. PayPal/Stripe/Binance/MercadoPago
│   ├── biometric.py               #   6. Templates biométricos
│   ├── business_logic.py          #   7. IDOR, precios, race, 2FA
│   ├── imei.py                    #   8. Luhn, blacklist
│   ├── multiplatform.py           #   9. Android/iOS/Win/Linux
│   ├── sourcesealcorp.py          #  10. 10 ataques dinámicos
│   └── recovery_page.py           #  11. Página de recuperación (target crítico)
├── ci/                            # CI/CD + reglas Semgrep
├── honeypot/                      # API señuelo
├── agent/standalone/              # Agente Dockerizado
├── integration/
│   ├── thehive/case_creator.py    # Crea cases en TheHive
│   └── notifier.py                # Slack/email/webhook
├── scripts/run_full_pipeline.sh   # Pipeline completo
├── tests/                         # Tests unitarios
├── reports/                       # Reportes generados
└── evidence/                      # Evidencia forense
```

## 11 escenarios

| # | Escenario | Tipo |
|---|---|---|
| 1 | rng | Estático (sistema) |
| 2 | pinning | Dinámico (backend) + Estático (app) |
| 3 | sidechannel | Estático |
| 4 | keyhandling | Estático |
| 5 | payments | Estático (4 pasarelas) |
| 6 | biometric | Estático |
| 7 | business_logic | Estático |
| 8 | imei | Estático (Luhn) |
| 9 | multiplatform | Estático |
| 10 | sourcesealcorp | **Dinámico (10 ataques)** |
| 11 | recovery_page | **Dinámico (target crítico)** |

## 10 ataques dinámicos de SOURCESEALCORP

| ID | Ataque |
|---|---|
| A1 | Reuso de hash anterior |
| A2 | Time-lock bypass |
| A3 | Race condition (N threads) |
| A4 | Rate limit / burst |
| A5 | Firma HMAC ausente / inválida |
| A6 | Replay attack |
| A7 | Path traversal en recuperación |
| A8 | Canary hash exposure |
| A9 | Health + latencia |
| A10 | Confirmación blockchain |

## 6 checks en la página de recuperación

- Headers de seguridad (HSTS, CSP, X-Frame-Options)
- Lista sin auth
- IDOR en endpoint individual
- CSRF / mutación sin token
- Clickjacking
- 2FA en acciones críticas

## Uso

### Local
```bash
pip install -r requirements.txt
./scripts/run_full_pipeline.sh build/app.apk https://api.tu-dominio.com
```

### Docker (recomendado para producción)
```bash
cd agent/standalone
cp .env.example .env  # rellenar
docker build -t redteam-agent .
docker run --rm \
  --network redteam-isolated \
  -v /ruta/a/app.apk:/agent/evidence/app.apk:ro \
  -v $(pwd)/../../reports:/agent/reports \
  -v $(pwd)/../../evidence:/agent/evidence \
  --env-file .env \
  redteam-agent
```

### Solo el pipeline de notificación
```bash
python3 integration/thehive/case_creator.py reports/latest-report.json
python3 integration/notifier.py reports/latest-report.json
```

### Solo el escenario SOURCESEALCORP
```bash
SOURCESEAL_API=https://api.real.sourcesealcorp.com \
SOURCESEAL_KEY=tu-key-real \
RECOVERY_PAGE=https://recuperacion.real.com \
python3 scenarios/sourcesealcorp.py
```

## Tests

```bash
python3 tests/test_scenarios.py
```

## Salida

- `reports/report-YYYYMMDD-HHMMSS.json` — datos estructurados
- `reports/latest.md` — resumen Markdown
- `evidence/A1..A10-*.json` — resultado de cada ataque dinámico
- `evidence/recovery-*.json` — checks de la página de recuperación
- `evidence/honeypot/*.json` — capturas del honeypot
- `evidence/sourceseal-attacks.json` — log consolidado

## Variables de entorno

Ver `agent/standalone/.env.example` para la lista completa.

## Consideraciones legales

✅ Solo sobre infraestructura propia con autorización escrita.
❌ Nunca contra sistemas de terceros.

---

## 🚀 Despliegue

### Opción A: Replit (más fácil, ejecutar en la nube)

1. Ve a [replit.com](https://replit.com) → New Repl → Import from GitHub (o sube el ZIP)
2. Replit detecta `.replit` y `replit.nix` automáticamente
3. En la pestaña **Secrets**, agrega:
   - `SOURCESEAL_API` = tu URL real
   - `SOURCESEAL_KEY` = tu key HMAC
   - `RECOVERY_PAGE` = URL de la página de recuperación
4. Pulsa **Run**. El dashboard aparece en la URL del Repl.
5. En el celular: abre la URL del Repl en Chrome/Safari → "Agregar a pantalla de inicio" → ya tienes la app PWA.

### Opción B: Vercel (dashboard público, escaneos limitados)

```bash
npm i -g vercel
cd redteam
vercel --prod
# configurar env vars en el dashboard de Vercel:
#   SOURCESEAL_API, SOURCESEAL_KEY, RECOVERY_PAGE
```

⚠️ Vercel tiene timeout de 10–60s. Para escaneos largos usa el agente Docker.

### Opción C: Docker (recomendado para producción)

```bash
cd agent/standalone
cp .env.example .env  # rellenar
docker build -t redteam-agent .
docker run -d --name redteam \
  -p 8000:8000 \
  -v $(pwd)/reports:/agent/reports \
  -v $(pwd)/evidence:/agent/evidence \
  --env-file .env \
  redteam-agent
```

Dashboard en `http://localhost:8000`.

### Opción D: Local sin Docker

```bash
pip install -r requirements.txt
python3 scripts/dashboard_server.py
# abre http://localhost:8000
```

---

## 📱 App en el celular

Una vez desplegado (Replit, Vercel o tu servidor):

1. Abre la URL en Chrome (Android) o Safari (iOS)
2. Menú → **"Agregar a pantalla de inicio"**
3. La PWA se instala como app nativa, con icono propio
4. Funciona offline (los reportes cacheados se ven sin conexión)
5. Recibe push si configuras las notificaciones (requiere HTTPS)

## 🧪 Tests

```bash
python3 tests/test_scenarios.py
```

---

## 🍯 Honeytramp (defensa contra Pegasus / stalkerware / spyware comercial)

Componentes defensivos para detectar compromiso por spyware de alta sofisticación.
**Solo sobre dispositivos con consentimiento explícito del usuario (EULA + opt-in).**

### Componentes

| Componente | Archivo | Función |
|---|---|---|
| **C2 Sinkhole** | `honeypot/c2-sinkhole/sinkhole.py` | Emula endpoints de C2 de NSO/FinFisher/HT/Candiru. Si el spyware beacon-ea, queda registrado. |
| **DNS Sinkhole** | `honeypot/c2-sinkhole/dns_sinkhole.py` | Resuelve dominios IoC de C2 a nuestra IP. Redirige el spyware al sinkhole. |
| **Canary Files** | `honeypot/canary-files/generate.py` | Archivos trampa con canary tokens. Detección por acceso o borrado. |
| **Network IDS** | `honeypot/network-ids/ids_rules.py` | Reglas Suricata + patrones pcap para IoC conocidos. |
| **Escenario Pegasus** | `scenarios/pegasus.py` | Análisis activo del dispositivo: procesos, persistencia, IoC DNS, canarios. |

### Familias detectadas

- **NSO Group** (Pegasus, Pegasus Bridge)
- **FinFisher / Gamma Group** (FinSpy, fcms, scrs)
- **HackingTeam** (RCS, HT-Bridge)
- **Candiru** (Sourgum, DevilsTongue)
- **Stalkerware comercial** (mSpy, FlexiSpy, Hoverwatch)

### Desplegar el honeytramp

```bash
# C2 sinkhole + DNS sinkhole
docker build -f honeypot/Dockerfile.pegasus -t redteam-honeytramp honeypot/
docker run -d --name honeytramp \
  -p 8443:8443 \
  --network redteam-isolated \
  -v $(pwd)/evidence:/honeypot/evidence \
  redteam-honeytramp

# Canary files en directorios objetivo
python3 -c "
from honeypot.canary-files.generate import deploy, CanaryWatchdog
import time
paths = deploy(['/tmp/DCIM', '/tmp/Downloads', '/tmp/Documents'])
print('Deployed:', paths)
w = CanaryWatchdog([p['path'] for p in paths if 'path' in p], poll_interval=1.0)
w.start()
time.sleep(5)
print('Alerts:', w.alerts)
"

# Reglas Suricata (si tienes Suricata instalado)
sudo cp honeypot/network-ids/suricata.rules /etc/suricata/rules/redteam.rules
sudo suricatasc -c reload-rules
```

### Escenario Pegasus

```bash
CHECK_CANARY_PATHS=/tmp/canary1.txt,/tmp/canary2.txt \
CHECK_DNS_DOMAINS=nsogroup.com,mspy.com \
python3 scenarios/pegasus.py
```

### ¿Qué detecta y qué no?

✅ **Detecta**: IoC conocidos en DNS, HTTP, procesos, persistencia, accesos a canarios
❌ **No detecta**: 0-day exploits no conocidos, spyware que se carga antes del kernel
⚠️ **Limitación crítica**: este es análisis estático + reglas. Pegasus cambia IoC. Mantener actualizado.
