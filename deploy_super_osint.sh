#!/bin/bash
set -e

# ═════════════════════════════════════════════════════════════════════════════
# SOURCESEAL RED TEAM — SCRIPT DE DESPLIEGUE COMPLETO
# Super OSINT Engine + fixes de auth + gateway mesh
# Uso: bash deploy_super_osint.sh
# ═════════════════════════════════════════════════════════════════════════════

# Colores
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; C='\033[0;36m'; N='\033[0m'
REPO="$HOME/Red-team-tauri"

echo -e "${C}════════════════════════════════════════════════════${N}"
echo -e "${C}  SOURCESEAL RED TEAM — DESPLIEGUE SUPER OSINT${N}"
echo -e "${C}════════════════════════════════════════════════════${N}"
echo ""

# ─── 1. VERIFICAR DEPENDENCIAS DEL SISTEMA ──────────────────────────────────
echo -e "${Y}[1/7] Verificando dependencias del sistema...${N}"
MISSING=""
for pkg in whois nmap dig tcpdump; do
  if command -v $pkg &>/dev/null; then
    echo -e "  ${G}✅ $pkg${N}"
  else
    echo -e "  ${R}❌ $pkg no instalado${N}"
    MISSING="$MISSING $pkg"
  fi
done

if [ -n "$MISSING" ]; then
  echo -e "${Y}Instalando paquetes faltantes...${N}"
  # dig viene en dnsutils, no bind-tools
  [ -n "$(echo $MISSING | grep dig)" ] && pkg install -y dnsutils
  [ -n "$(echo $MISSING | grep whois)" ] && pkg install -y whois
  [ -n "$(echo $MISSING | grep nmap)" ] && pkg install -y nmap
  [ -n "$(echo $MISSING | grep tcpdump)" ] && pkg install -y root-repo && pkg install -y tcpdump
fi

echo -e "${G}✅ Dependencias del sistema OK${N}"
echo ""

# ─── 2. CLONAR O ACTUALIZAR REPO ───────────────────────────────────────────
echo -e "${Y}[2/7] Sincronizando repositorio...${N}"
if [ ! -d "$REPO" ]; then
  echo -e "  Clonando desde GitHub..."
  git clone https://github.com/sourceseal-star/Red-team-tauri.git "$REPO"
else
  echo -e "  Repo existe — pulling cambios..."
  cd "$REPO"
  git stash 2>/dev/null || true
  git pull origin main 2>/dev/null || echo -e "  ${Y}Pull falló (sin internet o conflicto) — continuando con código local${N}"
fi

cd "$REPO"
echo -e "${G}✅ Repositorio en $(git rev-parse --short HEAD)${N}"
echo ""

# ─── 3. BUILD FRONTEND ──────────────────────────────────────────────────────
echo -e "${Y}[3/7] Build del frontend...${N}"
cd tauri-frontend

# Instalar dependencias si faltan
if [ ! -d "node_modules" ]; then
  echo -e "  Instalando dependencias npm..."
  npm install 2>&1 | tail -3
fi

npm run build 2>&1 | tail -5
if [ $? -ne 0 ]; then
  echo -e "${R}❌ Build del frontend falló${N}"
  exit 1
fi
echo -e "${G}✅ Frontend build OK${N}"
cd ..
echo ""

# ─── 4. VERIFICAR SINTAXIS BACKEND ─────────────────────────────────────────
echo -e "${Y}[4/7] Verificando backend Python...${N}"
python3 -c "
import py_compile
py_compile.compile('redteam/scripts/dashboard_server.py', doraise=True)
print('Sintaxis OK')
" || { echo -e "${R}❌ Error de sintaxis en backend${N}"; exit 1; }
echo -e "${G}✅ Backend OK${N}"
echo ""

# ─── 5. DETECTAR RED LOCAL (para topología) ─────────────────────────────────
echo -e "${Y}[5/7] Detectando red local...${N}"
# Verificar si hay WiFi (no datos móviles)
WIFI_IP=$(ip addr show wlan0 2>/dev/null | grep "inet " | awk '{print $2}' | head -1 || true)
if [ -z "$WIFI_IP" ]; then
  WIFI_IP=$(ip addr show ccmni0 2>/dev/null | grep "inet " | awk '{print $2}' | head -1 || true)
