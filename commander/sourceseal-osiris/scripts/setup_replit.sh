#!/bin/bash

# Script de instalación para Replit
# En Replit, este script se ejecuta manualmente

set -e

echo "🚀 Configurando proyecto para Replit..."

# Crear estructura de directorios
mkdir -p connectors utils scripts configs

# Crear configuraciones
cat > configs/default_config.json << 'EOF'
{
  "osiris_url": "http://localhost:8000/api",
  "seal_ws": "ws://localhost:8001/ws/alerts",
  "db_path": "/tmp/connector_cache.db",
  "log_file": "/tmp/connector.log",
  "log_level": "INFO",
  "max_retries": 3,
  "retry_delay": 1.0,
  "cache_cleanup_interval": 3600,
  "max_cache_age": 86400,
  "metrics_interval": 60,
  "heartbeat_interval": 30,
  "enable_camera": false,
  "enable_playbook": true
}
EOF

cat > configs/cameras_config.json << 'EOF'
{
  "enabled": false,
  "cameras": [],
  "image_storage": {
    "local_path": "/tmp/camera_captures",
    "max_images": 10,
    "quality": 75
  },
  "osiris": {
    "send_images": false,
    "image_format": "base64",
    "max_image_size": 512
  }
}
EOF

cat > configs/playbooks_config.json << 'EOF'
{
  "playbooks": [
    {
      "id": "replit_scan",
      "name": "Escanear Puertos",
      "description": "Escanear puertos básicos",
      "command": "python3",
      "args": ["-c", "import socket; print('Escaneo completado para:', '{{target}}')"],
      "timeout": 30,
      "working_directory": "/home/runner",
      "triggers": ["scan"]
    }
  ]
}
EOF

# Crear .replit
cat > .replit << 'EOF'
run = "python3 main.py"
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

# Crear README
cat > README.md << 'EOF'
# SourceSeal + OSIRIS Integration - Replit

## Quick Start

1. Click "Run" to start all services
2. OSIRIS will be available at: http://localhost:8000
3. Connectors will automatically connect to SourceSeal

## Configuration

- Edit `configs/default_config.json` for main settings
- Edit `configs/playbooks_config.json` for playbook definitions
- Edit `configs/cameras_config.json` for camera settings (disabled by default in Replit)

## Notes

- In Replit, camera integration is disabled due to network restrictions
- OSIRIS runs on port 8000 (not 3000) to avoid permission issues
- All logs are stored in /tmp/ directory

## Troubleshooting

- Check logs: `cat /tmp/connector.log`
- Verify OSIRIS: `curl http://localhost:8000/api/status`
- Restart: Click "Run" again
EOF

echo ""
echo "✅ Configuración para Replit completada!"
echo ""
echo "Siguientes pasos:"
echo "  1. git clone https://github.com/osiris-org/osiris.git"
echo "  2. Copia los archivos de connectors/ a tu proyecto"
echo "  3. Click 'Run' en Replit"
echo ""
