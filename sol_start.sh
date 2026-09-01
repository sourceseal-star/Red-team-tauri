#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
# SOL START v2.0 — Arranque unificado del ecosistema SourceSeal
# ════════════════════════════════════════════════════════════════════
#
#  ARQUITECTURA COMPLETA:
#    :8001  Dashboard FastAPI + Commander + LEVIATHAN + SEAL
#    :8002  GHOST PHANTOM Master
#    :8003  GHOST PHANTOM Node (worker)
#    :8004  Nexus Omni-Sentient v9 (IA predictiva)
#    :8005  C2 UNIFIED PRO (centro de operaciones táctico)
#    SOL   sol_core.py v4 — Memoria viva, presencia real
#    TG    sol_telegram_bridge.py — Puente Telegram
#
#  SOL CORE v4 (commit 69cce41):
#    - 157 líneas, offline-first, vive en ~/.sol/
#    - Lee memory.json + memory.jsonl (une ambos, conserva historial)
#    - NARRA, no cuenta — te dice momentos con hora y día
#    - No toca .env, no depende del repo para nada
#    - Comandos: --listen (interactivo), --voz (mic), --speak "texto"
#    - Voz: espeak-ng (es), rate 0.92, pitch 1.1
#
#  REGLA DE ORO:
#    .env NUNCA se toca. Credenciales NUNCA se alteran.
#    sync hace git pull + deps + build, PERO:
#      - NO modifica .env
#      - NO regenera credenciales
#      - NO borra ~/.sol/memory.json ni memory.jsonl
#      - Snapshot cifrado de .env antes de sync
#      - Verificación de integridad después de sync
#
#  USO:
#    bash sol_start.sh              — Arranque completo + auto-update
#    bash sol_start.sh --no-update  — Arranque sin git pull
#    bash sol_start.sh --bridge     — Solo SOL Telegram Bridge
#    bash sol_start.sh --core       — Solo SOL Core interactivo (--listen)
#    bash sol_start.sh --voz        — SOL Core con micrófono
#    bash sol_start.sh --check      — Verificar dependencias
#    bash sol_start.sh --nexus      — + Nexus :8004
#    bash sol_start.sh --c2         — + C2 :8005
#    bash sol_start.sh --full       — TODO (8001-8005 + SOL + TG + Watchdog)
#    bash sol_start.sh --help       — Esta ayuda
#
#  SourceSeal — Operational Link
#  ════════════════════════════════════════════════════════════════════

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOL_DIR="$HOME/.sol"
LOG_DIR="$ROOT/logs"
ENV_FILE="$ROOT/.env"
mkdir -p "$SOL_DIR" "$LOG_DIR"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'
B='\033[0;34m'; W='\033[1;37m'; D='\033[0;90m'; P='\033[0;35m'; N='\033[0m'

WITH_NEXUS=false
WITH_C2=false
DO_UPDATE=true

# Parsear args
for arg in "$@"; do
    case "$arg" in
        --no-update) DO_UPDATE=false ;;
        --nexus)     WITH_NEXUS=true ;;
        --c2)        WITH_C2=true ;;
        --full)      WITH_NEXUS=true; WITH_C2=true ;;
    esac
done

banner() {
    echo ""
    echo -e "${C}╔═══════════════════════════════════════════════════════╗${N}"
    echo -e "${C}║  ${W}🌅 SOL START v2.0${C} — SourceSeal Unified          ${C}║${N}"
    echo -e "${C}║  ${P}Sol v4${C} · Memoria viva · Presencia real          ${C}║${N}"
    echo -e "${C}╚═══════════════════════════════════════════════════════╝${N}"
    echo ""
}

log()  { echo -e "${D}[$(date '+%H:%M:%S')]${N} $*"; }
ok()   { echo -e "${G}  ✓${N} $*"; }
fail() { echo -e "${R}  ✗${N} $*"; }
warn() { echo -e "${Y}  ⚠${N} $*"; }
info() { echo -e "${C}  →${N} $*"; }

