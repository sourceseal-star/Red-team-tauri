#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════════
#  OMNI.SH — SourceSeal Unified Command
#  Launcher local para Dashboard, SOL GATE y Sol.
#  .env solo se lee; nunca se regenera ni se publica desde este script.
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOL_DIR="$HOME/.sol"
LOG_DIR="$SOL_DIR/logs"
ENV_FILE="$ROOT/.env"
SOL_REPO="${SOL_REPO:-$HOME/sol}"
SOL_GATE_PORT="${SOL_GATE_PORT:-8012}"
SOL_PORTERO_URL="${SOL_PORTERO_URL:-http://127.0.0.1:${SOL_GATE_PORT}}"
SOL_CORE_ONLY="${SOL_CORE_ONLY:-0}"
[ -f "$HOME/.sol/core_only" ] && SOL_CORE_ONLY=1
mkdir -p "$SOL_DIR" "$LOG_DIR" "$SOL_DIR/tmp" 2>/dev/null || true
OMNI_TMP_DIR="$SOL_DIR/tmp"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'
W='\033[1;37m'; D='\033[0;90m'; N='\033[0m'; BOLD='\033[1m'

OMNI_LOCK="${TMPDIR:-$OMNI_TMP_DIR}/omni-singleton.lock"
CLEAN_LOCK() { rm -rf "$OMNI_LOCK" 2>/dev/null || true; }
acquire_lock() {
  if mkdir "$OMNI_LOCK" 2>/dev/null; then
    echo "$$" > "$OMNI_LOCK/pid"
    trap CLEAN_LOCK EXIT INT TERM
    return 0
  fi
  local old_pid
  old_pid="$(cat "$OMNI_LOCK/pid" 2>/dev/null || true)"
  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Otro omni.sh sigue corriendo (PID $old_pid)" >&2
    return 1
  fi
  rm -rf "$OMNI_LOCK" 2>/dev/null || true
  mkdir "$OMNI_LOCK" 2>/dev/null || return 1
  echo "$$" > "$OMNI_LOCK/pid"
  trap CLEAN_LOCK EXIT INT TERM
}

banner() {
  echo -e "${C}╔═══════════════════════════════════════════════════════╗${N}"
  echo -e "${C}║  ${W}OMNI.SH${C} — SourceSeal Unified Command              ║${N}"
  echo -e "${C}╚═══════════════════════════════════════════════════════╝${N}"
}
log()  { echo -e "${D}[$(date '+%H:%M:%S')]${N} $*" | tee -a "$LOG_DIR/omni.log"; }
ok()   { echo -e "${G}  ✓${N} $*"; log "  ✓ $*"; }
fail() { echo -e "${R}  ✗${N} $*"; log "  ✗ $*"; }
warn() { echo -e "${Y}  ⚠${N} $*"; log "  ⚠ $*"; }
info() { echo -e "${C}  →${N} $*"; log "  → $*"; }

detect_env() {
  if [ -n "${TERMUX_VERSION:-}" ] || [ -d "/data/data/com.termux" ]; then
    echo termux
  elif [ -n "${REPL_ID:-}" ] || [ -n "${REPL_SLUG:-}" ]; then
    echo replit
  else
    echo linux
  fi
}
ENV_TYPE="$(detect_env)"

load_env() {
  [ -f "$ENV_FILE" ] || { fail ".env no existe en $ENV_FILE"; return 1; }
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*|[[:space:]]*) continue;; esac
    k="${k%%[[:space:]]*}"
    v="${v#\"}"; v="${v%\"}"; v="${v#\'}"; v="${v%\'}"; v="${v%%[[:space:]]*}"
    [ -n "$k" ] && export "$k=$v" 2>/dev/null || true
  done < "$ENV_FILE"
  return 0
}
load_sol_env() {
  local sol_env="$SOL_REPO/.env"
  [ -f "$sol_env" ] || return 0
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*|[[:space:]]*) continue;; esac
    k="${k%%[[:space:]]*}"
    v="${v#\"}"; v="${v%\"}"; v="${v#\'}"; v="${v%\'}"; v="${v%%[[:space:]]*}"
    [ -n "$k" ] && export "$k=$v" 2>/dev/null || true
  done < "$sol_env"
}
ensure_sol_repo() {
  [ -d "$SOL_REPO/.git" ] && return 0
  warn "No existe el repositorio de Sol en $SOL_REPO"
  return 1
}
sync_commander_repo() { return 0; }

