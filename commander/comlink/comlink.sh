#!/usr/bin/env bash
# COM-LINK v3.0 - Sistema de Comunicación de Emergencia Ultra-Resiliente
# Uso: comlink [comando] [argumentos]

# ============================================================
# INICIALIZACIÓN
# ============================================================
# Directorios
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$INSTALL_DIR"
CORE_DIR="$SCRIPT_DIR/core"
CHANNELS_DIR="$SCRIPT_DIR/channels"
MESH_DIR="$SCRIPT_DIR/mesh"
UTILS_DIR="$SCRIPT_DIR/utils"
CRYPTO_DIR="$SCRIPT_DIR/crypto"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"
DATA_DIR="$SCRIPT_DIR/data"
CONFIG_FILE="$DATA_DIR/config.json"
CONTACTS_FILE="$DATA_DIR/contacts.json"
KEYS_DIR="$DATA_DIR/keys"
QUEUE_DB="$DATA_DIR/queue/queue.db"
LOG_DIR="$DATA_DIR/logs"
TEMP_DIR="/tmp/comlink"
COMLINK_MACHINE_OUTPUT=false

# status-json se consume desde el backend y no debe mezclarse con logs.
if [ "${1:-}" = "status-json" ] || [ "${1:-}" = "--status-json" ]; then
    COMLINK_MACHINE_OUTPUT=true
fi

# Cargar módulos
source "$CORE_DIR/config.sh"
source "$CORE_DIR/logger.sh"
source "$CORE_DIR/queue.sh"
source "$CORE_DIR/fallback.sh"
source "$CORE_DIR/network.sh"

# Cargar canales
source "$CHANNELS_DIR/sms.sh"
source "$CHANNELS_DIR/telegram.sh"
source "$CHANNELS_DIR/voip.sh"
source "$CHANNELS_DIR/mesh_wifi.sh"
source "$CHANNELS_DIR/mesh_bluetooth.sh"
source "$CHANNELS_DIR/radio.sh"
source "$CHANNELS_DIR/satellite.sh"

# Cargar mesh
source "$MESH_DIR/p2p_http.sh"
source "$MESH_DIR/p2p_ssh.sh"
source "$MESH_DIR/discovery.sh"

# Cargar utilidades
source "$UTILS_DIR/location.sh"
source "$UTILS_DIR/battery.sh"
source "$UTILS_DIR/device_info.sh"
source "$UTILS_DIR/compress.sh"

# Cargar crypto
source "$CRYPTO_DIR/aes.sh"
source "$CRYPTO_DIR/rsa.sh"
source "$CRYPTO_DIR/key_manager.sh"
source "$CORE_DIR/emergency.sh"

# ============================================================
# FUNCIONES GLOBALES
# ============================================================
# Menú principal
main_menu() {
    clear
    echo -e "\033[1;34m============================================\033[0m"
    echo -e "\033[1;34m  📡 COM-LINK v3.0\033[0m"
    echo -e "\033[1;34m  Sistema de Comunicación de Emergencia\033[0m"
    echo -e "\033[1;34m============================================\033[0m"
    echo ""

    # Mostrar estado del dispositivo
    get_device_summary
    echo ""

    # Mostrar estado de la red
    echo -e "\033[1;34m🌐 ESTADO DE LA RED:\033[0m"
    check_internet && echo -e "  ✅ Internet: \033[0;32mConectado\033[0m" || echo -e "  ❌ Internet: \033[0;31mDesconectado\033[0m"
    check_wifi && echo -e "  ✅ WiFi: \033[0;32mConectado\033[0m" || echo -e "  ❌ WiFi: \033[0;31mDesconectado\033[0m"
    check_cellular && echo -e "  ✅ Celular: \033[0;32mConectado\033[0m" || echo -e "  ❌ Celular: \033[0;31mDesconectado\033[0m"
    check_bluetooth && echo -e "  ✅ Bluetooth: \033[0;32mDisponible\033[0m" || echo -e "  ❌ Bluetooth: \033[0;31mNo disponible\033[0m"
    echo ""

    # Mostrar cola de mensajes
    local pending=$(count_messages "pending")
    local processing=$(count_messages "processing")
    local sent=$(count_messages "sent")
    local failed=$(count_messages "failed")

    echo -e "\033[1;34m📦 COLA DE MENSAJES:\033[0m"
    echo "  Pendientes: $pending"
    echo "  Procesando: $processing"
    echo "  Enviados: $sent"
    echo "  Fallidos: $failed"
    echo ""

    echo -e "\033[1;34m📋 OPCIONES PRINCIPALES:\033[0m"
    echo "1️⃣  Enviar mensaje"
    echo "2️⃣  Enviar ubicación"
    echo "3️⃣  Llamada VoIP"
    echo "4️⃣  Comunicación Mesh"
    echo "5️⃣  Radio Aficionados"
    echo "6️⃣  Satélite"
    echo ""
    echo "7️⃣  Configuración"
    echo "8️⃣  Gestión de contactos"
    echo "9️⃣  Gestión de claves"
    echo ""
    echo "🔟 Procesar cola de mensajes"
    echo "🔢 Ver estado del sistema"
    echo "🔣 Utilidades"
    echo ""
    echo "0️⃣  Salir"
    echo -e "\033[1;34m============================================\033[0m"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1) send_message_menu ;;
        2) location_menu ;;
        3) voip_menu ;;
        4) mesh_menu ;;
        5) radio_menu ;;
        6) satellite_menu ;;
        7) config_menu ;;
        8) contacts_menu ;;
        9) keys_menu ;;
        🔟) process_queue_menu ;;
        🔢) status_menu ;;
        🔣) utilities_menu ;;
        0) exit 0 ;;
        *) error "Opción no válida" ;;
    esac

    main_menu
}

