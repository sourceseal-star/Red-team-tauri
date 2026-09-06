#!/data/data/com.termux/files/usr/bin/bash
# sol_abre.sh v5 — Siempre termina con Sol enfrente, por cualquier camino.
#   A: clave en algún .env → enlace mágico de la puerta pública (cookie 30 días)
#   B: sin clave → su casa local localhost:8006 (no pide clave)
#   C: nada corriendo → instrucción única de arranque

FILES="$HOME/sol/.env $HOME/Red-team-tauri/.env $HOME/Red-team-tauri/backend/.env $HOME/.sol/.env $HOME/.env"
URL_PUB="https://sol--supermancareman.replit.app"

get_key() {
  [ -f "$1" ] || return 1
  grep 'SOL_API_KEY' "$1" 2>/dev/null | grep -v '^[[:space:]]*#' | head -1 | \
    sed 's/^[[:space:]]*export[[:space:]]*//' | \
    cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]'
}

open_url() {
  if command -v termux-open-url >/dev/null 2>&1; then termux-open-url "$1"
  else echo "Abre este enlace (tócalo si sale azul):"; echo "  $1"; fi
}

KEY=""; FOUND_IN=""
for f in $FILES; do
  v=$(get_key "$f"); if [ -n "$v" ]; then KEY="$v"; FOUND_IN="$f"; break; fi
done

echo "☀️ sol_abre — buscando la puerta más cercana a Sol…"

if [ -n "$KEY" ]; then
  echo "✓ Clave encontrada en: $FOUND_IN"
  echo "☀️ Abriendo la puerta pública (cookie de 30 días)…"
  open_url "$URL_PUB/?key=$KEY"
  exit 0
fi

echo "· Sin clave en los .env — probando su casa local…"
if curl -s -m 4 http://localhost:8006/api/health 2>/dev/null | grep -q '"ok"\|status.*ok\|service.*sol'; then
  echo "✓ Su servidor local está vivo — abriendo…"
  open_url "http://localhost:8006"
  exit 0
fi

cat <<'EOF'
💔 Su servidor local no está corriendo. UNA sola línea lo despierta todo:

  cd ~/sol && git pull origin main && pkill -f sol_api.py; nohup python3 sol_api.py >> ~/.sol/sol_api.log 2>&1 &

Y después vuelve a correr:  bash sol_abre.sh

(Para la versión pública de Replit, plan manual: en la app de Replit →
Tools → Secrets → copiar SOL_API_KEY → pegarla en el campo de:)
EOF
echo "  $URL_PUB"
