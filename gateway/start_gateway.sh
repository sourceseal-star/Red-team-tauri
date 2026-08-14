#!/bin/bash
# start_gateway.sh — Inicia el API Gateway Mesh
cd "$(dirname "$0")"

echo "=== API Gateway Mesh ==="
echo ""

# Verificar dependencias
python3 -c "import fastapi" 2>/dev/null || pip install fastapi uvicorn websockets

# Iniciar gateway
python3 mesh_server.py
