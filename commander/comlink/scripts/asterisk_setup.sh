#!/bin/bash
# scripts/asterisk_setup.sh - Configuración de Asterisk para COM-LINK v3.0

# ============================================================
# CONFIGURACIÓN
# ============================================================
ASTERISK_CONFIG_PATH="${1:-$INSTALL_DIR/data/asterisk}"
ASTERISK_USER="${2:-$SIP_USERNAME}"
ASTERISK_PASS="${3:-$SIP_PASSWORD}"
ASTERISK_PORT="${4:-$SIP_PORT}"

# ============================================================
# FUNCIONES
# ============================================================
# Verificar si Asterisk está instalado
check_asterisk() {
    if ! command -v asterisk &>/dev/null; then
        error "Asterisk no está instalado"
        info "Instálalo con: pkg install asterisk"
        return 1
    fi
    return 0
}

# Configurar Asterisk
configure_asterisk() {
    info "Configurando Asterisk..."

    # Crear directorio de configuración
    mkdir -p "$ASTERISK_CONFIG_PATH"

    # Configurar sip.conf
    cat > "$ASTERISK_CONFIG_PATH/sip.conf" <<EOF
[general]
context=default
allowguest=no
allowoverlap=no
bindport=$ASTERISK_PORT
bindaddr=0.0.0.0
srvlookup=yes
udptl=yes

[authentication]
auth_type=userpass

[$ASTERISK_USER]
type=friend
context=default
host=dynamic
secret=$ASTERISK_PASS
nat=yes
canreinvite=no
qualify=yes
dtmfmode=rfc2833
EOF

    # Configurar extensions.conf
    cat > "$ASTERISK_CONFIG_PATH/extensions.conf" <<EOF
[general]
static=yes
writeprotect=yes
autofallthrough=yes
clearglobalvars=no

[globals]
CONSOLE=Console/dsp

[default]
exten => s,1,Answer()
exten => s,n,Playback(hello-world)
exten => s,n,Hangup()

; Permitir llamadas entre usuarios
exten => _X.,1,Dial(SIP/\${EXTEN},20,tr)
exten => _X.,n,Hangup()

; Llamadas de emergencia
exten => 911,1,Dial(SIP/emergency)
exten => 911,n,Hangup()
EOF

    # Configurar modules.conf (cargar módulos necesarios)
    cat > "$ASTERISK_CONFIG_PATH/modules.conf" <<EOF
[modules]
autoload=yes
;
; Módulos necesarios para COM-LINK
;
load => chan_sip.so
load => pbx_config.so
load => res_pjsip.so
load => res_pjsip_pubsub.so
EOF

    # Configurar logger.conf
    cat > "$ASTERISK_CONFIG_PATH/logger.conf" <<EOF
[general]
dateformat=%F %T
;
[logfiles]
console => notice,warning,error
full => notice,warning,error,debug,verbose
EOF

    success "Asterisk configurado en $ASTERISK_CONFIG_PATH"
    return 0
}

# Iniciar Asterisk
start_asterisk() {
    info "Iniciando Asterisk..."

    # Verificar si ya está en ejecución
    if [ -f "$ASTERISK_CONFIG_PATH/asterisk.pid" ]; then
        local pid=$(cat "$ASTERISK_CONFIG_PATH/asterisk.pid")
        if kill -0 "$pid" 2>/dev/null; then
            info "Asterisk ya está en ejecución (PID: $pid)"
            return 0
        else
            rm -f "$ASTERISK_CONFIG_PATH/asterisk.pid"
        fi
    fi

    # Iniciar Asterisk
    asterisk -f -C "$ASTERISK_CONFIG_PATH" -p "$ASTERISK_CONFIG_PATH/asterisk.pid" >/dev/null 2>&1 &

    sleep 2

    if [ -f "$ASTERISK_CONFIG_PATH/asterisk.pid" ]; then
        local pid=$(cat "$ASTERISK_CONFIG_PATH/asterisk.pid")
        success "Asterisk iniciado (PID: $pid)"
        info "Servidor SIP disponible en: $(get_local_ip):$ASTERISK_PORT"
        info "Usuario: $ASTERISK_USER, Contraseña: $ASTERISK_PASS"
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

# Reiniciar Asterisk
restart_asterisk() {
    stop_asterisk
    sleep 1
    start_asterisk
}

# ============================================================
# PUNTO DE ENTRADA
# ============================================================
if [ $# -eq 0 ]; then
    check_asterisk || exit 1
    configure_asterisk || exit 1
    start_asterisk || exit 1
else
    case "$1" in
        "configure"|"config")
            check_asterisk || exit 1
            configure_asterisk
            ;;
        "start")
            check_asterisk || exit 1
            start_asterisk
            ;;
        "stop")
            stop_asterisk
            ;;
        "restart")
            restart_asterisk
            ;;
        *)
            error "Comando no válido"
            echo "Uso: $0 [configure|start|stop|restart]"
            exit 1
            ;;
    esac
fi