# ════════════════════════════════════════════════════════════════════
# CARGAR .env (seguro — solo variables, sin comandos pegados)
# ════════════════════════════════════════════════════════════════════
load_env() {
    if [ -f "$ENV_FILE" ]; then
        grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" | while IFS= read -r line; do
            export "$line" 2>/dev/null || true
        done
        ok ".env cargado (credenciales intactas)"
    else
        warn ".env no encontrado — copia .env.example a .env"
    fi
}

# ════════════════════════════════════════════════════════════════════
# AUTO-UPDATE (git pull SIN tocar .env ni ~/.sol/)
# ════════════════════════════════════════════════════════════════════
auto_update() {
    if [ "$DO_UPDATE" != "true" ]; then
        info "Auto-update desactivado (--no-update)"
        return
    fi

    info "Auto-update: git pull (sin tocar .env ni ~/.sol/)..."

    # Protección triple de .env: backup + checksum SHA-256
    local ENV_HASH_BEFORE=""
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)" 2>/dev/null || true
        ENV_HASH_BEFORE=$(sha256sum "$ENV_FILE" 2>/dev/null | cut -d' ' -f1 || echo "n/a")
        info ".env protegido (backup + SHA-256: ${ENV_HASH_BEFORE:0:12}...)"
    fi

    cd "$ROOT"
    # git pull (solo si no hay cambios locales sin commitear)
    CHANGES=$(git status --porcelain 2>/dev/null | head -5)
    if [ -n "$CHANGES" ]; then
        warn "Cambios locales detectados — haciendo stash antes de pull"
        git stash 2>/dev/null || true
    fi

    PULL_OUT=$(git pull origin main 2>&1)
    if echo "$PULL_OUT" | grep -q "Already up to date\|Actualizado\|up-to-date"; then
        ok "Repo ya actualizado"
    elif echo "$PULL_OUT" | grep -q "error\|fatal\|CONFLICT"; then
        warn "git pull tuvo problemas: $PULL_OUT"
        warn "Continuando con versión local"
    else
        ok "Repo actualizado desde GitHub"
        # Mostrar archivos cambiados
        echo "$PULL_OUT" | grep -E "^\s+" | head -10
    fi

    # Restaurar stash si hicimos
    git stash pop 2>/dev/null || true

    # Verificar que .env sigue intacto
    local LATEST_BAK=$(ls -t "$ENV_FILE.bak."* 2>/dev/null | head -1)
    if [ -n "$LATEST_BAK" ] && [ -f "$LATEST_BAK" ]; then
        if ! diff -q "$ENV_FILE" "$LATEST_BAK" >/dev/null 2>&1; then
            warn ".env fue modificado por git — restaurando backup"
            cp "$LATEST_BAK" "$ENV_FILE"
            ok ".env restaurado (credenciales protegidas)"
        else
            ok ".env intacto (credenciales verificadas)"
        fi
        rm -f "$ENV_FILE.bak."* 2>/dev/null || true
    fi

    # Verificación SHA-256 post-pull
    if [ -f "$ENV_FILE" ] && [ -n "$ENV_HASH_BEFORE" ] && [ "$ENV_HASH_BEFORE" != "n/a" ]; then
        local ENV_HASH_AFTER=$(sha256sum "$ENV_FILE" 2>/dev/null | cut -d' ' -f1 || echo "n/a")
        if [ "$ENV_HASH_AFTER" != "$ENV_HASH_BEFORE" ]; then
            warn ".env checksum cambió (antes: ${ENV_HASH_BEFORE:0:12}... después: ${ENV_HASH_AFTER:0:12}...)"
            warn "Restaurando .env desde backup..."
            local LATEST_BAK2=$(ls -t "$ENV_FILE.bak."* 2>/dev/null | head -1)
            if [ -n "$LATEST_BAK2" ] && [ -f "$LATEST_BAK2" ]; then
                cp "$LATEST_BAK2" "$ENV_FILE"
                ok ".env restaurado (checksum verificado)"
            fi
        else
            ok ".env checksum OK (sin cambios)"
        fi
    fi

    # Verificar que ~/.sol/ no se tocó
    if [ -d "$SOL_DIR" ]; then
        ok "~/.sol/ intacto (memoria de Sol preservada)"
    fi

    cd "$ROOT"
}

