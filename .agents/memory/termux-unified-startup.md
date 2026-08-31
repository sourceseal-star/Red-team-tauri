---
name: Termux unified startup
description: Durable rule for starting Red-team-tauri with the separate Commander repository on Android
---

El flujo soportado en Termux separa sincronización y ejecución: `setup.sh`
prepara/sincroniza ambos repositorios y `iniciar_unificado.sh` ejecuta el código
local sin tocar Git. El launcher no debe volver a hacer `stash/pull` durante el
arranque.

El sincronizador respalda cambios tracked/untracked y también submódulos
anidados; crea ramas `backup/termux-*` para commits locales, alinea los
submódulos al remoto y se detiene si todavía queda un estado no limpio.

Commander se carga dentro del dashboard por `/api/commander/*`; no necesita un
servidor adicional ni el puerto 8003. El launcher debe comprobar el health del
dashboard y del PHANTOM Master, y detener todo si un proceso muere al iniciar.

**Why:** En Termux, el arranque anterior podía fallar con `cannot pull with rebase:
You have unstaged changes`; además, `git stash` del padre no protege cambios
internos de submódulos, lo que dejaba estados `M` y bloqueaba la actualización.

**How to apply:** Para actualizar usa `bash setup.sh`; para ejecutar sin tocar Git
usa `COMMANDER_DIR="$HOME/commander" bash iniciar_unificado.sh`. Verifica los
endpoints en `127.0.0.1:8001` y `127.0.0.1:8002`.