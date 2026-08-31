#!/bin/bash
# install.sh - Instalador de COM-LINK v3.0

# ============================================================
# CONFIGURACIÓN
# ============================================================
INSTALL_DIR="$HOME/comlink"
BIN_DIR="$HOME/bin"
TERMUX_API_VERSION="50.1"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================
# FUNCIONES
# ============================================================
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Verificar Termux
check_termux() {
    if [ ! -d "$PREFIX" ]; then
        error "Este script solo funciona en Termux"
    fi
}

# Verificar permisos de root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        warning "No eres root. Algunas funciones pueden no estar disponibles."
    fi
}

# Instalar paquetes
install_packages() {
    info "Instalando dependencias básicas..."
    pkg update -y && pkg upgrade -y || error "Error al actualizar paquetes"
    pkg install -y \
        jq sqlite curl wget openssl termux-api \
        hcitool bluez rfcomm python \
        linphone asterisk sox libax25 || warning "Algunas dependencias no se instalaron"

    # Instalar pip packages
    pip install --upgrade pip || warning "pip no disponible"
    pip install pycryptodome requests pyzip || warning "Algunos paquetes Python no se instalaron"
}

# Crear estructura de directorios
create_structure() {
    info "Creando estructura de directorios..."
    mkdir -p "$INSTALL_DIR"/{core,channels,crypto,mesh,utils,data/{keys,logs,queue},scripts}
    mkdir -p "$BIN_DIR"
}

# Copiar archivos
copy_files() {
    info "Copiando archivos..."
    cp -r core/ channels/ crypto/ mesh/ utils/ scripts/ "$INSTALL_DIR"/ || error "Error al copiar archivos"
    cp comlink.sh install.sh README.md "$INSTALL_DIR"/ || error "Error al copiar archivos principales"
}

# Dar permisos
set_permissions() {
    info "Configurando permisos..."
    chmod -R +x "$INSTALL_DIR"/*.sh "$INSTALL_DIR"/core/*.sh "$INSTALL_DIR"/channels/*.sh \
    "$INSTALL_DIR"/crypto/*.sh "$INSTALL_DIR"/mesh/*.sh "$INSTALL_DIR"/utils/*.sh \
    "$INSTALL_DIR"/scripts/*.sh || error "Error al configurar permisos"
}

# Crear enlace simbólico
create_symlink() {
    info "Creando enlace simbólico..."
    ln -sf "$INSTALL_DIR/comlink.sh" "$BIN_DIR/comlink" || warning "No se pudo crear el enlace simbólico"
}

# Configurar Termux API
configure_termux_api() {
    info "Configurando Termux:API..."
    local current_version=$(pkg show termux-api | grep Version | awk '{print $2}')
    if [ "$current_version" != "$TERMUX_API_VERSION" ]; then
        pkg install -y termux-api || warning "No se pudo instalar Termux:API"
    fi
}

# Configurar Asterisk
configure_asterisk() {
    info "Configurando Asterisk..."
    if command -v asterisk &> /dev/null; then
        "$INSTALL_DIR/scripts/asterisk_setup.sh" || warning "No se pudo configurar Asterisk"
    else
        warning "Asterisk no está instalado. VoIP no estará disponible."
    fi
}

# Configurar Sound Modem
configure_soundmodem() {
    info "Configurando Sound Modem..."
    if command -v soundmodem &> /dev/null; then
        "$INSTALL_DIR/scripts/soundmodem_setup.sh" || warning "No se pudo configurar Sound Modem"
    else
        warning "Sound Modem no está instalado. Radio Aficionados no estará disponible."
    fi
}

# Crear configuración inicial
create_initial_config() {
    info "Creando configuración inicial..."
    cat > "$INSTALL_DIR/data/config.json" <<EOF
{
    "version": "3.0",
    "device": {
        "name": "$(getprop ro.product.model 2>/dev/null || echo "Unknown")",
        "id": "$(settings get android_id 2>/dev/null || echo "unknown")"
    },
    "network": {
        "fallback_order": ["sms", "telegram", "voip", "mesh_wifi", "mesh_bluetooth", "radio", "satellite"],
        "retry_attempts": 3,
        "retry_delay": 5,
        "mesh_wifi": {
            "ssid": "COM-LINK-Mesh",
            "password": "emergency123",
            "port": 8080
        },
        "mesh_bluetooth": {
            "name": "COM-LINK-BT",
            "channel": 1
        }
    },
    "telegram": {
        "bot_token": "",
        "default_chat_id": "",
        "webhook_url": ""
    },
    "voip": {
        "sip": {
            "server": "192.168.1.100",
            "username": "emergencia",
            "password": "123456",
            "port": 5060
        },
        "asterisk": {
            "enabled": false,
            "config_path": "$INSTALL_DIR/data/asterisk"
        }
    },
        "radio": {
        "enabled": false,
            "frequency": "144.390",
        "mode": "AX.25",
        "baudrate": 1200
    },
    "satellite": {
        "enabled": false,
            "provider": "iridium",
        "device": "/dev/ttyS0"
    },
    "security": {
        "encryption": true,
        "auto_delete": false,
        "auto_delete_days": 30,
        "log_level": "INFO",
        "key_length": 4096,
        "stealth_mode": false
    },
    "contacts": {}
}
EOF

    chmod 600 "$INSTALL_DIR/data/config.json"
}

# Crear archivo de contactos
create_contacts() {
    cat > "$INSTALL_DIR/data/contacts.json" <<EOF
{
    "emergency": {
        "name": "Contacto de Emergencia Principal",
        "phone": "",
        "telegram_chat_id": "",
        "sip_address": "",
        "public_key": "",
        "priority": 1,
        "trusted": true
    },
    "backup": {
        "name": "Contacto Secundario",
        "phone": "",
        "telegram_chat_id": "",
        "sip_address": "",
        "public_key": "",
        "priority": 2,
        "trusted": true
    }
}
EOF
    chmod 600 "$INSTALL_DIR/data/contacts.json"
}

# ============================================================
# INSTALACIÓN
# ============================================================
main() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  📡 COM-LINK v3.0 - Instalador${NC}"
    echo -e "${BLUE}  Sistema de Comunicación de Emergencia${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""

    check_termux
    check_root

    install_packages
    create_structure
    copy_files
    set_permissions
    create_symlink
    configure_termux_api
    configure_asterisk
    configure_soundmodem
    create_initial_config
    create_contacts

    echo ""
    success "Instalación completada!"
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  📌 COM-LINK está instalado en: $INSTALL_DIR${NC}"
    echo -e "${BLUE}  📌 Ejecuta con: comlink${NC}"
    echo -e "${BLUE}  📌 O usa: ./comlink.sh${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    info "Reinicia Termux para que los cambios surtan efecto."
    info "Luego ejecuta 'comlink config' para configurar el sistema."
}

main "$@"
