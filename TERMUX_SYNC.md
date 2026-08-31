# Guía de Termux: actualizar, sincronizar y levantar todo

**Última actualización:** 2026-08-30

Esta es la guía del flujo activo para Android:

- **Red-team-tauri**: dashboard + frontend en `http://127.0.0.1:8001`.
- **Commander**: integrado dentro del dashboard, sin servidor separado.
- **COM-LINK**: disponible bajo `/api/commander/comlink/*`.
- **GHOST HUNTER PHANTOM**: Master en `http://127.0.0.1:8002`.

No ejecutes `commander.py` ni `commander_server.py` aparte para el flujo normal.
No se usa el puerto `8003`.

## Comandos principales

```bash
# Arranque local inmediato: no toca Git
cd ~/Red-team-tauri
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh

# Preparar, sincronizar y arrancar
bash termux_recover.sh
```

`arrancar.sh` y `termux_setup.sh` se mantienen como alias compatibles del
recuperador. Si hay cambios locales sin guardar, el recuperador se detiene; usa
`COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh` para probar primero la
versión local.

## 1. Preparación inicial

Instala Termux desde F-Droid. En Termux, prepara el acceso al almacenamiento
si lo necesitas:

```bash
termux-setup-storage
```

El script principal instala los paquetes del sistema, Python, Node.js, SQLite,
`jq`, `curl`, `openssl`, `nmap` y `termux-api`. Para poder clonar el primer
repositorio instala Git y SSH antes:

```bash
pkg update -y
pkg install -y git openssh
```

### Autenticación de GitHub por SSH

Si todavía no tienes una clave en Termux:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "termux" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

No sobrescribas una clave existente. Copia la clave pública en GitHub:

**GitHub → Settings → SSH and GPG keys → New SSH key**

Comprueba la autenticación:

```bash
ssh -T git@github.com
```

GitHub puede responder con código 1 aunque la autenticación sea correcta; lo
importante es que el mensaje confirme que la clave fue aceptada.

## 2. Primera instalación

Clona Red-team-tauri y ejecuta el recuperador desde su raíz:

```bash
git clone git@github.com:sourceseal-star/Red-team-tauri.git ~/Red-team-tauri
cd ~/Red-team-tauri
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

Si Red-team-tauri ya está clonado, basta con:

```bash
cd ~/Red-team-tauri
bash termux_recover.sh
```

El script crea Commander en `~/commander`, prepara COM-LINK y conserva el
archivo local `.env` si ya existe. La primera ejecución puede tardar porque
instala dependencias y compila el frontend.

### Actualizar mediante `setup.sh` usando `nano`

Si necesitas crear o editar el bootstrap directamente desde Termux:

```bash
cd ~/Red-team-tauri
nano setup.sh
```

Guarda con `Ctrl+O`, confirma con `Enter` y sal con `Ctrl+X`. Después ejecuta:

```bash
bash setup.sh
```

`setup.sh` instala las herramientas necesarias, sincroniza
`Red-team-tauri` y `commander` por SSH, instala dependencias, recompila el
frontend y comprueba que exista el monitor seguro. No inicia servidores por
defecto. Para actualizar y arrancar al terminar:

```bash
bash setup.sh --start
```

Para registrar cambios locales hechos después con `nano`:

```bash
bash setup.sh --watch
tail -f ~/.sourceseal/watcher.log
```

El watcher calcula SHA-256 de los archivos Python de `redteam/runner` y
`redteam/modules`, registra los cambios en la auditoría local y deja que el
próximo `/api/scan` cargue el código actualizado en un proceso nuevo. No
ejecuta automáticamente el archivo modificado ni reinicia procesos. Se puede
combinar con el arranque:

```bash
bash setup.sh --start --watch
```

También puedes guardar una copia del script en `~/setup.sh` y ejecutar
`bash ~/setup.sh`; si la carpeta `~/Red-team-tauri` no existe, el bootstrap la
clona usando `REDTEAM_REPO_URL`.

## 3. Arranque inmediato sin actualizar

Si tienes trabajos locales o la sincronización muestra `cannot pull with
rebase: You have unstaged changes`, no uses `git reset` ni borres archivos.
Para probar ahora mismo la versión que ya está en el teléfono:

```bash
cd ~/Red-team-tauri
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

Este comando no hace `git pull`, no hace `reset`, no hace `stash` y no instala
paquetes. Solo carga el `.env` existente y levanta Dashboard, Commander
in-process y PHANTOM. Déjalo abierto y presiona `Ctrl+C` cuando termines.

## 4. Actualizar y sincronizar

Este es el flujo recomendado para actualizar todo desde Termux. Detén el
sistema con `Ctrl+C` en la terminal donde está corriendo y ejecuta:

```bash
cd ~/Red-team-tauri
bash setup.sh
```

Si tu teléfono todavía tiene la versión anterior y muestra `quedaron cambios
después del respaldo`, descarga primero el sincronizador corregido en una
ubicación temporal y ejecútalo sin modificar ni borrar tus archivos:

```bash
cd ~/Red-team-tauri
curl -fsSL \
  https://raw.githubusercontent.com/sourceseal-star/Red-team-tauri/main/scripts/termux/sync_repositories.sh \
  -o /tmp/sourceseal-sync.sh
chmod 700 /tmp/sourceseal-sync.sh
REDTEAM_DIR="$HOME/Red-team-tauri" \
COMMANDER_DIR="$HOME/commander" \
REDTEAM_REPO_URL="git@github.com:sourceseal-star/Red-team-tauri.git" \
COMMANDER_REPO_URL="git@github.com:sourceseal-star/commander.git" \
  bash /tmp/sourceseal-sync.sh
```

