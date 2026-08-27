#!/bin/bash
# =====================================================================
# sync.sh — Sincroniza y reinicia el sistema unificado
# Funciona igual en Replit y en Termux. Detecta el entorno solo.
# Uso:  bash sync.sh
# =====================================================================
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "════════════════════════════════════════════════════════"
echo "  SYNC — Red-Team-Tauri / SourceSeal"
echo "════════════════════════════════════════════════════════"

# ── 1. Traer lo último de GitHub ──────────────────────────────────────
echo "[sync] git fetch + reset --hard origin/main..."
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "[sync] Ya estás en el último commit: $LOCAL"
else
  echo "[sync] Actualizando $LOCAL → $REMOTE"
  git reset --hard origin/main
fi
echo "[sync] Commit actual: $(git log --oneline -1)"

# ── 2. Detectar entorno y usar el script de arranque correcto ────────
if [ -d "/data/data/com.termux" ]; then
  echo "[sync] Entorno detectado: Termux"
  START_SCRIPT="./start-termux.sh"
else
  echo "[sync] Entorno detectado: Replit / Linux"
  START_SCRIPT="./replit_start.sh"
fi

# ── 3. Matar procesos viejos ANTES de reconstruir ─────────────────────
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# ── 4. Rebuild frontend (por si cambió CSS/TSX) ───────────────────────
echo "[sync] Reconstruyendo frontend..."
cd "$ROOT/tauri-frontend"
npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -3
npm run build 2>&1 | tail -5
cd "$ROOT"

# ── 5. Arrancar todo con el script del entorno ────────────────────────
echo "[sync] Arrancando con $START_SCRIPT ..."
echo "════════════════════════════════════════════════════════"
exec bash "$START_SCRIPT"
