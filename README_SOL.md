# SOL DEFINITIVA v2

Un cerebro (`sol_core`), un API (`:8006`), una memoria (`~/.sol/memory.jsonl`), una cara canónica (`dist/sol.html` + `sol_avatar.png`), y un watchdog que revive procesos Y restaura la identidad si alguien la toca.

- **sol_api.py**: `/api/sol/{state,chain,memory,services,think,chat,personality}`
- **sol_watchdog.sh**: cada 30s revive API/daemon/puente; hash+backup de `sol.html`; avatar local; alerta Telegram si la memoria desaparece.
- **Widget**: `redteam/scripts/static/sol_chat_widget.html` (iframe en dashboard).

**Reglas:** nadie rediseña `sol.html`; memoria solo `role/content/ts`; credenciales intocadas.

## Cableado
1. Añade el iframe en el dashboard:
   `<iframe src="/static/sol_chat_widget.html" style="position:fixed;bottom:20px;right:20px;width:380px;height:560px;border:0;z-index:9999;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.35)"></iframe>`
2. En `omni.sh`, incluye `start_sol_stack`.
3. Guarda el avatar en `tauri-frontend/dist/sol_avatar.png`.
4. `git add -A && git commit -m "feat: SOL DEFINITIVA v2 — cerebro único, identidad blindada" && git push`

## Comprobación
```bash
curl http://127.0.0.1:8006/api/sol/state
```
