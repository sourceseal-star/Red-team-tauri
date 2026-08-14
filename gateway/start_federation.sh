#!/bin/bash
# SourceSeal Federation Launcher

echo "========================================="
echo "   SourceSeal Federation Launcher"
echo "========================================="

# 1. Verificar dependencias
command -v python >/dev/null 2>&1 || { echo "Python no instalado"; exit 1; }
command -v cloudflared >/dev/null 2>&1 && echo "[OK] Cloudflared listo" || echo "[!] Instala cloudflared: pkg install cloudflared"

# 2. Variables
export API_KEY="${API_KEY:-tu-clave-maestra-federada}"
export NODE_MOTOR_URL="${NODE_MOTOR_URL:-https://tu-motor.replit.app}"
export NODE_MOTOR_KEY="${NODE_MOTOR_KEY:-clave-del-motor}"
export NODE_FRONTEND_URL="${NODE_FRONTEND_URL:-https://tu-frontend.replit.app}"
export NODE_INTEL_URL="${NODE_INTEL_URL:-}"
export NODE_INTEL_KEY="${NODE_INTEL_KEY:-}"

# 3. Iniciar Orchestrator
echo "[+] Iniciando Orchestrator en puerto 9000..."
python orchestrator.py &
ORCH_PID=$!

# 4. Iniciar tunnel (si cloudflared existe)
if command -v cloudflared >/dev/null 2>&1; then
    echo "[+] Iniciando Cloudflare Tunnel..."
    cloudflared tunnel --url http://localhost:9000 &
    TUNNEL_PID=$!
    echo "[+] Tunnel PID: $TUNNEL_PID"
fi

# 5. Iniciar servicios locales
echo "[+] Iniciando Dashboard Server..."
python ../redteam/scripts/dashboard_server.py &
DASH_PID=$!

echo ""
echo "[OK] Federacion activa"
echo "   Orchestrator: http://localhost:9000"
echo "   Dashboard:    http://localhost:8001"
echo ""
echo "Presiona Ctrl+C para detener todo"

# 6. Trap para limpieza
trap "echo ''; echo '[!] Deteniendo servicios...'; kill $ORCH_PID $DASH_PID ${TUNNEL_PID:-} 2>/dev/null; exit" INT TERM

wait
