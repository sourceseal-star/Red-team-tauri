#!/bin/bash
# SourceSeal — Launcher Unificado

echo "========================================="
echo "   SourceSeal Console Launcher"
echo "========================================="

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Variables
export API_KEY="${API_KEY:-tu-clave-secreta-123}"
export PORT=8001

# 2. Verificar backend
echo -e "${YELLOW}[1/3]${NC} Verificando backend..."
if [ ! -f "motor_cierre/backend/main.py" ]; then
    echo -e "${RED}[!] main.py no encontrado en motor_cierre/backend/${NC}"
    exit 1
fi

# 3. Levantar backend en background
echo -e "${YELLOW}[2/3]${NC} Levantando Motor de Cierre en puerto $PORT..."
cd motor_cierre/backend
python main.py > ../../backend.log 2>&1 &
BACKEND_PID=$!
cd ../..

# Esperar a que el backend responda
echo "    Esperando backend..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -s http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}[OK] Backend online en http://127.0.0.1:$PORT${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}[!] Backend no respondio. Revisa backend.log${NC}"
        exit 1
    fi
done

# 4. Levantar frontend
echo -e "${YELLOW}[3/3]${NC} Levantando frontend..."
cd tauri-frontend
npm run preview > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}[OK] TODO LEVANTADO${NC}"
echo "   Backend:   http://127.0.0.1:$PORT"
echo "   Frontend:  http://localhost:4173"
echo "   Logs:      backend.log | frontend.log"
echo ""
echo "   PIDs: Backend=$BACKEND_PID Frontend=$FRONTEND_PID"
echo ""
echo "Presiona Ctrl+C para detener todo"

# 5. Trap para limpieza
trap "echo ''; echo '[!] Deteniendo...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
