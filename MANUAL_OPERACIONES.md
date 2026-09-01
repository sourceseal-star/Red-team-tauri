# MANUAL DE OPERACIONES — Ecosistema SourceSeal (2026-08-31)
> Regla de oro: NUNCA escribir valores reales de claves en este documento.

## 0. Leyes del sistema (aprendidas a sangre, 26h)
1. `.env` es la única fuente de verdad de credenciales (permisos 600).
2. `ss`/`netstat -p` MIENTEN en Android sin root (Permission denied) → usar `curl` y `pgrep`.
3. `psutil` NO existe en Android/Python 3.14 → métricas opcionales.
4. `/tmp` puede negar redirecciones → logs siempre en `~/`.
5. Todo cambio de código → `git commit` + `git push` ANTES de probar cosas riesgosas.
6. Respaldo cifrado (`c2-backup`) después de cada cambio mayor.

## 1. Mapa de servicios
| Puerto | Servicio | Login |
|---|---|---|
| 8001 | Dashboard + Commander | ADMIN_EMAIL / ADMIN_PASSWORD (.env) |
| 8002 | PHANTOM Master | (interno) |
| 8004 | NEXUS OMNI | NEXUS_USER / NEXUS_PASS (.env) |
| 8005 | Controller (pendiente) | REDTEAM_API_KEY |

Archivos clave: `.env`, `control_claves.sh`, `auth_bootstrap.py`,
`nexus_credentials.py`, `iniciar_unificado.sh`, `redteam/scripts/.auth/password.json`

## 2. Arranque diario
    cd ~/Red-team-tauri
    COMMANDER_DIR="$PWD/commander" bash iniciar_unificado.sh
    pgrep -f nexus_omni || nohup python3 nexus_omni_v9.py > ~/nexus.log 2>&1 &
(El launcher NO arranca Nexus: se arranca manual.)

## 3. Verificación (sin ss)
    curl -s http://127.0.0.1:8001/api/health
    curl -s -m 3 -o /dev/null -w "%{http_code}" http://127.0.0.1:8004/  # 401 = vivo
    pgrep -f nexus_omni

## 4. Credenciales
    bash control_claves.sh set|status|restore|rotate
- Respaldo de secretos: ~/.c2/env_respaldo.aes
- PASSPHRASE: anotada EN PAPEL, guardada física. (Única cosa no recuperable.)
- Los .aes pueden vivir en Drive: cifrados son inútiles sin la passphrase.

## 5. Recuperación desde CERO (móvil nuevo / Termux limpio)
1. Termux de F-Droid + `termux-setup-storage`
2. `pkg install git openssh` + clave SSH en GitHub
3. `git clone git@github.com:sourceseal-star/Red-team-tauri.git ~/Red-team-tauri`
4. `cd ~/Red-team-tauri && bash setup.sh` (o `termux_recover.sh`)
5. Bajar el .aes de Drive → `bash control_claves.sh restore`
6. Arranque diario + verificación.

## 6. Trampas conocidas
- Ramas divergentes: `git pull --rebase origin main`; si lo local no vale: `git fetch && git reset --hard origin/main`.
- Replit: cuota muere a mitad de trabajo → push antes de pruebas.
- `auth_bootstrap` corre con `|| true` → si falla, es SILENCIOSO: probar `python3 auth_bootstrap.py --verbose`.
- Ruta `/api/commander/health` dio 404 en v3 → usar `/api/health`.

## 7. Bitácora de incidentes 2026-08-30/31
- Agente Replit borró workspace por variable HOME sin scope → restaurado por checkpoint; código vivo en GitHub+Termux.
- Cuota Replit murió post-push parcial → rescate manual vía Termux.
- Credenciales auto-generadas "impresas una vez" → lockout de horas → solución: control_claves.sh (.env dueño = operador).
- Nexus no arrancaba con el launcher + ss ciego + /tmp capado → diagnóstico real con curl/pgrep; arranque manual.


## 8. Recuperación de Lockout

