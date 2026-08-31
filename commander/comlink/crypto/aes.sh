#!/bin/bash
# crypto/aes.sh - Cifrado AES-256-GCM para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Cifrar mensaje con AES-256-GCM
aes_encrypt() {
    local message="$1"
    local key="$2"

    if [ -z "$message" ] || [ -z "$key" ]; then
        error "Mensaje y clave no pueden estar vacíos"
        return 1
    fi

    # Generar IV aleatorio (12 bytes para GCM)
    local iv=$(openssl rand -hex 12)

    # Cifrar con AES-256-GCM
    local encrypted=$(echo -n "$message" | openssl enc -aes-256-gcm -K "$key" -iv "$iv" -binary 2>/dev/null | base64 -w 0)

    if [ -z "$encrypted" ]; then
        error "Error cifrando mensaje con AES-256-GCM"
        return 1
    fi

    # Formato: IV:mensaje_cifrado
    echo "${iv}:${encrypted}"
    return 0
}

# Descifrar mensaje con AES-256-GCM
aes_decrypt() {
    local encrypted="$1"
    local key="$2"

    if [ -z "$encrypted" ] || [ -z "$key" ]; then
        error "Mensaje cifrado y clave no pueden estar vacíos"
        return 1
    fi

    # Extraer IV y mensaje cifrado
    local iv="${encrypted%%:*}"
    local ciphertext="${encrypted#*:}"

    # Decodificar base64
    ciphertext=$(echo "$ciphertext" | base64 -d 2>/dev/null)

    if [ -z "$ciphertext" ]; then
        error "Error decodificando base64"
        return 1
    fi

    # Descifrar
    local decrypted=$(echo -n "$ciphertext" | openssl enc -aes-256-gcm -d -K "$key" -iv "$iv" -binary 2>/dev/null)

    if [ -z "$decrypted" ]; then
        error "Error descifrando mensaje con AES-256-GCM"
        return 1
    fi

    echo "$decrypted"
    return 0
}

# Generar clave AES-256 (32 bytes)
generate_aes_key() {
    openssl rand -hex 32
}