# Menú de envío de mensajes
send_message_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ✉️  ENVIAR MENSAJE\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos
    echo "📋 Contactos configurados:"
    jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name) - Prioridad: \(.value.priority // "N/A")"' "$CONTACTS_FILE"

    echo ""
    read -p "👤 Contacto (ID o número/chat_id): " contact

    if [ -z "$contact" ]; then
        error "Debes especificar un contacto"
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

    # Preguntar si comprimir
    local compress="no"
    if [ ${#message} -gt 100 ]; then
        read -p "🗜️  ¿Comprimir mensaje? (s/n, default: n): " compress_choice
        if [ "${compress_choice:-n}" = "s" ]; then
            compress="yes"
        fi
    fi

    # Procesar mensaje
    local final_message="$message"
    local encrypted=""

    if [ "$compress" = "yes" ]; then
        if [ "$encrypt" = "yes" ]; then
            final_message=$(compress_and_encrypt "$message" "$contact")
            encrypted="compressed_encrypted"
        else
            final_message=$(compress_message "$message")
            encrypted="compressed"
        fi
    elif [ "$encrypt" = "yes" ]; then
        final_message=$(encrypt_message "$message" "$contact")
        encrypted="encrypted"
    fi

    if [ $? -ne 0 ]; then
        error "Error procesando mensaje"
        return
    fi

    # Añadir a cola o enviar directamente
    read -p "📤 ¿Enviar ahora o añadir a cola? (1=Enviar, 2=Cola, default: 1): " send_choice

    if [ "${send_choice:-1}" = "1" ]; then
        # Usar fallback automático
        send_with_fallback "$contact" "$final_message" ""
    else
        # Obtener ID del contacto
        local contact_id="$contact"
        if ! jq -e --arg id "$contact" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
            # Buscar contacto por teléfono o chat_id
            contact_id=$(jq -r --arg contact "$contact" '.contacts | to_entries[] | select(.value.phone == $contact or .value.telegram_chat_id == $contact) | .key' "$CONTACTS_FILE" | head -n 1)

            if [ -z "$contact_id" ]; then
                # Crear contacto temporal
                contact_id="temp_$(date +%s)"
                jq --arg id "$contact_id" \
                   --arg contact "$contact" \
                   '.contacts += {($id): {"name": "Temporal", "phone": $contact}}' \
                   "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"
            fi
        fi

        add_to_queue "$contact_id" "" "$message" "$encrypted" 0
        success "Mensaje añadido a la cola"
    fi

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
}

# Menú de Mesh
mesh_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🌐 COMUNICACIÓN MESH\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Mesh WiFi"
    echo "2️⃣  Mesh Bluetooth"
    echo "3️⃣  Detección de dispositivos"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1) mesh_wifi_menu ;;
        2) mesh_bluetooth_menu ;;
        3) discovery_menu ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    mesh_menu
}

# Menú de configuración
config_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Configuración general"
    echo "2️⃣  Configuración de red"
    echo "3️⃣  Configuración de Telegram"
    echo "4️⃣  Configuración de VoIP"
    echo "5️⃣  Configuración de Radio"
    echo "6️⃣  Configuración de Satélite"
    echo "7️⃣  Configuración de seguridad"
    echo "8️⃣  Ver configuración actual"
    echo "9️⃣  Guardar configuración"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1) config_general ;;
        2) config_network ;;
        3) config_telegram ;;
        4) config_voip ;;
        5) config_radio ;;
        6) config_satellite ;;
        7) config_security ;;
        8) show_config ;;
        9) save_config && success "Configuración guardada" ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    config_menu
}

# Configuración general
config_general() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN GENERAL\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Nombre del dispositivo: $DEVICE_NAME"
    echo "  ID del dispositivo: $DEVICE_ID"
    echo "  Versión: $COM_LINK_VERSION"

    echo ""
    read -p "📱 Nombre del dispositivo (dejar vacío para no cambiar): " name
    read -p "🆔 ID del dispositivo (dejar vacío para no cambiar): " id

    [ -n "$name" ] && DEVICE_NAME="$name"
    [ -n "$id" ] && DEVICE_ID="$id"

    return 0
}

# Configuración de red
config_network() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN DE RED\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Orden de fallback: $FALLBACK_ORDER"
    echo "  Intentos de reintento: $RETRY_ATTEMPTS"
    echo "  Retraso entre reintentos: $RETRY_DELAY segundos"

    echo ""
    echo "1️⃣  Orden de fallback"
    echo "2️⃣  Intentos de reintento"
    echo "3️⃣  Retraso entre reintentos"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            echo ""
            echo "Canales disponibles:"
            echo "  sms, telegram, voip, mesh_wifi, mesh_bluetooth, radio, satellite"
            read -p "📤 Orden de fallback (separado por espacios): " order
            if [ -n "$order" ]; then
                FALLBACK_ORDER="$order"
            fi
            ;;
        2)
            read -p "🔢 Intentos de reintento (1-10, default: $RETRY_ATTEMPTS): " attempts
            if [ -n "$attempts" ]; then
                RETRY_ATTEMPTS="$attempts"
            fi
            ;;
        3)
            read -p "⏱️  Retraso entre reintentos (segundos, default: $RETRY_DELAY): " delay
            if [ -n "$delay" ]; then
                RETRY_DELAY="$delay"
            fi
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    config_network
}

# Configuración de Telegram
config_telegram() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN DE TELEGRAM\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Bot Token: $( [ -n "$TELEGRAM_BOT_TOKEN" ] && echo "✅ Configurado" || echo "❌ No configurado")"
    echo "  Chat ID por defecto: $TELEGRAM_DEFAULT_CHAT_ID"
    echo "  Webhook URL: $TELEGRAM_WEBHOOK_URL"

    echo ""
    read -p "🤖 Bot Token (dejar vacío para no cambiar): " token
    read -p "💬 Chat ID por defecto (dejar vacío para no cambiar): " chat_id
    read -p "🌐 Webhook URL (dejar vacío para no cambiar): " webhook_url

    [ -n "$token" ] && TELEGRAM_BOT_TOKEN="$token"
    [ -n "$chat_id" ] && TELEGRAM_DEFAULT_CHAT_ID="$chat_id"
    [ -n "$webhook_url" ] && TELEGRAM_WEBHOOK_URL="$webhook_url"

    return 0
}

# Configuración de VoIP
config_voip() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN DE VOIP\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Servidor SIP: $SIP_SERVER"
    echo "  Usuario: $SIP_USERNAME"
    echo "  Puerto: $SIP_PORT"
    echo "  Asterisk: $( [ "$ASTERISK_ENABLED" = "true" ] && echo "✅ Habilitado" || echo "❌ Deshabilitado")"

    echo ""
    echo "1️⃣  Configuración SIP"
    echo "2️⃣  Configuración de Asterisk"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "🌐 Servidor SIP: " server
            read -p "👤 Usuario: " user
            read -p "🔑 Contraseña: " pass
            read -p "🌐 Puerto (default: $SIP_PORT): " port

            [ -n "$server" ] && SIP_SERVER="$server"
            [ -n "$user" ] && SIP_USERNAME="$user"
            [ -n "$pass" ] && SIP_PASSWORD="$pass"
            [ -n "$port" ] && SIP_PORT="$port"
            ;;
        2)
            read -p "📡 ¿Habilitar Asterisk? (s/n, current: $ASTERISK_ENABLED): " enabled
            read -p "📁 Ruta de configuración (default: $ASTERISK_CONFIG_PATH): " config_path

            [ -n "$enabled" ] && ASTERISK_ENABLED="$enabled"
            [ -n "$config_path" ] && ASTERISK_CONFIG_PATH="$config_path"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    config_voip
}

