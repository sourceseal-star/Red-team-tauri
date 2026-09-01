#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════
# COMMANDER + COM-LINK v3.6.0 — Dashboard Unificado
# Punto de entrada único para auditoría (Commander) y 
# comunicación de emergencia (COM-LINK)
# ════════════════════════════════════════════════════════════════════
set -e

VERSION="3.6.0"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMANDER="$ROOT/commander.py"
COMLINK="$ROOT/comlink/comlink.sh"
QUICKSTART="$ROOT/quickstart.sh"

# Colores
R='\033[0;31m'
G='\033[0;32m'
Y='\033[1;33m'
C='\033[0;36m'
B='\033[0;34m'
P='\033[0;35m'
W='\033[1;37m'
N='\033[0m'

# ════════════════════════════════════════════════════════════════════
# FUNCIONES DE UI
# ════════════════════════════════════════════════════════════════════

banner() {
    clear 2>/dev/null || true
    echo ""
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
    echo -e "${W}  ⚡ COMMANDER + COM-LINK v${VERSION} — Dashboard Unificado${N}"
    echo -e "${C}═══════════════════════════════════════════════════════${N}"
}

separator() {
    echo -e "${C}───────────────────────────────────────────────────────${N}"
}

ok()   { echo -e "  ${G}✅${N} $1"; }
fail() { echo -e "  ${R}❌${N} $1"; }
warn() { echo -e "  ${Y}⚠️${N} $1"; }
info() { echo -e "  ${B}ℹ️${N} $1"; }

pause() {
    echo ""
    echo -e "${Y}Presiona Enter para continuar...${N}"
    read -r
}

# ════════════════════════════════════════════════════════════════════
# VERIFICACIÓN DE DEPENDENCIAS
# ════════════════════════════════════════════════════════════════════

check_commander_deps() {
    echo -e "\n${B}── Commander ──${N}"
    
    command -v python3 >/dev/null 2>&1 && ok "Python3: $(python3 --version 2>&1)" || fail "Python3 no encontrado"
    command -v nmap >/dev/null 2>&1 && ok "nmap disponible" || fail "nmap no instalado (pkg install nmap)"
    command -v whois >/dev/null 2>&1 && ok "whois disponible" || warn "whois no instalado (OSINT limitado)"
    command -v sqlite3 >/dev/null 2>&1 && ok "sqlite3 disponible" || fail "sqlite3 no instalado"
    
    python3 -c "from Crypto.Cipher import AES" 2>/dev/null && ok "pycryptodome OK" || warn "pip install pycryptodome"
    python3 -c "import sqlite3" 2>/dev/null && ok "sqlite3 (stdlib) OK" || fail "sqlite3 stdlib no disponible"
    
    [ -f "$COMMANDER" ] && ok "commander.py encontrado" || fail "commander.py no encontrado"
}

check_comlink_deps() {
    echo -e "\n${B}── COM-LINK ──${N}"
    
    command -v jq >/dev/null 2>&1 && ok "jq disponible" || fail "jq no instalado (pkg install jq)"
    command -v sqlite3 >/dev/null 2>&1 && ok "sqlite3 disponible" || fail "sqlite3 no instalado"
    command -v curl >/dev/null 2>&1 && ok "curl disponible" || fail "curl no instalado"
    command -v openssl >/dev/null 2>&1 && ok "openssl disponible" || fail "openssl no instalado"
    
    # termux-api (solo en Termux)
    if [ -d "/data/data/com.termux" ]; then
        command -v termux-sms-send >/dev/null 2>&1 && ok "termux-sms-send disponible" || warn "termux-api no instalado (SMS no disponible)"
        command -v termux-location >/dev/null 2>&1 && ok "termux-location disponible" || warn "GPS no disponible"
    else
        info "No es Termux — funciones SMS/GPS limitadas"
    fi
    
    # Opcionales
    command -v hcitool >/dev/null 2>&1 && ok "hcitool (Bluetooth) disponible" || warn "Bluetooth no disponible"
    command -v asterisk >/dev/null 2>&1 && ok "Asterisk (VoIP) disponible" || warn "VoIP no disponible"
    
    [ -f "$COMLINK" ] && ok "comlink.sh encontrado" || fail "comlink.sh no encontrado"
}

