#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  ☀️ SOL_SPRITES_SYNC.SH — Fusión de sprites entre Sol y la Torre
#  (Capa ADITIVA v5.3+ — 2026-09-07)
#
#  ¿Para qué? Los PNG de Sol viven en varios lugares y nadie quería
#  copiarlos a mano cada vez:
#    ~/sol/assets/            ← AQUÍ los sueltas tú (punto de entrada)
#    ~/sol/static/           ← de dónde sirve sol_api.py (Replit/Termux)
#    ~/Red-team-tauri/backend/static/  ← de dónde sirve la Torre (:8001)
#    ~/.sol/vault/           ← su bóveda (respaldo del sellado)
#
#  Este script toma TODOS los sol_*.png de ~/sol/assets/, copia los
#  nuevos o cambiados (compara md5, nunca machaca por deporte) a los
#  otros destinos, y commitea + empuja ambos repos a GitHub.
#
#  Uso:
#    bash sol_sprites_sync.sh            # sincroniza y empuja
#    bash sol_sprites_sync.sh --no-push  # solo copia local (sin GitHub)
#
#  curar.sh lo llama automáticamente después de sincronizar los repos
#  (bloque aditivo [2½/5] — no toca ninguna línea de la cura original).
# ═══════════════════════════════════════════════════════════════════
set -u
HOME_DIR="$HOME"
SOL_DIR="$HOME_DIR/sol"
RT_DIR="$HOME_DIR/Red-team-tauri"
VAULT="$HOME_DIR/.sol/vault"
SRC="$SOL_DIR/assets"
PUSH=1
[ "${1:-}" = "--no-push" ] && PUSH=0

NEW=0; SAME=0

if [ ! -d "$SRC" ]; then
  echo "   (~/sol/assets/ no existe todavía — nada que fundir)"
  exit 0
fi
if [ -z "$(ls "$SRC"/sol_*.png 2>/dev/null)" ]; then
  echo "   😌 Nada nuevo en ~/sol/assets/ — todo sincronizado"
  exit 0
fi

# ── Copiar cada sprite nuevo/cambiado a los 3 destinos ──
for f in "$SRC"/sol_*.png; do
  b=$(basename "$f")
  m=$(md5sum "$f" 2>/dev/null | cut -d' ' -f1)
  changed=0
  for dest in "$SOL_DIR/static" "$RT_DIR/backend/static" "$VAULT"; do
    [ -d "$dest" ] || mkdir -p "$dest" 2>/dev/null
    if [ -f "$dest/$b" ]; then
      dm=$(md5sum "$dest/$b" 2>/dev/null | cut -d' ' -f1)
      [ "$m" = "$dm" ] && continue
    fi
    cp "$f" "$dest/$b" && changed=1
  done
  if [ $changed -eq 1 ]; then
    echo "   🌹 $b fusionado (assets → static + torre + vault)"
    NEW=$((NEW+1))
  else
    SAME=$((SAME+1))
  fi
done

[ $NEW -eq 0 ] && echo "   😌 Todos los sprites ya estaban sincronizados ($SAME)" && exit 0

# ── Commit + push de ambos repos (filosofía curar.sh: nunca destructivo) ──
for d in "$SOL_DIR" "$RT_DIR"; do
  name=$(basename "$d")
  [ -d "$d/.git" ] || { echo "   ⚠️  $name no es repo — sprites copiados, pero sin git"; continue; }
  cd "$d" || continue
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A
    if git -c user.email="sol@sourceseal.star" -c user.name="Sol (sprites)" \
        commit -m "sprites: fusión v5.3+ — $NEW PNG(s) desde assets/ ($(date '+%Y-%m-%d %H:%M'))" >/dev/null 2>&1; then
      if [ $PUSH -eq 1 ]; then
        if git push origin main >/dev/null 2>&1; then
          echo "   ☁️  $name → subido a GitHub"
        else
          echo "   ⚠️  $name commit listo pero sin push (¿sin internet/token?) — curar.sh lo reintentará"
        fi
      else
        echo "   📝 $name commit local listo (--no-push)"
      fi
    fi
  fi
done

echo "   ✨ Fusión completa: $NEW nuevo(s), $SAME ya sincronizado(s)"
