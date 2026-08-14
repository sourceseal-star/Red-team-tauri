#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# UPDATE.SH — Sistema de actualización para Red-Team-Tauri
# Equivalente a "actualizar la app" — pulsa cambios, reinstala deps si
# cambiaron, reinicia servicios. No relee todo el repo.
#
# Uso:
#   bash update.sh              # actualiza desde la branch actual
#   bash update.sh --main       # cambia a main y actualiza
#   bash update.sh --branch X    # actualiza desde branch X
#   bash update.sh --deps        # fuerza reinstalación de dependencias
#   bash update.sh --build       # fuerza rebuild del frontend
#   bash update.sh --all         # --deps + --build + restart completo
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

# Colors
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'

# Parse args
TARGET_BRANCH=""
FORCE_DEPS=false
FORCE_BUILD=false
FULL_RESTART=false

for arg in "$@"; do
    case "$arg" in
        --main)     TARGET_BRANCH="main" ;;
        --branch)   shift; TARGET_BRANCH="$1" ;;
        --deps)     FORCE_DEPS=true ;;
        --build)    FORCE_BUILD=true ;;
        --all)      FORCE_DEPS=true; FORCE_BUILD=true; FULL_RESTART=true ;;
        --help|-h)
            echo "Uso: bash update.sh [--main | --branch X] [--deps] [--build] [--all]"
            echo ""
            echo "  (sin args)  Actualiza desde la branch actual"
            echo "  --main      Cambia a main y actualiza"
            echo "  --branch X  Actualiza desde branch X"
            echo "  --deps      Fuerza reinstalación de dependencias"
            echo "  --build     Fuerza rebuild del frontend (npm run build)"
            echo "  --all       --deps + --build + restart completo"
            exit 0
            ;;
    esac
done

echo ""
echo -e "${B}╔══════════════════════════════════════════════╗${N}"
echo -e "${B}║  RED-TEAM-TAURI · UPDATE                      ║${N}"
echo -e "${B}╚══════════════════════════════════════════════╝${N}"
echo ""

# ── 1. GUARDAR HASHES DE DEPS ANTES DEL PULL ──────────────────────
DASHBOARD_REQ_BEFORE=$(mdsum redteam/scripts/requirements.txt 2>/dev/null || echo "")
BACKEND_REQ_BEFORE=$(mdsum backend/requirements.txt 2>/dev/null || echo "")
MOTOR_REQ_BEFORE=$(mdsum motor_cierre/backend/requirements.txt 2>/dev/null || echo "")
FRONTEND_PKG_BEFORE=$(mdsum tauri-frontend/package.json 2>/dev/null || echo "")
TERMUX_SCRIPT_BEFORE=$(mdsum start-termux.sh 2>/dev/null || echo "")

mdsum() {
    if [ -f "$1" ]; then
        md5sum "$1" | cut -d' ' -f1
    else
        echo ""
    fi
}

# Re-declare after function definition (bash quirk)
DASHBOARD_REQ_BEFORE=$(mdsum redteam/scripts/requirements.txt)
BACKEND_REQ_BEFORE=$(mdsum backend/requirements.txt)
MOTOR_REQ_BEFORE=$(mdsum motor_cierre/backend/requirements.txt)
FRONTEND_PKG_BEFORE=$(mdsum tauri-frontend/package.json)
TERMUX_SCRIPT_BEFORE=$(mdsum start-termux.sh)

# ── 2. GIT PULL ───────────────────────────────────────────────────
if [ -n "$TARGET_BRANCH" ]; then
    echo -e "${C}→ Cambiando a branch: $TARGET_BRANCH${N}"
    git checkout "$TARGET_BRANCH" 2>/dev/null || {
        echo -e "${R}✗ No se pudo cambiar a branch $TARGET_BRANCH${N}"
        exit 1
    }
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo -e "${C}→ Branch actual: $CURRENT_BRANCH${N}"
echo -e "${C}→ Haciendo git pull...${N}"

git pull origin "$CURRENT_BRANCH" 2>&1 | while read -r line; do
    echo "  $line"
done

