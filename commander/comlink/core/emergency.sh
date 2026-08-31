#!/usr/bin/env bash
# core/emergency.sh - Alerta de emergencia multicanal COM-LINK
#
# El flujo es deliberadamente conservador:
# - nunca transmite sin --confirm;
# - solo intenta canales con destino explícito y adaptador local;
# - no degrada el cifrado a texto plano;
# - radio, satélite y llamadas SIP no se simulan ni se activan solos.

EMERGENCY_REPORT_FILE="$DATA_DIR/last_emergency.json"

emergency_add_result() {
    local channel="$1"
    local state="$2"
    local reason="$3"
    local destination="${4:-}"

    EMERGENCY_RESULTS=$(jq -c \
        --arg channel "$channel" \
        --arg state "$state" \
        --arg reason "$reason" \
        --arg destination "$destination" \
        '. + [{channel:$channel,state:$state,reason:$reason,destination:$destination}]' \
        <<<"${EMERGENCY_RESULTS:-[]}")
}

emergency_location_suffix() {
    local raw lat lon accuracy altitude provider
    EMERGENCY_LOCATION_NOTE="Ubicación no disponible en este dispositivo"

    if ! command -v termux-location >/dev/null 2>&1; then
        return 0
    fi

    raw=$(timeout 12 termux-location 2>/dev/null) || return 0
    if ! jq -e '.latitude != null and .longitude != null' >/dev/null 2>&1 <<<"$raw"; then
        return 0
    fi

    lat=$(jq -r '.latitude' <<<"$raw")
    lon=$(jq -r '.longitude' <<<"$raw")
    accuracy=$(jq -r '.accuracy // "N/D"' <<<"$raw")
    altitude=$(jq -r '.altitude // "N/D"' <<<"$raw")
    provider=$(jq -r '.provider // "N/D"' <<<"$raw")
    EMERGENCY_LOCATION_NOTE="GPS obtenido por $provider"

    cat <<EOF

📍 Ubicación:
Latitud: $lat
Longitud: $lon
Precisión: ${accuracy}m
Altitud: ${altitude}m
Mapa: https://www.google.com/maps?q=$lat,$lon
EOF
}

emergency_queue_failed() {
    local contact_id="$1"
    local channel="$2"
    local body="$3"
    local encrypted="$4"
    local queue_message="$body"
    local queue_encrypted=""

    if [ "$ENCRYPTION_ENABLED" = "true" ]; then
        if [ -z "$encrypted" ]; then
            return 1
        fi
        # El cuerpo queda vacío; process_queue descifra encrypted al reintentar.
        queue_message=""
        queue_encrypted="$encrypted"
    fi

    add_to_queue "$contact_id" "$channel" "$queue_message" "$queue_encrypted" 100 "emergency"
}