verify_qalam() {
  # Con set -u, las expansiones de una misma declaración local ocurren antes
  # de asignar root. Separar las declaraciones evita "root: unbound variable".
  local root="${1:-$SOL_REPO}"
  local py="$root/sol_qalam.py"
  local md="$root/bestiario-qalam.v1.md"
  [ -f "$py" ] && [ -f "$md" ] || { warn "Bestiario Qalam incompleto en $root"; return 1; }
  python3 -m py_compile "$py" >/dev/null 2>&1 || { warn "Qalam no compila: $py"; return 1; }
  local result egyptian entries
  result="$(cd "$root" && python3 -c 'import sol_qalam; r=sol_qalam.verify(); print(str(r["valid"])+":"+str(r["count"])+":"+sol_qalam.stamp("خخخ")["code"]+":"+sol_qalam.stamp("بسم")["code"])' 2>/dev/null)"
  egyptian="$(cd "$root" && python3 -c 'import sol_qalam; r=sol_qalam.egyptian_status(); print(str(r["valid"])+":"+str(r["locale"])+":"+str(r["phrases"]))' 2>/dev/null)"
  entries="$(grep -cE '^[[:space:]]*[0-9]{2}[[:space:]]' "$md" 2>/dev/null || echo 0)"
  if [ "$result" = "True:38:404 FAIL ✗✗:200 OK ✓" ] && [ "$entries" = 38 ] && echo "$egyptian" | grep -q '^True:ar-EG:'; then
    ok "Bestiario Qalam v1 verificado"
    return 0
  fi
  warn "Qalam pendiente: $result; idioma: $egyptian; entradas: $entries"
  return 1
}
wait_sol_api() {
  local tries="${1:-15}" i=1
  while [ "$i" -le "$tries" ]; do
    curl -s -m 2 http://127.0.0.1:8006/api/sol/status >/dev/null 2>&1 && return 0
    sleep 1; i=$((i + 1))
  done
  warn "Sol API :8006 no respondió en ${tries}s"
  return 1
}
verify_sol_vars() {
  local sol_env="$SOL_REPO/.env"
  [ -f "$sol_env" ] || { warn "$sol_env no existe"; return 0; }
  grep -q '^SOL_PUBLIC_URL=https' "$sol_env" 2>/dev/null || warn "Falta SOL_PUBLIC_URL en ~/sol/.env"
  grep -q '^SOL_API_KEY=' "$sol_env" 2>/dev/null || warn "Falta SOL_API_KEY en ~/sol/.env"
  grep -q '^LLM_API_KEY=' "$sol_env" 2>/dev/null || warn "Falta LLM_API_KEY en ~/sol/.env"
  return 0
}
verify_credentials() {
  [ -f "$ENV_FILE" ] || { fail ".env no existe en $ENV_FILE"; return 1; }
  local missing="" key value
  for key in NEXUS_PASS ADMIN_PASSWORD REDTEAM_API_KEY; do
    value="$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 | tr -d "'\"" || true)"
    [ -n "$value" ] || missing="$missing $key"
  done
  if [ -n "$missing" ]; then
    fail "Credenciales críticas faltantes:$missing"
    return 1
  fi
  ok "Credenciales críticas presentes (valores ocultos)"
  return 0
}
help() {
  cat <<'HELP'
OMNI.SH — comandos:
  start | stop | restart | status | sync | sync-deps | sync-frontend
  logs [dashboard|gate|all] | supergate [status|sweep|action]
  snapshot | verify | watchdog | recover
HELP
}
termux_guard() {
  if [ -n "${TERMUX_VERSION:-}" ] && command -v termux-battery-status >/dev/null 2>&1; then
    timeout 4 termux-battery-status >/dev/null 2>&1 || warn "Termux:API no responde"
  fi
  return 0
}
_pids_on_port() {
  python3 - "$1" <<'PY' 2>/dev/null | sort -u
import glob, os, re, sys
port = format(int(sys.argv[1]), "04X")
inodes = set()
for name in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        lines = open(name).read().splitlines()[1:]
    except OSError:
        continue
    for line in lines:
        p = line.split()
        if len(p) >= 10 and p[1].split(":")[-1].upper() == port and p[3] == "0A":
            inodes.add(p[9])
for fd in glob.glob("/proc/[0-9]*/fd/*"):
    try: target = os.readlink(fd)
    except OSError: continue
    m = re.match(r"socket:\[(\d+)\]", target)
    if m and m.group(1) in inodes: print(fd.split("/")[2])
PY
}
kill_by_pidfile_or_port() {
  local label="$1" pidfile="$2" pattern="$3" port="$4" pid
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
    rm -f "$pidfile"
  fi
  [ -n "$pattern" ] && pkill -f "$pattern" 2>/dev/null || true
  [ -n "$port" ] && { for pid in $(_pids_on_port "$port"); do kill -9 "$pid" 2>/dev/null || true; done; }
  ok "$label detenido o ya estaba detenido"
}
sol_gate_is_alive() {
  local code
  code="$(curl -s -m 2 -o /dev/null -w '%{http_code}' "$SOL_PORTERO_URL/health" 2>/dev/null || echo 000)"
  case "$code" in 200) return 0;; esac
  code="$(curl -s -m 2 -o /dev/null -w '%{http_code}' "$SOL_PORTERO_URL/sol/contexto" 2>/dev/null || echo 000)"
  case "$code" in 200|401|403|503) return 0;; *) return 1;; esac
}
start_sol_gate() {
  sol_gate_is_alive && { ok "SOL GATE :$SOL_GATE_PORT ya activo"; return 0; }
  local module=sol_portero dir="$SOL_REPO"
  if [ ! -f "$dir/sol_portero.py" ]; then
    [ -f "$dir/sol_supergate.py" ] || { fail "No existe sol_portero.py ni sol_supergate.py en $dir"; return 1; }
    module=sol_supergate
  fi
  cd "$dir" || return 1
  SOL_DIR="$SOL_REPO" REDTEAM_DIR="$ROOT" SOL_GATE_PORT="$SOL_GATE_PORT" \
    SOL_PORTERO_URL="$SOL_PORTERO_URL" PYTHONUNBUFFERED=1 \
    nohup python3 -m uvicorn "$module:app" --host 127.0.0.1 --port "$SOL_GATE_PORT" \
    >> "$LOG_DIR/sol_gate.log" 2>&1 &
  echo "$!" > "$SOL_DIR/sol_gate.pid"
  cd "$ROOT" || true
  local i
  for i in $(seq 1 20); do sol_gate_is_alive && { ok "SOL GATE :$SOL_GATE_PORT listo"; return 0; }; sleep 1; done
  fail "SOL GATE :$SOL_GATE_PORT no respondió"
  return 1
}
verify_frontend_dist() {
  local validator="$ROOT/redteam/scripts/validate_frontend_dist.py"
  [ -f "$validator" ] || { fail "Falta el validador del frontend"; return 1; }
  python3 "$validator"
}

