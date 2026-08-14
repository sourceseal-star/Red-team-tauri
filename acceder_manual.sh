#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# ACCEDER AL MANUAL DE OPERACIONES (cifrado AES-256-CBC)
# Uso: bash acceder_manual.sh
# =====================================================================
set -e

MANUAL_ENC="manual_operaciones.enc"
TEMP_DIR="${TMPDIR:-$(dirname "$0")}"
[ ! -w "$TEMP_DIR" ] && TEMP_DIR="$(dirname "$0")"
MANUAL_DEC="$TEMP_DIR/.manual_dec_$$.md"

if [ ! -f "$MANUAL_ENC" ]; then
    echo "ERROR: $MANUAL_ENC no existe."
    exit 1
fi

echo ""
echo "============================================"
echo "  ACCESO AL MANUAL DE OPERACIONES"
echo "  Cifrado: AES-256-CBC + PBKDF2 (100k iter)"
echo "============================================"
echo ""

# Si MANUAL_ENC_KEY está en el entorno, usarla directamente
if [ -n "$MANUAL_ENC_KEY" ]; then
    CLAVE="$MANUAL_ENC_KEY"
    echo "Usando clave del entorno (MANUAL_ENC_KEY)"
else
    echo -n "Introduce la clave de acceso: "
    read -r -s CLAVE
    echo ""
fi

if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$MANUAL_ENC" \
    -out "$MANUAL_DEC" \
    -pass pass:"$CLAVE" 2>/dev/null; then

    if grep -qi "MANUAL DE OPERACIONES\|SourceSeal\|Red-Team" "$MANUAL_DEC" 2>/dev/null; then
        echo "✓ Clave correcta. Manual descifrado."
        echo ""
        echo "Como quieres verlo?"
        echo "  1) Mostrar en consola"
        echo "  2) Abrir con less (navegable)"
        echo "  3) Solo descifrar y salir"
        echo ""
        echo -n "Opcion: "
        read -r OPCION

        case "$OPCION" in
            1) cat "$MANUAL_DEC" ;;
            2) less "$MANUAL_DEC" ;;
            *) echo "Descifrado en: $MANUAL_DEC" ;;
        esac

        if [ "$OPCION" != "3" ]; then
            rm -f "$MANUAL_DEC"
            echo ""
            echo "Temporal borrado."
        fi
    else
        echo "✗ CLAVE INCORRECTA. Acceso denegado."
        rm -f "$MANUAL_DEC" 2>/dev/null
        exit 1
    fi
else
    echo "✗ CLAVE INCORRECTA o error tecnico. Acceso denegado."
    rm -f "$MANUAL_DEC" 2>/dev/null
    exit 1
fi
