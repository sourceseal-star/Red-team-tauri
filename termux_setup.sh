#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# TERMUX SETUP MAESTRO — Red-Team-Tauri / SourceSeal
# Instala TODO, sincroniza con GitHub y deja listo para ejecutar
# Uso:  bash termux_setup.sh
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Colores
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'
banner() { echo -e "\n${B}══════════════════════════════════════════════════${N}"; echo -e "${G}  $1${N}"; echo -e "${B}══════════════════════════════════════════════════${N}\n"; }

banner "TERMUX SETUP — Red-Team-Tauri v3.0"

# ── 1. VERIFICAR TERMUX ──────────────────────────────────────────────
if [ ! -d "/data/data/com.termux" ]; then
    echo -e "${Y}[!] No se detecto Termux. Algunas funciones pueden no funcionar.${N}"
fi

# ── 2. ACTUALIZAR PAQUETES BASE ──────────────────────────────────────
echo -e "${C}[1/7] Actualizando paquetes Termux...${N}"
pkg update -y && pkg upgrade -y 2>/dev/null || true

# ── 3. INSTALAR DEPENDENCIAS SISTEMA ─────────────────────────────────
echo -e "${C}[2/7] Instalando dependencias de sistema...${N}"
pkg install -y python python-pip nodejs-lts git openssl-tool jq curl wget termux-api 2>/dev/null || true

# Opcionales (no fallan si no se instalan)
pkg install -y qrencode nmap whois 2>/dev/null || true

# ── 4. DEPENDENCIAS PYTHON ───────────────────────────────────────────
echo -e "${C}[3/7] Instalando dependencias Python...${N}"
pip install --upgrade pip 2>/dev/null || true
pip install -q \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.32.0" \
    pydantic==2.9.0 \
    psutil==6.1.0 \
    requests==2.32.0 \
    aiofiles==24.1.0 \
    python-multipart==0.0.17 \
    websockets==13.1 \
    python-whois==0.9.5 \
    python-nmap==0.7.1 \
    2>/dev/null || echo -e "${Y}[!] Algunas paquetes pip pueden no haberse instalado${N}"

# ── 5. SINCRONIZAR CON GITHUB ────────────────────────────────────────
echo -e "${C}[4/7] Sincronizando con GitHub...${N}"
cd "$ROOT"
git fetch origin 2>/dev/null || true
LOCAL=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
REMOTE=$(git rev-parse --short origin/main 2>/dev/null || echo "unknown")
if [ "$LOCAL" != "$REMOTE" ]; then
    echo -e "${Y}[sync] Actualizando $LOCAL -> $REMOTE${N}"
    git reset --hard origin/main
else
    echo -e "${G}[sync] Ya en el ultimo commit: $LOCAL${N}"
fi
echo -e "Commit: $(git log --oneline -1)"

