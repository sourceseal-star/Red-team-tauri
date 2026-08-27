#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# DEPLOY.SH — Despliegue completo desde cero en Termux
# Hace TODO: paquetes → repo → deps → build → arranque → watchdog
#
# Uso:
#   bash deploy.sh              # despliegue completo + watchdog
#   bash deploy.sh --no-watch   # despliegue completo sin watchdog
#   bash deploy.sh --update     # git pull + deps + restart (como update.sh)
#   bash deploy.sh --fresh      # borra node_modules y venv, empieza limpio
# =====================================================================
set -e

# ── COLORES ──────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'
BOLD='\033[1m'

# ── CONFIG ────────────────────────────────────────────────────────
REPO_URL="https://github.com/sourceseal-star/Red-team-tauri.git"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCH="main"
LOG_DIR="$REPO_DIR/logs"
mkdir -p "$LOG_DIR"

# Parse args
WATCH=true
FRESH=false
UPDATE_ONLY=false
for arg in "$@"; do
    case "$arg" in
        --no-watch) WATCH=false ;;
        --fresh)    FRESH=true ;;
        --update)   UPDATE_ONLY=true ;;
        --help|-h)
            echo "Uso: bash deploy.sh [--no-watch] [--fresh] [--update]"
            echo ""
            echo "  (sin args)   Despliegue completo + watchdog activo"
            echo "  --no-watch   Despliegue completo sin watchdog (sale al terminar)"
            echo "  --update    Solo git pull + deps + restart (no instala paquetes)"
            echo "  --fresh     Borra node_modules y reinstala todo limpio"
            exit 0
            ;;
    esac
done

# ── HELPERS ──────────────────────────────────────────────────────
step() { echo ""; echo -e "${B}▶ $1${N}"; }
ok()   { echo -e "  ${G}✓ $1${N}"; }
fail() { echo -e "  ${R}✗ $1${N}"; }
warn() { echo -e "  ${Y}⚠ $1${N}"; }
info() { echo -e "  ${C}$1${N}"; }

check_health() {
    local name="$1" url="$2" retries="${3:-15}"
    echo -n "  Esperando $name"
    for i in $(seq 1 "$retries"); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo " ${G}OK${N}"
            return 0
        fi
        sleep 1
        echo -n "."
    done
    echo " ${R}TIMEOUT${N}"
    return 1
}

# ═════════════════════════════════════════════════════════════════════
#  FASE 0: WAKE LOCK (evita que Android suspenda Termux)
# ═════════════════════════════════════════════════════════════════════
step "FASE 0 · Termux Wake Lock"
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
    ok "Wake lock activo — Android no suspenderá Termux"
else
    warn "termux-wake-lock no disponible (instala: pkg install termux-api)"
fi

# ═════════════════════════════════════════════════════════════════════
#  FASE 1: PAQUETES BASE DE TERMUX (solo si no es --update)
# ═════════════════════════════════════════════════════════════════════
if [ "$UPDATE_ONLY" = false ]; then
    step "FASE 1 · Paquetes base de Termux"

    # Actualizar repositorios de Termux
    info "Actualizando repositorios..."
    pkg update -y >/dev/null 2>&1 || true

    # Lista de paquetes necesarios
    PACKAGES=(
        python python-pip
        nodejs
        git
        curl
        openssh
        termux-api
        nmap
        jq
        sqlite
    )

    # Verificar e instalar cada paquete
    for pkg in "${PACKAGES[@]}"; do
        if command -v "$pkg" >/dev/null 2>&1 || dpkg -s "$pkg" >/dev/null 2>&1; then
            echo -e "  ${G}✓${N} $pkg ya instalado"
        else
            echo -e "  ${C}→${N} Instalando $pkg..."
            pkg install -y "$pkg" >/dev/null 2>&1 && ok "$pkg" || warn "$pkg falló (puede no ser crítico)"
        fi
    done

    ok "Paquetes base listos"
fi

# ═════════════════════════════════════════════════════════════════════
#  FASE 2: REPOSITORIO (clonar o actualizar)
# ═════════════════════════════════════════════════════════════════════
step "FASE 2 · Repositorio"

