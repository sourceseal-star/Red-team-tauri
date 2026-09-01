#!/data/data/com.termux/files/usr/bin/bash
# SourceSeal — bootstrap y actualizador seguro para Termux
#
# Uso desde el repositorio:
#   nano setup.sh
#   bash setup.sh
#
# Uso como bootstrap guardado en $HOME:
#   bash ~/setup.sh
#   bash ~/setup.sh --start
#   bash ~/setup.sh --unified
#
# El script actualiza solo mediante el sincronizador SSH del repositorio.
# No recibe comandos remotos, no ejecuta shell recibido desde Telegram y no
# hace reset sin que el sincronizador haya creado primero un respaldo/stash.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REDTEAM_REPO_URL="${REDTEAM_REPO_URL:-git@github.com:sourceseal-star/Red-team-tauri.git}"
COMMANDER_REPO_URL="${COMMANDER_REPO_URL:-git@github.com:sourceseal-star/commander.git}"

if [ -n "${REDTEAM_DIR:-}" ]; then
  REPO_DIR="$REDTEAM_DIR"
elif [ -f "$ROOT/scripts/termux/sync_repositories.sh" ]; then
  REPO_DIR="$ROOT"
else
  REPO_DIR="$HOME/Red-team-tauri"
fi
REPO_DIR="$(cd "$(dirname "$REPO_DIR")" 2>/dev/null && pwd)/$(basename "$REPO_DIR")"
COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; N='\033[0m'
info() { printf '%b[setup]%b %s\n' "$C" "$N" "$*"; }
ok() { printf '%b[  OK  ]%b %s\n' "$G" "$N" "$*"; }
warn() { printf '%b[ WARN ]%b %s\n' "$Y" "$N" "$*"; }
die() { printf '%b[ERROR ]%b %s\n' "$R" "$N" "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
SourceSeal setup.sh — Termux

  bash setup.sh          Actualiza y prepara; no inicia servidores.
  bash setup.sh --start  Actualiza, prepara y luego inicia start-termux.sh.
  bash setup.sh --unified Actualiza y luego inicia Dashboard + Commander + PHANTOM.
  bash setup.sh --watch  Actualiza y deja el watcher local en segundo plano.
  bash setup.sh --unified --watch  Hace ambas cosas con el stack unificado.

Variables opcionales:
  REDTEAM_DIR, COMMANDER_DIR, REDTEAM_REPO_URL, COMMANDER_REPO_URL
EOF
}

START_AFTER_SETUP=0
UNIFIED_AFTER_SETUP=0
WATCH_AFTER_SETUP=0
for argument in "$@"; do
  case "$argument" in
    --start) START_AFTER_SETUP=1 ;;
    --unified) UNIFIED_AFTER_SETUP=1 ;;
    --watch) WATCH_AFTER_SETUP=1 ;;
    --help|-h) usage; exit 0 ;;
    *) die "Opción no reconocida: $argument. Usa --help." ;;
  esac
done

if [ "$START_AFTER_SETUP" = "1" ] && [ "$UNIFIED_AFTER_SETUP" = "1" ]; then
  die "Usa --start o --unified, no ambos."
fi

command -v pkg >/dev/null 2>&1 || die "Ejecuta setup.sh dentro de Termux."

info "Instalando herramientas base de Termux..."
pkg update -y
pkg install -y git openssh python nodejs-lts curl openssl-tool jq sqlite nmap \
  iproute2 bind-utils whois termux-api 2>/dev/null || {
  warn "Algunos paquetes opcionales no están disponibles; instalando esenciales."
  pkg install -y git openssh python nodejs curl openssl-tool
}
ok "Herramientas base listas"

if [ ! -d "$REPO_DIR/.git" ]; then
  if [ -e "$REPO_DIR" ]; then
    die "$REPO_DIR existe pero no es un repositorio Git. No borraré sus archivos."
  fi
  info "Clonando Red-team-tauri en $REPO_DIR..."
  git clone "$REDTEAM_REPO_URL" "$REPO_DIR"
fi

SYNC_SCRIPT="$REPO_DIR/scripts/termux/sync_repositories.sh"
[ -f "$SYNC_SCRIPT" ] || die "No encuentro el sincronizador seguro: $SYNC_SCRIPT"

info "Sincronizando Red-team-tauri y Commander con respaldo..."
REDTEAM_DIR="$REPO_DIR" \
COMMANDER_DIR="$COMMANDER_DIR" \
REDTEAM_REPO_URL="$REDTEAM_REPO_URL" \
COMMANDER_REPO_URL="$COMMANDER_REPO_URL" \
  bash "$SYNC_SCRIPT"