NEW_HEAD=$(git rev-parse --short HEAD)
echo -e "${G}✓ HEAD: $NEW_HEAD${N}"

# ── 3. MOSTRAR QUÉ CAMBIÓ ─────────────────────────────────────────
COMMITS_AHEAD=$(git log --oneline -5 2>/dev/null | head -5)
if [ -n "$COMMITS_AHEAD" ]; then
    echo ""
    echo -e "${Y}Commits recientes:${N}"
    echo "$COMMITS_AHEAD" | while read -r line; do
        echo "  $line"
    done
fi

# ── 4. DETECTAR SI LAS DEPS CAMBIARON ─────────────────────────────
DASHBOARD_REQ_AFTER=$(mdsum redteam/scripts/requirements.txt)
BACKEND_REQ_AFTER=$(mdsum backend/requirements.txt)
MOTOR_REQ_AFTER=$(mdsum motor_cierre/backend/requirements.txt)
FRONTEND_PKG_AFTER=$(mdsum tauri-frontend/package.json)
TERMUX_SCRIPT_AFTER=$(mdsum start-termux.sh)

DEPS_CHANGED=false
BUILD_NEEDED=false

if [ "$DASHBOARD_REQ_BEFORE" != "$DASHBOARD_REQ_AFTER" ] || [ "$FORCE_DEPS" = true ]; then
    echo ""
    echo -e "${Y}→ Deps del dashboard cambiaron. Reinstalando...${N}"
    pip install -q fastapi uvicorn httpx psutil aiohttp 2>/dev/null || true
    pip install -q -r redteam/scripts/requirements.txt 2>/dev/null || true
    DEPS_CHANGED=true
fi

if [ "$MOTOR_REQ_BEFORE" != "$MOTOR_REQ_AFTER" ] || [ "$FORCE_DEPS" = true ]; then
    echo ""
    echo -e "${Y}→ Deps del Motor de Cierre cambiaron. Reinstalando...${N}"
    pip install -q fastapi uvicorn "pydantic[email]" slowapi tenacity 2>/dev/null || true
    DEPS_CHANGED=true
fi

if [ "$FRONTEND_PKG_BEFORE" != "$FRONTEND_PKG_AFTER" ] || [ "$FORCE_DEPS" = true ]; then
    echo ""
    echo -e "${Y}→ package.json del frontend cambió. npm install...${N}"
    cd "$ROOT/tauri-frontend"
    npm install 2>&1 | tail -5
    cd "$ROOT"
    BUILD_NEEDED=true
fi

if [ "$TERMUX_SCRIPT_BEFORE" != "$TERMUX_SCRIPT_AFTER" ]; then
    echo ""
    echo -e "${Y}⚠ start-termux.sh cambió. Considera reiniciar con: bash start-termux.sh${N}"
fi

# ── 5. BUILD DEL FRONTEND (si es necesario) ──────────────────────
if [ "$BUILD_NEEDED" = true ] || [ "$FORCE_BUILD" = true ]; then
    echo ""
    echo -e "${C}→ Build del frontend...${N}"
    cd "$ROOT/tauri-frontend"
    npm run build 2>&1 | tail -5
    cd "$ROOT"
    echo -e "${G}✓ Frontend buildado${N}"
fi

# ── 6. RESTART DE SERVICIOS ──────────────────────────────────────
# Detectar si los servicios están corriendo
DASHBOARD_PID=$(pgrep -f "dashboard_server.py" 2>/dev/null | head -1)
MOTOR_PID=$(pgrep -f "uvicorn.*main:app.*8000" 2>/dev/null | head -1)
VITE_PID=$(pgrep -f "vite" 2>/dev/null | head -1)

RESTART_NEEDED=false

if [ "$DEPS_CHANGED" = true ] || [ "$FULL_RESTART" = true ]; then
    RESTART_NEEDED=true
fi

