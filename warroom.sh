#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  🛰️ WARROOM.SH — ¿Por qué localhost:8001 en negro? En 30 segundos.
#
#  Diagnostica los 3 sospechosos, en orden:
#    1. ¿El repo está al día? (bundle nuevo vs bundle de la era vieja)
#    2. ¿El servidor :8001 vive y sirve el index correcto?
#    3. ¿El bundle que sirve contiene el War Room de verdad?
#
#  Si TODO sale ✅ y aun así ves negro → el culpable es el NAVEGADOR
#  (index viejo cacheado que apunta a assets que ya no existen).
#  Este script te lo dice al final, con el paso exacto.
#
#  Uso:  cd ~/Red-team-tauri && bash warroom.sh
# ═══════════════════════════════════════════════════════════════════
RT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
DIST="$RT_DIR/tauri-frontend/dist"
URL="http://127.0.0.1:8001/"
MARKER="KRAKEN"
PASS=0; FAIL=0
ok(){  PASS=$((PASS+1)); echo "✅ $1"; }
bad(){ FAIL=$((FAIL+1)); echo "❌ $1"; echo "   └─ $2"; }

echo "══════════════════════════════════════"
echo "  🛰️ WAR ROOM — diagnóstico $(date '+%H:%M:%S')"
echo "══════════════════════════════════════"

# ── 1. ¿Repo al día? ──
cd "$RT_DIR" 2>/dev/null || { echo "❌ no encuentro el repo"; exit 1; }
git fetch origin main -q 2>/dev/null
LOCAL=$(git rev-parse --short HEAD 2>/dev/null)
REMOTE=$(git rev-parse --short origin/main 2>/dev/null)
if [ -n "$REMOTE" ] && [ "$LOCAL" = "$REMOTE" ]; then
  ok "repo al día ($LOCAL)"
else
  bad "repo atrasado (local: ${LOCAL:-?} · GitHub: ${REMOTE:-sin red})" "corre: cd ~/Red-team-tauri && git pull"
fi

# ── 2. ¿Servidor vivo? ──
CODE=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null)
if [ "$CODE" = "200" ]; then
  ok "servidor :8001 responde (200)"
else
  bad "servidor no responde (código: ${CODE:-ninguno})" "corre: bash curar.sh  (desde ~/Red-team-tauri) — enciende todo"
fi

# ── 3. ¿El index que SIRVE trae el bundle del War Room? ──
HTML=$(curl -s -m 5 "$URL" 2>/dev/null)
BUNDLE=$(echo "$HTML" | grep -o 'assets/index-[^"]*\.js' | head -1)
if [ -n "$BUNDLE" ]; then
  ok "index sirve bundle: $BUNDLE"
  if [ -f "$DIST/$BUNDLE" ]; then
    ok "ese bundle existe en disco"
    SIZE=$(wc -c < "$DIST/$BUNDLE" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt 400000 ]; then
      ok "tamaño OK ($SIZE bytes — War Room completa)"
    else
      bad "bundle chico ($SIZE bytes — es del sidebar viejo)" "cd ~/Red-team-tauri && git pull && bash curar.sh"
    fi
    if grep -q "$MARKER" "$DIST/$BUNDLE" 2>/dev/null; then
      ok "el bundle CONTIENE el War Room ($MARKER dentro)"
    else
      bad "bundle SIN War Room — es de otra era" "cd ~/Red-team-tauri && git pull && bash curar.sh"
    fi
  else
    bad "el bundle $BUNDLE NO existe en dist/" "dist incompleto: git pull; si persiste: git fetch origin && git reset --hard origin/main"
  fi
else
  bad "el index no referencia ningún bundle JS" "el servidor sirve otra cosa — captura: curl -s $URL | head -5"
fi

echo "──────────────────────────────"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ EL SERVIDOR ESTÁ PERFECTO — todo verde arriba."
  echo "   Si aun así ves negro, EL CULPABLE ES EL NAVEGADOR:"
  echo "   1. Abre pestaña de INCOGNITO → localhost:8001"
  echo "   2. ¿Cargó? → borra la caché del sitio:"
  echo "      Chrome → ⋮ → Historial → Borrar datos de navegación"
  echo "      → intervalo 'Última hora' → Borrar datos"
  echo "   3. Vuelve a abrir normal: localhost:8001"
else
  echo "❌ $FAIL problema(s) DEL LADO DEL SERVIDOR —"
  echo "   sigue la línea '└─' de cada ❌ de arriba, en orden."
fi