ok "Repositorios actualizados"

info "Instalando dependencias Python declaradas..."
PYTHON_PACKAGES=(fastapi uvicorn httpx pydantic aiohttp dnspython beautifulsoup4 python-whois requests)
if [ -d "/data/data/com.termux" ]; then
  warn "Android/Termux detectado: omito psutil, que puede no tener wheel para Python 3.14."
else
  PYTHON_PACKAGES+=(psutil)
fi
python3 -m pip install --disable-pip-version-check "${PYTHON_PACKAGES[@]}"
ok "Dependencias Python listas"

info "Verificando AI Orchestrator en Commander..."
if [ -f "$COMMANDER_DIR/ai_orchestrator.py" ]; then
  ok "AI Orchestrator encontrado en $COMMANDER_DIR"
  if [ -f "$COMMANDER_DIR/seal_ia_knowledge.py" ]; then
    ok "Seal IA Knowledge encontrado"
  else
    warn "seal_ia_knowledge.py no encontrado en Commander — intel de IA limitada"
  fi
else
  warn "AI Orchestrator no encontrado en $COMMANDER_DIR"
  warn "Endpoints /api/commander/ai/* quedaran desactivados"
fi


info "Instalando dependencias y compilando el frontend..."
(
  cd "$REPO_DIR/tauri-frontend"
  if [ ! -d node_modules ] || [ ! -e node_modules/vis-network ] || [ ! -e node_modules/leaflet ]; then
    npm install --legacy-peer-deps --no-audit --no-fund
  fi
  npm run build
)
ok "Frontend compilado"

if [ ! -f "$REPO_DIR/redteam/monitor/operations_monitor.py" ]; then
  die "La actualización no contiene el monitor seguro esperado."
fi
ok "Monitor seguro verificado"
python3 -m py_compile \
  "$REPO_DIR/watcher.py" \
  "$REPO_DIR/redteam/runner/hot_loader.py" \
  "$REPO_DIR/redteam/runner/engagement_guard.py" \
  "$REPO_DIR/redteam/modules/base.py"
ok "Watcher y componentes de alcance verificados"

printf '\n'
info "Actualización terminada: $(git -C "$REPO_DIR" log -1 --oneline)"
info "Ejecución separada: bash \"$REPO_DIR/start-termux.sh\""

if [ "$WATCH_AFTER_SETUP" = "1" ]; then
  WATCH_STATE_DIR="${SOURCESEAL_STATE_DIR:-$HOME/.sourceseal}"
  WATCH_PID_FILE="$WATCH_STATE_DIR/watcher.pid"
  WATCH_LOG="$WATCH_STATE_DIR/watcher.log"
  mkdir -p "$WATCH_STATE_DIR"
  WATCH_PID=""
  if [ -f "$WATCH_PID_FILE" ]; then
    WATCH_PID="$(cat "$WATCH_PID_FILE" 2>/dev/null || true)"
  fi
  WATCH_COMMAND=""
  if [[ "$WATCH_PID" =~ ^[0-9]+$ ]] && kill -0 "$WATCH_PID" 2>/dev/null; then
    WATCH_COMMAND="$(ps -p "$WATCH_PID" -o args= 2>/dev/null || true)"
  fi
  if [[ "$WATCH_COMMAND" == *"$REPO_DIR/watcher.py"* ]]; then
    ok "Watcher ya estaba activo (PID $WATCH_PID)"
  else
    rm -f "$WATCH_PID_FILE"
    SOURCESEAL_STATE_DIR="$WATCH_STATE_DIR" \
      nohup python3 "$REPO_DIR/watcher.py" >"$WATCH_LOG" 2>&1 </dev/null &
    echo "$!" > "$WATCH_PID_FILE"
    ok "Watcher iniciado (PID $(cat "$WATCH_PID_FILE")); log: $WATCH_LOG"
  fi
fi

if [ "$UNIFIED_AFTER_SETUP" = "1" ]; then
  info "Iniciando stack unificado porque se indicó --unified..."
  exec env COMMANDER_DIR="$COMMANDER_DIR" bash "$REPO_DIR/iniciar_unificado.sh"
fi

if [ "$START_AFTER_SETUP" = "1" ]; then
  info "Iniciando SourceSeal porque se indicó --start..."
  exec bash "$REPO_DIR/start-termux.sh"
fi