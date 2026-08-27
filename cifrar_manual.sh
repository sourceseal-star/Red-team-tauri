#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# CIFRAR MANUAL DE OPERACIONES — AES-256-CBC + scrypt KDF
# Uso: bash cifrar_manual.sh
# =====================================================================
set -e

MANUAL="manual_operaciones.md"
MANUAL_ENC="manual_operaciones.enc"

if [ ! -f "$MANUAL" ]; then
    echo "ERROR: $MANUAL no existe."
    exit 1
fi

echo ""
echo "============================================"
echo "  CIFRADO DEL MANUAL DE OPERACIONES"
echo "  Metodo: AES-256-CBC + PBKDF2 (100k iter)"
echo "============================================"
echo ""
echo "Elige una clave de acceso (minimo 12 caracteres)."
echo "Esta clave NO se guarda en ningun lado."
echo "Si la pierdes, el documento es irrecuperable."
echo ""
echo -s "Clave de acceso: "
read -r -s CLAVE
echo ""
echo -s "Confirma la clave: "
read -r -s CLAVE2
echo ""

if [ "$CLAVE" != "$CLAVE2" ]; then
    echo "ERROR: Las claves no coinciden."
    exit 1
fi

if [ ${#CLAVE} -lt 12 ]; then
    echo "ADVERTENCIA: Clave corta. Se recomienda minimo 12 caracteres."
    echo -n "Continuar de todas formas? (s/N): "
    read -r confirm
    [ "$confirm" = "s" ] || [ "$confirm" = "S" ] || exit 1
fi

# Cifrar
openssl enc -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$MANUAL" \
    -out "$MANUAL_ENC" \
    -pass pass:"$CLAVE" 2>/dev/null

# Borrar el original (secure delete)
shred -u "$MANUAL" 2>/dev/null || rm -f "$MANUAL"

echo ""
echo "============================================"
echo "  MANUAL CIFRADO CORRECTAMENTE"
echo "============================================"
echo ""
echo "  Archivo cifrado: $MANUAL_ENC"
echo "  Original borrado: $MANUAL (shred)"
echo ""
echo "  Para descifrar: bash acceder_manual.sh"
echo ""
echo "  IMPORTANTE:"
echo "  - Guarda tu clave en un gestor de contrasenas"
echo "  - No subas .enc a GitHub (esta en .gitignore)"
echo "  - El archivo .enc es inutil sin la clave"
echo ""
