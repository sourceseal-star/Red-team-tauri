#!/bin/bash
# scripts/soundmodem_setup.sh - Configuración de Sound Modem para COM-LINK v3.0

# ============================================================
# CONFIGURACIÓN
# ============================================================
SOUNDMODEM_CONFIG="${1:-$INSTALL_DIR/data/soundmodem.conf}"
RADIO_FREQUENCY="${2:-$RADIO_FREQUENCY}"
RADIO_MODE="${3:-$RADIO_MODE}"
RADIO_BAUDRATE="${4:-$RADIO_BAUDRATE}"
SATELLITE_DEVICE="${5:-$SATELLITE_DEVICE}"

# ============================================================
# FUNCIONES
# ============================================================
# Verificar si Sound Modem está instalado
check_soundmodem() {
    if ! command -v soundmodem &>/dev/null; then
        error "Sound Modem no está instalado"
        info "Instálalo con: pkg install soundmodem"
        return 1
    fi
    return 0
}

# Configurar Sound Modem
configure_soundmodem() {
    info "Configurando Sound Modem..."

    # Crear archivo de configuración
    cat > "$SOUNDMODEM_CONFIG" <<EOF
# Configuración de Sound Modem para COM-LINK v3.0
# Generado: $(date)

[Radio]
Port=$SATELLITE_DEVICE
Baudrate=$RADIO_BAUDRATE
Frequency=$RADIO_FREQUENCY
Mode=$RADIO_MODE
PTT=DTR
TXDelay=100
TXTail=100
Slottime=100
Persist=64
FullDuplex=0
EOF

    success "Sound Modem configurado en $SOUNDMODEM_CONFIG"
    return 0
}

# Iniciar Sound Modem
start_soundmodem() {
    info "Iniciando Sound Modem..."

    # Verificar si ya está en ejecución
    if pgrep soundmodem >/dev/null; then
        info "Sound Modem ya está en ejecución"
        return 0
    fi

    # Iniciar Sound Modem
    soundmodem -c "$SOUNDMODEM_CONFIG" >/dev/null 2>&1 &

    sleep 2

    if pgrep soundmodem >/dev/null; then
        success "Sound Modem iniciado"
        info "Usando configuración: $SOUNDMODEM_CONFIG"
        info "Dispositivo: $SATELLITE_DEVICE"
        info "Frecuencia: $RADIO_FREQUENCY MHz"
        info "Modo: $RADIO_MODE"
        info "Velocidad: $RADIO_BAUDRATE baudios"
        return 0
    else
        error "Error al iniciar Sound Modem"
        return 1
    fi
}

# Detener Sound Modem
stop_soundmodem() {
    if pgrep soundmodem >/dev/null; then
        pkill soundmodem
        success "Sound Modem detenido"
        return 0
    else
        info "Sound Modem no está en ejecución"
        return 1
    fi
}

# ============================================================
# PUNTO DE ENTRADA
# ============================================================
if [ $# -eq 0 ]; then
    check_soundmodem || exit 1
    configure_soundmodem || exit 1
    start_soundmodem || exit 1
else
    case "$1" in
        "configure"|"config")
            check_soundmodem || exit 1
            configure_soundmodem
            ;;
        "start")
            check_soundmodem || exit 1
            start_soundmodem
            ;;
        "stop")
            stop_soundmodem
            ;;
        *)
            error "Comando no válido"
            echo "Uso: $0 [configure|start|stop]"
            exit 1
            ;;
    esac
fi
