#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════════
#  ⚡ OMNI.SH — SourceSeal Unified Command
#  Un solo comando para levantar todo. Otro para sincronizar.
#  .env NUNCA se toca. Credenciales NUNCA se alteran.
# ═══════════════════════════════════════════════════════════════════════
#
#  USO:
#    bash omni.sh start        — Levanta TODO el sistema de una vez
#    bash omni.sh stop          — Detiene todo limpio
#    bash omni.sh restart       — Stop + Start
#    bash omni.sh status        — Estado de todos los servicios (incluye Sol API, daemon, watchdog, tools, SIL)
#    bash omni.sh sync          — git pull + deps + build (SIN tocar .env)
#    bash omni.sh sync-deps      — Solo instalar/actualizar dependencias
#    bash omni.sh sync-frontend  — Solo rebuild del frontend
#    bash omni.sh logs [serv]    — Ver logs (dash|ghost|tg|nexus|seal|all)
#    bash omni.sh snapshot       — Snapshot cifrado del .env
#    bash omni.sh verify         — Verifica integridad de credenciales
#    bash omni.sh help            — Esta ayuda
#
#  SERVICIOS QUE LEVANTA `start`:
#    :8001  Dashboard FastAPI + Commander integrado
#    :8002  GHOST PHANTOM Master + Node worker
#    :8004  Nexus Omni-Sentient
#    :8005  C2 UNIFIED PRO (si existe)
#    ☀️    Sol Autónoma (daemon que vigila y habla proactivamente)
#    ☀️    Puente Telegram (@sol_amg_bot)
#    🐕    Watchdog (vigila y reinicia caídos)
#    🦭    Seal IA Orquestador (si SEAL_ENABLED=1)
#
#  PROTECCIÓN DE CREDENCIALES:
#    .env es la ÚNICA fuente de verdad.
#    sync NUNCA modifica, regenera, ni borra .env.
#    Antes de sync: snapshot cifrado + checksum SHA-256.
#    Después de sync: verificación de integridad (checksum).
#    start verifica que NEXUS_PASS, ADMIN_PASSWORD, REDTEAM_API_KEY
#    existan ANTES de arrancar — si faltan, se DETIENE para evitar
#    que nexus_credentials.py regenere credenciales sin tu permiso.
#
#  SourceSeal — Operational Link
#  ═══════════════════════════════════════════════════════════════════════

set -uo pipefail

# ═══════════════════════════════════════════════════════════════════
#  LOCK GLOBAL — blindaje contra doble ejecución
#  Si omni.sh corre dos veces a la vez (ej: dos terminales), se levantan
#  procesos duplicados: dos puentes Telegram (conflicto de token), dos
#  relés, dos dashboards. mkdir es atómico: solo una instancia gana.
# ═══════════════════════════════════════════════════════════════════
OMNI_LOCK="${TMPDIR:-/tmp}/omni-singleton.lock"
CLEAN_LOCK() { rm -r "$OMNI_LOCK" 2>/dev/null; }
acquire_lock() {
  if mkdir "$OMNI_LOCK" 2>/dev/null; then
    echo "$$" > "$OMNI_LOCK/pid"
    trap 'CLEAN_LOCK' EXIT INT TERM
    return 0
  fi
  # ¿la instancia anterior sigue viva?
  OLD_PID="$(cat "$OMNI_LOCK/pid" 2>/dev/null)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo -e "${R}⛔ Otro omni.sh corre (PID $OLD_PID). Espera a que termine o mátalo con: kill $OLD_PID${N}" >&2
    exit 1
  fi
  # candado huérfano de una instancia muerta — limpiar y tomar
  rm -r "$OMNI_LOCK" 2>/dev/null
  mkdir "$OMNI_LOCK" 2>/dev/null || { echo -e "${R}⛔ No pude tomar el lock de omni.sh${N}" >&2; exit 1; }
  echo "$$" > "$OMNI_LOCK/pid"
  trap 'CLEAN_LOCK' EXIT INT TERM
}

# ── Paths absolutos ──
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOL_DIR="$HOME/.sol"
LOG_DIR="$SOL_DIR/logs"
ENV_FILE="$ROOT/.env"
# ☀️ Sol vive en SU PROPIO repo (sourceseal-star/sol) — NO en Red-team-tauri.
# omni.sh la levanta desde ahí: cerebro, daemon, Telegram y herramientas.
SOL_REPO="$HOME/sol"
mkdir -p "$SOL_DIR" "$LOG_DIR"

# ── Colores ──
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'
B='\033[0;34m'; W='\033[1;37m'; D='\033[0;90m'; N='\033[0m'
BOLD='\033[1m'

# ── Banner ──
banner() {
  echo -e "${C}╔═══════════════════════════════════════════════════════╗${N}"
  echo -e "${C}║  ${W}⚡ OMNI.SH${C} — SourceSeal Unified Command            ${C}║${N}"
  echo -e "${C}╚═══════════════════════════════════════════════════════╝${N}"
}

# ── Logging ──
log()  { echo -e "${D}[$(date '+%H:%M:%S')]${N} $*" | tee -a "$LOG_DIR/omni.log"; }
ok()   { echo -e "${G}  ✓${N} $*"; log "  ✓ $*"; }
fail() { echo -e "${R}  ✗${N} $*"; log "  ✗ $*"; }
warn() { echo -e "${Y}  ⚠${N} $*"; log "  ⚠ $*"; }
info() { echo -e "${C}  →${N} $*"; log "  → $*"; }

# ── ☀️ Asegurar repo de Sol (~/sol) ──
# Sol ya NO vive en Red-team-tauri (se eliminaron sus copias divergentes).
# Su única fuente de verdad es sourceseal-star/sol. Si ~/sol no existe,
# se clona; si existe, se actualiza con git pull (SIN tocar ~/sol/.env).
ensure_sol_repo() {
  if [ -d "$SOL_REPO/.git" ]; then
    if [ -f "$SOL_REPO/.env" ]; then
      local SOL_ENV_HASH_BEFORE="$(sha256sum "$SOL_REPO/.env" 2>/dev/null | cut -d' ' -f1)"
      (cd "$SOL_REPO" && git pull origin main >> "$LOG_DIR/sol_sync.log" 2>&1) || warn "git pull de ~/sol falló (continuando)"
      local SOL_ENV_HASH_AFTER="$(sha256sum "$SOL_REPO/.env" 2>/dev/null | cut -d' ' -f1)"
      if [ "$SOL_ENV_HASH_AFTER" != "$SOL_ENV_HASH_BEFORE" ]; then
        warn "¡~/sol/.env cambió tras el pull!"
      fi
    else
      (cd "$SOL_REPO" && git pull origin main >> "$LOG_DIR/sol_sync.log" 2>&1) || warn "git pull de ~/sol falló (continuando)"
    fi
    return 0
  fi
  info "☀️ ~/sol no existe — clonando sourceseal-star/sol..."
  # Repo PRIVADO: sin token el clone falla con "Repository not found".
  # Intentamos primero con GITHUB_ACCESS_TOKEN (si .env ya se cargó),
  # y solo si no hay token, probamos plano (por si algún día va público).
  local _SOL_CLONE_URL="https://github.com/sourceseal-star/sol.git"
  if [ -n "${GITHUB_ACCESS_TOKEN:-}" ]; then
    _SOL_CLONE_URL="https://x-access-token:${GITHUB_ACCESS_TOKEN}@github.com/sourceseal-star/sol.git"
  fi
  if git clone "$_SOL_CLONE_URL" "$SOL_REPO" >> "$LOG_DIR/sol_sync.log" 2>&1; then
    ok "☀️ Repo de Sol clonado en ~/sol"
    if [ -f "$SOL_REPO/.env.example" ] && [ ! -f "$SOL_REPO/.env" ]; then
      cp "$SOL_REPO/.env.example" "$SOL_REPO/.env"
      warn "☀️ Creado ~/sol/.env desde .env.example — revísalo (token de Telegram, keys)"
    fi
  else
    warn "☀️ No pude clonar ~/sol (¿sin acceso?) — Sol arrancará en modo limitado"
    warn "   Clona manualmente: git clone https://github.com/sourceseal-star/sol.git ~/sol"
    return 1
  fi
}

# ── Detectar entorno ──
detect_env() {
  if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
    echo "termux"
  elif [ -n "${REPL_ID:-}" ] || [ -n "${REPL_SLUG:-}" ]; then
    echo "replit"
  else
    echo "linux"
  fi
}

ENV_TYPE="$(detect_env)"

# ═══════════════════════════════════════════════════════════════════════
#  CARGAR .env — SEGURO (parse línea por línea, sin source)
# ═══════════════════════════════════════════════════════════════════════
load_env() {
  if [ ! -f "$ENV_FILE" ]; then
    fail ".env no existe en $ENV_FILE"
    echo "  Crea uno con: cp .env.example .env && edita los valores"
    exit 1
  fi
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*|[[:space:]]*) continue;; esac
    k="${k%%[[:space:]]*}"
    # Limpiar comillas y espacios
    v="${v#\"}"; v="${v%\"}"
    v="${v#\'}"; v="${v%\'}"
    v="${v%%[[:space:]]*}"
    [ -n "$k" ] && export "$k=$v" 2>/dev/null || true
  done < "$ENV_FILE" 2>/dev/null
  log ".env cargado (parse seguro, sin source)"
}

# ── ☀️ Cargar ~/sol/.env (parse seguro, SIN source, NUNCA lo modifica) ──
# Las llaves de Sol (GROQ_API_KEY/LLM_API_KEY, TELEGRAM_BOT_TOKEN, SOL_API_KEY,
# SOL_PUBLIC_URL...) viven en ~/sol/.env. Sin esto, omni.sh arrancaba su
# cerebro SIN llaves → sin LLM (pensamiento), sin relé Telegram. El archivo
# jamás se toca: solo se leen pares KEY=VALOR y se exportan.
load_sol_env() {
  local sol_env="$HOME/sol/.env"
  [ -f "$sol_env" ] || return 0
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*|[[:space:]]*) continue;; esac
    k="${k%%[[:space:]]*}"
    v="${v#\"}"; v="${v%\"}"; v="${v#\'}"; v="${v%\'}"
    v="${v%%[[:space:]]*}"
    [ -n "$k" ] && export "$k=$v" 2>/dev/null || true
  done < "$sol_env" 2>/dev/null
  log "☀️ ~/sol/.env cargado (Sol arranca con sus llaves: LLM, rele, etc.)"
}

