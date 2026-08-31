#!/bin/bash
# core/config.sh - Gestión de Configuración de COM-LINK v3.0

# ============================================================
# VARIABLES GLOBALES
# ============================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd ../ && pwd)"
INSTALL_DIR="$SCRIPT_DIR"
CONFIG_FILE="$INSTALL_DIR/data/config.json"
CONTACTS_FILE="$INSTALL_DIR/data/contacts.json"
DATA_DIR="$INSTALL_DIR/data"
KEYS_DIR="$DATA_DIR/keys"
QUEUE_DB="$DATA_DIR/queue/queue.db"
LOG_DIR="$DATA_DIR/logs"
TEMP_DIR="/tmp/comlink"

# Cargar configuración
load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        error "Archivo de configuración no encontrado: $CONFIG_FILE"
        exit 1
    fi

    # Cargar configuración general
    export COM_LINK_VERSION=$(jq -r '.version' "$CONFIG_FILE")
    export DEVICE_NAME=$(jq -r '.device.name' "$CONFIG_FILE")
    export DEVICE_ID=$(jq -r '.device.id' "$CONFIG_FILE")

    # Network
    export FALLBACK_ORDER=$(jq -r '.network.fallback_order | join(" ")' "$CONFIG_FILE")
    export RETRY_ATTEMPTS=$(jq -r '.network.retry_attempts' "$CONFIG_FILE")
    export RETRY_DELAY=$(jq -r '.network.retry_delay' "$CONFIG_FILE")

    # Mesh WiFi
    export MESH_WIFI_SSID=$(jq -r '.network.mesh_wifi.ssid' "$CONFIG_FILE")
    export MESH_WIFI_PASSWORD=$(jq -r '.network.mesh_wifi.password' "$CONFIG_FILE")
    export MESH_WIFI_PORT=$(jq -r '.network.mesh_wifi.port' "$CONFIG_FILE")

    # Mesh Bluetooth
    export MESH_BT_NAME=$(jq -r '.network.mesh_bluetooth.name' "$CONFIG_FILE")
    export MESH_BT_CHANNEL=$(jq -r '.network.mesh_bluetooth.channel' "$CONFIG_FILE")

    # Telegram
    export TELEGRAM_BOT_TOKEN=$(jq -r '.telegram.bot_token // empty' "$CONFIG_FILE")
    export TELEGRAM_DEFAULT_CHAT_ID=$(jq -r '.telegram.default_chat_id // empty' "$CONFIG_FILE")
    export TELEGRAM_WEBHOOK_URL=$(jq -r '.telegram.webhook_url // empty' "$CONFIG_FILE")

    # VoIP
    export SIP_SERVER=$(jq -r '.voip.sip.server' "$CONFIG_FILE")
    export SIP_USERNAME=$(jq -r '.voip.sip.username' "$CONFIG_FILE")
    export SIP_PASSWORD=$(jq -r '.voip.sip.password' "$CONFIG_FILE")
    export SIP_PORT=$(jq -r '.voip.sip.port' "$CONFIG_FILE")
    export ASTERISK_ENABLED=$(jq -r '.voip.asterisk.enabled' "$CONFIG_FILE")
    export ASTERISK_CONFIG_PATH=$(jq -r '.voip.asterisk.config_path' "$CONFIG_FILE")

    # Radio
    export RADIO_ENABLED=$(jq -r '.radio.enabled' "$CONFIG_FILE")
    export RADIO_FREQUENCY=$(jq -r '.radio.frequency' "$CONFIG_FILE")
    export RADIO_MODE=$(jq -r '.radio.mode' "$CONFIG_FILE")
    export RADIO_BAUDRATE=$(jq -r '.radio.baudrate' "$CONFIG_FILE")

    # Satellite
    export SATELLITE_ENABLED=$(jq -r '.satellite.enabled' "$CONFIG_FILE")
    export SATELLITE_PROVIDER=$(jq -r '.satellite.provider' "$CONFIG_FILE")
    export SATELLITE_DEVICE=$(jq -r '.satellite.device' "$CONFIG_FILE")

    # Security
    export ENCRYPTION_ENABLED=$(jq -r '.security.encryption' "$CONFIG_FILE")
    export AUTO_DELETE_ENABLED=$(jq -r '.security.auto_delete' "$CONFIG_FILE")
    export AUTO_DELETE_DAYS=$(jq -r '.security.auto_delete_days' "$CONFIG_FILE")
    export LOG_LEVEL=$(jq -r '.security.log_level' "$CONFIG_FILE")
    export KEY_LENGTH=$(jq -r '.security.key_length' "$CONFIG_FILE")
    export STEALTH_MODE=$(jq -r '.security.stealth_mode' "$CONFIG_FILE")

    # Crear directorios si no existen
    mkdir -p "$KEYS_DIR" "$LOG_DIR" "$DATA_DIR/queue" "$TEMP_DIR"
    chmod 700 "$KEYS_DIR"
}

