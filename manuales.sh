#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# MANUALES.SH — Centro de documentación en ventana separada de Termux
# Abre todos los manuales, docs, guías y recursos del sistema
# en un menú interactivo navegable. No toca los servicios.
#
# Uso:
#   bash manuales.sh              # menú interactivo
#   bash manuales.sh --termux     # abre en nueva ventana de Termux
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── COLORES ──────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'
BOLD='\033[1m'

# ── ABRIR EN NUEVA VENTANA DE TERMUX SI --termux ──────────────────
if [ "$1" = "--termux" ]; then
    # Intentar abrir nueva sesión de Termux
    if command -v termux-open-url >/dev/null 2>&1; then
        termux-open-url "termux://bash $(realpath "$0")" 2>/dev/null && exit 0
    fi
    # Fallback: usar tmux si está disponible
    if command -v tmux >/dev/null 2>&1; then
        tmux new-session -d -s manuales "bash $(realpath "$0")" 2>/dev/null && \
            echo -e "${G}Abierto en sesión tmux 'manuales'${N}" && \
            echo "Conecta con: tmux attach -t manuales" && exit 0
    fi
    # Si no hay manera, seguir en esta ventana
    echo -e "${Y}No se pudo abrir ventana nueva — continuando aquí${N}"
fi

# ── HELPERS ──────────────────────────────────────────────────────
hr() { echo -e "${B}────────────────────────────────────────────────${N}"; }

viewer() {
    local file="$1" title="$2"
    if [ ! -f "$file" ]; then
        echo -e "  ${R}✗ No encontrado: $file${N}"
        read -p "Presiona Enter para volver..." _
        return 1
    fi
    echo ""
    hr
    echo -e "${B}  $title${N}"
    echo -e "  ${C}$file${N}"
    hr
    echo ""
    if command -v less >/dev/null 2>&1; then
        less "$file"
    elif command -v more >/dev/null 2>&1; then
        more "$file"
    else
        cat "$file"
    fi
}

decrypt_and_view() {
    local enc_file="$ROOT/manual_operaciones.enc"
    local temp_out="${TMPDIR:-$ROOT}/.manual_dec_$$.md"

    if [ ! -f "$enc_file" ]; then
        echo -e "  ${R}✗ No encontrado: $enc_file${N}"
        read -p "Presiona Enter..." _
        return 1
    fi

    echo ""
    hr
    echo -e "${B}  MANUAL CIFRADO — AES-256-CBC${N}"
    hr
    echo -n "  Clave de acceso: "
    read -r -s CLAVE
    echo ""

    if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
        -in "$enc_file" -out "$temp_out" -pass pass:"$CLAVE" 2>/dev/null; then

        if grep -qi "MANUAL\|OPERACION\|SourceSeal" "$temp_out" 2>/dev/null; then
            echo -e "  ${G}✓ Clave correcta${N}"
            if command -v less >/dev/null 2>&1; then
                less "$temp_out"
            else
                cat "$temp_out"
            fi
            rm -f "$temp_out"
            echo -e "  ${G}Temporal borrado${N}"
        else
            echo -e "  ${R}✗ Clave incorrecta${N}"
            rm -f "$temp_out"
        fi
    else
        echo -e "  ${R}✗ Clave incorrecta o error${N}"
        rm -f "$temp_out"
    fi
    read -p "Presiona Enter..." _
}

# ── MENÚS POR CATEGORÍA ───────────────────────────────────────────