# ── ☀️ Esperar a que el cerebro de Sol (:8006) despierte DE VERDAD ──
# Mata el falso "DETENIDA": uvicorn tarda unos segundos en levantar y el
# health-check de un solo intento la reportaba caida con ella viva.
wait_sol_api() {
  local tries="${1:-15}" i=1
  while [ "$i" -le "$tries" ]; do
    if curl -s -m 2 http://127.0.0.1:8006/api/sol/status >/dev/null 2>&1; then
      return 0
    fi
    sleep 1; i=$((i+1))
  done
  warn "☀️ Sol API (:8006) no respondio en ${tries}s — revisa ~/.sol/sol_api.log"
  return 1
}

# ═══════════════════════════════════════════════════════════════════════
#  VERIFY — Verificar que las credenciales críticas existen
#  Esto evita que nexus_credentials.py regenere credenciales sin permiso
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
#  SOL VARS — ¿están las llaves del relé y del LLM? (warn, no fatal)
# ═══════════════════════════════════════════════════════════════════
verify_sol_vars() {
  local sol_env="$HOME/sol/.env"
  [ -f "$sol_env" ] || { warn "~/sol/.env no existe — Sol correrá sin relé ni LLM (ver ~/sol/.env.example)"; return 0; }
  grep -q "^SOL_PUBLIC_URL=https" "$sol_env" 2>/dev/null \
    || warn "Falta SOL_PUBLIC_URL en ~/sol/.env — el relé Termux⇄Replit quedará apagado"
  grep -q "^SOL_API_KEY=" "$sol_env" 2>/dev/null \
    || warn "Falta SOL_API_KEY en ~/sol/.env — el relé no podrá autenticarse con Replit"
  grep -q "^LLM_API_KEY=" "$sol_env" 2>/dev/null \
    || warn "Falta LLM_API_KEY en ~/sol/.env — Sol caerá a plantillas locales (respuestas genéricas)"
  grep -q "^TELEGRAM_BOT_TOKEN=" "$sol_env" 2>/dev/null \
    || warn "Falta TELEGRAM_BOT_TOKEN en ~/sol/.env — Sol no hablará por Telegram"
  return 0
}

verify_credentials() {
  echo -e "${BOLD}── Verificación de credenciales ──${N}"
  echo ""

  if [ ! -f "$ENV_FILE" ]; then
    fail ".env no existe en $ENV_FILE"
    echo ""
    echo -e "  ${R}NO se puede arrancar sin .env${N}"
    echo -e "  Crea uno con: ${W}cp .env.example .env${N} y edita los valores"
    echo -e "  Si tienes un respaldo, restáuralo: ${W}bash scripts/restore_env.sh${N}"
    return 1
  fi

  # Hash del .env
  ENV_HASH="$(sha256sum "$ENV_FILE" 2>/dev/null | cut -d' ' -f1)"
  ok ".env presente — hash: ${ENV_HASH:0:16}..."

  # Permisos
  ENV_PERMS="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%A' "$ENV_FILE" 2>/dev/null || echo '?')"
  if [ "$ENV_PERMS" = "600" ]; then
    ok ".env permisos: 600 (correcto)"
  else
    warn ".env permisos: $ENV_PERMS (recomendado 600). Ejecuta: chmod 600 $ENV_FILE"
  fi

  echo ""

  # Variables CRÍTICAS — si faltan, el backend las REGENERARÍA sin permiso
  local critical_missing=""
  local critical_vars=""

  # NEXUS_PASS — si falta, nexus_credentials.py genera una nueva y la escribe
  _val="$(grep "^NEXUS_PASS=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
  if [ -z "$_val" ]; then
    critical_missing="${critical_missing}  NEXUS_PASS\n"
    critical_vars="${critical_vars}NEXUS_PASS "
  else
    ok "NEXUS_PASS presente (no se muestra por seguridad)"
  fi

  # ADMIN_PASSWORD — si falta, ensure_managed_secret la regenera
  _val="$(grep "^ADMIN_PASSWORD=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
  if [ -z "$_val" ]; then
    critical_missing="${critical_missing}  ADMIN_PASSWORD\n"
    critical_vars="${critical_vars}ADMIN_PASSWORD "
  else
    ok "ADMIN_PASSWORD presente (no se muestra por seguridad)"
  fi

  # REDTEAM_API_KEY — si falta, ensure_managed_secret la regenera
  _val="$(grep "^REDTEAM_API_KEY=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
  if [ -z "$_val" ]; then
    critical_missing="${critical_missing}  REDTEAM_API_KEY\n"
    critical_vars="${critical_vars}REDTEAM_API_KEY "
  else
    ok "REDTEAM_API_KEY presente (no se muestra por seguridad)"
  fi

  # Variables importantes (warn, no fatal)
  _val="$(grep "^NEXUS_USER=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
  if [ -z "$_val" ]; then
    warn "NEXUS_USER vacío — se usará default 'admin'"
  else
    ok "NEXUS_USER presente"
  fi

  _val="$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
  if [ -z "$_val" ]; then
    warn "TELEGRAM_BOT_TOKEN vacío — puente de Sol desactivado"
  else
    ok "TELEGRAM_BOT_TOKEN presente (Sol ☀️)"
  fi

  _val="$(grep "^TELEGRAM_CHAT_ID=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
  if [ -z "$_val" ]; then
    warn "TELEGRAM_CHAT_ID vacío — puente de Sol no sabrá a quién responder"
  else
    ok "TELEGRAM_CHAT_ID presente"
  fi

  # Si faltan credenciales críticas, DETENER
  if [ -n "$critical_missing" ]; then
    echo ""
    echo -e "${R}╔══════════════════════════════════════════════════════════════╗${N}"
    echo -e "${R}║  ⛔ CREDENCIALES CRÍTICAS FALTANTES                          ║${N}"
    echo -e "${R}╠══════════════════════════════════════════════════════════════╣${N}"
    echo -e "${R}║  Las siguientes variables NO existen en .env:               ║${N}"
    printf "${R}║${N}  ${critical_missing}${R}║${N}"
    echo -e "${R}║                                                             ║${N}"
    echo -e "${R}║  NO se arrancó ningún servicio.                            ║${N}"
    echo -e "${R}║  NO se regeneró ninguna credencial.                         ║${N}"
    echo -e "${R}║                                                             ║${N}"
    echo -e "${R}║  Si arrancas el backend ahora, nexus_credentials.py        ║${N}"
    echo -e "${R}║  generará credenciales NUEVAS y las escribirá en .env.      ║${N}"
    echo -e "${R}║  Perderás acceso a Nexus y al dashboard.                   ║${N}"
    echo -e "${R}║                                                             ║${N}"
    echo -e "${R}║  Para recuperar:                                            ║${N}"
    echo -e "${R}║    bash scripts/restore_env.sh                              ║${N}"
    echo -e "${R}║  o si tienes respaldo manual:                                ║${N}"
    echo -e "${R}║    bash control_claves.sh restore                            ║${N}"
    echo -e "${R}║  o restaurar desde snapshot cifrado:                         ║${N}"
    echo -e "${R}║    bash omni.sh snapshot                                     ║${N}"
    echo -e "${R}╚══════════════════════════════════════════════════════════════╝${N}"
    return 1
  fi

  echo ""
  ok "Todas las credenciales críticas presentes"
  return 0
}

# ═══════════════════════════════════════════════════════════════════════
#  HELP
# ═══════════════════════════════════════════════════════════════════════
help() {
  cat << 'HELP'
⚡ OMNI.SH — SourceSeal Unified Command

COMANDOS:
  start          Levanta TODO: Dashboard + GHOST + Nexus + Telegram + Watchdog + Seal
  stop           Detiene todo limpio
  restart        Stop + Start
  status         Estado de todos los servicios
  sync           git pull + deps + build frontend (SIN tocar .env)
  sync-deps      Solo instalar/actualizar dependencias Python + Node
  sync-frontend  Solo rebuild del frontend (npm run build)
  logs [serv]    Ver logs: dash | ghost | tg | nexus | seal | all
  snapshot       Crea snapshot cifrado del .env
  verify         Verifica que las credenciales críticas existan
  help           Esta ayuda

SERVICIOS:
  :8001  Dashboard FastAPI + Commander
  :8002  GHOST PHANTOM Master + Node
  :8004  Nexus Omni-Sentient
  :8005  C2 UNIFIED PRO
  ☀️     Puente Telegram
  🐕     Watchdog (auto-restart)

SEGURIDAD DE CREDENCIALES:
  .env NUNCA se modifica, regenera, ni borra durante sync.
  Antes de sync: snapshot cifrado automático del .env + checksum SHA-256.
  Después de sync: verificación de integridad (checksum).
  start verifica NEXUS_PASS, ADMIN_PASSWORD, REDTEAM_API_KEY antes
  de arrancar — si faltan, se DETIENE para evitar regeneración.

HELP
}