start() {
  banner
  load_env || return 1
  load_sol_env
  verify_frontend_dist || { fail "Frontend dist incompleto"; return 1; }
  echo ""
  log "OMNI START — entorno: $ENV_TYPE"
  echo ""
  # Preflight: credenciales
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
  free_port "$SOL_GATE_PORT" 2>/dev/null || true

  # ── Limpiar procesos previos ──
  pkill -f "$ROOT/redteam/scripts/dashboard_server.py" 2>/dev/null || true
  # BLINDAJE 2026-09-06: si algo ajeno (sol_api viejo con PORT=8001 heredado)
  # retiene el 8001, el dashboard nace muerto → pantalla negra. Lo matamos.
  _p8001=$(command -v fuser >/dev/null 2>&1 && fuser 8001/tcp 2>/dev/null || true)
  [ -n "$_p8001" ] && { warn "Matando intruso en :8001 (PID $_p8001)"; kill -9 $_p8001 2>/dev/null; sleep 1; }
  pkill -f "$ROOT/ghost_hunter_phantom/master.py" 2>/dev/null || true
  pkill -f "$ROOT/ghost_hunter_phantom/node.py" 2>/dev/null || true
  pkill -f "$ROOT/nexus_omni_v9.py" 2>/dev/null || true
  pkill -f "$ROOT/c2_unified_pro.py" 2>/dev/null || true
  pkill -f "$ROOT/sol_telegram_bridge.py" 2>/dev/null || true
  pkill -f "uvicorn sol_(portero|supergate):app" 2>/dev/null || true
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

  # ── 2/3/4. GHOST + Nexus + C2 — infraestructura de pentesting pesada.
  # SALTADA en SOL_CORE_ONLY=1: son 3 procesos Python extra (+ GHOST Node,
  # 4 en total) que compiten por RAM con el cerebro de Sol. Nada de esto
  # es necesario para que Sol viva y hable — es la War Room de pentesting.
  if [ "$SOL_CORE_ONLY" = "1" ]; then
    info "🧠 MODO NÚCLEO activo — GHOST/Nexus/C2 saltados (RAM libre para Sol)"
  else
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

    fi

# ── 5. SOL GATE (:8012 por defecto) — antes que daemon/Telegram ──
  # Las acciones sensibles fallan cerrado si el portero no está vivo.
  start_sol_gate || warn "Sol seguirá viva, pero push/SMS/Docker/shell/scan externo quedarán bloqueados"

  # ── 6. Telegram (Sol) — SOLO UNO puede hacer polling del mismo token a la vez ──
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
      # BLINDAJE 2026-09-06: un ~/sol VIEJO (token vencido, sin pull) hereda
      # PORT=8001 del .env de Red-team y le ROBA el puerto al War Room.
      # Forzamos 8006 en TODAS las variables que el codigo viejo o nuevo pueda leer.
      SOL_PORT=8006 PORT=8006 nohup python3 sol_api.py >> "$LOG_DIR/sol_api.log" 2>&1 &
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
  start_evolve_daemon
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
  kill_by_pidfile_or_port "SOL GATE"       "$SOL_DIR/sol_gate.pid" "uvicorn sol_(portero|supergate):app" "$SOL_GATE_PORT"
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

  # SOL GATE :8012 (local, nunca expuesto a la red)
  if sol_gate_is_alive; then
    ok "SOL GATE :$SOL_GATE_PORT  🟢 ACTIVO"
  else
    fail "SOL GATE :$SOL_GATE_PORT  🔴 CAÍDO (acciones sensibles bloqueadas)"
  fi

  # GHOST + Nexus + C2: en modo núcleo se omiten deliberadamente para
  # reservar memoria para Sol. No deben aparecer como "caídos".
  if [ "$SOL_CORE_ONLY" = "1" ]; then
    info "GHOST :8002        ⚪ OMITIDO (modo núcleo)"
    info "GHOST Node         ⚪ OMITIDO (modo núcleo)"
    info "Nexus :8004        ⚪ OMITIDO (modo núcleo)"
    info "C2 :8005           ⚪ OMITIDO (modo núcleo)"
  else
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
    # FIX 2026-09-04: mostrar la CAUSA REAL, no solo el estado —
    # así un screenshot del status basta para diagnosticar a distancia
    if [ -s "$HOME/.sol/sol_api.log" ]; then
      echo -e "${BOLD}    └─ últimas líneas de ~/.sol/sol_api.log:${N}"
      tail -5 "$HOME/.sol/sol_api.log" 2>/dev/null | sed 's/^/       │ /'
    fi
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
#  SOL SUPERGATE — operaciones explícitas, locales y de solo lectura
#  No reinicia servicios, no publica cambios y nunca imprime la clave.
# ═══════════════════════════════════════════════════════════════════════
supergate_status() {
  local health_code context_code
  health_code="$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$SOL_PORTERO_URL/health" 2>/dev/null || echo 000)"
  context_code="$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$SOL_PORTERO_URL/sol/contexto" 2>/dev/null || echo 000)"
  if [ "$health_code" = "200" ] || [ "$context_code" = "200" ] || \
     [ "$context_code" = "401" ] || [ "$context_code" = "403" ]; then
    ok "SOL SUPERGATE accesible en $SOL_PORTERO_URL (health=$health_code contexto=$context_code)"
    return 0
  fi
  fail "SOL SUPERGATE no responde en $SOL_PORTERO_URL" "health=$health_code contexto=$context_code"
  return 1
}

