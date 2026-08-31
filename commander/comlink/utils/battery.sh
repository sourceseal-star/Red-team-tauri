#!/bin/bash
# utils/battery.sh - Utilidades de Batería para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Obtener estado de la batería
get_battery_status() {
    if ! command -v termux-battery-status &>/dev/null; then
        error "termux-battery-status no está disponible"
        return 1
    fi

    local battery_data=$(termux-battery-status 2>/dev/null)

    if [ -z "$battery_data" ]; then
        error "No se pudo obtener el estado de la batería"
        return 1
    fi

    echo "$battery_data"
    return 0
}

# Formatear estado de la batería
format_battery_status() {
    local battery_data="$1"

    local percentage=$(echo "$battery_data" | jq -r '.percentage // "N/A"')
    local status=$(echo "$battery_data" | jq -r '.status // "N/A"')
    local temperature=$(echo "$battery_data" | jq -r '.temperature // "N/A"')
    local voltage=$(echo "$battery_data" | jq -r '.voltage // "N/A"')
    local technology=$(echo "$battery_data" | jq -r '.technology // "N/A"')

    echo "🔋 Batería:
📊 Porcentaje: $percentage%
🔌 Estado: $status
🌡️  Temperatura: $temperature°C
⚡ Voltaje: $voltage mV
🔧 Tecnología: $technology"
}

# Obtener nivel de batería
get_battery_level() {
    local battery_data=$(get_battery_status)
    if [ $? -ne 0 ]; then
        return 1
    fi

    echo "$battery_data" | jq -r '.percentage // "0"'
    return 0
}

# Verificar si el dispositivo está cargando
is_charging() {
    local battery_data=$(get_battery_status)
    if [ $? -ne 0 ]; then
        return 1
    fi

    local status=$(echo "$battery_data" | jq -r '.status // "unknown"')
    if [ "$status" = "CHARGING" ] || [ "$status" = "FULL" ]; then
        return 0
    else
        return 1
    fi
}

# Menú de batería
battery_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🔋 ESTADO DE LA BATERÍA\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    local battery_data=$(get_battery_status)
    if [ $? -eq 0 ]; then
        format_battery_status "$battery_data"
    fi

    echo ""
    echo "1️⃣  Actualizar"
    echo "2️⃣  Configurar alertas de batería baja"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            local battery_data=$(get_battery_status)
            if [ $? -eq 0 ]; then
                format_battery_status "$battery_data"
            fi
            ;;
        2)
            read -p "🔢 Nivel de batería para alerta (1-100, default: 20): " level
            level="${level:-20}"

            if [ "$level" -ge 1 ] && [ "$level" -le 100 ]; then
                # Guardar configuración de alerta
                jq --argjson level "$level" '.battery_alert_level = $level' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
                success "Alerta de batería baja configurada a $level%"
            else
                error "Nivel no válido: $level"
            fi
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    battery_menu
}

# Punto de entrada: no ejecutar el menú cuando el módulo se carga con source.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [ $# -eq 0 ]; then
        battery_menu
    else
        case "$1" in
            "status") format_battery_status "$(get_battery_status)" ;;
            "level") get_battery_level ;;
            "charging") is_charging && echo "Cargando" || echo "No cargando" ;;
            *) error "Comando no válido" ;;
        esac
    fi
fi
