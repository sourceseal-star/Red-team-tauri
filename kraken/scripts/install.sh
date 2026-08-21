#!/bin/bash
set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar si es root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}❌ Este script debe ejecutarse como root (sudo)${NC}"
    exit 1
fi

# Detectar sistema
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
else
    OS=$(uname -s)
fi

echo -e "${YELLOW}🔧 Detectando sistema: $OS${NC}"

# Instalar dependencias del sistema
echo -e "${YELLOW}📦 Instalando dependencias del sistema...${NC}"
if [[ "$OS" == *"Kali"* ]] || [[ "$OS" == *"Debian"* ]] || [[ "$OS" == *"Ubuntu"* ]]; then
    apt update && apt install -y \
        nmap sshpass curl smbclient lftp default-mysql-client freerdp2-x11 \
        redis-server postgresql-client snmp redis-tools python3-pip \
        python3-venv python3-dev libpq-dev libssl-dev libffi-dev \
        git wget build-essential
elif [[ "$OS" == *"Arch"* ]]; then
    pacman -Syu --noconfirm nmap sshpass curl smbclient lftp mysql \
        freerdp redis postgresql snmp python-pip python build-essential git wget
elif [[ "$OS" == *"Termux"* ]]; then
    pkg update -y && pkg upgrade -y
    pkg install -y nmap sshpass curl smbclient lftp mysql-client freerdp2-x11 \
        redis postgresql snmp python pip git wget clang
else
    echo -e "${RED}❌ Sistema no soportado: $OS${NC}"
    exit 1
fi

# Instalar Masscan (no está en repos)
echo -e "${YELLOW}🔨 Compilando Masscan...${NC}"
if [ ! -d "/opt/masscan" ]; then
    git clone --depth 1 https://github.com/robertdavidgraham/masscan /opt/masscan
    cd /opt/masscan
    make
    ln -s /opt/masscan/bin/masscan /usr/local/bin/masscan
    cd -
fi

# Crear entorno virtual
echo -e "${YELLOW}🐍 Configurando entorno Python...${NC}"
python3 -m venv /opt/kraken-venv
source /opt/kraken-venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Configurar variables de entorno
echo -e "${YELLOW}⚙️  Configurando variables de entorno...${NC}"
cat > /etc/profile.d/kraken.sh << 'EOF'
export KRAKEN_HOME=/opt/kraken
export PATH=$PATH:$KRAKEN_HOME/bin
export PYTHONPATH=$PYTHONPATH:$KRAKEN_HOME/src
EOF

# Clonar/crear directorio del proyecto
if [ ! -d "/opt/kraken" ]; then
    mkdir -p /opt/kraken/{src,config,scripts,docs,web,tests,docker,.github/workflows}
fi

# Instalar como paquete
echo -e "${YELLOW}📦 Instalando KRAKEN como paquete Python...${NC}"
cd /opt/kraken
pip install -e .

# Crear directorios de logs y datos
mkdir -p /var/log/kraken /var/lib/kraken

# Configurar permisos
chown -R $SUDO_USER:$SUDO_USER /opt/kraken
chmod -R 750 /var/log/kraken /var/lib/kraken

# Crear servicio systemd
cat > /etc/systemd/system/kraken.service << 'EOF'
[Unit]
Description=KRAKEN v3.0 - Motor de Explotación Autónomo
After=network.target redis-server.target postgresql.service

[Service]
User=$SUDO_USER
Group=$SUDO_USER
WorkingDirectory=/opt/kraken
Environment="PYTHONPATH=/opt/kraken/src"
EnvironmentFile=/etc/kraken/kraken.env
ExecStart=/opt/kraken-venv/bin/python -m kraken.cli.commands daemon
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Crear archivo de entorno (ejemplo)
cat > /etc/kraken/kraken.env << 'EOF'
# Configuración de KRAKEN
KRAKEN_TARGETS=192.168.1.0/24,10.0.0.0/24
KRAKEN_INTERVAL=7200
KRAKEN_WORKERS=20
KRAKEN_DB=postgresql://kraken:kraken123@localhost/kraken
KRAKEN_REDIS_URL=redis://localhost:6379/0
KRAKEN_LOG_LEVEL=INFO
KRAKEN_CACHE_EXPIRY=3600

# Notificaciones
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SLACK_WEBHOOK_URL=
EMAIL_SMTP_SERVER=
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=
EMAIL_PASSWORD=
EMAIL_FROM=
EMAIL_TO=

# Integraciones
SHODAN_API_KEY=
CENSYS_API_ID=
CENSYS_API_SECRET=
VIRUSTOTAL_API_KEY=
SIEM_WEBHOOK_URL=
EOF

chmod 600 /etc/kraken/kraken.env

# Habilitar e iniciar servicio
systemctl daemon-reload
systemctl enable kraken
systemctl start kraken

# Verificar instalación
echo -e "${GREEN}✅ Instalación completada!${NC}"
echo -e "${GREEN}📌 KRAKEN está instalado en: /opt/kraken${NC}"
echo -e "${GREEN}📌 Entorno virtual: /opt/kraken-venv${NC}"
echo -e "${GREEN}📌 Configuración: /etc/kraken/kraken.env${NC}"
echo -e "${GREEN}📌 Servicio: systemctl start|stop|status kraken${NC}"
echo -e "${GREEN}📌 CLI: kraken --help${NC}"
echo -e "${GREEN}📌 API: kraken-api (puerto 8000)${NC}"
echo -e "${GREEN}📌 Web: kraken-web (puerto 8501)${NC}"