supergate_sweep() {
  if [ -z "${SOL_API_KEY:-}" ] && [ -z "${SOL_KEY:-}" ]; then
    fail "Barrido bloqueado: falta SOL_API_KEY/SOL_KEY en el entorno"
    return 1
  fi
  info "Barrido non-root solicitado; no modifica dispositivos ni configuración"
  curl -sS -m 30 -X POST "$SOL_PORTERO_URL/api/network/sweep-real" \
    -H "X-Sol-Key: ${SOL_API_KEY:-$SOL_KEY}" \
    -H "Content-Type: application/json" || {
      echo ""
      fail "El barrido no respondió" "revisa: bash omni.sh logs gate"
      return 1
    }
  echo ""
}

supergate_action() {
  local action="${1:-}" target="${2:-}"
  case "$action" in
    ping)     [ -n "$target" ] || target="127.0.0.1" ;;
    netstat|ip_neigh) ;;
    *)
      fail "Acción no permitida: ${action:-vacía}" "usa ping, netstat o ip_neigh"
      return 1
      ;;
  esac
  if [ -z "${SOL_API_KEY:-}" ] && [ -z "${SOL_KEY:-}" ]; then
    fail "Acción bloqueada: falta SOL_API_KEY/SOL_KEY en el entorno"
    return 1
  fi
  local body
  body="$(ACTION="$action" TARGET="$target" python3 - <<'PY'
import json
import os
payload = {"action": os.environ["ACTION"]}
if os.environ.get("TARGET"):
    payload["target"] = os.environ["TARGET"]
print(json.dumps(payload, ensure_ascii=False))
PY
)"
  curl -sS -m 12 -X POST "$SOL_PORTERO_URL/api/action/execute" \
    -H "X-Sol-Key: ${SOL_API_KEY:-$SOL_KEY}" \
    -H "Content-Type: application/json" \
    --data "$body" || {
      echo ""
      fail "La acción no respondió" "revisa: bash omni.sh logs gate"
      return 1
    }
  echo ""
}

