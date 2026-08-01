#!/data/data/com.termux/files/usr/bin/bash
# ============================================
# SourceSeal Console Pro — Instalador Termux
# Version corregida: instala Flutter SDK real
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "${RED}=== SourceSeal Console Pro — Instalador Termux ===${NC}"
echo ""

# ── 1. Actualizar paquetes ────────────────────────────
echo "${CYAN}[1/7] Actualizando paquetes Termux...${NC}"
pkg update -y && pkg upgrade -y

# ── 2. Instalar dependencias del sistema ─────────────
echo "${CYAN}[2/7] Instalando dependencias...${NC}"
pkg install -y python python-pip git curl wget unzip openjdk-21 cmake binutils

# ── 3. Instalar Flutter SDK (metodo correcto para Termux) ─
echo "${CYAN}[3/7] Instalando Flutter SDK...${NC}"

FLUTTER_DIR="$HOME/flutter"

if [ -d "$FLUTTER_DIR" ]; then
    echo "${YELLOW}Flutter ya existe, actualizando...${NC}"
    cd "$FLUTTER_DIR"
    git pull
    cd ~
else
    echo "${CYAN}Descargando Flutter SDK desde GitHub...${NC}"
    git clone https://github.com/flutter/flutter.git \
        --depth 1 \
        --branch stable \
        "$FLUTTER_DIR"
fi

# Agregar Flutter al PATH de esta sesion
export PATH="$FLUTTER_DIR/bin:$PATH"

# Agregar Flutter al .bashrc para sesiones futuras
if ! grep -q "flutter/bin" ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/flutter/bin:$PATH"' >> ~/.bashrc
fi

echo "${GREEN}Flutter instalado: $(flutter --version | head -1)${NC}"

# ── 4. Backend Python ──────────────────────────────────
echo "${CYAN}[4/7] Instalando backend Python...${NC}"

cd ~/Red-team-tauri
pip install -r backend/requirements.txt

echo "${GREEN}Backend listo${NC}"

# ── 5. Instalar dependencias Flutter ──────────────────
echo "${CYAN}[5/7] Instalando dependencias Flutter (flutter pub get)...${NC}"

# Corregir URLs a 127.0.0.1 para Termux local
sed -i 's|http://localhost:8000|http://127.0.0.1:8000|g' lib/core/constants/app_constants.dart 2>/dev/null || true
sed -i 's|ws://localhost:8000|ws://127.0.0.1:8000|g'   lib/core/constants/app_constants.dart 2>/dev/null || true

flutter pub get

# ── 6. Compilar APK ───────────────────────────────────
echo "${CYAN}[6/7] Compilando APK (puede tardar 5-15 min)...${NC}"
flutter build apk --release

# ── 7. Copiar APK a Descargas ─────────────────────────
echo "${CYAN}[7/7] Copiando APK...${NC}"
APK_SRC="build/app/outputs/flutter-apk/app-release.apk"
APK_DST="/sdcard/Download/SourceSeal-Console-v2.0.apk"

if [ -f "$APK_SRC" ]; then
    cp "$APK_SRC" "$APK_DST" 2>/dev/null && \
        echo "${GREEN}APK copiada a Descargas: SourceSeal-Console-v2.0.apk${NC}" || \
        echo "${YELLOW}No se pudo copiar a /sdcard — APK en: $APK_SRC${NC}"
else
    echo "${YELLOW}APK no encontrada en $APK_SRC${NC}"
fi

echo ""
echo "${GREEN}=== Instalacion completa! ===${NC}"
echo ""
echo "${CYAN}Para iniciar el backend:${NC}"
echo "   cd ~/Red-team-tauri/backend && python main.py"
echo ""
echo "${CYAN}Para correr la app en modo debug:${NC}"
echo "   cd ~/Red-team-tauri && flutter run"
echo ""
echo "${CYAN}APK generada:${NC} $APK_SRC"
