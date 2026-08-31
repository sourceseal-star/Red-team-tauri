#!/bin/bash
# crypto/rsa.sh - Cifrado RSA-4096 para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Generar par de claves RSA
generate_rsa_keypair() {
    local contact_id="$1"
    local key_dir="$KEYS_DIR"
    local private_key_file="$key_dir/${contact_id}_private.pem"
    local public_key_file="$key_dir/${contact_id}_public.pem"

    mkdir -p "$key_dir"

    # Generar clave privada
    openssl genpkey -algorithm RSA -out "$private_key_file" -pkeyopt rsa_keygen_bits:$KEY_LENGTH 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error generando clave privada RSA"
        return 1
    fi

    # Extraer clave pública
    openssl rsa -pubout -in "$private_key_file" -out "$public_key_file" 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error extrayendo clave pública RSA"
        return 1
    fi

    chmod 600 "$private_key_file"
    chmod 644 "$public_key_file"

    success "Par de claves RSA generado para $contact_id"
    return 0
}

# Cifrar con clave pública RSA
rsa_encrypt() {
    local message="$1"
    local public_key_file="$2"

    if [ -z "$message" ] || [ -z "$public_key_file" ]; then
        error "Mensaje y archivo de clave pública no pueden estar vacíos"
        return 1
    fi

    if [ ! -f "$public_key_file" ]; then
        error "Archivo de clave pública no encontrado: $public_key_file"
        return 1
    fi

    # Cifrar con RSA (máximo 4096 bits pueden cifrar 512 bytes)
    # Para mensajes largos, dividir en bloques
    local max_block_size=$(( (KEY_LENGTH / 8) - 11 ))  # PKCS#1 v1.5 padding
    local encrypted_blocks=()

    while [ ${#message} -gt $max_block_size ]; do
        local block="${message:0:$max_block_size}"
        message="${message:$max_block_size}"
        local encrypted_block=$(echo -n "$block" | openssl pkeyutl -encrypt -pubin -inkey "$public_key_file" -pkeyopt rsa_padding_mode:pkcs1 2>/dev/null | base64 -w 0)
        encrypted_blocks+=("$encrypted_block")
    done

    # Cifrar el último bloque
    local encrypted_block=$(echo -n "$message" | openssl pkeyutl -encrypt -pubin -inkey "$public_key_file" -pkeyopt rsa_padding_mode:pkcs1 2>/dev/null | base64 -w 0)
    encrypted_blocks+=("$encrypted_block")

    # Unir bloques con |
    echo "${encrypted_blocks[*]}" | tr ' ' '|'
    return 0
}

# Descifrar con clave privada RSA
rsa_decrypt() {
    local encrypted="$1"
    local private_key_file="$2"

    if [ -z "$encrypted" ] || [ -z "$private_key_file" ]; then
        error "Mensaje cifrado y archivo de clave privada no pueden estar vacíos"
        return 1
    fi

    if [ ! -f "$private_key_file" ]; then
        error "Archivo de clave privada no encontrado: $private_key_file"
        return 1
    fi

    # Dividir en bloques
    IFS='|' read -ra blocks <<< "$encrypted"
    local decrypted_blocks=()

    for block in "${blocks[@]}"; do
        local decrypted_block=$(echo "$block" | base64 -d 2>/dev/null | openssl pkeyutl -decrypt -inkey "$private_key_file" -pkeyopt rsa_padding_mode:pkcs1 2>/dev/null)
        decrypted_blocks+=("$decrypted_block")
    done

    # Unir bloques
    echo "${decrypted_blocks[*]}" | tr ' ' '\n' | tr -d '\n'
    return 0
}

# Firmar mensaje con clave privada RSA
rsa_sign() {
    local message="$1"
    local private_key_file="$2"
    local signature_file="${3:-$TEMP_DIR/signature.bin}"

    if [ -z "$message" ] || [ -z "$private_key_file" ]; then
        error "Mensaje y archivo de clave privada no pueden estar vacíos"
        return 1
    fi

    if [ ! -f "$private_key_file" ]; then
        error "Archivo de clave privada no encontrado: $private_key_file"
        return 1
    fi

    # Crear archivo temporal con el mensaje
    local message_file="$TEMP_DIR/message_$(date +%s).txt"
    echo -n "$message" > "$message_file"

    # Firmar
    openssl dgst -sha512 -sign "$private_key_file" -out "$signature_file" "$message_file" 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error firmando mensaje"
        rm -f "$message_file"
        return 1
    fi

    # Codificar firma en base64
    base64 -w 0 "$signature_file" | tr -d '\n'
    rm -f "$message_file" "$signature_file"
    return 0
}

# Verificar firma con clave pública RSA
rsa_verify() {
    local message="$1"
    local signature="$2"
    local public_key_file="$3"

    if [ -z "$message" ] || [ -z "$signature" ] || [ -z "$public_key_file" ]; then
        error "Mensaje, firma y archivo de clave pública no pueden estar vacíos"
        return 1
    fi

    if [ ! -f "$public_key_file" ]; then
        error "Archivo de clave pública no encontrado: $public_key_file"
        return 1
    fi

    # Crear archivos temporales
    local message_file="$TEMP_DIR/message_$(date +%s).txt"
    local signature_file="$TEMP_DIR/signature_$(date +%s).bin"

    echo -n "$message" > "$message_file"
    echo "$signature" | base64 -d > "$signature_file" 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error decodificando firma"
        rm -f "$message_file" "$signature_file"
        return 1
    fi

    # Verificar firma
    openssl dgst -sha512 -verify "$public_key_file" -signature "$signature_file" "$message_file" 2>/dev/null

    local result=$?
    rm -f "$message_file" "$signature_file"

    if [ $result -eq 0 ]; then
        return 0
    else
        return 1
    fi
}
