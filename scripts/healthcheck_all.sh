#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# HEALTHCHECK GLOBAL — SourceSeal Unified
# Verifica todos los servicios, .env y ledger SourceSeal.
# Uso: bash scripts/healthcheck_all.sh
# =====================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

ok()   { echo "  ✅ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL + 1)); }

check_http() {
    local label="$1"
    local url="$2"
    local expect="$3"   # "200" o "any"
    local code
    code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || true)"
    if [ "$expect" = "any" ]; then
        if [ "$code" != "000" ] && [ -n "$code" ]; then
            ok "$label — HTTP $code"
        else
            fail "$label — sin respuesta"
        fi
    else
        if [ "$code" = "$expect" ]; then
            ok "$label — HTTP $code"
        else
            fail "$label — HTTP ${code:-000} (esperaba $expect)"
        fi
    fi
}

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║  SOURCESEAL — HEALTHCHECK GLOBAL                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# 1. Dashboard :8001 /api/health
check_http "Dashboard  :8001 /api/health" "http://127.0.0.1:8001/api/health" "200"

# 1b. Commander in-process :8001 /api/commander/health
check_http "Commander  :8001 /api/commander/health" "http://127.0.0.1:8001/api/commander/health" "200"

# 2. GHOST PHANTOM :8002 /api/status
check_http "PHANTOM    :8002 /api/status" "http://127.0.0.1:8002/api/status" "200"

# 3. Nexus :8004 (cualquier HTTP code)
check_http "Nexus      :8004" "http://127.0.0.1:8004/" "any"

# 4. Controller :8005 /api/status
check_http "Controller :8005 /api/status" "http://127.0.0.1:8005/api/status" "200"

# 4b. Commander Dashboard standalone :8003 (si se ejecuta por separado)
check_http "Cmdr Dash :8003 (standalone)" "http://127.0.0.1:8003/" "any"

# 5. .env existe + permisos 600 + 3 variables críticas + snapshot
echo "  Archivos de configuración:"
if [ -f "$ROOT/.env" ]; then
    PERMS="$(stat -c '%a' "$ROOT/.env" 2>/dev/null || stat -f '%Lp' "$ROOT/.env" 2>/dev/null || echo "?")"
    if [ "$PERMS" = "600" ]; then
        ok ".env existe con permisos 600"
    else
        fail ".env permisos=$PERMS (esperaba 600)"
    fi
    # 5b. Verificar 3 variables críticas
    _ENV_MISSING=""
    for v in ADMIN_PASSWORD NEXUS_PASS REDTEAM_API_KEY; do
        _val="$(grep "^${v}=" "$ROOT/.env" 2>/dev/null | cut -d= -f2- | tr -d "'\"" | head -1)"
        if [ -z "$_val" ]; then
            _ENV_MISSING="$_ENV_MISSING $v"
        fi
    done
    if [ -z "$_ENV_MISSING" ]; then
        ok ".env 3 variables críticas presentes"
    else
        fail ".env variables faltantes:$_ENV_MISSING"
    fi
else
    fail ".env no encontrado — usa control_claves.sh set o scripts/restore_env.sh"
fi

# 5c. Snapshot de .env existe
_SNAP_DIR="${HOME}/.c2/snapshots"
_SNAP_COUNT=$(ls -1 "$_SNAP_DIR"/env_*.aes 2>/dev/null | wc -l)
if [ "$_SNAP_COUNT" -ge 1 ]; then
    ok "snapshots .env: $_SNAP_COUNT en ~/.c2/snapshots/"
else
    echo "  ⚠️  no hay snapshots — ejecuta: bash scripts/snapshot_env.sh"
fi

# 6. Ledger SourceSeal — buscar en .env y en archivos del repo
LEDGER_OK=0
if [ -f "$ROOT/.env" ]; then
    if grep -qi "ledger" "$ROOT/.env" 2>/dev/null; then
        LEDGER_OK=1
    fi
fi
# Buscar archivo de ledger en el repo
if [ "$LEDGER_OK" = "0" ]; then
    LEDGER_FILE="$(find "$ROOT" -maxdepth 3 \( -iname "*ledger*" -o -iname "*seal*ledger*" \) \
        2>/dev/null | grep -v node_modules | grep -v .git | head -1)"
    if [ -n "$LEDGER_FILE" ]; then
        LEDGER_OK=1
    fi
fi
if [ "$LEDGER_OK" = "1" ]; then
    ok "Ledger SourceSeal detectado"
else
    fail "Ledger SourceSeal no encontrado"
fi

echo ""
echo "────────────────────────────────────────────────────────"
echo "  RESULTADO: $PASS OK · $FAIL FALLO"
if [ "$FAIL" -gt 0 ]; then
    echo "  ⚠️  Hay servicios caídos — revisa arriba"
    exit 1
else
    echo "  ✅ Todos los servicios operativos"
    exit 0
fi
