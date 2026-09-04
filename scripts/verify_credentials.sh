#!/usr/bin/env bash
# Verifica que las credenciales críticas existan en .env — SIN imprimir sus
# valores. Solo dice "presente (N caracteres)" o "FALTA". Uso normal:
#   bash scripts/verify_credentials.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ No existe .env en $ROOT — nada que verificar."
  exit 1
fi

check() {
  local key="$1"
  local required="${2:-recomendada}"
  local val
  val="$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
  if [ -z "$val" ]; then
    if [ "$required" = "requerida" ]; then
      echo "❌ $key: FALTA (requerida)"
    else
      echo "⚠️  $key: no configurada (opcional)"
    fi
  else
    echo "✅ $key: presente (${#val} caracteres)"
  fi
}

echo "════════════════════════════════════════════"
echo " Verificación de credenciales — $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════"
echo ""
echo "── Dashboard / Auth ──"
check ADMIN_EMAIL requerida
check ADMIN_PASSWORD requerida
check API_KEY requerida
echo ""
echo "── Nexus (independiente, puerto 8004 — NO se toca) ──"
check NEXUS_USER requerida
check NEXUS_PASS requerida
echo ""
echo "── Telegram ──"
check TELEGRAM_BOT_TOKEN requerida
echo ""
echo "── Seal IA ──"
check SEAL_NETWORK opcional
check SEAL_ENABLED opcional
check LLM_API_KEY opcional
echo ""
echo "── Permisos del archivo .env ──"
PERMS="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%Lp' "$ENV_FILE" 2>/dev/null || echo '?')"
if [ "$PERMS" = "600" ]; then
  echo "✅ Permisos: $PERMS (correcto — solo el propietario puede leerlo)"
else
  echo "⚠️  Permisos: $PERMS (se recomienda 600 → chmod 600 .env)"
fi
echo ""
echo "════════════════════════════════════════════"
echo " password.json (login del dashboard): $([ -f "$ROOT/redteam/scripts/.auth/password.json" ] && echo "existe" || echo "no existe — usará ADMIN_PASSWORD de .env")"
echo "════════════════════════════════════════════"