# ═══════════════════════════════════════════════════════════════════════
#  START — Levantar TODO
# ═══════════════════════════════════════════════════════════════════════
termux_guard() {
  # Guard del puente CLI ↔ app Termux:API. Solo aplica en Termux real.
  # Síntoma que previene: comandos termux-* colgados sin responder
  # (linterna/batería/GPS mudos) por desincronización de versiones.
  if [ -z "${TERMUX_VERSION:-}" ] || [ ! -d "/data/data/com.termux" ]; then
    return 0  # No es Termux (Replit/servidor) — nada que vigilar
  fi
  if ! command -v termux-battery-status >/dev/null 2>&1; then
    warn "☀️  Paquete termux-api FALTA — Sol no podrá usar el teléfono"
    echo "    Solución: pkg install termux-api (y app Termux:API de F-Droid)"
    return 1
  fi
  # Puente vivo: battery-status debe responder en ≤4s. Si se cuelga,
  # el CLI y la app están desincronizados (ver docs/TERMUX_API_SALUD.md)
  local probe
  probe="$(timeout 4 termux-battery-status 2>&1 </dev/null)"
  if [ $? -eq 124 ]; then
    fail "☀️  Puente Termux:API COLGADO — CLI y app desincronizados"
    echo "    Sol NO puede usar linterna/cámara/GPS/batería hasta curarlo."
    echo "    Cura (ver docs/TERMUX_API_SALUD.md):"
    echo "      1. pkg upgrade  (actualiza el CLI)"
    echo "      2. Actualizar app Termux:API desde F-Droid"
    echo "      3. Ajustes > Batería > Sin restricciones (Termux y Termux:API)"
    echo "      4. bash omni.sh restart  y  «diagnóstico» a Sol"
    return 1
  fi
  ok "☀️  Puente Termux:API sano — Sol tiene acceso al teléfono"
  return 0
}


# ═══════════════════════════════════════════════════════════════════════
#  _pids_on_port — encuentra PIDs escuchando en un puerto TCP sin depender
#  de fuser/lsof/ss (que Termux NO trae instalados por defecto). Lee
#  /proc/net/tcp[6] + /proc/*/fd directamente. Solo necesita python3,
#  que siempre esta disponible porque todo el stack corre sobre el.
# ═══════════════════════════════════════════════════════════════════════
_pids_on_port() {
  python3 -c "
import sys, os, glob, re
port = int(sys.argv[1])
port_hex = format(port, '04X')
inodes = set()
for tcp_file in ('/proc/net/tcp', '/proc/net/tcp6'):
    try:
        with open(tcp_file) as f:
            lines = f.readlines()[1:]
    except Exception:
        continue
    for line in lines:
        parts = line.split()
        if len(parts) < 10:
            continue
        local, state, inode = parts[1], parts[3], parts[9]
        _, hexport = local.split(':')
        if hexport.upper() == port_hex and state == '0A':
            inodes.add(inode)
if inodes:
    for fd_link in glob.glob('/proc/[0-9]*/fd/*'):
        try:
            target = os.readlink(fd_link)
        except Exception:
            continue
        m = re.match(r'socket:\[(\d+)\]', target)
        if m and m.group(1) in inodes:
            print(fd_link.split('/')[2])
" "$1" 2>/dev/null | sort -u
}

# ═══════════════════════════════════════════════════════════════════════
#  kill_by_pidfile_or_port — mata un servicio de forma GARANTIZADA:
#  1) por el PID exacto guardado cuando lo arrancamos (mas confiable)
#  2) por pkill -f al patron (red de seguridad, por si el pidfile falta)
#  3) por PUERTO via _pids_on_port (funciona SIN fuser/lsof/ss instalados)
#  Antes solo existia (2), y el patron de pkill nunca coincidia porque el
#  proceso se lanza con ruta RELATIVA (cd + python3 archivo.py) — nunca
#  se moria, y "restart" dejaba el proceso viejo y roto corriendo para
#  siempre mientras el nuevo fallaba en silencio al intentar bindear el
#  puerto ya ocupado. Asi Sol se quedaba "Offline" sin importar cuantas
#  veces se reiniciara.
# ═══════════════════════════════════════════════════════════════════════
kill_by_pidfile_or_port() {
  local label="$1" pidfile="$2" pkill_pattern="$3" port="$4"
  local killed=""
  if [ -n "$pidfile" ] && [ -f "$pidfile" ]; then
    local saved_pid="$(cat "$pidfile" 2>/dev/null)"
    if [ -n "$saved_pid" ] && kill -0 "$saved_pid" 2>/dev/null; then
      kill -9 "$saved_pid" 2>/dev/null && killed="pidfile($saved_pid)"
    fi
    rm -f "$pidfile" 2>/dev/null
  fi
  if [ -n "$pkill_pattern" ] && pkill -f "$pkill_pattern" 2>/dev/null; then
    killed="${killed:+$killed+}pkill"
  fi
  if [ -n "$port" ]; then
    local port_pids="$(_pids_on_port "$port")"
    if [ -n "$port_pids" ]; then
      kill -9 $port_pids 2>/dev/null && killed="${killed:+$killed+}port($port_pids)"
    fi
  fi
  if [ -n "$killed" ]; then
    ok "$label detenido [$killed]"
  else
    ok "$label ya estaba detenido"
  fi
}

