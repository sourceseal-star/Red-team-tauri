#!/data/data/com.termux/files/usr/bin/bash
# backup_total.sh — Snapshot cifrado del ecosistema SourceSeal
set -euo pipefail
FECHA=$(date +%Y%m%d_%H%M)
[ -d "$HOME/storage/shared" ] && DEST="$HOME/storage/shared/SourceSeal_Backups" || DEST="$HOME/SourceSeal_Backups"
mkdir -p "$DEST"
TMP="$HOME/.backup_$FECHA.tgz"

# 1. Inventario de paquetes (para reconstruir rápido)
pkg list-installed 2>/dev/null | cut -d/ -f1 > "$HOME/.pkgs_$FECHA.txt" || true
pip freeze > "$HOME/.pip_$FECHA.txt" 2>/dev/null || true

# 2. Tar del ecosistema (excluye node_modules)
tar -czf "$TMP" -C "$HOME" \
  --exclude="*/node_modules" --exclude="*/.cache" --exclude="*/dist" \
  Red-team-tauri commander .c2 .sourceseal 2>/dev/null

# 3. Cifrado AES-256 con TU passphrase
read -rsp "🔒 Passphrase del respaldo: " PP; echo
openssl enc -aes-256-cbc -salt -pbkdf2 -in "$TMP" -out "$DEST/sourceseal_$FECHA.aes" -pass pass:"$PP"
rm -f "$TMP"
echo "✅ Respaldo cifrado: $DEST/sourceseal_$FECHA.aes"
echo "📦 Este archivo PUEDE subir a Drive/Dropbox: sin tu passphrase es ruido."
