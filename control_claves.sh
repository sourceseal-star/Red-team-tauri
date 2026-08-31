#!/data/data/com.termux/files/usr/bin/bash
# control_claves.sh — Harold es el dueño de las credenciales
# .env es la UNICA fuente de verdad. Este script es el instrumento del operador
# para definir, verificar y recuperar sus claves. Nunca imprime secretos al arrancar.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV="$PROJECT_ROOT/.env"
AUTH_DIR="$PROJECT_ROOT/motor_cierre/backend/.auth"
AUTH_JSON="$AUTH_DIR/password.json"
BACKUP_DIR="${HOME}/.c2"
BACKUP_FILE="$BACKUP_DIR/env_respaldo.aes"

_ensure_dirs() {
  mkdir -p "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR" 2>/dev/null || true
}

_set_env_var() {
  local key="$1" val="$2"
  if [ -f "$ENV" ] && grep -q "^${key}=" "$ENV"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV"
  else
    echo "${key}=${val}" >> "$ENV"
  fi
}

_has_env_var() {
  [ -f "$ENV" ] && grep -q "^${1}=" "$ENV" && [ -n "$(grep "^${1}=" "$ENV" | cut -d= -f2)" ]
}

_gen_strong() {
  head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c "${1:-32}"
}

case "${1:-status}" in

set)
  _ensure_dirs
  echo "=== Definir credenciales del operador ==="
  echo "  Enter = generar una clave fuerte automaticamente"
  echo

  read -rsp "  ADMIN_PASSWORD (dashboard :8001): " AP; echo
  read -rsp "  NEXUS_PASS (nexus :8004): " NP; echo

  [ -z "$AP" ] && AP="$(_gen_strong 24)"
  [ -z "$NP" ] && NP="$(_gen_strong 24)"

  _set_env_var "ADMIN_PASSWORD" "$AP"
  _set_env_var "NEXUS_PASS" "$NP"
  _has_env_var "NEXUS_USER"   || _set_env_var "NEXUS_USER" "admin"
  _has_env_var "ADMIN_EMAIL"  || _set_env_var "ADMIN_EMAIL" "admin@redteam.local"
  _has_env_var "REDTEAM_API_KEY" || _set_env_var "REDTEAM_API_KEY" "$(_gen_strong 48)"

  # El hash viejo de password.json se elimina; el backend lo re-crea desde .env
  rm -f "$AUTH_JSON" 2>/dev/null || true

  chmod 600 "$ENV"

  echo
  echo "  Credenciales guardadas en .env (permisos 600):"
  echo "    ADMIN_PASSWORD  = $AP"
  echo "    NEXUS_PASS      = $NP"
  echo "    NEXUS_USER      = admin"
  echo "    ADMIN_EMAIL     = admin@redteam.local"
  echo "    REDTEAM_API_KEY = (generada, 48 chars)"
  echo

  read -rsp "  Passphrase para el respaldo cifrado: " PP; echo
  openssl enc -aes-256-cbc -salt -pbkdf2 -in "$ENV" -out "$BACKUP_FILE" -pass pass:"$PP"
  chmod 600 "$BACKUP_FILE"
  echo "  Respaldo cifrado: $BACKUP_FILE"
  echo
  echo "  Reinicia el stack para aplicar:"
  echo "    bash recon.sh restart   (o detén y arranca manualmente)"
  ;;

restore)
  _ensure_dirs
  if [ ! -f "$BACKUP_FILE" ]; then
    echo "No existe respaldo en $BACKUP_FILE"
    echo "Ejecuta primero: bash control_claves.sh set"
    exit 1
  fi
  read -rsp "Passphrase del respaldo: " PP; echo
  openssl enc -d -aes-256-cbc -salt -pbkdf2 -in "$BACKUP_FILE" -pass pass:"$PP" > /tmp/env_restored_$$
  echo
  echo "  Credenciales recuperadas (nombres, no valores):"
  grep -E '^(ADMIN_PASSWORD|NEXUS_PASS|REDTEAM_API_KEY|NEXUS_USER|ADMIN_EMAIL)=' /tmp/env_restored_$$ \
    | sed 's/=.*/= presente/'
  echo
  echo "  Para restaurar completo:"
  echo "    cp /tmp/env_restored_$$ .env && chmod 600 .env"
  echo "    rm -f motor_cierre/backend/.auth/password.json"
  echo "    (luego reinicia el stack)"
  ;;

status)
  echo "=== Estado de credenciales ==="
  echo "  Archivo: $ENV"
  if [ -f "$ENV" ]; then
    echo "  Permisos: $(stat -c '%a' "$ENV" 2>/dev/null || stat -f '%A' "$ENV" 2>/dev/null || echo '?')"
    echo
    for key in ADMIN_EMAIL ADMIN_PASSWORD REDTEAM_API_KEY NEXUS_USER NEXUS_PASS; do
      if _has_env_var "$key"; then
        echo "  $key = presente"
      else
        echo "  $key = NO configurado"
      fi
    done
  else
    echo "  .env NO EXISTE. Ejecuta: bash control_claves.sh set"
  fi
  echo
  if [ -f "$BACKUP_FILE" ]; then
    echo "  Respaldo cifrado: $BACKUP_FILE (OK)"
  else
    echo "  Respaldo cifrado: no creado"
  fi
  if [ -f "$AUTH_JSON" ]; then
    echo "  password.json: existe (hash local)"
  else
    echo "  password.json: no existe (el backend lo re-creara desde .env)"
  fi
  ;;

*)
  echo "Uso:"
  echo "  bash control_claves.sh set       # definir tus claves + crear respaldo cifrado"
  echo "  bash control_claves.sh status    # verificar sin revelar valores"
  echo "  bash control_claves.sh restore   # recuperar desde respaldo cifrado"
  exit 1
  ;;

esac
