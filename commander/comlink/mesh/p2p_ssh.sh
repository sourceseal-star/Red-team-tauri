#!/bin/bash
# mesh/p2p_ssh.sh - Comunicación SSH P2P para COM-LINK v3.0

# ============================================================
# FUNCIONES
# ============================================================
# Iniciar servidor SSH P2P
start_p2p_ssh_server() {
    local port="${1:-2222}"

    if ! command -v sshd &>/dev/null; then
        error "sshd no está instalado"
        info "Instálalo con: pkg install openssh"
        return 1
    fi

    info "Iniciando servidor SSH P2P en el puerto $port..."

    # Configurar SSH
    local ssh_dir="$HOME/.ssh"
    mkdir -p "$ssh_dir"
    chmod 700 "$ssh_dir"

    # Generar clave si no existe
    if [ ! -f "$ssh_dir/id_rsa" ]; then
        ssh-keygen -t rsa -b "$KEY_LENGTH" -f "$ssh_dir/id_rsa" -N "" -q
    fi

    # Configurar autorización (permitir todas las claves por ahora)
    cat "$ssh_dir/id_rsa.pub" > "$ssh_dir/authorized_keys" 2>/dev/null
    chmod 600 "$ssh_dir/authorized_keys"

    # Configurar sshd
    local sshd_config="$TEMP_DIR/sshd_config_p2p"
    cat > "$sshd_config" <<EOF
Port $port
ListenAddress 0.0.0.0
HostKey $ssh_dir/id_rsa
AuthorizedKeysFile $ssh_dir/authorized_keys
PasswordAuthentication no
PermitRootLogin no
AllowUsers $(whoami)
EOF

    # Iniciar sshd
    sshd -f "$sshd_config" -D -e 2>/dev/null &

    local pid=$!
    echo "$pid" > "$DATA_DIR/p2p_ssh_server.pid"
    info "Servidor SSH P2P iniciado en el puerto $port (PID: $pid)"
    info "IP: $(get_local_ip)"
    info "Usuario: $(whoami)"
    info "Clave pública: $(cat "$ssh_dir/id_rsa.pub")"

    # Crear script para manejar conexiones entrantes
    cat > "$TEMP_DIR/ssh_handler.sh" <<'EOS'
#!/bin/bash
while true; do
    # Verificar si hay nuevas conexiones
    if [ -f "$HOME/.ssh/connection_log" ]; then
        # Procesar log de conexiones
        tail -n 1 "$HOME/.ssh/connection_log" | while read -r line; do
            if [[ "$line" == *"Accepted"* ]]; then
                local ip=$(echo "$line" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n 1)
                info "Nueva conexión SSH desde $ip"
            fi
        done
    fi
    sleep 1
done
EOS

    chmod +x "$TEMP_DIR/ssh_handler.sh"
    "$TEMP_DIR/ssh_handler.sh" > "$TEMP_DIR/ssh_handler.log" 2>&1 &

    return 0
}

# Detener servidor SSH P2P
stop_p2p_ssh_server() {
    if [ -f "$DATA_DIR/p2p_ssh_server.pid" ]; then
        local pid=$(cat "$DATA_DIR/p2p_ssh_server.pid")
        kill "$pid" 2>/dev/null
        rm -f "$DATA_DIR/p2p_ssh_server.pid" "$TEMP_DIR/sshd_config_p2p" "$TEMP_DIR/ssh_handler.sh" "$TEMP_DIR/ssh_handler.log" "$HOME/.ssh/connection_log"
        info "Servidor SSH P2P detenido"
        return 0
    else
        info "No hay servidor SSH P2P en ejecución"
        return 1
    fi
}

# Conectar a dispositivo via SSH P2P
connect_p2p_ssh() {
    local destination="$1"

    if [ -z "$destination" ]; then
        error "Debes especificar un destino"
        return 1
    fi

    info "Conectando a $destination via SSH P2P..."

    # Si es una IP, conectar directamente
    if [[ "$destination" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        ssh -p 2222 -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" "$(whoami)@$destination"
        return $?
    else
        # Buscar el dispositivo en la red local
        local target_ip=$(discover_devices | grep "$destination" | awk '{print $1}' | head -n 1)

        if [ -n "$target_ip" ]; then
            ssh -p 2222 -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" "$(whoami)@$target_ip"
            return $?
        else
            error "Dispositivo $destination no encontrado"
            return 1
        fi
    fi
}

# Enviar archivo via SSH P2P
send_p2p_ssh_file() {
    local destination="$1"
    local file_path="$2"

    if [ -z "$destination" ] || [ -z "$file_path" ]; then
        error "Destino y archivo no pueden estar vacíos"
        return 1
    fi

    if [ ! -f "$file_path" ]; then
        error "Archivo no encontrado: $file_path"
        return 1
    fi

    info "Enviando archivo $file_path a $destination via SSH P2P..."

    # Si es una IP, enviar directamente
    if [[ "$destination" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        scp -P 2222 -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" "$file_path" "$(whoami)@$destination:~/"
        return $?
    else
        # Buscar el dispositivo en la red local
        local target_ip=$(discover_devices | grep "$destination" | awk '{print $1}' | head -n 1)

        if [ -n "$target_ip" ]; then
            scp -P 2222 -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" "$file_path" "$(whoami)@$target_ip:~/"
            return $?
        else
            error "Dispositivo $destination no encontrado"
            return 1
        fi
    fi
}

# Menú de SSH P2P
p2p_ssh_menu() {
    clear
    echo -e "\033[1;34m====================================\033[0m"
    echo -e "\033[1;34m  🔌 SSH P2P\033[0m"
    echo -e "\033[1;34m====================================\033[0m"
    echo ""

    echo "1️⃣  Iniciar servidor SSH P2P"
    echo "2️⃣  Detener servidor SSH P2P"
    echo "3️⃣  Conectar a dispositivo"
    echo "4️⃣  Enviar archivo"
    echo "5️⃣  Ver clave pública"
    echo "0️⃣  Volver"

    read -p "👉 Selecciona una opción: " choice

    case $choice in
        1)
            read -p "🌐 Puerto (default: 2222): " port
            start_p2p_ssh_server "${port:-2222}"
            ;;
        2)
            stop_p2p_ssh_server
            ;;
        3)
            read -p "📡 Destino (IP o nombre): " destination
            connect_p2p_ssh "$destination"
            ;;
        4)
            read -p "📡 Destino (IP o nombre): " destination
            read -p "📁 Archivo: " file_path
            send_p2p_ssh_file "$destination" "$file_path"
            ;;
        5)
            info "Clave pública SSH:"
            echo "-----BEGIN PUBLIC KEY-----"
            cat "$HOME/.ssh/id_rsa.pub" 2>/dev/null
            echo "-----END PUBLIC KEY-----"
            read -p "Presiona Enter para continuar..." _ 2>/dev/null
            ;;
        0) return ;;
        *) error "Opción no válida" ;;
    esac

    read -p "Presiona Enter para continuar..." _ 2>/dev/null
    p2p_ssh_menu
}