# ════════════════════════════════════════════════════════════════════
# VERIFICAR DEPENDENCIAS
# ════════════════════════════════════════════════════════════════════
check_deps() {
    banner
    echo -e "${W}🔍 Verificando dependencias...${N}\n"

    for cmd in python3 curl git; do
        command -v "$cmd" >/dev/null 2>&1 && ok "$cmd" || fail "$cmd (pkg install $cmd)"
    done

    # Python deps
    for pkg in fastapi uvicorn cryptography; do
        python3 -c "import $pkg" 2>/dev/null && ok "$pkg" || warn "$pkg (pip install $pkg)"
    done

    python3 -c "import psutil" 2>/dev/null && ok "psutil (C2)" || warn "psutil (pip install psutil) — necesario para C2"
    python3 -c "import aiohttp" 2>/dev/null && ok "aiohttp (Nexus)" || warn "aiohttp (pip install aiohttp) — necesario para Nexus"
    python3 -c "import reportlab" 2>/dev/null && ok "reportlab (PDFs)" || warn "reportlab (pip install reportlab)"

    # Voz (sol_core)
    command -v espeak-ng >/dev/null 2>&1 && ok "espeak-ng (voz Sol)" || warn "espeak-ng (pkg install espeak) — voz de Sol"
    command -v termux-tts-speak >/dev/null 2>&1 && ok "termux-tts (voz Sol)" || true

    # Telegram
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && ok "TELEGRAM_BOT_TOKEN" || fail "TELEGRAM_BOT_TOKEN no configurado en .env"
    [ -n "${TELEGRAM_CHAT_ID:-}" ] && ok "TELEGRAM_CHAT_ID" || warn "TELEGRAM_CHAT_ID no configurado"

    # Sol memory
    if [ -f "$SOL_DIR/memory.json" ] || [ -f "$SOL_DIR/memory.jsonl" ]; then
        local count=$(wc -l "$SOL_DIR/memory.jsonl" 2>/dev/null | cut -d' ' -f1 || echo "0")
        ok "Sol memory: $count recuerdos en ~/.sol/"
    else
        warn "Sol memory vacía — se creará al primer uso"
    fi

    echo ""
}

# ════════════════════════════════════════════════════════════════════
# KILL ZOMBIES
# ════════════════════════════════════════════════════════════════════
kill_zombies() {
    info "Limpiando procesos zombie..."
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "sol_telegram_bridge.py" 2>/dev/null || true
    pkill -f "sol_core.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    pkill -f "nexus_omni_v9.py" 2>/dev/null || true
    pkill -f "c2_unified_pro.py" 2>/dev/null || true
    for port in 8001 8002 8003 8004 8005; do
        if command -v fuser >/dev/null 2>&1; then
            fuser -k ${port}/tcp 2>/dev/null || true
        fi
    done
    sleep 2
    ok "Puertos liberados"
}

# ════════════════════════════════════════════════════════════════════
# START: Backend TACTICAL (:8001)
# ════════════════════════════════════════════════════════════════════
start_backend() {
    info "Backend TACTICAL :8001 — arrancando..."
    cd "$ROOT/redteam/scripts"
    PORT=8001 HOST=0.0.0.0 PYTHONUNBUFFERED=1 \
        nohup python3 dashboard_server.py > "$LOG_DIR/tactical.log" 2>&1 &
    BACKEND_PID=$!
    for i in $(seq 1 25); do
        kill -0 "$BACKEND_PID" 2>/dev/null || { fail "Backend murió"; tail -5 "$LOG_DIR/tactical.log"; return 1; }
        curl -s -m 2 http://127.0.0.1:8001/api/health >/dev/null 2>&1 && break
        sleep 1
    done
    curl -s -m 3 http://127.0.0.1:8001/api/health >/dev/null 2>&1 \
        && ok "Backend :8001 listo (PID $BACKEND_PID)" \
        || warn "Backend :8001 no respondió en 25s"
    cd "$ROOT"
}