start() {
  banner
  load_env
  echo ""
  log "⚡ OMNI START — $(date '+%Y-%m-%d %H:%M:%S') — entorno: $ENV_TYPE"
  echo ""

  # ── Preflight: credenciales ──
  # CRÍTICO: verificar ANTES de arrancar nada.
  # Si el backend arranca sin estas vars, nexus_credentials.py las REGENERARÁ.
  if ! verify_credentials; then
    echo ""
    fail "Abortando start — credenciales incompletas"
    log "⛔ Start abortado — credenciales críticas faltantes"
    exit 1
  fi

# ── Preflight: puente Termux:API (guard anti-desincronización) ──
  # Detecta si el CLI termux-api quedó desincronizado de la app
  # Termux:API (F-Droid) ANTES de arrancar. Ver docs/TERMUX_API_SALUD.md
  verify_sol_vars

    termux_guard

  # ── Preflight: auth_bootstrap (sincronizar password.json desde .env) ──
  if [ -f "$ROOT/auth_bootstrap.py" ]; then
    info "Sincronizando password.json desde .env..."
    (cd "$ROOT" && python3 auth_bootstrap.py 2>/dev/null) && ok "password.json sincronizado" || warn "auth_bootstrap falló (no crítico)"
  fi

  # ── Preflight: pycryptodome ──
  if ! python3 -c "from Crypto.Cipher import AES" >/dev/null 2>&1; then
    info "Instalando pycryptodome (requerido)..."
    # En Replit: usar pkg, NO pip (pip rompe pydantic-core nativo)
    if [ "$ENV_TYPE" = "replit" ]; then
      warn "Entorno Replit: no instalando pycryptodome por pip (rompe Nix)"
      warn "Agrega pycryptodome a replit.nix deps"
    else
      python3 -m pip install pycryptodome >/dev/null 2>&1 || pkg install -y python-pycryptodome >/dev/null 2>&1 || true
      python3 -c "from Crypto.Cipher import AES" >/dev/null 2>&1 && ok "pycryptodome instalado" || warn "pycryptodome no disponible — algunos módulos fallarán"
    fi
  else
    ok "pycryptodome disponible"
  fi

  # ── Preflight: edge-tts (voz neuronal de Sol — es-CO-SalomeNeural) ──
  # 2026-09-04: la voz de Sol ahora usa voces neuronales de Microsoft via
  # edge-tts. Sin esto el /api/sol/tts cae a gTTS (robótica, "se escucha mal").
  if python3 -c "import edge_tts" >/dev/null 2>&1; then
    ok "edge-tts disponible (voz neuronal de Sol)"
  else
    info "Instalando edge-tts (voz neuronal de Sol)..."
    python3 -m pip install edge-tts >/dev/null 2>&1 || true
    python3 -c "import edge_tts" >/dev/null 2>&1 && ok "edge-tts instalado" || warn "edge-tts no disponible — Sol usará gTTS (voz robótica)"
  fi

  # ── Preflight: liberar puertos ──
  echo ""
  echo -e "${BOLD}── Liberando puertos ──${N}"
  free_port() {
    local port="$1"
    local pids=""
    if command -v fuser >/dev/null 2>&1; then
      pids="$(fuser -n tcp "$port" 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
      pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    fi
    if [ -z "$pids" ] && command -v ss >/dev/null 2>&1; then
      pids="$(ss -H -ltnp "sport = :$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u || true)"
    fi
    # Fallback puro-python — Termux base no trae fuser/lsof/ss instalados,
    # asi que sin esto free_port no hacia NADA en la mayoria de los casos.
    if [ -z "$pids" ]; then
      pids="$(_pids_on_port "$port")"
    fi
    if [ -n "$pids" ]; then
      info "Liberando puerto $port (PIDs: $pids)"
      kill -9 $pids 2>/dev/null || true
      sleep 1
    fi
  }
  free_port 8001
  free_port 8002
  free_port 8004 2>/dev/null || true
  free_port 8005 2>/dev/null || true
  free_port 8006 2>/dev/null || true

  # ── Limpiar procesos previos ──
  pkill -f "$ROOT/redteam/scripts/dashboard_server.py" 2>/dev/null || true
  pkill -f "$ROOT/ghost_hunter_phantom/master.py" 2>/dev/null || true
  pkill -f "$ROOT/ghost_hunter_phantom/node.py" 2>/dev/null || true
  pkill -f "$ROOT/nexus_omni_v9.py" 2>/dev/null || true
  pkill -f "$ROOT/c2_unified_pro.py" 2>/dev/null || true
  pkill -f "$ROOT/sol_telegram_bridge.py" 2>/dev/null || true
  sleep 1

  echo ""
  echo -e "${BOLD}── Levantando servicios ──${N}"
  echo ""

  # ── 1. Dashboard FastAPI (:8001) ──
  if [ -f "$ROOT/redteam/scripts/dashboard_server.py" ]; then
    info "Dashboard :8001 — arrancando..."
    cd "$ROOT/redteam/scripts"
    PORT=8001 HOST="${HOST:-0.0.0.0}" \
      COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}" \
      PYTHONUNBUFFERED=1 nohup python3 dashboard_server.py \
      >> "$LOG_DIR/dash.log" 2>&1 &
    DASH_PID=$!
    echo "$DASH_PID" > "$SOL_DIR/dash.pid"
    # Esperar a que responda
    for i in $(seq 1 30); do
      curl -s -m 2 http://127.0.0.1:8001/api/health >/dev/null 2>&1 && break
      # Verificar que el proceso sigue vivo
      if ! kill -0 "$DASH_PID" 2>/dev/null; then
        fail "Dashboard murió antes de responder — ver logs:"
        tail -10 "$LOG_DIR/dash.log" 2>/dev/null
        break
      fi
      sleep 1
    done
    if curl -s -m 3 http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
      ok "Dashboard :8001 listo (PID $DASH_PID)"
    else
      fail "Dashboard :8001 no respondió en 30s"
      echo "  Últimas líneas del log:"
      tail -5 "$LOG_DIR/dash.log" 2>/dev/null
    fi
    cd "$ROOT"
  else
    fail "No existe redteam/scripts/dashboard_server.py"
  fi

  # ── 2. GHOST PHANTOM (:8002) ──
  if [ -f "$ROOT/ghost_hunter_phantom/master.py" ]; then
    info "GHOST PHANTOM :8002 — arrancando Master..."
    cd "$ROOT/ghost_hunter_phantom"
    BACKEND_API="http://127.0.0.1:8001" MASTER_PORT=8002 \
      nohup python3 master.py >> "$LOG_DIR/ghost.log" 2>&1 &
    GHOST_PID=$!
    echo "$GHOST_PID" > "$SOL_DIR/ghost.pid"
    for i in $(seq 1 20); do
      curl -s -m 2 http://127.0.0.1:8002/api/status >/dev/null 2>&1 && break
      sleep 1
    done
    if curl -s -m 3 http://127.0.0.1:8002/api/status >/dev/null 2>&1; then
      ok "GHOST Master :8002 listo (PID $GHOST_PID)"
      # Node worker
      info "GHOST Node worker — arrancando..."
      NODE_ID="phantom_node_1" MASTER_URL="http://127.0.0.1:8002" \
        BACKEND_API="http://127.0.0.1:8001" \
        nohup python3 node.py >> "$LOG_DIR/ghost.log" 2>&1 &
      ok "GHOST Node worker activo"
    else
      fail "GHOST Master :8002 no respondió en 20s"
    fi
    cd "$ROOT"
  else
    warn "GHOST PHANTOM no encontrado — saltando"
  fi

  # ── 3. Nexus Omni-Sentient (:8004) ──
  if [ -f "$ROOT/nexus_omni_v9.py" ]; then
    info "Nexus :8004 — arrancando..."
    cd "$ROOT"
    nohup python3 nexus_omni_v9.py >> "$LOG_DIR/nexus.log" 2>&1 &
    NEXUS_PID=$!
    echo "$NEXUS_PID" > "$SOL_DIR/nexus.pid"
    for i in $(seq 1 15); do
      curl -s -m 2 http://127.0.0.1:8004/ >/dev/null 2>&1 && break
      sleep 1
    done
    if curl -s -m 2 http://127.0.0.1:8004/ >/dev/null 2>&1; then
      ok "Nexus :8004 listo (PID $NEXUS_PID)"
    else
      warn "Nexus :8004 no respondió en 15s — continua el resto"
    fi
  else
    info "Nexus no encontrado — saltando"
  fi

  # ── 4. C2 UNIFIED PRO (:8005) ──
  if [ -f "$ROOT/c2_unified_pro.py" ]; then
    info "C2 :8005 — arrancando..."
    cd "$ROOT"
    C2_PORT="${C2_PORT:-8005}" nohup python3 c2_unified_pro.py >> "$LOG_DIR/c2.log" 2>&1 &
    C2_PID=$!
    echo "$C2_PID" > "$SOL_DIR/c2.pid"
    for i in $(seq 1 15); do
      curl -s -m 2 http://127.0.0.1:8005/api/health >/dev/null 2>&1 && break
      sleep 1
    done
    if curl -s -m 3 http://127.0.0.1:8005/api/health >/dev/null 2>&1; then
      ok "C2 :8005 listo (PID $C2_PID)"
    else
      warn "C2 :8005 no respondió en 15s — continúa el resto"
    fi
  else
    info "C2 UNIFIED PRO no encontrado — saltando"
  fi

  # ── 5. Telegram (Sol) — SOLO UNO puede hacer polling del mismo token a la vez ──
  #    Telegram API rechaza (409 Conflict) una segunda conexión getUpdates simultánea.
  #    Preferimos la Miniapp (botones, recordatorios, voz, avatar); el Puente legacy
  #    queda como fallback automático si python-telegram-bot no está disponible.
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    # Limpiar procesos zombie/huérfanos antes de intentar arrancar
    pkill -9 -f "sol_telegram_bridge" >/dev/null 2>&1 || true
    pkill -9 -f "sol_telegram_bot.py" >/dev/null 2>&1 || true
    if pgrep -f "sol_telegram_bridge" >/dev/null 2>&1; then
      ok "Puente Telegram ya corriendo (legacy)"
    elif pgrep -f "sol_telegram_bot.py" >/dev/null 2>&1; then
      ok "Miniapp Telegram ya corriendo"
    elif [ -f "$SOL_REPO/sol_telegram_bot.py" ] && { python3 -c "import telegram" 2>/dev/null || pip install python-telegram-bot >> "$LOG_DIR/tg_bot.log" 2>&1 && python3 -c "import telegram" 2>/dev/null; }; then
      info "Miniapp Telegram — arrancando (desde ~/sol)..."
      cd "$SOL_REPO"
      : > "$LOG_DIR/tg_bot.log"
      nohup python3 sol_telegram_bot.py >> "$LOG_DIR/tg_bot.log" 2>&1 &
      echo $! > "$SOL_DIR/tg_bot.pid"
      sleep 4
      if kill -0 "$(cat "$SOL_DIR/tg_bot.pid" 2>/dev/null)" 2>/dev/null; then
        ok "Miniapp Telegram activa ☀️ (PID $(cat "$SOL_DIR/tg_bot.pid"))"
      else
        warn "Miniapp Telegram no arrancó — probando puente legacy..."
        echo -e "${R}  ── Error real (tg_bot.log) ──${N}"
        tail -n 15 "$LOG_DIR/tg_bot.log" 2>/dev/null | sed 's/^/    /'
        echo -e "${R}  ───────────────────────────${N}"
        : > "$LOG_DIR/tg.log"
        nohup python3 sol_telegram_bridge.py >> "$LOG_DIR/tg.log" 2>&1 &
        sleep 4
        if pgrep -f "sol_telegram_bridge" >/dev/null 2>&1; then
          ok "Puente Telegram activo ☀️ (fallback)"
        else
          fail "Ningún bot de Telegram arrancó"
          echo -e "${R}  ── Error real (tg.log) ──${N}"
          tail -n 15 "$LOG_DIR/tg.log" 2>/dev/null | sed 's/^/    /'
          echo -e "${R}  ─────────────────────────${N}"
        fi
      fi
    else
      info "python-telegram-bot no disponible — usando puente legacy (~/sol)"
      cd "$SOL_REPO"
      : > "$LOG_DIR/tg.log"
      nohup python3 sol_telegram_bridge.py >> "$LOG_DIR/tg.log" 2>&1 &
      sleep 4
      if pgrep -f "sol_telegram_bridge" >/dev/null 2>&1; then
        ok "Puente Telegram activo ☀️"
      else
        fail "Puente Telegram no arrancó"
        echo -e "${R}  ── Error real (tg.log) ──${N}"
        tail -n 15 "$LOG_DIR/tg.log" 2>/dev/null | sed 's/^/    /'
        echo -e "${R}  ─────────────────────────${N}"
      fi
    fi
  else
    warn "TELEGRAM_BOT_TOKEN no configurado — Telegram desactivado"
  fi

  # ── 6. Seal IA Orquestador ──
  if [ -f "$ROOT/seal/orchestrator/seal_orchestrator.py" ]; then
    SEAL_CHECK="$(grep -q '^SEAL_ENABLED=1' "$ENV_FILE" 2>/dev/null && echo 1 || echo 0)"
    if [ "$SEAL_CHECK" = "1" ]; then
      info "Seal IA — arrancando..."
      cd "$ROOT"
      nohup python3 seal/orchestrator/seal_orchestrator.py --start \
        >> "$LOG_DIR/seal.log" 2>&1 &
      sleep 2
      if pgrep -f "seal_orchestrator" >/dev/null 2>&1; then
        ok "Seal IA activo 🦭"
      else
        warn "Seal IA no arrancó — ver $LOG_DIR/seal.log"
      fi
    else
      info "Seal IA desactivado (SEAL_ENABLED≠1)"
    fi
  else
    info "Seal IA no encontrado — saltando"
  fi

  # ── 7. Watchdog ──
  if ! pgrep -f "omni.sh watchdog" >/dev/null 2>&1; then
    info "Watchdog — activando vigilancia..."
    nohup bash "$0" watchdog >> "$LOG_DIR/watchdog.log" 2>&1 &
    ok "Watchdog activo 🐕 (chequeo cada 60s)"
  else
    ok "Watchdog ya corriendo"
  fi

  # ── 8. Sol Autónoma (daemon) — vive en ~/sol, NO en Red-team-tauri ──
  ensure_sol_repo
  if [ -f "$SOL_REPO/sol_daemon.py" ] && [ -f "$SOL_REPO/sol_core.py" ]; then
    if [ -f "$SOL_DIR/sol.pid" ]; then
      SOL_DAEMON_PID=$(cat "$SOL_DIR/sol.pid" 2>/dev/null)
      if [ -n "$SOL_DAEMON_PID" ] && kill -0 "$SOL_DAEMON_PID" 2>/dev/null; then
        ok "Sol autónoma ☀️ ya corriendo (PID $SOL_DAEMON_PID)"
      else
        rm -f "$SOL_DIR/sol.pid"
        info "Sol autónoma ☀️ — arrancando daemon (desde ~/sol)..."
        cd "$SOL_REPO"
        nohup python3 sol_daemon.py >> "$LOG_DIR/sol_daemon.log" 2>&1 &
        echo $! > "$SOL_DIR/sol.pid"
        sleep 2
        if kill -0 "$(cat "$SOL_DIR/sol.pid" 2>/dev/null)" 2>/dev/null; then
          ok "Sol autónoma ☀️ activa (PID $(cat "$SOL_DIR/sol.pid"))"
        else
          warn "Sol autónoma ☀️ no arrancó — ver $LOG_DIR/sol_daemon.log"
        fi
      fi
    else
      info "Sol autónoma ☀️ — arrancando daemon (desde ~/sol)..."
      cd "$SOL_REPO"
      nohup python3 sol_daemon.py >> "$LOG_DIR/sol_daemon.log" 2>&1 &
      echo $! > "$SOL_DIR/sol.pid"
      sleep 2
      if kill -0 "$(cat "$SOL_DIR/sol.pid" 2>/dev/null)" 2>/dev/null; then
        ok "Sol autónoma ☀️ activa (PID $(cat "$SOL_DIR/sol.pid"))"
      else
        warn "Sol autónoma ☀️ no arrancó — ver $LOG_DIR/sol_daemon.log"
      fi
    fi
  else
    info "Sol daemon no encontrado — saltando (usa 'bash ~/sol.sh start' manualmente)"
  fi

  # ── 9. Sol integrado en :8001 (sol_api.py deprecado, todo en el dashboard) ──
  # Sol ya no necesita puerto separado — endpoints, herramientas y SIL
  # están montados en dashboard_server (:8001) via sol_router.py
  if [ -f "$SOL_REPO/sol_core.py" ]; then
    if curl -s -m 2 http://127.0.0.1:8001/api/sol/status >/dev/null 2>&1; then
      ok "Sol ☀️ activo en :8001 (integrado en dashboard)"
    else
      info "Sol ☀️ esperando dashboard :8001..."
    fi
    # sol_api.py como fallback legacy (puerto 8006, desde ~/sol)
    if [ -f "$SOL_REPO/sol_api.py" ] && ! pgrep -f "sol_api.py" >/dev/null 2>&1; then
      load_sol_env   # ☀️ llaves de ~/sol/.env para su cerebro (LLM, rele)
      cd "$SOL_REPO"
      nohup python3 sol_api.py >> "$LOG_DIR/sol_api.log" 2>&1 &
      echo "$!" > "$SOL_DIR/sol_api.pid"
      cd "$ROOT"
      wait_sol_api 15   # en vez de sleep 1: esperar a que despierte de verdad
    fi
  else
    warn "sol_core.py no encontrado — Sol sin cerebro"
  fi

  # ── 10. Sol Relay (Replit ⇄ Termux) — Sol en Replit ordena, el Edge ejecuta ──
  # El teléfono no tiene IP pública: el agente SONDEA la cola de Replit cada
  # 15s (patrón PULL). Requisitos: SOL_PUBLIC_URL + SOL_API_KEY en ~/sol/.env
  if [ -f "$SOL_REPO/sol_relay.py" ]; then
    if pgrep -f "sol_relay.py" >/dev/null 2>&1; then
      ok "Relé Termux ☀️     ya corriendo (PID $(pgrep -f sol_relay.py | head -1))"
    elif grep -q "^SOL_PUBLIC_URL=..*" "$SOL_REPO/.env" 2>/dev/null; then
      info "Relé Termux ☀️ — arrancando agente (desde ~/sol)..."
      cd "$SOL_REPO"
      nohup python3 sol_relay.py >> "$LOG_DIR/relay.log" 2>&1 &
      echo $! > "$SOL_DIR/relay.pid"
      sleep 2
      if kill -0 "$(cat "$SOL_DIR/relay.pid" 2>/dev/null)" 2>/dev/null; then
        ok "Relé Termux ☀️     activo (PID $(cat "$SOL_DIR/relay.pid")) — el Edge responde por Sol"
      else
        warn "Relé Termux ☀️ no arrancó — ver $LOG_DIR/relay.log (¿SOL_PUBLIC_URL/SOL_API_KEY en ~/sol/.env?)"
      fi
    else
      info "Relé Termux ☀️     desactivado (falta SOL_PUBLIC_URL en ~/sol/.env)"
    fi
  fi


  cd "$ROOT"
  echo ""
  echo -e "${G}╔═══════════════════════════════════════════════════════╗${N}"
  echo -e "${G}║  ${W}⚡ SISTEMA ARRANCADO${G}                              ║${N}"
  echo -e "${G}║  ${W}Sol ☀️ autónoma vigilando${G}                       ║${N}"
  echo -e "${G}╚═══════════════════════════════════════════════════════╝${N}"
  echo ""
  start_sol_stack
    status_short
  echo ""
  log "⚡ Sistema arrancado completamente — entorno: $ENV_TYPE"
}

