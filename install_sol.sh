#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SOL — Instalador completo para Termux
# Instala todo lo necesario y lanza a Sol como asistente libre
# =====================================================================
set -e

R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; C='\033[0;36m'; N='\033[0m'

echo ""
echo -e "  ${C}╔══════════════════════════════════════════════╗${N}"
echo -e "  ${C}║  ☀️  SOL — Instalador para Termux              ║${N}"
echo -e "  ${C}╚══════════════════════════════════════════════╝${N}"
echo ""

# ─── 1. Termux:API (vital) ─────────────────────────────────────
echo -e "${Y}[1/6] Instalando Termux:API...${N}"
pkg install -y termux-api 2>/dev/null || true
echo -e "${G}  ✅ termux-api instalado${N}"

# También instalar la app Termux:API de Google Play si no está
if ! command -v termux-tts-speak >/dev/null 2>&1; then
  echo -e "${R}  ⚠️  termux-tts-speak no disponible.${N}"
  echo -e "${Y}     Instala la app 'Termux:API' desde F-Droid o Play Store${N}"
  echo -e "${Y}     Luego corre: termux-setup-storage${N}"
fi

# ─── 2. Python + dependencias ──────────────────────────────────
echo -e "${Y}[2/6] Verificando Python...${N}"
if ! command -v python3 >/dev/null 2>&1; then
  pkg install -y python
fi
echo -e "${G}  ✅ $(python3 --version)${N}"

# ─── 3. herramientas del sistema ───────────────────────────────
echo -e "${Y}[3/6] Herramientas del sistema...${N}"
pkg install -y openssh git curl wget nmap whois dnsutils 2>/dev/null || true
# Verificar si ya están instalados
for tool in git curl whois dig nmap; do
  if command -v $tool >/dev/null 2>&1; then
    echo -e "${G}  ✅ $tool${N}"
  else
    echo -e "${Y}  ⚠️  $tool no disponible (algunas funciones de OSINT no funcionarán)${N}"
  fi
done

# ─── 4. Descargar Sol ──────────────────────────────────────────
echo -e "${Y}[4/6] Descargando Sol...${N}"
REPO_DIR="$HOME/Red-team-tauri"

# Si el repo existe, git pull
if [ -d "$REPO_DIR/.git" ]; then
  cd "$REPO_DIR"
  git config pull.rebase true 2>/dev/null || true
  git pull origin main 2>/dev/null || echo -e "${Y}  git pull falló, continuando...${N}"
else
  echo -e "${Y}  Clonando Red-team-tauri...${N}"
  git clone https://github.com/sourceseal-star/Red-team-tauri.git "$REPO_DIR" 2>/dev/null || true
fi

# Descargar sol_termux.py directamente si no está
if [ ! -f "$REPO_DIR/sol_termux.py" ]; then
  echo -e "${Y}  Descargando sol_termux.py...${N}"
  python3 -c "
import urllib.request
url = 'https://raw.githubusercontent.com/sourceseal-star/Red-team-tauri/main/sol_termux.py'
urllib.request.urlretrieve(url, '$REPO_DIR/sol_termux.py')
print('  ✅ Descargado')
" 2>/dev/null || echo -e "${R}  No se pudo descargar${N}"
fi

echo -e "${G}  ✅ Sol listo en $REPO_DIR/sol_termux.py${N}"

# ─── 5. Configurar .env ────────────────────────────────────────
echo -e "${Y}[5/6] Configurando entorno...${N}"

ENV_FILE="$REPO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  API_KEY=$(openssl rand -hex 24)
  cat > "$ENV_FILE" << EOF
REDTEAM_API_KEY=${API_KEY}
HOST=0.0.0.0
PORT=8001
ALLOWED_ORIGINS=http://localhost:8001
HUNTER_API_KEY=68d9591d7af507b01c5b1239d327ca16dbdd8239
EOF
  echo -e "${G}  ✅ .env creado${N}"
else
  echo -e "${G}  ✅ .env existe${N}"
fi

# ─── 6. Permisos ───────────────────────────────────────────────
echo -e "${Y}[6/6] Permisos...${N}"
# Solicitar permisos de storage
termux-setup-storage 2>/dev/null || true
# SMS y telefonía necesitan permisos
echo -e "${Y}  Acepta los permisos de Termux:API en tu teléfono:${N}"
echo -e "${Y}  Configuración → Apps → Termux:API → Permisos → SMS, Micrófono, Almacenamiento${N}"

echo ""
echo -e "${G}╔══════════════════════════════════════════════════╗${N}"
echo -e "${G}║  ☀️  SOL INSTALADO                              ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
echo ""
echo -e "  Para lanzar a Sol:"
echo -e "    ${C}python3 ~/Red-team-tauri/sol_termux.py${N}"
echo ""
echo -e "  O en modo comando directo:"
echo -e "    ${C}python3 ~/Red-team-tauri/sol_termux.py 'sol abre una leccion de pinyin 1'${N}"
echo -e "    ${C}python3 ~/Red-team-tauri/sol_termux.py 'sol envia whatsapp a mama que diga hola'${N}"
echo ""
echo -e "  Alias opcional (agrega a ~/.bashrc):"
echo -e "    ${C}alias sol='python3 ~/Red-team-tauri/sol_termux.py'${N}"
echo ""

# Preguntar si quiere el alias
read -p "Agregar alias 'sol' a .bashrc? (s/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Ss]$ ]]; then
  echo "alias sol='python3 ~/Red-team-tauri/sol_termux.py'" >> ~/.bashrc
  echo -e "${G}  ✅ Alias agregado. Abre Termux de nuevo y escribe 'sol'${N}"
fi

echo ""
echo -e "  ${Y}Lanzando Sol...${N}"
echo ""
exec python3 "$REPO_DIR/sol_termux.py"