Después ya puedes usar normalmente `bash setup.sh`. Si tu copia de Commander
está dentro de `Red-team-tauri`, cambia `COMMANDER_DIR` por
`"$HOME/Red-team-tauri/commander"`.

`setup.sh` actualiza SourceSeal y Commander, instala dependencias, recompila el
frontend y verifica los componentes nuevos. Si quieres dejar además el watcher
local ejecutándose:

```bash
bash setup.sh --watch
```

Si quieres actualizar y arrancar el sistema al terminar:

```bash
bash setup.sh --start
```

También puedes hacer ambas cosas:

```bash
bash setup.sh --start --watch
```

El sincronizador respalda cambios del repositorio y también de submódulos
anidados antes de actualizar. Si un submódulo tiene commits locales, crea una
rama `backup/termux-...`; si tiene cambios sin commit, los guarda en su stash.
Solo después alinea los submódulos y actualiza el repositorio padre. Si aun así
detecta cambios, se detiene y muestra el estado sin borrar nada.

Para consultar o recuperar un respaldo local:

```bash
git stash list
git -C ~/commander stash list 2>/dev/null || true
git branch --list 'backup/termux-*'
git -C ~/commander branch --list 'backup/termux-*' 2>/dev/null || true
```

Si necesitas arrancar inmediatamente la copia local sin actualizar Git:

```bash
cd ~/Red-team-tauri
COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
```

Para detener el watcher:

```bash
WATCH_PID_FILE="$HOME/.sourceseal/watcher.pid"
if [ -f "$WATCH_PID_FILE" ]; then
  kill "$(cat "$WATCH_PID_FILE")" 2>/dev/null || true
  rm -f "$WATCH_PID_FILE"
fi
```

En una actualización normal, el script:

1. actualiza los paquetes de Termux;
2. hace `fetch` y `pull --rebase` de ambos repositorios;
3. verifica `commander.py` y prepara COM-LINK;
4. instala las dependencias Python;
5. instala y compila el frontend;
6. preserva `.env`;
7. levanta dashboard, Commander in-process y PHANTOM.

## 5. Comprobaciones después del arranque

El recuperador permanece en primer plano. En otra sesión de Termux, ejecuta:

```bash
curl http://127.0.0.1:8001/api/health
curl http://127.0.0.1:8002/api/status
```

En Android/Termux con Python 3.14, `psutil` se omite intencionalmente porque
su compilación upstream no soporta Android. El backend lo trata como opcional;
el dashboard, Commander y PHANTOM siguen funcionando sin las métricas avanzadas
de proceso/memoria que aporta esa librería.

Para comprobar las rutas protegidas sin mostrar la API key en pantalla:

```bash
cd ~/Red-team-tauri
set -a
. ./.env
set +a

curl -H "Authorization: Bearer ${REDTEAM_API_KEY}" \
  http://127.0.0.1:8001/api/commander/health

curl -H "Authorization: Bearer ${REDTEAM_API_KEY}" \
  http://127.0.0.1:8001/api/commander/comlink/status
```

`available: true` solo indica que el script está instalado. El estado real debe
consultarse con:

```bash
bash commander/comlink/comlink.sh status-json | jq
```

Revisa `ready_count`, `ready_channels` y `channels[].reason`. `ready` confirma
requisitos locales conocidos, no la entrega de un mensaje. El arranque no envía
mensajes ni activa SMS, Telegram, radio, satélite, Bluetooth, mesh o VoIP.

## 6. COM-LINK

COM-LINK se consulta desde:

```text
GET /api/commander/comlink/status
POST /api/commander/comlink/send
```

El envío real requiere configurar el canal, sus dependencias y el destino en
Commander. No pruebes `send` con un destino real hasta confirmar la
configuración: esa ruta sí puede iniciar una comunicación externa. La matriz
de requisitos está en [`COMLINK_OPERATIVO.md`](COMLINK_OPERATIVO.md).

## 7. Detener y recuperar

Para detener el conjunto iniciado por `termux_recover.sh`:

```text
Ctrl+C
```

Para volver a levantarlo:

```bash
cd ~/Red-team-tauri
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

Si un proceso anterior dejó ocupado un puerto, compruébalo antes de matar nada:

```bash
ss -ltnp | grep -E ':8001|:8002' || true
```

El script detiene las instancias anteriores del dashboard. Si PHANTOM quedó
huérfano, cierra su proceso desde la misma sesión de Termux o reinicia Termux;
no borres archivos de datos para resolver un problema de puertos.

## 8. Archivos útiles y seguridad

- Dashboard: `~/Red-team-tauri/redteam/scripts/dashboard_server.py`
- Launcher unificado: `~/Red-team-tauri/iniciar_unificado.sh`
- Commander: `~/commander`
- Configuración local: `~/Red-team-tauri/.env` con permisos `600`
- Cola COM-LINK: `~/commander/comlink/data/queue/queue.db`

No pongas tokens ni contraseñas en URLs de Git, no publiques `.env` y no
compartas su contenido. Si necesitas cambiar de HTTPS a SSH, usa:

```bash
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```