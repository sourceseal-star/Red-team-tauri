#!/usr/bin/env bash
# =====================================================================
# SourceSeal Console — QUICKSTART
# Arranque + instalación + smoke tests en un solo comando
# Uso:
#   bash quickstart.sh            # Instalar + arrancar + testear
#   bash quickstart.sh --test-only # Solo tests (requiere backend corriendo)
# =====================================================================
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
BASE="http://127.0.0.1:${PORT}"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[0;34m'; N='\033[0m'

banner() {
  echo ""
  echo -e "${C}════════════════════════════════════════════════════${N}"
  echo -e "${G}  $1${N}"
  echo -e "${C}════════════════════════════════════════════════════${N}"
}

ok()   { echo -e "  ${G}✓${N} $1"; }
fail() { echo -e "  ${R}✗${N} $1"; }
warn() { echo -e "  ${Y}⚠${N} $1"; }

PASS=0; FAIL=0

# ─── MODO TEST-ONLY ────────────────────────────────────────────────────
TEST_ONLY=0
if [ "$1" = "--test-only" ]; then
  TEST_ONLY=1
  banner "SourceSeal Console — Smoke Tests"
  # Intentar obtener token
  if [ -f "$ROOT/.env" ]; then
    source "$ROOT/.env" 2>/dev/null || true
  fi
  TOKEN="${REDTEAM_API_KEY:-}"
  AUTH_HEADER=""
  if [ -n "$TOKEN" ]; then
    AUTH_HEADER="Authorization: Bearer ${TOKEN}"
  fi
  goto_tests=1
else
  goto_tests=0
fi

# ─── INSTALACIÓN ──────────────────────────────────────────────────────
if [ "$TEST_ONLY" -eq 0 ]; then
  banner "SourceSeal Console — Quickstart Completo"

  # 1. Detectar entorno
  echo -e "${C}[1/6] Detectando entorno...${N}"
  if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 --version 2>&1)
    ok "Python: $PY_VER"
  else
    fail "Python3 no encontrado. Instala: pkg install python (Termux) o apt install python3 (Linux)"
    exit 1
  fi

  if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node --version 2>&1)
    ok "Node.js: $NODE_VER"
  else
    fail "Node.js no encontrado. Instala: pkg install nodejs-lts (Termux) o apt install nodejs (Linux)"
    exit 1
  fi
  ok "Entorno: $(uname -s) $(uname -m)"

  # 2. Dependencias Python
  echo -e "${C}[2/6] Verificando dependencias Python...${N}"
  TERMUX_ANDROID=0
  if [ -d "/data/data/com.termux" ]; then
    TERMUX_ANDROID=1
  fi
  PYTHON_IMPORTS="import fastapi, uvicorn, httpx, pydantic, aiohttp"
  PYTHON_PACKAGES=(fastapi uvicorn httpx pydantic aiohttp dnspython beautifulsoup4 python-whois)
  if [ "$TERMUX_ANDROID" -eq 0 ]; then
    PYTHON_IMPORTS="$PYTHON_IMPORTS, psutil"
    PYTHON_PACKAGES+=(psutil)
  else
    warn "Android/Termux detectado: psutil se omite (no compila con Python 3.14)."
  fi
  python3 -c "$PYTHON_IMPORTS" 2>/dev/null && {
    ok "Dependencias Python OK"
  } || {
    warn "Instalando dependencias Python faltantes..."
    if [ "$TERMUX_ANDROID" -eq 0 ] && [ -f "$ROOT/backend/requirements.txt" ]; then
      pip install -r "$ROOT/backend/requirements.txt" 2>&1 | tail -3
    else
      pip install -q "${PYTHON_PACKAGES[@]}" 2>&1 | tail -3
    fi
    ok "Dependencias Python instaladas"
  }

  # 3. .env
  echo -e "${C}[3/6] Configurando .env...${N}"
  if [ ! -f "$ROOT/.env" ]; then
    API_KEY=$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))")
    cat > "$ROOT/.env" << EOF