# Configuración de Radio
config_radio() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN DE RADIO\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Habilitado: $( [ "$RADIO_ENABLED" = "true" ] && echo "✅ Sí" || echo "❌ No")"
    echo "  Frecuencia: $RADIO_FREQUENCY MHz"
    echo "  Modo: $RADIO_MODE"
    echo "  Velocidad: $RADIO_BAUDRATE baudios"

    echo ""
    read -p "📡 ¿Habilitar Radio? (s/n, current: $RADIO_ENABLED): " enabled
    read -p "🎵 Frecuencia (MHz, default: $RADIO_FREQUENCY): " frequency
    read -p "📊 Modo (AX.25, etc., default: $RADIO_MODE): " mode
    read -p "⚡ Velocidad (baudios, default: $RADIO_BAUDRATE): " baudrate

    [ -n "$enabled" ] && RADIO_ENABLED="$enabled"
    [ -n "$frequency" ] && RADIO_FREQUENCY="$frequency"
    [ -n "$mode" ] && RADIO_MODE="$mode"
    [ -n "$baudrate" ] && RADIO_BAUDRATE="$baudrate"

    return 0
}

# Configuración de Satélite
config_satellite() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN DE SATELITE\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Habilitado: $( [ "$SATELLITE_ENABLED" = "true" ] && echo "✅ Sí" || echo "❌ No")"
    echo "  Proveedor: $SATELLITE_PROVIDER"
    echo "  Dispositivo: $SATELLITE_DEVICE"

    echo ""
    read -p "🛰️  ¿Habilitar Satélite? (s/n, current: $SATELLITE_ENABLED): " enabled
    read -p "📡 Proveedor (iridium/globalstar, default: $SATELLITE_PROVIDER): " provider
    read -p "🔌 Dispositivo (/dev/ttyS0, etc., default: $SATELLITE_DEVICE): " device

    [ -n "$enabled" ] && SATELLITE_ENABLED="$enabled"
    [ -n "$provider" ] && SATELLITE_PROVIDER="$provider"
    [ -n "$device" ] && SATELLITE_DEVICE="$device"

    return 0
}

# Configuración de seguridad
config_security() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ⚙️  CONFIGURACIÓN DE SEGURIDAD\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "📌 Configuración actual:"
    echo "  Cifrado: $( [ "$ENCRYPTION_ENABLED" = "true" ] && echo "✅ Habilitado" || echo "❌ Deshabilitado")"
    echo "  Auto-eliminar: $( [ "$AUTO_DELETE_ENABLED" = "true" ] && echo "✅ Habilitado" || echo "❌ Deshabilitado")"
    echo "  Días de auto-eliminar: $AUTO_DELETE_DAYS"
    echo "  Nivel de log: $LOG_LEVEL"
    echo "  Longitud de clave: $KEY_LENGTH bits"
    echo "  Modo sigiloso: $( [ "$STEALTH_MODE" = "true" ] && echo "✅ Habilitado" || echo "❌ Deshabilitado")"

    echo ""
    echo "1️⃣  Habilitar/Deshabilitar cifrado"
    echo "2️⃣  Configurar auto-eliminar"
    echo "3️⃣  Nivel de log"
    echo "4️⃣  Longitud de clave RSA"
    echo "5️⃣  Modo sigiloso"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            local current=$(jq -r '.security.encryption' "$CONFIG_FILE")
            if [ "$current" = "true" ]; then
                ENCRYPTION_ENABLED=false
                info "Cifrado deshabilitado"
            else
                ENCRYPTION_ENABLED=true
                info "Cifrado habilitado"
            fi
            ;;
        2)
            read -p "🗑️  ¿Habilitar auto-eliminar? (s/n, current: $AUTO_DELETE_ENABLED): " enabled
            read -p "📅 Días para auto-eliminar (default: $AUTO_DELETE_DAYS): " days

            [ -n "$enabled" ] && AUTO_DELETE_ENABLED="$enabled"
            [ -n "$days" ] && AUTO_DELETE_DAYS="$days"
            ;;
        3)
            echo ""
            echo "Niveles de log disponibles:"
            echo "  1. DEBUG"
            echo "  2. INFO"
            echo "  3. WARNING"
            echo "  4. ERROR"
            echo "  5. CRITICAL"
            read -p "👉 Selecciona nivel (1-5): " level_choice

            case $level_choice in
                1) LOG_LEVEL="DEBUG" ;;
                2) LOG_LEVEL="INFO" ;;
                3) LOG_LEVEL="WARNING" ;;
                4) LOG_LEVEL="ERROR" ;;
                5) LOG_LEVEL="CRITICAL" ;;
                *) error "Opción no válida" ; return ;;
            esac

            info "Nivel de log actualizado a $LOG_LEVEL"
            ;;
        4)
            read -p "🔢 Longitud de clave RSA (1024/2048/4096, default: $KEY_LENGTH): " length
            if [ -n "$length" ]; then
                KEY_LENGTH="$length"
            fi
            ;;
        5)
            local current=$(jq -r '.security.stealth_mode' "$CONFIG_FILE")
            if [ "$current" = "true" ]; then
                STEALTH_MODE=false
                info "Modo sigiloso deshabilitado"
            else
                STEALTH_MODE=true
                info "Modo sigiloso habilitado"
            fi
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    config_security
}

# Mostrar configuración actual
show_config() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📄 CONFIGURACIÓN ACTUAL\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar configuración en formato bonito
    jq '.' "$CONFIG_FILE" | less

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
}

# Menú de contactos
contacts_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  👥 GESTIÓN DE CONTACTOS\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos
    echo "📋 Contactos configurados:"
    jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name) - Tel: \(.value.phone // "N/A") - TG: \(.value.telegram_chat_id // "N/A") - SIP: \(.value.sip_address // "N/A") - Prioridad: \(.value.priority // "N/A")"' "$CONTACTS_FILE"

    echo ""
    echo "1️⃣  Añadir contacto"
    echo "2️⃣  Editar contacto"
    echo "3️⃣  Eliminar contacto"
    echo "4️⃣  Ver contacto"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1) add_contact ;;
        2) edit_contact ;;
        3) delete_contact ;;
        4) view_contact ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    contacts_menu
}