fi

if echo "$WIFI_IP" | grep -q "192.168\.\|10\.\|172\." 2>/dev/null; then
  SUBNET=$(echo "$WIFI_IP" | sed 's/\.[0-9]*\//.0\//')
  echo -e "  ${G}WiFi detectado: $WIFI_IP (subnet: $SUBNET)${N}"
  echo -e "  ${G}Topología debería encontrar dispositivos${N}"
else
  echo -e "  ${Y}⚠️  No se detectó red WiFi local${N}"
  echo -e "  ${Y}   La topología solo funciona conectado a WiFi${N}"
  echo -e "  ${Y}   El OSINT sí funciona con datos móviles${N}"
fi
echo ""

# ─── 6. COMMIT Y PUSH (si hay cambios locales) ─────────────────────────────
echo -e "${Y}[6/7] Verificando cambios para GitHub...${N}"
cd "$REPO"
if [ -n "$(git status --short)" ]; then
  echo -e "  Hay cambios sin commitear. ¿Hacer commit + push? (s/N)"
  read -r RESPONSE 2>/dev/null || RESPONSE="n"
  if [ "$RESPONSE" = "s" ] || [ "$RESPONSE" = "S" ]; then
    git add -A
    git commit -m "deploy: Super OSINT Engine desplegado desde Termux $(date +%Y-%m-%d)"
    git push origin main
    echo -e "${G}✅ Push a GitHub completado${N}"
  else
    echo -e "  ${Y}Saltando commit — cambios quedan locales${N}"
  fi
else
  echo -e "${G}✅ Sin cambios locales — todo sincronizado${N}"
fi
echo ""

# ─── 7. ARRANCAR BACKEND ───────────────────────────────────────────────────
echo -e "${Y}[7/7] Arrancando backend...${N}"

# Matar procesos anteriores
pkill -f "dashboard_server.py" 2>/dev/null || true
pkill -f "mesh_server.py" 2>/dev/null || true
sleep 2

# Arrancar
bash start-termux.sh &
sleep 3

# Verificar que está vivo
if curl -s http://localhost:8001/api/health | grep -q "ok\|healthy\|status" 2>/dev/null; then
  echo -e "${G}✅ Backend saludable en :8001${N}"
else
  echo -e "${Y}⚠️  Backend aún arrancando — dale unos segundos${N}"
  sleep 5
  if curl -s http://localhost:8001/api/health | grep -q "ok\|healthy\|status" 2>/dev/null; then
    echo -e "${G}✅ Backend saludable en :8001${N}"
  else
    echo -e "${R}❌ Backend no responde — revisa logs${N}"
  fi
fi

echo ""
echo -e "${C}════════════════════════════════════════════════════${N}"
echo -e "${G}  🚀 DESPLIEGUE COMPLETO${N}"
echo -e "${C}════════════════════════════════════════════════════${N}"
echo ""
echo -e "Backend:     http://localhost:8001"
echo -e "Dashboard:   http://localhost:8001/dashboard"
echo -e "OSINT APIs:  /api/osint/whois|subdomains|emails|dns|headers|cert|social|reverse|breach|full|export"
echo ""
echo -e "${Y}RECUERDA:${N}"
echo -e "  1. Abre el dashboard en Chrome"
echo -e "  2. Si tienes token viejo: toca 'Salir' (arriba derecha) y re-login"
echo -e "  3. Topología: necesitas estar en WiFi"
echo -e "  4. OSINT: funciona con cualquier conexión"
echo ""
echo -e "${Y}PROBAR OSINT:${N}"
echo -e "  curl -H 'Authorization: Bearer <token>' http://localhost:8001/api/osint/whois/github.com"
echo -e "  curl -H 'Authorization: Bearer <token>' http://localhost:8001/api/osint/social/johndoe"
echo -e "  curl -H 'Authorization: Bearer <token>' http://localhost:8001/api/osint/full/github.com"
echo ""