REDTEAM_API_KEY=${API_KEY}
HOST=0.0.0.0
PORT=${PORT}
ALLOWED_ORIGINS=http://localhost:${PORT},http://127.0.0.1:${PORT}
ABUSEIPDB_KEY=
SHODAN_API_KEY=
HUNTER_API_KEY=
EOF
    chmod 600 "$ROOT/.env"
    ok ".env creado — API Key: ${API_KEY:0:8}..."
  else
    ok ".env ya existe (preservado)"
  fi
  source "$ROOT/.env" 2>/dev/null || true

  # 4. Frontend
  echo -e "${C}[4/6] Compilando frontend...${N}"
  cd "$ROOT/tauri-frontend"
  if [ ! -d "node_modules" ]; then
    warn "Instalando dependencias Node (puede tardar 1-2 min)..."
    npm install --legacy-peer-deps 2>&1 | tail -5
  fi
  if [ ! -d "dist" ] || [ ! -f "dist/index.html" ]; then
    npm run build 2>&1 | tail -5
    ok "Frontend compilado"
  else
    ok "Frontend ya compilado (dist/ existe)"
  fi
  cd "$ROOT"

  # 5. Matar procesos anteriores + levantar backend
  echo -e "${C}[5/6] Levantando backend...${N}"
  pkill -9 -f "dashboard_server.py" 2>/dev/null || true
  sleep 1

  cd "$ROOT/redteam/scripts"
  export PORT=$PORT HOST=$HOST PYTHONUNBUFFERED=1
  export $(grep -v '^#' "$ROOT/.env" | xargs 2>/dev/null || true)

  nohup python3 dashboard_server.py > "$ROOT/sourceSeal_backend.log" 2>&1 &
  BACKEND_PID=$!
  cd "$ROOT"
  ok "Backend PID: $BACKEND_PID"

  # Esperar a que arranque
  READY=0
  for i in $(seq 1 20); do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      fail "El proceso backend murió. Revisa $ROOT/sourceSeal_backend.log"
      tail -20 "$ROOT/sourceSeal_backend.log"
      exit 1
    fi
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
      READY=1
      ok "Backend respondiendo en :${PORT}"
      break
    fi
    sleep 1
  done

  if [ "$READY" -ne 1 ]; then
    fail "El backend no respondió tras 20s"
    echo "Logs:"
    tail -20 "$ROOT/sourceSeal_backend.log"
    exit 1
  fi

  # Token para tests
  TOKEN="${REDTEAM_API_KEY:-}"
  AUTH_HEADER=""
  if [ -n "$TOKEN" ]; then
    AUTH_HEADER="Authorization: Bearer ${TOKEN}"
  fi

  # 6. Smoke tests
  echo -e "${C}[6/6] Ejecutando smoke tests...${N}"
fi

# ════════════════════════════════════════════════════════════════════
# SMOKE TESTS
# ════════════════════════════════════════════════════════════════════

run_test() {
  local name="$1"
  local url="$2"
  local method="${3:-GET}"
  local body="$4"
  local expected="${5:-200}"
  local needs_auth="${6:-true}"

  local headers=""
  if [ "$needs_auth" = "true" ] && [ -n "$AUTH_HEADER" ]; then
    headers="-H \"$AUTH_HEADER\""
  fi
  if [ -n "$body" ]; then
    headers="$headers -H \"Content-Type: application/json\" -d '$body'"
  fi

  local cmd="curl -s -o /dev/null -w \"%{http_code}\" -X $method $headers \"$url\" --max-time 10 2>/dev/null"
  local code=$(eval "$cmd" 2>/dev/null || echo "000")

  if [ "$code" = "$expected" ]; then
    ok "$name → $code"
    PASS=$((PASS+1))
  elif [ "$code" = "000" ]; then
    fail "$name → SIN RESPUESTA"
    FAIL=$((FAIL+1))
  else
    warn "$name → $code (esperado $expected)"
    FAIL=$((FAIL+1))
  fi
}