# Añadir contacto
add_contact() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ➕ AÑADIR CONTACTO\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    read -p "🆔 ID del contacto: " contact_id
    if [ -z "$contact_id" ]; then
        error "El ID no puede estar vacío"
        return
    fi

    # Verificar si el contacto ya existe
    if jq -e --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "El contacto $contact_id ya existe"
        return
    fi

    read -p "👤 Nombre: " name
    read -p "📱 Teléfono (opcional): " phone
    read -p "💬 Chat ID de Telegram (opcional): " telegram
    read -p "📞 SIP Address (opcional): " sip
    read -p "🔢 Prioridad (1-10, default: 5): " priority
    read -p "✅ ¿Contacto de confianza? (s/n, default: s): " trusted

    priority="${priority:-5}"
    trusted="${trusted:-s}"

    # Añadir contacto
    jq --arg id "$contact_id" \
       --arg name "$name" \
       --arg phone "$phone" \
       --arg telegram "$telegram" \
       --arg sip "$sip" \
       --argjson priority "$priority" \
       --argjson trusted "$([ "$trusted" = "s" ] && echo "true" || echo "false")" \
       '.contacts += {($id): {"name": $name, "phone": $phone, "telegram_chat_id": $telegram, "sip_address": $sip, "priority": $priority, "trusted": $trusted}}' \
       "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"

    # Generar claves para el contacto
    read -p "🔑 ¿Generar claves para este contacto? (s/n, default: s): " generate_keys
    if [ "${generate_keys:-s}" = "s" ]; then
        generate_keys "$contact_id"
    fi

    success "Contacto $contact_id añadido"
}

# Editar contacto
edit_contact() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  ✏️  EDITAR CONTACTO\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos
    echo "📋 Contactos configurados:"
    jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

    read -p "🆔 ID del contacto a editar: " contact_id
    if [ -z "$contact_id" ]; then
        error "El ID no puede estar vacío"
        return
    fi

    # Verificar si el contacto existe
    if ! jq -e --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "Contacto $contact_id no existe"
        return
    fi

    # Mostrar información actual del contacto
    echo ""
    echo "📌 Información actual:"
    jq -r --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" | jq .

    read -p "👤 Nombre (dejar vacío para no cambiar): " name
    read -p "📱 Teléfono (dejar vacío para no cambiar): " phone
    read -p "💬 Chat ID de Telegram (dejar vacío para no cambiar): " telegram
    read -p "📞 SIP Address (dejar vacío para no cambiar): " sip
    read -p "🔢 Prioridad (1-10, dejar vacío para no cambiar): " priority
    read -p "✅ ¿Contacto de confianza? (s/n, dejar vacío para no cambiar): " trusted

    # Construir comando jq
    local update_cmd="."
    [ -n "$name" ] && update_cmd="$update_cmd | .contacts[$contact_id].name = \"$name\""
    [ -n "$phone" ] && update_cmd="$update_cmd | .contacts[$contact_id].phone = \"$phone\""
    [ -n "$telegram" ] && update_cmd="$update_cmd | .contacts[$contact_id].telegram_chat_id = \"$telegram\""
    [ -n "$sip" ] && update_cmd="$update_cmd | .contacts[$contact_id].sip_address = \"$sip\""
    [ -n "$priority" ] && update_cmd="$update_cmd | .contacts[$contact_id].priority = $priority"
    [ -n "$trusted" ] && update_cmd="$update_cmd | .contacts[$contact_id].trusted = $([ "$trusted" = "s" ] && echo "true" || echo "false")"

    jq "$update_cmd" "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"

    success "Contacto $contact_id actualizado"
}

# Eliminar contacto
delete_contact() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🗑️  ELIMINAR CONTACTO\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos
    echo "📋 Contactos configurados:"
    jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

    read -p "🆔 ID del contacto a eliminar: " contact_id
    if [ -z "$contact_id" ]; then
        error "El ID no puede estar vacío"
        return
    fi

    # Verificar si el contacto existe
    if ! jq -e --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "Contacto $contact_id no existe"
        return
    fi

    # Confirmar
    read -p "⚠️  ¿Estás seguro de que quieres eliminar $contact_id? (s/n): " confirm
    if [ "${confirm:-n}" != "s" ]; then
        info "Eliminación cancelada"
        return
    fi

    # Eliminar contacto
    jq --arg id "$contact_id" 'del(.contacts[$id])' "$CONTACTS_FILE" > "$CONTACTS_FILE.tmp" && mv "$CONTACTS_FILE.tmp" "$CONTACTS_FILE"

    # Eliminar claves del contacto
    rm -f "$KEYS_DIR/${contact_id}_"* 2>/dev/null

    success "Contacto $contact_id eliminado"
}

# Ver contacto
view_contact() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  👁️  VER CONTACTO\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Mostrar contactos
    echo "📋 Contactos configurados:"
    jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

    read -p "🆔 ID del contacto: " contact_id
    if [ -z "$contact_id" ]; then
        error "El ID no puede estar vacío"
        return
    fi

    # Verificar si el contacto existe
    if ! jq -e --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "Contacto $contact_id no existe"
        return
    fi

    # Mostrar información del contacto
    echo ""
    echo -e "\033[1;34m📋 INFORMACIÓN DEL CONTACTO:\033[0m"
    jq -r --arg id "$contact_id" '.contacts[$id]' "$CONTACTS_FILE" | jq .

    # Mostrar claves
    echo ""
    echo -e "\033[1;34m🔑 CLAVES:\033[0m"
    if [ -f "$KEYS_DIR/${contact_id}_key.txt" ]; then
        echo "  ✅ Clave AES: Configurada"
    else
        echo "  ❌ Clave AES: No configurada"
    fi

    if [ -f "$KEYS_DIR/${contact_id}_public.pem" ]; then
        echo "  ✅ Clave pública RSA: Configurada"
    else
        echo "  ❌ Clave pública RSA: No configurada"
    fi

    if [ -f "$KEYS_DIR/${contact_id}_private.pem" ]; then
        echo "  ✅ Clave privada RSA: Configurada"
    else
        echo "  ❌ Clave privada RSA: No configurada"
    fi

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
}