cd "$REPO_DIR"

if [ -d "$REPO_DIR/.git" ]; then
    # Ya existe el repo — hacer pull
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
    info "Repo ya existe (branch: $CURRENT_BRANCH)"
    info "Haciendo git pull..."
    git pull origin "$CURRENT_BRANCH" 2>&1 | while read -r line; do echo "  $line"; done
    NEW_HEAD=$(git rev-parse --short HEAD)
    ok "Actualizado a $NEW_HEAD"
else
    # Clonar el repo
    info "Clonando repo..."
    cd "$(dirname "$REPO_DIR")"
    git clone "$REPO_URL" "$(basename "$REPO_DIR")" 2>&1 | while read -r line; do echo "  $line"; done
    cd "$REPO_DIR"
    git checkout "$BRANCH" 2>/dev/null || true
    ok "Repo clonado en $REPO_DIR"
fi

NEW_HEAD=$(git rev-parse --short HEAD)
info "HEAD: $NEW_HEAD"

# ═════════════════════════════════════════════════════════════════════
#  FASE 3: DEPENDENCIAS PYTHON
# ═════════════════════════════════════════════════════════════════════
step "FASE 3 · Dependencias Python"

# Deps del dashboard
info "Instalando deps del dashboard..."
pip install -q fastapi uvicorn httpx psutil aiohttp 2>/dev/null || true
pip install -q -r "$REPO_DIR/redteam/scripts/requirements.txt" 2>/dev/null || true
ok "Dashboard deps OK"

# Deps del Motor de Cierre
info "Instalando deps del Motor de Cierre..."
pip install -q fastapi uvicorn "pydantic[email]" slowapi tenacity 2>/dev/null || true
pip install -q -r "$REPO_DIR/motor_cierre/backend/requirements.txt" 2>/dev/null || true
ok "Motor de Cierre deps OK"

# ═════════════════════════════════════════════════════════════════════
#  FASE 4: FRONTEND (Node + Vite)
# ═════════════════════════════════════════════════════════════════════
step "FASE 4 · Frontend (Node + Vite)"

cd "$REPO_DIR/tauri-frontend"

if [ "$FRESH" = true ] && [ -d "node_modules" ]; then
    warn "Modo --fresh: borrando node_modules..."
    rm -rf node_modules
fi

if [ ! -d "node_modules" ] || [ "$FRESH" = true ]; then
    info "npm install (puede tardar un par de minutos)..."
    npm install 2>&1 | tail -5
    ok "Node deps instaladas"
else
    ok "node_modules ya existe (usa --fresh para reinstalar)"
fi

# Build de producción (opcional — Vite dev server no lo necesita,
# pero sirve si quieres servir archivos estáticos desde el backend)
if [ ! -d "dist" ] || [ "$FRESH" = true ]; then
    info "Build del frontend..."
    npm run build 2>&1 | tail -5
    ok "Build completo"
else
    ok "dist/ ya existe (usa --fresh para rebuild)"
fi

cd "$REPO_DIR"

# ═════════════════════════════════════════════════════════════════════
#  FASE 5: CONFIGURACIÓN (.env)
# ═════════════════════════════════════════════════════════════════════
step "FASE 5 · Configuración"

# Motor de Cierre .env
MOTOR_ENV="$REPO_DIR/motor_cierre/backend/.env"
if [ ! -f "$MOTOR_ENV" ]; then
    if [ -f "$REPO_DIR/motor_cierre/backend/.env.example" ]; then
        cp "$REPO_DIR/motor_cierre/backend/.env.example" "$MOTOR_ENV"
        ok ".env creado desde .env.example (Motor de Cierre)"
    else
        warn "No hay .env.example para Motor de Cierre — creando básico..."
        cat > "$MOTOR_ENV" << 'ENVEOF'
# Motor de Cierre — configuración
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
ENVEOF
        ok ".env básico creado (Motor de Cierre)"
    fi