emergency_alert() {
    if [ "$#" -lt 2 ]; then
        error "Uso: comlink emergency <contacto> <mensaje> [--confirm] [--no-location] [--dry-run]"
        return 1
    fi

    local contact_id="$1"
    shift
    local confirm=false
    local dry_run=false
    local include_location=true
    local message_parts=()
    local option

    while [ "$#" -gt 0 ]; do
        option="$1"
        shift
        case "$option" in
            --confirm) confirm=true ;;
            --dry-run) dry_run=true ;;
            --no-location) include_location=false ;;
            --with-location) include_location=true ;;
            --) message_parts+=("$@"); break ;;
            *) message_parts+=("$option") ;;
        esac
    done

    local message="${message_parts[*]}"
    if [ -z "$message" ]; then
        error "El mensaje de emergencia no puede estar vacío"
        return 1
    fi
    if [ "$dry_run" != "true" ] && [ "$confirm" != "true" ]; then
        error "La alerta real requiere --confirm. Usa --dry-run para revisar el plan."
        return 1
    fi
    if ! jq -e --arg id "$contact_id" '(.contacts[$id] // .[$id]) != null' "$CONTACTS_FILE" >/dev/null 2>&1; then
        error "Contacto $contact_id no existe en $CONTACTS_FILE"
        return 1
    fi

    local contact_phone contact_telegram mesh_wifi_ip mesh_bluetooth_mac
    contact_phone=$(jq -r --arg id "$contact_id" '(.contacts[$id] // .[$id]).phone // empty' "$CONTACTS_FILE")
    contact_telegram=$(jq -r --arg id "$contact_id" '(.contacts[$id] // .[$id]).telegram_chat_id // empty' "$CONTACTS_FILE")
    mesh_wifi_ip=$(jq -r --arg id "$contact_id" '(.contacts[$id] // .[$id]).mesh_wifi_ip // (.contacts[$id] // .[$id]).mesh_wifi_endpoint // empty' "$CONTACTS_FILE")
    mesh_bluetooth_mac=$(jq -r --arg id "$contact_id" '(.contacts[$id] // .[$id]).mesh_bluetooth_mac // empty' "$CONTACTS_FILE")

    local body="$message"
    local location_note="omitida por el operador"
    if [ "$include_location" = "true" ]; then
        local location_text
        location_text=$(emergency_location_suffix)
        location_note="$EMERGENCY_LOCATION_NOTE"
        if [ -n "$location_text" ]; then
            body="${body}${location_text}"
        fi
    fi

    EMERGENCY_RESULTS="[]"
    local planned_channels=()
    local channel

    # Preparar solo destinos que el adaptador actual puede usar.
    if command -v termux-sms-send >/dev/null 2>&1 && [[ "$contact_phone" =~ ^\+[0-9]{8,15}$ ]]; then
        planned_channels+=("sms")
    else
        emergency_add_result "sms" "skipped" "Falta Termux:API o un teléfono válido" "$contact_phone"
    fi

    if [ -n "$TELEGRAM_BOT_TOKEN" ] && validate_telegram_chat_id "$contact_telegram"; then
        planned_channels+=("telegram")
    else
        emergency_add_result "telegram" "skipped" "Falta token o chat ID de Telegram" "$contact_telegram"
    fi

    if [ -n "$mesh_wifi_ip" ] && [[ "$mesh_wifi_ip" =~ ^[A-Za-z0-9._-]+$ ]]; then
        planned_channels+=("mesh_wifi")
    else
        emergency_add_result "mesh_wifi" "skipped" "El contacto no tiene mesh_wifi_ip/endpoint válido" "$mesh_wifi_ip"
    fi

    if command -v rfcomm >/dev/null 2>&1 && [[ "$mesh_bluetooth_mac" =~ ^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$ ]]; then
        planned_channels+=("mesh_bluetooth")
    else
        emergency_add_result "mesh_bluetooth" "skipped" "Falta RFCOMM o una MAC Bluetooth válida" "$mesh_bluetooth_mac"
    fi

    emergency_add_result "voip" "skipped" "SIP solo permite llamadas interactivas; no se autodialea" ""
    emergency_add_result "radio" "skipped" "Driver AX.25/TNC no verificado" ""
    emergency_add_result "satellite" "skipped" "Driver satelital específico no verificado" ""

    local report timestamp encrypted_payload=""
    timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    if [ "$dry_run" = "true" ]; then
        for channel in "${planned_channels[@]}"; do
            emergency_add_result "$channel" "planned" "Requisitos locales presentes; no se transmitió" ""
        done
    else
        if [ "$ENCRYPTION_ENABLED" = "true" ]; then
            encrypted_payload=$(encrypt_message "$body" "$contact_id")
            if [ $? -ne 0 ] || [ -z "$encrypted_payload" ]; then
                error "No hay una clave válida para cifrar la alerta; no se enviará en texto plano"
                emergency_add_result "all" "failed" "Falta clave de cifrado del contacto" ""
                planned_channels=()
            fi
        fi

        local sent_count=0
        local queued_count=0
        local destination send_ok
        for channel in "${planned_channels[@]}"; do
            destination=""
            case "$channel" in
                sms) destination="$contact_phone" ;;
                telegram) destination="$contact_telegram" ;;
                mesh_wifi) destination="$mesh_wifi_ip" ;;
                mesh_bluetooth) destination="$mesh_bluetooth_mac" ;;
            esac

            send_ok=false
            case "$channel" in
                sms) send_sms "$destination" "$body" "$encrypted_payload" && send_ok=true ;;
                telegram) send_telegram "$destination" "$body" "$encrypted_payload" && send_ok=true ;;
                mesh_wifi) send_mesh_wifi "$destination" "$body" "$encrypted_payload" && send_ok=true ;;
                mesh_bluetooth) send_mesh_bluetooth "$destination" "$body" "$encrypted_payload" && send_ok=true ;;
            esac

            if [ "$send_ok" = "true" ]; then
                emergency_add_result "$channel" "sent" "El adaptador devolvió éxito; entrega no confirmada" "$destination"
                sent_count=$((sent_count + 1))
            elif emergency_queue_failed "$contact_id" "$channel" "$body" "$encrypted_payload"; then
                emergency_add_result "$channel" "queued" "Falló el envío; queda en la cola persistente para reintento" "$destination"
                queued_count=$((queued_count + 1))
            else
                emergency_add_result "$channel" "failed" "Falló el envío y no se pudo encolar de forma segura" "$destination"
            fi
        done
    fi

    report=$(jq -cn \
        --arg timestamp "$timestamp" \
        --arg contact "$contact_id" \
        --arg location "$location_note" \
        --arg message_sha256 "$(printf '%s' "$body" | sha256sum | awk '{print $1}')" \
        --argjson results "$EMERGENCY_RESULTS" \
        '{timestamp:$timestamp,contact:$contact,location:$location,message_sha256:$message_sha256,results:$results}')

    if [ "$dry_run" != "true" ]; then
        printf '%s\n' "$report" > "$EMERGENCY_REPORT_FILE"
        chmod 600 "$EMERGENCY_REPORT_FILE"
    fi

    printf '%s\n' "$report"
    if [ "$dry_run" = "true" ]; then
        return 0
    fi
    if jq -e '[.results[] | select(.state == "sent" or .state == "queued")] | length > 0' <<<"$report" >/dev/null; then
        return 0
    fi
    return 1
}