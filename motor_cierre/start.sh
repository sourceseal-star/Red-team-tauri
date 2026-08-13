#!/bin/bash
# =====================================================================
# MOTOR DE CIERRE AUTÓNOMO v2.0 — Arranque independiente
# Backend FastAPI en puerto 8000 (separado del dashboard principal :8001)
# =====================================================================
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/backend"

# Crear .env si no existe
if [ ! -f .env ]; then
    echo "[motor_cierre] Copiando .env.example a .env..."
    cp .env.example .env
    echo "[motor_cierre] ⚠️  Edita .env con tus claves reales (Stripe, OpenAI, API_KEY)"
fi

# Instalar dependencias Python
echo "[motor_cierre] Instalando dependencias..."
pip install -r requirements.txt -q 2>&1 | tail -3

# Puerto
PORT="${MOTOR_CIERRE_PORT:-8000}"

# Matar procesos zombie en el puerto
pkill -f "uvicorn.*8000" 2>/dev/null || true

echo ""
echo "============================================"
echo "  MOTOR DE CIERRE AUTÓNOMO v2.0"
echo "  Puerto: $PORT"
echo "  Independiente del dashboard principal"
echo "============================================"
echo ""

# Arrancar
exec python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