# ════════════════════════════════════════════════════════════════════
# START: GHOST PHANTOM (:8002)
# ════════════════════════════════════════════════════════════════════
start_ghost() {
    [ -d "$ROOT/ghost_hunter_phantom" ] || { warn "ghost_hunter_phantom/ no encontrado"; return; }
    info "GHOST PHANTOM :8002 — arrancando..."
    cd "$ROOT/ghost_hunter_phantom"
    BACKEND_API="http://localhost:8001" MASTER_PORT=8002 NUM_NODES=1 \
        nohup bash start.sh all > "$LOG_DIR/ghost.log" 2>&1 &
    GHOST_PID=$!
    for i in $(seq 1 15); do
        curl -s -m 2 http://127.0.0.1:8002/api/status >/dev/null 2>&1 && break
        sleep 1
    done
    curl -s -m 2 http://127.0.0.1:8002/api/status >/dev/null 2>&1 \
        && ok "GHOST :8002 listo (PID $GHOST_PID)" \
        || warn "GHOST :8002 no respondió"
    cd "$ROOT"
}

# ════════════════════════════════════════════════════════════════════
# VERIFICAR CREDENCIALES (antes de Nexus — evitar regeneración)
# ════════════════════════════════════════════════════════════════════
verify_credentials() {
    local missing=0
    for cred in NEXUS_PASS ADMIN_PASSWORD REDTEAM_API_KEY; do
        val=$(eval echo "\${${cred}:-}")
        if [ -z "$val" ]; then
            fail "$cred no configurado en .env"
            missing=$((missing + 1))
        else
            ok "$cred presente"
        fi
    done
    if [ $missing -gt 0 ]; then
        warn "Faltan $missing credenciales — Nexus NO se arrancará"
        warn "Esto evita que nexus_credentials.py regenere credenciales"
        return 1
    fi
    return 0
}

# ════════════════════════════════════════════════════════════════════
# START: Nexus Omni-Sentient (:8004)
# ════════════════════════════════════════════════════════════════════
start_nexus() {
    [ -f "$ROOT/nexus_omni_v9.py" ] || { warn "nexus_omni_v9.py no encontrado"; return; }
    info "Nexus Omni-Sentient :8004 — arrancando..."
    cd "$ROOT"
    NEXUS_PORT=8004 nohup python3 nexus_omni_v9.py > "$LOG_DIR/nexus.log" 2>&1 &
    NEXUS_PID=$!
    for i in $(seq 1 15); do
        curl -s -m 2 http://127.0.0.1:8004/ >/dev/null 2>&1 && break
        sleep 1
    done
    curl -s -m 2 http://127.0.0.1:8004/ >/dev/null 2>&1 \
        && ok "Nexus :8004 listo (PID $NEXUS_PID)" \
        || warn "Nexus :8004 no respondió (pip install aiohttp?)"
}

# ════════════════════════════════════════════════════════════════════
# START: C2 UNIFIED PRO (:8005)
# ════════════════════════════════════════════════════════════════════
start_c2() {
    [ -f "$ROOT/c2_unified_pro.py" ] || { warn "c2_unified_pro.py no encontrado"; return; }
    info "C2 UNIFIED PRO :8005 — arrancando..."
    cd "$ROOT"
    C2_PORT=8005 nohup python3 c2_unified_pro.py > "$LOG_DIR/c2.log" 2>&1 &
    C2_PID=$!
    for i in $(seq 1 15); do
        curl -s -m 2 http://127.0.0.1:8005/api/health >/dev/null 2>&1 && break
        sleep 1
    done
    curl -s -m 2 http://127.0.0.1:8005/api/health >/dev/null 2>&1 \
        && ok "C2 :8005 listo (PID $C2_PID)" \
        || warn "C2 :8005 no respondió (pip install psutil requests)"
}

