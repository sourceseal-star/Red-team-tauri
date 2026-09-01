#!/bin/bash
# utils/location.sh - Utilidades de Ubicación para COM-LINK v3.0

# ============================================================
# CONFIGURACIÓN
# ============================================================
# Base de datos de ciudades (simplificada)
CITIES_DB="$DATA_DIR/cities.db"

# ============================================================
# FUNCIONES
# ============================================================
# Obtener ubicación GPS
get_gps_location() {
    local timeout="${1:-10}"
    local location_data

    info "Obteniendo ubicación GPS..."

    location_data=$(timeout "$timeout" termux-location 2>/dev/null)

    if [ -z "$location_data" ]; then
        error "No se pudo obtener la ubicación GPS"
        return 1
    fi

    echo "$location_data"
    return 0
}

# Formatear ubicación para mensaje
format_location() {
    local location_data="$1"
    local include_map="${2:-true}"

    local lat=$(echo "$location_data" | jq -r '.latitude // "N/A"')
    local lon=$(echo "$location_data" | jq -r '.longitude // "N/A"')
    local accuracy=$(echo "$location_data" | jq -r '.accuracy // "N/A"')
    local altitude=$(echo "$location_data" | jq -r '.altitude // "N/A"')
    local speed=$(echo "$location_data" | jq -r '.speed // "N/A"')
    local provider=$(echo "$location_data" | jq -r '.provider // "N/A"')
    local timestamp=$(echo "$location_data" | jq -r '.time // "N/A"')

    local formatted="📍 Ubicación:
🌍 Latitud: $lat
🌎 Longitud: $lon
📏 Precisión: ${accuracy}m
🏔️  Altitud: ${altitude}m
🚀 Velocidad: ${speed}m/s
📱 Proveedor: $provider
🕒 Fecha: $timestamp"

    # Añadir geocodificación si está disponible
    local city=$(geocode "$lat" "$lon")
    if [ -n "$city" ]; then
        formatted+="
🏙️  Ciudad: $city"
    fi

    if [ "$include_map" = "true" ]; then
        formatted+="

🗺️ Mapa: https://www.google.com/maps?q=$lat,$lon"
    fi

    echo "$formatted"
    return 0
}