# ── 6. PERMISOS DE EJECUCION ─────────────────────────────────────────
echo -e "${C}[5/7] Aplicando permisos de ejecucion...${N}"
chmod +x *.py *.sh redteam/scripts/*.py redteam/run_all_tests.py 2>/dev/null || true
chmod +x honeypot/*.js sealctl/*.js 2>/dev/null || true
echo -e "${G}  OK Permisos aplicados${N}"

# ── 7. VARIABLES DE ENTORNO ──────────────────────────────────────────
echo -e "${C}[6/7] Configurando entorno...${N}"

# API Key - generar si no existe
if [ ! -f "$ROOT/.env" ]; then
    API_KEY=$(openssl rand -hex 24)
    DECEPTION_KEY=$(openssl rand -hex 32)
    cat > "$ROOT/.env" << EOF
# Red-Team-Tauri - Configuracion
REDTEAM_API_KEY=${API_KEY}
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8001
HOST=0.0.0.0
PORT=8001
DECEPTION_HMAC_KEY=${DECEPTION_KEY}
EOF
    chmod 600 "$ROOT/.env"
    echo -e "${G}  OK .env creado con API Key: ${API_KEY:0:8}...${N}"
    echo -e "${Y}  GUARDA ESTA KEY: REDTEAM_API_KEY=${API_KEY}${N}"
else
    echo -e "${G}  OK .env ya existe${N}"
fi

# Cargar .env
set -a; source "$ROOT/.env" 2>/dev/null; set +a

# ── 8. VERIFICACION FINAL ────────────────────────────────────────────
echo -e "${C}[7/7] Verificacion final...${N}"

echo ""
echo -e "${B}+---------------------------------------------------+${N}"
echo -e "${B}|  ESTADO DEL SISTEMA                               |${N}"
echo -e "${B}+---------------------------------------------------+${N}"

python3 --version 2>/dev/null && echo -e "  ${G}OK Python${N}" || echo -e "  ${R}FAIL Python${N}"
node --version 2>/dev/null && echo -e "  ${G}OK Node.js${N}" || echo -e "  ${R}FAIL Node.js${N}"
git --version 2>/dev/null | head -1 && echo -e "  ${G}OK Git${N}" || echo -e "  ${R}FAIL Git${N}"
openssl version 2>/dev/null && echo -e "  ${G}OK OpenSSL${N}" || echo -e "  ${R}FAIL OpenSSL${N}"

# Tests
cd "$ROOT/redteam"
TEST_RESULT=$(python3 run_all_tests.py 2>&1 | grep -E "^Ran|OK|FAILED")
echo -e "  Tests: ${G}${TEST_RESULT}${N}"
cd "$ROOT"

echo -e "${B}+---------------------------------------------------+${N}"

# ── MENU DE HERRAMIENTAS ─────────────────────────────────────────────
echo ""
banner "HERRAMIENTAS DISPONIBLES"

echo -e "${C}  1.${N} Backend Dashboard    - FastAPI :8001 + Swagger"
echo -e "${C}  2.${N} Auditor v3           - Escaneo 10 vectores multi-repo"
echo -e "${C}  3.${N} Mirage               - Senuelos y datos falsos"
echo -e "${C}  4.${N} Watcher              - Proteccion datos + anti-vigilancia"
echo -e "${C}  5.${N} Guardian Custodian    - Fingerprinting + backup cifrado"
echo -e "${C}  6.${N} OSINT Mapper          - Extraccion de entidades de texto"
echo -e "${C}  7.${N} Tests suite           - 42 tests del sistema"
echo -e "${C}  8.${N} Sync completo         - git pull + rebuild + restart"
echo -e "${C}  9.${N} Honeypot             - API falsa + canary tokens"
echo -e "${C}  0.${N} Salir"
echo ""

read -p "$(echo -e ${Y}'Selecciona [0-9]: '${N})" opt

case $opt in
    1)
        echo -e "${G}Arrancando Dashboard Backend...${N}"
        cd "$ROOT/redteam/scripts"
        python3 dashboard_server.py
        ;;
    2)
        echo -e "${G}Ejecutando Auditor v3...${N}"
        cd "$ROOT"
        python3 source_seal_audit_v3.py
        ;;
    3)
        echo -e "${G}Ejecutando Mirage...${N}"
        cd "$ROOT"
        python3 mirage.py
        ;;
    4)
        echo -e "${G}Ejecutando Watcher...${N}"
        cd "$ROOT"
        bash watcher.sh
        ;;
    5)
        echo -e "${G}Ejecutando Guardian Custodian...${N}"
        cd "$ROOT"
        bash guardian_custodian.sh
        ;;
    6)
        echo -e "${G}Ejecutando OSINT Mapper...${N}"
        cd "$ROOT"
        python3 osint_struct_mapper.py
        ;;
    7)
        echo -e "${G}Ejecutando Tests...${N}"
        cd "$ROOT/redteam"
        python3 run_all_tests.py
        ;;
    8)
        echo -e "${G}Sync completo...${N}"
        cd "$ROOT"
        bash sync.sh
        ;;
    9)
        echo -e "${G}Arrancando Honeypot...${N}"
        cd "$ROOT/honeypot"
        node start-honeypot.js 2>/dev/null || echo -e "${R}Requiere: npm install express${N}"
        ;;
    0)
        echo -e "${G}Listo. Todo configurado.${N}"
        exit 0
        ;;
    *)
        echo -e "${R}Opcion invalida${N}"
        ;;
esac
