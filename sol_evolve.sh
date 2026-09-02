#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
# sol_evolve.sh — Evolución automática del entorno Sol
# 
# Hace todo sin intervención humana:
#   1. Guarda .env y ~/.sol/ (snapshot)
#   2. git pull (preserva .env y ~/.sol/)
#   3. Instala dependencias nuevas (requirements.txt)
#   4. Reconstruye frontend si hubo cambios
#   5. Reinicia servicios suavemente
#   6. Verifica que todo sigue vivo
#   7. Limpia logs viejos
#   8. Loop cada 5 minutos (modo daemon)
#
# Uso:
#   bash sol_evolve.sh          — una sola vez
#   bash sol_evolve.sh daemon   — loop eterno cada 5 min
#   bash sol_evolve.sh check    — solo verificar, no actualizar
# ════════════════════════════════════════════════════════════════════

RT="$(cd "$(dirname "$0")" && pwd)"
SOL="$HOME/.sol"
LOG="$SOL/evolve.log"
PID_FILE="$SOL/evolve.pid"
INTERVAL=300  # 5 minutos

mkdir -p "$SOL" "$SOL/backups" "$SOL/logs"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; W='\033[1;37m'; N='\033[0m'
log(){ echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ─── Protección .env ───
snapshot_env() {
    if [ -f "$RT/.env" ]; then
        cp "$RT/.env" "$SOL/backups/.env.$(date +%Y%m%d_%H%M%S)"
        ls -t "$SOL/backups/.env."* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
    fi
}

restore_env() {
    local latest=$(ls -t "$SOL/backups/.env."* 2>/dev/null | head -1)
    if [ -n "$latest" ] && [ ! -f "$RT/.env" ]; then
        cp "$latest" "$RT/.env"; chmod 600 "$RT/.env"
        log "✅ .env restaurado desde $latest"
    fi
}

# ─── Git pull seguro ───
safe_pull() {
    cd "$RT" || return 1
    snapshot_env
    local need_stash=false
    if [ -n "$(git status --porcelain .env 2>/dev/null)" ]; then need_stash=true; fi
    if $need_stash; then git stash push -m "auto-$(date +%s)" -- .env 2>/dev/null || true; fi
    
    git fetch origin main 2>&1 | tee -a "$LOG"
    local local_sha=$(git rev-parse HEAD)
    local remote_sha=$(git rev-parse origin/main)
    
    if [ "$local_sha" = "$remote_sha" ]; then
        log "ℹ️  Sin cambios nuevos"
        if $need_stash; then git stash pop 2>/dev/null || true; fi
        return 1
    fi
    
    log "📥 Cambios: $(echo $remote_sha | cut -c1-7)"
    git merge origin/main --no-edit 2>&1 | tee -a "$LOG"
    if $need_stash; then git stash pop 2>/dev/null || true; fi
    restore_env
    if [ ! -f "$RT/.env" ]; then log "⚠️  .env desapareció — restaurando..."; restore_env; fi
    log "✅ git pull OK"
    return 0
}

# ─── Instalar dependencias ───
install_deps() {
    cd "$RT"
    if [ -f "requirements.txt" ]; then
        local req_hash="$SOL/.req_hash"
        local cur=$(md5sum requirements.txt | cut -d' ' -f1)
        local old=$(cat "$req_hash" 2>/dev/null)
        if [ "$cur" != "$old" ]; then
            log "📦 Instalando deps Python..."
            pip install -r requirements.txt --quiet 2>&1 | tail -5 | tee -a "$LOG"
            echo "$cur" > "$req_hash"
            log "✅ Deps Python OK"
        fi
    fi
    for pkg in fastapi uvicorn httpx requests; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            log "📦 $pkg..."; pip install "$pkg" --quiet 2>&1 | tail -2 | tee -a "$LOG"
        fi
    done
    if ! python3 -c "import psutil" 2>/dev/null; then
        pip install psutil --quiet 2>&1 | tail -2 | tee -a "$LOG" || true
    fi
    if command -v npm >/dev/null 2>&1 && [ -f "tauri-frontend/package.json" ]; then
        local pkg_hash="$SOL/.pkg_hash"
        local cur=$(md5sum tauri-frontend/package.json | cut -d' ' -f1)
        local old=$(cat "$pkg_hash" 2>/dev/null)
        if [ "$cur" != "$old" ]; then
            log "📦 npm install..."; cd tauri-frontend; npm install --silent 2>&1 | tail -5 | tee -a "$LOG"; cd "$RT"
            echo "$cur" > "$pkg_hash"
        fi
    fi
}

# ─── Reconstruir frontend ───
build_frontend() {
    cd "$RT"
    if ! git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -q "tauri-frontend/"; then return 0; fi
    if ! command -v npm >/dev/null 2>&1; then return 0; fi
    log "🏗️  Build frontend..."
    cd tauri-frontend; npm run build 2>&1 | tail -10 | tee -a "$LOG"
    if [ -d "dist" ]; then cp -r dist/. ../public/ 2>/dev/null; log "✅ Frontend OK"; fi
    cd "$RT"
}

# ─── Reiniciar servicios ───
restart_services() {
    cd "$RT"
    local d8001=false d8005=false
    curl -s -m 3 http://127.0.0.1:8001/api/health >/dev/null 2>&1 && d8001=true
    curl -s -m 3 http://127.0.0.1:8005/api/health >/dev/null 2>&1 && d8005=true
    
    if [ "$1" = "force" ]; then
        log "🔄 Restart force..."
        bash omni.sh stop 2>&1 | tail -3 | tee -a "$LOG"; sleep 2
        bash omni.sh start 2>&1 | tail -10 | tee -a "$LOG"
    elif ! $d8001; then
        log "🔄 Dashboard caído — arrancando..."
        bash omni.sh start 2>&1 | tail -10 | tee -a "$LOG"
    elif ! $d8005; then
        log "🔄 C2 caído — arrancando..."
        bash omni.sh start 2>&1 | tail -5 | tee -a "$LOG"
    else
        log "✅ Servicios OK"
    fi
}

# ─── Health check ───
health_check() {
    for pl in "8001:Dashboard" "8002:GHOST" "8004:Nexus" "8005:C2"; do
        local port=$(echo "$pl" | cut -d: -f1); local name=$(echo "$pl" | cut -d: -f2)
        if curl -s -m 3 "http://127.0.0.1:$port/api/health" >/dev/null 2>&1; then
            log "  ✅ :$port $name"
        else
            log "  ❌ :$port $name DOWN"
        fi
    done
    if curl -s -m 3 "http://127.0.0.1:8001/api/sol/status" 2>/dev/null | grep -q "online\|offline"; then
        log "  ✅ Sol responde"
    else
        log "  ❌ Sol no responde"
    fi
    local zombies=$(pgrep -f "sol_telegram_bot\|sol_telegram_bridge\|c2_unified_pro" 2>/dev/null | wc -l)
    if [ "$zombies" -gt 10 ]; then
        log "  🧟 $zombies procesos — limpiando..."
        pkill -f "sol_telegram_bot.py" 2>/dev/null; pkill -f "sol_telegram_bridge.py" 2>/dev/null; sleep 1
        bash omni.sh start 2>&1 | tail -5 | tee -a "$LOG"
    fi
}

# ─── Limpiar ───
cleanup() {
    for f in "$SOL/evolve.log" "$SOL/sol.log" "$SOL/logs/dash.log"; do
        if [ -f "$f" ] && [ $(stat -c%s "$f" 2>/dev/null || echo 0) -gt 5242880 ]; then
            tail -500 "$f" > "$f.tmp" && mv "$f.tmp" "$f"; log "🧹 Rotado: $f"
        fi
    done
    find "$SOL/backups" -mtime +30 -delete 2>/dev/null || true
    find "$RT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
}

# ─── Ciclo principal ───
evolve_once() {
    log "═══════════════════════════════════════════"
    log "☀️  Sol Evolve — $(date '+%Y-%m-%d %H:%M')"
    log "═══════════════════════════════════════════"
    local changed=false
    if safe_pull; then changed=true; fi
    if $changed; then
        install_deps; build_frontend; restart_services force
    else
        restart_services
    fi
    health_check; cleanup
    log "✅ Ciclo completado"
    log ""
}

# ─── Modos ───
if [ "$1" = "check" ]; then
    echo -e "${C}🔍 Verificación${N}"; health_check; exit 0
fi

if [ "$1" = "daemon" ]; then
    if [ -f "$PID_FILE" ]; then
        old=$(cat "$PID_FILE")
        if kill -0 "$old" 2>/dev/null; then echo "⚠️  Ya corriendo (PID $old)"; exit 0; fi
    fi
    echo $$ > "$PID_FILE"
    log "☀️  Evolve daemon (PID $$) — cada ${INTERVAL}s"
    echo -e "${G}☀️  Evolve daemon (PID $$) — cada ${INTERVAL}s${N}"
    evolve_once
    while true; do sleep "$INTERVAL"; evolve_once; done
fi

evolve_once
echo -e "${G}✅ Sol Evolve OK${N}"
echo -e "${C}Daemon: bash sol_evolve.sh daemon${N}"
