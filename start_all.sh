#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# start-all.sh — Arranque completo de todos los servicios
# ============================================================
#   bash start-all.sh           → Dashboard + Nexus
#   bash start-all.sh --ai      → Dashboard + Nexus + AI Orchestrator
#   bash start-all.sh --phantom → Dashboard + Nexus + GHOST HUNTER PHANTOM
#   bash start-all.sh --full    → Todo
# ============================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; R='\033[0;31m'; N='\033[0m'

# Flags
WITH_AI=false
WITH_PHANTOM=false
WITH_NEXUS=true
for arg in "$@"; do
  case "$arg" in
    --ai) WITH_AI=true ;;
    --phantom) WITH_PHANTOM=true ;;
    --full) WITH_AI=true; WITH_PHANTOM=true ;;
    --no-nexus) WITH_NEXUS=false ;;
    --help|-h)
      echo "Uso: bash start-all.sh [--ai] [--phantom] [--full] [--no-nexus]"
      echo "  --ai      Inicia AI Orchestrator"
      echo "  --phantom Inicia GHOST HUNTER PHANTOM"
      echo "  --full    Inicia todo"
      echo "  --no-nexus No inicia Nexus OSINT"
      exit 0 ;;
  esac
done

echo ""
echo -e "${C}╔═══════════════════════════════════════════════════════╗${N}"
echo -e "${C}║  SOURCESEAL — ARRANQUE COMPLETO                        ║${N}"
echo -e "${C}║  Dashboard :8001 | Nexus :8004 | PHANTOM :8002       ║${N}"
echo -e "${C}╚═══════════════════════════════════════════════════════╝${N}"
echo ""

# Deps
for pkg in fastapi uvicorn httpx websockets; do
  python3 -c "import $pkg" 2>/dev/null || pip install "$pkg" 2>&1 | tail -1
done

# .env
if [ -f "$ROOT/.env" ]; then
  set -a; . "$ROOT/.env"; set +a
fi

export PYTHONUNBUFFERED=1
export COMMANDER_DIR="${COMMANDER_DIR:-$ROOT/commander}"
if [ ! -f "$COMMANDER_DIR/ai_orchestrator.py" ] && [ -f "$ROOT/commander/ai_orchestrator.py" ]; then
  export COMMANDER_DIR="$ROOT/commander"
fi

# PYTHONPATH: para que el backend completo encuentre leviathan_core, kraken, commander, modules, etc.
export PYTHONPATH="$ROOT:$ROOT/redteam/scripts:$ROOT/leviathan_core:$ROOT/kraken:$ROOT/commander:${PYTHONPATH:-}"

PIDS=()

# 1. Dashboard (:8001) — Backend completo (231 rutas)
echo -e "${G}[1] Dashboard en :8001 (backend completo: redteam/scripts/dashboard_server.py)...${N}"
pkill -f "dashboard_server.py" 2>/dev/null || true
sleep 1
cd "$ROOT/redteam/scripts"
nohup python3 "$ROOT/redteam/scripts/dashboard_server.py" > "$HOME/dashboard.log" 2>&1 &
DASH_PID=$!
PIDS+=("$DASH_PID")
cd "$ROOT"

for i in $(seq 1 15); do
  curl -s http://127.0.0.1:8001/api/health >/dev/null 2>&1 && break
  sleep 1
done

if curl -s http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
  echo -e "  ${G}✅ Dashboard online${N}"
  # Verificar AI Orchestrator (FastAPI serializa sin espacios: "available":true)
  if curl -s -H "X-Api-Key: ${REDTEAM_API_KEY:-}" http://127.0.0.1:8001/api/commander/ai/status 2>/dev/null | grep -qE '"available"[[:space:]]*:[[:space:]]*true'; then
    echo -e "  ${G}✅ AI Orchestrator disponible en /api/commander/ai/*${N}"
  else
    echo -e "  ${Y}⚠️  AI Orchestrator no disponible${N}"
  fi
  # Verificar frontend visual compilado
  if curl -s http://127.0.0.1:8001/ 2>/dev/null | grep -qi '<div id="root">'; then
    echo -e "  ${G}✅ Dashboard visual compilado y servido${N}"
  else
    echo -e "  ${Y}⚠️  Frontend no compilado — verás JSON en vez del dashboard visual${N}"
    echo -e "  ${Y}     Ejecuta: cd tauri-frontend && npm install --legacy-peer-deps && npm run build${N}"
  fi
else
  echo -e "  ${R}❌ Dashboard no respondió. Ver $HOME/dashboard.log${N}"
  tail -5 "$HOME/dashboard.log" 2>/dev/null
