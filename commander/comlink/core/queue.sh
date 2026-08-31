#!/bin/bash
# core/queue.sh - Sistema de Cola de Mensajes para COM-LINK v3.0

# ============================================================
# CONFIGURACIÓN
# ============================================================
QUEUE_DB="$INSTALL_DIR/data/queue/queue.db"

# ============================================================
# FUNCIONES
# ============================================================
# Inicializar base de datos
init_queue() {
    if [ ! -f "$QUEUE_DB" ]; then
        sqlite3 "$QUEUE_DB" <<EOF
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    message TEXT NOT NULL,
    encrypted TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 0,
    last_attempt DATETIME,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_contact ON messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_priority ON messages(priority);
CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp);
EOF
        debug "Base de datos de cola inicializada"
    fi
}

# Añadir mensaje a la cola
add_to_queue() {
    local contact_id="$1"
    local channel="$2"
    local message="$3"
    local encrypted="$4"
    local priority="${5:-0}"
    local metadata="${6:-}"

    # Escapar comillas simples para SQLite
    message=$(echo "$message" | sed "s/'/''/g")
    encrypted=$(echo "$encrypted" | sed "s/'/''/g")
    metadata=$(echo "$metadata" | sed "s/'/''/g")

    sqlite3 "$QUEUE_DB" <<EOF
INSERT INTO messages (contact_id, channel, message, encrypted, priority, status, metadata)
VALUES ('$contact_id', '$channel', '$message', '$encrypted', $priority, 'pending', '$metadata');
EOF

    if [ $? -eq 0 ]; then
        debug "Mensaje añadido a la cola (ID: $(sqlite3 "$QUEUE_DB" "SELECT last_insert_rowid();"))"
        return 0
    else
        error "Error al añadir mensaje a la cola"
        return 1
    fi
}

# Obtener mensajes pendientes
get_pending_messages() {
    local channel_filter="${1:-}"
    local limit="${2:-10}"

    if [ -n "$channel_filter" ]; then
        sqlite3 "$QUEUE_DB" "SELECT id, contact_id, channel, message, encrypted, priority, attempts FROM messages WHERE status = 'pending' AND channel = '$channel_filter' ORDER BY priority DESC, timestamp ASC LIMIT $limit;"
    else
        sqlite3 "$QUEUE_DB" "SELECT id, contact_id, channel, message, encrypted, priority, attempts FROM messages WHERE status = 'pending' ORDER BY priority DESC, timestamp ASC LIMIT $limit;"
    fi
}

# Obtener todos los mensajes pendientes
get_all_pending_messages() {
    sqlite3 "$QUEUE_DB" "SELECT id, contact_id, channel, message, encrypted, priority, attempts FROM messages WHERE status = 'pending' ORDER BY priority DESC, timestamp ASC;"
}

# Actualizar estado de un mensaje
update_message_status() {
    local id="$1"
    local status="$2"
    local encrypted="${3:-}"

    if [ -n "$encrypted" ]; then
        sqlite3 "$QUEUE_DB" "UPDATE messages SET status = '$status', encrypted = '$encrypted', attempts = attempts + 1, last_attempt = CURRENT_TIMESTAMP WHERE id = $id;"
    else
        sqlite3 "$QUEUE_DB" "UPDATE messages SET status = '$status', attempts = attempts + 1, last_attempt = CURRENT_TIMESTAMP WHERE id = $id;"
    fi
}

# Procesar cola
process_queue() {
    local channel_filter="${1:-}"

    # Obtener mensajes pendientes
    local messages=$(get_pending_messages "$channel_filter" 100)

    if [ -z "$messages" ]; then
        debug "No hay mensajes pendientes en la cola"
        return 0
    fi

    local message_count
    message_count=$(printf '%s\n' "$messages" | wc -l | tr -d ' ')
    debug "Procesando ${message_count} mensajes pendientes..."

    while IFS="|" read -r id contact_id channel message encrypted priority attempts; do
        # Saltar encabezado
        if [[ "$id" == "id" ]]; then
            continue
        fi

        # Actualizar estado a processing
        update_message_status "$id" "processing" "$encrypted"

        debug "Procesando mensaje $id para $contact_id via $channel (prioridad: $priority)"

        # Obtener información del contacto
        local contact_name=$(jq -r --arg id "$contact_id" '.contacts[$id].name // "Unknown"' "$CONTACTS_FILE")
        local contact_phone=$(jq -r --arg id "$contact_id" '.contacts[$id].phone // empty' "$CONTACTS_FILE")
        local contact_telegram=$(jq -r --arg id "$contact_id" '.contacts[$id].telegram_chat_id // empty' "$CONTACTS_FILE")
        local contact_sip=$(jq -r --arg id "$contact_id" '.contacts[$id].sip_address // empty' "$CONTACTS_FILE")

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

        # Intentar enviar
        local send_function="send_${channel}"
        if declare -f "$send_function" >/dev/null; then
            # Descifrar mensaje si es necesario
            local final_message="$message"
            if [ -n "$encrypted" ] && [ "$encrypted" != "no_encrypt" ]; then
                final_message=$(decrypt_message "$encrypted" "$contact_id")
                if [ $? -ne 0 ]; then
                    error "Error descifrando mensaje para $contact_id"
                    update_message_status "$id" "failed"
                    continue
                fi
            fi

            # Llamar a la función de envío
            "$send_function" "$destination" "$final_message" "no_encrypt"

            if [ $? -eq 0 ]; then
                update_message_status "$id" "sent" "$encrypted"
                info "Mensaje $id enviado a $contact_name via $channel"
            else
                # Verificar si se ha excedido el número de intentos
                local max_attempts=$(sqlite3 "$QUEUE_DB" "SELECT attempts FROM messages WHERE id = $id;")
                if [ "$max_attempts" -ge "$RETRY_ATTEMPTS" ]; then
                    update_message_status "$id" "failed"
                    error "Mensaje $id falló después de $max_attempts intentos"
                else
                    update_message_status "$id" "pending"
                fi
            fi
        else
            error "Función de envío no encontrada para el canal $channel"
            update_message_status "$id" "failed"
        fi
    done <<< "$messages"

    return 0
}

# Limpiar cola
clean_queue() {
    local days=${1:-30}

    # Eliminar mensajes enviados antiguos
    sqlite3 "$QUEUE_DB" "DELETE FROM messages WHERE status = 'sent' AND timestamp < datetime('now', '-$days days');"

    # Eliminar mensajes fallidos con muchos intentos
    sqlite3 "$QUEUE_DB" "DELETE FROM messages WHERE status = 'failed' AND attempts >= $RETRY_ATTEMPTS;"

    debug "Cola limpiada (mensajes de más de $days días o fallidos)"
}

# Contar mensajes por estado
count_messages() {
    local status="$1"
    sqlite3 "$QUEUE_DB" "SELECT COUNT(*) FROM messages WHERE status = '$status';"
}

# Inicializar
init_queue