# ═══════════════════════════════════════════════════════════════════════
#  STOP
# ═══════════════════════════════════════════════════════════════════════
stop() {
  banner
  echo ""
  log "🛑 Deteniendo sistema..."
  echo -e "${BOLD}── Deteniendo servicios ──${N}"

  pkill -f "omni.sh watchdog" 2>/dev/null && ok "Watchdog detenido" || true
  pkill -f "sol_telegram_bridge" 2>/dev/null && ok "Puente Telegram detenido" || true
  pkill -f "sol_telegram_bot.py" 2>/dev/null && ok "Miniapp Telegram detenida" || true
  rm -f "$SOL_DIR/tg_bot.pid" 2>/dev/null || true
  kill_by_pidfile_or_port "Nexus"          "$SOL_DIR/nexus.pid"   "nexus_omni_v9"                8004
  kill_by_pidfile_or_port "C2"             "$SOL_DIR/c2.pid"      "c2_unified_pro"               8005
  pkill -f "seal_orchestrator" 2>/dev/null && ok "Seal IA detenido" || true
  pkill -f "ghost_hunter_phantom/node" 2>/dev/null && ok "GHOST Node detenido" || true
  kill_by_pidfile_or_port "GHOST Master"   "$SOL_DIR/ghost.pid"   "ghost_hunter_phantom/master"  8002
  # ── Dashboard (:8001) — EL CRITICO. Antes solo tenia el pkill de abajo,
  # que NUNCA coincidia (el proceso corre como "python3 dashboard_server.py"
  # con ruta relativa, no "redteam/scripts/dashboard_server.py"). Por eso
  # "restart" jamas mataba el proceso viejo y Sol se quedaba Offline para
  # siempre sin importar cuantas veces se reiniciara.
  kill_by_pidfile_or_port "Dashboard"      "$SOL_DIR/dash.pid"    "redteam/scripts/dashboard_server" 8001
  pkill -f "sol_daemon.py" 2>/dev/null && ok "Sol autónoma detenida" || true
  rm -f "$SOL_DIR/sol.pid" 2>/dev/null || true
  kill_by_pidfile_or_port "Sol API (8006)" "$SOL_DIR/sol_api.pid" "sol_api.py"                   8006
  pkill -f "sol_relay.py" 2>/dev/null && ok "Relé Termux detenido" || true
  pkill -f "sol_body.sh" 2>/dev/null && ok "Sol cuerpo detenido" || true
  pkill -f "sol_watchdog.sh" 2>/dev/null && ok "Sol watchdog detenido" || true
  rm -f "$SOL_DIR/body.pid" 2>/dev/null || true

  sleep 1
  echo ""
  ok "Todo detenido"
  log "🛑 Sistema detenido"
}

# ═══════════════════════════════════════════════════════════════════════
#  RESTART
# ═══════════════════════════════════════════════════════════════════════
restart() {
  stop
  sleep 2
  start
}

# ═══════════════════════════════════════════════════════════════════════
#  STATUS
# ═══════════════════════════════════════════════════════════════════════
status() {
  banner
  echo ""
  status_short
}

