#!/bin/bash
# channels/mesh_wifi.sh - Comunicación Mesh WiFi para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Enviar mensaje via Mesh WiFi
send_mesh_wifi() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Verificar si hay conexión WiFi
    if ! check_wifi; then
        error "No hay conexión WiFi para Mesh"
        return 1
    fi

    # Si el destino es una IP, intentar enviar via HTTP
    if [[ "$destination" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        info "Enviando mensaje a $destination via HTTP..."

        # Cifrar mensaje si es necesario
        local final_message="$message"
        if [ "$ENCRYPTION_ENABLED" = "true" ] && [ -z "$encrypted" ]; then
            final_message=$(encrypt_message "$message" "$destination")
            if [ $? -ne 0 ]; then
                error "Error cifrando mensaje"
                return 1
            fi
        fi

        # Enviar via HTTP POST
        local response=$(curl -s -X POST "http://$destination:$MESH_WIFI_PORT/upload" \
            -H "Content-Type: application/json" \
            -H "X-COM-LINK: $DEVICE_ID" \
            -d "{\"message\": \"$final_message\", \"from\": \"$(get_local_ip)\", \"encrypted\": \"${encrypted:-false}\"}" 2>&1)

        if [ $? -eq 0 ]; then
            success "Mensaje enviado a $destination via Mesh WiFi"
            return 0
        else
            error "Error enviando mensaje via HTTP: $response"
            return 1
        fi
    else
        # Buscar el dispositivo en la red local
        info "Buscando dispositivo $destination en la red local..."
        local target_ip=$(discover_devices | grep "$destination" | awk '{print $1}' | head -n 1)

        if [ -n "$target_ip" ]; then
            send_mesh_wifi "$target_ip" "$message" "$encrypted"
            return $?
        else
            error "Dispositivo $destination no encontrado en la red local"
            return 1
        fi
    fi
}

# Descubrir dispositivos en la red local
discover_devices() {
    local output_file="$TEMP_DIR/discovery_$(date +%s).txt"
    local scan_output

    info "Escaneando red local en busca de dispositivos COM-LINK..."

    # Escanear puertos comunes de COM-LINK
    local ports=($MESH_WIFI_PORT 22 80 443)
    local network=$(get_network_range)

    for port in "${ports[@]}"; do
        # Usar nmap si está disponible
        if command -v nmap &>/dev/null; then
            scan_output=$(nmap -p "$port" --open "$network" -oG - 2>/dev/null)
        else
            # Usar ping + nc si nmap no está disponible
            scan_output=$(timeout 5 bash -c "for ip in \$(seq 1 254); do ping -c 1 -W 1 $network\$ip >/dev/null 2>&1 && echo \"$network\$ip $port open\"; done" 2>/dev/null)
        fi

        echo "$scan_output" >> "$output_file"
    done

    # Procesar resultados
    if [ -f "$output_file" ]; then
        # Buscar dispositivos COM-LINK
        grep -E "open" "$output_file" | while read -r line; do
            local ip=$(echo "$line" | awk '{print $2}')
            local port=$(echo "$line" | grep -oE '[0-9]+$' | head -n 1)

            # Verificar si es un dispositivo COM-LINK
            local is_comlink=$(curl -s -I "http://$ip:$MESH_WIFI_PORT" | grep -i "COM-LINK" || \
                             nc -z -w 1 "$ip" "$MESH_WIFI_PORT" 2>/dev/null && echo "COM-LINK")

            if [ -n "$is_comlink" ]; then
                # Obtener información del dispositivo
                local device_info=$(curl -s "http://$ip:$MESH_WIFI_PORT/device_info" 2>/dev/null)
                local device_name=$(echo "$device_info" | jq -r '.name // "Unknown"' 2>/dev/null)
                local device_id=$(echo "$device_info" | jq -r '.id // "Unknown"' 2>/dev/null)

                echo "$ip $device_name ($device_id)"
            fi
        done

        rm -f "$output_file"
    fi
}

# Obtener rango de red
get_network_range() {
    local ip=$(get_local_ip)
    if [[ "$ip" =~ ^192\.168\. ]]; then
        echo "192.168.${ip##*.}."
    elif [[ "$ip" =~ ^10\. ]]; then
        echo "10.0.${ip##*.}."
    elif [[ "$ip" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
        echo "172.${ip%%.*}."
    else
        echo "192.168.1."
    fi
}

# Iniciar servidor HTTP para Mesh
start_mesh_http_server() {
    local port="${1:-$MESH_WIFI_PORT}"

    info "Iniciando servidor HTTP para Mesh en el puerto $port..."

    # Crear script de servidor
    cat > "$TEMP_DIR/mesh_http_server.py" <<EOF
import http.server
import socketserver
import json
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PORT = $port
DATA_DIR = "$DATA_DIR"
TEMP_DIR = "$TEMP_DIR"

class MeshHTTPHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suprimir logs por defecto
        pass

    def do_GET(self):
        if self.path == "/device_info":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            device_info = {
                "name": "$DEVICE_NAME",
                "id": "$DEVICE_ID",
                "ip": "$(get_local_ip)",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "comlink_version": "$COM_LINK_VERSION"
            }
            self.wfile.write(json.dumps(device_info).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/upload":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            # Guardar mensaje recibido
            timestamp = datetime.utcnow().isoformat() + "Z"
            message_file = os.path.join(DATA_DIR, "received", f"message_{timestamp}.json")
            os.makedirs(os.path.dirname(message_file), exist_ok=True)

            with open(message_file, "w") as f:
                json.dump(data, f)

            # Responder
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "received", "timestamp": timestamp}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_error(404)

with socketserver.TCPServer(("", PORT), MeshHTTPHandler) as httpd:
    print(f"Servidor HTTP Mesh iniciado en el puerto {PORT}")
    print(f"URL: http://$(get_local_ip):{PORT}")
    httpd.serve_forever()
EOF

    # Iniciar servidor en segundo plano
    python3 "$TEMP_DIR/mesh_http_server.py" > "$TEMP_DIR/mesh_http_server.log" 2>&1 &

    local pid=$!
    echo "$pid" > "$DATA_DIR/mesh_http_server.pid"
    info "Servidor HTTP Mesh iniciado (PID: $pid)"
    info "URL: http://$(get_local_ip):$port"

    return 0
}

# Detener servidor HTTP Mesh
stop_mesh_http_server() {
    if [ -f "$DATA_DIR/mesh_http_server.pid" ]; then
        local pid=$(cat "$DATA_DIR/mesh_http_server.pid")
        kill "$pid" 2>/dev/null
        rm -f "$DATA_DIR/mesh_http_server.pid" "$TEMP_DIR/mesh_http_server.py" "$TEMP_DIR/mesh_http_server.log"
        info "Servidor HTTP Mesh detenido"
        return 0
    else
        info "No hay servidor HTTP Mesh en ejecución"
        return 1
    fi
}

# Iniciar servidor SSH para Mesh
start_mesh_ssh_server() {
    if ! command -v sshd &>/dev/null; then
        error "sshd no está instalado"
        info "Instálalo con: pkg install openssh"
        return 1
    fi

    info "Iniciando servidor SSH para Mesh..."

    # Configurar SSH
    local ssh_dir="$HOME/.ssh"
    mkdir -p "$ssh_dir"
    chmod 700 "$ssh_dir"

    # Generar clave si no existe
    if [ ! -f "$ssh_dir/id_rsa" ]; then
        ssh-keygen -t rsa -f "$ssh_dir/id_rsa" -N "" -q
    fi

    # Configurar autorización
    cat "$ssh_dir/id_rsa.pub" >> "$ssh_dir/authorized_keys" 2>/dev/null
    chmod 600 "$ssh_dir/authorized_keys"

    # Configurar sshd
    local sshd_config="$TEMP_DIR/sshd_config"
    cat > "$sshd_config" <<EOF
Port 2222
ListenAddress 0.0.0.0
HostKey $ssh_dir/id_rsa
AuthorizedKeysFile $ssh_dir/authorized_keys
PasswordAuthentication no
PermitRootLogin no
EOF

    # Iniciar sshd
    sshd -f "$sshd_config" -D -e 2>/dev/null &

    local pid=$!
    echo "$pid" > "$DATA_DIR/mesh_ssh_server.pid"
    info "Servidor SSH Mesh iniciado en el puerto 2222 (PID: $pid)"
    info "IP: $(get_local_ip)"
    info "Usuario: $(whoami)"
    info "Clave pública: $(cat "$ssh_dir/id_rsa.pub")"

    return 0
}

# Detener servidor SSH Mesh
stop_mesh_ssh_server() {
    if [ -f "$DATA_DIR/mesh_ssh_server.pid" ]; then
        local pid=$(cat "$DATA_DIR/mesh_ssh_server.pid")
        kill "$pid" 2>/dev/null
        rm -f "$DATA_DIR/mesh_ssh_server.pid" "$TEMP_DIR/sshd_config"
        info "Servidor SSH Mesh detenido"
        return 0
    else
        info "No hay servidor SSH Mesh en ejecución"
        return 1
    fi
}

# Conectar a dispositivo Mesh via SSH
connect_mesh_ssh() {
    local destination="$1"

    if [ -z "$destination" ]; then
        error "Debes especificar un destino"
        return 1
    fi

    info "Conectando a $destination via SSH Mesh..."

    # Si es una IP, conectar directamente
    if [[ "$destination" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        ssh -p 2222 "$(whoami)@$destination" 2>/dev/null
        return $?
    else
        # Buscar el dispositivo en la red local
        local target_ip=$(discover_devices | grep "$destination" | awk '{print $1}' | head -n 1)

        if [ -n "$target_ip" ]; then
            ssh -p 2222 "$(whoami)@$target_ip" 2>/dev/null
            return $?
        else
            error "Dispositivo $destination no encontrado"
            return 1
        fi
    fi
}

# Menú de Mesh WiFi
mesh_wifi_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🌐 MESH WIFI\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    # Obtener información de la red
    get_network_info

    echo ""
    echo "1️⃣  Escanear dispositivos en la red"
    echo "2️⃣  Enviar mensaje"
    echo "3️⃣  Iniciar servidor HTTP"
    echo "4️⃣  Detener servidor HTTP"
    echo "5️⃣  Iniciar servidor SSH"
    echo "6️⃣  Detener servidor SSH"
    echo "7️⃣  Conectar via SSH"
    echo "8️⃣  Configurar Mesh WiFi"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            info "Escaneando dispositivos..."
            discover_devices
            ;;
        2)
            read -p "📡 Destino (IP o nombre): " destination
            if [ -z "$destination" ]; then
                error "Debes especificar un destino"
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

            send_mesh_wifi "$destination" "$message" "$encrypt"
            ;;
        3)
            read -p "🌐 Puerto (default: $MESH_WIFI_PORT): " port
            start_mesh_http_server "${port:-$MESH_WIFI_PORT}"
            ;;
        4)
            stop_mesh_http_server
            ;;
        5)
            start_mesh_ssh_server
            ;;
        6)
            stop_mesh_ssh_server
            ;;
        7)
            read -p "📡 Destino (IP o nombre): " destination
            connect_mesh_ssh "$destination"
            ;;
        8)
            read -p "📡 SSID (default: $MESH_WIFI_SSID): " ssid
            read -p "🔑 Contraseña (default: $MESH_WIFI_PASSWORD): " password
            read -p "🌐 Puerto (default: $MESH_WIFI_PORT): " port

            [ -n "$ssid" ] && MESH_WIFI_SSID="$ssid"
            [ -n "$password" ] && MESH_WIFI_PASSWORD="$password"
            [ -n "$port" ] && MESH_WIFI_PORT="$port"

            save_config
            success "Configuración de Mesh WiFi actualizada"
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    mesh_wifi_menu
}