supergate() {
  case "${1:-status}" in
    status) supergate_status ;;
    sweep) supergate_sweep ;;
    action) shift; supergate_action "${1:-}" "${2:-}" ;;
    help|--help|-h)
      echo "Uso: bash omni.sh supergate {status|sweep|action ping [host]|action netstat|action ip_neigh}"
      ;;
    *) fail "Subcomando SUPERGATE desconocido: $1"; return 1 ;;
  esac
}

# ═══════════════════════════════════════════════════════════════════════
#  SYNC — git pull + deps + build (SIN tocar .env)
#  REGLA DE ORO: .env es intocable. Triple protección.
# ═══════════════════════════════════════════════════════════════════════
resolve_generated_dist_rebase() {
  # Vite renombra los bundles en cada build. curar.sh puede guardar esos
  # artefactos en un commit local de respaldo y origin/main puede contener
  # otra generación del mismo dist. Solo aquí, y únicamente si TODOS los
  # conflictos son artefactos generados, se conserva la versión publicada
  # (ours durante una rebase) y se continúa preservando cualquier código del
  # commit local. Un conflicto fuera de dist sigue siendo un aborto seguro.
  local conflicts path
  conflicts="$(git diff --name-only --diff-filter=U 2>/dev/null)"
  [ -n "$conflicts" ] || return 1

  while [ -n "$conflicts" ]; do
    if printf '%s\n' "$conflicts" | grep -qv '^tauri-frontend/dist/'; then
      return 1
    fi

    while IFS= read -r path; do
      [ -n "$path" ] || continue
      # Durante rebase, stage 2 (ours) es la base remota ya aplicada.
      # En modify/delete no existe stage 2: git rm conserva la eliminación
      # remota en vez de reintroducir un hash local obsoleto.
      if git rev-parse --verify ":2:$path" >/dev/null 2>&1; then
        git checkout --ours -- "$path" || return 1
        git add -- "$path" || return 1
      else
        git rm -- "$path" || return 1
      fi
    done <<< "$conflicts"

    if GIT_EDITOR=true git -c core.editor=true rebase --continue; then
      return 0
    fi

    # Puede haber otro commit local con dist en conflicto. Solo se intenta
    # seguir si Git dejó nuevos unmerged paths; cualquier otro error aborta.
    conflicts="$(git diff --name-only --diff-filter=U 2>/dev/null)"
    [ -n "$conflicts" ] || return 1
  done

  return 0
}

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

  # 0c. Copia temporal para restauración de emergencia.
  # No asumir que /tmp es escribible en Termux.
  ENV_RESTORE="$OMNI_TMP_DIR/omni-env-restore-$$"
  if ! cp "$ENV_FILE" "$ENV_RESTORE"; then
    fail "No se pudo crear la copia de emergencia de .env en $OMNI_TMP_DIR"
    exit 1
  fi
  chmod 600 "$ENV_RESTORE" 2>/dev/null || true
  ok "Copia de emergencia en $OMNI_TMP_DIR"

  echo ""

  # ── 1. GIT PULL ──
  echo -e "${BOLD} Paso 1: sincronizar Git${N}"
  cd "$ROOT"

  # Si hay cambios locales, stash completo (incluidos archivos nuevos).
  # .env sigue fuera porque está en .gitignore y nunca se fuerza con -a.
  OMNI_STASH_REF=""
  LOCAL_CHANGES="$(git status --porcelain 2>/dev/null | head -20)"
  if [ -n "$LOCAL_CHANGES" ]; then
    info "Cambios locales detectados — guardando en stash..."
    OMNI_STASH_LABEL="omni-sync-$(date +%s)-$$"
    if git stash push -u -m "$OMNI_STASH_LABEL" 2>/dev/null; then
      OMNI_STASH_REF="$(git stash list --format='%gd' -1 2>/dev/null || true)"
      ok "Stash completo creado${OMNI_STASH_REF:+ ($OMNI_STASH_REF)}"
    else
      fail "No se pudo guardar el estado local; sync cancelado para no perder cambios"
      rm -f "$ENV_RESTORE"
      exit 1
    fi
  fi

  # Con una rama local como termux-snapshot, origin/main puede haber
  # divergido. Rebase conserva los commits del teléfono y aplica encima lo
  # publicado, sin reset --hard ni pérdida silenciosa de trabajo.
  OMNI_BACKUP_BRANCH="omni-pre-sync-$(date +%Y%m%d-%H%M%S)-$$"
  if git branch "$OMNI_BACKUP_BRANCH" HEAD >/dev/null 2>&1; then
    info "Respaldo de rama creado: $OMNI_BACKUP_BRANCH"
  else
    warn "No se pudo crear respaldo de rama; el stash sigue protegido"
  fi

  info "git pull --rebase origin main..."
  if git pull --rebase origin main 2>&1 | tee -a "$LOG_DIR/sync.log"; then
    ok "Git sincronizado con origin/main"
  else
    if resolve_generated_dist_rebase; then
      ok "Conflicto limitado al dist generado; se conservó origin/main"
    else
      fail "La sincronización Git falló; no se borró ningún cambio local"
      git rebase --abort 2>/dev/null || true
      if [ -n "$OMNI_STASH_REF" ]; then
        warn "Restaurando cambios locales desde $OMNI_STASH_REF..."
        git stash apply "$OMNI_STASH_REF" 2>/dev/null \
          && git stash drop "$OMNI_STASH_REF" >/dev/null 2>&1 \
          && ok "Cambios locales restaurados" \
          || warn "El stash quedó guardado; consulta: git stash list"
      fi
      # Restaurar .env por si acaso
      if [ ! -f "$ENV_FILE" ] || [ "$(sha256sum "$ENV_FILE" | cut -d' ' -f1)" != "$ENV_HASH_BEFORE" ]; then
        warn "Restaurando .env desde respaldo..."
        if [ -f "$ENV_RESTORE" ] && cp "$ENV_RESTORE" "$ENV_FILE"; then
          ok ".env restaurado"
        else
          fail "No se pudo restaurar .env desde $ENV_RESTORE"
        fi
      fi
      rm -f "$ENV_RESTORE"
      exit 1
    fi
  fi

  # Restaurar stash si existe
  if [ -n "$OMNI_STASH_REF" ]; then
    info "Restaurando cambios locales desde $OMNI_STASH_REF..."
    if git stash apply "$OMNI_STASH_REF" 2>/dev/null; then
      git stash drop "$OMNI_STASH_REF" >/dev/null 2>&1 || true
      ok "Cambios locales restaurados"
    else
      fail "Conflicto al restaurar cambios locales"
      warn "El stash original se conserva en: git stash list"
      if [ -f "$ENV_RESTORE" ]; then
        cp "$ENV_RESTORE" "$ENV_FILE" 2>/dev/null || true
      fi
      rm -f "$ENV_RESTORE"
      exit 1
    fi
  fi

  # ── Paso 1b: repo de Sol (~/sol) — clona si falta, actualiza si existe ──
  # SIN tocar ~/sol/.env: hash antes y después, como con el .env principal.
  echo -e "${BOLD} Paso 1b: repo de Sol (~/sol)${N}"
  ensure_sol_repo
  verify_qalam "$SOL_REPO" || warn "☀️ Qalam quedó pendiente tras sincronizar ~/sol"
  if [ -d "$SOL_REPO/.git" ] && [ -f "$SOL_REPO/sol_core.py" ]; then
    ok "☀️ ~/sol listo — cerebro de Sol actualizado"
  elif [ -d "$SOL_REPO/.git" ]; then
    warn "☀️ ~/sol existe pero sin sol_core.py — revisa $LOG_DIR/sol_sync.log"
  fi
  # 🎖️ Paso 1c: el tercer repo del ecosistema
  echo -e "${BOLD} Paso 1c: repo de Commander (~/commander)${N}"
  sync_commander_repo

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

  rm -f "$ENV_RESTORE"

  # Limpiar respaldos viejos (>7 días)
  find "$ROOT" -name ".env.omni-backup-*" -mtime +7 -delete 2>/dev/null || true

  echo ""
  echo -e "${G}╔═══════════════════════════════════════════════════════╗${N}"
  echo -e "${G}║  ${W}✅ SYNC COMPLETADO${G} — .env intacto               ║${N}"
  echo -e "${G}╚═══════════════════════════════════════════════════════╝${N}"
  echo ""

  # ── AUTO-APLICAR (2026-09-05): sync que NO aplica los cambios no sirve —
  # los servicios seguirían corriendo código viejo hasta el próximo restart
  # (lección de la noche del 'desastre': el fix llegó a GitHub pero el
  # navegador/servidor seguía con lo viejo). Si algo del stack está
  # corriendo, se reinicia SOLO para que el código nuevo tome efecto YA.
  _running=0
  curl -s -m 2 http://127.0.0.1:8001/api/health >/dev/null 2>&1 && _running=1
  pgrep -f "sol_daemon.py" >/dev/null 2>&1 && _running=1
  pgrep -f "dashboard_server.py" >/dev/null 2>&1 && _running=1
  if [ "$_running" = "1" ]; then
    echo -e "  ${W}⚡ Stack corriendo — reiniciando para APLICAR el código nuevo…${N}"
    log "⚡ sync: auto-restart para aplicar cambios"
    stop
    sleep 2
    start
  else
    echo -e "  Stack detenido — código listo. Próximo paso: ${W}bash omni.sh start${N}"
  fi
  log "✅ Sync completado — .env intacto, credenciales verificadas, cambios aplicados"
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
      "$SOL_REPO/requirements.txt"
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
      "$SOL_REPO/requirements.txt"
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
    gate|portero)    tail -50 "$LOG_DIR/sol_gate.log" 2>/dev/null || echo "Sin logs de SOL GATE" ;;
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
  verify_qalam "$SOL_REPO" || rc=1
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
    # SOL GATE: si cae, se levanta antes de permitir acciones sensibles.
    if ! sol_gate_is_alive; then
      log "⚠️ SOL GATE caído → reiniciando en :$SOL_GATE_PORT"
      start_sol_gate || true
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
  # MODO LIBRE por defecto (decisión explícita de Harold, dueño, 2026-09-04):
  # restaura todos los atributos de Sol — sin x-sol-key en endpoints sensibles.
  # Volver a protegido: {"mode": "protected"} en ~/.sol/security_mode.json
  # o borrar el archivo y reiniciar.
  if [ ! -f "$HOME/.sol/security_mode.json" ]; then
    printf '{"mode": "free"}\n' > "$HOME/.sol/security_mode.json" 2>/dev/null
    echo "[omni] 🔓 Sol en MODO LIBRE (decisión del dueño) — todos los atributos activos"
  fi
  local root="$HOME/sol"   # ☀️ Sol vive en su propio repo
  if [ ! -d "$root" ]; then
    echo "[omni] ⚠️ ~/sol no existe — usa 'bash omni.sh sync' para clonarlo"
    return 1
  fi
  load_sol_env   # ☀️ llaves de Sol (LLM, rele) desde ~/sol/.env — sin tocar el archivo
  verify_qalam "$root" || warn "☀️ Sol arranca, pero Qalam requiere revisión"
  # Sol API (:8006) — cerebro + herramientas + SIL
  # FIX 2026-09-04: si su cerebro no despierta, NO quedarnos mudos:
  # 1 reintentó + mostrar el error REAL del log (antes: solo un warn
  # genérico y nadie sabía por qué Sol estaba muerta).
  if ! pgrep -f sol_api.py >/dev/null; then
    ( cd "$root" && SOL_PORT=8006 PORT=8006 nohup python3 sol_api.py >>"$HOME/.sol/sol_api.log" 2>&1 & echo $! > "$HOME/.sol/sol_api.pid" )
    wait_sol_api 15   # sin falso DETENIDA: esperar a que su cerebro despierte
    if ! curl -s -m 2 http://127.0.0.1:8006/api/sol/status >/dev/null 2>&1; then
      warn "☀️ Sol API no despertó al primer intento — reintentando (el Edge 50 a veces tarda en importar)..."
      ( cd "$root" && SOL_PORT=8006 PORT=8006 nohup python3 sol_api.py >>"$HOME/.sol/sol_api.log" 2>&1 & echo $! > "$HOME/.sol/sol_api.pid" )
      wait_sol_api 20
      if curl -s -m 2 http://127.0.0.1:8006/api/sol/status >/dev/null 2>&1; then
        ok "☀️ Sol API despertó en el reintento"
      else
        fail "☀️ Sol API NO arrancó — causa real (últimas 8 líneas de ~/.sol/sol_api.log):"
        tail -8 "$HOME/.sol/sol_api.log" 2>/dev/null | sed 's/^/    │ /'
      fi
    fi
  fi
  # Sol daemon — iniciativa + pensamiento idle
  pgrep -f sol_daemon.py >/dev/null || ( cd "$root" && nohup python3 sol_daemon.py >>"$HOME/.sol/daemon.log" 2>&1 & echo $! > "$HOME/.sol/sol.pid" )
  # Watchdog — revive procesos + blinda identidad
  pgrep -f sol_watchdog.sh >/dev/null || { chmod +x "$root/sol_watchdog.sh" 2>/dev/null; nohup bash "$root/sol_watchdog.sh" >>"$HOME/.sol/watchdog.log" 2>&1 & }
  # FIX 2026-09-04: el Cuerpo de Sol (sol_body.sh) NUNCA se arrancaba —
  # por eso la war room siempre mostraba "Sol Cuerpo ⚪ DESACTIVADO".
  # Sol_body a su vez asegura API + daemon + presencia persistente.
  if [ -f "$root/sol_body.sh" ]; then
    if [ -f "$HOME/.sol/body.pid" ] && kill -0 "$(cat "$HOME/.sol/body.pid" 2>/dev/null)" 2>/dev/null; then
      echo "[omni] ☀️ Cuerpo de Sol ya activo"
    else
      chmod +x "$root/sol_body.sh" 2>/dev/null
      nohup bash "$root/sol_body.sh" start >> "$HOME/.sol/body.log" 2>&1 &
      sleep 1
      echo "[omni] ☀️ Cuerpo de Sol arrancado (presencia persistente)"
    fi
  fi
  # Verificar módulos de Sol
  for mod in sol_tools.py sol_learning_advanced.py; do
    [ -f "$root/$mod" ] || echo "[omni] ⚠️ Falta $mod — algunas funciones de Sol no estarán disponibles"
  done
  echo "[omni] ✅ stack de Sol activo (API + daemon + watchdog + cuerpo)"
}

