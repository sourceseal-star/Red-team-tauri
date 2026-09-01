#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# SEAL TELEGRAM CMD — puente para comando /seal via Telegram
# Ejecuta seal_orchestrator --status y responde (máx 500 chars).
# Uso directo:  bash scripts/seal_telegram_cmd.sh
# Desde poller: salida a stdout, o envía por Telegram si está configurado.
# =====================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SEAL_SCRIPT="$ROOT/seal/orchestrator/seal_orchestrator.py"

if [ ! -f "$SEAL_SCRIPT" ]; then
    echo "❌ Seal IA no encontrado: $SEAL_SCRIPT"
    exit 1
fi

# Capturar salida de --status
RAW_OUTPUT="$("$PYTHON_BIN" "$SEAL_SCRIPT" --status 2>&1 || true)"

# Truncar a 500 caracteres
OUTPUT="$(echo "$RAW_OUTPUT" | head -c 500)"

# Si hay token y chat_id configurados, enviar por Telegram
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    PAYLOAD=$(jq -n --arg chat "$TELEGRAM_CHAT_ID" --arg text "$OUTPUT" \
        '{chat_id: $chat, text: $text}')
    curl -sS --max-time 10 \
        -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -H "Content-Type: application/json" \
        --data-binary "$PAYLOAD" >/dev/null 2>&1 || true
    echo "[seal-tg] Estado enviado a Telegram"
else
    # Sin Telegram configurado — imprimir a stdout
    echo "$OUTPUT"
fi
