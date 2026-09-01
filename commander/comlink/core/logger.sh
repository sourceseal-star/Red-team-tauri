#!/bin/bash
# core/logger.sh - Logging Avanzado para COM-LINK v3.0

# ============================================================
# CONFIGURACIÓN
# ============================================================
LOG_DIR="$INSTALL_DIR/data/logs"
MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB
MAX_LOG_FILES=5
LOG_LEVEL=${LOG_LEVEL:-INFO}

# Niveles de log (por prioridad)
declare -A LOG_LEVELS=(
    ["DEBUG"]=0
    ["INFO"]=1
    ["WARNING"]=2
    ["ERROR"]=3
    ["CRITICAL"]=4
)

# Colores para cada nivel
declare -A LOG_COLORS=(
    ["DEBUG"]="\033[0;36m"
    ["INFO"]="\033[0;32m"
    ["WARNING"]="\033[1;33m"
    ["ERROR"]="\033[0;31m"
    ["CRITICAL"]="\033[1;31m"
)

# Iconos para cada nivel
declare -A LOG_ICONS=(
    ["DEBUG"]="🔍"
    ["INFO"]="ℹ️"
    ["WARNING"]="⚠️"
    ["ERROR"]="❌"
    ["CRITICAL"]="🚨"
)

# ============================================================
# FUNCIONES
# ============================================================
# Log principal
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local color="${LOG_COLORS[$level]}"
    local icon="${LOG_ICONS[$level]}"
    local nc="\033[0m"

    # Verificar si el nivel actual permite este log
    local current_level_priority=${LOG_LEVELS[$LOG_LEVEL]}
    local message_level_priority=${LOG_LEVELS[$level]}

    if [ $message_level_priority -lt $current_level_priority ]; then
        return
    fi

    # Formatear mensaje
    local formatted_message="${icon} [${timestamp}] [${level}] ${message}"

    # Log a consola (solo si no está en modo stealth)
    if [ "$STEALTH_MODE" != "true" ]; then
        echo -e "${color}${formatted_message}${nc}"
    fi

    # Log a archivo
    echo "[$timestamp] [$level] $message" >> "$LOG_DIR/comlink_$(date +%Y%m%d).log"

    # Rotar logs si es necesario
    rotate_logs
}

# Logs específicos
debug() { log "DEBUG" "$1"; }
info() { log "INFO" "$1"; }
warning() { log "WARNING" "$1"; }
error() { log "ERROR" "$1"; }
critical() { log "CRITICAL" "$1"; }
success() { log "INFO" "$1"; }

# Rotar logs
rotate_logs() {
    local current_log="$LOG_DIR/comlink_$(date +%Y%m%d).log"

    if [ -f "$current_log" ]; then
        local size=$(stat -c%s "$current_log" 2>/dev/null || echo 0)

        if [ $size -gt $MAX_LOG_SIZE ]; then
            # Rotar logs antiguos
            for ((i=$MAX_LOG_FILES-1; i>=1; i--)); do
                local prev=$((i-1))
                local old_log="$LOG_DIR/comlink_$(date +%Y%m%d).log.$prev"
                local new_log="$LOG_DIR/comlink_$(date +%Y%m%d).log.$i"

                if [ -f "$old_log" ]; then
                    mv "$old_log" "$new_log"
                fi
            done

            # Rotar el log actual
            mv "$current_log" "$LOG_DIR/comlink_$(date +%Y%m%d).log.0"
        fi
    fi
}

# Limpiar logs antiguos
clean_logs() {
    local days=${1:-30}
    find "$LOG_DIR" -name "comlink_*.log.*" -mtime +$days -delete 2>/dev/null
    info "Logs antiguos limpiados (más de $days días)"
}

# Inicializar logger
mkdir -p "$LOG_DIR"
rotate_logs