if [ "$RESTART_NEEDED" = true ]; then
    echo ""
    echo -e "${Y}→ Reiniciando servicios...${N}"

    # Dashboard backend (8001)
    if [ -n "$DASHBOARD_PID" ]; then
        echo -e "  ${C}Reiniciando dashboard backend (:8001)...${N}"
        pkill -f "dashboard_server.py" 2>/dev/null || true
        sleep 1
        cd "$ROOT/redteam/scripts"
        export PORT=8001 HOST=0.0.0.0
        python3 dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
        echo -e "  ${G}✓ Dashboard backend reiniciado (PID: $!)${N}"
        cd "$ROOT"
    fi

    # Motor de Cierre (8000)
    if [ -n "$MOTOR_PID" ]; then
        echo -e "  ${C}Reiniciando Motor de Cierre (:8000)...${N}"
        pkill -f "uvicorn.*main:app.*8000" 2>/dev/null || true
        sleep 1
        cd "$ROOT/motor_cierre/backend"
        python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/motor_cierre.log" 2>&1 &
        echo -e "  ${G}✓ Motor de Cierre reiniciado (PID: $!)${N}"
        cd "$ROOT"
    fi

    # Vite frontend (5173) — solo si full restart
    if [ "$FULL_RESTART" = true ] && [ -n "$VITE_PID" ]; then
        echo -e "  ${C}Reiniciando Vite (:5173)...${N}"
        pkill -f "vite" 2>/dev/null || true
        sleep 1
        cd "$ROOT/tauri-frontend"
        npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
        echo -e "  ${G}✓ Vite reiniciado (PID: $!)${N}"
        cd "$ROOT"
    fi

    sleep 3
else
    echo ""
    echo -e "${G}✓ Sin cambios en deps — servicios continúan corriendo${N}"
    echo -e "  (uvicorn --reload detecta cambios automáticamente)"
    echo -e "  Si tienes problemas, usa: bash update.sh --all"
fi

# ── 7. HEALTH CHECK ──────────────────────────────────────────────
echo ""
echo -e "${C}→ Health check...${N}"

check_health() {
    local name="$1"
    local url="$2"
    local expected="$3"
    local retries=5
    for i in $(seq 1 $retries); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo -e "  ${G}✓ $name: OK ($HTTP_CODE)${N}"
            return 0
        fi
        sleep 1
    done
    echo -e "  ${R}✗ $name: NO RESPONDE (último HTTP: $HTTP_CODE)${N}"
    return 1
}

if [ -n "$DASHBOARD_PID" ] || [ "$RESTART_NEEDED" = true ]; then
    check_health "Dashboard :8001" "http://127.0.0.1:8001/api/health" "200"
fi

if [ -n "$MOTOR_PID" ] || [ "$RESTART_NEEDED" = true ]; then
    check_health "Motor Cierre :8000" "http://127.0.0.1:8000/health" "200"
fi

if [ -n "$VITE_PID" ]; then
    check_health "Vite :5173" "http://127.0.0.1:5173" "200"
fi

# ── 8. RESUMEN ───────────────────────────────────────────────────
echo ""
echo -e "${B}╔══════════════════════════════════════════════╗${N}"
echo -e "${B}║  UPDATE COMPLETO                              ║${N}"
echo -e "${B}╠══════════════════════════════════════════════╣${N}"
echo -e "${B}║  Branch: $CURRENT_BRANCH                        ║${N}"
echo -e "${B}║  HEAD:   $NEW_HEAD                       ║${N}"
echo -e "${B}║  Deps:   $([ "$DEPS_CHANGED" = true ] && echo "reinstaladas" || echo "sin cambios")              ║${N}"
echo -e "${B}║  Build:  $([ "$BUILD_NEEDED" = true ] && echo "ejecutado" || echo "sin cambios")                 ║${N}"
echo -e "${B}╚══════════════════════════════════════════════╝${N}"
echo ""
echo -e "  Logs: tail -f $LOG_DIR/backend.log"
echo -e "        tail -f $LOG_DIR/motor_cierre.log"
echo -e "        tail -f $LOG_DIR/frontend.log"
echo ""
echo -e "  Frontend: http://localhost:5173"
echo -e "  Backend:  http://localhost:8001"
echo -e "  Motor:    http://localhost:8000"
echo ""
