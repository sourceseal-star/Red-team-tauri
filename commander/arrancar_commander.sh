#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# COMMANDER Dashboard — Arranque en Termux
# Puerto :8003 — Dashboard web unificado de COMMANDER
# Se conecta a Red-team-tauri (:8001) y PHANTOM (:8002)
# =====================================================================

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ─── Cargar .env de la raiz del repo (para SMTP, Telegram, OSINT keys) ──
# Commander vive en un subdirectorio y se arranca independiente del backend
# principal, asi que nunca heredaba las variables de .env. Sin esto,
# SMTP_SENDER_EMAIL/PASSWORD y demas quedaban vacias aunque estuvieran en .env.
REPO_ROOT="$(dirname "$ROOT")"
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    . "$REPO_ROOT/.env"
    set +a
    echo "[commander] .env cargado desde $REPO_ROOT/.env"
else
    echo "[commander][WARN] No se encontro .env en $REPO_ROOT — SMTP/Telegram/OSINT usaran valores por defecto (vacios)."
fi

PORT=8003
BACKEND_API="${BACKEND_API:-http://localhost:8001}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  COMMANDER Dashboard v1.0 — Iniciando en :$PORT           ║"
echo "║  → Red-team-tauri: $BACKEND_API"
echo "║  → PHANTOM Master:  http://localhost:8002             ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ─── Cleanup previo ──────────────────────────────────────
pkill -f "commander_server.py" 2>/dev/null || true
sleep 1

# ─── Verificar dependencias Python ───────────────────────
if ! "$PYTHON_BIN" -c "import cryptography, fastapi, httpx, pydantic, uvicorn" 2>/dev/null; then
    echo "[commander] Instalando dependencias Python..."
    "$PYTHON_BIN" -m pip install -r "$ROOT/requirements.txt"
fi

# ─── Arrancar ────────────────────────────────────────────
echo "[commander] Arrancando dashboard en :$PORT..."
COMMANDER_PORT=$PORT BACKEND_API="$BACKEND_API" "$PYTHON_BIN" "$ROOT/commander_server.py" &
CMD_PID=$!
echo "[commander] PID: $CMD_PID"

# ─── Verificar ───────────────────────────────────────────
for i in $(seq 1 15); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[commander] ✅ Dashboard listo en http://localhost:$PORT"
        break
    fi
    sleep 1
done

echo ""
echo "[commander] Dashboard COMMANDER: http://localhost:$PORT"
echo "[commander] Red-team-tauri:     http://localhost:8001"
echo "[commander] PHANTOM Master:     http://localhost:8002/api/status"
echo ""

# Cleanup
cleanup() {
    echo "[commander] Apagando..."
    kill $CMD_PID 2>/dev/null || true
    pkill -f "commander_server.py" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

wait