menu_principales() {
    while true; do
        clear
        echo ""
        echo -e "${B}╔══════════════════════════════════════════════╗${N}"
        echo -e "${B}║  📚 MANUALES PRINCIPALES                     ║${N}"
        echo -e "${B}╚══════════════════════════════════════════════╝${N}"
        echo ""
        echo -e "  ${C}1${N}  Manual Operativo Completo      ${G}(48KB)${N}"
        echo -e "  ${C}2${N}  Manual Cifrado (.enc)           ${Y}(AES-256)${N}"
        echo -e "  ${C}3${N}  README General"
        echo -e "  ${C}4${N}  Guía de Replit"
        echo -e "  ${C}5${N}  Continuar Aquí (pendientes)"
        echo -e "  ${C}6${N}  Setup Firma APK"
        echo -e "  ${C}0${N}  ← Volver"
        echo ""
        echo -n "  → "
        read -r opt
        case "$opt" in
            1) viewer "$ROOT/MANUAL_OPERATIVO.md" "MANUAL OPERATIVO COMPLETO" ;;
            2) decrypt_and_view ;;
            3) viewer "$ROOT/README.md" "README GENERAL" ;;
            4) viewer "$ROOT/replit.md" "GUÍA DE REPLIT" ;;
            5) viewer "$ROOT/CONTINUAR_AQUI.md" "CONTINUAR AQUÍ" ;;
            6) viewer "$ROOT/SETUP_FIRMA_APK.md" "SETUP FIRMA APK" ;;
            0|q|n) return ;;
        esac
    done
}

menu_arquitectura() {
    while true; do
        clear
        echo ""
        echo -e "${B}╔══════════════════════════════════════════════╗${N}"
        echo -e "${B}║  🏗️  ARQUITECTURA Y SISTEMA                  ║${N}"
        echo -e "${B}╚══════════════════════════════════════════════╝${N}"
        echo ""
        echo -e "  ${C}1${N}  Arquitectura del Sistema"
        echo -e "  ${C}2${N}  Runbook de Operaciones"
        echo -e "  ${C}3${N}  Guía de Build OLLVM"
        echo -e "  ${C}4${N}  Endpoints de Cámaras"
        echo -e "  ${C}5${N}  Redteam README"
        echo -e "  ${C}6${N}  Motor de Cierre README"
        echo -e "  ${C}0${N}  ← Volver"
        echo ""
        echo -n "  → "
        read -r opt
        case "$opt" in
            1) viewer "$ROOT/redteam/docs/ARCHITECTURE.md" "ARQUITECTURA DEL SISTEMA" ;;
            2) viewer "$ROOT/redteam/docs/RUNBOOK.md" "RUNBOOK DE OPERACIONES" ;;
            3) viewer "$ROOT/redteam/docs/OLLVM_BUILD_GUIDE.md" "GUÍA OLLVM" ;;
            4) viewer "$ROOT/docs/CAMERA_ENDPOINTS.md" "ENDPOINTS DE CÁMARAS" ;;
            5) viewer "$ROOT/redteam/README.md" "REDTEAM README" ;;
            6) viewer "$ROOT/motor_cierre/README.md" "MOTOR DE CIERRE" ;;
            0|q|n) return ;;
        esac
    done
}

menu_modulos() {
    while true; do
        clear
        echo ""
        echo -e "${B}╔══════════════════════════════════════════════╗${N}"
        echo -e "${B}║  🧩 MÓDULOS Y COMPONENTES                   ║${N}"
        echo -e "${B}╚══════════════════════════════════════════════╝${N}"
        echo ""
        echo -e "  ${C}1${N}  Protocolo MURCIÉLAGO (Ultrasonidos)"
        echo -e "  ${C}2${N}  Honeypot / Decepción"
        echo -e "  ${C}3${N}  Agente Standalone"
        echo -e "  ${C}4${N}  Native (C/C++)"
        echo -e "  ${C}5${N}  NDR (Detección de Red)"
        echo -e "  ${C}6${N}  OLLVM (Ofuscación)"
        echo -e "  ${C}7${N}  RASP (Protección App)"
        echo -e "  ${C}8${N}  SOAR (Orquestación)"
        echo -e "  ${C}9${N}  TIP (Threat Intel Platform)"
        echo -e "  ${C}10${N} XDR (Detection & Response)"
        echo -e "  ${C}11${N} Build Quickstart"
        echo -e "  ${C}0${N}  ← Volver"
        echo ""
        echo -n "  → "
        read -r opt
        case "$opt" in
            1)  viewer "$ROOT/redteam/murcielago/README.md" "MURCIÉLAGO" ;;
            2)  viewer "$ROOT/redteam/deception/README.md" "DECEPTION/HONEYPOT" ;;
            2b) viewer "$ROOT/honeypot/HONEYPOT_README.md" "HONEYPOT" ;;
            3)  viewer "$ROOT/redteam/agent/standalone/README.md" "AGENT STANDALONE" ;;
            4)  viewer "$ROOT/redteam/native/README.md" "NATIVE C/C++" ;;
            5)  viewer "$ROOT/redteam/ndr/README.md" "NDR" ;;
            6)  viewer "$ROOT/redteam/ollvm/README.md" "OLLVM" ;;
            7)  viewer "$ROOT/redteam/rasp/README.md" "RASP" ;;
            8)  viewer "$ROOT/redteam/soar/README.md" "SOAR" ;;
            9)  viewer "$ROOT/redteam/tip/README.md" "TIP" ;;
            10) viewer "$ROOT/redteam/xdr/README.md" "XDR" ;;
            11) viewer "$ROOT/build/QUICKSTART.md" "BUILD QUICKSTART" ;;
            0|q|n) return ;;
        esac
    done
}

