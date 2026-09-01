#!/data/data/com.termux/files/usr/bin/bash
# snapshot_env.sh — Crea un snapshot cifrado del .env actual
# Uso:
#   bash scripts/snapshot_env.sh                    # passphrase interactiva
#   SNAPSHOT_PASS="mipass" bash scripts/snapshot_env.sh  # passphrase via env
#
# Conserva solo los últimos 5 snapshots.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
SNAPSHOT_DIR="${HOME}/.c2/snapshots"
MAX_SNAPSHOTS=5

if [ ! -f "$ENV_FILE" ]; then
    echo "[snapshot] ERROR: .env no existe en $ENV_FILE"
    echo "[snapshot] No se puede snapshotear lo que no existe."
    exit 1
fi

mkdir -p "$SNAPSHOT_DIR"
chmod 700 "$SNAPSHOT_DIR" 2>/dev/null || true

# Passphrase
if [ -z "${SNAPSHOT_PASS:-}" ]; then
    read -rsp "Passphrase para el snapshot: " SNAPSHOT_PASS; echo
fi

if [ -z "$SNAPSHOT_PASS" ]; then
    echo "[snapshot] ERROR: Passphrase vacía. Cancelado."
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$SNAPSHOT_DIR/env_${TIMESTAMP}.aes"

# Cifrar
openssl enc -aes-256-cbc -salt -pbkdf2 \
    -in "$ENV_FILE" \
    -out "$OUT_FILE" \
    -pass pass:"$SNAPSHOT_PASS" 2>/dev/null

chmod 600 "$OUT_FILE"

# Verificar que el cifrado funciona
if ! openssl enc -d -aes-256-cbc -salt -pbkdf2 \
    -in "$OUT_FILE" \
    -pass pass:"$SNAPSHOT_PASS" \
    -out /dev/null 2>/dev/null; then
    echo "[snapshot] ERROR: El cifrado falló. No se guardó nada."
    rm -f "$OUT_FILE"
    exit 1
fi

echo "[snapshot] ✅ Snapshot creado: $OUT_FILE"

# Conservar solo los últimos 5
SNAPSHOTS=($(ls -1t "$SNAPSHOT_DIR"/env_*.aes 2>/dev/null))
if [ ${#SNAPSHOTS[@]} -gt $MAX_SNAPSHOTS ]; then
    for old_file in "${SNAPSHOTS[@]:$MAX_SNAPSHOTS}"; do
        rm -f "$old_file"
        echo "[snapshot] 🗑️  Eliminado snapshot viejo: $(basename "$old_file")"
    done
fi

COUNT=$(ls -1 "$SNAPSHOT_DIR"/env_*.aes 2>/dev/null | wc -l)
echo "[snapshot] Total snapshots: $COUNT (máximo $MAX_SNAPSHOTS)"
