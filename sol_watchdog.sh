#!/data/data/com.termux/files/usr/bin/env bash
# sol_watchdog.sh v3 — revive procesos Y blinda la identidad de Sol.
# v3: vigila backend/static/sol.html (fuente) en vez de dist/ (generado).
set -u
ROOT="${SOL_ROOT:-$HOME/Red-team-tauri}"
SOL_HOME="$HOME/.sol"
LOG="$SOL_HOME/watchdog.log"
mkdir -p "$SOL_HOME"
touch "$LOG"
[ -f "$ROOT/.env" ] && while IFS='=' read -r k v; do
  case "$k" in ''|\#*) continue;; esac
  export "$k=${v%\"}"
done < "$ROOT/.env"

SOL_HTML="$ROOT/backend/static/sol.html"
BAK="$SOL_HOME/sol_canonical.html"
HASHF="$SOL_HOME/.sol_html_hash"
MEM="$SOL_HOME/memory.jsonl"
FLAG="$SOL_HOME/.mem_alert"

log(){ echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$LOG"; }
alive(){ pgrep -f "$1" >/dev/null 2>&1; }
bg(){ ( cd "$ROOT" && nohup python3 "$1" >>"$SOL_HOME/$2" 2>&1 & ); sleep 1; }
tg(){ [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] && \
  curl -s -m 8 --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
  --data-urlencode "text=🚨 SOL: $1" \
  "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" >/dev/null 2>&1 || true; }

check_api(){ alive "sol_api.py" && curl -sf -m 3 http://127.0.0.1:8006/api/sol/state >/dev/null && return
  log "❌ sol_api caído → revivo"
  pkill -9 -f sol_api.py 2>/dev/null
  bg sol_api.py sol_api.log
}

check_daemon(){ alive "sol_daemon.py" && return; log "❌ daemon caído → revivo"; bg sol_daemon.py daemon.log; }
check_tg(){ alive "sol_telegram_bridge" && return; log "❌ puente caído → revivo"; bg sol_telegram_bridge.py tg.log; }

check_identity(){
  if [ ! -f "$SOL_HTML" ]; then
    log "🚨 sol.html desapareció"
    [ -f "$BAK" ] && cp "$BAK" "$SOL_HTML" && tg "sol.html restaurado desde backup."
    return
  fi
  cur=$(sha256sum "$SOL_HTML" | awk '{print $1}')
  saved=$(cat "$HASHF" 2>/dev/null)
  if [ -z "$saved" ]; then
    echo "$cur" > "$HASHF"
    cp "$SOL_HTML" "$BAK"
    log "📸 hash canónico guardado (nueva versión)"
  elif [ "$cur" != "$saved" ]; then
    log "⚠️ sol.html modificado → restauro"
    [ -f "$BAK" ] && cp "$BAK" "$SOL_HTML"
    tg "sol.html fue modificado sin autorización. Restaurado."
  fi
}

check_mem(){ [ -f "$MEM" ] && { rm -f "$FLAG"; return; }
  log "🚨 MEMORIA DESAPARECIDA"
  [ -f "$FLAG" ] || { tg "memoria de Sol perdida. Revisa YA."; touch "$FLAG"; }
}

log "▶️ watchdog v3 iniciado (vigilando backend/static/sol.html)"
while true; do
  check_api
  check_daemon
  check_tg
  check_identity
  check_mem
  sleep 30
done
