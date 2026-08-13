#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# ACCEDER AL MANUAL DE OPERACIONES (cifrado AES-256-CBC)
# Uso: bash acceder_manual.sh
# =====================================================================
set -e

MANUAL_ENC="manual_operaciones.enc"

# En Termux/Android, /tmp NO es escribible. Usar TMPDIR o el dir del script.
TEMP_DIR="${TMPDIR:-$(dirname "$0")}"
if [ ! -w "$TEMP_DIR" ]; then
    TEMP_DIR="$(dirname "$0")"
fi
MANUAL_DEC="$TEMP_DIR/.manual_dec_$$.md"

if [ ! -f "$MANUAL_ENC" ]; then
    echo "ERROR: $MANUAL_ENC no existe."
    exit 1
fi

echo ""
echo "============================================"
echo "  ACCESO AL MANUAL DE OPERACIONES"
echo "  Cifrado: AES-256-CBC + scrypt KDF"
echo "============================================"
echo ""

echo -n "Introduce la clave de acceso: "
read -r -s CLAVE
echo ""

if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$MANUAL_ENC" \
    -out "$MANUAL_DEC" \
    -pass pass:"$CLAVE" 2>/tmp/openssl_err_$$.log; then

    if grep -qi "MANUAL DE OPERACIONES" "$MANUAL_DEC" 2>/dev/null; then
        echo ""
        echo "Clave correcta. Manual descifrado."
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
        echo "CLAVE INCORRECTA. Acceso denegado."
        rm -f "$MANUAL_DEC" 2>/dev/null
        exit 1
    fi
else
    echo "CLAVE INCORRECTA o error tecnico. Acceso denegado."
    echo "(detalle: $(cat /tmp/openssl_err_$$.log 2>/dev/null))"
    rm -f "$MANUAL_DEC" 2>/dev/null
    exit 1
fi

rm -f /tmp/openssl_err_$$.log 2>/dev/null
