#!/bin/bash
# crypto/key_manager.sh - Gestión de Claves para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Generar claves para un contacto
generate_keys() {
    local contact_id="$1"

    if [ -z "$contact_id" ]; then
        error "Debes especificar un ID de contacto"
        return 1
    fi

    # Verificar si el contacto existe
    if ! jq -e --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "Contacto $contact_id no existe"
        return 1
    fi

    info "Generando claves para $contact_id..."

    # Generar clave AES
    local aes_key=$(generate_aes_key)
    save_key "$contact_id" "$aes_key" "aes"

    # Generar par de claves RSA
    generate_rsa_keypair "$contact_id"

    # Guardar clave pública en el contacto
    local public_key_file="$KEYS_DIR/${contact_id}_public.pem"
    local public_key=$(cat "$public_key_file" 2>/dev/null)

    if [ -n "$public_key" ]; then
        jq --arg id "$contact_id" \
           --arg public_key "$public_key" \
           '.contacts[$id].public_key = $public_key' \
           "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"
    fi

    success "Claves generadas para $contact_id"
    return 0
}

# Cargar clave para un contacto
load_key() {
    local contact_id="$1"
    local key_type="${2:-aes}"

    local key_file="$KEYS_DIR/${contact_id}_${key_type}.pem"
    if [ "$key_type" = "aes" ]; then
        key_file="$KEYS_DIR/${contact_id}_key.txt"
    fi

    if [ -f "$key_file" ]; then
        cat "$key_file"
        return 0
    else
        error "Clave $key_type no encontrada para $contact_id"
        return 1
    fi
}

# Guardar clave para un contacto
save_key() {
    local contact_id="$1"
    local key="$2"
    local key_type="${3:-aes}"

    local key_file="$KEYS_DIR/${contact_id}_${key_type}.pem"
    if [ "$key_type" = "aes" ]; then
        key_file="$KEYS_DIR/${contact_id}_key.txt"
    fi

    echo "$key" > "$key_file"
    chmod 600 "$key_file"

    success "Clave $key_type guardada para $contact_id"
    return 0
}

# Intercambiar claves con un contacto
exchange_keys() {
    local contact_id="$1"
    local method="${2:-sms}"

    if [ -z "$contact_id" ]; then
        error "Debes especificar un ID de contacto"
        return 1
    fi

    # Verificar si el contacto existe
    if ! jq -e --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "Contacto $contact_id no existe"
        return 1
    fi

    # Generar claves si no existen
    if [ ! -f "$KEYS_DIR/${contact_id}_key.txt" ]; then
        generate_keys "$contact_id"
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi

    # Obtener clave pública
    local public_key_file="$KEYS_DIR/${contact_id}_public.pem"
    local public_key=$(cat "$public_key_file" 2>/dev/null)

    if [ -z "$public_key" ]; then
        error "Clave pública no encontrada para $contact_id"
        return 1
    fi

    # Obtener información del contacto
    local contact_name=$(jq -r --arg id "$contact_id" '.contacts[$id].name' "$CONTACTS_FILE")
    local contact_phone=$(jq -r --arg id "$contact_id" '.contacts[$id].phone // empty' "$CONTACTS_FILE")
    local contact_telegram=$(jq -r --arg id "$contact_id" '.contacts[$id].telegram_chat_id // empty' "$CONTACTS_FILE")

    # Enviar clave pública según el método
    case $method in
        "sms")
            if [ -z "$contact_phone" ]; then
                error "El contacto $contact_id no tiene número de teléfono configurado"
                return 1
            fi

            # Dividir clave en partes (SMS tiene límite de 160 caracteres)
            local max_length=150  # Dejar espacio para el mensaje
            local message="🔑 Clave pública COM-LINK para $DEVICE_NAME ($DEVICE_ID):