status_short() {
  echo -e "${BOLD}── Estado del sistema ──${N}"
  echo ""

  # Puente Termux:API (solo en Termux)
  termux_guard

  # Dashboard :8001
  if curl -s -m 3 http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
    ok "Dashboard :8001   🟢 ACTIVO"
  else
    fail "Dashboard :8001   🔴 CAÍDO"
  fi

  # Commander (integrado en :8001)
  if curl -s -m 3 -H "Authorization: Bearer ${REDTEAM_API_KEY:-}" \
    http://127.0.0.1:8001/api/commander/health >/dev/null 2>&1; then
    ok "Commander         🟢 INTEGRADO"
  else
    warn "Commander         🟡 NO RESPONDE"
  fi

  # GHOST :8002
  if curl -s -m 3 http://127.0.0.1:8002/api/status >/dev/null 2>&1; then
    ok "GHOST :8002        🟢 ACTIVO"
  else
    fail "GHOST :8002        🔴 CAÍDO"
  fi

  # GHOST Node
  if pgrep -f "ghost_hunter_phantom/node" >/dev/null 2>&1; then
    ok "GHOST Node         🟢 ACTIVO"
  else
    warn "GHOST Node         🟡 INACTIVO"
  fi

  # Nexus :8004
  if [ -f "$ROOT/nexus_omni_v9.py" ]; then
    if curl -s -m 2 http://127.0.0.1:8004/ >/dev/null 2>&1; then
      ok "Nexus :8004        🟢 ACTIVO"
    else
      fail "Nexus :8004        🔴 CAÍDO"
    fi

  # C2 :8005
  if [ -f "$ROOT/c2_unified_pro.py" ]; then
    if curl -s -m 2 http://127.0.0.1:8005/api/health >/dev/null 2>&1; then
      ok "C2 :8005           🟢 ACTIVO"
    else
      fail "C2 :8005           🔴 CAÍDO"
    fi
  fi
  fi

  # Telegram (puente legacy)
  if pgrep -f "sol_telegram_bridge" >/dev/null 2>&1; then
    ok "TG Puente ☀️       🟢 ACTIVO"
  else
    warn "TG Puente ☀️       🟡 INACTIVO"
  fi

  # Telegram (miniapp con botones)
  if [ -f "$SOL_DIR/tg_bot.pid" ]; then
    TG_BOT_PID=$(cat "$SOL_DIR/tg_bot.pid" 2>/dev/null)
    if [ -n "$TG_BOT_PID" ] && kill -0 "$TG_BOT_PID" 2>/dev/null; then
      ok "TG Miniapp ☀️      🟢 ACTIVA (PID $TG_BOT_PID)"
    else
      warn "TG Miniapp ☀️      🟡 INACTIVA"
    fi
  else
    warn "TG Miniapp ☀️      🟡 DETENIDA"
  fi

  # Relé Termux (agente PULL hacia Replit)
  if pgrep -f "sol_relay.py" >/dev/null 2>&1; then
    ok "Relé Termux ☀️     🟢 ACTIVO (el Edge ejecuta por Sol)"
  else
    warn "Relé Termux ☀️     🟡 INACTIVO (Sol en Replit no puede usar el teléfono)"
  fi

  # Seal IA
  if [ -f "$ROOT/seal/orchestrator/seal_orchestrator.py" ]; then
    if pgrep -f "seal_orchestrator" >/dev/null 2>&1; then
      ok "Seal IA 🦭         🟢 ACTIVO"
    else
      info "Seal IA 🦭         ⚪ DESACTIVADO"
    fi
  fi

  # Sol ☀️ — cerebro + herramientas + SIL (via dashboard, o directo a su cerebro)
  SOL_STATE=""
  if curl -s -m 2 http://127.0.0.1:8001/api/sol/status >/dev/null 2>&1; then
    SOL_STATE=$(curl -s -m 2 http://127.0.0.1:8001/api/sol/status 2>/dev/null)
  elif curl -s -m 2 http://127.0.0.1:8006/api/sol/status >/dev/null 2>&1; then
    SOL_STATE=$(curl -s -m 2 http://127.0.0.1:8006/api/sol/status 2>/dev/null)  # directo: ella viva aunque el dashboard tarde
  fi
  if [ -n "$SOL_STATE" ]; then
    SOL_MEM=$(echo "$SOL_STATE" | grep -o '"memories":[0-9]*' | grep -o '[0-9]*' || echo "?")
    ok "Sol ☀️         🟢 ACTIVO ($SOL_MEM recuerdos)"
  else
    warn "Sol ☀️         🟡 DETENIDA"
  fi

  # Sol Autónoma (daemon)
  if [ -f "$SOL_DIR/sol.pid" ]; then
    SOL_DAEMON_PID=$(cat "$SOL_DIR/sol.pid" 2>/dev/null)
    if [ -n "$SOL_DAEMON_PID" ] && kill -0 "$SOL_DAEMON_PID" 2>/dev/null; then
      ok "Sol Daemon ☀️     🟢 ACTIVA (PID $SOL_DAEMON_PID)"
    else
      warn "Sol Daemon ☀️     🟡 INACTIVA (PID stale)"
    fi
  else
    warn "Sol Daemon ☀️     🟡 DETENIDA"
  fi

  # Sol Watchdog
  if pgrep -f "sol_watchdog.sh" >/dev/null 2>&1; then
    ok "Sol Watchdog 🐕    🟢 VIGILANDO"
  else
    warn "Sol Watchdog 🐕    🟡 DETENIDO"
  fi

  # Sol Body (cuerpo persistente)
  if [ -f "$SOL_DIR/body.pid" ]; then
    BODY_PID=$(cat "$SOL_DIR/body.pid" 2>/dev/null)
    if [ -n "$BODY_PID" ] && kill -0 "$BODY_PID" 2>/dev/null; then
      ok "Sol Cuerpo ☀️     🟢 ACTIVO (PID $BODY_PID)"
    else
      warn "Sol Cuerpo ☀️     🟡 INACTIVO"
    fi
  else
    info "Sol Cuerpo ☀️     ⚪ DESACTIVADO"
  fi

  # SIL (Inmersión Lingüística)
  if [ -f "$ROOT/sol_learning_advanced.py" ]; then
    if curl -s -m 2 http://127.0.0.1:8001/api/sol/sil/stats >/dev/null 2>&1; then
      SIL_STATS=$(curl -s -m 2 http://127.0.0.1:8001/api/sol/sil/stats 2>/dev/null)
      SIL_LEARNED=$(echo "$SIL_STATS" | grep -o '"learned_items":[0-9]*' | grep -o '[0-9]*' || echo "0")
      SIL_DUE=$(echo "$SIL_STATS" | grep -o '"due_today":[0-9]*' | grep -o '[0-9]*' || echo "0")
      ok "SIL 📚            🟢 ACTIVO ($SIL_LEARNED aprendidas, $SIL_DUE pendientes)"
    else
      info "SIL 📚            ⚪ API DETENIDA"
    fi
  else
    warn "SIL 📚            🟡 NO INSTALADO"
  fi

  # Sol Tools (herramientas)
  if [ -f "$ROOT/sol_tools.py" ]; then
    if curl -s -m 2 http://127.0.0.1:8001/api/sol/tools >/dev/null 2>&1; then
      TOOLS_COUNT=$(curl -s -m 2 http://127.0.0.1:8001/api/sol/tools 2>/dev/null | grep -o '"tools"' | head -1)
      ok "Sol Tools 🔧      🟢 20 herramientas disponibles"
    else
      info "Sol Tools 🔧      ⚪ API DETENIDA"
    fi
  else
    warn "Sol Tools 🔧      🟡 NO INSTALADO"
  fi

  # Watchdog
  if pgrep -f "omni.sh watchdog" >/dev/null 2>&1; then
    ok "Watchdog 🐕        🟢 VIGILANDO"
  else
    warn "Watchdog 🐕        🟡 DETENIDO"
  fi

  echo ""
  # .env integrity
  if [ -f "$ENV_FILE" ]; then
    ENV_HASH="$(sha256sum "$ENV_FILE" 2>/dev/null | cut -d' ' -f1)"
    echo -e "${D}.env: ${ENV_HASH:0:16}... | permisos: $(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%A' "$ENV_FILE" 2>/dev/null || echo '?')${N}"
  fi
}

# ═══════════════════════════════════════════════════════════════════════
#  SYNC — git pull + deps + build (SIN tocar .env)
#  REGLA DE ORO: .env es intocable. Triple protección.
# ═══════════════════════════════════════════════════════════════════════
sync() {
  banner
  echo ""
  log "🔄 SYNC — $(date '+%Y-%m-%d %H:%M:%S') — entorno: $ENV_TYPE"
  echo -e "${BOLD}── Sincronización segura ──${N}"
  echo ""
  # Cargar .env ANTES de protegerlo/clonar (solo export de variables,
  # nunca modifica el archivo) — así GITHUB_ACCESS_TOKEN está disponible
  # para clonar ~/sol si hace falta.
  load_env 2>/dev/null || true

  # ── 0. PROTEGER .env — TRIPLE PROTECCIÓN ──
  echo -e "${BOLD} Paso 0: Proteger .env (triple protección)${N}"
  echo ""

  if [ ! -f "$ENV_FILE" ]; then
    fail ".env no existe — no se puede sincronizar sin él"
    fail "NO se puede continuar. Crea un .env primero:"
    echo "  cp .env.example .env && edita los valores"
    exit 1
  fi

  # 0a. SHA-256 antes de todo
  ENV_HASH_BEFORE="$(sha256sum "$ENV_FILE" | cut -d' ' -f1)"
  ok ".env hash ANTES: ${ENV_HASH_BEFORE:0:16}..."

  # 0b. Snapshot cifrado automático
  if [ -f "$ROOT/scripts/snapshot_env.sh" ]; then
    info "Creando snapshot cifrado del .env..."
    if SNAPSHOT_PASS="omni-auto-$(date +%s)" bash "$ROOT/scripts/snapshot_env.sh" >/dev/null 2>&1; then
      ok "Snapshot cifrado creado en ~/.c2/snapshots/"
    else
      warn "Snapshot falló — respaldo plano"
      cp "$ENV_FILE" "$ENV_FILE.omni-backup-$(date +%s)"
      ok "Respaldo plano: $ENV_FILE.omni-backup-*"
    fi
  else
    cp "$ENV_FILE" "$ENV_FILE.omni-backup-$(date +%s)"
    ok "Respaldo plano creado"
  fi

  # 0c. Copia a tmp para restauración emergencia
  ENV_RESTORE="/tmp/omni-env-restore-$$"
  cp "$ENV_FILE" "$ENV_RESTORE"
  ok "Copia de emergencia en /tmp/"

  echo ""

  # ── 1. GIT PULL ──
  echo -e "${BOLD} Paso 1: git pull${N}"
  cd "$ROOT"

  # Si hay cambios locales sin commitear, stash (NUNCA stashear .env — está en .gitignore)
  LOCAL_CHANGES="$(git status --porcelain 2>/dev/null | grep -v '^\?\?' | head -5)"
  if [ -n "$LOCAL_CHANGES" ]; then
    info "Cambios locales detectados — guardando en stash..."
    git stash push -m "omni-sync-$(date +%s)" 2>/dev/null && ok "Stash creado" || warn "No se pudo stash"
  fi

  info "git pull origin main..."
  if git pull origin main 2>&1 | tee -a "$LOG_DIR/sync.log"; then
    ok "git pull completado"
  else
    fail "git pull falló"
    warn "Restaurando stash si existe..."
    git stash pop 2>/dev/null || true
    # Restaurar .env por si acaso
    if [ ! -f "$ENV_FILE" ] || [ "$(sha256sum "$ENV_FILE" | cut -d' ' -f1)" != "$ENV_HASH_BEFORE" ]; then
      warn "Restaurando .env desde respaldo..."
      cp "$ENV_RESTORE" "$ENV_FILE"
      ok ".env restaurado"
    fi
    rm -f "$ENV_RESTORE"
    exit 1
  fi

  # Restaurar stash si existe
  if git stash list 2>/dev/null | head -1 | grep -q "omni-sync"; then
    info "Restaurando cambios locales..."
    git stash pop 2>/dev/null && ok "Cambios locales restaurados" || warn "Conflicto en stash pop — resuelve manualmente"
  fi

  # ── Paso 1b: repo de Sol (~/sol) — clona si falta, actualiza si existe ──
  # SIN tocar ~/sol/.env: hash antes y después, como con el .env principal.
  echo -e "${BOLD} Paso 1b: repo de Sol (~/sol)${N}"
  ensure_sol_repo
  if [ -d "$SOL_REPO/.git" ] && [ -f "$SOL_REPO/sol_core.py" ]; then
    ok "☀️ ~/sol listo — cerebro de Sol actualizado"
  elif [ -d "$SOL_REPO/.git" ]; then
    warn "☀️ ~/sol existe pero sin sol_core.py — revisa $LOG_DIR/sol_sync.log"
  fi
  cd "$ROOT"

  echo ""

  # ── 2. VERIFICAR .env INTEGRIDAD ──
  echo -e "${BOLD} Paso 2: Verificar .env (no se tocó)${N}"
  if [ ! -f "$ENV_FILE" ]; then
    fail "⚠️ .env DESAPARECIÓ después de git pull!"
    info "Restaurando desde respaldo de emergencia..."
    cp "$ENV_RESTORE" "$ENV_FILE"
    ok ".env restaurado"
  else
    ENV_HASH_AFTER="$(sha256sum "$ENV_FILE" | cut -d' ' -f1)"
    if [ "$ENV_HASH_BEFORE" = "$ENV_HASH_AFTER" ]; then
      ok ".env INTACTO — hash coincide: ${ENV_HASH_AFTER:0:16}..."
    else
      fail "⚠️ .env FUE MODIFICADO — hash cambió!"
      warn "ANTES: ${ENV_HASH_BEFORE:0:16}..."
      warn "DESPUÉS: ${ENV_HASH_AFTER:0:16}..."
      warn "Restaurando .env original..."
      cp "$ENV_RESTORE" "$ENV_FILE"
      ENV_HASH_RESTORED="$(sha256sum "$ENV_FILE" | cut -d' ' -f1)"
      if [ "$ENV_HASH_BEFORE" = "$ENV_HASH_RESTORED" ]; then
        ok ".env restaurado correctamente — credenciales a salvo"
      else
        fail "No se pudo restaurar .env — usa tu respaldo manual"
        fail "Respaldo en: $ENV_RESTORE"
        exit 1
      fi
    fi
  fi
  rm -f "$ENV_RESTORE"

  echo ""

  # ── 3. DEPENDENCIAS PYTHON ──
  echo -e "${BOLD} Paso 3: Dependencias Python${N}"
  install_python_deps

  echo ""

  # ── 4. FRONTEND BUILD ──
  echo -e "${BOLD} Paso 4: Frontend build${N}"
  build_frontend

  echo ""

  # ── 5. Verificación final de .env ──
  echo -e "${BOLD} Paso 5: Verificación final de credenciales${N}"
  ENV_HASH_FINAL="$(sha256sum "$ENV_FILE" | cut -d' ' -f1)"
  if [ "$ENV_HASH_BEFORE" = "$ENV_HASH_FINAL" ]; then
    ok ".env VERIFICADO — intacto durante todo el sync ✅"
  else
    fail "⚠️ .env cambió durante sync — REVISAR"
    warn "Restaurando desde respaldo..."
    cp "$ENV_RESTORE" "$ENV_FILE" 2>/dev/null || true
  fi

  # Verificar que las credenciales críticas siguen presentes
  _missing=""
  for v in NEXUS_PASS ADMIN_PASSWORD REDTEAM_API_KEY; do
    _val="$(grep "^${v}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
    [ -z "$_val" ] && _missing="$_missing $v"
  done
  if [ -n "$_missing" ]; then
    fail "Credenciales faltantes después de sync:$_missing"
    fail "NO ARRANQUES el backend — restaurar .env manualmente"
  else
    ok "Credenciales críticas verificadas: NEXUS_PASS, ADMIN_PASSWORD, REDTEAM_API_KEY"
  fi

  # Limpiar respaldos viejos (>7 días)
  find "$ROOT" -name ".env.omni-backup-*" -mtime +7 -delete 2>/dev/null || true

  echo ""
  echo -e "${G}╔═══════════════════════════════════════════════════════╗${N}"
  echo -e "${G}║  ${W}✅ SYNC COMPLETADO${G} — .env intacto               ║${N}"
  echo -e "${G}╚═══════════════════════════════════════════════════════╝${N}"
  echo ""
  echo -e "  Próximo paso: ${W}bash omni.sh start${N}"
  log "✅ Sync completado — .env intacto, credenciales verificadas"
}

# ═══════════════════════════════════════════════════════════════════════
#  SYNC-DEPS — Solo dependencias
# ═══════════════════════════════════════════════════════════════════════
install_python_deps() {
  local PIP="python3 -m pip"
  local installed=0

  # En Replit: NO instalar fastapi/pydantic por pip (rompe Nix)
  if [ "$ENV_TYPE" = "replit" ]; then
    warn "Entorno Replit: saltando pip install de fastapi/pydantic/uvicorn"
    warn "Esas deps viven en replit.nix — instalarlas por pip rompe pydantic-core"
    # Solo instalar deps que NO están en replit.nix
    local REQ_FILES=(
      "$ROOT/redteam/requirements.txt"
      "$ROOT/commander/requirements.txt"
    )
    for req in "${REQ_FILES[@]}"; do
      if [ -f "$req" ]; then
        # Filtrar paquetes que ya están en Nix
        info "Instalando (filtrado): $(basename $req)"
        grep -vE "^(fastapi|uvicorn|pydantic|httpx|psutil|requests) " "$req" 2>/dev/null | \
          $PIP install -r /dev/stdin --quiet 2>>"$LOG_DIR/sync.log" && ok "$(basename $req) instalado (filtrado)" || warn "$(basename $req) falló"
        installed=1
      fi
    done
  else
    # Termux / Linux: instalar todo
    local REQ_FILES=(
      "$ROOT/redteam/requirements.txt"
      "$ROOT/commander/requirements.txt"
      "$ROOT/leviathan_core/requirements.txt"
    )
    for req in "${REQ_FILES[@]}"; do
      if [ -f "$req" ]; then
        info "Instalando: $req"
        $PIP install -r "$req" --quiet 2>>"$LOG_DIR/sync.log" && ok "$(basename $req) instalado" || warn "$(basename $req) falló (algunas deps pueden no ser críticas)"
        installed=1
      fi
    done
  fi

  if [ "$installed" = "0" ]; then
    warn "No se encontraron requirements.txt — instalando mínimas"
    $PIP install requests psutil --quiet 2>>"$LOG_DIR/sync.log" && ok "Deps mínimas instaladas" || warn "Algunas deps fallaron"
  fi

  # pycryptodome (crítico, seguro en todos los entornos)
  if ! python3 -c "from Crypto.Cipher import AES" >/dev/null 2>&1; then
    if [ "$ENV_TYPE" != "replit" ]; then
      $PIP install pycryptodome --quiet 2>>"$LOG_DIR/sync.log" && ok "pycryptodome instalado" || warn "pycryptodome falló"
    fi
  fi
}

sync_deps() {
  banner
  echo ""
  log "📦 SYNC-DEPS — $(date) — entorno: $ENV_TYPE"
  echo -e "${BOLD}── Instalando dependencias ──${N}"
  echo ""
  echo -e "${BOLD} Python:${N}"
  install_python_deps
  echo ""
  echo -e "${BOLD} Node:${N}"
  install_node_deps
  echo ""
  ok "Dependencias instaladas"
}

install_node_deps() {
  if [ -d "$ROOT/tauri-frontend" ] && [ -f "$ROOT/tauri-frontend/package.json" ]; then
    info "npm install (tauri-frontend)..."
    cd "$ROOT/tauri-frontend"
    npm install --silent 2>>"$LOG_DIR/sync.log" && ok "npm install completado" || warn "npm install falló"
    cd "$ROOT"
  else
    warn "tauri-frontend no encontrado"
  fi
}

# ═══════════════════════════════════════════════════════════════════════
#  SYNC-FRONTEND — Solo rebuild
# ═══════════════════════════════════════════════════════════════════════
build_frontend() {
  if [ ! -d "$ROOT/tauri-frontend" ]; then
    warn "tauri-frontend no encontrado — saltando build"
    return
  fi

  cd "$ROOT/tauri-frontend"

  # Instalar deps si node_modules no existe
  if [ ! -d "node_modules" ]; then
    info "node_modules no existe — npm install..."
    npm install --silent 2>>"$LOG_DIR/sync.log" || warn "npm install falló"
  fi

  info "npm run build..."
  if npm run build 2>>"$LOG_DIR/sync.log"; then
    ok "Frontend compilado"

    # Copiar assets post-build (npm limpia dist/)
    [ -f "$ROOT/assets/sol_avatar.jpg" ] && cp "$ROOT/assets/sol_avatar.jpg" dist/ && ok "sol_avatar.jpg copiado a dist/"
    [ -f "$ROOT/backend/static/sol_avatar.png" ] && cp "$ROOT/backend/static/sol_avatar.png" dist/ && ok "sol_avatar.png copiado a dist/"
    [ -f "$ROOT/backend/static/sol.html" ] && cp "$ROOT/backend/static/sol.html" dist/ && ok "sol.html copiado a dist/"
    # Verificar módulos de Sol
    [ -f "$ROOT/sol_tools.py" ] && ok "sol_tools.py presente" || warn "sol_tools.py FALTA"
    [ -f "$ROOT/sol_learning_advanced.py" ] && ok "sol_learning_advanced.py presente" || warn "sol_learning_advanced.py FALTA"
    [ -f "$ROOT/sol_body.sh" ] && ok "sol_body.sh presente" || warn "sol_body.sh FALTA"
    [ -f "$ROOT/sol_watchdog.sh" ] && ok "sol_watchdog.sh presente" || warn "sol_watchdog.sh FALTA"
  else
    fail "Frontend build falló"
    warn "El sistema puede funcionar con el build anterior si existe"
  fi

  cd "$ROOT"
}

sync_frontend() {
  banner
  echo ""
  log "🎨 SYNC-FRONTEND — $(date)"
  echo -e "${BOLD}── Rebuild frontend ──${N}"
  echo ""
  build_frontend
  echo ""
  ok "Frontend actualizado"
}

# ═══════════════════════════════════════════════════════════════════════
#  LOGS
# ═══════════════════════════════════════════════════════════════════════
logs() {
  local svc="${1:-all}"
  case "$svc" in
    dash|dashboard)  tail -50 "$LOG_DIR/dash.log" 2>/dev/null || echo "Sin logs de dashboard" ;;
    ghost|phantom)   tail -50 "$LOG_DIR/ghost.log" 2>/dev/null || echo "Sin logs de GHOST" ;;
    tg|telegram|sol) tail -50 "$LOG_DIR/tg.log" 2>/dev/null || echo "Sin logs de Telegram" ;;
    c2)              tail -50 "$LOG_DIR/c2.log" 2>/dev/null || echo "Sin logs de C2" ;;
    nexus)           tail -50 "$LOG_DIR/nexus.log" 2>/dev/null || echo "Sin logs de Nexus" ;;
    seal)            tail -50 "$LOG_DIR/seal.log" 2>/dev/null || echo "Sin logs de Seal" ;;
    watchdog)        tail -50 "$LOG_DIR/watchdog.log" 2>/dev/null || echo "Sin logs de Watchdog" ;;
    all|*)           echo -e "${BOLD}=== Dashboard ===${N}"; tail -20 "$LOG_DIR/dash.log" 2>/dev/null
                     echo -e "\n${BOLD}=== GHOST ===${N}"; tail -20 "$LOG_DIR/ghost.log" 2>/dev/null
                     echo -e "\n${BOLD}=== Telegram ===${N}"; tail -20 "$LOG_DIR/tg.log" 2>/dev/null
                     echo -e "\n${BOLD}=== Nexus ===${N}"; tail -20 "$LOG_DIR/nexus.log" 2>/dev/null
                     echo -e "\n${BOLD}=== Seal ===${N}"; tail -20 "$LOG_DIR/seal.log" 2>/dev/null ;;
  esac
}

