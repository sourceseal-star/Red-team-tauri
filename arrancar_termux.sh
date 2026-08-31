#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
# ARRANQUE LOCAL SEGURO — no sincroniza ni modifica el repositorio
#
# Levanta el código que ya está en el dispositivo:
#   :8001 Dashboard + Commander in-process
#   :8002 GHOST HUNTER PHANTOM
#
# Uso:
#   bash arrancar_termux.sh
#   COMMANDER_DIR="$HOME/commander" bash arrancar_termux.sh
# =====================================================================
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"

die() {
  printf '[arranque][ERROR] %s\n' "$*" >&2
  exit 1
}

printf '\n'
printf '%s\n' '============================================================'
printf '%s\n' ' SourceSeal — arranque local seguro'
printf '%s\n' ' No sincroniza, no hace pull y no borra cambios locales'
printf '%s\n' '============================================================'

command -v python3 >/dev/null 2>&1 || die "python3 no está instalado"
command -v curl >/dev/null 2>&1 || die "curl no está instalado"
[ -f "$ROOT/iniciar_unificado.sh" ] || die "No encuentro iniciar_unificado.sh en $ROOT"
[ -f "$ROOT/redteam/scripts/dashboard_server.py" ] || die "Falta el backend del dashboard"
[ -d "$ROOT/ghost_hunter_phantom" ] || die "Falta el módulo PHANTOM"

if [ ! -f "$COMMANDER_DIR/commander.py" ] && [ -f "$ROOT/commander/commander.py" ]; then
  COMMANDER_DIR="$ROOT/commander"
fi

if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
else
  printf '%s\n' '[arranque][WARN] No existe .env; el dashboard puede requerir configuración manual.'
fi

export COMMANDER_DIR
export PYTHONUNBUFFERED=1

if [ -f "$COMMANDER_DIR/commander.py" ]; then
  printf '[arranque] Commander: %s\n' "$COMMANDER_DIR"
else
  printf '%s\n' "[arranque][WARN] Commander no encontrado en $COMMANDER_DIR"
  printf '%s\n' '[arranque][WARN] Se levantará Dashboard + PHANTOM sin sus rutas.'
fi

exec bash "$ROOT/iniciar_unificado.sh"