$public_key"

            if [ ${#message} -gt $max_length ]; then
                # Enviar en múltiples SMS
                local parts=()
                while [ ${#message} -gt $max_length ]; do
                    parts+=("${message:0:$max_length}")
                    message="${message:$max_length}"
                done
                parts+=("$message")

                for part in "${parts[@]}"; do
                    send_sms "$contact_phone" "$part" "no_encrypt"
                    if [ $? -ne 0 ]; then
                        error "Error enviando parte de la clave"
                        return 1
                    fi
                done
            else
                send_sms "$contact_phone" "$message" "no_encrypt"
                if [ $? -ne 0 ]; then
                    error "Error enviando clave pública"
                    return 1
                fi
            fi

            success "Clave pública enviada via SMS a $contact_name"
            ;;
        "telegram")
            if [ -z "$contact_telegram" ]; then
                error "El contacto $contact_id no tiene chat ID de Telegram configurado"
                return 1
            fi

            local message="🔑 Clave pública COM-LINK para $DEVICE_NAME ($DEVICE_ID):

\`\`\`
$public_key
\`\`\`"

            send_telegram "$contact_telegram" "$message" "no_encrypt"
            if [ $? -ne 0 ]; then
                error "Error enviando clave pública"
                return 1
            fi

            success "Clave pública enviada via Telegram a $contact_name"
            ;;
        *)
            error "Método no válido: $method"
            return 1
            ;;
    esac

    return 0
}

# Recibir clave de un contacto
receive_key() {
    local contact_id="$1"
    local public_key="$2"
    local method="${3:-manual}"

    if [ -z "$contact_id" ] || [ -z "$public_key" ]; then
        error "Debes especificar un ID de contacto y una clave pública"
        return 1
    fi

    # Guardar clave pública
    local public_key_file="$KEYS_DIR/${contact_id}_public.pem"
    echo "$public_key" > "$public_key_file"
    chmod 644 "$public_key_file"

    # Guardar en el contacto
    jq --arg id "$contact_id" \
       --arg public_key "$public_key" \
       '.contacts[$id].public_key = $public_key' \
       "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"

    success "Clave pública recibida de $contact_id"

    # Generar clave AES compartida (si no existe)
    if [ ! -f "$KEYS_DIR/${contact_id}_key.txt" ]; then
        local aes_key=$(generate_aes_key)
        save_key "$contact_id" "$aes_key" "aes"

        # Enviar clave AES cifrada con RSA
        exchange_aes_key "$contact_id"
    fi

    return 0
}

# Intercambiar clave AES cifrada con RSA
exchange_aes_key() {
    local contact_id="$1"

    if [ -z "$contact_id" ]; then
        error "Debes especificar un ID de contacto"
        return 1
    fi

    # Obtener clave AES
    local aes_key=$(load_key "$contact_id" "aes")
    if [ $? -ne 0 ]; then
        error "No se pudo cargar la clave AES para $contact_id"
        return 1
    fi

    # Obtener clave pública del contacto
    local public_key_file="$KEYS_DIR/${contact_id}_public.pem"
    if [ ! -f "$public_key_file" ]; then
        error "Clave pública no encontrada para $contact_id"
        return 1
    fi

    # Cifrar clave AES con RSA
    local encrypted_aes=$(rsa_encrypt "$aes_key" "$public_key_file")
    if [ $? -ne 0 ]; then
        error "Error cifrando clave AES"
        return 1
    fi

    # Obtener información del contacto
    local contact_phone=$(jq -r --arg id "$contact_id" '.contacts[$id].phone // empty' "$CONTACTS_FILE")
    local contact_telegram=$(jq -r --arg id "$contact_id" '.contacts[$id].telegram_chat_id // empty' "$CONTACTS_FILE")

    # Enviar clave AES cifrada
    if [ -n "$contact_phone" ]; then
        local message="🔐 Clave AES COM-LINK cifrada para $DEVICE_NAME:

$encrypted_aes"
        send_sms "$contact_phone" "$message" "no_encrypt"
        if [ $? -ne 0 ]; then
            warning "No se pudo enviar clave AES via SMS"
        else
            success "Clave AES enviada via SMS a $contact_id"
            return 0
        fi
    fi

    if [ -n "$contact_telegram" ]; then
        local message="🔐 Clave AES COM-LINK cifrada para $DEVICE_NAME:

\`\`\`
$encrypted_aes
\`\`\`"
        send_telegram "$contact_telegram" "$message" "no_encrypt"
        if [ $? -ne 0 ]; then
            error "Error enviando clave AES"
            return 1
        else
            success "Clave AES enviada via Telegram a $contact_id"
            return 0
        fi
    fi

    error "No hay método de envío configurado para $contact_id"
    return 1
}

# Cifrar mensaje para un contacto
encrypt_message() {
    local message="$1"
    local contact_id="$2"

    if [ -z "$message" ] || [ -z "$contact_id" ]; then
        error "Mensaje y contacto no pueden estar vacíos"
        return 1
    fi

    # Verificar si hay clave AES para el contacto
    local aes_key=$(load_key "$contact_id" "aes")
    if [ $? -ne 0 ]; then
        # Si no hay clave AES, usar RSA
        local public_key_file="$KEYS_DIR/${contact_id}_public.pem"
        if [ -f "$public_key_file" ]; then
            rsa_encrypt "$message" "$public_key_file"
            return $?
        else
            error "No hay clave para cifrar el mensaje para $contact_id"
            return 1
        fi
    fi

    # Cifrar con AES
    aes_encrypt "$message" "$aes_key"
    return $?
}

# Descifrar mensaje de un contacto
decrypt_message() {
    local encrypted="$1"
    local contact_id="$2"

    if [ -z "$encrypted" ] || [ -z "$contact_id" ]; then
        error "Mensaje cifrado y contacto no pueden estar vacíos"
        return 1
    fi

    # Intentar descifrar con AES primero
    local aes_key=$(load_key "$contact_id" "aes")
    if [ $? -eq 0 ]; then
        aes_decrypt "$encrypted" "$aes_key"
        if [ $? -eq 0 ]; then
            return 0
        fi
    fi

    # Si falla AES, intentar con RSA
    local private_key_file="$KEYS_DIR/${contact_id}_private.pem"
    if [ -f "$private_key_file" ]; then
        rsa_decrypt "$encrypted" "$private_key_file"
        return $?
    fi

    error "No se pudo descifrar el mensaje de $contact_id"
    return 1
}