fi

# 2. Nexus OSINT (:8004)
if [ "$WITH_NEXUS" = true ] && [ -f "$ROOT/nexus_omni_v9.py" ]; then
  echo -e "${G}[2] Nexus OSINT en :8004...${N}"
  pkill -f "nexus_omni_v9.py" 2>/dev/null || true
  nohup python3 "$ROOT/nexus_omni_v9.py" > "$HOME/nexus.log" 2>&1 &
  NEXUS_PID=$!
  PIDS+=("$NEXUS_PID")
  sleep 2
  if curl -s http://127.0.0.1:8004/ >/dev/null 2>&1; then
    echo -e "  ${G}✅ Nexus online${N}"
  else
    echo -e "  ${Y}⚠️  Nexus iniciando (ver $HOME/nexus.log)${N}"
  fi
fi

# 3. GHOST HUNTER PHANTOM (:8002)
if [ "$WITH_PHANTOM" = true ] && [ -f "$ROOT/ghost_hunter_phantom/start.sh" ]; then
  echo -e "${G}[3] GHOST HUNTER PHANTOM en :8002...${N}"
  pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
  pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
  cd "$ROOT/ghost_hunter_phantom"
  nohup python3 master.py > "$HOME/phantom.log" 2>&1 &
  PHANTOM_PID=$!
  PIDS+=("$PHANTOM_PID")
  sleep 1
  nohup env NODE_ID="phantom_01" MASTER_URL="http://localhost:8002" \
    BACKEND_API="http://localhost:8001" python3 node.py >> "$HOME/phantom.log" 2>&1 &
  PIDS+=("$!")
  cd "$ROOT"
  echo -e "  ${G}✅ PHANTOM iniciado${N}"
fi

# 4. AI Orchestrator (modo --once o continuo)
if [ "$WITH_AI" = true ] && [ -f "$COMMANDER_DIR/ai_orchestrator.py" ]; then
  echo -e "${G}[4] AI Orchestrator...${N}"
  if [ -n "${LLM_API_KEY:-}" ]; then
    echo -e "  ${G}IA activa (LLM_API_KEY configurada)${N}"
    nohup python3 "$COMMANDER_DIR/ai_orchestrator.py" \
      --network "${TARGET_NETWORK:-192.168.1.0/24}" \
      > "$HOME/ai_orch.log" 2>&1 &
  else
    echo -e "  ${Y}Modo offline (sin LLM_API_KEY)${N}"
    nohup python3 "$COMMANDER_DIR/ai_orchestrator.py" \
      --no-ai --once \
      --network "${TARGET_NETWORK:-192.168.1.0/24}" \
      > "$HOME/ai_orch.log" 2>&1 &
  fi
  PIDS+=("$!")
  echo -e "  ${G}✅ AI Orchestrator iniciado${N}"
fi

# 5. Telegram (si está configurado)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  SVC="Dashboard✅"
  [ "$WITH_NEXUS" = true ] && SVC="${SVC} Nexus✅"
  [ "$WITH_PHANTOM" = true ] && SVC="${SVC} PHANTOM✅"
  [ "$WITH_AI" = true ] && SVC="${SVC} AI✅"
  MSG=$(printf "SourceSeal iniciado\n%s\nDashboard: http://localhost:8001" "$SVC")
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" -d text="$MSG" >/dev/null 2>&1
  echo -e "${G}Telegram notificado${N}"
fi

echo ""
echo -e "${G}╔═══════════════════════════════════════════════════════╗${N}"
echo -e "${G}║  SERVICIOS ACTIVOS                                     ║${N}"
echo -e "${G}║  Dashboard:  http://localhost:8001                      ║${N}"
[ "$WITH_NEXUS" = true ] && echo -e "${G}║  Nexus:     http://localhost:8004                      ║${N}"
[ "$WITH_PHANTOM" = true ] && echo -e "${G}║  PHANTOM:   http://localhost:8002/api/status          ║${N}"
echo -e "${G}║  Logs:      ~/dashboard.log | ~/nexus.log              ║${N}"
[ "$WITH_PHANTOM" = true ] && echo -e "${G}║             ~/phantom.log                              ║${N}"
[ "$WITH_AI" = true ] && echo -e "${G}║  AI Orch:   ~/ai_orch.log                             ║${N}"
echo -e "${G}╚═══════════════════════════════════════════════════════╝${N}"
echo ""
echo -e "${Y}Ctrl+C para detener todo${N}"

trap "echo ''; echo '[stop] Deteniendo...'; kill ${PIDS[*]} 2>/dev/null; exit" INT TERM
wait