# Geocodificación offline (simplificada)
geocode() {
    local lat="$1"
    local lon="$2"

    # Verificar si la base de datos existe
    if [ ! -f "$CITIES_DB" ]; then
        create_cities_db
    fi

    # Buscar la ciudad más cercana por distancia euclidiana aproximada. No
    # devuelve una ciudad aleatoria: si la base es pequeña, el resultado sigue
    # siendo orientativo y se etiqueta como tal en la documentación.
    if ! [[ "$lat" =~ ^-?[0-9]+([.][0-9]+)?$ ]] || \
       ! [[ "$lon" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
        return 0
    fi
    local city
    city=$(sqlite3 "$CITIES_DB" \
        "SELECT name FROM cities ORDER BY ((lat - $lat) * (lat - $lat) + (lon - $lon) * (lon - $lon)) LIMIT 1;")

    echo "$city"
    return 0
}

# Crear base de datos de ciudades (simplificada)
create_cities_db() {
    info "Creando base de datos de ciudades..."

    sqlite3 "$CITIES_DB" <<EOF
CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    lat REAL,
    lon REAL,
    country TEXT
);

-- Insertar algunas ciudades importantes
INSERT OR IGNORE INTO cities (name, lat, lon, country) VALUES
    ('Bogotá', 4.7110, -74.0721, 'Colombia'),
    ('Medellín', 6.2442, -75.5812, 'Colombia'),
    ('Cali', 3.4372, -76.5225, 'Colombia'),
    ('Barranquilla', 10.9685, -74.7806, 'Colombia'),
    ('Cartagena', 10.4055, -75.5150, 'Colombia'),
    ('Lima', -12.0464, -77.0428, 'Perú'),
    ('Quito', -0.1807, -78.4678, 'Ecuador'),
    ('Caracas', 10.5050, -66.9140, 'Venezuela'),
    ('Panamá', 8.9840, -79.5199, 'Panamá'),
    ('Buenos Aires', -34.6037, -58.3816, 'Argentina');
EOF

    success "Base de datos de ciudades creada"
    return 0
}

# Obtener ubicación con geocodificación
get_location_with_geocode() {
    local location_data=$(get_gps_location)
    if [ $? -ne 0 ]; then
        return 1
    fi

    format_location "$location_data"
    return 0
}

# Enviar ubicación
send_location() {
    local contact_id="$1"
    local method="${2:-auto}"

    if [ -z "$contact_id" ]; then
        error "Debes especificar un contacto"
        return 1
    fi

    # Obtener ubicación
    local location_data=$(get_gps_location)
    if [ $? -ne 0 ]; then
        error "No se pudo obtener la ubicación"
        return 1
    fi

    # Formatear ubicación
    local formatted_location=$(format_location "$location_data" "false")

    # Obtener información del contacto
    local contact_name=$(jq -r --arg id "$contact_id" '.contacts[$id].name // "Unknown"' "$CONTACTS_FILE")
    local contact_phone=$(jq -r --arg id "$contact_id" '.contacts[$id].phone // empty' "$CONTACTS_FILE")
    local contact_telegram=$(jq -r --arg id "$contact_id" '.contacts[$id].telegram_chat_id // empty' "$CONTACTS_FILE")

    # Determinar método de envío
    if [ "$method" = "auto" ]; then
        # Usar fallback automático
        send_with_fallback "$contact_id" "$formatted_location" "location"
    else
        # Enviar según el método especificado
        case $method in
            "sms")
                if [ -n "$contact_phone" ]; then
                    send_sms "$contact_phone" "$formatted_location" ""
                else
                    error "El contacto $contact_id no tiene número de teléfono configurado"
                    return 1
                fi
                ;;
            "telegram")
                if [ -n "$contact_telegram" ]; then
                    send_telegram "$contact_telegram" "$formatted_location" ""
                else
                    error "El contacto $contact_id no tiene chat ID de Telegram configurado"
                    return 1
                fi
                ;;
            *)
                error "Método no válido: $method"
                return 1
                ;;
        esac
    fi

    # Abrir en Google Maps si hay conexión a internet
    if check_internet; then
        local lat=$(echo "$location_data" | jq -r '.latitude')
        local lon=$(echo "$location_data" | jq -r '.longitude')
        info "Abrir en Google Maps: https://www.google.com/maps?q=$lat,$lon"
        termux-open "https://www.google.com/maps?q=$lat,$lon" 2>/dev/null || \
        am start -a android.intent.action.VIEW -d "https://www.google.com/maps?q=$lat,$lon" 2>/dev/null || \
        xdg-open "https://www.google.com/maps?q=$lat,$lon" 2>/dev/null
    fi

    success "Ubicación enviada a $contact_name"
    return 0
}

# Menú de ubicación
location_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  📍 UBICACIÓN\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Obtener ubicación actual"
    echo "2️⃣  Enviar ubicación a contacto"
    echo "3️⃣  Configurar geocodificación"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            local location_data=$(get_gps_location)
            if [ $? -eq 0 ]; then
                format_location "$location_data"
            fi
            ;;
        2)
            # Mostrar contactos
            echo ""
            echo "📋 Contactos configurados:"
            jq -r '.contacts | to_entries[] | "  \(.key): \(.value.name)"' "$CONTACTS_FILE"

            read -p "👤 Contacto: " contact_id
            if [ -z "$contact_id" ]; then
                error "Debes especificar un contacto"
                return
            fi

            read -p "📤 Método (auto/sms/telegram, default: auto): " method
            send_location "$contact_id" "${method:-auto}"
            ;;
        3)
            create_cities_db
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    location_menu
}

# Punto de entrada: no ejecutar el menú cuando el módulo se carga con source.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    if [ $# -eq 0 ]; then
        location_menu
    else
        case "$1" in
            "get") get_location_with_geocode ;;
            "send")
                shift
                send_location "$@"
                ;;
            *) error "Comando no válido" ;;
        esac
    fi
fi
