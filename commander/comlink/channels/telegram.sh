#!/bin/bash
# channels/telegram.sh - Envío de mensajes por Telegram para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar mensaje por Telegram
send_telegram() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Validar chat_id
    if ! validate_telegram_chat_id "$destination"; then
        error "Chat ID no válido: $destination"
        return 1
    fi

    # Verificar token
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        error "Token de Telegram no configurado"
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

    # Dividir mensaje si es largo (Telegram tiene límite de 4096 caracteres)
    local max_length=4000
    if [ ${#final_message} -gt $max_length ]; then
        local parts=()
        while [ ${#final_message} -gt $max_length ]; do
            parts+=("${final_message:0:$max_length}")
            final_message="${final_message:$max_length}"
        done
        parts+=("$final_message")
    else
        local parts=("$final_message")
    fi

    info "Enviando ${#parts[@]} parte(s) a $destination via Telegram..."

    local success=true
    for part in "${parts[@]}"; do
        # Escapar caracteres especiales para JSON
        local escaped_part=$(echo "$part" | jq -Rs .)

        local response=$(curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\": $destination, \"text\": $escaped_part, \"parse_mode\": \"HTML\"}" 2>&1)

        if echo "$response" | jq -e '.ok == true' >/dev/null 2>&1; then
            debug "Parte enviada a Telegram"
        else
            error "Error enviando a Telegram: $(echo "$response" | jq -r '.description // "Desconocido"')"
            success=false
            break
        fi

        sleep 1  # Evitar límites de velocidad
    done

    if [ "$success" = true ]; then
        success "Mensaje enviado a Telegram (Chat ID: $destination)"
        return 0
    else
        error "Error enviando mensaje a Telegram"
        return 1
    fi
}

# Validar chat ID de Telegram
validate_telegram_chat_id() {
    local chat_id="$1"
    # Puede ser un número (negativo para grupos) o un string (@username)
    if [[ "$chat_id" =~ ^-?[0-9]+$ ]] || [[ "$chat_id" =~ ^@[a-zA-Z0-9_]+$ ]]; then
        return 0
    else
        return 1
    fi
}

# Configurar webhook de Telegram
setup_telegram_webhook() {
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_WEBHOOK_URL" ]; then
        error "Token de Telegram o URL de webhook no configurados"
        return 1
    fi

    info "Configurando webhook de Telegram..."

    local response=$(curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
        -H "Content-Type: application/json" \
        -d "{\"url\": \"$TELEGRAM_WEBHOOK_URL\"}" 2>&1)

    if echo "$response" | jq -e '.ok == true' >/dev/null 2>&1; then
        success "Webhook configurado: $TELEGRAM_WEBHOOK_URL"
        return 0
    else
        error "Error al configurar webhook: $(echo "$response" | jq -r '.description // "Desconocido"')"
        return 1
    fi
}

# Eliminar webhook de Telegram
remove_telegram_webhook() {
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        error "Token de Telegram no configurado"
        return 1
    fi

    info "Eliminando webhook de Telegram..."

    local response=$(curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook" 2>&1)

    if echo "$response" | jq -e '.ok == true' >/dev/null 2>&1; then
        success "Webhook eliminado"
        return 0
    else
        error "Error al eliminar webhook: $(echo "$response" | jq -r '.description // "Desconocido"')"
        return 1
    fi
}

# Menú de Telegram
telegram_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🤖 ENVÍO POR TELEGRAM\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos con Telegram configurado
    echo "📋 Contactos con Telegram:"
    jq -r --arg filter "telegram_chat_id" '.contacts | to_entries[] | select(.value.telegram_chat_id != null and .value.telegram_chat_id != "") | "  \(.key): \(.value.name) - Chat ID: \(.value.telegram_chat_id)"' "$CONTACTS_FILE"

    echo ""
    echo "1️⃣  Enviar mensaje"
    echo "2️⃣  Configurar webhook"
    echo "3️⃣  Eliminar webhook"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "💬 Mensaje: " message
            if [ -z "$message" ]; then
                error "El mensaje no puede estar vacío"
                return
            fi

            read -p "🆔 Chat ID (dejar vacío para usar el default): " chat_id
            chat_id="${chat_id:-$TELEGRAM_DEFAULT_CHAT_ID}"

            if [ -z "$chat_id" ]; then
                error "Chat ID no configurado"
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

            send_telegram "$chat_id" "$message" "$encrypt"
            ;;
        2)
            read -p "🌐 URL del webhook: " webhook_url
            if [ -n "$webhook_url" ]; then
                TELEGRAM_WEBHOOK_URL="$webhook_url"
                save_config
            fi
            setup_telegram_webhook
            ;;
        3)
            remove_telegram_webhook
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    telegram_menu
}