# Guardar configuración
save_config() {
    local temp_file="$CONFIG_FILE.tmp"

    # Crear backup
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak" 2>/dev/null

    # Actualizar configuración
    jq \
        --arg version "$COM_LINK_VERSION" \
        --arg device_name "$DEVICE_NAME" \
        --arg device_id "$DEVICE_ID" \
        --argjson fallback_order "$(echo "$FALLBACK_ORDER" | jq -R 'split(" ")')" \
        --argjson retry_attempts "$RETRY_ATTEMPTS" \
        --argjson retry_delay "$RETRY_DELAY" \
        --arg mesh_wifi_ssid "$MESH_WIFI_SSID" \
        --arg mesh_wifi_password "$MESH_WIFI_PASSWORD" \
        --argjson mesh_wifi_port "$MESH_WIFI_PORT" \
        --arg mesh_bt_name "$MESH_BT_NAME" \
        --argjson mesh_bt_channel "$MESH_BT_CHANNEL" \
        --arg telegram_bot_token "$TELEGRAM_BOT_TOKEN" \
        --arg telegram_default_chat_id "$TELEGRAM_DEFAULT_CHAT_ID" \
        --arg telegram_webhook_url "$TELEGRAM_WEBHOOK_URL" \
        --arg sip_server "$SIP_SERVER" \
        --arg sip_username "$SIP_USERNAME" \
        --arg sip_password "$SIP_PASSWORD" \
        --argjson sip_port "$SIP_PORT" \
        --argjson asterisk_enabled "$ASTERISK_ENABLED" \
        --arg asterisk_config_path "$ASTERISK_CONFIG_PATH" \
        --argjson radio_enabled "$RADIO_ENABLED" \
        --arg radio_frequency "$RADIO_FREQUENCY" \
        --arg radio_mode "$RADIO_MODE" \
        --argjson radio_baudrate "$RADIO_BAUDRATE" \
        --argjson satellite_enabled "$SATELLITE_ENABLED" \
        --arg satellite_provider "$SATELLITE_PROVIDER" \
        --arg satellite_device "$SATELLITE_DEVICE" \
        --argjson encryption_enabled "$ENCRYPTION_ENABLED" \
        --argjson auto_delete_enabled "$AUTO_DELETE_ENABLED" \
        --argjson auto_delete_days "$AUTO_DELETE_DAYS" \
        --arg log_level "$LOG_LEVEL" \
        --argjson key_length "$KEY_LENGTH" \
        --argjson stealth_mode "$STEALTH_MODE" \
        '.version = $version |
         .device.name = $device_name |
         .device.id = $device_id |
         .network.fallback_order = $fallback_order |
         .network.retry_attempts = $retry_attempts |
         .network.retry_delay = $retry_delay |
         .network.mesh_wifi.ssid = $mesh_wifi_ssid |
         .network.mesh_wifi.password = $mesh_wifi_password |
         .network.mesh_wifi.port = $mesh_wifi_port |
         .network.mesh_bluetooth.name = $mesh_bt_name |
         .network.mesh_bluetooth.channel = $mesh_bt_channel |
         .telegram.bot_token = $telegram_bot_token |
         .telegram.default_chat_id = $telegram_default_chat_id |
         .telegram.webhook_url = $telegram_webhook_url |
         .voip.sip.server = $sip_server |
         .voip.sip.username = $sip_username |
         .voip.sip.password = $sip_password |
         .voip.sip.port = $sip_port |
         .voip.asterisk.enabled = $asterisk_enabled |
         .voip.asterisk.config_path = $asterisk_config_path |
         .radio.enabled = $radio_enabled |
         .radio.frequency = $radio_frequency |
         .radio.mode = $radio_mode |
         .radio.baudrate = $radio_baudrate |
         .satellite.enabled = $satellite_enabled |
         .satellite.provider = $satellite_provider |
         .satellite.device = $satellite_device |
         .security.encryption = $encryption_enabled |
         .security.auto_delete = $auto_delete_enabled |
         .security.auto_delete_days = $auto_delete_days |
         .security.log_level = $log_level |
         .security.key_length = $key_length |
         .security.stealth_mode = $stealth_mode' \
        "$CONFIG_FILE" > "$temp_file" && mv "$temp_file" "$CONFIG_FILE"

    chmod 600 "$CONFIG_FILE"
    success "Configuración guardada"
}

# Cargar contactos
load_contacts() {
    if [ ! -f "$CONTACTS_FILE" ]; then
        error "Archivo de contactos no encontrado: $CONTACTS_FILE"
        exit 1
    fi
    export CONTACTS_FILE
}

# Guardar contactos
save_contacts() {
    local temp_file="$CONTACTS_FILE.tmp"
    cp "$CONTACTS_FILE" "$temp_file" 2>/dev/null
    mv "$temp_file" "$CONTACTS_FILE"
    chmod 600 "$CONTACTS_FILE"
    success "Contactos guardados"
}

# Cargar clave para un contacto
load_key() {
    local contact_id="$1"
    local key_file="$KEYS_DIR/${contact_id}_private.pem"

    if [ -f "$key_file" ]; then
        cat "$key_file"
        return 0
    else
        error "Clave no encontrada para $contact_id"
        return 1
    fi
}

# Guardar clave para un contacto
save_key() {
    local contact_id="$1"
    local key="$2"
    local key_file="$KEYS_DIR/${contact_id}_private.pem"

    echo "$key" > "$key_file"
    chmod 600 "$key_file"
    success "Clave guardada para $contact_id"
}

# Inicializar
load_config
load_contacts
