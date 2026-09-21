#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════════════
# 🗼 TORRE — Diagnóstico integral del War Room
# Compañero del endpoint /api/readiness del dashboard_server.py.
#
# MODO ONLINE  (servidor arriba):  curl a /api/readiness con tu token.
# MODO OFFLINE (servidor caído):   verificaciones locales en bash.
#
# Uso:  bash torre_diagnostico.sh [token]
#       (o exporta DASH_TOKEN / API_KEY antes)
# ═══════════════════════════════════════════════════════════════════
set -u
TOKEN="${1:-${DASH_TOKEN:-${API_KEY:-}}}"
PORT="${PORT:-8001}"
BASE_URL="http://127.0.0.1:${PORT}"
REPO="$(cd "$(dirname "$0")" && pwd)"
DIST="$REPO/tauri-frontend/dist"

rojo='\033[0;31m'; verde='\033[0;32m'; amarillo='\033[1;33m'; azul='\033[1;36m'; normal='\033[0m'

banner() { echo -e "${azul}════════════════════════════════════════════════"; echo -e "  🗼 TORRE — Diagnóstico del War Room"; echo -e "════════════════════════════════════════════════${normal}"; }

# ── ¿Servidor vivo? ─────────────────────────────────────────────
if curl -s -m 3 "$BASE_URL/api/health" > /dev/null 2>&1; then
  banner
  echo -e "${verde}[ONLINE] Servidor respondiendo en :${PORT}${normal}"
  if [ -z "$TOKEN" ]; then
    echo -e "${amarillo}⚠ Sin token: pásalo como argumento o exporta DASH_TOKEN.${normal}"
    echo "   bash torre_diagnostico.sh TU_TOKEN"
    exit 1
  fi
  echo "Consultando /api/readiness..."
  RESP=$(curl -s -m 10 -H "X-API-Key: $TOKEN" "$BASE_URL/api/readiness")
  if [ -z "$RESP" ] || echo "$RESP" | grep -q '"Unauthorized"'; then
    echo -e "${rojo}✗ Token rechazado o respuesta vacía. Verifica DASH_TOKEN.${normal}"
    exit 1
  fi
  echo "$RESP" | python3 -c '
import json, sys
d = json.load(sys.stdin)
col = {"ok": "\033[0;32m✓\033[0m", "warn": "\033[1;33m⚠\033[0m", "fail": "\033[0;31m✗\033[0m"}
print(f"\n  READINESS: {d[\"ready\"]}  ({d[\"fails\"]} fallos, {d[\"warns\"]} avisos)\n")
for c in d["checks"]:
    print(f"  {col[c[\"status\"]]} {c[\"name\"]}: {c[\"detail\"]}")
    if c.get("fix"): print(f"      → fix: {c[\"fix\"]}")
' 2>/dev/null || echo "$RESP"
  exit 0
fi

# ── MODO OFFLINE: servidor caído ─────────────────────────────────
banner
echo -e "${amarillo}[OFFLINE] Servidor NO responde en :${PORT} — modo local${normal}"
echo ""
PUNTOS=0; TOTAL=0

check() {  # check <nombre> <ok(0/1)> <detalle> <fix>
  TOTAL=$((TOTAL+1))
  if [ "$2" = "0" ]; then echo -e "  ${verde}✓${normal} $1: $3"; PUNTOS=$((PUNTOS+1));
  else echo -e "  ${rojo}✗${normal} $1: $3"; [ -n "${4:-}" ] && echo "      → fix: $4"; fi
}

# 1. dist completo (guardia regla #41)
if [ -f "$DIST/index.html" ]; then
  FALTAN=""
  for ref in $(grep -o '/assets/[A-Za-z0-9_.-]*\.\(js\|css\)' "$DIST/index.html" | sed 's|/assets/||'); do
    [ -f "$DIST/assets/$ref" ] || FALTAN="$FALTAN $ref"
  done
  if [ -z "$FALTAN" ]; then check "frontend_dist" 0 "index.html + assets consistentes";
  else check "frontend_dist" 1 "faltan bundles:$FALTAN" "git pull (regla #41: dist con git add -f)"; fi
else
  check "frontend_dist" 1 "index.html no existe" "git pull + rebuild"
fi

# 2. binarios
for b in nmap ip ping; do
  if command -v "$b" > /dev/null 2>&1; then check "binario_$b" 0 "presente";
  else check "binario_$b" 1 "no está en PATH" "pkg install $b"; fi
done
command -v termux-api > /dev/null 2>&1 && check "termux_api" 0 "presente" || check "termux_api" 1 "falta" "pkg install termux-api + app Termux:API"

# 3. módulos de python importables
cd "$REPO" || exit 1
PYTHONPATH="$REPO/redteam/scripts:$REPO/redteam/modules:$REPO" python3 -c "
import sys
try:
    import fastapi, uvicorn; print('PY_OK fastapi')
except Exception as e: print('PY_FAIL fastapi', e)
try:
    sys.path.insert(0, '$REPO/redteam/modules')
    import tactical_executor; print('PY_OK tactical_executor')
except Exception as e: print('PY_FAIL tactical_executor', e)
try:
    import leviathan_core; print('PY_OK leviathan_core')
except Exception as e: print('PY_FAIL leviathan_core', e)
" 2>/dev/null | while read -r linea; do
  case "$linea" in
    PY_OK*)   echo -e "  ${verde}✓${normal} python: ${linea#PY_OK }";;
    PY_FAIL*) echo -e "  ${rojo}✗${normal} python: ${linea#PY_FAIL }";;
  esac
done

echo ""
echo -e "  RESULTADO LOCAL: ${PUNTOS}/${TOTAL}"
echo -e "${amarillo}Para la matriz completa (10 checks en vivo) arranca el servidor:${normal}"
echo "   cd ~/Red-team-tauri && pkill -9 -f dashboard_server.py; bash omni.sh start"
echo "   bash torre_diagnostico.sh TU_TOKEN"
