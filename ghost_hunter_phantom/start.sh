#!/bin/bash
# =====================================================================
# GHOST HUNTER v3.0 PHANTOM — Script de ejecución
# Arranca Master (:8002) + N nodos workers
# Se integra con el backend SourceSeal en :8001
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ─── Config ─────────────────────────────────────────────
BACKEND_API="${BACKEND_API:-http://localhost:8001}"
MASTER_PORT="${MASTER_PORT:-8002}"
NUM_NODES="${NUM_NODES:-1}"
MODE="${1:-all}"  # master | node | all

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  GHOST HUNTER v3.0 PHANTOM — Iniciando                 ║"
echo "║  Backend: $BACKEND_API"
echo "║  Master:  :$MASTER_PORT"
echo "║  Nodos:   $NUM_NODES"
echo "║  Modo:    $MODE"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# ─── Verificar dependencias Python ──────────────────────
check_deps() {
    local missing=()
    for pkg in fastapi uvicorn httpx websockets pydantic; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            missing+=("$pkg")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        echo "[ghost] Instalando dependencias: ${missing[*]}"
        pip install "${missing[@]}" 2>&1 | tail -5
    fi
}

# ─── Verificar backend ──────────────────────────────────
check_backend() {
    local HTTP_CODE
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_API/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[ghost] ✅ Backend disponible en $BACKEND_API"
    else
        echo "[ghost] ⚠️  Backend no responde en $BACKEND_API (HTTP $HTTP_CODE)"
        echo "[ghost]    Los hallazgos se guardarán localmente (phantom_retry.json)"
    fi
}

# ─── Arrancar Master ────────────────────────────────────
start_master() {
    echo "[ghost] Arrancando Master en :$MASTER_PORT..."
    export BACKEND_API="$BACKEND_API"
    export MASTER_PORT="$MASTER_PORT"
    python3 master.py &
    MASTER_PID=$!
    echo "[ghost] Master PID: $MASTER_PID"

    # Esperar a que el master esté listo
    for i in $(seq 1 15); do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$MASTER_PORT/api/status" 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ]; then
            echo "[ghost] ✅ Master listo en :$MASTER_PORT"
            return 0
        fi
        sleep 1
    done
    echo "[ghost] ❌ Master no respondió tras 15s"
    return 1
}

# ─── Arrancar Nodos ─────────────────────────────────────
start_nodes() {
    local n=$NUM_NODES
    for i in $(seq 1 $n); do
        local NODE_ID="phantom_node_$i"
        echo "[ghost] Arrancando nodo $i/$n ($NODE_ID)..."
        NODE_ID="$NODE_ID" \
        MASTER_URL="http://localhost:$MASTER_PORT" \
        BACKEND_API="$BACKEND_API" \
        python3 node.py &
        echo "[ghost] Nodo $i PID: $!"
        sleep 0.5
    done
}

# ─── Cleanup ────────────────────────────────────────────
cleanup() {
    echo ""
    echo "[ghost] Apagando GHOST HUNTER PHANTOM..."
    pkill -f "ghost_hunter_phantom/master.py" 2>/dev/null || true
    pkill -f "ghost_hunter_phantom/node.py" 2>/dev/null || true
    echo "[ghost] ✅ Apagado completo"
    exit 0
}
trap cleanup SIGTERM SIGINT

# ─── Ejecución ───────────────────────────────────────────
check_deps
check_backend

case "$MODE" in
    master)
        start_master
        echo ""
        echo "[ghost] Master corriendo. Presiona Ctrl+C para detener."
        wait $MASTER_PID
        ;;
    node)
        echo "[ghost] Arrancando nodo standalone (conecta a Master)..."
        NODE_ID="${NODE_ID:-phantom_node_$$}" \
        MASTER_URL="${MASTER_URL:-http://localhost:$MASTER_PORT}" \
        BACKEND_API="$BACKEND_API" \
        python3 node.py
        ;;
    all)
        start_master
        start_nodes
        echo ""
        echo "╔═══════════════════════════════════════════════════════╗"
        echo "║  GHOST HUNTER PHANTOM — Sistema activo                 ║"
        echo "║  Master:   http://localhost:$MASTER_PORT/api/status"
        echo "║  Backend:  $BACKEND_API/api/health"
        echo "║  Endpoints: /api/hunt/start, /api/tasks, /api/status  ║"
        echo "║  WS:        ws://localhost:$MASTER_PORT/ws/nodes       ║"
        echo "╚═══════════════════════════════════════════════════════╝"
        echo ""
        echo "[ghost] Presiona Ctrl+C para detener todo."
        wait
        ;;
    *)
        echo "Uso: $0 [master|node|all]"
        echo "  master  — Solo el orquestador Master (:8002)"
        echo "  node    — Solo un nodo worker (conecta a Master)"
        echo "  all     — Master + $NUM_NODES nodos (recomendado)"
        exit 1
        ;;
esac
