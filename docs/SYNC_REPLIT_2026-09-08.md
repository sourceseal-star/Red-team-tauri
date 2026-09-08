# Guía rápida — Sincronizar, actualizar y levantar TODO (2026-09-08)

Estado verificado antes de escribir esto: ambos repos limpios y 100% empujados
a GitHub. Red-team-tauri @ a17655c · sol @ 8fa708b.

## En el teléfono (Termux) — TODO en un comando

```bash
cd ~/Red-team-tauri
bash omni.sh sync        # git pull de los 3 repos + deps + build del frontend (NO toca .env)
bash omni.sh restart     # baja todo y sube limpio: dashboard :8001, Sol :8006, guardias
bash omni.sh status      # verificar que TODO esté verde
```

- ¿Comportamiento raro, pantalla negra, puerto secuestrado? → `bash curar.sh`
  PRIMERO, antes de tocar nada a mano (regla del LEEME_PRIMERO).
- Phone Intel / guardia de radio nuevos:
  ```bash
  nohup python3 redteam/scripts/phone_intel_v2.py --guard &
  python3 redteam/scripts/phone_intel_v2.py --list   # ver análisis de llamadas
  ```

## En Replit — repo privado `sol`

1. Abrir el Shell de Replit y hacer `git pull` (o usar el botón de Git Pull
   del panel de control de versiones).
2. Botón **Run** para probar (`sol_api.py` standalone, NO necesita nada de
   Red-team-tauri).
3. **Deploy** (no solo Run) para que quede persistente 24/7 sin depender de
   la pestaña abierta — sigue pendiente desde el LEEME_PRIMERO.

## Reglas de oro (del LEEME_PRIMERO)

- Commit ANTES de cualquier cambio grande.
- Nunca `git push --force`, nunca borrar sin confirmación explícita.
- Tras rebuild del frontend: `git add -f tauri-frontend/dist` SIEMPRE
  (el .gitignore bloquea el bundle si no se fuerza).
- `~/sol/.env` NO se toca en los syncs — sigue pendiente completar sus
  credenciales faltantes (ver docs/POSTMORTEM_2026-09-06_pantalla_negra.md).
