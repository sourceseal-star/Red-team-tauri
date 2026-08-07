#!/bin/bash
# ============================================
# SourceSeal Console Pro — Instalador Replit
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "${RED}🔴 SourceSeal Console Pro — Instalador Replit${NC}"
echo ""

# 1. Instalar backend
echo "${CYAN}[1/3] Instalando backend Python...${NC}"
cd backend
pip install -r requirements.txt
cd ..

# 2. Detectar URL pública de Replit
echo "${CYAN}[2/3] Configurando URL pública...${NC}"
if [ -n "$REPLIT_DEPLOYMENT_URL" ]; then
    PUBLIC_URL="$REPLIT_DEPLOYMENT_URL"
elif [ -n "$REPL_ID" ]; then
    PUBLIC_URL="https://$REPL_ID.$REPL_OWNER.repl.co"
else
    PUBLIC_URL="https://$(basename $(pwd)).$(whoami).repl.co"
fi

echo "${CYAN}URL detectada: $PUBLIC_URL${NC}"

# Configurar URLs en la app
sed -i "s|http://localhost:8000|$PUBLIC_URL/api|g" lib/core/constants/app_constants.dart
sed -i "s|ws://localhost:8000|wss://$(echo $PUBLIC_URL | sed 's|https://||')/ws|g" lib/core/constants/app_constants.dart

# 3. Iniciar backend
echo "${CYAN}[3/3] Iniciando backend...${NC}"
cd backend
python main.py &

echo ""
echo "${GREEN}✅ Backend iniciado en Replit!${NC}"
echo ""
echo "${CYAN}🌐 API Base URL:${NC} $PUBLIC_URL/api"
echo "${CYAN}📡 WebSocket URL:${NC} wss://$(echo $PUBLIC_URL | sed 's|https://||')/ws"
echo ""
echo "${CYAN}🔧 Para compilar Flutter Web:${NC}"
echo "   flutter build web"
echo ""
echo "${CYAN}📱 Para compilar APK (si Replit soporta Android):${NC}"
echo "   flutter build apk"