echo ""
echo -e "${B}── Health ──${N}"
run_test "GET /api/health"     "$BASE/api/health"     "GET" "" "200" "false"
run_test "GET /health"        "$BASE/health"          "GET" "" "200" "false"

echo ""
echo -e "${B}── ARTO ──${N}"
run_test "GET /api/arto/status"      "$BASE/api/arto/status"      "GET"
run_test "GET /api/arto/stats"       "$BASE/api/arto/stats"       "GET"
run_test "GET /api/arto/operations"  "$BASE/api/arto/operations"  "GET"
run_test "GET /api/arto/templates"   "$BASE/api/arto/templates"   "GET"

echo ""
echo -e "${B}── Interceptor ──${N}"
run_test "GET /api/interceptor/stats"       "$BASE/api/interceptor/stats"       "GET"
run_test "GET /api/interceptor/flows"       "$BASE/api/interceptor/flows"       "GET"
run_test "GET /api/interceptor/alerts"      "$BASE/api/interceptor/alerts"      "GET"
run_test "POST /api/interceptor/analyze/user-agent" "$BASE/api/interceptor/analyze/user-agent" "POST" '{"user_agent":"nmap/7.94"}' "200"
run_test "POST /api/interceptor/decode"     "$BASE/api/interceptor/decode"      "POST" '{"payload":"SGVsbG8=","encoding":"base64"}' "200"
run_test "GET /api/interceptor/capture/status" "$BASE/api/interceptor/capture/status" "GET"

echo ""
echo -e "${B}── OSINT ──${N}"
run_test "GET /api/osint/whois/example.com"  "$BASE/api/osint/whois/example.com"  "GET"

echo ""
echo -e "${B}── Network ──${N}"
run_test "GET /api/network/info"     "$BASE/api/network/info"     "GET"
run_test "GET /api/services"        "$BASE/api/services"         "GET"
run_test "GET /api/resources"       "$BASE/api/resources"        "GET"
run_test "GET /api/ops/config"      "$BASE/api/ops/config"        "GET"

echo ""
echo -e "${B}── Geo / Intel ──${N}"
run_test "GET /api/geo?ip=8.8.8.8"   "$BASE/api/geo?ip=8.8.8.8"   "GET"
run_test "GET /api/intel?ip=8.8.8.8" "$BASE/api/intel?ip=8.8.8.8" "GET"

echo ""
echo -e "${B}── Honeypot ──${N}"
run_test "GET /api/honeypot/status"  "$BASE/api/honeypot/status"  "GET"

# ─── RESUMEN ──────────────────────────────────────────────────────────
echo ""
echo -e "${C}════════════════════════════════════════════════════${N}"
echo -e "${G}  RESULTADOS: ${PASS} OK · ${FAIL} FAIL · $((PASS+FAIL)) TOTAL${N}"
echo -e "${C}════════════════════════════════════════════════════${N}"

if [ "$FAIL" -eq 0 ]; then
  echo -e "${G}  ✅ TODOS LOS TESTS PASARON${N}"
else
  echo -e "${Y}  ⚠ $FAIL test(s) fallaron — revisa los endpoints marcados arriba${N}"
fi

if [ "$TEST_ONLY" -eq 0 ]; then
  echo ""
  echo -e "${G}╔══════════════════════════════════════════════════╗${N}"
  echo -e "${G}║  ✅ SOURCESEAL CONSOLE LISTO                     ║${N}"
  echo -e "${G}║                                                  ║${N}"
  echo -e "${G}║  Navegador:  http://localhost:${PORT}             ║${N}"
  echo -e "${G}║  API:        http://localhost:${PORT}/api/health  ║${N}"
  echo -e "${G}║  Docs:       http://localhost:${PORT}/docs        ║${N}"
  echo -e "${G}║                                                  ║${N}"
  echo -e "${G}║  Detener:    pkill -f dashboard_server.py        ║${N}"
  echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
fi