# ═══════════════════════════════════════════════════════════════════════
#  SNAPSHOT — Snapshot cifrado del .env
# ═══════════════════════════════════════════════════════════════════════
snapshot() {
  banner
  echo ""
  if [ -f "$ROOT/scripts/snapshot_env.sh" ]; then
    bash "$ROOT/scripts/snapshot_env.sh"
  else
    fail "scripts/snapshot_env.sh no encontrado"
    info "Respaldando plano..."
    cp "$ENV_FILE" "$ENV_FILE.snapshot-$(date +%s)"
    ok "Respaldo plano: $ENV_FILE.snapshot-*"
  fi
}

# ═══════════════════════════════════════════════════════════════════════
#  VERIFY — Solo verificar credenciales (sin arrancar nada)
# ═══════════════════════════════════════════════════════════════════════
verify() {
  banner
  echo ""
  log "🔍 VERIFY — $(date)"
  echo ""
  verify_credentials
  local rc=$?
  echo ""
  if [ $rc -eq 0 ]; then
    ok "Todo en orden — seguro para arrancar"
  else
    fail "NO arrancar — credenciales incompletas"
  fi
  return $rc
}

# ═══════════════════════════════════════════════════════════════════════
#  WATCHDOG — Vigilar y reiniciar caídos
# ═══════════════════════════════════════════════════════════════════════
watchdog() {
  log "🐕 Watchdog en marcha — chequeo cada 60s"
  load_env
  while true; do
    sleep 60

    # Dashboard :8001
    if ! curl -s -m 4 http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
      log "⚠️ Dashboard caído → reiniciando"
      cd "$ROOT/redteam/scripts"
      PORT=8001 HOST="${HOST:-0.0.0.0}" \
        COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}" \
        PYTHONUNBUFFERED=1 nohup python3 dashboard_server.py >> "$LOG_DIR/dash.log" 2>&1 &
      sleep 10
      cd "$ROOT"
    fi

    # GHOST :8002
    if [ -f "$ROOT/ghost_hunter_phantom/master.py" ]; then
      if ! curl -s -m 3 http://127.0.0.1:8002/api/status >/dev/null 2>&1; then
        if ! pgrep -f "ghost_hunter_phantom/master" >/dev/null; then
          log "⚠️ GHOST Master caído → reiniciando"
          cd "$ROOT/ghost_hunter_phantom"
          BACKEND_API="http://127.0.0.1:8001" MASTER_PORT=8002 \
            nohup python3 master.py >> "$LOG_DIR/ghost.log" 2>&1 &
          sleep 8
          cd "$ROOT"
        fi
      fi
    fi

    # Nexus :8004
    if [ -f "$ROOT/nexus_omni_v9.py" ]; then
      if ! curl -s -m 3 http://127.0.0.1:8004/ >/dev/null 2>&1; then
        if ! pgrep -f "nexus_omni" >/dev/null; then
          log "⚠️ Nexus caído → reiniciando"
          cd "$ROOT"
          nohup python3 nexus_omni_v9.py >> "$LOG_DIR/nexus.log" 2>&1 &
          sleep 5
        fi
      fi
    fi


    # C2 :8005
    if [ -f "$ROOT/c2_unified_pro.py" ]; then
      if ! curl -s -m 3 http://127.0.0.1:8005/api/health >/dev/null 2>&1; then
        if ! pgrep -f "c2_unified_pro" >/dev/null; then
          log "⚠️ C2 caído → reiniciando"
          cd "$ROOT"
          C2_PORT=8005 nohup python3 c2_unified_pro.py >> "$LOG_DIR/c2.log" 2>&1 &
          sleep 5
        fi
      fi
    fi
    # Telegram — reiniciar SOLO si NINGUNO de los dos (puente/miniapp) está corriendo
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
      if ! pgrep -f "sol_telegram_bridge" >/dev/null && ! pgrep -f "sol_telegram_bot.py" >/dev/null; then
        log "⚠️ Telegram caído → reiniciando (desde ~/sol)"
        cd "$SOL_REPO"
        if [ -f "$SOL_REPO/sol_telegram_bot.py" ] && python3 -c "import telegram" 2>/dev/null; then
          nohup python3 sol_telegram_bot.py >> "$LOG_DIR/tg_bot.log" 2>&1 &
          echo $! > "$SOL_DIR/tg_bot.pid"
        else
          nohup python3 sol_telegram_bridge.py >> "$LOG_DIR/tg.log" 2>&1 &
        fi
        sleep 3
      fi
    fi

  done
}

