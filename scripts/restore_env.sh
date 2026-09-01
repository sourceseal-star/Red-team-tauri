#!/data/data/com.termux/files/usr/bin/bash
# restore_env.sh — Restaura .env desde un snapshot cifrado
# Uso:
#   bash scripts/restore_env.sh              # lista snapshots y elige
#   bash scripts/restore_env.sh 2            # restaura el snapshot #2 directamente
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
SNAPSHOT_DIR="${HOME}/.c2/snapshots"
AUTH_FILE="$PROJECT_ROOT/redteam/scripts/.auth/password.json"

if [ ! -d "$SNAPSHOT_DIR" ] || [ -z "$(ls -A "$SNAPSHOT_DIR"/env_*.aes 2>/dev/null)" ]; then
    echo "[restore] No hay snapshots en $SNAPSHOT_DIR"
    echo "[restore] Alternativas:"
    echo "[restore]   bash control_claves.sh restore   (respaldo cifrado de control_claves)"
    echo "[restore]   bash control_claves.sh set       (definir desde cero)"
    exit 1
fi

# Listar snapshots
SNAPSHOTS=($(ls -1t "$SNAPSHOT_DIR"/env_*.aes 2>/dev/null))
COUNT=${#SNAPSHOTS[@]}

echo "=== Snapshots disponibles ==="
for i in "${!SNAPSHOTS[@]}"; do
    F="$(basename "${SNAPSHOTS[$i]}")"
    SIZE=$(stat -c '%s' "${SNAPSHOTS[$i]}" 2>/dev/null || stat -f '%z' "${SNAPSHOTS[$i]}" 2>/dev/null || echo '?')
    echo "  $((i+1)). $F (${SIZE} bytes)"
done
echo ""

# Elegir
CHOICE="${1:-}"
if [ -z "$CHOICE" ]; then
    read -rp "Elige snapshot # (1-$COUNT): " CHOICE
fi

if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt "$COUNT" ]; then
    echo "[restore] Selección inválida: $CHOICE"
    exit 1
fi

SELECTED="${SNAPSHOTS[$((CHOICE-1))]}"
echo "[restore] Seleccionado: $(basename "$SELECTED")"

# Passphrase
read -rsp "Passphrase del snapshot: " RESTORE_PASS; echo

# Descifrar a temporal
TEMP_FILE="/tmp/env_restore_$$.tmp"
if ! openssl enc -d -aes-256-cbc -salt -pbkdf2 \
    -in "$SELECTED" \
    -out "$TEMP_FILE" \
    -pass pass:"$RESTORE_PASS" 2>/dev/null; then
    echo "[restore] ERROR: Passphrase incorrecta o archivo corrupto."
    rm -f "$TEMP_FILE"
    exit 1
fi

# Verificar que tiene las 3 variables críticas
MISSING=""
for v in ADMIN_PASSWORD NEXUS_PASS REDTEAM_API_KEY; do
    if ! grep -q "^${v}=" "$TEMP_FILE" || [ -z "$(grep "^${v}=" "$TEMP_FILE" | cut -d= -f2)" ]; then
        MISSING="$MISSING $v"
    fi
done

if [ -n "$MISSING" ]; then
    echo "[restore] ERROR: El snapshot no tiene:$MISSING"
    echo "[restore] No se restauró nada. El .env actual quedó intacto."
    rm -f "$TEMP_FILE"
    exit 1
fi

# Restaurar
cp "$TEMP_FILE" "$ENV_FILE"
chmod 600 "$ENV_FILE"
rm -f "$TEMP_FILE"

# Borrar password.json para que se regenere desde el .env restaurado
if [ -f "$AUTH_FILE" ]; then
    rm -f "$AUTH_FILE"
    echo "[restore] 🗑️  password.json borrado (se regenerará desde .env al arrancar)"
fi

echo ""
echo "[restore] ✅ .env restaurado desde: $(basename "$SELECTED")"
echo "[restore] Permisos: 600"
echo ""
echo "[restore] Pasos para reiniciar:"
echo "  1. cd $PROJECT_ROOT"
echo "  2. bash iniciar_unificado.sh"
echo "  3. bash scripts/healthcheck_all.sh"
echo ""
echo "[restore] Si usas Commander en proceso separado:"
echo "  export COMMANDER_DIR=\"$PROJECT_ROOT/commander\""
