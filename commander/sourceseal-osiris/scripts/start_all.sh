#!/bin/bash
# start_all.sh — Iniciar todos los servicios SourceSeal + OSIRIS

set -e
cd "$(dirname "$0")/.."

echo "🚀 Iniciando SourceSeal + OSIRIS..."

# Crear .env si no existe
if [ ! -f ".env" ]; then
    cp .env.template .env
    echo "⚠️ .env creado desde template — edítalo con tus valores"
fi

# Crear directorios
mkdir -p configs logs

# Iniciar conector principal
echo "📡 Iniciando conector principal..."
python3 connectors/main_connector.py &
SEAL_PID=$!

# Iniciar conector de cámaras si está habilitado
if [ -f "configs/cameras_config.json" ]; then
    ENABLED=$(python3 -c "import json; print(json.load(open('configs/cameras_config.json')).get('enabled', False))" 2>/dev/null || echo "False")
    if [ "$ENABLED" = "True" ] || [ "$ENABLED" = "true" ]; then
        echo "🎥 Iniciando conector de cámaras..."
        python3 connectors/camera_connector.py &
        CAM_PID=$!
    fi
fi

# Iniciar conector de playbooks si está habilitado
if [ -f "configs/playbooks_config.json" ]; then
    echo "📜 Iniciando conector de playbooks..."
    python3 connectors/playbook_connector.py &
        PB_PID=$!
fi

# Iniciar monitor
if [ -f "scripts/monitor.py" ]; then
    echo "📊 Iniciando monitor..."
    python3 scripts/monitor.py &
    MON_PID=$!
fi

echo ""
echo "✅ Servicios iniciados:"
echo "  Conector principal: PID $SEAL_PID"
[ -n "$CAM_PID" ] && echo "  Cámaras: PID $CAM_PID"
[ -n "$PB_PID" ] && echo "  Playbooks: PID $PB_PID"
[ -n "$MON_PID" ] && echo "  Monitor: PID $MON_PID"
echo ""
echo "Logs: tail -f ~/connector.log"
echo "Detener: kill $SEAL_PID ${CAM_PID:-} ${PB_PID:-} ${MON_PID:-}"

# Trap para detener todo
trap "echo '🛑 Deteniendo...'; kill $SEAL_PID ${CAM_PID:-} ${PB_PID:-} ${MON_PID:-} 2>/dev/null; exit" SIGINT SIGTERM

# Esperar
wait
