#!/usr/bin/env bash
# Reconstruye el frontend de Sol Y VERIFICA que el build nuevo de verdad
# contenga las funciones esperadas (microfono, voz) antes de decir "listo".
#
# El build_frontend() de omni.sh, si npm run build fallaba, seguia adelante
# con un warning y el sistema quedaba usando el dist/ VIEJO sin que nadie se
# diera cuenta - eso es lo que ha estado pasando. Este script no permite eso:
# si el build falla o el resultado no tiene lo esperado, se detiene con
# codigo de salida distinto de cero y dice EXACTAMENTE que salio mal.
#
# Uso:
#   bash scripts/build_and_verify_frontend.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT/tauri-frontend"
DIST_DIR="$FRONTEND_DIR/dist"
LOG_FILE="$ROOT/logs/frontend_build.log"
mkdir -p "$ROOT/logs"

# Cadenas que DEBEN aparecer en el JS compilado si el build incluyo el
# microfono/voz de Sol (FloatingSol.tsx). Si vite minifica, los string
# literales sobreviven igual (no son nombres de variable).
MARKERS=("Hablar con Sol" "Escuchando" "SpeechRecognition")

fail() { echo "❌ $*"; exit 1; }
ok()   { echo "✅ $*"; }
info() { echo "ℹ️  $*"; }

[ -d "$FRONTEND_DIR" ] || fail "No existe $FRONTEND_DIR"
cd "$FRONTEND_DIR"

echo "════════════════════════════════════════════"
echo " Build + verificación del frontend de Sol"
echo "════════════════════════════════════════════"
echo ""

info "Commit actual: $(cd "$ROOT" && git log -1 --oneline 2>/dev/null || echo 'desconocido')"
info "RAM disponible: $(free -h 2>/dev/null | awk '/Mem:/{print $7}' || echo 'no medible en este entorno')"
echo ""

# Limpiar node_modules corrupto es agresivo -> solo instalar si falta
if [ ! -d node_modules ]; then
  info "node_modules no existe — npm install (puede tardar unos minutos)..."
  if ! npm install 2>&1 | tee -a "$LOG_FILE"; then
    fail "npm install falló. Revisa $LOG_FILE"
  fi
fi

info "npm run build — esto SÍ va a mostrar el error completo si falla..."
BUILD_EXIT=0
npm run build 2>&1 | tee -a "$LOG_FILE" || BUILD_EXIT=$?

if [ "$BUILD_EXIT" -eq 137 ] || [ "$BUILD_EXIT" -eq 134 ]; then
  fail "El build murió por FALTA DE MEMORIA (código $BUILD_EXIT). Esto es lo que probablemente ha estado pasando siempre en Termux. Solución: cerrar otras apps antes de compilar, o compilar con más swap. No lo intentes de nuevo sin resolver esto — seguirá fallando igual."
fi
if [ "$BUILD_EXIT" -ne 0 ]; then
  fail "npm run build terminó con error (código $BUILD_EXIT). Mira las últimas líneas arriba o en $LOG_FILE — ese es el error real, no lo ignores."
fi

[ -d "$DIST_DIR" ] || fail "npm run build 'tuvo éxito' pero dist/ no existe. Algo raro pasó — revisa $LOG_FILE."

ok "npm run build terminó sin errores."
echo ""

# ── Verificación real: ¿el JS compilado tiene el código del micrófono? ──
info "Buscando el código del micrófono dentro de dist/assets/*.js..."
FOUND_ALL=1
for marker in "${MARKERS[@]}"; do
  if grep -rl -- "$marker" "$DIST_DIR"/assets/*.js >/dev/null 2>&1; then
    ok "Encontrado: \"$marker\""
  else
    echo "❌ NO encontrado: \"$marker\""
    FOUND_ALL=0
  fi
done

echo ""
if [ "$FOUND_ALL" -ne 1 ]; then
  fail "El build se generó pero NO contiene el código del micrófono/voz. Esto significa que tauri-frontend/src NO tiene la versión esperada (revisa 'git log -1' arriba, y si el pull realmente trajo los cambios de FloatingSol.tsx)."
fi

ok "El build nuevo SÍ contiene el micrófono y el reconocimiento de voz."

# Copiar assets estáticos (igual que hace omni.sh)
[ -f "$ROOT/assets/sol_avatar.jpg" ] && cp "$ROOT/assets/sol_avatar.jpg" "$DIST_DIR/" && ok "sol_avatar.jpg copiado"
[ -f "$ROOT/backend/static/sol_avatar.png" ] && cp "$ROOT/backend/static/sol_avatar.png" "$DIST_DIR/" && ok "sol_avatar.png copiado"
[ -f "$ROOT/backend/static/sol.html" ] && cp "$ROOT/backend/static/sol.html" "$DIST_DIR/" && ok "sol.html copiado"

echo ""
echo "════════════════════════════════════════════"
ok "TODO VERIFICADO. Ahora sí reinicia el servidor:"
echo "   bash omni.sh start"
echo "Y en el navegador: borra caché (una vez) y abre localhost:8001"
echo "════════════════════════════════════════════"