menu_evidencia() {
    while true; do
        clear
        echo ""
        echo -e "${B}╔══════════════════════════════════════════════╗${N}"
        echo -e "${B}║  🔍 EVIDENCIA Y REPORTES                    ║${N}"
        echo -e "${B}╚══════════════════════════════════════════════╝${N}"
        echo ""
        echo -e "  ${C}1${N}  Reporte Más Reciente"
        echo -e "  ${C}2${N}  Evidencia Más Reciente"
        echo -e "  ${C}3${N}  Continuar Aquí (Redteam)"
        echo -e "  ${C}4${N}  Configuración de Defensa"
        echo -e "  ${C}0${N}  ← Volver"
        echo ""
        echo -n "  → "
        read -r opt
        case "$opt" in
            1) viewer "$ROOT/build/reports/latest.md" "REPORTE MÁS RECIENTE" ;;
            2) viewer "$ROOT/evidence/latest.md" "EVIDENCIA MÁS RECIENTE" ;;
            3) viewer "$ROOT/redteam/CONTINUAR_AQUI.md" "CONTINUAR AQUÍ (REDTEAM)" ;;
            4) viewer "$ROOT/redteam/defense/config.yaml" "CONFIG DEFENSA" ;;
            0|q|n) return ;;
        esac
    done
}

menu_scripts() {
    while true; do
        clear
        echo ""
        echo -e "${B}╔══════════════════════════════════════════════╗${N}"
        echo -e "${B}║  🛠️  SCRIPTS Y HERRAMIENTAS                 ║${N}"
        echo -e "${B}╚══════════════════════════════════════════════╝${N}"
        echo ""
        echo -e "  ${C}1${N}  Ver: deploy.sh         ${G}(despliegue completo)${N}"
        echo -e "  ${C}2${N}  Ver: update.sh         ${G}(actualizar + watchdog)${N}"
        echo -e "  ${C}3${N}  Ver: start-termux.sh   ${G}(arranque clásico)${N}"
        echo -e "  ${C}4${N}  Ver: recon.sh          ${G}(red + dispositivos)${N}"
        echo -e "  ${C}5${N}  Ver: cifrar_manual.sh  ${G}(cifrar manual)${N}"
        echo -e "  ${C}6${N}  Ver: acceder_manual.sh ${G}(descifrar manual)${N}"
        echo -e "  ${C}7${N}  Ejecutar recon.sh --status  ${Y}(estado del sistema)${N}"
        echo -e "  ${C}0${N}  ← Volver"
        echo ""
        echo -n "  → "
        read -r opt
        case "$opt" in
            1) viewer "$ROOT/deploy.sh" "DEPLOY.SH" ;;
            2) viewer "$ROOT/update.sh" "UPDATE.SH" ;;
            3) viewer "$ROOT/start-termux.sh" "START-TERMUX.SH" ;;
            4) viewer "$ROOT/recon.sh" "RECON.SH" ;;
            5) viewer "$ROOT/cifrar_manual.sh" "CIFRAR MANUAL" ;;
            6) viewer "$ROOT/acceder_manual.sh" "ACCEDER MANUAL" ;;
            7) bash "$ROOT/recon.sh" --status; read -p "Enter para volver..." _ ;;
            0|q|n) return ;;
        esac
    done
}