# ═══════════════════════════════════════════════════════════════════════
#  SOL STACK — cerebro + watchdog de identidad
# ═══════════════════════════════════════════════════════════════════════
start_sol_stack() {
  local root="$HOME/sol"   # ☀️ Sol vive en su propio repo
  if [ ! -d "$root" ]; then
    echo "[omni] ⚠️ ~/sol no existe — usa 'bash omni.sh sync' para clonarlo"
    return 1
  fi
  load_sol_env   # ☀️ llaves de Sol (LLM, rele) desde ~/sol/.env — sin tocar el archivo
  # Sol API (:8006) — cerebro + herramientas + SIL
  if ! pgrep -f sol_api.py >/dev/null; then
    ( cd "$root" && nohup python3 sol_api.py >>"$HOME/.sol/sol_api.log" 2>&1 & echo $! > "$HOME/.sol/sol_api.pid" )
    wait_sol_api 15   # sin falso DETENIDA: esperar a que su cerebro despierte
  fi
  # Sol daemon — iniciativa + pensamiento idle
  pgrep -f sol_daemon.py >/dev/null || ( cd "$root" && nohup python3 sol_daemon.py >>"$HOME/.sol/daemon.log" 2>&1 & echo $! > "$HOME/.sol/sol.pid" )
  # Watchdog — revive procesos + blinda identidad
  pgrep -f sol_watchdog.sh >/dev/null || { chmod +x "$root/sol_watchdog.sh" 2>/dev/null; nohup bash "$root/sol_watchdog.sh" >>"$HOME/.sol/watchdog.log" 2>&1 & }
  # Verificar módulos de Sol
  for mod in sol_tools.py sol_learning_advanced.py; do
    [ -f "$root/$mod" ] || echo "[omni] ⚠️ Falta $mod — algunas funciones de Sol no estarán disponibles"
  done
  echo "[omni] ✅ stack de Sol activo (API + daemon + watchdog)"
}

# ═══════════════════════════════════════════════════════════════════════
#  DISPATCH
# ═══════════════════════════════════════════════════════════════════════
case "${1:-help}" in
  start)          acquire_lock; start ;;
  stop)           acquire_lock; stop ;;
  restart)        acquire_lock; restart ;;
  status)         status ;;
  sync)           acquire_lock; sync ;;
  sync-deps)      sync_deps ;;
  sync-frontend)  sync_frontend ;;
  logs)           logs "${2:-all}" ;;
  snapshot)       snapshot ;;
  verify)         verify ;;
  watchdog)       watchdog ;;
  help|--help|-h) help ;;
  *)              echo "Comando desconocido: $1"; 
# ════════════════════════════════════════════════════════════════════
# EVOLVE DAEMON — auto-actualización y mantenimiento
# ════════════════════════════════════════════════════════════════════
if [ -f "$RT/sol_evolve.sh" ]; then
  if ! pgrep -f "sol_evolve.sh daemon" >/dev/null 2>&1; then
    (nohup bash "$RT/sol_evolve.sh" daemon >> "$HOME/.sol/evolve.log" 2>&1 &)
    echo -e "${G}☀️  Evolve daemon activo — el sistema se mantiene solo${N}"
  else
    echo -e "${C}☀️  Evolve daemon ya corriendo${N}"
  fi
fi

echo ""; help; exit 1 ;;
esac
