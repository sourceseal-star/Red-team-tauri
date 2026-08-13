#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# TERMUX SETUP MAESTRO — Red-Team-Tauri / SourceSeal v3.2
# Instala TODO, sincroniza con GitHub y deja listo para ejecutar
# Uso:  bash termux_setup.sh
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Colores
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; P='\033[0;35m'; N='\033[0m'
banner() { echo -e "\n${B}══════════════════════════════════════════════════${N}"; echo -e "${G}  $1${N}"; echo -e "${B}══════════════════════════════════════════════════${N}\n"; }

banner "TERMUX SETUP — Red-Team-Tauri v3.2"

# ── 1. VERIFICAR TERMUX ──────────────────────────────────────────────
if [ ! -d "/data/data/com.termux" ]; then
    echo -e "${Y}[!] No se detecto Termux. Algunas funciones pueden no funcionar.${N}"
fi

# ── 2. ACTUALIZAR PAQUETES BASE ──────────────────────────────────────
echo -e "${C}[1/8] Actualizando paquetes Termux...${N}"
pkg update -y && pkg upgrade -y 2>/dev/null || true

# ── 3. DEPENDENCIAS CORE (obligatorias) ──────────────────────────────
echo -e "${C}[2/8] Instalando dependencias core...${N}"
pkg install -y python python-pip nodejs-lts git openssl-tool jq curl wget 2>/dev/null || true

# ── 4. DEPENDENCIAS POR MODULO ───────────────────────────────────────
echo -e "${C}[3/8] Instalando herramientas por modulo...${N}"

# MURCIÉLAGO — ultrasonidos
pkg install -y termux-api 2>/dev/null || true
# Nota: requiere permiso de microfono: Ajustes → Apps → Termux → Permisos → Microfono

# ESCANEO — nmap + traceroute
pkg install -y nmap traceroute 2>/dev/null || true

# OSINT ENGINE — whois, dig, exiftool
pkg install -y whois 2>/dev/null || true
pkg install -y bind-utils 2>/dev/null || true    # dig
pkg install -y exiftool 2>/dev/null || true
pkg install -y termux-api 2>/dev/null || true    # wifi scan (sin root)

# WIFI SCANNER — termux-api (sin root), aircrack-ng (con root)
pkg install -y aircrack-ng 2>/dev/null || true
# iw NO disponible en Termux (solo Linux/Kali)

# BLACK MIRROR — netcat para Shadow Twin + Chaos
pkg install -y netcat-openbsd 2>/dev/null || true
# iptables NO disponible en Termux (requiere root + kernel mod)

# EVIDENCIA — qrencode + ffmpeg
pkg install -y qrencode ffmpeg 2>/dev/null || true

# CAPTURA — tcpdump
pkg install -y tcpdump 2>/dev/null || true

echo -e "${G}  OK Herramientas de sistema instaladas${N}"

# ── 5. DEPENDENCIAS PYTHON ───────────────────────────────────────────
echo -e "${C}[4/8] Instalando dependencias Python...${N}"
pip install --upgrade pip 2>/dev/null || true
pip install -q \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.32.0" \
    pydantic==2.9.0 \
    httpx==0.27.0 \
    psutil==6.1.0 \
    requests==2.32.0 \
    aiofiles==24.1.0 \
    python-multipart==0.0.17 \
    websockets==13.1 \
    python-whois==0.9.5 \
    python-nmap==0.7.1 \
    "qrcode[pil]==7.4.2" \
    reportlab==4.2.5 \
    numpy==2.1.0 \
    2>/dev/null || echo -e "${Y}[!] Algunos paquetes pip pueden no haberse instalado${N}"

echo -e "${G}  OK Dependencias Python instaladas${N}"

# ── 6. SINCRONIZAR CON GITHUB ────────────────────────────────────────
echo -e "${C}[5/8] Sincronizando con GitHub...${N}"
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

# ── 7. BUILD FRONTEND ────────────────────────────────────────────────
echo -e "${C}[6/8] Build frontend...${N}"
cd "$ROOT/tauri-frontend"
npm install 2>/dev/null || true
npm run build 2>/dev/null || echo -e "${Y}[!] Build falló — el backend puede servir sin frontend${N}"
cd "$ROOT"
echo -e "${G}  OK Frontend buildado${N}"

