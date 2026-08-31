#!/bin/bash
# crypto/aes.sh - Cifrado autenticado AES-256-CBC + HMAC-SHA256
#
# openssl enc no admite AES-GCM de forma fiable en las versiones actuales.
# El formato v1 usa encrypt-then-MAC con IV aleatorio y claves derivadas.

# ============================================================
# FUNCIONES
# ============================================================
# Derivar una clave de autenticación independiente de la clave AES.
derive_mac_key() {
    local key="$1"
    printf '%s' "COM-LINK-MAC-v1" | \
        openssl dgst -sha256 -mac HMAC -macopt "hexkey:$key" -binary 2>/dev/null | \
        od -An -tx1 -v | tr -d ' \n'
}

# Calcular HMAC-SHA256 en hexadecimal.
message_mac() {
    local value="$1"
    local key="$2"
    printf '%s' "$value" | \
        openssl dgst -sha256 -mac HMAC -macopt "hexkey:$key" -binary 2>/dev/null | \
        od -An -tx1 -v | tr -d ' \n'
}

# Cifrar mensaje con AES-256-CBC + HMAC-SHA256.
aes_encrypt() {
    local message="$1"
    local key="$2"

    if [ -z "$message" ] || [ -z "$key" ]; then
        error "Mensaje y clave no pueden estar vacíos"
        return 1
    fi

    if ! [[ "$key" =~ ^[0-9A-Fa-f]{64}$ ]]; then
        error "La clave AES debe contener 32 bytes en hexadecimal"
        return 1
    fi

    # CBC usa un IV de 16 bytes.
    local iv
    iv=$(openssl rand -hex 16) || return 1

    local encrypted
    encrypted=$(printf '%s' "$message" | \
        openssl enc -aes-256-cbc -K "$key" -iv "$iv" -nosalt -a -A 2>/dev/null) || {
        error "Error cifrando mensaje con AES-256-CBC"
        return 1
    }

    if [ -z "$encrypted" ]; then
        error "El cifrado devolvió un mensaje vacío"
        return 1
    fi

    local mac_key
    mac_key=$(derive_mac_key "$key")
    local mac
    mac=$(message_mac "${iv}:${encrypted}" "$mac_key")
    if [ -z "$mac" ]; then
        error "Error calculando la autenticación del mensaje"
        return 1
    fi

    # Formato v1: versión:IV:cifrado_base64:HMAC.
    printf '%s\n' "v1:${iv}:${encrypted}:${mac}"
    return 0
}

# Descifrar mensaje con AES-256-CBC + HMAC-SHA256.
aes_decrypt() {
    local encrypted="$1"
    local key="$2"

    if [ -z "$encrypted" ] || [ -z "$key" ]; then
        error "Mensaje cifrado y clave no pueden estar vacíos"
        return 1
    fi

    if ! [[ "$key" =~ ^[0-9A-Fa-f]{64}$ ]]; then
        error "La clave AES debe contener 32 bytes en hexadecimal"
        return 1
    fi

    local version iv ciphertext mac
    IFS=':' read -r version iv ciphertext mac <<< "$encrypted"
    if [ "$version" != "v1" ] || \
       ! [[ "$iv" =~ ^[0-9A-Fa-f]{32}$ ]] || \
       ! [[ "$mac" =~ ^[0-9A-Fa-f]{64}$ ]] || [ -z "$ciphertext" ]; then
        error "Formato de mensaje cifrado no compatible"
        return 1
    fi

    local mac_key expected_mac
    mac_key=$(derive_mac_key "$key")
    expected_mac=$(message_mac "${iv}:${ciphertext}" "$mac_key")
    if [ -z "$expected_mac" ] || [ "$expected_mac" != "$mac" ]; then
        error "La autenticación del mensaje cifrado falló"
        return 1
    fi

    printf '%s' "$ciphertext" | \
        openssl enc -d -aes-256-cbc -K "$key" -iv "$iv" -nosalt -a -A 2>/dev/null || {
        error "Error descifrando mensaje con AES-256-CBC"
        return 1
    }
    printf '\n'
    return 0
}

# Generar clave AES-256 (32 bytes)
generate_aes_key() {
    openssl rand -hex 32
}
