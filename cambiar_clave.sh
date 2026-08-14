#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# CAMBIAR CLAVE DEL MANUAL — Descifra con clave vieja, recifra con nueva
# Uso: bash cambiar_clave.sh
# =====================================================================
set -e

MANUAL_ENC="manual_operaciones.enc"
TEMP_DEC="/tmp/manual_operaciones_$$.md"

if [ ! -f "$MANUAL_ENC" ]; then
    echo "ERROR: $MANUAL_ENC no existe."
    exit 1
fi

echo ""
echo "============================================"
echo "  CAMBIAR CLAVE DEL MANUAL"
echo "============================================"
echo ""

# ── 1. Descifrar con clave actual ──
echo -s "Clave ACTUAL: "
read -r -s CLAVE_VIEJA
echo ""

if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$MANUAL_ENC" \
    -out "$TEMP_DEC" \
    -pass pass:"$CLAVE_VIEJA" 2>/dev/null; then
    echo "CLAVE ACTUAL INCORRECTA. Operacion cancelada."
    rm -f "$TEMP_DEC" 2>/dev/null
    exit 1
fi

echo "Clave actual verificada OK."
echo ""

# ── 2. Pedir clave nueva (dos veces) ──
echo -s "Nueva clave: "
read -r -s CLAVE_NUEVA
echo ""
echo -s "Confirma nueva clave: "
read -r -s CLAVE_NUEVA2
echo ""

if [ "$CLAVE_NUEVA" != "$CLAVE_NUEVA2" ]; then
    echo "ERROR: Las claves nuevas no coinciden. Cancelado."
    shred -u "$TEMP_DEC" 2>/dev/null || rm -f "$TEMP_DEC"
    exit 1
fi

if [ ${#CLAVE_NUEVA} -lt 12 ]; then
    echo "ADVERTENCIA: Clave corta (minimo 12 caracteres recomendado)."
    echo -n "Continuar? (s/N): "
    read -r confirm
    [ "$confirm" = "s" ] || [ "$confirm" = "S" ] || { shred -u "$TEMP_DEC" 2>/dev/null || rm -f "$TEMP_DEC"; exit 1; }
fi

if [ "$CLAVE_VIEJA" = "$CLAVE_NUEVA" ]; then
    echo "AVISO: La clave nueva es igual a la actual. Sin cambios."
    shred -u "$TEMP_DEC" 2>/dev/null || rm -f "$TEMP_DEC"
    exit 0
fi

# ── 3. Recifrar con clave nueva ──
openssl enc -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$TEMP_DEC" \
    -out "$MANUAL_ENC" \
    -pass pass:"$CLAVE_NUEVA" 2>/dev/null

# ── 4. Verificar que el nuevo cifrado funciona ──
VERIFY="/tmp/manual_verify_$$.md"
if openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 \
    -in "$MANUAL_ENC" \
    -out "$VERIFY" \
    -pass pass:"$CLAVE_NUEVA" 2>/dev/null; then
    echo ""
    echo "============================================"
    echo "  CLAVE CAMBIADA CORRECTAMENTE"
    echo "============================================"
    echo ""
    echo "  El manual sigue cifrado en: $MANUAL_ENC"
    echo "  La clave anterior YA NO funciona."
    echo "  La nueva clave funciona (verificada)."
    echo ""
    echo "  Guarda la nueva clave en un gestor seguro."
    echo ""
else
    echo "ERROR: La verificacion fallo. Algo salio mal."
    echo "El archivo .enc puede estar corrupto."
fi

# ── 5. Limpiar temporales ──
shred -u "$TEMP_DEC" 2>/dev/null || rm -f "$TEMP_DEC"
shred -u "$VERIFY" 2>/dev/null || rm -f "$VERIFY"
