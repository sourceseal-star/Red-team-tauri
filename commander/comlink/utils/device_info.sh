#!/bin/bash
# utils/device_info.sh - Información del Dispositivo para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Obtener información completa del dispositivo
get_device_info() {
    echo "📱 Información del Dispositivo:"
    echo "=============================="

    # Modelo y fabricante
    echo "📱 Modelo: $(getprop ro.product.model 2>/dev/null || echo "Unknown")"
    echo "🔧 Fabricante: $(getprop ro.product.manufacturer 2>/dev/null || echo "Unknown")"

    # Versión de Android
    echo "📊 Versión de Android: $(getprop ro.build.version.release 2>/dev/null || echo "Unknown")"
    echo "🆔 Versión SDK: $(getprop ro.build.version.sdk 2>/dev/null || echo "Unknown")"

    # Hardware
    echo "🖥️  CPU: $(getprop ro.product.cpu.abi 2>/dev/null || echo "Unknown")"
    echo "💾 Arquitectura: $(uname -m 2>/dev/null || echo "Unknown")"
    echo "🔢 Núcleos: $(nproc 2>/dev/null || echo "Unknown")"

    # Almacenamiento
    echo "💾 Almacenamiento:"
    df -h / | tail -n 1 | awk '{print "  Total: " $2 ", Usado: " $3 ", Libre: " $4}'

    # Memoria
    echo "🧠 Memoria:"
    free -h 2>/dev/null | grep Mem | awk '{print "  Total: " $2 ", Usado: " $3 ", Libre: " $4}'

    # Red
    echo "🌐 Red:"
    echo "  IP Local: $(get_local_ip)"
    echo "  MAC: $(get_local_mac)"
    echo "  WiFi: $(check_wifi && echo "Conectado" || echo "Desconectado")"
    echo "  Celular: $(check_cellular && echo "Conectado" || echo "Desconectado")"
    echo "  Internet: $(check_internet && echo "Conectado" || echo "Desconectado")"

    # Batería
    echo "🔋 Batería:"
    if command -v termux-battery-status &>/dev/null; then
        local battery_data=$(termux-battery-status 2>/dev/null)
        local percentage=$(echo "$battery_data" | jq -r '.percentage // "N/A"')
        local status=$(echo "$battery_data" | jq -r '.status // "N/A"')
        echo "  Nivel: $percentage%"
        echo "  Estado: $status"
    else
        echo "  No disponible"
    fi

    # COM-LINK
    echo "📡 COM-LINK:"
    echo "  Versión: $COM_LINK_VERSION"
    echo "  ID del Dispositivo: $DEVICE_ID"
    echo "  Nombre: $DEVICE_NAME"
}

# Obtener información resumida
get_device_summary() {
    local model=$(getprop ro.product.model 2>/dev/null || echo "Unknown")
    local manufacturer=$(getprop ro.product.manufacturer 2>/dev/null || echo "Unknown")
    local android_version=$(getprop ro.build.version.release 2>/dev/null || echo "Unknown")
    local ip=$(get_local_ip)
    local battery=$(get_battery_level 2>/dev/null || echo "N/A")

    echo "$model ($manufacturer) - Android $android_version - IP: $ip - Batería: $battery%"
}

# Menú de información del dispositivo
device_info_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📱 INFORMACIÓN DEL DISPOSITIVO\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    get_device_info

    echo ""
    echo "1️⃣  Actualizar"
    echo "2️⃣  Copiar información"
    echo "3️⃣  Enviar información a contacto"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            get_device_info
            ;;
        2)
            local info=$(get_device_info)
            echo "$info" | termux-clipboard-set
            success "Información copiada al portapapeles"
            ;;
        3)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos configurados:"
            jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            local info=$(get_device_summary)
            send_with_fallback "$contact_id" "📱 Información del Dispositivo:
$info"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    device_info_menu
}

# Punto de entrada: no ejecutar el menú cuando el módulo se carga con source.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [ $# -eq 0 ]; then
        device_info_menu
    else
        case "$1" in
            "full") get_device_info ;;
            "summary") get_device_summary ;;
            *) error "Comando no válido" ;;
        esac
    fi
fi
