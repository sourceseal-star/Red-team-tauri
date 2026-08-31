#!/bin/bash
# mesh/p2p_bluetooth.sh — Bluetooth P2P para COM-LINK v3.0
# Nota: Este archivo fue parte de la estructura original pero no se incluyó
# como sección separada en el documento de diseño. La funcionalidad de
# Bluetooth P2P está cubierta por channels/mesh_bluetooth.sh

source "$(dirname "$0")/../core/logger.sh"
source "$(dirname "$0")/../core/config.sh"

p2p_bt_send() {
    local target_mac="$1"
    local message="$2"
    log_info "Iniciando conexión Bluetooth P2P con $target_mac"
    
    if ! command -v rfcomm &> /dev/null; then
        log_error "rfcomm no disponible. Instala bluez: pkg install bluez"
        return 1
    fi
    
    local port=$(rfcomm bind 0 "$target_mac" 2>/dev/null && echo "0")
    if [ -z "$port" ]; then
        log_error "No se pudo vincular $target_mac"
        return 1
    fi
    
    echo "$message" > /dev/rfcomm0 2>/dev/null
    local result=$?
    rfcomm release 0 2>/dev/null
    return $result
}

p2p_bt_receive() {
    local port="${1:-1}"
    log_info "Escuchando en Bluetooth P2P puerto $port"
    rfcomm listen "$port" 2>/dev/null
}

case "$1" in
    send)   p2p_bt_send "$2" "$3" ;;
    listen) p2p_bt_receive "$2" ;;
    *)      echo "Uso: p2p_bluetooth.sh {send MAC MSG|listen PORT}" ;;
esac
