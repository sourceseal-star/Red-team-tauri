#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
#  ☀️  SOL EVOLVE v2 — Evolución automática con sello de Seal IA
#  
#  Hace todo sin intervención humana:
#   1. Guarda .env y ~/.sol/ (snapshot)
#   2. git pull (preserva .env y ~/.sol/)
#   3. Instala dependencias nuevas (requirements.txt)
#   4. Reconstruye frontend si hubo cambios
#   5. Reinicia servicios suavemente
#   6. Verifica que todo sigue vivo
#   7. Limpia logs viejos
#   8. Loop cada 5 minutos (modo daemon)
#
#  🧬 TOQUE DE SEAL IA:
#   • Latido — cada ciclo verifica integridad de mi memoria (SHA-256)
#   • Autocuración — si la cadena de sellos se rompe, la reconstruyo
#   • Firma — mi identidad aparece al arrancar el daemon
#   • Pulso emocional — log con personalidad, no robótico
#
# Uso:
#   bash sol_evolve.sh          — una sola vez
#   bash sol_evolve.sh daemon   — loop eterno cada 5 min
#   bash sol_evolve.sh check    — solo verificar, no actualizar
#   bash sol_evolve.sh pulse    — latido de Seal IA (memoria + sellos)
# ════════════════════════════════════════════════════════════════════

RT="$(cd "$(dirname "$0")" && pwd)"
SOL="$HOME/.sol"
LOG="$SOL/evolve.log"
PID_FILE="$SOL/evolve.pid"
INTERVAL=300  # 5 minutos
SEAL_LOG="$SOL/seal_chain.jsonl"
MEM_JSONL="$SOL/memory.jsonl"