# Menú de claves
keys_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🗝️  GESTIÓN DE CLAVES\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Generar claves para contacto"
    echo "2️⃣  Intercambiar claves con contacto"
    echo "3️⃣  Recibir clave de contacto"
    echo "4️⃣  Listar claves"
    echo "5️⃣  Eliminar claves"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos configurados:"
            jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            generate_keys "$contact_id"
            ;;
        2)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos configurados:"
            jq -r '.contacts | to_entries[] | select(.value.phone != null or .value.telegram_chat_id != null) | "  \(.key): \(.value.name) - \(.value.phone // .value.telegram_chat_id)"' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            echo ""
            echo "Selecciona método para enviar la clave:"
            echo "1️⃣  SMS"
            echo "2️⃣  Telegram"
            read -p "👉 Método: " method_choice

            case $method_choice in
                1) exchange_keys "$contact_id" "sms" ;;
                2) exchange_keys "$contact_id" "telegram" ;;
                *) error "Método no válido" ;;
            esac
            ;;
        3)
            read -p "🆔 ID del contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un ID de contacto"
                return
            fi

            read -p "🔑 Clave pública: " public_key
            if [ -z "$public_key" ]; then
                error "La clave pública no puede estar vacía"
                return
            fi

            receive_key "$contact_id" "$public_key"
            ;;
        4)
            echo ""
            echo "🗝️  Claves generadas:"
            ls -1 "$KEYS_DIR" 2>/dev/null | sed 's/_.*//' | sort -u | while read -r contact_id; do
                echo "  $contact_id:"
                [ -f "$KEYS_DIR/${contact_id}_key.txt" ] && echo "    ✅ AES"
                [ -f "$KEYS_DIR/${contact_id}_public.pem" ] && echo "    ✅ RSA Pública"
                [ -f "$KEYS_DIR/${contact_id}_private.pem" ] && echo "    ✅ RSA Privada"
            done
            ;;
        5)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos con claves:"
            ls -1 "$KEYS_DIR" 2>/dev/null | sed 's/_.*//' | sort -u | while read -r contact_id; do
                [ -f "$KEYS_DIR/${contact_id}_key.txt" ] || [ -f "$KEYS_DIR/${contact_id}_public.pem" ] || [ -f "$KEYS_DIR/${contact_id}_private.pem" ]
            done | jq -r --arg id "$contact_id" '.contacts[$id].name // $id' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            # Confirmar
            read -p "⚠️  ¿Estás seguro de que quieres eliminar todas las claves de $contact_id? (s/n): " confirm
            if [ "${confirm:-n}" != "s" ]; then
                info "Eliminación cancelada"
                return
            fi

            rm -f "$KEYS_DIR/${contact_id}_"* 2>/dev/null
            success "Claves de $contact_id eliminadas"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    keys_menu
}

# Menú de cola de mensajes
process_queue_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📦 GESTIÓN DE COLA DE MENSAJES\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    local pending=$(count_messages "pending")
    local processing=$(count_messages "processing")
    local sent=$(count_messages "sent")
    local failed=$(count_messages "failed")

    echo "📊 Estadísticas de la cola:"
    echo "  Pendientes: $pending"
    echo "  Procesando: $processing"
    echo "  Enviados: $sent"
    echo "  Fallidos: $failed"

    echo ""
    echo "1️⃣  Procesar todos los mensajes pendientes"
    echo "2️⃣  Procesar mensajes de un canal específico"
    echo "3️⃣  Ver cola detallada"
    echo "4️⃣  Limpiar mensajes antiguos"
    echo "5️⃣  Reintentar mensajes fallidos"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            info "Procesando todos los mensajes pendientes..."
            process_queue
            success "Cola procesada"
            ;;
        2)
            echo ""
            echo "Canales disponibles:"
            echo "  sms, telegram, voip, mesh_wifi, mesh_bluetooth, radio, satellite"
            read -p "📤 Canal: " channel
            if [ -n "$channel" ]; then
                info "Procesando mensajes del canal $channel..."
                process_queue "--channel $channel"
                success "Cola procesada para $channel"
            else
                error "Debes especificar un canal"
            fi
            ;;
        3)
            clear
            echo -e "\033[1;34m====================================\033[0m"
            echo -e "\033[1;34m  📋 COLA DETALLADA\033[0m"
            echo -e "\033[1;34m====================================\033[0m"
            echo ""

            sqlite3 "$QUEUE_DB" "SELECT id, contact_id, channel, timestamp, status, attempts FROM messages ORDER BY priority DESC, timestamp ASC;" | \
            awk 'BEGIN {print "ID | Contacto | Canal | Fecha | Estado | Intentos | Prioridad"}
                NR>1 {printf "%-3d | %-15s | %-12s | %-19s | %-7s | %2d | %d\n", $1, $2, $3, $4, $5, $6, $7}'

            read -p "Presiona Enter para continuar..." _ 2>/dev/null
            ;;
        4)
            read -p "🗑️  ¿Cuántos días conservar mensajes? (default: 30): " days
            clean_queue "${days:-30}"
            success "Mensajes antiguos limpiados"
            ;;
        5)
            info "Reintentando mensajes fallidos..."
            sqlite3 "$QUEUE_DB" "UPDATE messages SET status = 'pending', attempts = 0 WHERE status = 'failed';"
            process_queue
            success "Mensajes fallidos reintentados"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    process_queue_menu
}

# Menú de estado
status_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📊 ESTADO DEL SISTEMA\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Información del dispositivo
    echo -e "\033[1;34m📱 DISPOSITIVO:\033[0m"
    get_device_summary
    echo ""

    # Estado de la red
    echo -e "\033[1;34m🌐 RED:\033[0m"
    get_network_info
    echo ""

    # Cola de mensajes
    local pending=$(count_messages "pending")
    local processing=$(count_messages "processing")
    local sent=$(count_messages "sent")
    local failed=$(count_messages "failed")

    echo -e "\033[1;34m📦 COLA DE MENSAJES:\033[0m"
    echo "  Pendientes: $pending"
    echo "  Procesando: $processing"
    echo "  Enviados: $sent"
    echo "  Fallidos: $failed"
    echo ""

    # Canales disponibles
    echo -e "\033[1;34m📡 CANALES DISPONIBLES:\033[0m"
    local available_channels=($(get_available_channels))
    for channel in "${available_channels[@]}"; do
        echo "  ✅ $channel"
    done

    # Canales no disponibles
    local all_channels=($FALLBACK_ORDER)
    for channel in "${all_channels[@]}"; do
        if ! [[ " ${available_channels[@]} " =~ " $channel " ]]; then
            echo "  ❌ $channel"
        fi
    done
    echo ""

    # Batería
    if command -v termux-battery-status &>/dev/null; then
        echo -e "\033[1;34m🔋 BATERÍA:\033[0m"
        format_battery_status "$(get_battery_status)"
        echo ""
    fi

    # Logs
    echo -e "\033[1;34m📝 LOGS:\033[0m"
    local log_files=$(ls -1 "$LOG_DIR" 2>/dev/null | wc -l)
    local log_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
    echo "  Archivos: $log_files"
    echo "  Tamaño: $log_size"

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
}

