#!/data/data/com.termux/files/usr/bin/bash
# SourceSeal — sincronización segura de los repositorios en Termux
#
# Uso:
#   bash ~/Red-team-tauri/scripts/termux/sync_repositories.sh
#
# Por defecto usa SSH para no poner tokens en URLs, historiales ni procesos.
# Se puede cambiar el nombre de las carpetas con REDTEAM_DIR y COMMANDER_DIR.
set -Eeuo pipefail

REDTEAM_URL="${REDTEAM_REPO_URL:-git@github.com:sourceseal-star/Red-team-tauri.git}"
COMMANDER_URL="${COMMANDER_REPO_URL:-git@github.com:sourceseal-star/commander.git}"
REDTEAM_DIR="${REDTEAM_DIR:-$HOME/Red-team-tauri}"
COMMANDER_DIR="${COMMANDER_DIR:-$HOME/commander}"
STAMP="$(date +%Y%m%d-%H%M%S)"

say() { printf '[sync] %s\n' "$*"; }
fail() { printf '[sync] ERROR: %s\n' "$*" >&2; exit 1; }

for command in git ssh python3; do
  command -v "$command" >/dev/null 2>&1 || fail "Falta '$command'. Ejecuta: pkg install -y git openssh python"
done

uses_ssh_url() {
  case "$1" in
    git@*|ssh://*) return 0 ;;
    *) return 1 ;;
  esac
}

if uses_ssh_url "$REDTEAM_URL" || uses_ssh_url "$COMMANDER_URL"; then
  say "Comprobando autenticación SSH de GitHub..."
  SSH_CHECK="$(ssh -o BatchMode=yes -o ConnectTimeout=10 -T git@github.com 2>&1 || true)"
  if ! printf '%s\n' "$SSH_CHECK" | grep -Eqi 'successfully authenticated|Hi sourceseal-star'; then
    printf '\n'
    printf 'No hay una sesión SSH válida con GitHub.\n'
    printf 'Añade esta clave pública en GitHub → Settings → SSH and GPG keys:\n\n'
    if [ -f "$HOME/.ssh/id_ed25519.pub" ]; then
      cat "$HOME/.ssh/id_ed25519.pub"
    else
      printf '  ssh-keygen -t ed25519 -C "termux" -f ~/.ssh/id_ed25519\n'
      printf '  cat ~/.ssh/id_ed25519.pub\n'
    fi
    printf '\nDespués prueba: ssh -T git@github.com\n'
    printf 'O ejecuta el sincronizador con URLs HTTPS explícitas si el repositorio es público.\n'
    exit 2
  fi
  say "SSH de GitHub: OK"
else
  say "URLs HTTPS explícitas: omitiendo comprobación SSH"
fi

backup_dirty_work() {
  local dir="$1"
  local label="$2"
  if [ -n "$(git -C "$dir" status --porcelain --untracked-files=all)" ]; then
    say "$label: guardando cambios locales en stash..."
    git -C "$dir" stash push --include-untracked \
      -m "Termux backup before sync $STAMP" >/dev/null
    say "$label: cambios guardados; se pueden recuperar con git stash list/pop"
  fi
}

backup_nested_submodules() {
  local dir="$1"
  local label="$2"
  local gitlink_paths
  local nested_path
  local nested_dir
  local nested_status
  local expected
  local current
  local backup_branch

  # git stash del repositorio padre no incluye cambios dentro de submódulos.
  # Usamos los gitlinks del índice directamente porque algunos repositorios
  # Termux no conservan .gitmodules, aunque sigan registrando los anidados.
  gitlink_paths="$(git -C "$dir" ls-files -s | awk '$1 == "160000" {print $4}')"
  if [ -z "$gitlink_paths" ]; then
    return
  fi

  while IFS= read -r nested_path; do
    [ -n "$nested_path" ] || continue
    nested_dir="$dir/$nested_path"
    if [ ! -e "$nested_dir/.git" ]; then
      fail "$label/$nested_path: gitlink sin repositorio local; no lo tocaré"
    fi

    nested_status="$(git -C "$nested_dir" status --porcelain --untracked-files=all)"
    if [ -n "$nested_status" ]; then
      git -C "$nested_dir" stash push --include-untracked \
        -m "Termux nested backup before sync $STAMP" >/dev/null
      say "$label/$nested_path: cambios guardados en stash"
    fi

    expected="$(git -C "$dir" ls-tree HEAD -- "$nested_path" | awk '{print $3}')"
    current="$(git -C "$nested_dir" rev-parse HEAD)"
    if [ "$current" != "$expected" ]; then
      backup_branch="backup/termux-$STAMP"
      if git -C "$nested_dir" show-ref --verify --quiet "refs/heads/$backup_branch"; then
        backup_branch="$backup_branch-submodule"
      fi
      git -C "$nested_dir" branch "$backup_branch" HEAD
      say "$label/$nested_path: respaldo creado en rama $backup_branch"
    fi

    if ! git -C "$nested_dir" cat-file -e "${expected}^{commit}" 2>/dev/null; then
      say "$label/$nested_path: obteniendo el commit requerido desde su remoto..."
      git -C "$nested_dir" fetch --all --prune
    fi
    if ! git -C "$nested_dir" cat-file -e "${expected}^{commit}" 2>/dev/null; then
      fail "$label/$nested_path: el commit $expected no existe en el clon ni en sus remotos; no haré reset"
    fi

    git -C "$nested_dir" reset --hard "$expected" >/dev/null
  done <<EOF
$gitlink_paths
EOF

  git -C "$dir" submodule update --init --recursive --force 2>/dev/null || true
  say "$label: submódulos locales respaldados y alineados"
}

