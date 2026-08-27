#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# RECUPERACIÓN TERMUX — Red-team-tauri + Commander
#
# Uso:
#   bash termux_recover.sh
#   bash termux_recover.sh
#
# El script sincroniza ambos repositorios. Commander usa la URL oficial por defecto;
# puedes sustituirla por SSH con COMMANDER_REPO_URL si tu autenticación lo requiere.
# =====================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REDTEAM_REPO_DIR:-$HOME/Red-team-tauri}"
COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"
COMMANDER_REPO_URL="${COMMANDER_REPO_URL:-https://github.com/sourceseal-star/commander.git}"
PORT="${PORT:-8001}"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; N='\033[0m'
info() { echo -e "${C}[termux]${N} $*"; }
ok() { echo -e "${G}[  OK  ]${N} $*"; }
warn() { echo -e "${Y}[ WARN ]${N} $*"; }
die() { echo -e "${R}[ERROR ]${N} $*" >&2; exit 1; }

command -v pkg >/dev/null 2>&1 || die "Ejecuta este script dentro de Termux de F-Droid."

echo ""
echo -e "${C}════════════════════════════════════════════════════════${N}"
echo -e "${C}  Recuperación Termux — Red-team-tauri + Commander       ${N}"
echo -e "${C}════════════════════════════════════════════════════════${N}"
echo ""

# ── 1. Paquetes nativos ──────────────────────────────────────────────────────
info "Actualizando paquetes de Termux..."
pkg update -y
pkg upgrade -y
pkg install -y python nodejs-lts git curl openssl-tool jq nmap \
  iproute2 bind-utils whois termux-api 2>/dev/null || {
  # Algunos mirrors de Termux no contienen todos los paquetes opcionales.
  warn "Un paquete opcional no está disponible; continúo con los esenciales."
  pkg install -y python nodejs git curl openssl-tool
}
ok "Paquetes base instalados"

# ── 2. Resolver el repositorio Red-team-tauri ───────────────────────────────
if [ ! -d "$REPO_DIR/.git" ]; then
  info "Clonando Red-team-tauri en $REPO_DIR..."
  git clone https://github.com/sourceseal-star/Red-team-tauri.git "$REPO_DIR"
else
  info "Sincronizando Red-team-tauri..."
  git -C "$REPO_DIR" fetch origin
  branch="$(git -C "$REPO_DIR" branch --show-current)"
  [ -n "$branch" ] || branch="main"
  git -C "$REPO_DIR" pull --rebase origin "$branch"
fi
ok "Red-team-tauri sincronizado: $(git -C "$REPO_DIR" log -1 --oneline)"

# ── 3. Resolver Commander sin adivinar URL ──────────────────────────────────
  if [ ! -f "$COMMANDER_DIR/commander.py" ]; then
    die "Commander clonado pero no contiene commander.py: $COMMANDER_DIR"
  fi
  ok "Commander listo: $COMMANDER_DIR"
  if [ -d "$COMMANDER_DIR/.git" ]; then
    info "Sincronizando Commander..."
    git -C "$COMMANDER_DIR" fetch origin
    git -C "$COMMANDER_DIR" pull --rebase
  else
    info "Clonando Commander desde URL proporcionada..."
    git clone "$COMMANDER_REPO_URL" "$COMMANDER_DIR"
  fi
  [ -f "$COMMANDER_DIR/commander.py" ] \
    && ok "Commander listo: $COMMANDER_DIR" \
    || warn "El repo clonado no contiene commander.py; quedará desactivado."
else
  warn "Commander no está clonado."
  die "No se pudo preparar Commander. Revisa la autenticación de GitHub en Termux."
fi

# ── 4. Dependencias Python reales del backend ────────────────────────────────
info "Instalando dependencias Python..."
python -m pip install --upgrade pip
python -m pip install \
  fastapi uvicorn httpx pydantic psutil aiohttp \
  dnspython beautifulsoup4 python-whois requests
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
exec env COMMANDER_DIR="$COMMANDER_DIR" COMMANDER_PORT="${COMMANDER_PORT:-8003}" bash "$REPO_DIR/iniciar_unificado.sh"