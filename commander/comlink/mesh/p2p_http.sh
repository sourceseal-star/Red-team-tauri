#!/bin/bash
# mesh/p2p_http.sh - Comunicación HTTP P2P para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Iniciar servidor HTTP P2P
start_p2p_http_server() {
    local port="${1:-$MESH_WIFI_PORT}"

    info "Iniciando servidor HTTP P2P en el puerto $port..."

    # Crear script de servidor
    cat > "$TEMP_DIR/p2p_http_server.py" <<EOF
import http.server
import socketserver
import json
import os
import threading
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PORT = $port
DATA_DIR = "$DATA_DIR"
INSTALL_DIR = "$INSTALL_DIR"
TEMP_DIR = "$TEMP_DIR"
DEVICE_NAME = "$DEVICE_NAME"
DEVICE_ID = "$DEVICE_ID"

# Lista de mensajes recibidos
received_messages = []
message_lock = threading.Lock()

class P2PHTTPHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suprimir logs por defecto
        pass

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>COM-LINK P2P - {DEVICE_NAME}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h1 {{ color: #2c3e50; }}
                    .message {{ background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                    .info {{ background: #e3f2fd; }}
                    .success {{ background: #d4edda; }}
                    .error {{ background: #f8d7da; }}
                </style>
            </head>
            <body>
                <h1>📡 COM-LINK P2P</h1>
                <p>Dispositivo: {DEVICE_NAME} ({DEVICE_ID})</p>
                <p>IP: {self.get_local_ip()}</p>
                <p>Puerto: {PORT}</p>

                <h2>Enviar Mensaje</h2>
                <form action="/send" method="post">
                    <textarea name="message" rows="4" cols="50" placeholder="Escribe tu mensaje aquí..."></textarea><br>
                    <input type="text" name="destination" placeholder="IP o nombre del destino"><br>
                    <button type="submit">Enviar</button>
                </form>

                <h2>Mensajes Recibidos</h2>
                <div id="messages">
            """

            with message_lock:
                for msg in received_messages[-10:]:  # Mostrar últimos 10 mensajes
                    html += f'<div class="message {msg.get("type", "info")}"><strong>{msg.get("from", "Unknown")}</strong> ({msg.get("timestamp", "")}): {msg.get("message", "")}</div>'

            html += """
                </div>

                <h2>Dispositivos Cercanos</h2>
                <div id="devices">
            """

            # Obtener dispositivos cercanos
            try:
                import subprocess
                result = subprocess.run(["$INSTALL_DIR/mesh/discovery.sh", "list"],
                                      capture_output=True, text=True, timeout=5)
                devices = result.stdout.strip().split('\\n')
                for device in devices:
                    if device:
                        html += f'<div class="message info">{device}</div>'
            except:
                pass

            html += """
                </div>

                <script>
                    // Actualizar cada 5 segundos
                    setInterval(function() {
                        location.reload();
                    }, 5000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())

        elif self.path == "/device_info":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            device_info = {
                "name": DEVICE_NAME,
                "id": DEVICE_ID,
                "ip": self.get_local_ip(),
                "port": PORT,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "comlink_version": "$COM_LINK_VERSION"
            }
            self.wfile.write(json.dumps(device_info).encode())

        elif self.path == "/messages":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            with message_lock:
                self.wfile.write(json.dumps(received_messages[-50:]).encode())  # Últimos 50 mensajes

        elif self.path.startswith("/download/"):
            # Servir archivos
            file_path = os.path.join(DATA_DIR, "received", self.path[10:])
            if os.path.exists(file_path):
                self.send_response(200)
                self.send_header("Content-type", "application/octet-stream")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)

        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/send":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = parse_qs(post_data.decode())

            message = data.get("message", [""])[0]
            destination = data.get("destination", [""])[0]

            if not message:
                self.send_error(400, "Mensaje vacío")
                return

            # Guardar mensaje para enviar
            with message_lock:
                received_messages.append({
                    "from": self.client_address[0],
                    "message": message,
                    "destination": destination,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "type": "info"
                })

            # Intentar enviar el mensaje
            try:
                import subprocess
                cmd = ["$INSTALL_DIR/comlink.sh", "mesh_wifi", destination, message]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "queued", "message": "Mensaje en cola para envío"}
            self.wfile.write(json.dumps(response).encode())

        elif self.path == "/upload":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            # Guardar mensaje recibido
            with message_lock:
                received_messages.append({
                    "from": data.get("from", self.client_address[0]),
                    "message": data.get("message", ""),
                    "timestamp": data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                    "type": "success"
                })

            # Guardar en archivo
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            message_file = os.path.join(DATA_DIR, "received", f"message_{timestamp}.json")
            os.makedirs(os.path.dirname(message_file), exist_ok=True)
            with open(message_file, "w") as f:
                json.dump(data, f)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "received", "timestamp": datetime.utcnow().isoformat() + "Z"}
            self.wfile.write(json.dumps(response).encode())

        else:
            self.send_error(404)

    def get_local_ip(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

# Iniciar servidor
with socketserver.TCPServer(("", PORT), P2PHTTPHandler) as httpd:
    print(f"Servidor HTTP P2P iniciado en el puerto {PORT}")
    print(f"URL: http://{socket.gethostbyname(socket.gethostname())}:{PORT}")
    httpd.serve_forever()
EOF

    # Iniciar servidor en segundo plano
    python3 "$TEMP_DIR/p2p_http_server.py" > "$TEMP_DIR/p2p_http_server.log" 2>&1 &

    local pid=$!
    echo "$pid" > "$DATA_DIR/p2p_http_server.pid"
    info "Servidor HTTP P2P iniciado (PID: $pid)"
    info "URL: http://$(get_local_ip):$port"

    return 0
}

# Detener servidor HTTP P2P
stop_p2p_http_server() {
    if [ -f "$DATA_DIR/p2p_http_server.pid" ]; then
        local pid=$(cat "$DATA_DIR/p2p_http_server.pid")
        kill "$pid" 2>/dev/null
        rm -f "$DATA_DIR/p2p_http_server.pid" "$TEMP_DIR/p2p_http_server.py" "$TEMP_DIR/p2p_http_server.log"
        info "Servidor HTTP P2P detenido"
        return 0
    else
        info "No hay servidor HTTP P2P en ejecución"
        return 1
    fi
}

# Enviar mensaje via HTTP P2P
send_p2p_http() {
    local destination="$1"
    local message="$2"
    local encrypted="$3"

    # Verificar si hay conexión de red
    if ! check_internet && ! check_lan; then
        error "No hay conexión de red para HTTP P2P"
        return 1
    fi

    # Si el destino es una IP, enviar directamente
    if [[ "$destination" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        info "Enviando mensaje a $destination via HTTP P2P..."

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
            success "Mensaje enviado a $destination via HTTP P2P"
            return 0
        else
            error "Error enviando mensaje via HTTP P2P: $response"
            return 1
        fi
    else
        # Buscar el dispositivo en la red local
        info "Buscando dispositivo $destination en la red local..."
        local target_ip=$(discover_devices | grep "$destination" | awk '{print $1}' | head -n 1)

        if [ -n "$target_ip" ]; then
            send_p2p_http "$target_ip" "$message" "$encrypted"
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

    # Escanear puertos comunes
    local ports=($MESH_WIFI_PORT 80 443 8080 2222)
    local network=$(get_network_range)

    for port in "${ports[@]}"; do
        # Usar nmap si está disponible
        if command -v nmap &>/dev/null; then
            scan_output=$(nmap -p "$port" --open "$network" -oG - 2>/dev/null)
        else
            # Usar nc si nmap no está disponible
            scan_output=$(timeout 5 bash -c "for ip in \$(seq 1 254); do nc -z -w 1 $network\$ip $port 2>/dev/null && echo \"$network\$ip $port open\"; done" 2>/dev/null)
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
            local is_comlink=$(curl -s -I "http://$ip:$port" | grep -i "COM-LINK" || \
                             curl -s "http://$ip:$port/device_info" | jq -e '.comlink_version' >/dev/null 2>&1)

            if [ -n "$is_comlink" ]; then
                # Obtener información del dispositivo
                local device_info=$(curl -s "http://$ip:$port/device_info" 2>/dev/null)
                local device_name=$(echo "$device_info" | jq -r '.name // "Unknown"' 2>/dev/null)
                local device_id=$(echo "$device_info" | jq -r '.id // "Unknown"' 2>/dev/null)

                echo "$ip $device_name ($device_id) - Puerto: $port"
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
