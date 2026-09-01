#!/bin/bash
# channels/sms.sh - Envío de SMS para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar SMS
send_sms() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Validar número de teléfono
    if ! validate_phone "$destination"; then
        error "Número de teléfono no válido: $destination"
        return 1
    fi

    # Cifrar mensaje si es necesario
    local final_message="$message"
    if [ "$ENCRYPTION_ENABLED" = "true" ] && [ -z "$encrypted" ]; then
        final_message=$(encrypt_message "$message" "$destination")
        if [ $? -ne 0 ]; then
            error "Error cifrando mensaje para $destination"
            return 1
        fi
    elif [ -n "$encrypted" ] && [ "$encrypted" != "no_encrypt" ]; then
        final_message="$encrypted"
    fi

    # Dividir mensaje si es largo (SMS tiene límite de 160 caracteres)
    local max_length=160
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

    info "Enviando ${#parts[@]} parte(s) a $destination via SMS..."

    local send_succeeded=true
    for part in "${parts[@]}"; do
        # Enviar via Termux API
        # termux-sms-send recibe el texto como argumento. Enviarlo por stdin
        # deja el comportamiento dependiente de la versión de Termux:API.
        termux-sms-send -n "$destination" "$part" 2>/dev/null

        if [ $? -ne 0 ]; then
            error "Error enviando parte del mensaje a $destination"
            send_succeeded=false
            break
        fi

        debug "Parte enviada: ${part:0:50}..."
        sleep 1  # Esperar para evitar límites de velocidad
    done

    if [ "$send_succeeded" = true ]; then
        success "SMS enviado a $destination (${#parts[@]} parte(s))"
        return 0
    else
        error "Error enviando SMS a $destination"
        return 1
    fi
}

# Validar número de teléfono
validate_phone() {
    local phone="$1"
    # Formato básico: + seguido de 8-15 dígitos
    if [[ "$phone" =~ ^\+[0-9]{8,15}$ ]]; then
        return 0
    else
        return 1
    fi
}

# Menú de SMS
sms_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📱 ENVÍO DE SMS\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos con teléfono configurado
    echo "📋 Contactos con teléfono:"
    jq -r --arg filter "phone" '.contacts | to_entries[] | select(.value.phone != null and .value.phone != "") | "  \(.key): \(.value.name) - \(.value.phone)"' "$CONTACTS_FILE"

    echo ""
    read -p "📱 Número de teléfono (+57...): " phone

    if ! validate_phone "$phone"; then
        error "Número de teléfono no válido"
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

    # Preguntar si añadir a cola
    read -p "📤 ¿Enviar ahora o añadir a cola? (1=Enviar, 2=Cola, default: 1): " send_choice

    if [ "${send_choice:-1}" = "1" ]; then
        send_sms "$phone" "$message" "$encrypt"
    else
        # Obtener ID del contacto
        local contact_id=$(jq -r --arg phone "$phone" '.contacts | to_entries[] | select(.value.phone == $phone) | .key' "$CONTACTS_FILE" | head -n 1)

        if [ -z "$contact_id" ]; then
            # Crear contacto temporal
            contact_id="temp_$(date +%s)"
            jq --arg id "$contact_id" \
               --arg phone "$phone" \
               '.contacts += {($id): {"name": "Temporal", "phone": $phone}}' \
               "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"
        fi

        add_to_queue "$contact_id" "sms" "$message" "" 0
        success "Mensaje añadido a la cola"
    fi

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
}
