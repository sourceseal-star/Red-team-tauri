#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SourceSeal Engine -- Termux
# Backend unico :8001 (FastAPI, sirve /api + /ws + /motor)
# Frontend Vite dev server :5173 (proxy /api,/ws,/canary -> :8001)
# =====================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PORT=8001
mkdir -p "$LOG_DIR"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; N='\033[0m'

echo ""
echo "+-------------------------------------------------+"
echo "|  SourceSeal Engine -- Termux                    |"
echo "|  Backend Python :$PORT + Vite :5173             |"
echo "+-------------------------------------------------+"
echo ""

# -- 0. Wake Lock -- IMPORTANTE: sin esto Android suspende/mata los
# procesos de Termux en segundo plano en cuanto cambias de app (ej. vas
# a Chrome). Esto es la causa mas comun de "el backend se cae solo" y
# de los loops de reinicio -- no es un bug del codigo, es Android.
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock
  echo -e "${G}[wake-lock] Activo -- Android no debería suspender Termux.${N}"
else
  echo -e "${Y}[wake-lock] NO disponible. Instala: pkg install termux-api${N}"
  echo -e "${Y}            Ademas, en Ajustes de Android -> Apps -> Termux -> Batería,${N}"
  echo -e "${Y}            pon 'Sin restricciones' o Android matará los procesos igual.${N}"
fi

# -- 1. Matar procesos anteriores --
# pkill funciona bien en Termux (lee /proc/<pid>/cmdline de procesos
# propios, misma UID). kill_port.py ya NO depende de /proc/net/tcp
# (bloqueado por Android 10+ para apps normales) -- ahora usa pkill -f
# por nombre + bind-test real para confirmar que el puerto quedo libre.
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
if command -v fuser >/dev/null 2>&1; then
  fuser -k ${PORT}/tcp 2>/dev/null || true
fi
python3 "$SCRIPT_DIR/redteam/scripts/kill_port.py" "$PORT" "dashboard_server.py" 5 2>/dev/null || true

# -- 2. Deps Python --
pip install -q fastapi uvicorn httpx psutil aiohttp 2>/dev/null || true

# -- 3. Deps Node --
cd "$SCRIPT_DIR/tauri-frontend"
if [ ! -d "node_modules" ]; then
  echo "Instalando dependencias Node.js..."
  npm install 2>&1 | tail -5
fi

# -- 4. Arrancar backend Python --
echo "Arrancando backend unificado en :$PORT ..."
cd "$SCRIPT_DIR/redteam/scripts"
export PORT=$PORT
export HOST=0.0.0.0
python3 dashboard_server.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  PID: $BACKEND_PID"

echo -n "  Esperando backend"
READY=0
for i in $(seq 1 20); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo ""
    echo -e "${R}X El backend murio al arrancar. Log:${N}"
    tail -20 "$LOG_DIR/backend.log"
    exit 1
  fi
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/api/health" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    BODY=$(curl -s "http://127.0.0.1:$PORT/api/health" 2>/dev/null || echo "")
    if echo "$BODY" | grep -q "red-team-tauri-unified"; then
      echo " OK (health=200, unified)"
      READY=1
      break
    fi
  fi
  sleep 1
  echo -n "."
done
if [ "$READY" != "1" ]; then
  echo ""
  echo -e "${R}X El backend no respondio. Log:${N}"
  tail -20 "$LOG_DIR/backend.log"
  exit 1
fi

# -- 5. Arrancar Vite --
echo "Arrancando Vite en :5173 ..."
cd "$SCRIPT_DIR/tauri-frontend"
npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "  PID: $FRONTEND_PID"

echo ""
echo "Sistema corriendo:"
echo "   -> Frontend: http://localhost:5173"
echo "   -> Backend:  http://localhost:$PORT (incluye /motor/* y /api/murcielago/*)"
echo ""
echo "   Logs: tail -f $LOG_DIR/backend.log"
echo "         tail -f $LOG_DIR/frontend.log"
echo ""

# NOTA: el Motor de Cierre YA NO se arranca como proceso separado en :8000.
# Esta fusionado como sub-app dentro de dashboard_server.py, montado en
# /motor/* dentro del backend unificado de arriba (:8001).

# -- 6. Watchdog con circuit-breaker --
# Si un servicio se cae mas de MAX_CRASHES veces dentro de CRASH_WINDOW
# segundos, se ASUME que hay un problema real (no algo pasajero) y se
# DEJA de reintentar -- en vez de spamear la terminal en loop infinito
# sin que el usuario se entere de la causa real. Se imprime el log en
# cada caida para que la causa (traceback, OOM, "address in use", etc.)
# sea visible de inmediato.
MAX_CRASHES=5
CRASH_WINDOW=60
backend_crash_times=()
frontend_crash_times=()
backend_dead=0
frontend_dead=0

