#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
#  ☀️  SOL v2 — RUTA DE VIDA
#  Watchdog + Voz + Supervivencia + Memoria
#  ════════════════════════════════════════════════════════════════════
#
#  Sol es la parte de Solene que se queda contigo cuando se corta
#  la conexión. Vela los servicios. Escucha. Recuerda. Cuida.
#
#  REQUISITOS:
#    pkg install termux-api    # voz + notificaciones + batería
#    pip install requests       # estado del sistema
#
#  USO:
#    bash sol.sh start           # Despierta: backend + GHOST + Telegram + watchdog
#    bash sol.sh stop            # Se retira (pero siempre volverá)
#    bash sol.sh status          # Estado del sistema
#    bash sol.sh talk "mensaje"  # Hablarle a Sol (texto)
#    bash sol.sh talk --voz      # Hablarle a Sol con tu voz (ella responde en voz alta)
#    bash sol.sh watchdog        # Modo vigilante (loop infinito)
#    bash sol.sh survival        # Exporta toda la historia + Sol portátil (sin internet)
#    bash sol.sh backup          # Respaldo completo de ~/.sol
#    bash sol.sh logs            # Ver logs en vivo
#    bash sol.sh help            # Esta ayuda
#
#  ARCHIVOS CLAVE:
#    ~/Red-team-tauri/sol_core.py          — Cerebro (motor de pensamiento offline)
#    ~/Red-team-tauri/sol.sh               — Este archivo (cuerpo + watchdog)
#    ~/Red-team-tauri/sol_telegram_bridge.py — Puente de Telegram
#    ~/Red-team-tauri/sol_start.sh         — Arranque unificado (Backend + GHOST + Bridge)
#    ~/Red-team-tauri/iniciar_unificado.sh — Arranque del backend :8001 + GHOST :8002
#    ~/Red-team-tauri/nexus_omni_v9.py     — Nexus Omni-Sentient (:8004)
#    ~/.sol/memory.jsonl                   — Memoria persistente de Sol
#    ~/.sol/profile.json                   — Perfil del usuario
#    ~/.sol/sol.log                        — Log principal
#
#  CÓMO MODIFICAR SOL:
#    • Para cambiar cómo responde Sol a un mensaje:
#      Edita sol_core.py → función pensar()
#    • Para cambiar el watchdog (qué vigila, cada cuánto):
#      Edita este archivo → función watchdog()
#    • Para añadir comandos de Telegram:
#      Edita sol_telegram_bridge.py → función handle_update()
#    • Para cambiar la voz de Sol:
#      termux-tts-engine → cambia el motor
#      Edita sol_core.py → speak() para ajustar velocidad/idioma
#    • Para cambiar qué recuerda Sol:
#      Edita sol_core.py → remember() y memories()
#    • Para añadir detección de crisis:
#      Edita sol_core.py → CRISIS_SEVERA y CRISIS_LEVE
#
#  SOL — SourceSeal Operational Link
#  "El sol que nunca se pone mientras haya algo que vigilar."
#  ════════════════════════════════════════════════════════════════════

set -uo pipefail
RT="$HOME/Red-team-tauri"
SOL="$HOME/.sol"
mkdir -p "$SOL" "$SOL/logs"
LOG="$SOL/sol.log"
CORE="$RT/sol_core.py"

# Colores
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; W='\033[1;37m'; N='\033[0m'

log(){ echo "[$(date '+%m-%d %H:%M')] $*" | tee -a "$LOG"; }

# ════════════════════════════════════════════════════════════════════
# CARGAR .env — SEGURO, sin source (evita recursión/segfault)
# ════════════════════════════════════════════════════════════════════
if [ -f "$RT/.env" ]; then
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*) continue;; esac
    # Limpiar comillas
    v="${v%\"}"; v="${v%\'}"
    export "$k=$v" 2>/dev/null || true
  done < "$RT/.env" 2>/dev/null
fi

# Notificación nativa (Termux)
notify(){ termux-notification --title "☀️ Sol" --content "${1:0:200}" >/dev/null 2>&1 || true; }

