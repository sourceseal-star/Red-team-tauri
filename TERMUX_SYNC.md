# Guía de Termux: actualizar, sincronizar y levantar todo

Esta es la guía del flujo activo para Android:

- **Red-team-tauri**: dashboard + frontend en `http://127.0.0.1:8001`.
- **Commander**: integrado dentro del dashboard, sin servidor separado.
- **COM-LINK**: disponible bajo `/api/commander/comlink/*`.
- **GHOST HUNTER PHANTOM**: Master en `http://127.0.0.1:8002`.

No ejecutes `commander.py` ni `commander_server.py` aparte para el flujo normal.
No se usa el puerto `8003`.

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
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

El script crea Commander en `~/commander`, prepara COM-LINK y conserva el
archivo local `.env` si ya existe. La primera ejecución puede tardar porque
instala dependencias y compila el frontend.

## 3. Arranque inmediato sin actualizar

Si tienes trabajos locales o la sincronización muestra `cannot pull with
rebase: You have unstaged changes`, no uses `git reset` ni borres archivos.
Para probar ahora mismo la versión que ya está en el teléfono:

```bash
cd ~/Red-team-tauri
bash arrancar_termux.sh
```

Este script no hace `git pull`, no hace `reset`, no hace `stash` y no instala
paquetes. Solo carga el `.env` existente y levanta Dashboard, Commander
in-process y PHANTOM. Déjalo abierto y presiona `Ctrl+C` cuando termines.

## 4. Actualizar y sincronizar

Detén el sistema con `Ctrl+C` en la terminal donde está corriendo y revisa
primero si tienes cambios locales:

```bash
cd ~/Red-team-tauri
git status --short
git -C ~/commander status --short 2>/dev/null || true
```

Si tienes cambios que quieres conservar, haz commit o guárdalos explícitamente
antes de actualizar:

```bash
git add -A
git commit -m "Cambios locales de Termux"
```

O, si todavía no quieres hacer commit:

```bash
git stash push -u -m "respaldo local antes de actualizar"
git -C ~/commander stash push -u -m "respaldo local antes de actualizar" 2>/dev/null || true
```

Después sincroniza y vuelve a levantar todo con el mismo comando:

```bash
cd ~/Red-team-tauri
COMMANDER_REPO_URL=git@github.com:sourceseal-star/commander.git \
  bash termux_recover.sh
```

El sincronizador ahora se detiene antes de tocar Git si encuentra cambios
locales sin guardar. En ese caso, usa el arranque local de la sección anterior
o guarda primero el trabajo con commit/stash.

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

El estado de COM-LINK debe indicar `available: true` y mostrar sus canales.
El arranque no envía mensajes ni activa SMS, Telegram, radio, satélite,
Bluetooth, mesh o VoIP.

## 6. COM-LINK

COM-LINK se consulta desde:

```text
GET /api/commander/comlink/status
POST /api/commander/comlink/send
```

El envío real requiere configurar el canal y el destino en Commander. No
pruebes `send` con un destino real hasta confirmar la configuración: esa ruta
sí puede iniciar una comunicación externa. El arranque y el health check son
seguros y no hacen envíos.

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