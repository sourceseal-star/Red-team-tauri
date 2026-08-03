#!/data/data/com.termux/files/usr/bin/bash
# =====================================================
# SourceSeal Console — Inicio LEGACY (Node.js + Vite)
# ⚠️  ESTO ES LA VERSIÓN ANTERIOR (v1) — NO es el backend actual.
# El backend actual es Python FastAPI: usa start-termux.sh
# =====================================================
# Modo: build estático (sin inotify, sin watchers)
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/tauri-frontend"
LOG_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOG_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     SourceSeal Red-team Console          ║"
echo "║     Modo Termux (Android) — LEGACY       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Pedir API key si no está seteada ──────────────
if [ -z "$REDTEAM_API_KEY" ]; then
  read -rp "🔑 API Key del backend: " REDTEAM_API_KEY
  export REDTEAM_API_KEY
fi

echo "🔧 Arrancando backend..."

# ── Instalar deps de Node si faltan (npm install se olvida seguido) ──
cd "$SCRIPT_DIR"
if [ ! -d "node_modules" ] || [ ! -d "node_modules/axios" ]; then
  echo "📦 Instalando dependencias Node.js (falta node_modules o axios)..."
  npm install
fi

# ── Matar procesos anteriores ──────────────────────
pkill -f "node server.js" 2>/dev/null
sleep 1

# ── Backend ────────────────────────────────────────
cd "$SCRIPT_DIR"
node server.js > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  PID backend: $BACKEND_PID"

# Esperar que el backend responda
echo -n "  Esperando backend"
for i in $(seq 1 10); do
  sleep 1
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 1 \
    -H "Authorization: Bearer $REDTEAM_API_KEY" \
    "http://127.0.0.1:3000/api/status" 2>/dev/null)
  if [ "$CODE" = "200" ]; then
    echo " ✅"
    break
  fi
  echo -n "."
done

# ── Frontend — build estático ──────────────────────
cd "$FRONTEND_DIR"

# Build si no existe o si el código cambió
if [ ! -d "dist" ] || [ "$(find src -newer dist/index.html 2>/dev/null | wc -l)" -gt 0 ]; then
  echo ""
  echo "🔨 Compilando frontend (primera vez o cambios detectados)..."
  npx vite build 2>&1 | tail -5
  echo "  Build completo ✅"
fi

# Servir el build con vite preview (sin watchers, sin inotify)
echo ""
echo "🌐 Sirviendo dashboard en http://localhost:5173"
echo "   (también en http://$(hostname -I | awk '{print $1}'):5173)"
echo ""
echo "⚡ Abre Chrome y ve a: http://localhost:5173"
echo "   Presiona Ctrl+C para detener"
echo ""

# Asegurarse de que el BACKEND_URL llegue al frontend
export VITE_API_URL="http://127.0.0.1:3000"

npx vite preview --host 0.0.0.0 --port 5173

# Al salir, matar backend
kill $BACKEND_PID 2>/dev/null
echo "Backend detenido."