# Menú de utilidades
utilities_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🛠️  UTILIDADES\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Ubicación"
    echo "2️⃣  Batería"
    echo "3️⃣  Información del dispositivo"
    echo "4️⃣  Compresión"
    echo "5️⃣  Limpiar datos"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1) location_menu ;;
        2) battery_menu ;;
        3) device_info_menu ;;
        4) compress_menu ;;
        5)
            read -p "⚠️  ¿Estás seguro de que quieres limpiar todos los datos? (s/n): " confirm
            if [ "${confirm:-n}" = "s" ]; then
                # Limpiar cola
                clean_queue 0

                # Limpiar logs
                clean_logs 0

                # Limpiar mensajes recibidos
                rm -rf "$DATA_DIR/received" 2>/dev/null

                success "Datos limpiados"
            else
                info "Limpieza cancelada"
            fi
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    utilities_menu
}

# Procesar comandos desde línea de comandos
process_command() {
    local command="$1"
    shift

    case "$command" in
        "send")
            if [ $# -lt 2 ]; then
                error "Uso: comlink send <canal> <mensaje> [destino]"
                exit 1
            fi
            local send_channel="$1"
            local send_message="$2"
            local send_destination="${3:-}"
            case "$send_channel" in
                "sms")
                    [ -n "$send_destination" ] || send_destination="$(
                        jq -r '.contacts.emergency.phone // empty' "$CONTACTS_FILE"
                    )"
                    [ -n "$send_destination" ] || {
                        error "SMS requiere un destino o contacts.emergency.phone"
                        exit 1
                    }
                    send_sms "$send_destination" "$send_message" ""
                    ;;
                "telegram")
                    [ -n "$send_destination" ] || send_destination="$TELEGRAM_DEFAULT_CHAT_ID"
                    [ -n "$send_destination" ] || {
                        error "Telegram requiere un destino o telegram.default_chat_id"
                        exit 1
                    }
                    send_telegram "$send_destination" "$send_message" ""
                    ;;
                "voip")
                    [ -n "$send_destination" ] || {
                        error "VoIP requiere un destino SIP"
                        exit 1
                    }
                    voip_call "$send_destination"
                    ;;
                "mesh_wifi"|"mesh_bluetooth"|"radio"|"satellite")
                    [ -n "$send_destination" ] || send_destination="$(
                        jq -r '.contacts.emergency.name // "emergency"' "$CONTACTS_FILE"
                    )"
                    "send_${send_channel}" "$send_destination" "$send_message" ""
                    ;;
                *)
                    error "Canal no válido: $send_channel"
                    exit 1
                    ;;
            esac
            ;;
        "sms")
            if [ $# -lt 2 ]; then
                error "Uso: comlink sms <número> <mensaje>"
                exit 1
            fi
            send_sms "$1" "$2" ""
            ;;
        "telegram")
            if [ $# -lt 1 ]; then
                error "Uso: comlink telegram <mensaje> [chat_id]"
                exit 1
            fi
            local chat_id="${2:-$TELEGRAM_DEFAULT_CHAT_ID}"
            send_telegram "$chat_id" "$1" ""
            ;;
        "location")
            if [ $# -lt 1 ]; then
                error "Uso: comlink location <contacto>"
                exit 1
            fi
            send_location "$1" "auto"
            ;;
        "location-get")
            get_gps_location
            ;;
        "device-info")
            get_device_info
            ;;
        "battery-status")
            get_battery_status
            ;;
        "queue-process")
            process_queue "${1:-}"
            ;;
        "queue-clean")
            clean_queue "${1:-30}"
            ;;
        "queue-retry-failed")
            sqlite3 "$QUEUE_DB" "UPDATE messages SET status = 'pending', attempts = 0 WHERE status = 'failed';"
            process_queue
            ;;
        "emergency")
            emergency_alert "$@"
            ;;
        "voip")
            if [ $# -lt 1 ]; then
                error "Uso: comlink voip <comando> [argumentos]"
                exit 1
            fi
            case "$1" in
                "call")
                    if [ $# -lt 2 ]; then
                        error "Uso: comlink voip call <destino>"
                        exit 1
                    fi
                    voip_call "$2"
                    ;;
                "server")
                    start_p2p_ssh_server
                    ;;
                *)
                    error "Comando VoIP no válido"
                    exit 1
                    ;;
            esac
            ;;
        "mesh")
            mesh_menu
            ;;
        "mesh_wifi")
            mesh_wifi_menu
            ;;
        "mesh_bluetooth")
            mesh_bluetooth_menu
            ;;
        "radio")
            radio_menu
            ;;
        "satellite")
            satellite_menu
            ;;
        "config")
            config_menu
            ;;
        "contacts")
            contacts_menu
            ;;
        "keys")
            keys_menu
            ;;
        "queue")
            process_queue_menu
            ;;
        "status")
            status_menu
            ;;
        "status-json"|"--status-json")
            status_json
            ;;
        "utilities"|"utils")
            utilities_menu
            ;;
        "help"|"--help"|"-h")
            help_menu
            ;;
        "version"|"--version"|"-v")
            echo "COM-LINK v$COM_LINK_VERSION"
            echo "ID del dispositivo: $DEVICE_ID"
            echo "Nombre: $DEVICE_NAME"
            exit 0
            ;;
        *)
            error "Comando desconocido: $command"
            help_menu
            exit 1
            ;;
    esac
}