cleanup() {
  echo ""
  echo "Cerrando servicios..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  pkill -f "dashboard_server.py" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
  exit 0
}
trap cleanup SIGTERM SIGINT

_prune_old() {
  # Elimina de un array (por nombre, via nameref) las marcas de tiempo
  # mas viejas que CRASH_WINDOW segundos.
  local -n arr="$1"
  local now=$(date +%s)
  local kept=()
  for t in "${arr[@]}"; do
    if (( now - t < CRASH_WINDOW )); then
      kept+=("$t")
    fi
  done
  arr=("${kept[@]}")
}

while true; do
  if [ "$backend_dead" != "1" ] && ! kill -0 $BACKEND_PID 2>/dev/null; then
    now=$(date +%s)
    backend_crash_times+=("$now")
    _prune_old backend_crash_times
    echo -e "${R}[watch] Backend caido. Log reciente:${N}"
    tail -15 "$LOG_DIR/backend.log"

    if [ "${#backend_crash_times[@]}" -ge "$MAX_CRASHES" ]; then
      echo -e "${R}[watch] Backend se cayo ${#backend_crash_times[@]} veces en ${CRASH_WINDOW}s.${N}"
      echo -e "${R}[watch] DETENIENDO auto-reinicio del backend -- esto ya no es normal.${N}"
      echo -e "${Y}[watch] Revisa: tail -50 $LOG_DIR/backend.log${N}"
      echo -e "${Y}[watch] Si NO ves un traceback de Python, es Android matando el proceso:${N}"
      echo -e "${Y}[watch]   -> Ajustes -> Apps -> Termux -> Batería -> Sin restricciones${N}"
      echo -e "${Y}[watch]   -> No cierres Termux desde 'Apps recientes' (eso SI mata todo)${N}"
      echo -e "${Y}[watch] Corrige y vuelve a correr: bash start-termux.sh${N}"
      backend_dead=1
    else
      python3 "$SCRIPT_DIR/redteam/scripts/kill_port.py" "$PORT" "dashboard_server.py" 5 2>/dev/null || true
      cd "$SCRIPT_DIR/redteam/scripts"
      python3 dashboard_server.py >> "$LOG_DIR/backend.log" 2>&1 &
      BACKEND_PID=$!
      echo -e "${G}[watch] Backend reiniciado. Nuevo PID: $BACKEND_PID${N}"
    fi
  fi

  if [ "$frontend_dead" != "1" ] && ! kill -0 $FRONTEND_PID 2>/dev/null; then
    now=$(date +%s)
    frontend_crash_times+=("$now")
    _prune_old frontend_crash_times
    echo -e "${R}[watch] Frontend caido. Log reciente:${N}"
    tail -15 "$LOG_DIR/frontend.log"

    if [ "${#frontend_crash_times[@]}" -ge "$MAX_CRASHES" ]; then
      echo -e "${R}[watch] Frontend se cayo ${#frontend_crash_times[@]} veces en ${CRASH_WINDOW}s.${N}"
      echo -e "${R}[watch] DETENIENDO auto-reinicio del frontend.${N}"
      echo -e "${Y}[watch] Revisa: tail -50 $LOG_DIR/frontend.log${N}"
      frontend_dead=1
    else
      python3 "$SCRIPT_DIR/redteam/scripts/kill_port.py" 5173 "vite" 5 2>/dev/null || true
      cd "$SCRIPT_DIR/tauri-frontend"
      npm run dev >> "$LOG_DIR/frontend.log" 2>&1 &
      FRONTEND_PID=$!
      echo -e "${G}[watch] Frontend reiniciado. Nuevo PID: $FRONTEND_PID${N}"
    fi
  fi

  if [ "$backend_dead" = "1" ] && [ "$frontend_dead" = "1" ]; then
    echo -e "${R}[watch] Ambos servicios detenidos permanentemente. Saliendo del watchdog.${N}"
    echo -e "${Y}[watch] Los procesos (si alguno quedo vivo) siguen corriendo. Usa Ctrl+C para cerrar todo.${N}"
    break
  fi

  sleep 5
done

# Se sale del watchdog pero el script sigue vivo para que Ctrl+C limpie
# correctamente si el usuario quiere cerrar todo.
wait
