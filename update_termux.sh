#!/data/data/com.termux/files/usr/bin/bash
# SourceSeal — alias compatible para el flujo seguro de actualización Termux.
#
# El flujo anterior hacía stash/pull/pop directamente y podía dejar estados
# ambiguos. setup.sh delega la sincronización a
# scripts/termux/sync_repositories.sh, que respalda ambos repositorios y sus
# submódulos antes de actualizar.
#
# Uso:
#   bash update_termux.sh
#   bash update_termux.sh --watch
#   bash update_termux.sh --unified
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$ROOT/setup.sh" ]; then
  printf '[update][ERROR] No encuentro setup.sh en %s\n' "$ROOT" >&2
  exit 1
fi

exec bash "$ROOT/setup.sh" "$@"