else
    ok ".env ya existe (Motor de Cierre)"
fi

# Dashboard .env si existe
DASH_ENV="$REPO_DIR/redteam/scripts/.env"
if [ ! -f "$DASH_ENV" ]; then
    cat > "$DASH_ENV" << 'ENVEOF'
# Dashboard Backend — configuración
HOST=0.0.0.0
PORT=8001
ENVEOF
    ok ".env creado (Dashboard)"
else
    ok ".env ya existe (Dashboard)"
fi

# ═════════════════════════════════════════════════════════════════════
#  FASE 6: MATAR PROCESOS ANTERIORES
# ═════════════════════════════════════════════════════════════════════
step "FASE 6 · Limpiando procesos anteriores"

pkill -f "dashboard_server.py" 2>/dev/null && warn "Dashboard anterior matado" || ok "Sin dashboard previo"
pkill -f "uvicorn.*main:app.*8000" 2>/dev/null && warn "Motor anterior matado" || ok "Sin motor previo"
pkill -f "vite" 2>/dev/null && warn "Vite anterior matado" || ok "Sin vite previo"

sleep 2
ok "Limpieza completa"

# ═════════════════════════════════════════════════════════════════════
#  FASE 7: ARRANQUE DE SERVICIOS EN ORDEN
# ═════════════════════════════════════════════════════════════════════
echo ""
echo -e "${B}╔══════════════════════════════════════════════╗${N}"
echo -e "${B}║  ARRANCANDO SERVICIOS                         ║${N}"
echo -e "${B}╚══════════════════════════════════════════════╝${N}"

# ── 7.1 Dashboard Backend (:8001) ──
step "7.1 · Dashboard Backend (:8001)"
cd "$REPO_DIR/redteam/scripts"
export PORT=8001 HOST=0.0.0.0
python3 dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
DASH_PID=$!
info "PID: $DASH_PID"
check_health "Dashboard" "http://127.0.0.1:8001/api/health" 20 || {
    fail "Dashboard no arrancó. Últimas líneas del log:"
    tail -20 "$LOG_DIR/backend.log"
    echo ""
    warn "Continuando con los demás servicios..."
    DASH_PID=""
}
cd "$REPO_DIR"

# ── 7.2 Motor de Cierre (:8000) ──
step "7.2 · Motor de Cierre (:8000)"
cd "$REPO_DIR/motor_cierre/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/motor_cierre.log" 2>&1 &
MOTOR_PID=$!
info "PID: $MOTOR_PID"
check_health "Motor de Cierre" "http://127.0.0.1:8000/health" 15 || {
    fail "Motor de Cierre no arrancó. Log:"
    tail -15 "$LOG_DIR/motor_cierre.log"
    warn "Continuando sin Motor de Cierre..."
    MOTOR_PID=""
}
cd "$REPO_DIR"

# ── 7.3 Vite Frontend (:5173) ──
step "7.3 · Vite Frontend (:5173)"
cd "$REPO_DIR/tauri-frontend"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
VITE_PID=$!
info "PID: $VITE_PID"
check_health "Vite" "http://127.0.0.1:5173" 20 || {
    fail "Vite no arrancó. Log:"
    tail -15 "$LOG_DIR/frontend.log"
    warn "Continuando sin frontend..."
    VITE_PID=""
}
cd "$REPO_DIR"

