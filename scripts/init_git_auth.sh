#!/bin/bash
# Restaura autenticación de GitHub después de cada reinicio del contenedor.
# Se ejecuta automáticamente desde replit_start.sh.

if [ -z "$GITHUB_TOKEN" ]; then
  echo "[git-auth] ADVERTENCIA: GITHUB_TOKEN no está configurado. Git push no funcionará."
  exit 0
fi

REPO_URL="https://sourceseal-star:${GITHUB_TOKEN}@github.com/sourceseal-star/Red-team-tauri.git"

# Embeber token en remote URL (solo en .git/config local, nunca se sube a GitHub)
git -C "$(dirname "$0")/.." remote set-url origin "$REPO_URL" 2>/dev/null || true

# Configurar credential helper como respaldo
git -C "$(dirname "$0")/.." config credential.helper store 2>/dev/null || true
echo "https://sourceseal-star:${GITHUB_TOKEN}@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials

echo "[git-auth] Autenticación de GitHub restaurada -> sourceseal-star/Red-team-tauri"
