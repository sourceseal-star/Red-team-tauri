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
pkg install -y python python-pip git openssh curl nodejs nmap whois 2>/dev/null || true

# 3. Dependencias Python
echo "[3/5] Instalando dependencias Python..."
python3 -m pip install -q psutil websocket-server requests 2>/dev/null || true

# 4. Clonar/actualizar repositorio
echo "[4/5] Preparando repositorio..."
cd ~
if [ ! -d "$HOME/Red-team-tauri/.git" ]; then
    if [ -e "$HOME/Red-team-tauri" ]; then
        echo "ERROR: ~/Red-team-tauri existe pero no es un repositorio Git."
        echo "Muévelo antes de continuar: mv ~/Red-team-tauri ~/Red-team-tauri.backup"
        exit 2
    fi
    echo "Clonando Red-team-tauri por SSH..."
    git clone git@github.com:sourceseal-star/Red-team-tauri.git "$HOME/Red-team-tauri"
fi
bash "$HOME/Red-team-tauri/scripts/termux/sync_repositories.sh"

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