check_deps() {
    banner
    echo -e "${W}  🔍 Verificación de Dependencias${N}"
    separator
    
    check_commander_deps
    check_comlink_deps
    
    echo ""
    separator
    echo -e "${W}  Resumen:${N}"
    info "Commander: auditoría de red + OSINT + forense"
    info "COM-LINK: 7 adaptadores; canales operativos según hardware y configuración"
    pause
}

# ════════════════════════════════════════════════════════════════════
# ACCIONES COMMANDER
# ════════════════════════════════════════════════════════════════════

run_commander_menu() {
    if [ ! -f "$COMMANDER" ]; then
        fail "commander.py no encontrado en $COMMANDER"
        pause
        return
    fi
    echo -e "\n${G}🛡️  Iniciando Commander...${N}\n"
    python3 "$COMMANDER"
    pause
}

run_commander_auto() {
    local target="$1"
    if [ -z "$target" ]; then
        echo -ne "${Y}🌐 Rango a auditar (ej: 192.168.1.0/24): ${N}"
        read -r target
    fi
    [ -z "$target" ] && return
    
    echo -ne "${Y}📧 Email para informe (Enter para omitir): ${N}"
    read -r email
    
    local args="--auto $target"
    [ -n "$email" ] && args="$args --email $email"
    
    echo -e "\n${G}🛡️  Ejecutando auditoría de $target...${N}\n"
    python3 "$COMMANDER" $args
    pause
}

run_osint_ip() {
    echo -ne "${Y}🌐 IP a investigar: ${N}"
    read -r ip
    [ -z "$ip" ] && return
    python3 "$COMMANDER" --osint-ip "$ip"
    pause
}

run_osint_domain() {
    echo -ne "${Y}🌐 Dominio a investigar: ${N}"
    read -r domain
    [ -z "$domain" ] && return
    python3 "$COMMANDER" --osint-domain "$domain"
    pause
}

run_osint_email() {
    echo -ne "${Y}📧 Email a investigar: ${N}"
    read -r email
    [ -z "$email" ] && return
    python3 "$COMMANDER" --osint-email "$email"
    pause
}

run_scan_network() {
    echo -ne "${Y}🌐 IP o rango: ${N}"
    read -r target
    [ -z "$target" ] && return
    python3 "$COMMANDER" --scan-network "$target"
    pause
}

run_scan_cameras() {
    echo -ne "${Y}🌐 Rango para cámaras: ${N}"
    read -r target
    [ -z "$target" ] && return
    python3 "$COMMANDER" --scan-cameras "$target"
    pause
}

run_list_audits() {
    python3 "$COMMANDER" --list
    echo ""
    echo -ne "${Y}ID a reanudar (Enter para omitir): ${N}"
    read -r scan_id
    [ -z "$scan_id" ] && return
    python3 "$COMMANDER" --resume "$scan_id"
    pause
}

# ════════════════════════════════════════════════════════════════════
# ACCIONES COM-LINK
# ════════════════════════════════════════════════════════════════════

run_comlink_menu() {
    if [ ! -f "$COMLINK" ]; then
        fail "comlink.sh no encontrado en $COMLINK"
        warn "Ejecuta: cd comlink && ./install.sh"
        pause
        return
    fi
    echo -e "\n${G}🚨 Iniciando COM-LINK...${N}\n"
    bash "$COMLINK"
    pause
}

run_comlink_sms() {
    echo -ne "${Y}📱 Número (ej: +573001234567): ${N}"
    read -r number
    echo -ne "${Y}💬 Mensaje: ${N}"
    read -r message
    [ -z "$number" ] || [ -z "$message" ] && return
    bash "$COMLINK" sms "$number" "$message"
    pause
}

run_comlink_telegram() {
    echo -ne "${Y}💬 Mensaje: ${N}"
    read -r message
    [ -z "$message" ] && return
    bash "$COMLINK" telegram "$message"
    pause
}

run_comlink_location() {
    bash "$COMLINK" location
    pause
}

run_comlink_emergency() {
    echo -ne "${Y}📱 Número de emergencia: ${N}"
    read -r number
    [ -z "$number" ] && return
    bash "$COMLINK" emergency "$number"
    pause
}

run_comlink_mesh() {
    bash "$COMLINK" mesh
    pause
}

run_comlink_queue() {
    bash "$COMLINK" queue
    pause
}