> Si no puedes entrar al dashboard o Nexus responde 401/403, NO intentes regenerar
> credenciales desde un agente. Usa estos pasos en orden.

### Escenario A: .env existe pero una clave está mal

```bash
cd ~/Red-team-tauri

# 1. Verificar estado sin revelar valores
bash control_claves.sh status

# 2. Si necesitas redefinir manualmente
nano .env
# Cambiar SOLO la variable problemática
chmod 600 .env

# 3. Borrar hash viejo para que se regenere
rm -f redteam/scripts/.auth/password.json

# 4. Reiniciar
bash iniciar_unificado.sh
```

### Escenario B: .env se borró o corrompió

```bash
cd ~/Red-team-tauri

# Opción 1 — Restaurar desde snapshot cifrado
bash scripts/restore_env.sh
# Lista snapshots disponibles, elige uno, pide passphrase

# Opción 2 — Restaurar desde respaldo de control_claves
bash control_claves.sh restore
# Pide passphrase del respaldo en ~/.c2/env_respaldo.aes

# Opción 3 — Definir desde cero (último recurso)
bash control_claves.sh set
# Te pedira nuevas credenciales

# Después de cualquier opción:
bash iniciar_unificado.sh
bash scripts/healthcheck_all.sh
```

### Escenario C: Nexus Omni inaccesible (401/403)

```bash
cd ~/Red-team-tauri

# 1. Verificar que Nexus está corriendo
curl -s http://127.0.0.1:8004/ -o /dev/null -w "%{http_code}"

# 2. Si no responde, arrancar desde Control Tower o manualmente:
python3 nexus_omni_v9.py &

# 3. Si responde pero da 401 — credenciales no coinciden
# Verificar que NEXUS_USER y NEXUS_PASS en .env son correctos
grep "^NEXUS_USER=" .env
grep "^NEXUS_PASS=" .env

# 4. Probar acceso directo con las credenciales del .env
NEXUS_USER_VAL="$(grep "^NEXUS_USER=" .env | cut -d= -f2)"
NEXUS_PASS_VAL="$(grep "^NEXUS_PASS=" .env | cut -d= -f2)"
curl -u "$NEXUS_USER_VAL:$NEXUS_PASS_VAL" http://127.0.0.1:8004/

# 5. Si funciona directo pero no via dashboard proxy:
# El dashboard lee las mismas credenciales de .env vía nexus_credentials.py
# Reiniciar el dashboard para que relea:
pkill -f dashboard_server.py
bash iniciar_unificado.sh
```

### Prevención: crear snapshot antes de cambios

```bash
# ANTES de cualquier cambio en el sistema:
bash scripts/snapshot_env.sh
# Pide passphrase, guarda copia cifrada en ~/.c2/snapshots/

# Verificar que el snapshot funciona:
# (restore_env.sh te deja elegir y probar sin tocar el .env real)
```

### Scripts de recuperación disponibles

| Script | Cuándo usarlo |
|--------|---------------|
| `scripts/restore_env.sh` | .env borrado o corrompido — restaura desde snapshot |
| `scripts/snapshot_env.sh` | Antes de cambios — crea snapshot cifrado |
| `control_claves.sh restore` | .env borrado — restaura desde respaldo de control_claves |
| `control_claves.sh set` | Desde cero — define nuevas credenciales |
| `control_claves.sh status` | Verificar sin revelar valores |

### Reglas de oro

1. **.env es la única fuente de verdad** — el código nunca lo sobrescribe si los valores ya existen
2. **Nunca borrar .env sin tener un snapshot** — ejecuta `snapshot_env.sh` antes de cualquier cambio
3. **Si un agente (Replit u otro) toca el repo**, verifica con `control_claves.sh status` después
4. **El preflight de iniciar_unificado.sh aborta si .env falta o está incompleto** — no arranca servicios con credenciales vacías
5. **password.json se regenera solo** desde .env — borrarlo es seguro, borrar .env NO
