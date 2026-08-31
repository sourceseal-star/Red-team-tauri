#!/bin/bash
# mesh/discovery.sh - Detección de Dispositivos para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Escanear todos los métodos disponibles
scan_all() {
    info "Escaneando todos los métodos de detección..."

    # WiFi
    if check_wifi; then
        info "Escaneando red WiFi..."
        scan_wifi_networks
    else
        warning "WiFi no disponible"
    fi

    # Bluetooth
    if check_bluetooth; then
        info "Escaneando Bluetooth..."
        scan_bluetooth_devices
    else
        warning "Bluetooth no disponible"
    fi

    # Radio (si está habilitado)
    if [ "$RADIO_ENABLED" = "true" ]; then
        info "Escaneando Radio Aficionados..."
        # Esto es más complejo y requiere hardware específico
        warning "Detección de Radio Aficionados no implementada aún"
    fi

    # Satélite (si está habilitado)
    if [ "$SATELLITE_ENABLED" = "true" ]; then
        info "Escaneando dispositivos satelitales..."
        warning "Detección de dispositivos satelitales no implementada aún"
    fi
}

# Escanear redes WiFi
scan_wifi_networks() {
    local output_file="$TEMP_DIR/wifi_scan_$(date +%s).txt"

    info "Escaneando redes WiFi cercanas..."
    termux-wifi-scan 2>/dev/null > "$output_file"

    if [ -f "$output_file" ]; then
        local networks=$(jq -r '.[] | "\(.ssid) | \(.bssid) | \(.signal_strength) | \(.encryption)"' "$output_file" 2>/dev/null)

        if [ -n "$networks" ]; then
            echo -e "\033[1;34m📡 REDES WIFI CERCANAS:\033[0m"
            echo "$networks" | sed 's/|/ | /g'
            echo ""
        else
            warning "No se encontraron redes WiFi"
        fi

        rm -f "$output_file"
    else
        error "Error al escanear redes WiFi"
    fi
}

# Escanear dispositivos Bluetooth
scan_bluetooth_devices() {
    if ! command -v hcitool &>/dev/null; then
        error "hcitool no está instalado"
        return 1
    fi

    # Activar Bluetooth
    termux-bluetooth-enable 2>/dev/null

    info "Escaneando dispositivos Bluetooth..."
    timeout 8 hcitool scan 2>/dev/null | grep -v "Scanning" | grep -v "^$" | while read -r line; do
        local mac=$(echo "$line" | awk '{print $1}')
        local name=$(echo "$line" | awk '{print $2}')

        # Verificar si es un dispositivo COM-LINK
        if [[ "$name" == *"COM-LINK"* ]]; then
            echo -e "\033[1;32m$mac $name (COM-LINK)\033[0m"
        else
            echo "$mac $name"
        fi
    done
}

# Listar dispositivos COM-LINK conocidos
list_known_devices() {
    info "Dispositivos COM-LINK conocidos:"

    # Buscar en la red local
    if check_wifi || check_lan; then
        discover_devices
    fi

    # Buscar en Bluetooth
    if check_bluetooth; then
        scan_bluetooth_devices | grep "COM-LINK"
    fi
}

# Añadir dispositivo conocido
add_known_device() {
    local ip="$1"
    local name="$2"
    local device_id="$3"

    if [ -z "$ip" ]; then
        error "Debes especificar una IP"
        return 1
    fi

    # Guardar en archivo de dispositivos conocidos
    local known_devices_file="$DATA_DIR/known_devices.json"

    if [ ! -f "$known_devices_file" ]; then
        echo '{"devices": {}}' > "$known_devices_file"
    fi

    jq --arg ip "$ip" \
       --arg name "${name:-Unknown}" \
       --arg device_id "${device_id:-unknown}" \
       --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       '.devices[$ip] = {"name": $name, "device_id": $device_id, "last_seen": $timestamp}' \
       "$known_devices_file" > "$known_devices_file.tmp" && mv "$known_devices_file.tmp" "$known_devices_file"

    success "Dispositivo $ip añadido a la lista de conocidos"
    return 0
}

# Menú de detección
discovery_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🔍 DETECCIÓN DE DISPOSITIVOS\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Escanear todos los métodos"
    echo "2️⃣  Escanear redes WiFi"
    echo "3️⃣  Escanear Bluetooth"
    echo "4️⃣  Listar dispositivos COM-LINK conocidos"
    echo "5️⃣  Añadir dispositivo conocido manualmente"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1) scan_all ;;
        2) scan_wifi_networks ;;
        3) scan_bluetooth_devices ;;
        4) list_known_devices ;;
        5)
            read -p "🌐 IP: " ip
            read -p "👤 Nombre (opcional): " name
            read -p "🆔 ID del dispositivo (opcional): " device_id
            add_known_device "$ip" "$name" "$device_id"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    discovery_menu
}

# Punto de entrada: no ejecutar el menú cuando el módulo se carga con source.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [ $# -eq 0 ]; then
        discovery_menu
    else
        case "$1" in
            "scan_all") scan_all ;;
            "scan_wifi") scan_wifi_networks ;;
            "scan_bt") scan_bluetooth_devices ;;
            "list") list_known_devices ;;
            "add")
                shift
                add_known_device "$@"
                ;;
            *) error "Comando no válido" ;;
        esac
    fi
fi
