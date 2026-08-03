#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal / Red-team-tauri — Inicio para Termux
# Backend ACTUAL: Python FastAPI (backend/main.py) — v2.0.0 Pro
# =====================================================
#
# NOTA IMPORTANTE:
# Este repo acumuló 3 generaciones de código durante su desarrollo:
#   1. server.js + tauri-frontend/  → LEGACY (Node.js, versión anterior)
#   2. redteam/                     → Toolkit paralelo, NO es esta app
#   3. backend/main.py + lib/       → ACTUAL (v2.0.0 Pro) — esto es lo que arranca este script
#
# Si buscas el servidor Node.js legacy, usa: start-termux-legacy-nodejs.sh
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   SourceSeal Engine — Backend v2.0.0     ║"
echo "║   Modo Termux (Android)                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Matar procesos anteriores del backend ──────────
pkill -f "python.*main.py" 2>/dev/null
pkill -f "python3.*main.py" 2>/dev/null
sleep 1

# ── Instalar dependencias si falta algo ─────────────
cd "$SCRIPT_DIR/backend"
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "📦 Instalando dependencias Python (primera vez)..."
  pip install -r requirements.txt
fi

# ── Arrancar backend ─────────────────────────────────
echo "🔧 Arrancando backend en http://127.0.0.1:8000 ..."
PORT=8000 HOST=0.0.0.0 python3 main.py > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  PID backend: $BACKEND_PID"

# Esperar que el backend responda
echo -n "  Esperando backend"
READY=0
for i in $(seq 1 15); do
  sleep 1
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 "http://127.0.0.1:8000/" 2>/dev/null)
  if [ "$CODE" = "200" ]; then
    echo " ✅"
    READY=1
    break
  fi
  echo -n "."
done

if [ "$READY" != "1" ]; then
  echo ""
  echo "❌ El backend no respondió a tiempo. Revisa el log:"
  echo "   cat $LOG_DIR/backend.log"
  exit 1
fi

echo ""
echo "🌐 Backend operativo:"
echo "   API:     http://127.0.0.1:8000"
echo "   Swagger: http://127.0.0.1:8000/docs"
echo ""
echo "⚡ Abre Chrome y ve a: http://127.0.0.1:8000/docs"
echo "   Presiona Ctrl+C para detener"
echo ""

# Mantener el script vivo mostrando logs, hasta Ctrl+C
trap "echo ''; echo 'Deteniendo backend...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM
tail -f "$LOG_DIR/backend.log"
