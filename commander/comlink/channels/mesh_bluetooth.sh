#!/bin/bash
# channels/mesh_bluetooth.sh - Comunicación Mesh Bluetooth para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar mensaje via Mesh Bluetooth
send_mesh_bluetooth() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Verificar Bluetooth
    if ! check_bluetooth; then
        error "Bluetooth no está disponible"
        return 1
    fi

    # Si el destino es una MAC, intentar enviar directamente
    if [[ "$destination" =~ ^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$ ]]; then
        info "Enviando mensaje a $destination via Bluetooth..."

        # Cifrar mensaje si es necesario
        local final_message="$message"
        if [ "$ENCRYPTION_ENABLED" = "true" ] && [ -z "$encrypted" ]; then
            final_message=$(encrypt_message "$message" "$destination")
            if [ $? -ne 0 ]; then
                error "Error cifrando mensaje"
                return 1
            fi
        elif [ -n "$encrypted" ] && [ "$encrypted" != "no_encrypt" ]; then
            final_message="$encrypted"
        fi

        # Enviar via rfcomm
        local channel="${MESH_BT_CHANNEL:-1}"
        local rfcomm_device="/dev/rfcomm0"

        # Conectar a rfcomm
        rfcomm connect "$rfcomm_device" "$destination" "$channel" 2>/dev/null
        if [ $? -ne 0 ]; then
            error "Error al conectar a $destination via rfcomm"
            return 1
        fi

        # Enviar mensaje
        echo -e "$final_message" > "$rfcomm_device"
        if [ $? -eq 0 ]; then
            success "Mensaje enviado a $destination via Bluetooth"
            rfcomm release "$rfcomm_device" 2>/dev/null
            return 0
        else
            error "Error al enviar mensaje via Bluetooth"
            rfcomm release "$rfcomm_device" 2>/dev/null
            return 1
        fi
    else
        # Buscar el dispositivo por nombre
        info "Buscando dispositivo $destination..."
        local target_mac=$(scan_bluetooth_devices | grep "$destination" | awk '{print $1}' | head -n 1)

        if [ -n "$target_mac" ]; then
            send_mesh_bluetooth "$target_mac" "$message" "$encrypted"
            return $?
        else
            error "Dispositivo $destination no encontrado"
            return 1
        fi
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

    # Escanear durante 8 segundos
    timeout 8 hcitool scan 2>/dev/null | grep -v "Scanning" | grep -v "^$"
}

# Conectar a dispositivo Bluetooth
connect_bluetooth_device() {
    local mac="$1"

    if [ -z "$mac" ]; then
        error "Debes especificar una MAC"
        return 1
    fi

    if ! command -v bluetoothctl &>/dev/null; then
        error "bluetoothctl no está instalado"
        return 1
    fi

    info "Conectando a $mac..."

    # Conectar usando bluetoothctl
    echo -e "connect $mac\nquit" | bluetoothctl 2>/dev/null

    if [ $? -eq 0 ]; then
        success "Conectado a $mac"
        return 0
    else
        error "Error al conectar a $mac"
        return 1
    fi
}

# Iniciar servidor Bluetooth para Mesh
start_mesh_bluetooth_server() {
    info "Iniciando servidor Bluetooth para Mesh..."

    # Configurar rfcomm
    local channel="${MESH_BT_CHANNEL:-1}"
    local rfcomm_config="/etc/bluetooth/rfcomm.conf"

    # Crear configuración de rfcomm
    cat > "$rfcomm_config" <<EOF
rfcomm0 {
    bind yes;
    device $(get_local_mac);
    channel $channel;
    comment "COM-LINK Mesh Bluetooth";
}
EOF

    # Iniciar rfcomm
    rfcomm bind /dev/rfcomm0 2>/dev/null
    if [ $? -eq 0 ]; then
        info "Servidor Bluetooth Mesh iniciado en el canal $channel"
        info "Dispositivo: /dev/rfcomm0"
        info "MAC: $(get_local_mac)"
        info "Nombre: $MESH_BT_NAME"

        # Crear script para manejar conexiones entrantes
        cat > "$TEMP_DIR/bluetooth_server.sh" <<'EOS'
#!/bin/bash
while true; do
    if [ -e /dev/rfcomm0 ]; then
        while read -r line; do
            echo "Mensaje recibido via Bluetooth: $line"
            # Aquí podrías procesar el mensaje recibido
        done < /dev/rfcomm0
    fi
    sleep 1
done
EOS

        chmod +x "$TEMP_DIR/bluetooth_server.sh"
        "$TEMP_DIR/bluetooth_server.sh" > "$TEMP_DIR/bluetooth_server.log" 2>&1 &

        local pid=$!
        echo "$pid" > "$DATA_DIR/mesh_bluetooth_server.pid"
        success "Servidor Bluetooth Mesh iniciado (PID: $pid)"
        return 0
    else
        error "Error al iniciar servidor Bluetooth Mesh"
        return 1
    fi
}

