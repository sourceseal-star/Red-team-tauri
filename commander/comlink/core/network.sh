#!/bin/bash
# core/network.sh - Detección de Redes para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Obtener información de la red
get_network_info() {
    local info=""

    # WiFi
    if check_wifi; then
        local wifi_info=$(termux-wifi-connectioninfo 2>/dev/null)
        local ssid=$(echo "$wifi_info" | jq -r '.ssid // "Unknown"')
        local bssid=$(echo "$wifi_info" | jq -r '.bssid // "Unknown"')
        local ip=$(echo "$wifi_info" | jq -r '.ip_address // "Unknown"')
        local signal=$(echo "$wifi_info" | jq -r '.signal_strength // "Unknown"')
        info+="📶 WiFi: $ssid ($bssid) - IP: $ip - Señal: $signal\n"
    fi

    # Red Celular
    if check_cellular; then
        local cellular_info=$(termux-telephony-device-info 2>/dev/null)
        local carrier=$(echo "$cellular_info" | jq -r '.carrier_name // "Unknown"')
        local network_type=$(echo "$cellular_info" | jq -r '.network_type // "Unknown"')
        local signal_strength=$(echo "$cellular_info" | jq -r '.signal_strength // "Unknown"')
        info+="📱 Celular: $carrier ($network_type) - Señal: $signal_strength\n"
    fi

    # Bluetooth
    if check_bluetooth; then
        local bt_info=$(hcitool dev 2>/dev/null | head -n 1)
        info+="📡 Bluetooth: $bt_info\n"
    fi

    # GPS
    if command -v termux-location &>/dev/null; then
        local gps_info=$(termux-location 2>/dev/null | jq -r '{lat: .latitude, lon: .longitude, acc: .accuracy} | select(.lat != null) | "📍 GPS: \(.lat), \(.lon) (±\(.acc)m)"')
        if [ -n "$gps_info" ]; then
            info+="$gps_info\n"
        fi
    fi

    # Batería
    if command -v termux-battery-status &>/dev/null; then
        local battery_info=$(termux-battery-status 2>/dev/null)
        local percentage=$(echo "$battery_info" | jq -r '.percentage // "Unknown"')
        local status=$(echo "$battery_info" | jq -r '.status // "Unknown"')
        info+="🔋 Batería: $percentage% ($status)\n"
    fi

    echo -e "$info"
}

# Obtener IP local
get_local_ip() {
    if check_wifi; then
        termux-wifi-connectioninfo 2>/dev/null | jq -r '.ip_address // empty'
    elif check_cellular; then
        # Intentar obtener IP celular
        if command -v ifconfig &>/dev/null; then
            ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1
        else
            echo "Unknown"
        fi
    else
        echo "Unknown"
    fi
}

# Obtener MAC local
get_local_mac() {
    if check_wifi; then
        termux-wifi-connectioninfo 2>/dev/null | jq -r '.mac_address // empty'
    else
        ifconfig | grep -Eo '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}' | head -n 1
    fi
}

# Escanear redes WiFi
scan_wifi_networks() {
    termux-wifi-scan 2>/dev/null | jq -r '.[] | "\(.ssid) | \(.bssid) | \(.signal_strength) | \(.encryption)"'
}

# Escanear dispositivos Bluetooth
scan_bluetooth_devices() {
    if command -v hcitool &>/dev/null; then
        hcitool scan 2>/dev/null | grep -v "Scanning" | grep -v "^$"
    else
        error "hcitool no está disponible"
        return 1
    fi
}

# Obtener información del dispositivo
get_device_info() {
    echo "📱 Modelo: $(getprop ro.product.model 2>/dev/null || echo "Unknown")"
    echo "🔧 Fabricante: $(getprop ro.product.manufacturer 2>/dev/null || echo "Unknown")"
    echo "📊 Versión de Android: $(getprop ro.build.version.release 2>/dev/null || echo "Unknown")"
    echo "🆔 ID del dispositivo: $(settings get android_id 2>/dev/null || echo "Unknown")"
    echo "🔢 Número de serie: $(getprop ro.serialno 2>/dev/null || echo "Unknown")"
    echo "💾 Almacenamiento: $(df -h / | tail -n 1 | awk '{print $4 " libre de " $2}')"
    echo "🧠 Memoria: $(free -h 2>/dev/null | grep Mem | awk '{print $4 " libre de " $2}')"
}