# ═════════════════════════════════════════════════════════════════════
#  FASE 8: RESUMEN
# ═════════════════════════════════════════════════════════════════════
echo ""
echo -e "${B}╔══════════════════════════════════════════════╗${N}"
echo -e "${B}║  DESPLIEGUE COMPLETO                          ║${N}"
echo -e "${B}╠══════════════════════════════════════════════╣${N}"
echo -e "${B}║  Repo:   $NEW_HEAD                          ║${N}"
echo -e "${B}║                                              ║${N}"
[ -n "$DASH_PID" ]  && echo -e "${B}║  Dashboard :8001  ${G}● ONLINE${B}  PID $DASH_PID        ║${N}"  || echo -e "${B}║  Dashboard :8001  ${R}✗ OFFLINE${B}                  ║${N}"
[ -n "$MOTOR_PID" ] && echo -e "${B}║  Motor    :8000  ${G}● ONLINE${B}  PID $MOTOR_PID        ║${N}" || echo -e "${B}║  Motor    :8000  ${R}✗ OFFLINE${B}                  ║${N}"
[ -n "$VITE_PID" ]  && echo -e "${B}║  Vite     :5173  ${G}● ONLINE${B}  PID $VITE_PID        ║${N}"  || echo -e "${B}║  Vite     :5173  ${R}✗ OFFLINE${B}                  ║${N}"
echo -e "${B}╠══════════════════════════════════════════════╣${N}"
echo -e "${B}║  Frontend: http://localhost:5173              ║${N}"
echo -e "${B}║  Backend:  http://localhost:8001              ║${N}"
echo -e "${B}║  Motor:    http://localhost:8000              ║${N}"
echo -e "${B}╠══════════════════════════════════════════════╣${N}"
echo -e "${B}║  Logs: $LOG_DIR/                    ${N}"
echo -e "${B}║    backend.log · motor_cierre.log            ║${N}"
echo -e "${B}║    frontend.log · watchdog.log               ║${N}"
echo -e "${B}╚══════════════════════════════════════════════╝${N}"
echo ""

# ═════════════════════════════════════════════════════════════════════
#  FASE 9: WATCHDOG (vigilancia permanente)
# ═════════════════════════════════════════════════════════════════════
if [ "$WATCH" = true ]; then
    echo -e "${B}▶ WATCHDOG ACTIVO — Ctrl+C para salir${N}"
    echo -e "  Vigilando los 3 servicios cada 10s"
    echo -e "  Los servicios siguen corriendo en background aunque salgas${N}"
    echo ""

    WATCH_LOG="$LOG_DIR/watchdog.log"
    echo "[$(date '+%F %T')] Watchdog iniciado" >> "$WATCH_LOG"

    cleanup() {
        echo ""
        echo -e "${Y}Watchdog detenido — los servicios siguen corriendo${N}"
        exit 0
    }
    trap cleanup SIGINT SIGTERM

    while true; do
        # Dashboard
        if [ -n "$DASH_PID" ] && ! kill -0 "$DASH_PID" 2>/dev/null; then
            MSG="[$(date '+%F %T')] Dashboard caído — reiniciando"
            echo -e "${R}$MSG${N}"
            echo "$MSG" >> "$WATCH_LOG"
            cd "$REPO_DIR/redteam/scripts"
            export PORT=8001 HOST=0.0.0.0
            python3 dashboard_server.py >> "$LOG_DIR/backend.log" 2>&1 &
            DASH_PID=$!
            cd "$REPO_DIR"
        fi

        # Motor de Cierre
        if [ -n "$MOTOR_PID" ] && ! kill -0 "$MOTOR_PID" 2>/dev/null; then
            MSG="[$(date '+%F %T')] Motor de Cierre caído — reiniciando"
            echo -e "${R}$MSG${N}"
            echo "$MSG" >> "$WATCH_LOG"
            cd "$REPO_DIR/motor_cierre/backend"
            python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 >> "$LOG_DIR/motor_cierre.log" 2>&1 &
            MOTOR_PID=$!
            cd "$REPO_DIR"
        fi

        # Vite
        if [ -n "$VITE_PID" ] && ! kill -0 "$VITE_PID" 2>/dev/null; then
            MSG="[$(date '+%F %T')] Vite caído — reiniciando"
            echo -e "${R}$MSG${N}"
            echo "$MSG" >> "$WATCH_LOG"
            cd "$REPO_DIR/tauri-frontend"
            npm run dev >> "$LOG_DIR/frontend.log" 2>&1 &
            VITE_PID=$!
            cd "$REPO_DIR"
        fi

        sleep 10
    done
else
    echo -e "${G}✓ Despliegue completo (sin watchdog)${N}"
    echo -e "  Para vigilar: bash update.sh --watch"
fi