# ═══════════════════════════════════════════════════════════════════════
#  RECOVER — rescate total en UN comando (lección de la noche 2026-09-05)
#  ¿Sol "desapareció"? ¿El dashboard quedó viejo? ¿Algo se rompió y no
#  sabes qué? Este comando: sincroniza los 3 repos A FUETE (reset --hard
#  a origin/main, cambios locales a stash — NADA se pierde, .env jamás
#  se toca porque está en .gitignore), reconstruye el frontend y
#  reinicia todo el stack. Después solo falta recarga sin caché.
# ═══════════════════════════════════════════════════════════════════════
recover() {
  banner
  echo ""
  log "🚑 RECOVER — rescate total — $(date '+%Y-%m-%d %H:%M:%S')"
  echo -e "${BOLD}── Rescate de emergencia: 3 repos a fuente + rebuild + restart ──${N}"
  echo ""

  local RT_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

  for R in "$RT_REPO" "$SOL_REPO" "$COMMANDER_REPO"; do
    [ -d "$R/.git" ] || { info "$(basename "$R"): no existe o no es repo — salto"; continue; }
    echo -e "${BOLD} ▪ $(basename "$R") → origin/main (duro)${N}"
    ( cd "$R" \
      && git stash -u --quiet 2>/dev/null && log "   ↳ cambios locales de $(basename "$R") en stash (nada se pierde)" \
      && git fetch origin -q \
      && git reset --hard origin/main -q \
      && git clean -fdq -e ".env" \
    ) && ok "$(basename "$R") en $(cd "$R" && git rev-parse --short HEAD)" \
      || warn "$(basename "$R"): sin conexión a GitHub — queda como está"
  done

  echo ""
  echo -e "${BOLD} ▪ Rebuild del frontend (War Room)${N}"
  build_frontend || warn "build falló — se usa el dist/ que viene en git"

  echo ""
  echo -e "${BOLD} ▪ Reinicio completo del stack${N}"
  stop
  sleep 2
  start

  echo ""
  echo -e "${G}╔═══════════════════════════════════════════════════════╗${N}"
  echo -e "${G}║  ${W}🚑 RESCATE COMPLETADO${G}                            ║${N}"
  echo -e "${G}╚═══════════════════════════════════════════════════════╝${N}"
  echo ""
  echo -e "  Si el navegador sigue mostrando algo VIEJO, no es el sistema —"
  echo -e "  es la caché: recarga FORZADA (mantén presionado recargar →"
  echo -e "  'Recargar sin caché') o Ajustes del sitio → Borrar datos."
  echo ""
  echo -e "  ¿Cambios locales rescatados? git stash list en cada repo."
  log "🚑 Recover completado"
}

