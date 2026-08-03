#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# SourceSeal Console Pro — Instalador Termux
# ============================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "${RED}🔴 SourceSeal Console Pro — Instalador Termux${NC}"
echo ""

# 1. Actualizar paquetes
echo "${CYAN}[1/8] Actualizando paquetes...${NC}"
pkg update -y

# 2. Instalar dependencias
echo "${CYAN}[2/8] Instalando dependencias...${NC}"
pkg install -y python python-pip git curl wget

# 3. Verificar/instalar Flutter
echo "${CYAN}[3/8] Verificando Flutter...${NC}"
if ! command -v flutter &> /dev/null; then
    echo "${CYAN}Instalando Flutter...${NC}"
    pkg install -y flutter
fi

# 4. Clonar repositorio
echo "${CYAN}[4/8] Preparando directorio...${NC}"
cd ~
if [ -d "Red-team-tauri" ]; then
    echo "${CYAN}Actualizando repositorio existente...${NC}"
    cd Red-team-tauri && git pull || true
else
    echo "${CYAN}Clonando repositorio...${NC}"
    git clone https://github.com/sourceseal-star/Red-team-tauri.git
    cd Red-team-tauri
fi

# 5. Instalar backend
echo "${CYAN}[5/8] Instalando backend Python...${NC}"
cd backend
pip install -r requirements.txt
cd ..

# 6. Configurar API URL para Termux local
echo "${CYAN}[6/8] Configurando URLs...${NC}"
sed -i 's|http://localhost:8000|http://127.0.0.1:8000|g' lib/core/constants/app_constants.dart
sed -i 's|ws://localhost:8000|ws://127.0.0.1:8000|g' lib/core/constants/app_constants.dart

# 7. Instalar dependencias Flutter
echo "${CYAN}[7/8] Instalando dependencias Flutter...${NC}"
flutter pub get

# 8. Compilar
echo "${CYAN}[8/8] Compilando aplicación...${NC}"
flutter build apk --release

echo ""
echo "${GREEN}✅ Instalación completa!${NC}"
echo ""
echo "${CYAN}🚀 Para iniciar:${NC}"
echo "   1. Backend:  cd ~/Red-team-tauri/backend && python main.py"
echo "   2. App:      cd ~/Red-team-tauri && flutter run"
echo ""
echo "${CYAN}📱 APK generada en:${NC}"
echo "   build/app/outputs/flutter-apk/app-release.apk"
echo ""
echo "${CYAN}🔧 Para instalar el APK:${NC}"
echo "   cp build/app/outputs/flutter-apk/app-release.apk /sdcard/Download/"
