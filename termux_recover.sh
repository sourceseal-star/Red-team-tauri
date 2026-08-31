#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# RECUPERACIÓN TERMUX — Red-team-tauri + Commander in-process
#
# Uso:
#   bash termux_recover.sh
#
# El script sincroniza ambos repositorios. Commander se integra en el dashboard
# mediante /api/commander/*; no arranca un segundo servidor ni otro puerto.
# Usa SSH por defecto para no exponer tokens en URLs, historiales ni procesos.
# Puedes sustituir ambas URLs con REDTEAM_REPO_URL y COMMANDER_REPO_URL.
# =====================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REDTEAM_REPO_DIR:-$ROOT}"
if [ -n "${COMMANDER_DIR:-}" ]; then
  COMMANDER_DIR="$COMMANDER_DIR"
elif [ -f "$REPO_DIR/commander/commander.py" ]; then
  COMMANDER_DIR="$REPO_DIR/commander"
else
  COMMANDER_DIR="$HOME/commander"
fi
REDTEAM_REPO_URL="${REDTEAM_REPO_URL:-git@github.com:sourceseal-star/Red-team-tauri.git}"
COMMANDER_REPO_URL="${COMMANDER_REPO_URL:-git@github.com:sourceseal-star/commander.git}"
PORT="${PORT:-8001}"
TERMUX_ANDROID=0
if [ -d "/data/data/com.termux" ]; then
  TERMUX_ANDROID=1
fi

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; N='\033[0m'
info() { echo -e "${C}[termux]${N} $*"; }
ok() { echo -e "${G}[  OK  ]${N} $*"; }
warn() { echo -e "${Y}[ WARN ]${N} $*"; }
die() { echo -e "${R}[ERROR ]${N} $*" >&2; exit 1; }

command -v pkg >/dev/null 2>&1 || die "Ejecuta este script dentro de Termux de F-Droid."

check_repo_clean_before_sync() {
  local repo_dir="$1"
  local repo_name="$2"
  if [ -d "$repo_dir/.git" ]; then
    if [ -n "$(git -C "$repo_dir" status --porcelain --untracked-files=all)" ]; then
      die "$repo_name tiene cambios locales sin guardar. No haré pull ni los borraré.
Usa primero 'bash arrancar_termux.sh' para trabajar con tu versión local,
o guarda esos cambios con commit/stash y vuelve a ejecutar termux_recover.sh."
    fi
  fi
}