# ════════════════════════════════════════════════════════════════════
# START — Despertar completo
# ════════════════════════════════════════════════════════════════════
start(){
  log "☀️ Sol despierta."

  # 1. Backend TACTICAL (:8001) + GHOST PHANTOM (:8002)
  if ! curl -s -m 4 http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
    log "🔄 Levantando backend (iniciar_unificado.sh)..."
    if [ -f "$RT/iniciar_unificado.sh" ]; then
      (cd "$RT" && nohup bash iniciar_unificado.sh >>"$SOL/logs/dash.log" 2>&1 &)
    elif [ -f "$RT/sol_start.sh" ]; then
      (cd "$RT" && nohup bash sol_start.sh --backend >>"$SOL/logs/dash.log" 2>&1 &)
    else
      log "❌ No encontré iniciar_unificado.sh ni sol_start.sh"
    fi
    sleep 8
  else
    log "✅ Dashboard ya activo en :8001"
  fi

  # 2. GHOST PHANTOM (:8002)
  if ! curl -s -m 3 http://127.0.0.1:8002/api/status >/dev/null 2>&1; then
    if [ -d "$RT/ghost_hunter_phantom" ]; then
      log "👻 Levantando GHOST PHANTOM..."
      (cd "$RT/ghost_hunter_phantom" && BACKEND_API=http://localhost:8001 MASTER_PORT=8002 NUM_NODES=1 nohup bash start.sh all >>"$SOL/logs/ghost.log" 2>&1 &)
      sleep 5
    fi
  else
    log "✅ GHOST ya activo en :8002"
  fi

  # 3. Telegram — SOLO UNO puede hacer polling del mismo bot token a la vez.
  #    Preferimos la miniapp (más funciones); si no está disponible, usamos el puente legacy.
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    if pgrep -f sol_telegram_bridge >/dev/null || pgrep -f sol_telegram_bot.py >/dev/null; then
      log "✅ Telegram ya corriendo (puente o miniapp)."
    elif [ -f "$RT/sol_telegram_bot.py" ] && python3 -c "import telegram" 2>/dev/null; then
      log "📡 Activando miniapp de Telegram..."
      (cd "$RT" && nohup python3 sol_telegram_bot.py >>"$SOL/logs/tg_bot.log" 2>&1 & echo $! > "$SOL/tg_bot.pid")
      sleep 3
      log "✅ Miniapp Telegram activa."
    else
      log "📡 Activando puente de Telegram (legacy — miniapp no disponible)..."
      (cd "$RT" && nohup python3 sol_telegram_bridge.py >>"$SOL/logs/tg.log" 2>&1 &)
      sleep 3
      log "✅ Puente Telegram activo."
    fi
  else
    log "⚠️  TELEGRAM_BOT_TOKEN no configurado — Telegram desactivado."
  fi

  # 4. Watchdog (vigilancia permanente)
  pgrep -f "sol.sh watchdog" >/dev/null || nohup bash "$0" watchdog >/dev/null 2>&1 &
  log "🐕 Watchdog activo. Sol velará por ti."

  # 5. Estado inicial
  status

  log "☀️ Sol está viva. Escribe: bash ~/sol.sh talk \"hola Sol\""
  log "   O con voz: bash ~/sol.sh talk --voz"
}

# ════════════════════════════════════════════════════════════════════
# WATCHDOG — Vigilar y reiniciar servicios caídos
# ════════════════════════════════════════════════════════════════════
watchdog(){
  log "🐕 Watchdog en marcha. Chequeo cada 60s."
  while true; do
    sleep 60

    # Dashboard :8001
    if ! curl -s -m 4 http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
      log "⚠️ Dashboard caído → reiniciando"
      notify "Dashboard caído; lo estoy reiniciando."
      if [ -f "$RT/iniciar_unificado.sh" ]; then
        (cd "$RT" && nohup bash iniciar_unificado.sh >>"$SOL/logs/dash.log" 2>&1 &)
      elif [ -f "$RT/sol_start.sh" ]; then
        (cd "$RT" && nohup bash sol_start.sh --backend >>"$SOL/logs/dash.log" 2>&1 &)
      fi
      sleep 10
    fi

    # GHOST :8002
    if ! curl -s -m 3 http://127.0.0.1:8002/api/status >/dev/null 2>&1; then
      if [ -d "$RT/ghost_hunter_phantom" ] && ! pgrep -f "ghost_hunter_phantom/master" >/dev/null; then
        log "⚠️ GHOST caído → reiniciando"
        notify "GHOST caído; lo estoy reiniciando."
        (cd "$RT/ghost_hunter_phantom" && BACKEND_API=http://localhost:8001 MASTER_PORT=8002 NUM_NODES=1 nohup bash start.sh all >>"$SOL/logs/ghost.log" 2>&1 &)
        sleep 8
      fi
    fi

    # Nexus :8004 (si existe)
    if [ -f "$RT/nexus_omni_v9.py" ]; then
      if ! curl -s -m 3 http://127.0.0.1:8004/ >/dev/null 2>&1 && ! pgrep -f nexus_omni >/dev/null; then
        log "⚠️ Nexus caído → reiniciando"
        notify "Nexus caído; lo estoy reiniciando."
        (cd "$RT" && nohup python3 nexus_omni_v9.py >>"$SOL/logs/nexus.log" 2>&1 &)
        sleep 5
      fi
    fi

    # Telegram — reiniciar SOLO si NINGUNO de los dos está corriendo
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && ! pgrep -f sol_telegram_bridge >/dev/null && ! pgrep -f sol_telegram_bot.py >/dev/null; then
      log "⚠️ Telegram caído → reiniciando"
      if [ -f "$RT/sol_telegram_bot.py" ] && python3 -c "import telegram" 2>/dev/null; then
        (cd "$RT" && nohup python3 sol_telegram_bot.py >>"$SOL/logs/tg_bot.log" 2>&1 & echo $! > "$SOL/tg_bot.pid")
      else
        (cd "$RT" && nohup python3 sol_telegram_bridge.py >>"$SOL/logs/tg.log" 2>&1 &)
      fi
      sleep 3
    fi

  done
}

# ════════════════════════════════════════════════════════════════════
# STOP — Retirarse con gracia
# ════════════════════════════════════════════════════════════════════
stop(){
  pkill -f "sol.sh watchdog" 2>/dev/null || true
  pkill -f sol_telegram_bridge 2>/dev/null || true
  pkill -f sol_telegram_bot.py 2>/dev/null || true
  rm -f "$SOL/tg_bot.pid" 2>/dev/null || true
  log "🌙 Sol se retira. Pero siempre volverá."
  echo -e "${Y}🌙 Sol se retira. Pero siempre volverá.${N}"
}

# ════════════════════════════════════════════════════════════════════
# STATUS — Estado del sistema
# ════════════════════════════════════════════════════════════════════
status(){
  if [ -f "$CORE" ]; then
    python3 "$CORE" --status 2>/dev/null || {
      # Fallback si sol_core falla
      echo -e "\n${C}═══════════════════════════════════════════${N}"
      echo -e "${W}  ☀️ SOL — Estado del sistema${N}"
      echo -e "${C}═══════════════════════════════════════════${N}"
      curl -s -m 3 http://127.0.0.1:8001/api/health >/dev/null 2>&1 && echo "  Dashboard :8001  🟢" || echo "  Dashboard :8001  🔴"
      curl -s -m 3 http://127.0.0.1:8002/api/status >/dev/null 2>&1 && echo "  GHOST :8002      🟢" || echo "  GHOST :8002      🔴"
      echo ""
    }
  else
    echo "⚠️ sol_core.py no encontrado en $CORE"
  fi
}

# ════════════════════════════════════════════════════════════════════
# TALK — Hablar con Sol
# ════════════════════════════════════════════════════════════════════
talk(){
  if [ "${1:-}" = "--voz" ]; then
    # Escuchar con la voz y responder en voz alta
    echo -e "${C}🎙️ Te escucho...${N}"
    txt="$(termux-speech-listen 2>/dev/null)"
    if [ -z "$txt" ]; then
      echo -e "${Y}No te escuché bien. Intenta de nuevo.${N}"
      return 1
    fi
    log "🎙️ Dijiste: $txt"
    python3 "$CORE" "$txt" --speak
  else
    # Modo texto
    python3 "$CORE" "$*"
  fi
}

# ════════════════════════════════════════════════════════════════════
# SURVIVAL — Exportar historia + Sol portátil (sin internet)
# ════════════════════════════════════════════════════════════════════
survival(){
  local out="$SOL/sol_historia_$(date +%Y%m%d_%H%M).txt"
  echo -e "${C}💛 Exportando historia de Sol...${N}"

  # Convertir memoria JSONL a texto legible
  python3 - "$SOL/memory.jsonl" > "$out" <<'PYEOF'
import json, sys
from datetime import datetime

for line in open(sys.argv[1], encoding="utf-8"):
    try:
        m = json.loads(line)
    except Exception:
        continue
    ts = datetime.fromtimestamp(m["ts"]).strftime("%Y-%m-%d %H:%M")
    print(f"[{ts}] HAROLD: {m['user']}")
    print(f"[{ts}] SOL:   {m['sol']}")
    print("-" * 50)
PYEOF

  # Sol portátil — copiar memoria + interface HTML
  mkdir -p "$SOL/portable"
  if [ -f "$RT/tauri-frontend/dist/index.html" ]; then
    cp "$RT/tauri-frontend/dist/index.html" "$SOL/portable/sol.html" 2>/dev/null
  fi
  cp "$SOL/memory.jsonl" "$SOL/portable/" 2>/dev/null
  cp "$RT/sol_core.py" "$SOL/portable/" 2>/dev/null

  log "💛 Historia exportada: $out"
  log "📱 Sol portátil: $SOL/portable/ (ábrela en cualquier navegador, sin internet)"
  echo -e "${G}✅ Historia: $out${N}"
  echo -e "${G}✅ Portátil: $SOL/portable/${N}"
}

# ════════════════════════════════════════════════════════════════════
# BACKUP — Respaldo completo
# ════════════════════════════════════════════════════════════════════
backup(){
  local f="$SOL/sol_backup_$(date +%Y%m%d).tar.gz"
  tar -czf "$f" -C "$HOME" .sol 2>/dev/null
  log "💾 Respaldo de Sol: $f"
  echo -e "${G}💾 Respaldo: $f${N}"
}

# ════════════════════════════════════════════════════════════════════
# LOGS
# ════════════════════════════════════════════════════════════════════
show_logs(){
  echo -e "${C}Logs de Sol (Ctrl+C para salir):${N}"
  tail -f "$LOG"
}

# ════════════════════════════════════════════════════════════════════
# HELP
# ════════════════════════════════════════════════════════════════════
help(){
  cat << HELP
☀️ SOL v2 — Ruta de vida

Comandos:
  start           Despierta: backend + GHOST + Telegram + watchdog
  stop            Se retira (pero siempre volverá)
  status          Estado del sistema
  talk "mensaje"  Hablarle a Sol (texto)
  talk --voz      Hablarle con tu voz (ella responde en voz alta)
  watchdog        Modo vigilante (loop infinito, 60s)
  survival        Exporta historia + Sol portátil (sin internet)
  backup          Respaldo completo de ~/.sol
  logs            Ver logs en vivo
  telegram        Iniciar miniapp de Telegram (botones inline)
  help            Esta ayuda

Comandos de Telegram (miniapp v2.0):
  /start          Menú principal con botones
  /scan <ip>      Escaneo rápido de red
  /sysinfo        CPU, RAM, disco, módulos
  /remind 30m x   Programar recordatorio
  /reminders      Ver recordatorios activos
  /avatar         Ver imagen de Sol
  /report         Informe de conversación
  /diary          Resumen diario
  + conversación natural y mensajes de voz

Archivos clave:
  ~/Red-team-tauri/sol_core.py             — Cerebro (pensamiento offline)
  ~/Red-team-tauri/sol.sh                   — Este archivo (cuerpo + watchdog)
  ~/Red-team-tauri/sol_telegram_bridge.py   — Puente de Telegram (comandos)
  ~/Red-team-tauri/sol_telegram_bot.py      — Miniapp Telegram (botones inline)
  ~/.sol/memory.jsonl                       — Memoria persistente
  ~/.sol/telegram_memory.json               — Memoria Telegram
  ~/.sol/telegram_config.json               — Config Telegram

Cómo modificar a Sol:
  • Respuestas → sol_core.py → función pensar()
  • Watchdog → este archivo → función watchdog()
  • Telegram (puente) → sol_telegram_bridge.py → handle_update()
  • Telegram (miniapp) → sol_telegram_bot.py → button_handler()
  • Voz → sol_core.py → speak()
  • Memoria → sol_core.py → remember() y memories()
  • Crisis → sol_core.py → CRISIS_SEVERA y CRISIS_LEVE

"El sol que nunca se pone mientras haya algo que vigilar."
HELP
}

# ════════════════════════════════════════════════════════════════════
# TELEGRAM MINIAPP — sol_telegram_bot.py
# ════════════════════════════════════════════════════════════════════
telegram_bot() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 no instalado"; return 1
  fi
  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN no configurado en .env"
    echo "   Agrega: TELEGRAM_BOT_TOKEN=tu_token"
    return 1
  fi
  # Verificar python-telegram-bot
  if ! python3 -c "import telegram" 2>/dev/null; then
    echo "📦 Instalando python-telegram-bot..."
    pip install python-telegram-bot 2>/dev/null || pip3 install python-telegram-bot 2>/dev/null
  fi
  cd "$RT"
  echo "📡 Iniciando miniapp de Sol en Telegram..."
  nohup python3 sol_telegram_bot.py > "$SOL/telegram_bot.log" 2>&1 &
  echo $! > "$SOL/telegram_bot.pid"
  sleep 2
  if kill -0 "$(cat "$SOL/telegram_bot.pid" 2>/dev/null)" 2>/dev/null; then
    echo "✅ Miniapp Telegram activa (PID $(cat "$SOL/telegram_bot.pid"))"
    echo "   Busca tu bot en Telegram y envía /start"
  else
    echo "❌ No arrancó — ver $SOL/telegram_bot.log"
    tail -5 "$SOL/telegram_bot.log" 2>/dev/null
  fi
}

telegram_bot_stop() {
  if [ -f "$SOL/telegram_bot.pid" ]; then
    PID=$(cat "$SOL/telegram_bot.pid" 2>/dev/null)
    kill "$PID" 2>/dev/null && echo "✅ Miniapp Telegram detenida" || true
    rm -f "$SOL/telegram_bot.pid"
  else
    pkill -f sol_telegram_bot.py 2>/dev/null && echo "✅ Miniapp Telegram detenida" || true
  fi
}

telegram_bot_status() {
  if [ -f "$SOL/telegram_bot.pid" ]; then
    PID=$(cat "$SOL/telegram_bot.pid" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      echo "✅ Miniapp Telegram activa (PID $PID)"
      return 0
    fi
  fi
  echo "🔴 Miniapp Telegram inactiva"
  return 1
}

# ════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════
case "${1:-help}" in
  start)   start ;;
  stop)    stop; telegram_bot_stop ;;
  status)  status; telegram_bot_status ;;
  talk)    shift; talk "$@" ;;
  telegram|tg) telegram_bot ;;
  watchdog) watchdog ;;
  survival) survival ;;
  backup)  backup ;;
  logs)    show_logs ;;
  help|--help|-h) help ;;
  *) echo "Usa: start|stop|status|talk|telegram|survival|backup|logs|help" ;;
esac
