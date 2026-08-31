#!/bin/bash
# utils/compress.sh - Compresión de Mensajes para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Comprimir mensaje
compress_message() {
    local message="$1"

    if [ -z "$message" ]; then
        error "El mensaje no puede estar vacío"
        return 1
    fi

    # Crear archivo temporal
    local temp_file="$TEMP_DIR/message_$(date +%s).txt"
    echo "$message" > "$temp_file"

    # Comprimir con gzip
    gzip -c "$temp_file" > "$temp_file.gz" 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error comprimiendo mensaje"
        rm -f "$temp_file" "$temp_file.gz"
        return 1
    fi

    # Codificar en base64
    local compressed=$(base64 -w 0 "$temp_file.gz" 2>/dev/null)

    # Limpiar
    rm -f "$temp_file" "$temp_file.gz"

    if [ -z "$compressed" ]; then
        error "Error codificando mensaje comprimido"
        return 1
    fi

    echo "$compressed"
    return 0
}

# Descomprimir mensaje
decompress_message() {
    local compressed="$1"

    if [ -z "$compressed" ]; then
        error "El mensaje comprimido no puede estar vacío"
        return 1
    fi

    # Decodificar base64
    local temp_file="$TEMP_DIR/message_$(date +%s).gz"
    echo "$compressed" | base64 -d > "$temp_file" 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error decodificando mensaje comprimido"
        rm -f "$temp_file"
        return 1
    fi

    # Descomprimir
    gzip -d "$temp_file" 2>/dev/null

    if [ $? -ne 0 ]; then
        error "Error descomprimiendo mensaje"
        rm -f "$temp_file" "$temp_file.gz"
        return 1
    fi

    # Leer mensaje
    local message=$(cat "${temp_file%.gz}" 2>/dev/null)

    # Limpiar
    rm -f "$temp_file" "${temp_file%.gz}"

    if [ -z "$message" ]; then
        error "Error leyendo mensaje descomprimido"
        return 1
    fi

    echo "$message"
    return 0
}

# Comprimir y cifrar mensaje
compress_and_encrypt() {
    local message="$1"
    local contact_id="$2"

    if [ -z "$message" ] || [ -z "$contact_id" ]; then
        error "Mensaje y contacto no pueden estar vacíos"
        return 1
    fi

    # Comprimir
    local compressed=$(compress_message "$message")
    if [ $? -ne 0 ]; then
        return 1
    fi

    # Cifrar
    encrypt_message "$compressed" "$contact_id"
    return $?
}

# Descifrar y descomprimir mensaje
decrypt_and_decompress() {
    local encrypted="$1"
    local contact_id="$2"

    if [ -z "$encrypted" ] || [ -z "$contact_id" ]; then
        error "Mensaje cifrado y contacto no pueden estar vacíos"
        return 1
    fi

    # Descifrar
    local compressed=$(decrypt_message "$encrypted" "$contact_id")
    if [ $? -ne 0 ]; then
        return 1
    fi

    # Descomprimir
    decompress_message "$compressed"
    return $?
}

# Menú de compresión
compress_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🗜️  COMPRESIÓN DE MENSAJES\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Comprimir mensaje"
    echo "2️⃣  Descomprimir mensaje"
    echo "3️⃣  Comprimir y cifrar"
    echo "4️⃣  Descifrar y descomprimir"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "💬 Mensaje: " message
            if [ -z "$message" ]; then
                error "El mensaje no puede estar vacío"
                return
            fi

            local compressed=$(compress_message "$message")
            if [ $? -eq 0 ]; then
                echo -e "\n\033[1;32mMensaje comprimido:\033[0m"
                echo "$compressed"
                echo ""
                read -p "¿Copiar al portapapeles? (s/n, default: n): " choice
                if [ "${choice:-n}" = "s" ]; then
                    echo "$compressed" | termux-clipboard-set
                    success "Mensaje comprimido copiado al portapapeles"
                fi
            fi
            ;;
        2)
            read -p "🗜️  Mensaje comprimido: " compressed
            if [ -z "$compressed" ]; then
                error "El mensaje comprimido no puede estar vacío"
                return
            fi

            local decompressed=$(decompress_message "$compressed")
            if [ $? -eq 0 ]; then
                echo -e "\n\033[1;32mMensaje descomprimido:\033[0m"
                echo "$decompressed"
                echo ""
            fi
            ;;
        3)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos configurados:"
            jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            read -p "💬 Mensaje: " message
            if [ -z "$message" ]; then
                error "El mensaje no puede estar vacío"
                return
            fi

            local result=$(compress_and_encrypt "$message" "$contact_id")
            if [ $? -eq 0 ]; then
                echo -e "\n\033[1;32mMensaje comprimido y cifrado:\033[0m"
                echo "$result"
                echo ""
                read -p "¿Copiar al portapapeles? (s/n, default: n): " choice
                if [ "${choice:-n}" = "s" ]; then
                    echo "$result" | termux-clipboard-set
                    success "Mensaje copiado al portapapeles"
                fi
            fi
            ;;
        4)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos configurados:"
            jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            read -p "🔐 Mensaje cifrado y comprimido: " encrypted
            if [ -z "$encrypted" ]; then
                error "El mensaje no puede estar vacío"
                return
            fi

            local result=$(decrypt_and_decompress "$encrypted" "$contact_id")
            if [ $? -eq 0 ]; then
                echo -e "\n\033[1;32mMensaje descifrado y descomprimido:\033[0m"
                echo "$result"
                echo ""
            fi
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    compress_menu
}

# Punto de entrada: no ejecutar el menú cuando el módulo se carga con source.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [ $# -eq 0 ]; then
        compress_menu
    else
        case "$1" in
            "compress")
                shift
                compress_message "$@"
                ;;
            "decompress")
                shift
                decompress_message "$@"
                ;;
            "compress_encrypt")
                shift
                compress_and_encrypt "$@"
                ;;
            "decrypt_decompress")
                shift
                decrypt_and_decompress "$@"
                ;;
            *) error "Comando no válido" ;;
        esac
    fi
fi
