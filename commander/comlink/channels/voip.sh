#!/bin/bash
# channels/voip.sh - Llamadas VoIP para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar mensaje de voz (no implementado aún, pero se puede añadir)
send_voip() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Por ahora, solo mostramos un mensaje
    info "VoIP no soporta envío de mensajes, solo llamadas. Usa 'comlink voip call <destino>' para llamar."
    return 1
}

# Realizar llamada VoIP
voip_call() {
    local destination="$1"

    # Verificar formato
    if [[ ! "$destination" =~ ^[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+$ ]]; then
        error "Formato de destino no válido. Usa: usuario@servidor"
        return 1
    fi

    # Verificar si hay conexión de red
    if ! check_internet && ! check_lan; then
        error "No hay conexión de red para VoIP"
        return 1
    fi

    # Configurar SIP si no está configurado
    if ! is_sip_configured; then
        configure_sip
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi

    # Iniciar llamada
    info "Llamando a $destination via SIP..."

    # Usar linphonec
    if command -v linphonec &>/dev/null; then
        linphonec -c "call sip:$destination" 2>/dev/null

        if [ $? -eq 0 ]; then
            success "Llamada iniciada a $destination"
            info "Presiona Ctrl+C para terminar la llamada"
            # Esperar a que el usuario termine la llamada
            read -p "Presiona Enter cuando termines la llamada..." _ 2>/dev/null
            linphonec -c "terminate" 2>/dev/null
            return 0
        else
            error "Error al iniciar la llamada con linphonec"
            return 1
        fi
    else
        error "linphonec no está instalado"
        return 1
    fi
}

# Verificar si SIP está configurado
is_sip_configured() {
    if [ -f "$HOME/.linphonerc" ]; then
        return 0
    else
        return 1
    fi
}

# Configurar cliente SIP
configure_sip() {
    if ! command -v linphonec &>/dev/null; then
        error "linphonec no está instalado"
        info "Instálalo con: pkg install linphone"
        return 1
    fi

    info "Configurando cliente SIP..."

    # Crear archivo de configuración
    cat > "$HOME/.linphonerc" <<EOF
[default]
sip_port=$SIP_PORT
audio_port=7078
video_port=9078

[auth_info]
username=$SIP_USERNAME
userid=$SIP_USERNAME
password=$SIP_PASSWORD
realm=$SIP_SERVER
ha1=
algorithm=md5

[proxy]
reg_proxy=proxy:$SIP_SERVER:$SIP_PORT
reg_expires=3600
reg_sendregister=1

[net]
upnp=0
EOF

    chmod 600 "$HOME/.linphonerc"
    info "Configuración SIP guardada en $HOME/.linphonerc"

    # Registrar en el servidor SIP
    linphonec -c "register sip:$SIP_USERNAME:$SIP_PASSWORD@$SIP_SERVER" 2>/dev/null
    if [ $? -eq 0 ]; then
        success "Registrado en servidor SIP: $SIP_SERVER"
        return 0
    else
        error "Error al registrar en servidor SIP"
        return 1
    fi
}

# Configurar Asterisk local
setup_asterisk() {
    if [ "$ASTERISK_ENABLED" != "true" ]; then
        info "Asterisk no está habilitado en la configuración"
        read -p "¿Habilitar Asterisk? (s/n, default: n): " choice
        if [ "${choice:-n}" != "s" ]; then
            return 0
        fi
        ASTERISK_ENABLED=true
        save_config
    fi

    if ! command -v asterisk &>/dev/null; then
        error "Asterisk no está instalado"
        info "Instálalo con: pkg install asterisk"
        return 1
    fi

    info "Configurando Asterisk local..."

    # Crear directorio de configuración
    mkdir -p "$ASTERISK_CONFIG_PATH"

    # Configurar sip.conf
    cat > "$ASTERISK_CONFIG_PATH/sip.conf" <<EOF
[general]
context=default
allowguest=no
allowoverlap=no
bindport=$SIP_PORT
bindaddr=0.0.0.0
srvlookup=yes

[authentication]
auth_type=userpass

[$SIP_USERNAME]
type=friend
context=default
host=dynamic
secret=$SIP_PASSWORD
nat=yes
canreinvite=no
qualify=yes
EOF

    # Configurar extensions.conf
    cat > "$ASTERISK_CONFIG_PATH/extensions.conf" <<EOF
[general]
static=yes
writeprotect=yes

[default]
exten => $SIP_USERNAME,1,Answer()
exten => $SIP_USERNAME,2,Playback(hello-world)
exten => $SIP_USERNAME,3,Hangup()

; Permitir llamadas entre usuarios
exten => _X.,1,Dial(SIP/\${EXTEN},20)
exten => _X.,n,Hangup()
EOF

    # Iniciar Asterisk
    info "Iniciando Asterisk..."
    asterisk -f -C "$ASTERISK_CONFIG_PATH" -p "$ASTERISK_CONFIG_PATH/asterisk.pid" >/dev/null 2>&1 &

    sleep 2

    if [ -f "$ASTERISK_CONFIG_PATH/asterisk.pid" ]; then
        success "Asterisk iniciado (PID: $(cat "$ASTERISK_CONFIG_PATH/asterisk.pid"))"
        info "Servidor SIP local disponible en: $SIP_SERVER:$SIP_PORT"
        info "Usuario: $SIP_USERNAME, Contraseña: $SIP_PASSWORD"
        return 0
    else
        error "Error al iniciar Asterisk"
        return 1
    fi
}

# Detener Asterisk
stop_asterisk() {
    if [ -f "$ASTERISK_CONFIG_PATH/asterisk.pid" ]; then
        local pid=$(cat "$ASTERISK_CONFIG_PATH/asterisk.pid")
        kill "$pid" 2>/dev/null
        rm -f "$ASTERISK_CONFIG_PATH/asterisk.pid"
        success "Asterisk detenido"
        return 0
    else
        info "Asterisk no está en ejecución"
        return 1
    fi
}

# Configurar WebRTC P2P (experimental)
setup_webrtc() {
    if ! command -v python3 &>/dev/null; then
        error "Python3 no está instalado"
        return 1
    fi

    if ! python3 -c "import aiortc" 2>/dev/null; then
        info "aiortc no está instalado"
        read -p "¿Instalar aiortc? (s/n, default: n): " choice
        if [ "${choice:-n}" = "s" ]; then
            pip install aiortc aiohttp 2>/dev/null || error "Error al instalar aiortc"
        else
            return 1
        fi
    fi

    info "WebRTC P2P está listo para usar"
    info "Ejecuta: comlink voip webrtc <destino>"
    return 0
}

# Llamada WebRTC P2P
webrtc_call() {
    local destination="$1"

    error "WebRTC P2P no está implementado: no se inicia ninguna llamada"
    info "Requiere un servidor de señalización y un cliente WebRTC verificado."
    return 1
}

# Menú de VoIP
voip_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📞 LLAMADAS VOIP\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Servidor SIP: $SIP_SERVER"
    echo "  Usuario: $SIP_USERNAME"
    echo "  Puerto: $SIP_PORT"
    echo "  Asterisk: $( [ "$ASTERISK_ENABLED" = "true" ] && echo "Habilitado" || echo "Deshabilitado")"

    echo ""
    echo "1️⃣  Configurar SIP"
    echo "2️⃣  Configurar Asterisk local"
    echo "3️⃣  Iniciar Asterisk"
    echo "4️⃣  Detener Asterisk"
    echo "5️⃣  Realizar llamada SIP"
    echo "6️⃣  Configurar WebRTC P2P"
    echo "7️⃣  Llamada WebRTC P2P"
    echo "8️⃣  Probar conexión SIP"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "🌐 Servidor SIP: " new_server
            read -p "👤 Usuario: " new_user
            read -p "🔑 Contraseña: " new_pass
            read -p "🌐 Puerto (default: $SIP_PORT): " new_port

            [ -n "$new_server" ] && SIP_SERVER="$new_server"
            [ -n "$new_user" ] && SIP_USERNAME="$new_user"
            [ -n "$new_pass" ] && SIP_PASSWORD="$new_pass"
            [ -n "$new_port" ] && SIP_PORT="$new_port"

            save_config
            configure_sip
            ;;
        2)
            setup_asterisk
            ;;
        3)
            setup_asterisk
            ;;
        4)
            stop_asterisk
            ;;
        5)
            read -p "📞 Destino (usuario@servidor): " destination
            voip_call "$destination"
            ;;
        6)
            setup_webrtc
            ;;
        7)
            read -p "📞 Destino (IP o nombre): " destination
            webrtc_call "$destination"
            ;;
        8)
            info "Probando conexión SIP..."
            linphonec -c "info" 2>/dev/null
            read -p "Presiona Enter para continuar..." _ 2>/dev/null
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    voip_menu
}