# Menú de ayuda
help_menu() {
    clear
    echo -e "\033[1;34m============================================\033[0m"
    echo -e "\033[1;34m  ❓ AYUDA DE COM-LINK v3.0\033[0m"
    echo -e "\033[1;34m============================================\033[0m"
    echo ""
    echo -e "\033[1;34m📌 DESCRIPCIÓN:\033[0m"
    echo "COM-LINK es un sistema de comunicación de emergencia diseñado para"
    echo "funcionar incluso cuando la red principal está caída o vigilada."
    echo ""
    echo "Proporciona múltiples canales de comunicación que pueden operar"
    echo "de forma independiente o en combinación:"
    echo ""
    echo "  📱 SMS - Funciona con red celular (no requiere internet)"
    echo "  🤖 Telegram - Requiere conexión a internet"
    echo "  📞 VoIP - Llamadas de voz sobre IP (requiere servidor SIP o Asterisk local)"
    echo "  🌐 Mesh WiFi - Comunicación directa entre dispositivos en la misma red"
    echo "  📡 Mesh Bluetooth - Comunicación directa entre dispositivos cercanos"
    echo "  📻 Radio Aficionados - Comunicación por radio (requiere hardware)"
    echo "  🛰️  Satélite - Comunicación satelital (requiere hardware)"
    echo ""
    echo -e "\033[1;34m📋 USO:\033[0m"
    echo "comlink [comando] [argumentos]"
    echo ""
    echo "Comandos disponibles:"
    echo ""
    echo -e "\033[1m  📱 Envío de mensajes:\033[0m"
    echo "    comlink sms <número> <mensaje>              - Envía un SMS"
    echo "    comlink telegram <mensaje> [chat_id]        - Envía mensaje por Telegram"
    echo "    comlink location <contacto>                 - Envía la ubicación"
    echo "    comlink emergency <contacto> <mensaje>      - Alerta multicanal confirmada"
    echo "      (añade --dry-run para revisar; --confirm para transmitir)"
    echo ""
    echo -e "\033[1m  📞 VoIP:\033[0m"
    echo "    comlink voip call <destino>                 - Realiza una llamada VoIP"
    echo "    comlink voip server                          - Inicia servidor VoIP local"
    echo ""
    echo -e "\033[1m  🌐 Mesh:\033[0m"
    echo "    comlink mesh                                - Menú de comunicación mesh"
    echo "    comlink mesh_wifi                           - Menú de Mesh WiFi"
    echo "    comlink mesh_bluetooth                      - Menú de Mesh Bluetooth"
    echo ""
    echo -e "\033[1m  📻 Radio y Satélite:\033[0m"
    echo "    comlink radio                               - Menú de Radio Aficionados"
    echo "    comlink satellite                            - Menú de Satélite"
    echo ""
    echo -e "\033[1m  ⚙️  Configuración:\033[0m"
    echo "    comlink config                              - Configuración del sistema"
    echo "    comlink contacts                            - Gestión de contactos"
    echo "    comlink keys                                - Gestión de claves"
    echo ""
    echo -e "\033[1m  📦 Cola y Estado:\033[0m"
    echo "    comlink queue                               - Gestión de cola de mensajes"
    echo "    comlink status                              - Estado del sistema"
    echo "    comlink status-json                         - Estado JSON sin menú"
    echo ""
    echo -e "\033[1m  🛠️  Utilidades:\033[0m"
    echo "    comlink utilities                           - Utilidades varias"
    echo ""
    echo -e "\033[1m  ❓ Ayuda:\033[0m"
    echo "    comlink help                                - Mostrar esta ayuda"
    echo "    comlink version                             - Versión de COM-LINK"
    echo ""
    echo -e "\033[1;34m🎯 EJEMPLOS:\033[0m"
    echo ""
    echo -e "\033[1m  # Enviar SMS\033[0m"
    echo "    comlink sms +573001234567 \"Mensaje de emergencia\""
    echo ""
    echo -e "\033[1m  # Enviar ubicación\033[0m"
    echo "    comlink location emergencia"
    echo ""
    echo -e "\033[1m  # Revisar una alerta sin transmitir\033[0m"
    echo "    comlink emergency emergencia \"Necesito ayuda\" --dry-run"
    echo ""
    echo -e "\033[1m  # Transmitir alerta por canales preparados\033[0m"
    echo "    comlink emergency emergencia \"Necesito ayuda\" --confirm"
    echo ""
    echo -e "\033[1m  # Llamada VoIP\033[0m"
    echo "    comlink voip call usuario@192.168.1.100"
    echo ""
    echo -e "\033[1m  # Iniciar servidor Mesh WiFi\033[0m"
    echo "    comlink mesh_wifi"
    echo "    (Luego selecciona 'Iniciar servidor HTTP')"
    echo ""
    echo -e "\033[1m  # Configurar el sistema\033[0m"
    echo "    comlink config"
    echo ""
    echo -e "\033[1m  # Procesar cola de mensajes\033[0m"
    echo "    comlink queue"
    echo ""
    echo -e "\033[1;34m🔧 DEPENDENCIAS:\033[0m"
    echo "  Obligatorias:"
    echo "    - Termux:API (para SMS, ubicación, etc.)"
    echo "    - jq (para procesamiento JSON)"
    echo "    - sqlite3 (para la cola de mensajes)"
    echo "    - curl (para Telegram y HTTP)"
    echo "    - openssl (para cifrado)"
    echo ""
    echo "  Opcionales:"
    echo "    - hcitool, bluez (para Bluetooth)"
    echo "    - linphone, asterisk (para VoIP)"
    echo "    - openssh (para SSH)"
    echo "    - nmap (para detección de dispositivos)"
    echo "    - soundmodem, ax25-tools (para Radio Aficionados)"
    echo ""
    echo -e "\033[1;34m📦 INSTALACIÓN:\033[0m"
    echo "  1. Instala Termux desde F-Droid (recomendado)"
    echo "  2. Ejecuta:"
    echo "     pkg update && pkg upgrade"
    echo "     pkg install jq sqlite3 curl openssl termux-api"
    echo "     pkg install hcitool bluez linphone asterisk openssh nmap"
    echo "  3. Descarga COM-LINK:"
    echo "     git clone https://github.com/tu-usuario/comlink.git"
    echo "     cd comlink"
    echo "     chmod +x *.sh core/*.sh channels/*.sh mesh/*.sh utils/*.sh"
    echo "  4. Ejecuta el instalador:"
    echo "     ./install.sh"
    echo ""
    echo -e "\033[1;34m⚠️  ADVERTENCIA:\033[0m"
    echo "  COM-LINK está diseñado para uso en emergencias y pruebas de comunicación."
    echo "  No lo uses para actividades ilegales."
    echo "  El uso no autorizado de sistemas de comunicación puede violar leyes locales."
    echo ""
    echo -e "\033[1;34m📜 LICENCIA:\033[0m"
    echo "  COM-LINK se distribuye bajo la Licencia MIT."
    echo "  Consulta el archivo LICENSE para más detalles."

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
}

