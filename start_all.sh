#!/bin/bash
# SourceSeal — Launcher Unificado (dev mode)
# Usa npm run dev en vez de preview para ver errores en el navegador

echo "========================================="
echo "   SourceSeal Console Launcher"
echo "========================================="

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Variables
export API_KEY="${API_KEY:-tu-clave-secreta-123}"
export PORT=8001

# 2. Verificar backend
echo -e "${YELLOW}[1/3]${NC} Verificando backend..."
if [ ! -f "redteam/scripts/dashboard_server.py" ]; then
    echo -e "${RED}[!] dashboard_server.py no encontrado${NC}"
    exit 1
fi

# 3. Levantar backend UNIFICADO (dashboard_server.py incluye motor_cierre
# como sub-app en /motor/* + todos los endpoints de escaneo/camaras/etc)
echo -e "${YELLOW}[2/3]${NC} Levantando backend unificado en puerto $PORT..."
cd redteam/scripts
python3 dashboard_server.py > ../../backend.log 2>&1 &
BACKEND_PID=$!
cd ../..

echo "    Esperando backend..."
BACKEND_OK=0
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -s http://127.0.0.1:$PORT/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}[OK] Backend online en http://127.0.0.1:$PORT${NC}"
        BACKEND_OK=1
        break
    fi
done
if [ "$BACKEND_OK" -eq 0 ]; then
    echo -e "${RED}[!] Backend no respondio. Revisa backend.log:${NC}"
    tail -20 backend.log
    exit 1
fi

# 4. Levantar frontend en modo dev (muestra errores en el navegador)
echo -e "${YELLOW}[3/3]${NC} Levantando frontend (dev mode)..."
cd tauri-frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 3

echo ""
echo -e "${GREEN}[OK] TODO LEVANTADO${NC}"
echo "   Backend:   http://127.0.0.1:$PORT"
echo "   Frontend:  http://localhost:5173"
echo "   Logs:      backend.log | frontend.log"
echo ""
echo "   PIDs: Backend=$BACKEND_PID Frontend=$FRONTEND_PID"
echo ""
echo "   Si ves pantalla blanca, abre F12 en el navegador"
echo "   y mira la consola — dev mode muestra los errores."
echo ""
echo "Presiona Ctrl+C para detener todo"

trap "echo ''; echo '[!] Deteniendo...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
