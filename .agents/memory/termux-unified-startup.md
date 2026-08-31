---
name: Termux unified startup
description: Durable rule for starting Red-team-tauri with the separate Commander repository on Android
---

El flujo soportado en Termux separa sincronización y ejecución: `termux_recover.sh`
prepara/sincroniza ambos repositorios y `arrancar_termux.sh` ejecuta el código
local sin tocar Git. El launcher histórico no debe volver a hacer `stash/pull`
durante el arranque.

Commander se carga dentro del dashboard por `/api/commander/*`; no necesita un
servidor adicional ni el puerto 8003. El launcher debe comprobar el health del
dashboard y del PHANTOM Master, y detener todo si un proceso muere al iniciar.

**Why:** En Termux, el arranque anterior podía fallar con `cannot pull with rebase:
You have unstaged changes` y además dejar servicios parcialmente iniciados, lo que
hacía parecer que el sistema no funcionaba.

**How to apply:** Para cambios locales usa `bash arrancar_termux.sh`; para
sincronizar usa `bash termux_recover.sh` después de guardar o revisar cambios
locales. Verifica los endpoints en `127.0.0.1:8001` y `127.0.0.1:8002`.