# ── ESTADO RÁPIDO DEL SISTEMA ─────────────────────────────────────
system_quick_status() {
    clear
    echo ""
    echo -e "${B}╔══════════════════════════════════════════════╗${N}"
    echo -e "${B}║  📊 ESTADO RÁPIDO                           ║${N}"
    echo -e "${B}╚══════════════════════════════════════════════╝${N}"
    echo ""

    for svc in "Dashboard:8001:dashboard_server.py" "Motor:8000:uvicorn.*main:app.*8000" "Vite:5173:vite"; do
        name=$(echo "$svc" | cut -d: -f1)
        port=$(echo "$svc" | cut -d: -f2)
        pattern=$(echo "$svc" | cut -d: -f3)
        if pgrep -f "$pattern" >/dev/null 2>&1; then
            echo -e "  ${G}✓${N} $name (:$port) — ${G}ONLINE${N}"
        else
            echo -e "  ${R}✗${N} $name (:$port) — ${R}OFFLINE${N}"
        fi
    done

    echo ""
    echo -e "  ${C}Manuales disponibles:${N}"
    count=0
    for f in MANUAL_OPERATIVO.md README.md replit.md docs/CAMERA_ENDPOINTS.md \
             redteam/docs/ARCHITECTURE.md redteam/docs/RUNBOOK.md \
             motor_cierre/README.md redteam/README.md; do
        [ -f "$ROOT/$f" ] && count=$((count+1))
    done
    echo -e "  ${G}$count${N} documentos accesibles"
    echo ""

    # Git status
    cd "$ROOT"
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
    commit=$(git rev-parse --short HEAD 2>/dev/null || echo "?")
    echo -e "  Git: ${C}$branch${N} @ ${C}$commit${N}"

    echo ""
    read -p "Presiona Enter para volver..." _
}

# ── MENÚ PRINCIPAL ────────────────────────────────────────────────
while true; do
    clear
    echo ""
    echo -e "${B}╔══════════════════════════════════════════════╗${N}"
    echo -e "${B}║  🛡️  SOURCESEAL — CENTRO DE MANUALES          ║${N}"
    echo -e "${B}║     Red-Team-Tauri · Sala de Guerra           ║${N}"
    echo -e "${B}╠══════════════════════════════════════════════╣${N}"
    echo -e "${B}║  Todo documentado · Navegable · Offline       ║${N}"
    echo -e "${B}╚══════════════════════════════════════════════╝${N}"
    echo ""
    echo -e "  ${C}1${N}  📚 Manuales principales"
    echo -e "  ${C}2${N}  🏗️  Arquitectura y sistema"
    echo -e "  ${C}3${N}  🧩 Módulos y componentes"
    echo -e "  ${C}4${N}  🔍 Evidencia y reportes"
    echo -e "  ${C}5${N}  🛠️  Scripts y herramientas"
    echo -e "  ${C}6${N}  📊 Estado del sistema"
    echo -e "  ${C}0${N}  🚪 Salir"
    echo ""
    echo -n "  → "
    read -r opt
    case "$opt" in
        1) menu_principales ;;
        2) menu_arquitectura ;;
        3) menu_modulos ;;
        4) menu_evidencia ;;
        5) menu_scripts ;;
        6) system_quick_status ;;
        0|q|exit|salir) clear; echo -e "${G}Hasta luego. Los servicios siguen corriendo.${N}"; exit 0 ;;
        *) ;;
    esac
done
