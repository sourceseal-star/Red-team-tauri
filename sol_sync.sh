#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════════════
#  SOL_SYNC.SH — Sincronizar el repo sol (privado) con Red-team-tauri
#  Copia el sol.html y avatar del repo sol al backend/static del Tower
#
#  Uso:
#    bash sol_sync.sh pull   # baja cambios del repo sol y los copia
#    bash sol_sync.sh push   # empuja cambios locales al repo sol
# ════════════════════════════════════════════════════════════════════
set -e
RT="$(cd "$(dirname "$0")" && pwd)"
SOL_REPO="$HOME/sol"

R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; N='\033[0m'

echo -e "${C}╔══════════════════════════════════════════════╗${N}"
echo -e "${C}║  SOL_SYNC — sol repo ↔ Red-team-tauri       ║${N}"
echo -e "${C}╚══════════════════════════════════════════════╝${N}"

if [ ! -d "$SOL_REPO/.git" ]; then
  echo -e "${Y}⚠️  Repo sol no encontrado en $SOL_REPO${N}"
  echo -e "  Clona primero: git clone https://github.com/sourceseal-star/sol.git ~/sol"
  exit 1
fi

ACTION="${1:-pull}"

case "$ACTION" in
  pull)
    echo -e "${C}→ Actualizando repo sol...${N}"
    cd "$SOL_REPO"
    git fetch origin
    git reset --hard origin/main 2>&1 | tail -2
    echo -e "${G}✓ Repo sol: $(git log --oneline -1)${N}"

    echo ""
    echo -e "${C}→ Copiando sol.html y avatar a backend/static/...${N}"
    mkdir -p "$RT/backend/static"
    cp "$SOL_REPO/static/sol.html" "$RT/backend/static/sol.html"
    cp "$SOL_REPO/static/sol_avatar.jpg" "$RT/backend/static/sol_avatar.jpg" 2>/dev/null || true
    cp "$SOL_REPO/static/sol_avatar.png" "$RT/backend/static/sol_avatar.png" 2>/dev/null || true

    echo -e "${C}→ Copiando a tauri-frontend/public/...${N}"
    mkdir -p "$RT/tauri-frontend/public"
    cp "$SOL_REPO/static/sol.html" "$RT/tauri-frontend/public/sol.html"
    cp "$SOL_REPO/static/sol_avatar.jpg" "$RT/tauri-frontend/public/sol_avatar.jpg" 2>/dev/null || true

    echo ""
    echo -e "${G}✅ Sincronización completa${N}"
    echo -e "  sol.html → backend/static/ y tauri-frontend/public/"
    echo -e "  Rebuild con: cd tauri-frontend && npm run build"
    echo -e "  Reiniciar backend para que sirva el nuevo sol.html"
    ;;
  push)
    echo -e "${Y}→ Copiando desde backend/static al repo sol...${N}"
    cp "$RT/backend/static/sol.html" "$SOL_REPO/static/sol.html" 2>/dev/null || true
    cp "$RT/backend/static/sol_avatar.jpg" "$SOL_REPO/static/sol_avatar.jpg" 2>/dev/null || true
    cd "$SOL_REPO"
    git add -A
    git commit -m "sync: actualizado desde Red-team-tauri" 2>/dev/null || echo "Sin cambios"
    git push origin main
    echo -e "${G}✅ Pushado al repo sol${N}"
    ;;
  *)
    echo "Uso: bash sol_sync.sh [pull|push]"
    exit 1
    ;;
esac
