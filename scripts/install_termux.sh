#!/data/data/com.termux/files/usr/bin/bash
# SourceSeal Red-team Console — Instalador Termux
set -e

echo "🔴 SourceSeal Red-team Console — Instalador Termux"
echo ""

# 1. Actualizar paquetes
echo "[1/5] Actualizando paquetes..."
pkg update -y 2>/dev/null || true

# 2. Instalar dependencias
echo "[2/5] Instalando dependencias..."
pkg install -y python python-pip git curl 2>/dev/null || true

# 3. Dependencias Python
echo "[3/5] Instalando dependencias Python..."
pip install -q psutil websocket-server requests 2>/dev/null || true

# 4. Clonar/actualizar repositorio
echo "[4/5] Preparando repositorio..."
cd ~
if [ -d "Red-team-tauri" ]; then
    cd Red-team-tauri && git pull
else
    git clone https://github.com/sourceseal-star/Red-team-tauri.git
    cd Red-team-tauri
fi

# 5. Instalar dependencias del frontend
echo "[5/5] Instalando dependencias frontend..."
cd tauri-frontend
if [ ! -d "node_modules" ]; then
    npm install --prefer-offline --no-audit --no-fund
fi

echo ""
echo "✅ Instalación completa!"
echo ""
echo "Para iniciar:  bash ~/Red-team-tauri/start-termux.sh"
echo "Para detener:  bash ~/Red-team-tauri/scripts/termux/stop_all.sh"
