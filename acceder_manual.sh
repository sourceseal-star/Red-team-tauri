#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# ACCESO AL MANUAL DE OPERACIONES — Cifrado AES-256-CBC
# Uso: bash acceder_manual.sh
# =====================================================================
set -e

MANUAL_ENC="manual_operaciones.enc"
MANUAL_DEC="/tmp/manual_operaciones.md"

if [ ! -f "$MANUAL_ENC" ]; then
    echo "ERROR: $MANUAL_ENC no existe."
    echo "Ejecuta primero: bash cifrar_manual.sh"
    exit 1
fi

echo ""
echo "============================================"
echo "  ACCESO AL MANUAL DE OPERACIONES"
echo "  Cifrado: AES-256-CBC + scrypt KDF"
echo "============================================"
echo ""
echo -s "Introduce la clave de acceso: "
read -r -s CLAVE
echo ""

# Descifrar a temporal
if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$MANUAL_ENC" \
    -out "$MANUAL_DEC" \
    -pass pass:"$CLAVE" 2>/dev/null; then

    echo "Clave correcta. Manual descifrado."
    echo ""
    echo "Como quieres verlo?"
    echo "  1) Mostrar en consola"
    echo "  2) Abrir con less (navegable)"
    echo "  3) Copiar a portapapeles"
    echo "  4) Solo descifrar y salir"
    echo ""
    echo -n "Opcion: "
    read -r opt

    case "$opt" in
        1) cat "$MANUAL_DEC" ;;
        2) less "$MANUAL_DEC" ;;
        3)
            if command -v termux-clipboard-set >/dev/null 2>&1; then
                cat "$MANUAL_DEC" | termux-clipboard-set
                echo "Copiado al portapapeles."
            else
                echo "termux-clipboard no disponible. Mostrando:"
                cat "$MANUAL_DEC"
            fi
            ;;
        4) echo "Descifrado en $MANUAL_DEC" ;;
        *) cat "$MANUAL_DEC" ;;
    esac

    # Borrar el temporal al salir (secure delete)
    shred -u "$MANUAL_DEC" 2>/dev/null || rm -f "$MANUAL_DEC"
    echo ""
    echo "Temporal borrado. El manual cifrado sigue en $MANUAL_ENC"
else
    echo "CLAVE INCORRECTA. Acceso denegado."
    rm -f "$MANUAL_DEC" 2>/dev/null
    exit 1
fi