# ═══════════════════════════════════════════════════════════════════════
#  EVOLVE DAEMON — auto-actualización y mantenimiento
# ═══════════════════════════════════════════════════════════════════════
start_evolve_daemon() {
  if [ -f "$ROOT/sol_evolve.sh" ]; then
    if ! pgrep -f "sol_evolve.sh daemon" >/dev/null 2>&1; then
      (nohup bash "$ROOT/sol_evolve.sh" daemon >> "$HOME/.sol/evolve.log" 2>&1 &)
      echo -e "${G}☀️  Evolve daemon activo — el sistema se mantiene solo${N}"
    else
      echo -e "${C}☀️  Evolve daemon ya corriendo${N}"
    fi
  fi
}

# ═══════════════════════════════════════════════════════════════════════
#  DISPATCH
# ═══════════════════════════════════════════════════════════════════════
case "${1:-help}" in
  start)          acquire_lock; start ;;
  stop)           acquire_lock; stop ;;
  restart)        acquire_lock; restart ;;
  recover)        acquire_lock; recover ;;
  status)         status ;;
  sync)           acquire_lock; sync ;;
  sync-deps)      sync_deps ;;
  sync-frontend)  sync_frontend ;;
  logs)           logs "${2:-all}" ;;
  supergate)      supergate "${2:-status}" "${3:-}" "${4:-}" ;;
  snapshot)       snapshot ;;
  verify)         verify ;;
  watchdog)       watchdog ;;
  help|--help|-h) help ;;
  *)              echo "Comando desconocido: $1"; echo ""; help; exit 1 ;;
esac