ensure_repo_location_is_safe() {
  local repo_dir="$1"
  local repo_name="$2"
  if [ -e "$repo_dir" ] && [ ! -d "$repo_dir/.git" ]; then
    if [ -n "$(find "$repo_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
      die "$repo_name existe pero no es un repositorio Git completo: $repo_dir
No borraré sus archivos. Muévelo a una carpeta de respaldo y vuelve a ejecutar:
  mv \"$repo_dir\" \"${repo_dir}.incompleto-$(date +%Y%m%d-%H%M%S)\"
  bash termux_recover.sh"
    fi
  fi
}

ensure_repo_location_is_safe "$REPO_DIR" "Red-team-tauri"
if [ "$COMMANDER_DIR" != "$REPO_DIR/commander" ]; then
  ensure_repo_location_is_safe "$COMMANDER_DIR" "Commander"
fi
check_repo_clean_before_sync "$REPO_DIR" "Red-team-tauri"
if [ "$COMMANDER_DIR" != "$REPO_DIR/commander" ]; then
  check_repo_clean_before_sync "$COMMANDER_DIR" "Commander"
fi

echo ""
echo -e "${C}════════════════════════════════════════════════════════${N}"
echo -e "${C}  Recuperación Termux — Red-team-tauri + Commander       ${N}"
echo -e "${C}════════════════════════════════════════════════════════${N}"
echo ""

# ── 1. Paquetes nativos ──────────────────────────────────────────────────────
info "Actualizando paquetes de Termux..."
pkg update -y
pkg upgrade -y
  pkg install -y python nodejs-lts git curl openssl-tool jq sqlite nmap \
  iproute2 bind-utils whois termux-api 2>/dev/null || {
  # Algunos mirrors de Termux no contienen todos los paquetes opcionales.
  warn "Un paquete opcional no está disponible; continúo con los esenciales."
  pkg install -y python nodejs git curl openssl-tool
}
ok "Paquetes base instalados"

# ── 2. Resolver el repositorio Red-team-tauri ───────────────────────────────
if [ ! -d "$REPO_DIR/.git" ]; then
  info "Clonando Red-team-tauri en $REPO_DIR..."
  git clone "$REDTEAM_REPO_URL" "$REPO_DIR"
else
  info "Sincronizando Red-team-tauri..."
  git -C "$REPO_DIR" fetch origin
  branch="$(git -C "$REPO_DIR" branch --show-current)"
  if [ -n "$branch" ]; then
    git -C "$REPO_DIR" pull --rebase origin "$branch"
  else
    git -C "$REPO_DIR" switch -c main --track origin/main
  fi
fi
ok "Red-team-tauri sincronizado: $(git -C "$REPO_DIR" log -1 --oneline)"

# ── 3. Resolver Commander ──────────────────────────────────────────────────
if [ -f "$COMMANDER_DIR/commander.py" ]; then
  ok "Commander detectado: $COMMANDER_DIR"
elif [ -n "$COMMANDER_REPO_URL" ]; then
  if [ -d "$COMMANDER_DIR/.git" ]; then
    info "Sincronizando Commander..."
    git -C "$COMMANDER_DIR" fetch origin
    git -C "$COMMANDER_DIR" pull --rebase
  else
    info "Clonando Commander desde la URL oficial..."
    git clone "$COMMANDER_REPO_URL" "$COMMANDER_DIR"
  fi
  if [ ! -f "$COMMANDER_DIR/commander.py" ]; then
    die "Commander clonado pero no contiene commander.py: $COMMANDER_DIR"
  fi
  ok "Commander listo: $COMMANDER_DIR"
else
  die "No se pudo preparar Commander. Revisa la autenticación de GitHub en Termux."
fi

# ── 3.1 Preparar COM-LINK sin activar canales externos ─────────────────────
COMLINK_DIR="$COMMANDER_DIR/comlink"
if [ -d "$COMLINK_DIR" ] && [ -f "$COMLINK_DIR/comlink.sh" ]; then
  info "Preparando COM-LINK..."
  mkdir -p "$COMLINK_DIR/data/keys" "$COMLINK_DIR/data/logs" "$COMLINK_DIR/data/queue"
  find "$COMLINK_DIR" -type f -name "*.sh" -exec chmod u+x {} +
  command -v jq >/dev/null 2>&1 || die "jq es necesario para COM-LINK"
  command -v sqlite3 >/dev/null 2>&1 || die "sqlite3 es necesario para COM-LINK (paquete Termux: sqlite)"
  ok "COM-LINK preparado (sin iniciar SMS, radio, satélite ni mensajería)"
fi

# ── 4. Dependencias Python reales del backend ────────────────────────────────
info "Instalando dependencias Python..."
# Termux administra pip mediante el paquete python-pip; no intentar actualizarlo con pip.
PYTHON_PACKAGES=(
  fastapi uvicorn httpx pydantic aiohttp
  dnspython beautifulsoup4 python-whois requests
)
if [ "$TERMUX_ANDROID" = "1" ]; then
  warn "Android/Termux detectado: omito psutil, no compila con Python 3.14 en Android."
else
  PYTHON_PACKAGES+=(psutil)
fi
python -m pip install "${PYTHON_PACKAGES[@]}"
if [ -f "$COMMANDER_DIR/requirements.txt" ]; then
  info "Instalando dependencias de Commander..."
  python -m pip install -r "$COMMANDER_DIR/requirements.txt"
else
  python -m pip install cryptography
fi
python3 -c "import cryptography" 2>/dev/null || die "cryptography no quedó disponible para Commander"
ok "Dependencias Python listas (Red-team-tauri + Commander)"

# ── 5. Dependencias Node + build real del frontend ───────────────────────────
info "Instalando y compilando el frontend..."
(
  cd "$REPO_DIR/tauri-frontend"
  npm install --legacy-peer-deps --no-audit --no-fund
  npm run build
)
ok "Frontend compilado"

# ── 6. Configuración local sin sobrescribir secretos existentes ─────────────
ENV_FILE="$REPO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  API_KEY="$(openssl rand -hex 24)"
  cat > "$ENV_FILE" <<EOF
REDTEAM_API_KEY=$API_KEY
HOST=0.0.0.0
PORT=$PORT
ALLOWED_ORIGINS=http://localhost:$PORT,http://127.0.0.1:$PORT
EOF
  chmod 600 "$ENV_FILE"
  warn "Se creó .env con una nueva API key; quedó guardada en $ENV_FILE"
else
  ok ".env existente preservado"
fi

# ── 7. Detener solo instancias anteriores del dashboard ─────────────────────
pkill -f "redteam/scripts/dashboard_server.py" 2>/dev/null || true
sleep 1

# ── 8. Arranque real, con Commander in-process si está disponible ───────────
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export COMMANDER_DIR
export PYTHONUNBUFFERED=1

if [ -f "$COMMANDER_DIR/commander.py" ]; then
  ok "Commander se montará en /api/commander/*"
else
  warn "Commander permanecerá desactivado hasta clonar su repo correcto"
fi

info "Iniciando sistema unificado en http://127.0.0.1:$PORT ..."
cd "$REPO_DIR"
exec env COMMANDER_DIR="$COMMANDER_DIR" bash "$REPO_DIR/iniciar_unificado.sh"