# ── 8. PERMISOS DE EJECUCION ─────────────────────────────────────────
echo -e "${C}[7/8] Aplicando permisos de ejecucion...${N}"
chmod +x *.py *.sh redteam/scripts/*.py redteam/run_all_tests.py 2>/dev/null || true
chmod +x honeypot/*.js sealctl/*.js 2>/dev/null || true
echo -e "${G}  OK Permisos aplicados${N}"

# ── 9. VARIABLES DE ENTORNO ──────────────────────────────────────────
echo -e "${C}[8/8] Configurando entorno...${N}"

if [ ! -f "$ROOT/.env" ]; then
    API_KEY=$(openssl rand -hex 24)
    DECEPTION_KEY=$(openssl rand -hex 32)
    cat > "$ROOT/.env" << EOF
# Red-Team-Tauri - Configuracion v3.2
REDTEAM_API_KEY=${API_KEY}
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8001
HOST=0.0.0.0
PORT=8001
DECEPTION_HMAC_KEY=${DECEPTION_KEY}
# OSINT — opcional (25 req/mes gratis en hunter.io)
# HUNTER_API_KEY=tu_key_aqui
# THREAT INTEL — opcional (1000 req/dia gratis)
# ABUSEIPDB_API_KEY=tu_key_aqui
EOF
    chmod 600 "$ROOT/.env"
    echo -e "${G}  OK .env creado con API Key: ${API_KEY:0:8}...${N}"
    echo -e "${Y}  GUARDA ESTA KEY: REDTEAM_API_KEY=${API_KEY}${N}"
else
    echo -e "${G}  OK .env ya existe${N}"
fi

set -a; source "$ROOT/.env" 2>/dev/null; set +a

# ── VERIFICACION FINAL ──────────────────────────────────────────────
echo ""
echo -e "${B}+---------------------------------------------------+${N}"
echo -e "${B}|  ESTADO DEL SISTEMA                               |${N}"
echo -e "${B}+---------------------------------------------------+${N}"

echo -ne "  Python:     "; python3 --version 2>/dev/null && echo -e "  ${G}OK${N}" || echo -e "  ${R}FAIL${N}"
echo -ne "  Node.js:    "; node --version 2>/dev/null && echo -e "  ${G}OK${N}" || echo -e "  ${R}FAIL${N}"
echo -ne "  Git:        "; git --version 2>/dev/null | head -1 && echo -e "  ${G}OK${N}" || echo -e "  ${R}FAIL${N}"
echo -ne "  OpenSSL:    "; openssl version 2>/dev/null && echo -e "  ${G}OK${N}" || echo -e "  ${R}FAIL${N}"
echo -ne "  nmap:       "; which nmap >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (opcional)${N}"
echo -ne "  whois:      "; which whois >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (OSINT)${N}"
echo -ne "  dig:        "; which dig >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (OSINT brute)${N}"
echo -ne "  exiftool:   "; which exiftool >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (metadata)${N}"
echo -ne "  termux-api: "; which termux-wifi-scaninfo >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (WiFi scan)${N}"
echo -ne "  aircrack:   "; which aircrack-ng >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (WiFi crack)${N}"
echo -ne "  netcat:     "; which nc >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (Shadow Twin)${N}"
echo -ne "  tcpdump:    "; which tcpdump >/dev/null 2>&1 && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (captura)${N}"
echo -ne "  reportlab:  "; python3 -c "import reportlab" 2>/dev/null && echo -e "  ${G}OK${N}" || echo -e "  ${Y}NO (Canary PDF)${N}"

echo -e "${B}+---------------------------------------------------+${N}"

# ── PERMISOS ANDROID (recordatorio) ─────────────────────────────────
echo ""
echo -e "${P}Permisos de Android necesarios:${N}"
echo -e "  ${C}Microfono${N}   → Ajustes > Apps > Termux > Permisos > Microfono (MURCIÉLAGO)"
echo -e "  ${C}Ubicacion${N}   → Ajustes > Apps > Termux > Permisos > Ubicacion (WiFi scan)"
echo -e "  ${C}Almacenamiento${N} → termux-setup-storage (ya hecho)"
echo ""

# ── MENU DE HERRAMIENTAS ─────────────────────────────────────────────
banner "SALA DE GUERRA — MENU"

echo -e "${C}  1.${N} Dashboard Backend    - FastAPI :8001 + Sala de Guerra"
echo -e "${C}  2.${N} Frontend dev server  - Vite :5173 (hot reload)"
echo -e "${C}  3.${N} Sync completo        - git pull + rebuild + restart"
echo -e "${C}  4.${N} Tests suite          - Verificacion del sistema"
echo -e "${C}  5.${N} Auditor v3           - Escaneo multi-repo"
echo -e "${C}  6.${N} Mirage               - Señuelos y datos falsos"
echo -e "${C}  7.${N} Watcher              - Anti-vigilancia"
echo -e "${C}  8.${N} Guardian Custodian    - Fingerprinting + backup"
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
        echo -e "${G}Arrancando Frontend dev server...${N}"
        cd "$ROOT/tauri-frontend"
        npm run dev
        ;;
    3)
        echo -e "${G}Sync completo...${N}"
        cd "$ROOT"
        bash sync.sh
        ;;
    4)
        echo -e "${G}Ejecutando Tests...${N}"
        cd "$ROOT/redteam"
        python3 run_all_tests.py
        ;;
    5)
        echo -e "${G}Ejecutando Auditor v3...${N}"
        cd "$ROOT"
        python3 source_seal_audit_v3.py
        ;;
    6)
        echo -e "${G}Ejecutando Mirage...${N}"
        cd "$ROOT"
        python3 mirage.py
        ;;
    7)
        echo -e "${G}Ejecutando Watcher...${N}"
        cd "$ROOT"
        bash watcher.sh
        ;;
    8)
        echo -e "${G}Ejecutando Guardian Custodian...${N}"
        cd "$ROOT"
        bash guardian_custodian.sh
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
