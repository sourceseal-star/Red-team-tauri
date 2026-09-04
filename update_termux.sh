#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# ACTUALIZAR RED-TEAM-TAURI EN TERMUX — Sin perder el estado actual
# Sincroniza tu Termux con los últimos cambios del repo
# (enhanced_recon, CameraCommandCenter, TopologyMapFixed, etc.)
#
# USO:  bash update_termux.sh
# =====================================================================
set -e

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo -e "\n${C}══════════════════════════════════════════════════${N}"
echo -e "${C}  SourceSeal — Actualización de Termux${N}"
echo -e "${C}══════════════════════════════════════════════════${N}\n"

# ── 1. DETENER PROCESOS ─────────────────────────────────────────────
echo -e "${Y}[1/7] Deteniendo procesos actuales...${N}"
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 2
echo -e "  ${G}OK Procesos detenidos${N}"

# ── 2. GIT PULL ─────────────────────────────────────────────────────
echo -e "\n${Y}[2/7] Sincronizando con GitHub...${N}"
if [ ! -d "$ROOT/.git" ]; then
    echo -e "  ${R}X No es un repositorio git. Clona primero:${N}"
    echo "    git clone https://github.com/sourceseal-star/Red-team-tauri.git"
    exit 1
fi

git stash 2>/dev/null || true
git pull origin main 2>&1 || {
    echo -e "  ${R}X git pull falló. Intentando via HTTPS público...${N}"
    git pull https://github.com/sourceseal-star/Red-team-tauri.git main 2>&1 || {
        echo -e "  ${R}X No se pudo hacer pull. Verifica tu conexión.${N}"
        exit 1
    }
}
git stash pop 2>/dev/null || true
echo -e "  ${G}OK Código sincronizado${N}"

# ── 3. DEPENDENCIAS PYTHON ──────────────────────────────────────────
echo -e "\n${Y}[3/7] Instalando dependencias Python...${N}"
pip install -q fastapi uvicorn httpx psutil aiohttp 2>&1 | tail -3 || true
echo -e "  ${G}OK Python deps listas${N}"

# ── 4. DEPENDENCIAS NODE ─────────────────────────────────────────────
echo -e "\n${Y}[4/7] Verificando dependencias Node...${N}"
cd "$ROOT/tauri-frontend"
if [ ! -d "node_modules" ]; then
    echo "  Instalando node_modules..."
    npm install 2>&1 | tail -5
fi
# Asegurar lucide-react (nuevo icono Network)
npm ls lucide-react 2>/dev/null | grep -q "lucide-react" || npm install lucide-react 2>&1 | tail -3
echo -e "  ${G}OK Node deps listas${N}"

# ── 5. VERIFICAR FRONTEND ───────────────────────────────────────────
echo -e "\n${Y}[5/7] Verificando nuevos componentes frontend...${N}"
for f in CameraCommandCenter.tsx TopologyMapFixed.tsx; do
    if [ -f "$ROOT/tauri-frontend/src/components/$f" ]; then
        echo -e "  ${G}OK $f presente${N}"
    else
        echo -e "  ${R}X $f NO encontrado — el git pull pudo fallar${N}"
    fi
done

# ── 6. VERIFICAR .env ──────────────────────────────────────────────
echo -e "\n${Y}[6/7] Verificando .env...${N}"
if [ ! -f "$ROOT/.env" ]; then
    echo -e "  ${Y}  .env no existe. Generando...${N}"
    API_KEY=$(openssl rand -hex 24)
    DECEPTION_KEY=$(openssl rand -hex 32)
    cat > "$ROOT/.env" << EOF
# Red-Team-Tauri - Configuracion v3.2
REDTEAM_API_KEY=${API_KEY}
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8001
HOST=0.0.0.0
PORT=8001
DECEPTION_HMAC_KEY=${DECEPTION_KEY}
EOF
    chmod 600 "$ROOT/.env"
    echo -e "  ${G}  OK .env creado. API Key: ${API_KEY:0:8}...${N}"
    echo -e "  ${Y}  GUARDA TU KEY: ${API_KEY}${N}"
else
    echo -e "  ${G}OK .env existe (clave preservada)${N}"
fi

# ── 7. VERIFICAR ENHANCED RECON ─────────────────────────────────────
echo -e "\n${Y}[7/7] Verificando módulo enhanced_recon...${N}"
if [ -f "$ROOT/backend/modules/enhanced_recon.py" ]; then
    echo -e "  ${G}OK enhanced_recon.py presente${N}"
else
    echo -e "  ${R}X enhanced_recon.py NO encontrado${N}"
    echo -e "  ${Y}  El backend arrancará sin enhanced recon (fallback seguro)${N}"
fi

echo ""
echo -e "${C}══════════════════════════════════════════════════${N}"
echo -e "${G}  ACTUALIZACION COMPLETA${N}"
echo -e "${C}══════════════════════════════════════════════════${N}"
echo ""
echo -e "Para arrancar el sistema:"
echo -e "  ${C}bash start-termux.sh${N}"
echo ""
echo -e "Endpoints nuevos:"
echo -e "  POST /api/enhanced/discover/all  - descubrimiento completo"
echo -e "  GET  /api/enhanced/cameras       - camaras guardadas"
echo -e "  GET  /api/enhanced/hosts         - hosts descubiertos"
echo -e "  POST /api/enhanced/camera/scan   - escaneo individual"
echo ""
echo -e "Frontend nuevas rutas:"
echo -e "  /cameras   - Camera Command Center"
echo -e "  /topology  - Topologia con filtros"
echo ""
