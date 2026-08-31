#!/bin/bash
# core/fallback.sh - Sistema de Fallback Automático para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Verificar disponibilidad de un canal
check_channel_available() {
    local channel="$1"

    case $channel in
        "sms")
            # Verificar si hay red celular
            check_cellular
            ;;
        "telegram")
            # Verificar conexión a internet
            check_internet
            ;;
        "voip")
            # Verificar conexión a internet o red local
            check_internet || check_lan
            ;;
        "mesh_wifi")
            # Verificar si hay WiFi disponible
            check_wifi
            ;;
        "mesh_bluetooth")
            # Verificar si Bluetooth está disponible
            check_bluetooth
            ;;
        "radio")
            # El driver AX.25/TNC aún no está implementado. No incluir este
            # canal en fallback aunque el binario soundmodem exista.
            return 1
            ;;
        "satellite")
            # Los comandos AT genéricos no constituyen un driver satelital.
            return 1
            ;;
        *)
            return 1
            ;;
    esac
}

# Obtener canales disponibles
get_available_channels() {
    local available_channels=()
    local channels=($FALLBACK_ORDER)

    for channel in "${channels[@]}"; do
        if check_channel_available "$channel"; then
            available_channels+=("$channel")
        fi
    done

    echo "${available_channels[@]}"
}

# Enviar mensaje con fallback automático
send_with_fallback() {
    local contact_id="$1"
    local message="$2"
    local original_channel="${3:-}"

    # Obtener información del contacto
    local contact_name=$(jq -r --arg id "$contact_id" '.contacts[$id].name // "Unknown"' "$CONTACTS_FILE")
    local contact_phone=$(jq -r --arg id "$contact_id" '.contacts[$id].phone // empty' "$CONTACTS_FILE")
    local contact_telegram=$(jq -r --arg id "$contact_id" '.contacts[$id].telegram_chat_id // empty' "$CONTACTS_FILE")
    local contact_sip=$(jq -r --arg id "$contact_id" '.contacts[$id].sip_address // empty' "$CONTACTS_FILE")

    # Obtener canales disponibles
    local available_channels=($(get_available_channels))

    if [ ${#available_channels[@]} -eq 0 ]; then
        error "No hay canales disponibles para enviar el mensaje"
        return 1
    fi

    # Si se especifica un canal, intentarlo primero
    if [ -n "$original_channel" ]; then
        if check_channel_available "$original_channel"; then
            available_channels=("$original_channel" "${available_channels[@]}")
            # Eliminar duplicados
            available_channels=($(printf "%s\n" "${available_channels[@]}" | awk '!x[$0]++'))
        fi
    fi

    info "Intentando enviar mensaje a $contact_name via ${available_channels[0]} (fallback: ${available_channels[*]})"

    # Intentar cada canal en orden
    for channel in "${available_channels[@]}"; do
        info "Probando canal: $channel"

        # Determinar el destino según el canal
        local destination=""
        case $channel in
            "sms")
                destination="$contact_phone"
                ;;
            "telegram")
                destination="$contact_telegram"
                ;;
            "voip")
                destination="$contact_sip"
                ;;
            *)
                destination="$contact_id"
                ;;
        esac

        if [ -z "$destination" ]; then
            debug "No hay destino configurado para $channel en el contacto $contact_id"
            continue
        fi

        # Cifrar mensaje si está habilitado
        local encrypted=""
        if [ "$ENCRYPTION_ENABLED" = "true" ]; then
            encrypted=$(encrypt_message "$message" "$contact_id")
            if [ $? -ne 0 ]; then
                warning "No se pudo cifrar el mensaje para $contact_id"
                encrypted="no_encrypt"
            fi
        fi

        # Intentar enviar
        local send_function="send_${channel}"
        if declare -f "$send_function" >/dev/null; then
            "$send_function" "$destination" "$message" "$encrypted"

            if [ $? -eq 0 ]; then
                success "Mensaje enviado a $contact_name via $channel"
                return 0
            else
                warning "Fallo al enviar via $channel, probando siguiente..."
            fi
        else
            warning "Función de envío no encontrada para $channel"
        fi
    done

    error "No se pudo enviar el mensaje a $contact_name en ningún canal disponible"
    return 1
}

# Verificar conexión a internet
check_internet() {
    if ping -c 1 -W 2 8.8.8.8 &>/dev/null || \
       ping -c 1 -W 2 1.1.1.1 &>/dev/null || \
       curl -s -o /dev/null --connect-timeout 2 https://google.com &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Verificar conexión a red celular
check_cellular() {
    local network_type=$(termux-telephony-device-info 2>/dev/null | jq -r '.network_type // "unknown"')
    if [ "$network_type" = "cellular" ] || [ "$network_type" = "mobile" ]; then
        return 0
    else
        return 1
    fi
}

# Verificar conexión WiFi
check_wifi() {
    local wifi_state=$(termux-wifi-connectioninfo 2>/dev/null | jq -r '.state // "unknown"')
    if [ "$wifi_state" = "CONNECTED" ]; then
        return 0
    else
        return 1
    fi
}

# Verificar conexión LAN
check_lan() {
    # Verificar si hay conexión a la red local
    if ping -c 1 -W 2 192.168.1.1 &>/dev/null || \
       ping -c 1 -W 2 10.0.0.1 &>/dev/null || \
       ping -c 1 -W 2 172.16.0.1 &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Verificar Bluetooth
check_bluetooth() {
    if command -v hcitool &>/dev/null && \
       hcitool dev 2>/dev/null | grep -q "hci"; then
        return 0
    else
        return 1
    fi
}
