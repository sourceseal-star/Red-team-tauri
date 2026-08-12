#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# CONTROL CENTER — Red-Team-Tauri
# Punto unico de acceso a: Corset, Triage, OSINT
# Uso: bash control.sh
# =====================================================================
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Colors (ASCII only)
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'; C='\033[0;36m'; N='\033[0m'

banner() {
    echo ""
    echo -e "${B}======================================================${N}"
    echo -e "${G}  $1${N}"
    echo -e "${B}======================================================${N}"
    echo ""
}

while true; do
    banner "CONTROL CENTER - Red-Team-Tauri"
    echo -e "  ${C}1${N}) Triage Kit (scan de dispositivo Android)"
    echo -e "  ${C}2${N}) Corset Status (scope validator)"
    echo -e "  ${C}3${N}) OSINT Extract (extraccion de entidades)"
    echo -e "  ${C}4${N}) Generate Scope (crear scope.bin / Replit b64)"
    echo -e "  ${C}5${N}) Start Dashboard (backend + frontend)"
    echo -e "  ${C}0${N}) Salir"
    echo ""
    echo -ne "${Y}Selecciona una opcion: ${N}"
    read -r opt

    case "$opt" in
        1)
            banner "TRIAGE KIT"
            bash "$ROOT/triage_kit.sh"
            ;;
        2)
            banner "CORSET STATUS"
            python3 -c "
import sys, os
sys.path.insert(0, os.path.join('$ROOT', 'redteam', 'scripts'))
try:
    if os.environ.get('REPL_ID') or os.environ.get('REPL_SLUG'):
        from corset_replit import CorsetReplit
        c = CorsetReplit(enforce=False)
    else:
        from corset_termux import CorsetTermux
        c = CorsetTermux(enforce=False)
    print('Status:', c.status())
except Exception as e:
    print('Error:', e)
"
            ;;
        3)
            banner "OSINT EXTRACT"
            echo -n "Pega el texto a analizar (Ctrl+D para terminar): "
            text=$(cat)
            python3 -c "
import sys, os, json
sys.path.insert(0, os.path.join('$ROOT', 'redteam', 'scripts'))
try:
    from osint_module import extract_from_text
    result = extract_from_text('''$text''')
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print('Error:', e)
"
            ;;
        4)
            banner "GENERATE SCOPE"
            echo -n "Redes (separadas por coma, ej 192.168.1.0/24,10.0.0.0/8): "
            read -r networks
            echo -n "Modo: (1) Termux/archivo binario  (2) Replit/base64: "
            read -r mode
            if [ "$mode" = "2" ]; then
                python3 redteam/scripts/generate_scope.py --networks "$networks" --replit
            else
                python3 redteam/scripts/generate_scope.py --networks "$networks" --output "$HOME/.corset/scope.bin"
                echo -e "${G}Scope guardado en ~/.corset/scope.bin${N}"
            fi
            ;;
        5)
            banner "START DASHBOARD"
            if [ -n "$(command -v termux-wake-lock 2>/dev/null)" ]; then
                bash "$ROOT/start-termux.sh"
            else
                bash "$ROOT/replit_start.sh"
            fi
            ;;
        0)
            echo -e "${G}Hasta luego.${N}"
            exit 0
            ;;
        *)
            echo -e "${R}Opcion invalida${N}"
            ;;
    esac

    echo ""
    echo -ne "${Y}Presiona Enter para continuar...${N}"
    read -r
done
