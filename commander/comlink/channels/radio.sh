#!/bin/bash
# channels/radio.sh - Comunicación por Radio Aficionados para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar mensaje via Radio
send_radio() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    if [ "$RADIO_ENABLED" != "true" ]; then
        error "Radio Aficionados no está habilitado"
        return 1
    fi

    # Verificar hardware
    if ! command -v soundmodem &>/dev/null; then
        error "Sound Modem no está instalado"
        info "Instálalo con: pkg install soundmodem"
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

    info "Enviando mensaje via Radio a $destination..."

    # Configurar Sound Modem
    local soundmodem_config="$TEMP_DIR/soundmodem.conf"
    cat > "$soundmodem_config" <<EOF
[Radio]
Port=/dev/ttyS0
Baudrate=$RADIO_BAUDRATE
Frequency=$RADIO_FREQUENCY
Mode=$RADIO_MODE
EOF

    # Iniciar Sound Modem
    soundmodem -c "$soundmodem_config" &

    local pid=$!
    sleep 2

    # Verificar si Sound Modem está en ejecución
    if ! kill -0 "$pid" 2>/dev/null; then
        error "Error al iniciar Sound Modem"
        return 1
    fi

    # Enviar mensaje via AX.25
    # Nota: Esto es un ejemplo simplificado. En la práctica, necesitarías:
    # 1. Un TNC (Terminal Node Controller) o Sound Modem configurado
    # 2. Software como ax25-tools o direwolf
    # 3. Una radio compatible

    info "Transmitiendo mensaje via $RADIO_MODE a $RADIO_FREQUENCY MHz..."
    echo "$final_message" > /dev/ttyS0

    if [ $? -eq 0 ]; then
        success "Mensaje enviado via Radio"
        kill "$pid" 2>/dev/null
        return 0
    else
        error "Error al enviar mensaje via Radio"
        kill "$pid" 2>/dev/null
        return 1
    fi
}

# Configurar Sound Modem
setup_soundmodem() {
    if [ "$RADIO_ENABLED" != "true" ]; then
        info "Radio Aficionados no está habilitado en la configuración"
        read -p "¿Habilitar Radio Aficionados? (s/n, default: n): " choice
        if [ "${choice:-n}" != "s" ]; then
            return 0
        fi
        RADIO_ENABLED=true
        save_config
    fi

    if ! command -v soundmodem &>/dev/null; then
        error "Sound Modem no está instalado"
        info "Instálalo con: pkg install soundmodem"
        return 1
    fi

    info "Configurando Sound Modem..."

    # Crear configuración
    cat > "$INSTALL_DIR/scripts/soundmodem.conf" <<EOF
[Radio]
Port=$SATELLITE_DEVICE
Baudrate=$RADIO_BAUDRATE
Frequency=$RADIO_FREQUENCY
Mode=$RADIO_MODE
EOF

    success "Sound Modem configurado"
    info "Edita $INSTALL_DIR/scripts/soundmodem.conf para ajustar la configuración"
    return 0
}

# Configurar AX.25
setup_ax25() {
    if ! command -v ax25 &>/dev/null; then
        error "ax25-tools no está instalado"
        info "Instálalo con: pkg install ax25-tools"
        return 1
    fi

    info "Configurando AX.25..."

    # Configurar axports
    cat > "/etc/ax25/axports" <<EOF
# /etc/ax25/axports
#
# The format for the axports file is:
# name callsign speed paclen window description
comlink $DEVICE_ID-$RADIO_MODE $RADIO_BAUDRATE 255 7 144.390 MHz
EOF

    # Configurar ax25d.conf
    cat > "/etc/ax25/ax25d.conf" <<EOF
[
$DEVICE_ID
N0CALL Via Radio
144.390
1200
255
7
]
EOF

    success "AX.25 configurado"
    return 0
}

# Menú de Radio
radio_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📻 RADIO AFICIONADOS\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Habilitado: $( [ "$RADIO_ENABLED" = "true" ] && echo "✅ Sí" || echo "❌ No")"
    echo "  Frecuencia: $RADIO_FREQUENCY MHz"
    echo "  Modo: $RADIO_MODE"
    echo "  Velocidad: $RADIO_BAUDRATE baudios"
    echo "  Dispositivo: $SATELLITE_DEVICE"

    echo ""
    echo "1️⃣  Enviar mensaje"
    echo "2️⃣  Configurar Sound Modem"
    echo "3️⃣  Configurar AX.25"
    echo "4️⃣  Configurar Radio"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "📞 Indicativo o destino: " destination
            read -p "💬 Mensaje: " message

            if [ -z "$destination" ] || [ -z "$message" ]; then
                error "Destino y mensaje no pueden estar vacíos"
                return
            fi

            send_radio "$destination" "$message"
            ;;
        2)
            setup_soundmodem
            ;;
        3)
            setup_ax25
            ;;
        4)
            read -p "📡 ¿Habilitar Radio? (s/n, current: $RADIO_ENABLED): " enabled
            read -p "🎵 Frecuencia (MHz, default: $RADIO_FREQUENCY): " frequency
            read -p "📊 Modo (AX.25, etc., default: $RADIO_MODE): " mode
            read -p "⚡ Velocidad (baudios, default: $RADIO_BAUDRATE): " baudrate
            read -p "🔌 Dispositivo (/dev/ttyS0, etc., default: $SATELLITE_DEVICE): " device

            [ -n "$enabled" ] && RADIO_ENABLED="$enabled"
            [ -n "$frequency" ] && RADIO_FREQUENCY="$frequency"
            [ -n "$mode" ] && RADIO_MODE="$mode"
            [ -n "$baudrate" ] && RADIO_BAUDRATE="$baudrate"
            [ -n "$device" ] && SATELLITE_DEVICE="$device"

            save_config
            success "Configuración de Radio actualizada"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    radio_menu
}
