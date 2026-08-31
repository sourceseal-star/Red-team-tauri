#!/bin/bash
# channels/satellite.sh - Comunicación Satelital para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar mensaje via Satélite
send_satellite() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    if [ "$SATELLITE_ENABLED" != "true" ]; then
        error "Comunicación satelital no está habilitada"
        return 1
    fi

    # Verificar dispositivo
    if [ ! -e "$SATELLITE_DEVICE" ]; then
        error "Dispositivo satelital no encontrado: $SATELLITE_DEVICE"
        return 1
    fi

    # Cifrar mensaje si es necesario
    local final_message="$message"
    if [ "$ENCRYPTION_ENABLED" = "true" ] && [ -z "$encrypted" ]; then
        final_message=$(encrypt_message "$message" "$destination")
        if [ $? -ne 0 ]; then
            error "Error cifrando mensaje"
            return 1
        fi
    fi

    info "Enviando mensaje via Satélite a $destination..."

    case $SATELLITE_PROVIDER in
        "iridium")
            send_iridium "$destination" "$final_message"
            ;;
        "globalstar")
            send_globalstar "$destination" "$final_message"
            ;;
        *)
            error "Proveedor satelital no soportado: $SATELLITE_PROVIDER"
            return 1
            ;;
    esac
}

# Enviar mensaje via Iridium
send_iridium() {
    local destination="$1"
    local message="$2"

    # Verificar si el dispositivo Iridium está disponible
    if ! ls "$SATELLITE_DEVICE" 2>/dev/null; then
        error "Dispositivo Iridium no encontrado: $SATELLITE_DEVICE"
        return 1
    fi

    # Configurar velocidad
    stty -F "$SATELLITE_DEVICE" 19200 2>/dev/null

    # Enviar mensaje (formato simplificado)
    # Nota: En la práctica, necesitarías el protocolo específico de Iridium
    echo "AT+SBDWB=$message" > "$SATELLITE_DEVICE"
    sleep 2
    echo "AT+SBDIX" > "$SATELLITE_DEVICE"

    info "Mensaje enviado via Iridium (esto es una simulación)"
    success "Mensaje enviado via Satélite (Iridium)"
    return 0
}

# Enviar mensaje via Globalstar
send_globalstar() {
    local destination="$1"
    local message="$2"

    # Verificar si el dispositivo Globalstar está disponible
    if ! ls "$SATELLITE_DEVICE" 2>/dev/null; then
        error "Dispositivo Globalstar no encontrado: $SATELLITE_DEVICE"
        return 1
    fi

    # Configurar velocidad
    stty -F "$SATELLITE_DEVICE" 9600 2>/dev/null

    # Enviar mensaje (formato simplificado)
    echo "AT+CMGW=\"$destination\"" > "$SATELLITE_DEVICE"
    sleep 1
    echo "$message" > "$SATELLITE_DEVICE"
    sleep 1
    echo -e "\x1A" > "$SATELLITE_DEVICE"  # Ctrl+Z para enviar

    info "Mensaje enviado via Globalstar (esto es una simulación)"
    success "Mensaje enviado via Satélite (Globalstar)"
    return 0
}

# Configurar dispositivo satelital
setup_satellite() {
    if [ "$SATELLITE_ENABLED" != "true" ]; then
        info "Comunicación satelital no está habilitada en la configuración"
        read -p "¿Habilitar comunicación satelital? (s/n, default: n): " choice
        if [ "${choice:-n}" != "s" ]; then
            return 0
        fi
        SATELLITE_ENABLED=true
        save_config
    fi

    info "Configurando dispositivo satelital..."

    # Mostrar dispositivos serial disponibles
    info "Dispositivos serial disponibles:"
    ls /dev/tty* 2>/dev/null | grep -E 'ttyS|ttyUSB|ttyACM'

    read -p "🔌 Dispositivo serial (default: $SATELLITE_DEVICE): " device
    read -p "🛰️  Proveedor (iridium/globalstar, default: $SATELLITE_PROVIDER): " provider

    [ -n "$device" ] && SATELLITE_DEVICE="$device"
    [ -n "$provider" ] && SATELLITE_PROVIDER="$provider"

    save_config
    success "Configuración satelital actualizada"

    # Configurar permisos
    if [ -e "$SATELLITE_DEVICE" ]; then
        chmod 666 "$SATELLITE_DEVICE" 2>/dev/null || warning "No se pudieron cambiar permisos de $SATELLITE_DEVICE"
    fi

    return 0
}

# Menú de Satélite
satellite_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🛰️  COMUNICACIÓN SATELITAL\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Habilitado: $( [ "$SATELLITE_ENABLED" = "true" ] && echo "✅ Sí" || echo "❌ No")"
    echo "  Proveedor: $SATELLITE_PROVIDER"
    echo "  Dispositivo: $SATELLITE_DEVICE"

    echo ""
    echo "1️⃣  Enviar mensaje"
    echo "2️⃣  Configurar dispositivo satelital"
    echo "3️⃣  Probar conexión"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "📞 Número o identificador: " destination
            read -p "💬 Mensaje: " message

            if [ -z "$destination" ] || [ -z "$message" ]; then
                error "Destino y mensaje no pueden estar vacíos"
                return
            fi

            send_satellite "$destination" "$message"
            ;;
        2)
            setup_satellite
            ;;
        3)
            info "Probando conexión satelital..."
            if [ -e "$SATELLITE_DEVICE" ]; then
                stty -F "$SATELLITE_DEVICE" 19200 2>/dev/null
                echo "AT" > "$SATELLITE_DEVICE"
                sleep 2
                if cat "$SATELLITE_DEVICE" 2>/dev/null | grep -q "OK"; then
                    success "Dispositivo satelital responde"
                else
                    warning "No se recibió respuesta del dispositivo satelital"
                fi
            else
                error "Dispositivo satelital no disponible: $SATELLITE_DEVICE"
            fi
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    satellite_menu
}