run_comlink_status() {
    bash "$COMLINK" status
    pause
}

run_comlink_config() {
    bash "$COMLINK" config
    pause
}

# ════════════════════════════════════════════════════════════════════
# ACCIONES DE SISTEMA
# ════════════════════════════════════════════════════════════════════

run_quickstart() {
    if [ -f "$QUICKSTART" ]; then
        bash "$QUICKSTART"
    else
        fail "quickstart.sh no encontrado"
    fi
    pause
}

run_deps() {
    check_deps
}

run_clean_logs() {
    echo -e "\n${Y}🧹 Limpiando logs...${N}"
    
    # Commander logs
    [ -f ~/commander.log ] && echo "" > ~/commander.log && ok "commander.log limpiado"
    
    # COM-LINK logs
    local comlink_logs_dir="$ROOT/comlink/data/logs"
    if [ -d "$comlink_logs_dir" ]; then
        rm -f "$comlink_logs_dir"/comlink_*.log 2>/dev/null
        ok "Logs de COM-LINK limpiados"
    fi
    
    # DB temporal
    [ -f /tmp/commander_test.db ] && rm -f /tmp/commander_test.db
    
    echo -e "${G}✅ Limpieza completada${N}"
    pause
}

run_update() {
    echo -e "\n${Y}🔄 Actualizando desde GitHub...${N}"
    cd "$ROOT"
    
    if ! command -v git >/dev/null 2>&1; then
        fail "git no instalado"
        pause
        return
    fi
    
    git fetch origin 2>&1 | head -5
    
    local changes=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$changes" -gt 0 ]; then
        warn "Tienes $changes archivos modificados localmente"
        echo -ne "${Y}¿Stash + actualizar? (s/n): ${N}"
        read -r confirm
        [ "$confirm" = "s" ] || [ "$confirm" = "S" ] || return
        git stash 2>&1 | head -3
    fi
    
    git pull origin main 2>&1 | head -10
    ok "Actualización completada"
    
    # Actualizar COM-LINK si hay cambios
    if [ -f "$COMLINK" ]; then
        chmod -R +x "$ROOT/comlink"/*.sh "$ROOT/comlink"/core/*.sh "$ROOT/comlink"/channels/*.sh \
            "$ROOT/comlink"/mesh/*.sh "$ROOT/comlink"/utils/*.sh "$ROOT/comlink"/scripts/*.sh 2>/dev/null
    fi
    
    pause
}

# ════════════════════════════════════════════════════════════════════
# MENÚ PRINCIPAL
# ════════════════════════════════════════════════════════════════════

main_menu() {
    while true; do
        banner
        
        # Sección Auditoría
        echo -e "\n  ${W}🛡️  AUDITORÍA (Commander)${N}"
        separator
        echo -e "  ${G}1${N}  Escaneo de red completo"
        echo -e "  ${G}2${N}  Detección de cámaras IP"
        echo -e "  ${G}3${N}  OSINT en IP"
        echo -e "  ${G}4${N}  OSINT en dominio (WHOIS+DNS+Subdominios)"
        echo -e "  ${G}5${N}  OSINT en email (MX+SPF+DMARC)"
        echo -e "  ${G}6${N}  Auditoría completa (red + cámaras + OSINT)"
        echo -e "  ${G}7${N}  Listar y reanudar auditorías"
        echo -e "  ${G}8${N}  Menú completo de Commander"
        
        # Sección Comunicación
        echo -e "\n  ${W}🚨 COMUNICACIÓN (COM-LINK)${N}"
        separator
        echo -e "  ${P}C1${N} Enviar SMS"
        echo -e "  ${P}C2${N} Enviar Telegram"
        echo -e "  ${P}C3${N} Enviar Ubicación GPS"
        echo -e "  ${P}C4${N} Modo Emergencia (todo en 1)"
        echo -e "  ${P}C5${N} Menú Mesh (WiFi + Bluetooth)"
        echo -e "  ${P}C6${N} Cola de Mensajes"
        echo -e "  ${P}C7${N} Estado del Sistema"
        echo -e "  ${P}C8${N} Configuración COM-LINK"
        echo -e "  ${P}C9${N} Menú completo de COM-LINK"
        
        # Sección OSIRIS
        echo -e "\n  ${W}🌐 OSIRIS (Integración SourceSeal)${N}"
        separator
        echo -e "  ${P}O1${N} Iniciar conectores (main + cameras + playbooks)"
        echo -e "  ${P}O2${N} Verificar estado (check_all)"
        echo -e "  ${P}O3${N} Instalar para Termux"
        echo -e "  ${P}O4${N} Instalar para Replit"
        echo -e "  ${P}O5${N} Ver logs del conector"
        echo -e "  ${P}O6${N} Configurar .env"
        
  # Sección Sistema
        echo -e "\n  ${W}🔧 SISTEMA${N}"
        separator
        echo -e "  ${B}S1${N} Quickstart + Smoke Tests"
        echo -e "  ${B}S2${N} Ver dependencias"
        echo -e "  ${B}S3${N} Limpiar logs"
        echo -e "  ${B}S4${N} Actualizar desde GitHub"
        
        echo ""
        separator
        echo -e "  ${R}0${N}  Salir"
        separator
        echo -ne "\n${Y}👉 Selecciona una opción: ${N}"
        read -r choice
        
        case "$choice" in
            # Commander
            1) run_scan_network ;;
            2) run_scan_cameras ;;
            3) run_osint_ip ;;
            4) run_osint_domain ;;
            5) run_osint_email ;;
            6) run_commander_auto ;;
            7) run_list_audits ;;
            8) run_commander_menu ;;
            
            # COM-LINK
            c1|C1) run_comlink_sms ;;
            c2|C2) run_comlink_telegram ;;
            c3|C3) run_comlink_location ;;
            c4|C4) run_comlink_emergency ;;
            c5|C5) run_comlink_mesh ;;
            c6|C6) run_comlink_queue ;;
            c7|C7) run_comlink_status ;;
            c8|C8) run_comlink_config ;;
            c9|C9) run_comlink_menu ;;
            
            # Sistema
            s1|S1) run_quickstart ;;
            s2|S2) check_deps ;;
            s3|S3) run_clean_logs ;;
            s4|S4) run_update ;;
            
            # OSIRIS
            o1|O1) run_osiris_start ;;
            o2|O2) run_osiris_check ;;
            o3|O3) run_osiris_termux ;;
            o4|O4) run_osiris_replit ;;
            o5|O5) run_osiris_logs ;;
            o6|O6) run_osiris_config ;;
            
            # Tactical
            t1|T1) run_tactical_master ;;
            t2|T2) run_tactical_worker ;;
            t3|T3) run_tactical_dashboard ;;
            t4|T4) run_tactical_playbook ;;
            t5|T5) run_tactical_alerts ;;
            t6|T6) run_tactical_workers ;;
            
            # Salir
            0|q|Q)
                echo -e "\n${G}👋 ¡Hasta pronto!${N}"
                exit 0
                ;;
            
            *)
                echo -e "\n${R}❌ Opción inválida${N}"
                sleep 1
                ;;
        esac
    done
}

# ════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════

# Verificación inicial mínima
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo -e "${R}❌ Python no encontrado. Instala: pkg install python${N}"
    exit 1
fi

# Argumentos CLI
case "${1:-}" in
    --help|-h)
        echo "COMMANDER + COM-LINK v${VERSION} — Dashboard Unificado"
        echo ""
        echo "Uso:"
        echo "  bash start.sh              # Dashboard interactivo"
        echo "  bash start.sh --check       # Verificar dependencias"
        echo "  bash start.sh --quickstart  # Smoke tests"
        echo "  bash start.sh --commander   # Commander directo"
        echo "  bash start.sh --comlink    # COM-LINK directo"
        echo "  bash start.sh --help        # Esta ayuda"
        echo ""
        echo "Desde el dashboard, usa:"
        echo "  1-8  : Funciones de Commander"
        echo "  C1-C9: Funciones de COM-LINK"
        echo "  S1-S4: Funciones de sistema"
        exit 0
        ;;
    --check)
        check_deps
        exit 0
        ;;
    --quickstart)
        run_quickstart
        exit 0
        ;;
    --commander)
        run_commander_menu
        exit 0
        ;;
    --comlink)
        run_comlink_menu
        exit 0
        ;;
    --version|-v)
        echo "v${VERSION}"
        exit 0
        ;;
esac

# Lanzar dashboard
main_menu
