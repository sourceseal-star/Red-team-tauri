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
echo -e "${YELLOW}[1/4]${NC} Verificando backend..."
if [ ! -f "motor_cierre/backend/main.py" ]; then
    echo -e "${RED}[!] main.py no encontrado en motor_cierre/backend/${NC}"
    exit 1
fi

# 3. Levantar backend en background
echo -e "${YELLOW}[2/4]${NC} Levantando Motor de Cierre en puerto $PORT..."
cd motor_cierre/backend
python main.py > ../../backend.log 2>&1 &
BACKEND_PID=$!
cd ../..

# Esperar a que el backend responda
echo "    Esperando backend..."
BACKEND_OK=0
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -s http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}[OK] Backend online en http://127.0.0.1:$PORT${NC}"
        BACKEND_OK=1
        break
    fi
done
if [ "$BACKEND_OK" -eq 0 ]; then
    echo -e "${RED}[!] Backend no respondio en 10s. Revisa backend.log${NC}"
    echo "    Ultimas lineas de backend.log:"
    tail -20 backend.log
    exit 1
fi

# 4. Compilar frontend (SIEMPRE — sin esto preview sirve un dist/ viejo o vacio y da pantalla blanca)
echo -e "${YELLOW}[3/4]${NC} Compilando frontend (npm run build)..."
cd tauri-frontend
if ! npm run build > ../build.log 2>&1; then
    echo -e "${RED}[!] npm run build fallo. Revisa build.log${NC}"
    echo "    Ultimas lineas de build.log:"
    tail -30 ../build.log
    cd ..
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}[OK] Build completado (dist/ generado)${NC}"

# 5. Levantar frontend compilado
echo -e "${YELLOW}[4/4]${NC} Levantando frontend..."
npm run preview -- --host 0.0.0.0 > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Esperar a que el frontend responda
sleep 2
if ! curl -s http://127.0.0.1:4173 > /dev/null 2>&1; then
    echo -e "${YELLOW}[!] Frontend aun no responde, dale unos segundos mas${NC}"
fi

echo ""
echo -e "${GREEN}[OK] TODO LEVANTADO${NC}"
echo "   Backend:   http://127.0.0.1:$PORT"
echo "   Frontend:  http://localhost:4173"
echo "   Logs:      backend.log | build.log | frontend.log"
echo ""
echo "   PIDs: Backend=$BACKEND_PID Frontend=$FRONTEND_PID"
echo ""
echo "Presiona Ctrl+C para detener todo"

# 6. Trap para limpieza
trap "echo ''; echo '[!] Deteniendo...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