sync_repo() {
  local label="$1"
  local url="$2"
  local dir="$3"

  say "===== $label ====="
  if [ ! -d "$dir/.git" ]; then
    if [ -e "$dir" ]; then
      fail "$dir existe pero no es un repositorio Git; muévelo o define ${label}_DIR antes de continuar"
    fi
    say "$label: clonando..."
    git clone "$url" "$dir"
  else
    git -C "$dir" remote set-url origin "$url"

    if [ -d "$dir/.git/rebase-merge" ] || [ -d "$dir/.git/rebase-apply" ]; then
      say "$label: rebase incompleta detectada; abortándola antes de sincronizar"
      git -C "$dir" rebase --abort
    fi
    if [ -f "$dir/.git/MERGE_HEAD" ]; then
      say "$label: merge incompleto detectado; abortándolo antes de sincronizar"
      git -C "$dir" merge --abort
    fi

    backup_dirty_work "$dir" "$label"
    backup_nested_submodules "$dir" "$label"
    git -C "$dir" fetch origin --prune

    if ! git -C "$dir" show-ref --verify --quiet refs/heads/main; then
      git -C "$dir" switch -c main --track origin/main
    else
      git -C "$dir" switch main
    fi

    remaining="$(git -C "$dir" status --porcelain=v1 --untracked-files=all)"
    if [ -n "$remaining" ]; then
      printf '%s\n' "$remaining" >&2
      fail "$label: quedaron cambios después del respaldo; no se hará reset"
    fi

    if [ "$(git -C "$dir" rev-parse HEAD)" != "$(git -C "$dir" rev-parse origin/main)" ]; then
      local backup_branch="backup/termux-$STAMP"
      git -C "$dir" branch "$backup_branch" HEAD
      say "$label: respaldo creado en rama $backup_branch"
      git -C "$dir" reset --hard origin/main
      git -C "$dir" submodule update --init --recursive --force
      backup_nested_submodules "$dir" "$label"
    else
      say "$label: ya estaba actualizado"
    fi

    remaining="$(git -C "$dir" status --porcelain=v1 --untracked-files=all)"
    if [ -n "$remaining" ]; then
      printf '%s\n' "$remaining" >&2
      fail "$label: quedaron cambios después de actualizar; no continuaré con dependencias"
    fi
  fi

  say "$label: $(git -C "$dir" log -1 --oneline)"
}

sync_repo "Red-team-tauri" "$REDTEAM_URL" "$REDTEAM_DIR"
sync_repo "commander" "$COMMANDER_URL" "$COMMANDER_DIR"

if [ -f "$COMMANDER_DIR/requirements.txt" ]; then
  say "Instalando dependencias declaradas por commander..."
  python3 -m pip install -r "$COMMANDER_DIR/requirements.txt"
fi

if ! python3 -c 'from cryptography.fernet import Fernet' >/dev/null 2>&1; then
  say "cryptography no puede importarse; reinstalando cryptography y cffi para el Python actual..."
  python3 -m pip install --upgrade --force-reinstall --no-cache-dir cryptography cffi
else
  say "cryptography: OK"
fi

printf '\n'
say "Sincronización terminada."
say "Red-team-tauri: $REDTEAM_DIR"
say "commander:       $COMMANDER_DIR"
say "Para arrancar SourceSeal: bash \"$REDTEAM_DIR/start-termux.sh\""
say "Para revisar el otro proyecto: cd \"$COMMANDER_DIR\" && python3 commander.py"