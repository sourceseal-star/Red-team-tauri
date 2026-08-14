#!/bin/bash
# start_orchestrator.sh — Inicia el Nodo Maestro Termux
cd "$(dirname "$0")"

echo "=== Termux Orchestrator — Nodo Maestro ==="
echo ""

# Verificar dependencias Python
python3 -c "import fastapi" 2>/dev/null || pip install fastapi uvicorn

# Variables de entorno (editar segun tu setup)
export PORT=8080
export DB_PATH="./master.db"

# URLs de los Replits (cambiar por tus URLs reales)
export REPLIT_MOTOR_URL="${REPLIT_MOTOR_URL:-http://localhost:8000}"
export REPLIT_FRONTEND_URL="${REPLIT_FRONTEND_URL:-http://localhost:5173}"
export REPLIT_THREAT_URL="${REPLIT_THREAT_URL:-http://localhost:8001}"

# URL del tunel (cambiar por la tuya)
export TUNNEL_URL="${TUNNEL_URL:-}"
export TUNNEL_DOMAIN="${TUNNEL_DOMAIN:-tu-subdomain.trycloudflare.com}"

echo "[*] Orchestrator: http://localhost:$PORT"
echo "[*] Tunnel: $TUNNEL_DOMAIN"
echo ""

python3 orchestrator.py