# Detener servidor Bluetooth Mesh
stop_mesh_bluetooth_server() {
    if [ -f "$DATA_DIR/mesh_bluetooth_server.pid" ]; then
        local pid=$(cat "$DATA_DIR/mesh_bluetooth_server.pid")
        kill "$pid" 2>/dev/null
        rm -f "$DATA_DIR/mesh_bluetooth_server.pid" "$TEMP_DIR/bluetooth_server.sh" "$TEMP_DIR/bluetooth_server.log" "/etc/bluetooth/rfcomm.conf"
        info "Servidor Bluetooth Mesh detenido"
        return 0
    else
        info "No hay servidor Bluetooth Mesh en ejecución"
        return 1
    fi
}

# Menú de Mesh Bluetooth
mesh_bluetooth_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📡 MESH BLUETOOTH\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Obtener información de Bluetooth
    if command -v hcitool &>/dev/null; then
        local bt_info=$(hcitool dev 2>/dev/null | head -n 1)
        local bt_mac=$(hcitool dev 2>/dev/null | grep -oE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}')
        echo "📡 Bluetooth: $bt_info"
        echo "🆔 MAC: $bt_mac"
    else
        echo "📡 Bluetooth: No disponible (hcitool no instalado)"
    fi

    echo ""
    echo "1️⃣  Escanear dispositivos Bluetooth"
    echo "2️⃣  Enviar mensaje"
    echo "3️⃣  Conectar a dispositivo"
    echo "4️⃣  Iniciar servidor Bluetooth"
    echo "5️⃣  Detener servidor Bluetooth"
    echo "6️⃣  Configurar Mesh Bluetooth"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            info "Escaneando dispositivos Bluetooth..."
            scan_bluetooth_devices
            ;;
        2)
            read -p "📡 Destino (MAC o nombre): " destination
            if [ -z "$destination" ]; then
                error "Debes especificar un destino"
                return
            fi

            read -p "💬 Mensaje: " message
            if [ -z "$message" ]; then
                error "El mensaje no puede estar vacío"
                return
            fi

            # Preguntar si cifrar
            local encrypt="yes"
            if [ "$ENCRYPTION_ENABLED" = "true" ]; then
                read -p "🔒 ¿Cifrar mensaje? (s/n, default: s): " encrypt_choice
                if [ "${encrypt_choice:-s}" = "n" ]; then
                    encrypt="no"
                fi
            fi

            send_mesh_bluetooth "$destination" "$message" "$encrypt"
            ;;
        3)
            scan_bluetooth_devices
            read -p "📡 MAC del dispositivo: " mac
            connect_bluetooth_device "$mac"
            ;;
        4)
            start_mesh_bluetooth_server
            ;;
        5)
            stop_mesh_bluetooth_server
            ;;
        6)
            read -p "📡 Nombre del dispositivo (default: $MESH_BT_NAME): " name
            read -p "🔢 Canal (1-30, default: $MESH_BT_CHANNEL): " channel

            [ -n "$name" ] && MESH_BT_NAME="$name"
            [ -n "$channel" ] && MESH_BT_CHANNEL="$channel"

            save_config
            success "Configuración de Mesh Bluetooth actualizada"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    mesh_bluetooth_menu
}