# ============================================================
# PUNTO DE ENTRADA PRINCIPAL
# ============================================================
# Verificar dependencias
check_dependencies() {
    local missing=()

    # Dependencias del núcleo. Las APIs específicas de Termux son opcionales:
    # solo se necesitan cuando se usa el canal correspondiente.
    for cmd in jq sqlite3 curl openssl; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Faltan dependencias obligatorias: ${missing[*]}"
        error "Instálalas con: pkg install ${missing[*]}"
        exit 1
    fi

    local optional_missing=()
    for cmd in termux-sms-send termux-location termux-wifi-enable; do
        if ! command -v "$cmd" &>/dev/null; then
            optional_missing+=("$cmd")
        fi
    done
    if [ ${#optional_missing[@]} -gt 0 ] && [ "$COMLINK_MACHINE_OUTPUT" != "true" ]; then
        info "APIs Termux no disponibles: ${optional_missing[*]} (canales móviles limitados)"
    fi
}

# Estado no interactivo y honesto para el dashboard. "ready" significa que
# existen los requisitos locales conocidos; no prueba ni ejecuta un envío.
status_json() {
    local missing=()
    local core_ready=true
    for cmd in jq sqlite3 curl openssl; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
            core_ready=false
        fi
    done

    local emergency_phone
    emergency_phone=$(jq -r '.contacts.emergency.phone // empty' "$CONTACTS_FILE")

    local sms_ready=false
    local sms_reason="Instala Termux:API y configura el teléfono de emergencia"
    if command -v termux-sms-send &>/dev/null && [ -n "$emergency_phone" ]; then
        sms_ready=true
        sms_reason="API de SMS y destino configurados; falta confirmar cobertura/SIM"
    elif ! command -v termux-sms-send &>/dev/null; then
        sms_reason="Falta termux-sms-send"
    elif [ -z "$emergency_phone" ]; then
        sms_reason="Falta contacts.emergency.phone"
    fi

    local telegram_ready=false
    local telegram_reason="Falta token o chat ID de Telegram"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_DEFAULT_CHAT_ID" ]; then
        telegram_ready=true
        telegram_reason="Token y chat ID configurados; falta confirmar conectividad"
    fi

    local voip_ready=false
    local voip_reason="Falta linphonec o configuración SIP"
    if command -v linphonec &>/dev/null && \
       [ -n "$SIP_SERVER" ] && [ -n "$SIP_USERNAME" ] && [ -n "$SIP_PASSWORD" ]; then
        voip_ready=true
        voip_reason="Cliente y credenciales SIP presentes; falta confirmar registro"
    fi

    local wifi_ready=false
    local wifi_reason="WiFi/Termux:API no disponible o no conectado"
    if command -v python3 &>/dev/null && command -v curl &>/dev/null && check_wifi; then
        wifi_ready=true
        wifi_reason="WiFi conectado; falta confirmar un peer COM-LINK"
    fi

    local bluetooth_ready=false
    local bluetooth_reason="Bluetooth RFCOMM no disponible"
    if command -v hcitool &>/dev/null && command -v rfcomm &>/dev/null && check_bluetooth; then
        bluetooth_ready=true
        bluetooth_reason="Bluetooth y RFCOMM presentes; falta confirmar un peer"
    fi

    # No se marcan como listos: las funciones de transmisión actuales no
    # implementan un driver verificable para hardware de radio/satélite.
    local radio_ready=false
    local radio_reason="Driver/TNC AX.25 verificado pendiente"
    local satellite_ready=false
    local satellite_reason="Driver del modelo satelital verificado pendiente"

    local missing_text
    missing_text=$(printf '%s\n' "${missing[@]}" | jq -Rsc 'split("\n") | map(select(length > 0))')
    jq -n \
        --arg version "$COM_LINK_VERSION" \
        --arg device_id "$DEVICE_ID" \
        --arg device_name "$DEVICE_NAME" \
        --argjson core_ready "$core_ready" \
        --argjson missing "$missing_text" \
        --argjson sms "$sms_ready" --arg sms_reason "$sms_reason" \
        --argjson telegram "$telegram_ready" --arg telegram_reason "$telegram_reason" \
        --argjson voip "$voip_ready" --arg voip_reason "$voip_reason" \
        --argjson wifi "$wifi_ready" --arg wifi_reason "$wifi_reason" \
        --argjson bluetooth "$bluetooth_ready" --arg bluetooth_reason "$bluetooth_reason" \
        --argjson radio "$radio_ready" --arg radio_reason "$radio_reason" \
        --argjson satellite "$satellite_ready" --arg satellite_reason "$satellite_reason" \
        '[
          {id:"sms", ready:$sms, reason:$sms_reason, requires:["Termux:API","SIM","destino"]},
          {id:"telegram", ready:$telegram, reason:$telegram_reason, requires:["token","chat ID","internet"]},
          {id:"voip", ready:$voip, reason:$voip_reason, requires:["linphonec","SIP"]},
          {id:"mesh_wifi", ready:$wifi, reason:$wifi_reason, requires:["WiFi","peer COM-LINK"]},
          {id:"mesh_bluetooth", ready:$bluetooth, reason:$bluetooth_reason, requires:["Bluetooth","RFCOMM","peer"]},
          {id:"radio", ready:$radio, reason:$radio_reason, requires:["TNC","driver AX.25","radio"]},
          {id:"satellite", ready:$satellite, reason:$satellite_reason, requires:["módem","driver del proveedor"]}
        ] as $channels |
        {
          # available describe el motor COM-LINK, no la presencia de un
          # canal físico. En Replit/PC el núcleo y sus comandos locales
          # pueden operar aunque Termux:API, SIM o radios no existan.
          available:$core_ready,
          channels_ready:(([$channels[] | select(.ready)] | length) > 0),
          core_ready:$core_ready,
          version:$version,
          device:{id:$device_id,name:$device_name},
          core:{ready:$core_ready,missing:$missing},
          channels:$channels,
          ready_channels:[$channels[] | select(.ready) | .id],
          ready_count:([$channels[] | select(.ready)] | length),
          note:"ready indica requisitos locales; no confirma que un mensaje haya sido entregado"
        }'
}

# Inicializar
check_dependencies
init_queue

# Manejo de señales
trap 'cleanup' INT TERM

cleanup() {
    info "Limpiando recursos..."
    stop_p2p_http_server 2>/dev/null
    stop_p2p_ssh_server 2>/dev/null
    stop_mesh_http_server 2>/dev/null
    stop_mesh_ssh_server 2>/dev/null
    stop_mesh_bluetooth_server 2>/dev/null
    stop_asterisk 2>/dev/null
    exit 0
}

# Procesar argumentos
if [ $# -eq 0 ]; then
    main_menu
else
    process_command "$@"
fi
