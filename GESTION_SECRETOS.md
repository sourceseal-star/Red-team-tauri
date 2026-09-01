# Gestión de secretos de SourceSeal

Este documento registra los **nombres y ubicaciones** de credenciales. No
contiene valores reales.

| Variable | Uso | Ubicación recomendada | Rotación |
|---|---|---|---|
| `NEXUS_USER` | Usuario HTTP Basic de Nexus Omni | `.env` local o secreto del entorno | Editar el valor y reiniciar Nexus |
| `NEXUS_PASS` | Contraseña HTTP Basic de Nexus Omni | `.env` con permisos `600` o secreto del entorno | `python3 nexus_omni_v9.py --reset-credentials`, después reiniciar el dashboard |
| `ADMIN_EMAIL` | Identidad del administrador del dashboard | `.env` o configuración del entorno | Editar el valor y reiniciar |
| `ADMIN_PASSWORD` | Contraseña del acceso principal al dashboard | `.env` con permisos `600` o secreto del entorno | `python3 gestionar_credenciales.py --reset-dashboard`, después reiniciar |
| `REDTEAM_API_KEY` | Acceso a rutas protegidas del dashboard | `.env` o secreto del entorno | Generar una nueva clave y reiniciar el dashboard |
| `C2_API_SECRET` | Autenticación de integraciones C2, si se habilita | Secreto del entorno | Rotar en el proveedor y reiniciar el servicio |
| `TELEGRAM_BOT_TOKEN` | Alertas de Telegram, si se habilitan | Secreto del entorno | Revocar el bot anterior y crear uno nuevo |
| `TELEGRAM_CHAT_ID` | Destino de alertas de Telegram | `.env` o configuración del entorno | Cambiar el destino y reiniciar |
| `SHODAN_API_KEY` | Inteligencia de Shodan | `.env` o secreto del entorno | Revocar y crear una clave nueva en Shodan |
| `ABUSEIPDB_KEY` | Consultas de reputación AbuseIPDB | `.env` o secreto del entorno | Revocar y crear una clave nueva en AbuseIPDB |
| `HUNTER_API_KEY` | Consultas Hunter.io | `.env` o secreto del entorno | Revocar y crear una clave nueva en Hunter.io |
| `VIRUSTOTAL_API_KEY` | Consultas VirusTotal | `.env` o secreto del entorno | Revocar y crear una clave nueva en VirusTotal |
| `CENSYS_API_ID` / `CENSYS_API_SECRET` | Acceso Censys | `.env` o secreto del entorno | Rotar desde la cuenta Censys |
| `GOOGLE_API_KEY` / `GOOGLE_CSE_ID` | Google Custom Search | `.env` o configuración del entorno | Rotar la API key y revisar el motor |
| `GITHUB_TOKEN` | Operaciones autorizadas de GitHub | Secreto del entorno o credential helper | Revocar el token y crear uno con alcance mínimo |
| `CORSET_SCOPE_B64` | Alcance autorizado de escaneo | `.env` o configuración del entorno | Cambiar cuando cambie el alcance aprobado |
| `SESSION_SECRET` | Sesiones del entorno Replit | Replit Secrets | Rotar solo coordinadamente con las sesiones activas |
| `ORCHESTRATOR_KEY` | Autenticación del gateway federado | `.env` o secreto del nodo | Rotar en el nodo coordinador |
| `NODE_MOTOR_KEY` / `NODE_INTEL_KEY` | Acceso a nodos remotos opcionales | `.env` o configuración de cada nodo | Rotar en el servicio remoto |
| `REDIS_URL` | Acceso a Redis opcional | Secreto del entorno | Rotar la credencial en Redis |

## Reglas

- `.env` debe permanecer fuera de Git y con permisos `600`.
- Nunca pongas valores de secretos en código, documentación, URLs, capturas o
  mensajes de commit.
- En Replit, guarda los secretos mediante el gestor de Secrets del workspace;
  no los pegues en el chat ni en archivos versionados.

## Recuperar el acceso en el workspace

Desde la raíz del proyecto:

```bash
# Solo nombres, origen y permisos; no muestra valores
python3 gestionar_credenciales.py --status

# Recuperación explícita para el operador local
python3 gestionar_credenciales.py --show

# Crea las credenciales internas que falten
python3 gestionar_credenciales.py --generate-missing
```

El acceso principal usa `ADMIN_EMAIL` y `ADMIN_PASSWORD`; el token que protege
las rutas del dashboard es `REDTEAM_API_KEY`. Nexus usa `NEXUS_USER` y
`NEXUS_PASS`. Las cuatro credenciales internas se guardan en `.env` con modo
`600`; el dashboard nunca guarda la contraseña en texto plano. El comando
`--show` debe ejecutarse solo en una terminal privada y su salida no debe
copiarse a chats, commits, capturas ni tickets.

Para rotar:

```bash
python3 gestionar_credenciales.py --reset-nexus
python3 gestionar_credenciales.py --reset-dashboard
```

Después de cualquier rotación reinicia `SourceSeal Dashboard`. Si la variable
correspondiente existe como Replit Secret o variable de entorno, esa fuente
tiene prioridad sobre `.env` y también debe actualizarse allí.

## Credenciales de proveedores y dispositivos

Las claves de Shodan, AbuseIPDB, Hunter, VirusTotal, Censys, Google y GitHub
deben recuperarse desde sus respectivos paneles y guardarse como Secrets del
workspace. No se pueden generar localmente porque el proveedor debe emitirlas.
Las credenciales de cámaras o dispositivos son de cada activo autorizado y no
son credenciales de acceso al dashboard; deben introducirse solo durante una
operación aprobada.

## GitHub Actions / GitHub Secrets

Para el repositorio `sourceseal-star/Red-team-tauri`:

1. Abre **Settings → Secrets and variables → Actions**.
2. Selecciona **New repository secret**.
3. Crea `NEXUS_PASS` y `REDTEAM_API_KEY` con sus valores fuera del repositorio.
4. En workflows, consúmelos como `${{ secrets.NEXUS_PASS }}` y
   `${{ secrets.REDTEAM_API_KEY }}`; no los escribas en los logs.
5. Al rotar, actualiza el secreto y reinicia el servicio que lo consume.

Si `gh` está autenticado, el procedimiento equivalente es:

```bash
gh secret set NEXUS_PASS
gh secret set REDTEAM_API_KEY
```

Los comandos solicitan el valor de forma interactiva; nunca lo incluyas en la
línea de comandos ni en el historial.