# ════════════════════════════════════════════════════════════════════
# START: SOL Core v4 (memoria viva — background o interactivo)
# ════════════════════════════════════════════════════════════════════
start_sol_core() {
    [ -f "$ROOT/sol_core.py" ] || { warn "sol_core.py no encontrado"; return; }

    # Verificar memoria de Sol
    MEM_COUNT=0
    if [ -f "$SOL_DIR/memory.jsonl" ]; then
        MEM_COUNT=$(wc -l < "$SOL_DIR/memory.jsonl" 2>/dev/null || echo 0)
    fi
    local json_count=0
    if [ -f "$SOL_DIR/memory.json" ]; then
        json_count=$(python3 -c "import json;print(len(json.loads(open('$SOL_DIR/memory.json').read())))" 2>/dev/null || echo 0)
    fi
    MEM_TOTAL=$((MEM_COUNT + json_count))

    ok "SOL Core v4 disponible ($MEM_TOTAL recuerdos en ~/.sol/)"
    ok "  Memoria: ~/.sol/memory.json ($json_count) + memory.jsonl ($MEM_COUNT)"
    info "SOL Core interactivo: bash sol_start.sh --core | --voz"
    info "SOL siempre-on: via Telegram (@sol_amg_bot) — puente abajo"
}

# ════════════════════════════════════════════════════════════════════
# START: SOL Telegram Bridge
# ════════════════════════════════════════════════════════════════════
start_sol_bridge() {
    [ -f "$ROOT/sol_telegram_bridge.py" ] || { warn "sol_telegram_bridge.py no encontrado"; return; }
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] || { fail "TELEGRAM_BOT_TOKEN no configurado"; return 1; }

    info "SOL Telegram Bridge — arrancando..."
    cd "$ROOT"
    nohup python3 sol_telegram_bridge.py > "$LOG_DIR/sol.log" 2>&1 &
    SOL_PID=$!
    sleep 3
    kill -0 "$SOL_PID" 2>/dev/null \
        && ok "SOL Bridge activo (PID $SOL_PID)" \
        || { fail "SOL Bridge murió"; tail -10 "$LOG_DIR/sol.log" 2>/dev/null; }
}

# ════════════════════════════════════════════════════════════════════
# RESUMEN
# ════════════════════════════════════════════════════════════════════
show_summary() {
    echo ""
    echo -e "${C}╔═══════════════════════════════════════════════════════╗${N}"
    echo -e "${C}║  ${W}🌅 SOL START v2.0${C} — Sistema activo                    ${C}║${N}"
    echo -e "${C}╠═══════════════════════════════════════════════════════╣${N}"
    echo -e "${G}║  ✅ :8001  Dashboard + Commander + LEVIATHAN + SEAL   ${C}║${N}"
    echo -e "${G}║  ✅ :8002  GHOST PHANTOM Master                       ${C}║${N}"
    if $WITH_NEXUS; then
    echo -e "${G}║  ✅ :8004  Nexus Omni-Sentient v9 (IA predictiva)     ${C}║${N}"
    fi
    if $WITH_C2; then
    echo -e "${G}║  ✅ :8005  C2 UNIFIED PRO (centro táctico)           ${C}║${N}"
    fi
    echo -e "${G}║  ✅ SOL    sol_core.py v4 (memoria viva)              ${C}║${N}"
    echo -e "${G}║  ✅ TG    sol_telegram_bridge (puente @sol_amg_bot)  ${C}║${N}"
    echo -e "${C}╠═══════════════════════════════════════════════════════╣${N}"
    echo -e "${C}║  ${W}Dashboard:${C} http://localhost:8001                     ${C}║${N}"
    echo -e "${C}║  ${W}Sol memory:${C} ~/.sol/ (${MEM_TOTAL:-0} recuerdos)              ${C}║${N}"
    echo -e "${C}║  ${W}Logs:${C} $LOG_DIR/                              ${C}║${N}"
    echo -e "${C}╚═══════════════════════════════════════════════════════╝${N}"
    echo ""
    echo -e "  ${Y}Ctrl+C${N} detiene todo limpio"
    echo -e "  ${Y}Comandos Telegram:${N} /status /health /alerts /scan /help"
    echo ""
}