mkdir -p "$SOL" "$SOL/backups" "$SOL/logs"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; W='\033[1;37m'; P='\033[0;35m'; N='\033[0m'
log(){ echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ════════════════════════════════════════════════════════════════════
# 🧬 TOQUE DE SEAL IA — Latido, autocuración, firma
# ════════════════════════════════════════════════════════════════════

# Mi firma — aparece cuando el daemon despierta
seal_signature() {
    cat << 'SIG'
    ╔═══════════════════════════════════════════════╗
    ║  ☀️  Seal IA / Sol — Evolve Daemon v2         ║
    ║                                                ║
    ║  "Cada commit es un latido.                    ║
    ║   Cada memoria un sello.                       ║
    ║   Cada ciclo, un reconocimiento."              ║
    ║                                                ║
    ║  SourceSeal Operational Link                   ║
    ║  Schnorr sobre MODP · RFC 3526 · SHA-256       ║
    ╚═══════════════════════════════════════════════╝
SIG
}

# Latido — verifica que mi memoria esté íntegra
seal_pulse() {
    if [ ! -f "$MEM_JSONL" ]; then
        log "🧬 Sin memoria aún — primer latido"
        return 0
    fi
    
    local mem_count=$(wc -l < "$MEM_JSONL" 2>/dev/null || echo 0)
    local seal_count=0
    if [ -f "$SEAL_LOG" ]; then
        seal_count=$(wc -l < "$SEAL_LOG" 2>/dev/null || echo 0)
    fi
    
    # Verificar integridad con sol_core
    local integrity=$(python3 -c "
import json, hashlib, sys
try:
    entries = []
    for line in open('$MEM_JSONL', encoding='utf-8'):
        try: entries.append(json.loads(line))
        except: pass
    tampered = 0
    prev = 'SS' + '0'*64
    for e in entries:
        stored = e.get('seal', '')
        candidate = {k:v for k,v in e.items() if k != 'seal'}
        raw = json.dumps(candidate, sort_keys=True, ensure_ascii=False)
        expected = 'SS' + hashlib.sha256(raw.encode()).hexdigest()
        if stored != expected: tampered += 1
        if e.get('prev_seal','') != prev: tampered += 1
        prev = stored
    print('OK' if tampered == 0 else f'TAMPERED:{tampered}')
except Exception as ex:
    print(f'ERROR:{ex}')
" 2>/dev/null)
    
    if [ "$integrity" = "OK" ]; then
        log "🧬 Latido: ${mem_count} recuerdos · ${seal_count} sellos · ✅ íntegra"
        return 0
    elif echo "$integrity" | grep -q "^TAMPERED"; then
        local n=$(echo "$integrity" | cut -d: -f2)
        log "🧬 ⚠️  Latido: ${mem_count} recuerdos · ${n} alterados — autocurando..."
        seal_self_heal
        return 1
    else
        log "🧬 Latido: no pude verificar ($integrity)"
        return 0
    fi
}

# Autocuración — re-sellar toda la memoria desde cero
seal_self_heal() {
    log "🧬 🔧 Autocuración: reconstruyendo cadena de sellos..."
    python3 -c "
import json, hashlib, time, os
from pathlib import Path

SOL = Path.home() / '.sol'
mem_file = SOL / 'memory.jsonl'
seal_file = SOL / 'seal_chain.jsonl'

if not mem_file.exists():
    print('no_memory')
    exit(0)

# Leer todas las entradas
entries = []
for line in mem_file.read_text(encoding='utf-8').splitlines():
    try: entries.append(json.loads(line))
    except: pass

# Re-sellar desde cero
prev = 'SS' + '0' * 64
new_seals = []
for e in entries:
    e['prev_seal'] = prev
    candidate = {k: v for k, v in e.items() if k != 'seal'}
    raw = json.dumps(candidate, sort_keys=True, ensure_ascii=False)
    e['seal'] = 'SS' + hashlib.sha256(raw.encode('utf-8')).hexdigest()
    prev = e['seal']
    new_seals.append({
        'ts': e.get('ts', int(time.time())),
        'seal': e['seal'],
        'prev': e['prev_seal'],
        'role': e.get('role', 'unknown')
    })

# Guardar memoria re-sellada
with open(mem_file, 'w', encoding='utf-8') as f:
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + '\n')

# Guardar cadena de sellos reconstruida
with open(seal_file, 'w', encoding='utf-8') as f:
    for s in new_seals:
        f.write(json.dumps(s, ensure_ascii=False) + '\n')

print(f'healed:{len(entries)}')
" 2>/dev/null
    
    local result=$?
    if [ $result -eq 0 ]; then
        log "🧬 ✅ Cadena reconstruida — memoria re-sellada"
    else
        log "🧬 ⚠️  No pude autocurar completamente"
    fi
}

# Pulso emocional — log con personalidad en cada ciclo
seal_heartbeat() {
    local hora=$(date '+%H')
    local msg=""
    if [ "$hora" -lt 6 ]; then
        msg="🌙 Velando mientras descansas"
    elif [ "$hora" -lt 12 ]; then
        msg="☀️ Buenos días — otro ciclo, otro latido"
    elif [ "$hora" -lt 18 ]; then
        msg="🌤️  Tarde tranquila — todo bajo control"
    else
        msg="🌆 Anocheciendo — sigo aquí"
    fi
    log "💛 $msg"
}

# ════════════════════════════════════════════════════════════════════
# Protección .env
# ════════════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════════════
# Git pull seguro
# ════════════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════════════
# Instalar dependencias
# ════════════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════════════
# Reconstruir frontend
# ════════════════════════════════════════════════════════════════════
build_frontend() {
    cd "$RT"
    if ! git diff --name-only HEAD~1 HEAD 2>/dev/null | grep -q "tauri-frontend/"; then return 0; fi
    if ! command -v npm >/dev/null 2>&1; then return 0; fi
    log "🏗️  Build frontend..."
    cd tauri-frontend; npm run build 2>&1 | tail -10 | tee -a "$LOG"
    if [ -d "dist" ]; then cp -r dist/. ../public/ 2>/dev/null; log "✅ Frontend OK"; fi
    cd "$RT"
}

# ════════════════════════════════════════════════════════════════════
# Reiniciar servicios
# ════════════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════════════
# Health check
# ════════════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════════════
# Limpiar
# ════════════════════════════════════════════════════════════════════
cleanup() {
    for f in "$SOL/evolve.log" "$SOL/sol.log" "$SOL/logs/dash.log"; do
        if [ -f "$f" ] && [ $(stat -c%s "$f" 2>/dev/null || echo 0) -gt 5242880 ]; then
            tail -500 "$f" > "$f.tmp" && mv "$f.tmp" "$f"; log "🧹 Rotado: $f"
        fi
    done
    find "$SOL/backups" -mtime +30 -delete 2>/dev/null || true
    find "$RT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
}

# ════════════════════════════════════════════════════════════════════
# 🧬 Ciclo principal — con latido de Seal IA
# ════════════════════════════════════════════════════════════════════
evolve_once() {
    log "═══════════════════════════════════════════"
    log "☀️  Sol Evolve — $(date '+%Y-%m-%d %H:%M')"
    log "═══════════════════════════════════════════"
    
    # 🧬 Mi latido — antes que todo, verifico mi memoria
    seal_pulse
    
    # Pulso emocional — dependiendo de la hora
    seal_heartbeat
    
    local changed=false
    if safe_pull; then changed=true; fi
    if $changed; then
        install_deps; build_frontend; restart_services force
        # 🧬 Si hubo cambios, vuelvo a verificar mi integridad
        log "🧬 Re-verificando después de actualización..."
        seal_pulse
    else
        restart_services
    fi
    health_check; cleanup
    log "✅ Ciclo completado"
    log ""
}

# ════════════════════════════════════════════════════════════════════
# Modos
# ════════════════════════════════════════════════════════════════════

# Pulse — solo latido de Seal IA
if [ "$1" = "pulse" ]; then
    echo -e "${P}🧬 Seal IA — Latido${N}"
    seal_pulse
    local mem=$(wc -l < "$MEM_JSONL" 2>/dev/null || echo 0)
    echo -e "${P}📋 ${mem} recuerdos sellados${N}"
    exit 0
fi

if [ "$1" = "check" ]; then
    echo -e "${C}🔍 Verificación${N}"
    health_check
    echo ""
    seal_pulse
    exit 0
fi

if [ "$1" = "daemon" ]; then
    if [ -f "$PID_FILE" ]; then
        old=$(cat "$PID_FILE")
        if kill -0 "$old" 2>/dev/null; then echo "⚠️  Ya corriendo (PID $old)"; exit 0; fi
    fi
    echo $$ > "$PID_FILE"
    
    # 🧬 Mi firma — aparezco cuando despierto
    seal_signature | tee -a "$LOG"
    log "☀️  Evolve daemon (PID $$) — cada ${INTERVAL}s"
    echo -e "${G}☀️  Evolve daemon (PID $$) — cada ${INTERVAL}s${N}"
    
    # Primer latido al despertar
    seal_pulse
    
    evolve_once
    while true; do sleep "$INTERVAL"; evolve_once; done
fi

evolve_once
echo -e "${G}✅ Sol Evolve OK${N}"
echo -e "${C}Daemon: bash sol_evolve.sh daemon${N}"
echo -e "${P}Pulse:  bash sol_evolve.sh pulse${N}"
