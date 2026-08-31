#!/bin/bash

# Script de instalación para Termux
# Uso: bash setup_termux.sh

set -e

echo "🚀 Iniciando instalación en Termux..."

# Crear directorio de trabajo
mkdir -p ~/sourceseal-osiris
cd ~/sourceseal-osiris

# Instalar dependencias
echo "📦 Instalando dependencias..."
pkg update -y
pkg install python python-pip nodejs git wget curl openssh ffmpeg -y

# Instalar paquetes Python
pip install aiohttp websockets requests opencv-python-headless numpy Pillow python-dotenv pydantic

# Clonar OSIRIS
echo "📥 Clonando OSIRIS..."
git clone https://github.com/osiris-org/osiris.git
cd osiris
npm install
cd ..

# Crear estructura de directorios
echo "📁 Creando estructura de directorios..."
mkdir -p connectors utils scripts configs docs

# Crear archivos de configuración
echo "⚙️  Creando configuraciones..."

# Configuración por defecto
cat > configs/default_config.json << 'EOF'
{
  "osiris_url": "http://localhost:3000/api",
  "seal_ws": "ws://localhost:8001/ws/alerts",
  "db_path": "~/connector_cache.db",
  "log_file": "~/connector.log",
  "log_level": "INFO",
  "max_retries": 5,
  "retry_delay": 1.0,
  "cache_cleanup_interval": 3600,
  "max_cache_age": 86400,
  "metrics_interval": 60,
  "heartbeat_interval": 30,
  "enable_camera": false,
  "enable_playbook": true
}
EOF

# Configuración de cámaras (ejemplo para Termux)
cat > configs/cameras_config.json << 'EOF'
{
  "enabled": true,
  "cameras": [
    {
      "id": "termux_cam",
      "name": "Cámara Termux",
      "url": "http://192.168.1.100:8080/video",
      "type": "http",
      "motion_detection": true,
      "motion_threshold": 0.1,
      "capture_interval": 10,
      "osiris_event_type": "camera_motion"
    }
  ],
  "image_storage": {
    "local_path": "~/camera_captures",
    "max_images": 100,
    "quality": 75
  },
  "osiris": {
    "send_images": true,
    "image_format": "base64",
    "max_image_size": 512
  }
}
EOF

# Configuración de playbooks
cat > configs/playbooks_config.json << 'EOF'
{
  "playbooks": [
    {
      "id": "termux_scan",
      "name": "Escanear con Nmap",
      "description": "Escanear puertos básicos",
      "command": "nmap",
      "args": ["-sS", "-p-", "-T2", "{{target}}"],
      "timeout": 120,
      "working_directory": "/data/data/com.termux/files/home",
      "triggers": ["scan"]
    }
  ]
}
EOF

# Crear script de inicio
echo "📝 Creando scripts de inicio..."

cat > start_osiris.sh << 'EOF'
#!/bin/bash
cd ~/sourceseal-osiris/osiris
npm start &
EOF

cat > start_connector.sh << 'EOF'
#!/bin/bash
cd ~/sourceseal-osiris
python3 connectors/main_connector.py &
EOF

cat > start_all.sh << 'EOF'
#!/bin/bash
# Iniciar todos los servicios
cd ~/sourceseal-osiris

# Iniciar OSIRIS
bash start_osiris.sh

# Esperar a que OSIRIS inicie
sleep 5

# Iniciar conector principal
bash start_connector.sh

# Iniciar conector de cámaras (si está habilitado)
if [ -f "configs/cameras_config.json" ]; then
    python3 connectors/camera_connector.py &
fi

# Iniciar conector de playbooks
python3 connectors/playbook_connector.py &

echo "✅ Todos los servicios iniciados"
echo "🌐 OSIRIS Dashboard: http://localhost:3000"
EOF

# Crear script de verificación
cat > check_all.py << 'EOF'
#!/usr/bin/env python3
import asyncio
import aiohttp
import os
import sys

async def check():
    checks = []
    
    # Verificar OSIRIS
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:3000/api/status", timeout=5) as resp:
                if resp.status == 200:
                    checks.append(("OSIRIS", "✅ Funcionando"))
                else:
                    checks.append(("OSIRIS", f"⚠️  Código {resp.status}"))
    except Exception as e:
        checks.append(("OSIRIS", f"❌ Error: {e}"))
    
    # Verificar conector
    if os.path.exists("~/connector.log"):
        with open("~/connector.log", "r") as f:
            lines = f.readlines()
            if lines and "Conector iniciado" in lines[-1]:
                checks.append(("Conector", "✅ Funcionando"))
            else:
                checks.append(("Conector", "⚠️  Verificar logs"))
    else:
        checks.append(("Conector", "❌ No iniciado"))
    
    # Verificar cámaras
    if os.path.exists("configs/cameras_config.json"):
        checks.append(("Cámaras", "✅ Configuradas"))
    else:
        checks.append(("Cámaras", "⚠️  No configuradas"))
    
    # Verificar playbooks
    if os.path.exists("configs/playbooks_config.json"):
        checks.append(("Playbooks", "✅ Configurados"))
    else:
        checks.append(("Playbooks", "⚠️  No configurados"))
    
    # Mostrar resultados
    print("\n" + "="*50)
    print("📊 ESTADO DE LOS SERVICIOS")
    print("="*50)
    for name, status in checks:
        print(f"{name:15} {status}")
    print("="*50 + "\n")
    
    # Verificar si todo está OK
    all_ok = all("✅" in status for _, status in checks)
    if all_ok:
        print("✅ Todos los servicios están funcionando correctamente!")
        print("\n🌐 Accede al dashboard: http://localhost:3000")
        return 0
    else:
        print("⚠️  Algunos servicios no están funcionando")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(check()))
EOF

# Dar permisos de ejecución
chmod +x start_osiris.sh start_connector.sh start_all.sh check_all.py

# Crear .env para OSIRIS
cat > osiris/.env << 'EOF'
PORT=3000
NEXT_PUBLIC_MAPBOX_TOKEN=""
NEXT_PUBLIC_OSIRIS_VERSION=3.0.0
ALLOW_CORS=true
EOF

# Crear requirements.txt
cat > requirements.txt << 'EOF'
aiohttp>=3.8.0
websockets>=10.0
requests>=2.28.0
opencv-python-headless>=4.5.0
numpy>=1.21.0
Pillow>=9.0.0
python-dotenv>=0.19.0
pydantic>=1.9.0
EOF

echo ""
echo "✅ Instalación completada!"
echo ""
echo "Para iniciar los servicios:"
echo "  1. bash start_all.sh"
echo "  2. Verificar: python3 check_all.py"
echo ""
echo "Para acceder al dashboard:"
echo "  http://localhost:3000"
echo ""
echo "Notas para Termux:"
echo "  - Usa 'nohup bash start_all.sh &' para ejecutar en background"
echo "  - Los logs están en ~/connector.log"
echo "  - Para detener: pkill -f python3; pkill -f node"