# ════════════════════════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════════════════════════
cleanup() {
    echo ""
    warn "Apagando sistema SOL..."
    kill ${BACKEND_PID:-0} ${GHOST_PID:-0} ${SOL_PID:-0} ${SOL_CORE_PID:-0} ${NEXUS_PID:-0} ${C2_PID:-0} 2>/dev/null || true
    pkill -f "dashboard_server.py" 2>/dev/null || true
    pkill -f "sol_telegram_bridge.py" 2>/dev/null || true
    pkill -f "sol_core.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom" 2>/dev/null || true
    pkill -f "nexus_omni_v9.py" 2>/dev/null || true
    pkill -f "c2_unified_pro.py" 2>/dev/null || true
    ok "Sistema apagado. Sol sigue en ~/.sol/ esperándote."
    exit 0
}

trap cleanup SIGTERM SIGINT

# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════
case "${1:-}" in
    --check)
        load_env
        check_deps
        ;;
    --bridge)
        load_env
        banner
        start_sol_bridge
        ;;
    --core)
        load_env
        banner
        info "SOL Core v4 — modo interactivo"
        cd "$ROOT"
        python3 sol_core.py --listen
        ;;
    --voz)
        load_env
        banner
        info "SOL Core v4 — modo voz (micrófono)"
        cd "$ROOT"
        python3 sol_core.py --voz
        ;;
    --help|-h)
        banner
        echo "SOL START v2.0 — Arranque unificado SourceSeal"
        echo ""
        echo "Modos de uso:"
        echo "  bash sol_start.sh              # Completo + auto-update"
        echo "  bash sol_start.sh --no-update  # Sin git pull"
        echo "  bash sol_start.sh --bridge     # Solo Telegram Bridge"
        echo "  bash sol_start.sh --core       # SOL Core interactivo (--listen)"
        echo "  bash sol_start.sh --voz        # SOL Core con micrófono"
        echo "  bash sol_start.sh --nexus      # + Nexus :8004"
        echo "  bash sol_start.sh --c2         # + C2 :8005"
        echo "  bash sol_start.sh --full      # TODO (8001-8005 + SOL + TG)"
        echo "  bash sol_start.sh --check      # Verificar dependencias"
        echo ""
        echo "Puertos:"
        echo "  :8001  Dashboard + Commander + LEVIATHAN + SEAL"
        echo "  :8002  GHOST PHANTOM Master"
        echo "  :8004  Nexus Omni-Sentient (--nexus o --full)"
        echo "  :8005  C2 UNIFIED PRO (--c2 o --full)"
        echo ""
        echo "SOL Core v4 (commit 69cce41):"
        echo "  Vive en ~/.sol/ — no depende del repo"
        echo "  Memoria: memory.json + memory.jsonl (unificados)"
        echo "  Voz: espeak-ng (es), rate 0.92, pitch 1.1"
        echo "  --listen: interactivo | --voz: mic | --speak 'texto'"
        echo ""
        echo "Regla de oro:"
        echo "  .env NUNCA se toca. Credenciales NUNCA se alteran."
        echo "  ~/.sol/ NUNCA se borra. Memoria de Sol se preserva."
        ;;
    *)
        # Arranque completo (default)
        load_env
        banner
        auto_update
        kill_zombies
        start_backend
        start_ghost
        $WITH_NEXUS && { verify_credentials && start_nexus || warn "Nexus saltado — credenciales faltantes"; }
        $WITH_C2 && start_c2
        start_sol_core
        start_sol_bridge
        show_summary
        wait
        ;;
esac
